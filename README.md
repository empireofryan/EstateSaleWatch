# EstateSaleWatch

Watches Front Range Colorado estate sales (estatesales.net, 100 mi around Denver) and flags photos of
large mirrors, interesting cabinets and Buddhist pieces using a local zero-shot CLIP-family model
(SigLIP base via open_clip, CPU). No LLM APIs. Runs daily on GitHub Actions.

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python watch.py --max-sales 3     # scan (omit flag for all sales)
.venv/bin/python watch.py --digest          # writes digest.md if there are new hits
.venv/bin/python tests/calibrate.py         # mirror threshold calibration + cabinet/buddhist eyeball
```

Tune prompts, thresholds and keywords in `config.yaml`. State lives in `state/*.json` (committed by the workflow).
Wed/Fri runs open a GitHub issue "Estate sale finds" that mentions @empireofryan.
