# Validation and reproduction

The accepted local checkpoint is frozen under `checkpoitns_to_execution/`. The project-root app is a copy of its runtime, models and thresholds. Historical root files are preserved under `local_archive/before_root_migration_2026-11-06/`. No files were deleted during organization.

## Accepted demonstration

| Clip | Frames | Phone events | Head events | Event times in source seconds |
|---|---:|---:|---:|---|
| 01 | 488 | 0 | 2 | 4.958, 11.542 |
| 02 | 256 | 1 | 2 | 0.292 phone; 2.544, 9.510 head |
| 03 | 226 | 0 | 2 | 3.170, 8.467 |
| 04 | 261 | 0 | 3 | 1.043, 4.463, 9.343 |

The intended subject is the foreground woman in Clip 01, phone-holding boy in Clip 02, woman with glasses in Clip 03 and girl in gray in Clip 04. Track numbers are not stable identities or application rules. Clip 04 events are head raises, with no verified gaze target.

## Run checks from the project root

```cmd
python -m unittest discover -s tests -v
python scripts\evaluate.py --name my_review
python scripts\verify_outputs.py reports\my_review
```

Choose a fresh evaluation name every time. Evaluation snapshots settings and creates videos, traces, screenshots, summaries and a SQLite database under ignored `reports/`. Cached replay with `--cache` reuses local real model detections; it is not a live-model speed benchmark. The cache verifies video hashes and detector settings but must also be regenerated when weights change, even under the same filename.

Reference clips and their hashes are versioned in `test_videos/manifest.json`. Local weights are identified in `models/manifest.json`. The package snapshot is in `TESTED_ENVIRONMENT.json`. Generated reports are not needed to launch the app and are intentionally excluded from Git.

The relocation's actual results are recorded in root `STATUS.md` and locally under `reports/relocation_validation/`. The preservation and source-equality checks are in `work/organization/migration_manifest.json`. This is a development regression, not independent accuracy evaluation. A clean installation, executable packaging and broader normal/ambiguous footage remain future checks.

## Public baseline and optional local evidence

`docs/accepted_baseline/evaluation.json` preserves accepted event identities, times, scores and evidence for the four clips. `python scripts/check_gui.py --real-clips --name fresh_review` compares a new live GUI run against that portable baseline. Generated annotated videos, traces, screenshots and SQLite history remain local under ignored reports/. The optional `compare_phone_regression.py` command requires full baseline traces from an earlier local report, which are not distributed in this repository. Cached evaluation similarly requires a locally generated inference cache. Run `scripts/evaluate.py` without `--cache` for fresh model inference.
