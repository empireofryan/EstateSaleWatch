"""Zero-shot CLIP-family classifier (open_clip, torch CPU). Free, local, no APIs."""
import os
import re
import time
from pathlib import Path

import torch
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "hf"))
os.environ.setdefault("TORCH_HOME", str(ROOT / ".cache" / "torch"))
import open_clip  # noqa: E402


def load_config(path=ROOT / "config.yaml"):
    return yaml.safe_load(open(path))


class Classifier:
    def __init__(self, cfg, model_name=None, pretrained=None):
        self.cfg = cfg
        m = cfg["model"]
        name, pre = model_name or m["name"], pretrained or m["pretrained"]
        torch.set_num_threads(os.cpu_count() or 2)
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(name, pretrained=pre)
        self.model.eval()
        tok = open_clip.get_tokenizer(name)
        self.cats = list(cfg["prompts"])
        phrases, self.owner = [], []
        for c in self.cats:
            for p in cfg["prompts"][c]:
                phrases.append(p); self.owner.append(c)
        for p in cfg["negatives"]:
            phrases.append(p); self.owner.append(None)
        self.phrases = phrases
        with torch.no_grad():
            t = tok([cfg["template"].format(p) for p in phrases])
            tf = self.model.encode_text(t)
            self.text = tf / tf.norm(dim=-1, keepdim=True)
        self.scale = self.model.logit_scale.exp().item()
        self.bias = getattr(self.model, "logit_bias", None)
        self.bs = m.get("batch_size", 64)
        self.cat_idx = {c: [i for i, o in enumerate(self.owner) if o == c] for c in self.cats}
        # separate "luxe" prompt set (sale-level high-end signal), softmax over luxe+ordinary only
        lx = cfg.get("luxe") or {}
        self.luxe_phr = list(lx.get("positive", [])) + list(lx.get("ordinary", []))
        self.n_luxe = len(lx.get("positive", []))
        if self.luxe_phr:
            with torch.no_grad():
                tf = self.model.encode_text(tok([cfg["template"].format(p) for p in self.luxe_phr]))
                self.ltext = tf / tf.norm(dim=-1, keepdim=True)

    def _logits(self, f, text):
        logits = self.scale * f @ text.T
        if self.bias is not None:
            logits = logits + self.bias
        return logits

    @torch.no_grad()
    def probs(self, images, with_luxe=False):
        """images: list of PIL -> tensor [N, n_prompts] softmax probs (plus luxe probs if asked).
        Image embeddings are computed once and shared by both prompt sets."""
        out, lout = [], []
        for i in range(0, len(images), self.bs):
            x = torch.stack([self.preprocess(im) for im in images[i:i + self.bs]])
            f = self.model.encode_image(x)
            f = f / f.norm(dim=-1, keepdim=True)
            out.append(self._logits(f, self.text).softmax(-1))
            if with_luxe and self.luxe_phr:
                lout.append(self._logits(f, self.ltext).softmax(-1))
        if with_luxe:
            return torch.cat(out), (torch.cat(lout) if lout else None)
        return torch.cat(out)

    def score(self, images):
        """-> list of {category: (score, top phrase)}; with the luxe set configured each dict also has
        key "_luxe": (P(luxe prompts), top luxe phrase)."""
        p, lp = self.probs(images, with_luxe=True)
        res = []
        for n, row in enumerate(p):
            d = {}
            for c, idx in self.cat_idx.items():
                best = max(idx, key=lambda i: row[i].item())
                d[c] = (float(row[idx].sum()), self.phrases[best])
            if lp is not None:
                lr = lp[n]
                best = int(lr[:self.n_luxe].argmax())
                d["_luxe"] = (float(lr[:self.n_luxe].sum()), self.luxe_phr[best])
            res.append(d)
        return res


def load_image(path):
    return Image.open(path).convert("RGB")


def keyword_hits(text, cfg):
    """-> set of categories whose keywords appear in text."""
    t = (text or "").lower()
    return {c for c, kws in cfg["keywords"].items() if match_keywords(t, kws)}


def match_keywords(text, kws):
    """-> list of matched keywords. Prefix match on word start; a leading "=" means whole word only."""
    t = (text or "").lower()
    out = []
    for k in kws:
        whole = k.startswith("=")
        k = k.lstrip("=")
        if re.search(r"\b" + re.escape(k) + (r"\b" if whole else ""), t):
            out.append(k)
    return out
