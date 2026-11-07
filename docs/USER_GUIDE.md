# User guide

## Start and process a video

1. Open CMD in the project root and run `conda activate main`.
2. Run `python main.py`. Keep the terminal open while using the app.
3. Select **Upload Video** and choose an MP4, AVI or MOV. Processing starts automatically; the window title shows the filename. During initialization, the preview remains empty, progress is indeterminate and only Stop is enabled.
4. Processing runs in a background worker. The preview may skip display frames to remain responsive; inference still processes source frames sequentially. Progress shows the processed frame count and percentage.
5. Use **Pause** to finish the current frame and freeze the pipeline; the status confirms when it is paused. **Play** resumes the same run, tracks and source-time clock. Pause is not video seeking or real-time playback.
6. Review the red boxes and five-second alert cards. The history shows local recording time, temporary track number, friendly behavior label, score and source filename. UTC timestamps and raw behavior codes remain unchanged in the database.
7. Click a history row to view its screenshot inline below the table. The caption includes source-video time and local recording time. Scroll the table vertically for earlier records, or horizontally when a narrow window cannot fit every column. Use **Clear Logs** beside the observation count to clear all saved alert records from the database after a confirmation prompt.
8. **Stop** cancels safely, including while paused. It may wait for a model load or an in-flight frame to finish. Partial processing is not a completed evaluation. The last processed preview frame remains visible after completion or Stop; upload another video to start a fresh run.
9. **Clear** resets the preview and progress to Ready while keeping history and the selected evidence image. During a run it requests cancellation, suppresses later preview updates, and enables Upload once the worker exits. Clear is disabled during model loading, as specified by the loading-state exception.
10. **About** explains the observations, scores and limitations. **Full screen / Exit full screen** in the preview header is mouse-operated. The window also supports resizing and the standard maximize button. Closing while active asks whether to stop and close; declining leaves the run unchanged.

Track numbers are temporary per-video IDs, not verified identities. Green means no active alert, not certified normal behavior. Head raises can be ordinary actions and require human interpretation.

## Files and storage

- `configs/thresholds.yaml`: active settings, reloaded on each upload. Preserve the accepted values while polishing Tkinter.
- `models/yolo11n-pose.pt` and `models/yolo11n.pt`: separate pose and phone models. Their expected SHA-256 values are in `models/manifest.json`.
- `alerts/screenshots/`: event images.
- `alerts/cheating_alerts.db`: persistent SQLite history.
- `alerts/runs/<run_id>/`: annotated MP4, frame trace and summary for each processed upload.
- `reports/`: independent verification outputs; these do not populate the app's history.

This version writes app data beside the source code. Keep the project in a writable folder. Portable/user-data storage and executable packaging remain deployment work. The historical checkpoint and its own alert history have not been modified or copied into a fresh app history.

## Fresh environment

Python 3.11 with Tkinter is the recorded baseline. In a fresh environment, install `requirements.txt`, then run `python scripts/setup_models.py` explicitly to download weights. The application refuses to download missing weights implicitly.

For the laptop's CUDA 12.1 torch build, install the matching pair before the remaining requirements:

```cmd
python -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
python -m pip install -r requirements.txt
python scripts\setup_models.py
```

These commands document the existing dependency family; clean installation and redistribution remain unverified. `docs/TESTED_ENVIRONMENT.json` records the packages actually used for the relocation checks. The GPU default is device 0, with an existing CPU fallback if CUDA is unavailable. Processing speed depends on the device and scene; it is not guaranteed real-time playback.

After acquiring weights, compare them with the committed manifest before relying on a reproduced result. The setup utility reports downloaded hashes; a hash alone is not a model-license grant.

## Headless use

```cmd
python main.py --video test_videos\clip04.mp4 --output reports\manual_clip04
```

An alternative YAML can be supplied with `--config`. Headless flags do not change the graphical app's default configuration.

## Troubleshooting

| Symptom | Check |
|---|---|
| Missing model error | Put the two manifest-matching weights in models/ or run the explicit setup utility. |
| Wrong environment/import failure | Activate main and check `python --version`; avoid silently changing the working environment. |
| Screenshot or output creation fails | Use a writable, reasonably short project path and enough disk space. |
| Nothing alerts immediately | The rules require calibration and observed evidence. Small or occluded faces can remain unknown. |
| Too many head alerts | Review the underlying motion before changing thresholds; normal head raises can qualify. |
| Duplicate history on a repeated upload | Separate runs intentionally retain separate records; deduplication is within an event episode. |

Errors appear in the status area without a popup. A missing or corrupt screenshot leaves history intact; selecting an available image restores the evidence view. After a processing failure, use Upload Video to retry. No application keyboard shortcuts are installed.

The polished GUI has been checked in the existing conda `main` environment. See [GUI_VALIDATION.md](GUI_VALIDATION.md). A packaged executable and clean-machine installation remain future work. For a demonstration, use a clean demo history and a desktop view without unrelated personal information.


## Replay after completion

After processing finishes successfully, select Play to watch the saved annotated video again from the beginning. Pause and Play pause/resume replay; Stop ends replay, and the next Play starts from the beginning. At the end, the last frame stays visible and Play becomes available again. Replay uses the saved video at its recorded frame rate and adds no new observations, screenshots or history entries. Existing history remains available for reviewing evidence.

Clear, uploading another video or closing the app stops replay and releases the saved video. Cancelled processing is not replayable through this control. If the saved annotated MP4 was moved or removed, the app shows an error; upload/process the source again to create a new result.
