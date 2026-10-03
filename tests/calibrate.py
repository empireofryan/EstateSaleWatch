"""Calibrate mirror threshold on labeled photos; eyeball cabinet/buddhist on a random set.
Usage: python tests/calibrate.py [--model ViT-B-32:laion2b_s34b_b79k ...] [--keep]
Downloads thumbnails only into tests/_work (gitignored, deleted unless --keep)."""
import argparse, json, random, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from estate import api, classify  # noqa: E402

WORK = ROOT / "tests" / "_work"
TRUE = [(5097639, 45), (5096502, 118), (5096502, 21), (5096502, 57), (5092440, 56), (5092440, 57), (5099466, 228)]
FALSE = [(5099652, 242), (5101206, 7), (5101206, 60), (5101206, 141), (5101206, 50),
         (5092440, 172), (5092440, 173), (5092440, 176), (5099466, 325)]
SALES = sorted({s for s, _ in TRUE + FALSE})
N_RANDOM = 200


def dl(url, path):
    if path.exists():
        return True
    r = api.get(url)
    if r.status_code != 200:
        return False
    path.write_bytes(r.content)
    return True


def build_set():
    WORK.mkdir(parents=True, exist_ok=True)
    pics = {}
    for sid in SALES:
        d = api.fetch_detail(sid)
        if not d or not d.get("pictures"):
            print(f"!! sale {sid}: detail unavailable (ended/removed?)")
            continue
        pics[sid] = {p["order"]: p for p in api.pictures(d)}
        print(f"sale {sid}: {len(pics[sid])} pictures")
    items = []  # (label, key, path, url)
    labeled = set()
    for lab, lst in (("true", TRUE), ("false", FALSE)):
        for sid, o in lst:
            p = pics.get(sid, {}).get(o)
            if not p:
                print(f"!! missing {sid}#{o}"); continue
            labeled.add(p["id"])
            items.append((lab, f"{sid}#{o}", p))
    rest = [(sid, p) for sid, ps in pics.items() for p in ps.values() if p["id"] not in labeled]
    random.Random(7).shuffle(rest)
    for sid, p in rest[:N_RANDOM]:
        items.append(("bg", f"{sid}#{p['order']}", p))
    def job(it):
        lab, key, p = it
        path = WORK / f"{p['id']}.jpg"
        return path if dl(p["thumb"], path) else None
    paths = api.map_pool(job, items, 6)
    return [(l, k, p, pa) for (l, k, p), pa in zip(items, paths) if pa]


def evaluate(items, spec, cfg):
    name, pre = spec.split(":")
    clf = classify.Classifier(cfg, name, pre)
    imgs = [classify.load_image(x[3]) for x in items]
    t = time.time(); sc = clf.score(imgs); dt = time.time() - t
    print(f"\n=== {spec}: {len(imgs)} imgs in {dt:.1f}s = {len(imgs)/dt:.1f} img/s")
    return sc, len(imgs) / dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", default=None)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    cfg = classify.load_config()
    specs = a.model or ["ViT-B-32:laion2b_s34b_b79k", "ViT-B-16-SigLIP:webli"]
    items = build_set()
    print(f"{len(items)} images ({sum(i[0]=='true' for i in items)} true, "
          f"{sum(i[0]=='false' for i in items)} false, {sum(i[0]=='bg' for i in items)} bg)")
    allres = {}
    for spec in specs:
        sc, ips = evaluate(items, spec, cfg)
        allres[spec] = (sc, ips)
        m = [s["mirror"][0] for s in sc]
        print("true mirrors:")
        for it, s in zip(items, sc):
            if it[0] == "true":
                print(f"  {it[1]:12s} {s['mirror'][0]:.3f}  ({s['mirror'][1]})")
        print("false (labeled) scores:", ", ".join(f"{it[1]}={s['mirror'][0]:.3f}" for it, s in zip(items, sc) if it[0] == "false"))
        print("top-8 bg by mirror score:")
        bg = sorted([(s["mirror"][0], it) for it, s in zip(items, sc) if it[0] == "bg"], reverse=True)[:8]
        for v, it in bg:
            print(f"  {it[1]:12s} {v:.3f} {it[2]['thumb']}")
        nt = sum(i[0] == "true" for i in items); nneg = sum(i[0] != "true" for i in items)
        print("thr  recall  FP(labeled+bg of %d)  FP/1000" % nneg)
        for thr in [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6]:
            rec = sum(v >= thr for it, v in zip(items, m) if it[0] == "true")
            fp = sum(v >= thr for it, v in zip(items, m) if it[0] != "true")
            print(f"{thr:.2f}  {rec}/{nt}    {fp:3d}   {1000*fp/nneg:.0f}")
    # buddhist / cabinet eyeball with the first model listed
    spec = specs[0]; sc = allres[spec][0]
    bgi = [(i, it) for i, it in enumerate(items) if it[0] == "bg"]
    for cat in ("cabinet", "buddhist"):
        top = sorted(bgi, key=lambda x: -sc[x[0]][cat][0])[:10]
        print(f"\n--- top-10 {cat} ({spec}) ---")
        for rank, (i, it) in enumerate(top, 1):
            print(f"{rank:2d} {sc[i][cat][0]:.3f} {sc[i][cat][1]:45s} {it[2]['url']}")
        (WORK / f"top_{cat}.txt").write_text("\n".join(str(it[3]) for _, it in top))
    if not a.keep:
        pass  # cleanup done by caller after viewing contact sheets
    print("\nwork dir:", WORK)


if __name__ == "__main__":
    main()
