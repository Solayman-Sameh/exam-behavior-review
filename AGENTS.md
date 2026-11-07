# Project execution rules

Read `README.md`, `STATUS.md` and `DECISIONS.md` before editing.

- Work in this project root. Never modify checkpoitns_to_execution/ during app development.
- Preserve original files; archive before replacing historical material. Do not delete the user's files.
- Keep accepted detection logic, thresholds and model identity frozen during Tkinter-only work.
- Keep test_videos/ and its manifest eligible for Git as requested by the user. Keep model binaries, archives and generated app data ignored.
- Use scripts/ for setup/evaluation commands and docs/ for curated current documentation.

- Follow the user's layer gate: Layer 0 phone detection, Layer 1 head turns, Layer 2 leaning/neighbor validation. Evaluate all four clips and address regressions before progressing.
- Never mark a layer complete solely because mocked or synthetic tests pass.
- Preserve model identity and test-video manifest. No training is authorized or necessary under this specification.
- Use separate pretrained phone and pose models; COCO pose is person-only.
- Phone events are independent of neighbor direction.
- Run focused unit tests after logic changes; real model/config changes require the affected clip checks and a final all-clip regression pass.
- Keep output trace, annotated video, screenshots and database for each evaluation.
- Report unverified GUI behavior explicitly. Do not claim perfect detection or cheating probability.
- Update `STATUS.md` with actual evidence, failures and next actions.
