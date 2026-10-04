"""Run: .venv/bin/python tests/test_links.py"""
import hashlib, hmac, sys, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from estate import email as m

S = "topsecret"
ref = lambda p: hmac.new(S.encode(), p.encode(), hashlib.sha256).hexdigest()[:32]
q = lambda u: dict(urllib.parse.parse_qsl(urllib.parse.urlparse(u).query, keep_blank_values=True))

u = m.vote_url("https://x.app", S, "hit", "123", "art_deco", -1)
d = q(u); assert d["s"] == ref("vote|hit|123|art_deco|-1") and d["c"] == "art_deco" and d["v"] == "-1", d
u = m.vote_url("https://x.app", S, "sale", 99, "", 1)
d = q(u); assert d["s"] == ref("vote|sale|99||1") and d["c"] == "" and d["t"] == "sale", d
assert "&c=&v=1&" in u
u = m.auth_url("https://x.app", S, to="/sale/5", now=1000)
d = q(u); assert d["exp"] == str(1000 + 90 * 86400) and d["s"] == ref(f"auth|{d['exp']}") and d["to"] == "/sale/5", d
assert len(d["s"]) == 32
print("ok")
