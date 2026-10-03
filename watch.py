#!/usr/bin/env python3
"""Estate sale watcher. `python watch.py` scans; `python watch.py --digest` builds digest.md."""
import argparse
import io
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state"
sys.path.insert(0, str(ROOT))
from estate import api  # noqa: E402

CATS = {"mirror": "Large mirrors", "cabinet": "Interesting cabinets", "buddhist": "Buddhist pieces"}


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
    hits = load("hits.json", {})
    hits.setdefault("sales", {}); hits.setdefault("hits", {})
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
    for r, d in api.map_pool(get_detail, rows, 6):
        if not d:
            print(f"  sale {r['id']}: no detail, skipped"); continue
        pics = api.pictures(d)
        if not pics:
            print(f"  sale {r['id']} ({r.get('typeName')}): no pictures, skipped"); continue
        meta = api.normalize(d, r)
        hits["sales"][str(meta["id"])] = {k: v for k, v in meta.items() if k != "text"}
        seen["sales"][str(meta["id"])] = meta["end"]
        for p in pics:
            if str(p["id"]) not in seen["pics"]:
                todo.append((meta, p))
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
            for (meta, p), sc in zip((it for it, _ in ok), scores):
                kw_cap = classify.keyword_hits(p["caption"], cfg)
                kw_desc = classify.keyword_hits(meta["text"] + " " + meta["name"], cfg)
                cats = {}
                for c, (s, phrase) in sc.items():
                    boost = cfg["caption_boost"] if c in kw_cap else (cfg["description_boost"] if c in kw_desc else 0)
                    final = min(1.0, s + boost)
                    if final >= cfg["thresholds"][c]:
                        cats[c] = round(final, 3)
                if cats:
                    new_hits += 1
                    hits["hits"][str(p["id"])] = {
                        "sale": meta["id"], "url": p["url"], "thumb": p["thumb"], "caption": p["caption"],
                        "cats": cats, "first_seen": t0,
                        "why": {c: sc[c][1] for c in cats}}
            for (meta, p), im in zip(chunk, imgs):
                if im is not None:
                    seen["pics"][str(p["id"])] = meta["id"]
            done += len(ok)
            print(f"  scored {done}/{len(todo)} ({done / (time.time() - t0s):.1f} img/s), hits so far {new_hits}", flush=True)
            save("seen.json", seen); save("hits.json", hits)  # checkpoint
        print(f"{new_hits} new hits")
    # prune sales that ended > prune_days ago
    cutoff = (date.today() - timedelta(days=cfg["prune_days"])).isoformat()
    old = {s for s, e in seen["sales"].items() if e < cutoff}
    if old:
        seen["pics"] = {p: s for p, s in seen["pics"].items() if str(s) not in old}
        hits["hits"] = {p: h for p, h in hits["hits"].items() if str(h["sale"]) not in old}
        for s in old:
            seen["sales"].pop(s, None); hits["sales"].pop(s, None)
        print(f"pruned {len(old)} ended sales")
    save("seen.json", seen); save("hits.json", hits)


def digest(args):
    from estate import classify
    cfg = classify.load_config()
    hits = load("hits.json", {"sales": {}, "hits": {}})
    digested = set(load("digested.json", []))
    t0 = today()
    by_cat = {c: {} for c in CATS}
    for pid, h in hits["hits"].items():
        sale = hits["sales"].get(str(h["sale"]))
        if not sale or pid in digested or sale["end"] < t0:
            continue
        for c, s in h["cats"].items():
            by_cat[c].setdefault(h["sale"], []).append((s, pid, h))
    cap = cfg["digest_cap_per_category"]
    out, used = [], set()
    total = 0
    for c, title in CATS.items():
        flat = sorted(((s, pid, h) for L in by_cat[c].values() for s, pid, h in L), key=lambda x: -x[0])[:cap]
        if not flat:
            continue
        keep = {pid for _, pid, _ in flat}
        out.append(f"## {title}\n")
        sales = {}
        for s, pid, h in flat:
            sales.setdefault(h["sale"], []).append((s, pid, h))
        for sid, lst in sorted(sales.items(), key=lambda kv: -max(x[0] for x in kv[1])):
            m = hits["sales"][str(sid)]
            tag = " `online auction`" if m.get("online") else ""
            where = ", ".join(x for x in [m.get("address"), m.get("city")] if x)
            out.append(f"### [{m['name'].strip() or 'Sale ' + str(sid)}]({m['page']}){tag}")
            hrs = (f"Online auction, local pickup, ends {m['end']}" if m.get("online")
                   else "; ".join(m.get("hours", [])[:6]) or f"{m['start']} to {m['end']}")
            out.append(f"{where or 'Address not yet posted'}  \n{hrs}\n")
            for s, pid, h in lst:
                cap_txt = f" \"{h['caption']}\"" if h.get("caption") else ""
                out.append(f"[![{c} {s:.2f}]({h['thumb']})]({h['url']})  \n"
                           f"score **{s:.2f}**{cap_txt}\n")
                used.add(pid); total += 1
    dflag = ROOT / "digest.md"
    if not out:
        dflag.unlink(missing_ok=True)
        (ROOT / "digest_count.txt").unlink(missing_ok=True)
        print("no new hits; no digest written")
        return
    head = f"# Estate sale finds, {t0} ({total} hits)\n\nFront Range CO, photos flagged by a local CLIP model. @empireofryan\n\n"
    dflag.write_text(head + "\n".join(out))
    (ROOT / "digest_count.txt").write_text(str(total))
    save("digested.json", sorted(digested | used))
    print(f"digest.md written ({total} hits)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digest", action="store_true")
    ap.add_argument("--max-sales", type=int)
    ap.add_argument("--max-images", type=int)
    a = ap.parse_args()
    (digest if a.digest else scan)(a)


if __name__ == "__main__":
    main()
