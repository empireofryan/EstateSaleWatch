"""Turso (libSQL) over its HTTP pipeline API, plus the upsert helpers the scanner/migration share."""
import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

from estate import sales as salemod

ROOT = Path(__file__).resolve().parent.parent
CHUNK = 200


def load_env(path=ROOT / ".env.local"):
    """Load KEY=VALUE lines into os.environ (never overriding real env vars). Silent if the file is absent."""
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        return
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need_env(*names):
    load_env()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit("missing env: " + ", ".join(missing))
    return [os.environ[n] for n in names]


def _arg(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        return {"type": "blob", "base64": base64.b64encode(bytes(v)).decode()}
    return {"type": "text", "value": str(v)}


def _val(c):
    t = c.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(c["value"])
    if t == "float":
        return float(c["value"])
    if t == "blob":
        return base64.b64decode(c["base64"] + "=" * (-len(c["base64"]) % 4))
    return c.get("value")


class Turso:
    def __init__(self, url=None, token=None):
        if not url:
            url, token = need_env("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN")
        self.base = re.sub(r"^libsql://", "https://", url).rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    def _pipeline(self, stmts):
        reqs = [{"type": "execute", "stmt": {"sql": q, "args": [_arg(a) for a in args]}} for q, args in stmts]
        reqs.append({"type": "close"})
        last = None
        for attempt in range(3):
            try:
                r = self.s.post(self.base + "/v2/pipeline", data=json.dumps({"requests": reqs}), timeout=60)
                if r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                break
            except requests.RequestException as e:
                last = e
        else:
            raise RuntimeError(f"turso request failed: {type(last).__name__}")
        if r.status_code != 200:
            raise RuntimeError(f"turso HTTP {r.status_code}: {r.text[:300]}")
        out = []
        for i, res in enumerate(r.json()["results"][:len(stmts)]):
            if res.get("type") == "error":
                raise RuntimeError(f"turso statement error: {res['error'].get('message')} :: {stmts[i][0][:80]}")
            out.append(res["response"]["result"])
        return out

    def batch(self, stmts):
        """Run [(sql, args)] in pipelines of ~200. Returns raw results."""
        out = []
        for i in range(0, len(stmts), CHUNK):
            out.extend(self._pipeline(stmts[i:i + CHUNK]))
        return out

    def execute(self, sql, args=()):
        return self._pipeline([(sql, list(args))])[0]

    def query(self, sql, args=()):
        r = self.execute(sql, args)
        names = [c["name"] for c in r["cols"]]
        return [dict(zip(names, (_val(c) for c in row))) for row in r["rows"]]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_days(hours, start):
    """['Thu Oct 1 9am-3pm', ...] -> [{date: ISO, hours: '9am-3pm'}] (year taken from the sale start date)."""
    out = []
    yr = int(start[:4]) if start and start[:4].isdigit() else datetime.now().year
    for h in hours or []:
        m = re.match(r"^\w{3} (\w{3}) (\d+) ?(.*)$", h)
        if not m:
            continue
        try:
            d = datetime.strptime(f"{yr} {m.group(1)} {m.group(2)}", "%Y %b %d").strftime("%Y-%m-%d")
        except ValueError:
            continue
        out.append({"date": d, "hours": m.group(3)})
    return out


SALE_SQL = """INSERT INTO sales(id,name,org,city,state,address,url,type_name,start_date,end_date,dates_json,
  score,standout,why,top_json,first_seen,updated_at,emailed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)
ON CONFLICT(id) DO UPDATE SET name=excluded.name, org=excluded.org, city=excluded.city, state=excluded.state,
  address=excluded.address, url=excluded.url, type_name=excluded.type_name, start_date=excluded.start_date,
  end_date=excluded.end_date, dates_json=excluded.dates_json, score=excluded.score, standout=excluded.standout,
  why=excluded.why, top_json=excluded.top_json, updated_at=excluded.updated_at"""

HIT_SQL = """INSERT INTO hits(pic_id,category,sale_id,score,model_score,caption,thumb,url,why,first_seen,hidden,emailed_at)
VALUES(?,?,?,?,?,?,?,?,?,?,0,?)
ON CONFLICT(pic_id,category) DO UPDATE SET sale_id=excluded.sale_id, model_score=excluded.model_score,
  score=CASE WHEN hits.emailed_at IS NULL THEN excluded.score ELSE hits.score END,
  caption=excluded.caption, thumb=excluded.thumb, url=excluded.url, why=excluded.why"""

EMB_SQL = "INSERT INTO embeddings(pic_id,emb) VALUES(?,?) ON CONFLICT(pic_id) DO UPDATE SET emb=excluded.emb"


def sale_stmt(meta, st, cfg, emailed_at=None):
    """Build the sales upsert for one sale meta + its luxe stats (st may be None)."""
    sc = cfg["sale"]
    score, parts = salemod.score(st, cfg) if st else (0.0, {})
    standout = int(score >= sc["threshold"])
    why = ""
    if st and parts:
        why = f"{parts['frac']:.0%} of {st['n']} photos look high end"
        if st.get("feat"):
            why += ", featured listing"
        if st.get("kw"):
            why += "; " + ", ".join(st["kw"][:6])
    top = [{"pic_id": r[1], "thumb": r[2], "url": r[3], "p": r[0]} for r in (st or {}).get("top", [])[:8]]
    days = meta.get("days") or parse_days(meta.get("hours"), meta.get("start"))
    t = now_iso()
    return (SALE_SQL, [int(meta["id"]), meta.get("name", "").strip(), meta.get("org", ""), meta.get("city", ""), "CO",
                       meta.get("address", ""), meta.get("page", ""), meta.get("typeName") or "",
                       meta.get("start"), meta.get("end"), json.dumps(days), round(score, 4), standout, why,
                       json.dumps(top), t, t])


def upsert_sales(db, metas, sstats, cfg):
    db.batch([sale_stmt(m, sstats.get(str(m["id"])), cfg) for m in metas])


def hit_stmts(pic_id, h, emailed_at=None):
    """h = the hits.json-shaped record {sale,url,thumb,caption,cats,first_seen,why}; one row per category."""
    return [(HIT_SQL, [str(pic_id), c, int(h["sale"]), s, s, h.get("caption", ""), h["thumb"], h["url"],
                       (h.get("why") or {}).get(c, ""), h.get("first_seen"), emailed_at])
            for c, s in h["cats"].items()]


def emb_stmt(pic_id, vec):
    """vec: float32 numpy, L2-normalized -> float16 LE blob."""
    import numpy as np
    v = np.asarray(vec, dtype=np.float32)
    v = v / (np.linalg.norm(v) or 1.0)
    return (EMB_SQL, [str(pic_id), v.astype("<f2").tobytes()])


def blob_to_vec(b):
    import numpy as np
    return np.frombuffer(b, dtype="<f2").astype(np.float32)
