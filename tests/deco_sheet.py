"""Contact sheet of top art_deco hits among ~600 random photos of the high-end calibration sales.
Usage: python tests/deco_sheet.py [N=20]   (needs tests/_work/sales_scores.json from calibrate_sales.py)"""
import json, random, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
W = ROOT / "tests" / "_work"
d = json.loads((W / "sales_scores.json").read_text())
pool = [dict(r, sale=s) for s in ("5097639", "5069280", "5078349", "5090493", "5097672") for r in d.get(s, {}).get("photos", [])]
random.Random(3).shuffle(pool)
pool = pool[:600]
top = sorted(pool, key=lambda r: -r["cats"]["art_deco"])[: int(sys.argv[1]) if len(sys.argv) > 1 else 20]
for i, r in enumerate(top, 1):
    print(i, f"{r['cats']['art_deco']:.3f}", r["sale"], r["phr"]["art_deco"], "|", r["cap"][:50])
print("count >=0.85:", sum(r["cats"]["art_deco"] >= .85 for r in pool), "of", len(pool))
fs = [str(W / "thumbs" / f"{r['id']}.jpg") for r in top]
subprocess.run(["montage", *fs, "-tile", "5x4", "-geometry", "200x150+2+2", str(W / "deco_top.jpg")])
