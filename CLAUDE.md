# EstateSaleWatch

Daily watcher for Front Range CO estate sales (estatesales.net). Flags photos of (1) large mirrors,
(2) unique cabinets, (3) Buddhist pieces, (4) Art Deco; also flags whole "high-end" sales. Digest goes out as a GitHub issue (daily, never repeats a hit; old issues auto-closed) mentioning @empireofryan.

## Stack
Python 3.12, requests, open_clip (SigLIP ViT-B-16 webli, torch CPU), PyYAML, Pillow. GitHub Actions cron.

## Key files
- `watch.py` : scan (default) and `--digest`; flags `--max-sales N`, `--max-images N`, `--state-dir D` (temp state for tests)
- `estate/api.py` : list/detail fetch (browser UA, retries, 6 workers), sale normalization
- `estate/classify.py` : zero-shot scorer; category score = sum of softmax probs of its positive prompts over positives+negatives
- `config.yaml` : search area, model, prompts (positive + many negatives), thresholds, keyword boosts
- `tests/calibrate.py` : labeled mirror set (sale id#pictureOrder) + 200 random bg photos; downloads thumbs to tests/_work (delete after)
- `estate/sales.py` : sale-level high-end score (per-photo luxe prob stats + text keywords)
- `tests/calibrate_sales.py` (labeled high-end vs ordinary sales, score table), `tests/deco_sheet.py` (art_deco contact sheet)
- `state/seen.json` (pics+sale end dates), `hits.json`, `digested.json`, `sales.json` (per-sale luxe stats: n, sum, hi count, top-15, keywords), `standouts.json` (sales already announced)
- `.github/workflows/watch.yml` : daily 12:00 UTC scan; daily digest -> issue (closes prior digest issues); commits state with [skip ci]

## Commands
See README. venv at `.venv/`, all caches under `.cache/` (both gitignored).

## Status
LIVE (2026-10-03). Repo: github.com/empireofryan/EstateSaleWatch (private). Daily scan 12:00 UTC; digest issue daily (since 2026-10-03) (emails via @mention).
First digest issue #1 sent 2026-10-03 (54 hits). Backlog (15k photos) was scored locally on the Mac (21 img/s); Actions runner does only ~2.4 img/s, so a full rescore must be done locally.
Sale "standout" threshold 0.92 (2026-10-03: 14 of 93 sales). art_deco 0.92. Jewelry/coins/memorabilia are luxe "ordinary" counterweights.
Next ideas: thumbs-up/down feedback to tune thresholds; cabinet category is broad ("unique" is subjective).

## Decisions
- NO LLM APIs or SDKs, ever. Classifier is local open-source CLIP-family only.
- Scheduled work runs on GitHub Actions cron, never the laptop.
- SigLIP beat laion2b ViT-B-32 on the mirror calibration set (recall 7/7 vs 4/7) but is ~4x slower; max_images_per_run caps CI time.
- Thresholds after QA 2026-10-03: mirror 0.80, cabinet 0.85, buddhist 0.85 + extra distractor negatives (trunks, screens, necklaces, rosaries, tool chests).
- To rescore everything after a config change: reset state/seen.json + hits.json + sales.json + standouts.json, run `.venv/bin/python watch.py --max-images 30000` locally, commit state.
- CI installs torch+torchvision from the CPU index together (mismatch broke the first run).
- Keep test downloads tiny (thumbnails); disk was once 100% full.
- Mirror/cabinet/buddhist thresholds chosen on small sets; Buddhist verified on real thangka/Buddha/Guanyin captions (score >0.99).
- Luxe: same forward pass, separate softmax over luxe vs ordinary prompts (config `luxe`). Sale score = 0.2*mean(top-15 luxe) + 0.8*fraction of photos >=0.8 + 0.04/keyword (cap 0.2) + 0.05 if API-featured; flag at >=0.70 (calibration: HIGH min 0.82, ordinary max 0.54). Top-K saturates at 1.0 for big sales so the 0.8-cut fraction does the separating.
- art_deco threshold 0.85 (caption keyword adds 0.4). Many modern/postmodern glass+chrome distractor negatives; keyword "=deco" means whole word (so "decor" does not match).
- A fresh/reset run populates sales.json; sales scored before this feature have no stats and never flag until rescored.
- Sale detail: type 64 = online auction (tagged in digest); sales with no pictures are skipped.
