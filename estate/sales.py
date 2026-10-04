"""Sale-level "high-end" scoring: accumulate per-photo luxe probabilities, then mix with text signals."""
import heapq

from estate import classify


def new_stats():
    return {"n": 0, "sum": 0.0, "hi": 0, "top": [], "kw": [], "feat": False}


def add_photo(st, prob, pid, p, k, hi=0.8):
    """Fold one scored photo into a sale's stats. top = running top-k [prob, pid, thumb, url, caption]."""
    st["n"] += 1
    st["sum"] = round(st["sum"] + prob, 5)
    st["hi"] += prob >= hi
    row = [round(prob, 3), str(pid), p["thumb"], p["url"], (p.get("caption") or "")[:80]]
    st["top"] = heapq.nlargest(k, st["top"] + [row], key=lambda r: r[0])


def add_text(st, meta_text, captions, cfg, featured=False):
    """Union of luxe keywords found in sale title/description/captions; featured flag sticks."""
    kws = cfg["sale"]["keywords"]
    found = set(st["kw"])
    found.update(classify.match_keywords(meta_text, kws))
    for c in captions:
        found.update(classify.match_keywords(c, kws))
    st["kw"] = sorted(found)
    st["feat"] = bool(st["feat"] or featured)


def score(st, cfg):
    """-> (score, parts dict). Photo evidence (top-K mean + fraction at/above frac_cut) plus capped text bonus."""
    c = cfg["sale"]
    if st["n"] < c["min_photos"]:
        return 0.0, {}
    top = [r[0] for r in st["top"]][: c["top_k"]]
    topk = sum(top) / len(top) if top else 0.0
    frac = st["hi"] / st["n"]
    text = min(c["kw_cap"], c["kw_each"] * len(st["kw"]))
    feat = c["featured_bonus"] if st["feat"] else 0.0
    s = c["w_top"] * topk + c["w_frac"] * frac + text + feat
    return s, {"topk": topk, "frac": frac, "text": text, "feat": feat}
