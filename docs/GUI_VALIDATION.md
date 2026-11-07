# Tkinter implementation and validation

Implemented 6 November 2026 against the agreed implementation plan (retained locally) in conda `main` (Python 3.11). This is interface engineering only; detection rules, thresholds, callback contract, database schema, model identity, existing detection tests and evaluation scripts are unchanged.

## Delivered interface

- `ttkbootstrap` 1.20.4, based on `flatly`, with a navy palette, warm off-white background and Segoe UI typography. The new dependency was installed without upgrading detection packages and pinned after the app launched successfully.
- Resizable two-panel layout (minimum 1100 x 650), mouse-operated fullscreen toggle, empty preview, determinate frame progress and loading animation.
- Upload, Play/Pause, Stop, Clear and About controls; filename in the title while a run is active; final frame retained on completion.
- Five-column persistent history: local time, track, friendly behavior, two-decimal score and filename. Only behavior text carries the behavior color. The virtualized Canvas table supports vertical/horizontal scrolling and renders only visible rows; ttk Treeview row tags would have colored every column.
- Inline, aspect-preserving screenshot viewer; source-video time in the caption; non-modal handling for missing/corrupt/out-of-folder images.
- Stacked five-second toast cards inside the preview, a styled modal About dialog, permanent disclaimer and original shield/eye Windows icon.
- Inline processing errors, state recovery and confirmation before closing an active worker.

## Lifecycle decisions

Upload starts processing automatically, preserving the existing workflow. During loading, only Stop is enabled; this follows the plan's explicit loading-state exception to Clear being normally available. The loading message covers initialization until the first frame arrives because the frozen pipeline has no separate model-ready callback.

Pause finishes the current frame, including any screenshot/database writes, then blocks the worker at the existing frame callback. The UI first says `Pausing after the current frame…` and then confirms `Paused`. Resume retains the same run, tracks and source-video timing. Stop wakes a paused worker immediately, then lets the pipeline release its video resources. Model initialization itself is not interruptible; Stop/close waits safely for it to return.

Clear during a run requests cancellation, immediately resets the preview/progress/status, suppresses stale visual updates and retains every persisted event. Upload stays disabled until that worker exits. Clear leaves the selected evidence image and history intact. After successful completion, Play replays the saved annotated video at its recorded frame rate. Replay adds no observations. Cancelled processing is not replayable; another Upload starts a new inference run.

All worker messages pass through queues. Only the Tk thread creates or updates widgets; the frame queue is bounded to one newest preview frame, while event/error messages are retained. Pending toast/poll timers are cancelled on close.

## Evidence

| Check | Result | Local evidence |
|---|---|---|
| Existing tests, unchanged | 39 passed; zero skips | `reports/gui_validation/detection_tests_full.log` |
| GUI lifecycle checks | 14 groups passed | `reports/gui_validation/gui_checks.json` |
| Fresh models through GUI worker | Four clips, 1,231 frames, 10 events | `reports/gui_live_validation/evaluation.json`, `gui_checks.json` |
| Accepted event comparison | Identical subject, behavior, source time, score and evidence for every event | Assertions in `scripts/check_gui.py --real-clips` |
| Recorded output integrity | 1,231 annotated frames decoded; all 10 screenshots and DB records valid; active states replay correctly | `reports/gui_live_validation/verification.json` |
| Phone regression | Person/phone tracks, ownership and active phone states identical frame-for-frame | `reports/gui_live_validation/phone_regression.json` |
| Frozen-file audit | 553 recorded files unchanged | `reports/gui_validation/frozen_check.json` |

The initial restricted test runs failed to create temporary databases/videos. The unchanged suite was rerun with normal temporary-folder access and passed all 39 tests. Those initial failures are retained in the report logs; they are not counted as successful validation.

The GUI checks cover idle/loading controls, actual worker pause acknowledgement, resume, Stop during loading/processing, Clear while paused, last-frame retention, declining/accepting close, inline failures, all labels, three concurrent toasts with timed dismissal, screenshot recovery/path containment, local/legacy UTC times, 2,000-row history scrolling, minimum layout, fullscreen return and modal About. Synthetic fixtures test UI behavior only. The four-clip run separately uses the actual local models, invokes Pause/Play for every clip, selects every saved screenshot and compares against accepted events.

Desktop visual inspection checked the navy/white Upload contrast, off-white/white panel separation, placeholder, all history colors, selected screenshot at normal and minimum size, navy About header and title-bar icon. A discovered automatic-theme recoloring issue was fixed using explicit custom-surface colors; lifecycle checks passed again. Fullscreen behavior is covered by the GUI harness. The separate Windows taskbar icon and alternate monitors/DPI settings have not been independently verified.

`scripts/verify_outputs.py` intentionally still reports `gui_verified_here: false`: that frozen verifier checks recorded pipeline artifacts, not widgets. GUI evidence is recorded separately above.

## Reproduce

From this project folder:

```cmd
conda activate main
python -m unittest discover -s tests -v
python scripts\check_gui.py
python scripts\check_gui.py --real-clips --name gui_review_new
python scripts\verify_outputs.py reports\gui_review_new

```

The live GUI check compares events with the versioned `docs/accepted_baseline/evaluation.json`, so it also works without historical reports. Use a fresh report name for live checks to keep evidence separate. Frame-by-frame comparison with `compare_phone_regression.py` additionally requires the full local historical report and traces. `check_replay.py` requires saved annotated videos from a prior GUI live run under `reports/gui_live_validation/`. The UI checks use isolated report databases and do not populate the user's `alerts/` history. Originals of edited interface/documentation files are preserved under `local_archive/before_gui_2026-11-06/`.

Clean-machine setup, a packaged executable, broader detection accuracy and additional monitor/DPI configurations remain outside this GUI validation.

## Subsequent interface updates

Play now supports replay after successful processing. The interface also provides Clear Logs with confirmation for deleting saved alert records. Clear continues to reset the preview while preserving history. See the user guide for current behavior.
