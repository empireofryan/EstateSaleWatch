"""Learned taste: per category, logistic regression on SigLIP embeddings of voted hits -> p_like.
Applied to every not-yet-emailed hit each run (hidden if p_like is low, score blended with the model score)."""
import numpy as np

MIN_LABELED, MIN_EACH = 12, 4
HIDE_BELOW = 0.25
BLEND = 0.5
C = 10.0  # embeddings are unit-norm, so C=1 squashes p_like toward 0.5; 10 is still well regularized


def _fit(X, y):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=C, max_iter=1000, class_weight="balanced").fit(X, y)


def _cv_acc(X, y):
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    k = min(5, int(min((y == 1).sum(), (y == 0).sum())))
    if k < 2:
        return None
    return float(cross_val_score(_fit_est(), X, y, cv=StratifiedKFold(k, shuffle=True, random_state=0)).mean())


def _fit_est():
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=C, max_iter=1000, class_weight="balanced")


def apply(db, cfg=None, log=print):
    from estate.db import blob_to_vec
    cats = list((cfg or {}).get("prompts", {})) or ["mirror", "cabinet", "buddhist", "art_deco"]
    # sale thumbs are stored only (no model yet)
    sv = db.query("SELECT COUNT(*) n FROM votes WHERE target_type='sale' AND vote IS NOT NULL")[0]["n"]
    log(f"taste: {sv} sale votes stored (not modelled)")
    for cat in cats:
        lab = db.query("""SELECT v.vote, e.emb FROM votes v JOIN embeddings e ON e.pic_id=v.target_id
                          WHERE v.target_type='hit' AND v.category=? AND v.vote IS NOT NULL""", [cat])
        y = np.array([1 if r["vote"] > 0 else 0 for r in lab])
        pos, neg = int(y.sum()), int(len(y) - y.sum())
        active = len(y) >= MIN_LABELED and pos >= MIN_EACH and neg >= MIN_EACH
        pend = db.query("""SELECT h.pic_id, h.model_score, h.score, h.hidden, e.emb FROM hits h
                           LEFT JOIN embeddings e ON e.pic_id=h.pic_id
                           WHERE h.category=? AND h.emailed_at IS NULL""", [cat])
        if not active:
            log(f"taste[{cat}]: {len(y)} votes ({pos}+/{neg}-), model inactive")
            ups = [("UPDATE hits SET score=model_score, hidden=0 WHERE pic_id=? AND category=? AND (hidden!=0 OR score IS NOT model_score)",
                    [r["pic_id"], cat]) for r in pend if r["hidden"] or r["score"] != r["model_score"]]
            if ups:
                db.batch(ups)
            continue
        X = np.stack([blob_to_vec(r["emb"]) for r in lab])
        acc = _cv_acc(X, y)
        model = _fit(X, y)
        ups, hid = [], 0
        for r in pend:
            if r["emb"] is None:
                continue
            p = float(model.predict_proba(blob_to_vec(r["emb"])[None])[0, 1])
            hidden = int(p < HIDE_BELOW)
            hid += hidden
            score = round(BLEND * (r["model_score"] or 0) + BLEND * p, 4)
            ups.append(("UPDATE hits SET score=?, hidden=? WHERE pic_id=? AND category=?", [score, hidden, r["pic_id"], cat]))
        if ups:
            db.batch(ups)
        log(f"taste[{cat}]: {len(y)} votes ({pos}+/{neg}-), ACTIVE, cv_acc={'n/a' if acc is None else f'{acc:.2f}'}, "
            f"hid {hid} of {len(pend)} pending")
