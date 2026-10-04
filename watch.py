#!/usr/bin/env python3
"""Estate sale watcher. `python watch.py` scans into Turso; `python watch.py --email [--dry-run]` sends the daily email."""
import argparse
import io
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state"
sys.path.insert(0, str(ROOT))
from estate import api, db as dbm, sales as salemod  # noqa: E402


def load(name, default):
    p = STATE / name
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def save(name, obj):
    STATE.mkdir(exist_ok=True)
    (STATE / name).write_text(json.dumps(obj, separators=(",", ":"), sort_keys=True))


def today():
    return date.today().isoformat()


def scan(args):
    from PIL import Image
    from estate import classify
    cfg = classify.load_config()
    seen = load("seen.json", {})
    seen.setdefault("pics", {}); seen.setdefault("sales", {})
    db = dbm.Turso()  # Turso is the source of truth for sales/hits/embeddings; state/ keeps only dedupe + luxe stats
    sstats = load("sales.json", {})  # per-sale luxe stats, accumulated across runs
    se = cfg["search"]
    rows = api.fetch_list(se["lat"], se["lon"], se["miles"])
    t0 = today()
    rows = [r for r in rows if (api.dt(r.get("lastLocalEndDate")) or datetime.max.replace(year=9999)).strftime("%Y-%m-%d") >= t0]
    rows.sort(key=lambda r: r["lastLocalEndDate"]["_value"] if r.get("lastLocalEndDate") else "9")
    if args.max_sales:
        rows = rows[:args.max_sales]
    print(f"{len(rows)} active sales to check")

    def get_detail(r):
        try:
            return r, api.fetch_detail(r["id"])
        except Exception as e:  # noqa
            print(f"  sale {r['id']}: detail error {e}")
            return r, None

    todo = []  # (sale_meta, pic)
    metas = {}
    for r, d in api.map_pool(get_detail, rows, 6):
        if not d:
            print(f"  sale {r['id']}: no detail, skipped"); continue
        pics = api.pictures(d)
        if not pics:
            print(f"  sale {r['id']} ({r.get('typeName')}): no pictures, skipped"); continue
        meta = api.normalize(d, r)
        feat = any(d.get(k) for k in ("isLocallyFeatured", "isRegionallyFeatured", "isNationallyFeatured"))
        meta["featured"] = bool(feat)
        st = sstats.setdefault(str(meta["id"]), salemod.new_stats())
        salemod.add_text(st, meta["name"] + " " + meta["text"], [], cfg, feat)
        metas[meta["id"]] = {k: v for k, v in meta.items() if k != "text"}
        seen["sales"][str(meta["id"])] = meta["end"]
        for p in pics:
            if str(p["id"]) not in seen["pics"]:
                todo.append((meta, p))
    dbm.upsert_sales(db, metas.values(), sstats, cfg)  # sale rows must exist before their hits
    cap = args.max_images or cfg["max_images_per_run"]
    if len(todo) > cap:
        print(f"{len(todo)} new photos, capped to {cap} this run")
        todo = todo[:cap]
    print(f"{len(todo)} new photos to score")
    if todo:
        clf = classify.Classifier(cfg)

        def fetch(item):
            try:
                r = api.get(item[1]["thumb"])
                return Image.open(io.BytesIO(r.content)).convert("RGB") if r.status_code == 200 else None
            except Exception:  # noqa
                return None
        import time
        new_hits = 0
        CH = 256
        t0s = time.time(); done = 0
        for i in range(0, len(todo), CH):
            chunk = todo[i:i + CH]
            imgs = api.map_pool(fetch, chunk, 6)
            ok = [(it, im) for it, im in zip(chunk, imgs) if im is not None]
            scores = clf.score([im for _, im in ok]) if ok else []
            stmts = []
            for (meta, p), sc in zip((it for it, _ in ok), scores):
                st = sstats.setdefault(str(meta["id"]), salemod.new_stats())
                if "_luxe" in sc:
                    salemod.add_photo(st, sc["_luxe"][0], p["id"], p, cfg["sale"]["top_k"], cfg["sale"]["frac_cut"])
                    salemod.add_text(st, "", [p["caption"]], cfg)
                kw_cap = classify.keyword_hits(p["caption"], cfg)
                kw_desc = classify.keyword_hits(meta["text"] + " " + meta["name"], cfg)
                cats = {}
                for c, (s, phrase) in ((k, v) for k, v in sc.items() if not k.startswith("_")):
                    boost = cfg["caption_boost"] if c in kw_cap else (cfg["description_boost"] if c in kw_desc else 0)
                    final = min(1.0, s + boost)
                    if final >= cfg["thresholds"][c]:
                        cats[c] = round(final, 3)
                if cats:
                    new_hits += 1
                    rec = {"sale": meta["id"], "url": p["url"], "thumb": p["thumb"], "caption": p["caption"],
                           "cats": cats, "first_seen": t0, "why": {c: sc[c][1] for c in cats}}
                    stmts += dbm.hit_stmts(p["id"], rec)
                    stmts.append(dbm.emb_stmt(p["id"], sc["_emb"]))  # embeddings for HIT photos only
            # write to Turso BEFORE marking photos seen, so a failed write is retried next run
            if stmts:
                db.batch(stmts)
            dbm.upsert_sales(db, [metas[m["id"]] for m in {it[0]["id"]: it[0] for it, _ in ok}.values()], sstats, cfg)
            for (meta, p), im in zip(chunk, imgs):
                if im is not None:
                    seen["pics"][str(p["id"])] = meta["id"]
            done += len(ok)
            print(f"  scored {done}/{len(todo)} ({done / (time.time() - t0s):.1f} img/s), hits so far {new_hits}", flush=True)
            save("seen.json", seen); save("sales.json", sstats)  # checkpoint
        print(f"{new_hits} new hits")
    # prune sales that ended > prune_days ago
    cutoff = (date.today() - timedelta(days=cfg["prune_days"])).isoformat()
    old = {s for s, e in seen["sales"].items() if e < cutoff}
    if old:
        seen["pics"] = {p: s for p, s in seen["pics"].items() if str(s) not in old}
        for s in old:
            seen["sales"].pop(s, None); sstats.pop(s, None)
        print(f"pruned {len(old)} ended sales")
    save("seen.json", seen); save("sales.json", sstats)
    dbm.upsert_sales(db, metas.values(), sstats, cfg)  # refresh sale score / standout from the final stats
    from estate import taste
    taste.apply(db, cfg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", action="store_true", help="send the daily email of never-emailed items")
    ap.add_argument("--digest", action="store_true", help="deprecated alias for --email")
    ap.add_argument("--dry-run", action="store_true", help="with --email: write email.html/email.txt, send nothing, mark nothing")
    ap.add_argument("--max-sales", type=int)
    ap.add_argument("--max-images", type=int)
    ap.add_argument("--state-dir", help="use this dir for state/*.json (testing)")
    a = ap.parse_args()
    if a.state_dir:
        global STATE
        STATE = Path(a.state_dir).resolve()
    if a.email or a.digest:
        from estate import email as mail
        mail.run(dry_run=a.dry_run, out_dir=ROOT)
    else:
        scan(a)


if __name__ == "__main__":
    main()
