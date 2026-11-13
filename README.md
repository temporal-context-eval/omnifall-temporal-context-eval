# Event-level evaluation of temporal context length for video fall detection (OmniFall)

Code, split-correction rules, and event-level results for the manuscript
*"Effect of Temporal Context Length on False Alarms, Misses, and Detection Latency in
Video-Based Fall Event Detection: An Event-Level Evaluation on the OmniFall Benchmark"*
(under review). This repository is anonymized for double-blind review.

No video is redistributed. Labels and splits come from the OmniFall Hugging Face dataset
(revision `83572a37`); OOPS videos were obtained from the public mirror `pengxiang/oops`
(revision `8ca3e64b`). See the manuscript, Section III.

## Layout

| Path | Contents |
|---|---|
| `scripts/omnifall_eval.py` | Event-level evaluation library: event merging (0.5 s), reference-camera rule, tolerance window [t0−0.5, t1+3.0], alarm bundling (gap ≤ 2 s), EDR / FA/h / latency / pAUC. SHA-256 of the frozen version is recorded in `runs_meta/design_freeze.json`. |
| `tests/test_omnifall_eval.py` | 20 unit tests for the boundary cases (Fig. 3). `reports/eval_unit_tests.log` is the run log. |
| `scripts/05_split_audit.py`, `11_verify_design.py` | Raw-level audit of the official cross-subject split (subject leakage), duplicate rows in the OOPS split file, and pre-event footage (Table 3). Split-correction rule: remove leaked subjects from *train*. |
| `scripts/10_extract_features.py` | Frozen SigLIP2-base features at 7.5 fps. |
| `scripts/13_train_eval.py` | Conditions A / B / C, operating-point selection (Eq. 12–13), one-shot test evaluation with access logging. |
| `scripts/14_analysis.py`, `15_ab_recalc.py` | Auxiliary (pre-specified) and post hoc analyses; recomputation of every number in the paper. |
| `scripts/16_figures.py` | Generates Figs. 1–7 (numbering of the pre-revision manuscript; see `figs/`). |
| `results/main/` | `results_main.csv` (Table 5), `results_paired.csv` (paired bootstrap), `curves.csv` (Fig. 5), `events_at_op.csv`, `results_subset.csv` (Table 7), `results_by_dataset.csv`, `results_fa_by_label.csv`. |
| `results/recalc/` | B1–B6, D1, D2 recomputation tables (`ab_recalc.md`). |
| `results/analysis/` | C1–C3 (auxiliary operating points, subject-level CI, sensitivity), D3–D4 (missed-event breakdown, pre-event scores), F7 case data. Full tables referenced in Table 4. |
| `runs_meta/` | `design_freeze.json` (frozen design, created 2026-11-09 18:29:59), `test_access_log.md` (every access to the test split), `val_selection.csv` (validation operating points). |
| `reports/` | Design-verification report and its CSVs (`dv_*.csv`), raw-file SHA-256 inventory. |

## Reproduce

```bash
pip install -r requirements.txt
python -m pytest tests/ -q                 # evaluation rules
python scripts/13_train_eval.py --stage fit   # requires features from 10_extract_features.py
python scripts/13_train_eval.py --stage test  # refuses to run without design_freeze.json
python scripts/15_ab_recalc.py --name main
python scripts/14_analysis.py --name main
python scripts/16_figures.py
```

Paths default to the repository root (`OF_HOME`). Comments in the scripts are in Korean.

## License

MIT (code). Result tables (CSV) are released under CC BY 4.0. Datasets keep their own licenses.
