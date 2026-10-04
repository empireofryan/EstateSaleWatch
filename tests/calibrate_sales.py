"""Calibrate the sale-level high-end score on labeled sales (scored fully from the detail API).
Usage: python tests/calibrate_sales.py [--rescore] [--max-photos 400]
Thumbnails cached in tests/_work/thumbs (gitignored; delete when done). Per-photo scores cached in
tests/_work/sales_scores.json so threshold/weight tuning is instant; --rescore redoes the model pass."""
import argparse, io, json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from estate import api, classify, sales  # noqa: E402

WORK = ROOT / "tests" / "_work"
THUMBS = WORK / "thumbs"
CACHE = WORK / "sales_scores.json"
HIGH = [5097639, 5069280, 5078349, 5090493, 5097672]
ORDINARY = [5099466, 5077578, 5100930, 5071086, 5085399, 5101338, 5096502]


def thumb_path(pid):
    return THUMBS / f"{pid}.jpg"


def fetch_thumb(p):
    path = thumb_path(p["id"])
    if not path.exists():
        r = api.get(p["thumb"])
        if r.status_code != 200:
            return None
        path.write_bytes(r.content)
    return path


def build(args, cfg):
    THUMBS.mkdir(parents=True, exist_ok=True)
    clf = classify.Classifier(cfg)
    out = {}
    for sid in HIGH + ORDINARY:
        d = api.fetch_detail(sid)
        if not d or not d.get("pictures"):
            print(f"!! sale {sid}: not available from API"); continue
        meta = api.normalize(d)
        pics = api.pictures(d)
        total = len(pics)
        if total > args.max_photos:
            random.Random(sid).shuffle(pics); pics = pics[:args.max_photos]
        paths = api.map_pool(fetch_thumb, [dict(p, id=p["id"]) for p in pics], 6)
        ok = [(p, pa) for p, pa in zip(pics, paths) if pa]
        rows = []
        for i in range(0, len(ok), 128):
            ch = ok[i:i + 128]
            sc = clf.score([classify.load_image(pa) for _, pa in ch])
            for (p, _), s in zip(ch, sc):
                rows.append({"id": p["id"], "thumb": p["thumb"], "url": p["url"], "cap": p["caption"],
                             "luxe": s["_luxe"][0], "luxe_phrase": s["_luxe"][1],
                             "cats": {c: s[c][0] for c in clf.cats}, "phr": {c: s[c][1] for c in clf.cats}})
        out[sid] = {"name": meta["name"], "text": meta["text"], "total": total, "online": meta["online"],
                    "feat": any(d.get(k) for k in ("isLocallyFeatured", "isRegionallyFeatured", "isNationallyFeatured")),
                    "photos": rows}
        print(f"sale {sid}: {len(rows)}/{total} scored  {meta['name'][:60]}", flush=True)
    CACHE.write_text(json.dumps(out))
    return out


def sale_stats(sd, cfg):
    st = sales.new_stats()
    for r in sd["photos"]:
        sales.add_photo(st, r["luxe"], r["id"], {"thumb": r["thumb"], "url": r["url"], "caption": r["cap"]}, cfg["sale"]["top_k"], cfg["sale"]["frac_cut"])
    sales.add_text(st, sd["name"] + " " + sd["text"], [r["cap"] for r in sd["photos"]], cfg, sd["feat"])
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--max-photos", type=int, default=400)
    a = ap.parse_args()
    cfg = classify.load_config()
    data = None
    if CACHE.exists() and not a.rescore:
        data = {int(k): v for k, v in json.loads(CACHE.read_text()).items()}
    else:
        data = build(a, cfg)
    print(f"\n{'sale':8s} {'lab':4s} {'n':>4s} {'topK':>5s} {'frac':>5s} {'text':>5s} {'SCORE':>6s}  kw / name")
    rows = []
    for sid in HIGH + ORDINARY:
        if sid not in data:
            continue
        st = sale_stats(data[sid], cfg)
        s, parts = sales.score(st, cfg)
        rows.append((sid, "HIGH" if sid in HIGH else "ord", s))
        print(f"{sid:<8d} {rows[-1][1]:4s} {st['n']:4d} {parts['topk']:5.2f} {parts['frac']:5.2f} {parts['text']:5.2f} {s:6.3f}  "
              f"{','.join(st['kw'])[:50]} | {data[sid]['name'][:40]}")
    hi = [s for _, l, s in rows if l == "HIGH"]; lo = [s for _, l, s in rows if l == "ord"]
    print(f"\nmin HIGH {min(hi):.3f}  max ordinary {max(lo):.3f}  threshold in config: {cfg['sale']['threshold']}")


if __name__ == "__main__":
    main()
