# EstateSaleWatch

Watches Front Range Colorado estate sales (estatesales.net, 100 mi around Denver) and flags photos of
large mirrors, interesting cabinets, Buddhist pieces and Art Deco using a local zero-shot CLIP-family model
(SigLIP base via open_clip, CPU). It also scores each sale for a "high-end" signal (fine art, designer/antique furniture, collector pieces) and lists flagged sales first in the digest as "Standout sales". No LLM APIs. Runs daily on GitHub Actions.

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python watch.py --max-sales 3     # scan (omit flag for all sales)
.venv/bin/python watch.py --digest          # writes digest.md if there are new hits
.venv/bin/python tests/calibrate.py         # mirror threshold calibration + cabinet/buddhist eyeball
.venv/bin/python tests/calibrate_sales.py   # high-end sale score table on labeled sales (then tests/deco_sheet.py)
.venv/bin/python watch.py --state-dir /tmp/x --max-sales 3   # test run without touching state/
```

Tune prompts, thresholds and keywords in `config.yaml`. State lives in `state/*.json` (committed by the workflow).
Each daily run opens a GitHub issue "Estate sale finds" that mentions @empireofryan.
