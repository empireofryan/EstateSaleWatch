"""Daily email via Resend: only never-emailed items, with signed one-tap vote links."""
import hashlib
import hmac
import html
import json
import os
import time
import urllib.parse
from datetime import date, datetime

import requests

from estate import db as dbm

CATS = [("art_deco", "Art Deco"), ("mirror", "Mirrors"), ("buddhist", "Buddhist"), ("cabinet", "Cabinets")]
CAP = 25
MAX_HTML = 95_000  # Gmail clips messages over ~102KB
INK, MUTED, ACCENT, BG, CARD, LINE = "#1d2b2a", "#667472", "#1f5c57", "#e9eeec", "#ffffff", "#d5dedb"


# ---- signed links (the web app verifies these identically) ----
def sig(payload, secret):
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def vote_url(app, secret, t, id_, cat, v):
    c = cat if t == "hit" else ""
    s = sig(f"vote|{t}|{id_}|{c}|{v}", secret)
    return f"{app}/api/v?t={t}&id={urllib.parse.quote(str(id_))}&c={urllib.parse.quote(c)}&v={v}&s={s}"


def auth_url(app, secret, to=None, now=None, days=90):
    exp = int((now or time.time()) + days * 86400)
    u = f"{app}/api/auth?exp={exp}&s={sig(f'auth|{exp}', secret)}"
    return u + "&to=" + urllib.parse.quote(to, safe="/") if to else u


# ---- formatting ----
def _d(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d")
    except (TypeError, ValueError):
        return iso or ""


def when(s):
    if "Online" in (s.get("type_name") or "") or "Auction" in (s.get("type_name") or ""):
        return f"ends {_d(s['end_date'])}"
    if s["start_date"] == s["end_date"]:
        return _d(s["start_date"])
    return f"{_d(s['start_date'])} to {_d(s['end_date'])}"


def is_online(s):
    return "Auction" in (s.get("type_name") or "") or "Online" in (s.get("type_name") or "")


def e(x):
    return html.escape(str(x or ""), quote=True)


def vote_row(app, secret, t, id_, cat):
    return (f'<a class="b y" href="{e(vote_url(app, secret, t, id_, cat, 1))}">&#128077;</a>'
            f'<a class="b n" href="{e(vote_url(app, secret, t, id_, cat, -1))}">&#128078;</a>')


# ---- data ----
def fetch(db, today):
    sales = db.query("""SELECT * FROM sales WHERE standout=1 AND emailed_at IS NULL AND end_date>=?
                        ORDER BY score DESC""", [today])
    hits = {}
    for key, _ in CATS:
        hits[key] = db.query("""SELECT h.*, s.name sale_name, s.city, s.start_date, s.end_date, s.type_name
                                FROM hits h JOIN sales s ON s.id=h.sale_id
                                WHERE h.category=? AND h.emailed_at IS NULL AND h.hidden=0 AND s.end_date>=?
                                ORDER BY h.score DESC LIMIT ?""", [key, today, CAP])
    return sales, hits


# ---- render ----
def render(sales, hits, app, secret, today):
    n = len(sales) + sum(len(v) for v in hits.values())
    open_top = auth_url(app, secret)
    pretty = datetime.strptime(today, "%Y-%m-%d").strftime("%a %b %-d")
    P = []
    P.append(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Estate finds</title><style>
.b{{display:inline-block;font:600 14px Arial,sans-serif;padding:9px 0;width:46%;text-align:center;border-radius:6px;text-decoration:none}}
.y{{background:#dcebe4;color:#1f5c57;margin-right:2%}}.n{{background:#eceeee;color:#667472}}
.c{{background:#fff;border:1px solid #d5dedb;border-radius:8px}}.i{{display:block;width:100%;height:auto;border-radius:5px}}
.t{{font-size:13px;line-height:1.3;padding:7px 0 3px;min-height:34px}}.m{{font-size:12px;line-height:1.3;color:#667472;padding-bottom:7px}}
.m a{{color:#1f5c57;text-decoration:none;font-weight:700}}
</style></head><body style="margin:0;padding:0;background:{BG}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:12px 8px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;font-family:Arial,Helvetica,sans-serif;color:{INK}">
<tr><td style="padding:8px 4px 14px"><div style="font:700 26px Georgia,serif;color:{ACCENT}">Estate finds</div>
<div style="font-size:14px;color:{MUTED};padding-top:4px">{n} new &middot; {pretty} &middot; <a href="{e(open_top)}" style="color:{ACCENT};font-weight:700">Open in app</a></div></td></tr>""")
    if sales:
        P.append(f'<tr><td style="padding:10px 4px 6px;font:700 13px Arial;letter-spacing:1px;color:{MUTED}">STANDOUT SALES</td></tr>')
        for s in sales:
            top = json.loads(s.get("top_json") or "[]")[:5]
            strip = "".join(f'<td width="20%" style="padding:0 2px 0 0"><a href="{e(t["url"])}"><img class="i" src="{e(t["thumb"])}" width="100%" height="72" style="height:72px;object-fit:cover" alt=""></a></td>'
                            for t in top)
            tag = f' <span style="background:{ACCENT};color:#fff;font-size:11px;padding:2px 6px;border-radius:3px">ONLINE AUCTION</span>' if is_online(s) else ""
            deep = auth_url(app, secret, to=f"/sale/{s['id']}")
            P.append(f"""<tr><td style="padding:0 0 12px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="c"><tr><td style="padding:14px">
<a href="{e(s['url'])}" style="font:700 18px Georgia,serif;color:{INK};text-decoration:none">{e(s['name'] or 'Sale ' + str(s['id']))}</a>{tag}
<div style="font-size:13px;color:{MUTED};padding:4px 0 8px">{e(s['city'])} &middot; {e(when(s))}</div>
<div style="font-size:14px;line-height:1.4;padding-bottom:10px">{e(s['why'])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{strip}</tr></table>
<div style="padding-top:12px">{vote_row(app, secret, 'sale', s['id'], '')}</div>
<div style="padding-top:8px;font-size:12px"><a href="{e(deep)}" style="color:{ACCENT}">Open in app</a></div>
</td></tr></table></td></tr>""")
    for key, label in CATS:
        rows = hits[key]
        if not rows:
            continue
        P.append(f'<tr><td style="padding:14px 4px 6px;font:700 13px Arial;letter-spacing:1px;color:{MUTED}">{label.upper()} &middot; {len(rows)}</td></tr>')
        P.append('<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">')
        for i in range(0, len(rows), 2):
            P.append("<tr>")
            for h in rows[i:i + 2]:
                cap = (h["caption"] or "").strip()
                cap = cap[:70] + ("..." if len(cap) > 70 else "")
                P.append(f"""<td width="50%" valign="top" style="padding:0 4px 8px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="c"><tr><td style="padding:8px">
<a href="{e(h['url'])}"><img class="i" src="{e(h['thumb'])}" width="100%" alt=""></a>
<div class="t">{e(cap) or '&nbsp;'}</div>
<div class="m"><a href="{e(h['sale_url'])}">{e((h['sale_name'] or '').strip()[:48])}</a><br>{e(h['city'])} &middot; {e(when(h))}</div>
{vote_row(app, secret, 'hit', h['pic_id'], key)}
</td></tr></table></td>""")
            if len(rows[i:i + 2]) == 1:
                P.append('<td width="50%"></td>')
            P.append("</tr>")
        P.append("</table></td></tr>")
    P.append(f"""<tr><td align="center" style="padding:18px 4px 10px"><a href="{e(open_top)}" style="display:inline-block;background:{ACCENT};color:#fff;text-decoration:none;font:700 15px Arial;padding:12px 28px;border-radius:6px">Open in app</a>
<div style="font-size:11px;color:{MUTED};padding-top:12px">Votes teach the filter what you like. Links are personal; don't forward.</div></td></tr>
</table></td></tr></table></body></html>""")
    return n, "".join(P), pretty


def render_text(sales, hits, app, secret):
    L = ["Open in app: " + auth_url(app, secret), ""]
    if sales:
        L.append("STANDOUT SALES")
        for s in sales:
            L += [f"- {s['name']} ({s['city']}, {when(s)}){' [online auction]' if is_online(s) else ''}", f"  {s['why']}", f"  {s['url']}",
                  f"  like: {vote_url(app, secret, 'sale', s['id'], '', 1)}", f"  pass: {vote_url(app, secret, 'sale', s['id'], '', -1)}"]
        L.append("")
    for key, label in CATS:
        if hits[key]:
            L.append(label.upper())
        for h in hits[key]:
            L += [f"- {h['caption'] or '(no caption)'} | {h['sale_name']} ({h['city']}, {when(h)})", f"  {h['url']}",
                  f"  like: {vote_url(app, secret, 'hit', h['pic_id'], key, 1)}", f"  pass: {vote_url(app, secret, 'hit', h['pic_id'], key, -1)}"]
        if hits[key]:
            L.append("")
    return "\n".join(L)


def run(dry_run=False, out_dir=None):
    app, secret = dbm.need_env("APP_URL", "APP_SECRET")
    app = app.rstrip("/")
    db = dbm.Turso()
    today = date.today().isoformat()
    sales, hits = fetch(db, today)
    # sale page links for hit cards
    smap = {r["id"]: r["url"] for r in db.query("SELECT id,url FROM sales")}
    for rows in hits.values():
        for h in rows:
            h["sale_url"] = smap.get(h["sale_id"], "")
    n, body, pretty = render(sales, hits, app, secret, today)
    while len(body.encode()) > MAX_HTML and any(hits.values()):  # Gmail clips >102KB; leftovers roll to tomorrow
        big = max(hits, key=lambda k: len(hits[k]))
        hits[big].pop()
        n, body, pretty = render(sales, hits, app, secret, today)
    if n == 0:
        print("nothing new; no email")
        return
    text = render_text(sales, hits, app, secret)
    subject = f"Estate finds · {n} new · {pretty}"
    if dry_run:
        from pathlib import Path
        out = Path(out_dir or ".")
        (out / "email.html").write_text(body)
        (out / "email.txt").write_text(text)
        print(f"dry run: {subject} ({len(sales)} sales, {sum(len(v) for v in hits.values())} hits) -> {out / 'email.html'}")
        return
    key, frm, to = dbm.need_env("RESEND_API_KEY", "EMAIL_FROM", "EMAIL_TO")
    r = requests.post("https://api.resend.com/emails", timeout=60,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"from": frm, "to": [x.strip() for x in to.split(",") if x.strip()],
                            "subject": subject, "html": body, "text": text})
    if r.status_code >= 300:
        raise SystemExit(f"resend failed: HTTP {r.status_code} {r.text[:300]}")
    t = dbm.now_iso()
    stmts = [("UPDATE sales SET emailed_at=? WHERE id=?", [t, s["id"]]) for s in sales]
    stmts += [("UPDATE hits SET emailed_at=? WHERE pic_id=? AND category=?", [t, h["pic_id"], k])
              for k, rows in hits.items() for h in rows]
    db.batch(stmts)
    print(f"sent: {subject}; marked {len(stmts)} items emailed")
