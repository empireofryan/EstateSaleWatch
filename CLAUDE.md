# EstateSaleWatch

Daily watcher for Front Range CO estate sales (estatesales.net). Flags photos of (1) large mirrors,
(2) unique cabinets, (3) Buddhist pieces. Digest goes out as a GitHub issue (Wed/Fri) mentioning @empireofryan.

## Stack
Python 3.12, requests, open_clip (SigLIP ViT-B-16 webli, torch CPU), PyYAML, Pillow. GitHub Actions cron.

## Key files
- `watch.py` : scan (default) and `--digest`; flags `--max-sales N`, `--max-images N`
- `estate/api.py` : list/detail fetch (browser UA, retries, 6 workers), sale normalization
- `estate/classify.py` : zero-shot scorer; category score = sum of softmax probs of its positive prompts over positives+negatives
- `config.yaml` : search area, model, prompts (positive + many negatives), thresholds, keyword boosts
- `tests/calibrate.py` : labeled mirror set (sale id#pictureOrder) + 200 random bg photos; downloads thumbs to tests/_work (delete after)
- `state/seen.json` (pics+sale end dates), `hits.json`, `digested.json`
- `.github/workflows/watch.yml` : daily 12:00 UTC scan; Wed/Fri digest -> issue; commits state with [skip ci]

## Commands
See README. venv at `.venv/`, all caches under `.cache/` (both gitignored).

## Status
Local end-to-end verified (scan 3 sales, digest). Not yet pushed; no GitHub repo created. Workflow untested on Actions.

## Decisions
- NO LLM APIs or SDKs, ever. Classifier is local open-source CLIP-family only.
- Scheduled work runs on GitHub Actions cron, never the laptop.
- SigLIP beat laion2b ViT-B-32 on the mirror calibration set (recall 7/7 vs 4/7) but is ~4x slower; max_images_per_run caps CI time.
- Keep test downloads tiny (thumbnails); disk was once 100% full.
- Mirror/cabinet/buddhist thresholds chosen on small sets; Buddhist verified on real thangka/Buddha/Guanyin captions (score >0.99).
- Sale detail: type 64 = online auction (tagged in digest); sales with no pictures are skipped.
