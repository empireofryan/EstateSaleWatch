#!/usr/bin/env python3
"""One-off: load state/{hits,sales,digested,standouts}.json into Turso and embed existing hit photos.
Run: HF_HOME=$PWD/.cache/hf .venv/bin/python scripts/migrate_to_turso.py   (idempotent; safe to re-run)"""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402
from estate import api, classify, db as dbm  # noqa: E402

EMAILED = "2026-10-03"


def load(name, default):
    try:
        return json.loads((ROOT / "state" / name).read_text())
    except (OSError, ValueError):
        return default


def main():
    cfg = classify.load_config()
    hits = load("hits.json", {"sales": {}, "hits": {}})
    sstats = load("sales.json", {})
    digested = set(load("digested.json", []))
    standouts = {str(x) for x in load("standouts.json", [])}
    db = dbm.Turso()

    # sales (preserve first_seen / emailed_at on re-run via the shared upsert)
    metas = list(hits["sales"].values())
    dbm.upsert_sales(db, metas, sstats, cfg)
    if standouts:
        db.batch([("UPDATE sales SET emailed_at=? WHERE id=? AND emailed_at IS NULL", [EMAILED, int(s)]) for s in standouts])

    # hits
    stmts = []
    for pid, h in hits["hits"].items():
        stmts += dbm.hit_stmts(pid, h, EMAILED if pid in digested else None)
    db.batch(stmts)

    # embeddings for hit photos that lack one
    have = {r["pic_id"] for r in db.query("SELECT pic_id FROM embeddings")}
    todo = [(pid, h["thumb"]) for pid, h in hits["hits"].items() if pid not in have]
    n_emb = 0
    if todo:
        clf = classify.Classifier(cfg)

        def fetch(it):
            try:
                r = api.get(it[1])
                return Image.open(io.BytesIO(r.content)).convert("RGB") if r.status_code == 200 else None
            except Exception:  # noqa
                return None
        for i in range(0, len(todo), 64):
            chunk = todo[i:i + 64]
            imgs = api.map_pool(fetch, chunk, 6)
            ok = [(it, im) for it, im in zip(chunk, imgs) if im is not None]
            if not ok:
                continue
            sc = clf.score([im for _, im in ok])
            db.batch([dbm.emb_stmt(it[0], s["_emb"]) for (it, _), s in zip(ok, sc)])
            n_emb += len(ok)
            print(f"  embedded {n_emb}/{len(todo)}", flush=True)
    c = {t: db.query(f"SELECT COUNT(*) n FROM {t}")[0]["n"] for t in ("sales", "hits", "embeddings")}
    em = db.query("SELECT COUNT(*) n FROM hits WHERE emailed_at IS NOT NULL")[0]["n"]
    so = db.query("SELECT COUNT(*) n FROM sales WHERE standout=1")[0]["n"]
    print(f"migrated: sales={c['sales']} (standout={so}, standouts.json ids={len(standouts)}), hits={c['hits']} "
          f"(emailed={em}), embeddings={c['embeddings']} (+{n_emb} new)")


if __name__ == "__main__":
    main()
