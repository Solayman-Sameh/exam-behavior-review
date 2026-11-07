# Exam Behavior Review

A Tkinter desktop app that tracks students in uploaded exam videos and flags visible phones, sideways head movements and forward head raises for human review. It saves annotated screenshots and a local SQLite alert history.

The computer-vision checkpoint has been locally accepted on the four included development clips. The Tkinter interface now includes the academic navy/off-white theme, pause/resume, progress, inline screenshots and non-blocking alert cards. Distributable Windows packaging remains future work. Alerts are observations for review, not proof of cheating; scores are not cheating probabilities. A full video demonstration of the application in action is available in [demo video](assets/demo.mp4).

## Run in the existing environment

In CMD, from this project folder:

```cmd
conda activate main
python main.py
```

Use **Upload Video**, select a clip in `test_videos/`, and processing starts automatically. **Pause / Play** freezes and resumes processing at a frame boundary. **Stop** ends it safely. After successful completion, **Play** replays the saved annotated video without running inference again. Click a history row to view its screenshot below the table. **Clear** restores the empty preview while keeping history; during processing it also requests cancellation. New runs save under `alerts/`; historical checkpoint history remains untouched inside the checkpoint folder.

The GUI uses `ttkbootstrap==1.20.4`. On another machine, install `requirements.txt` first. See [GUI validation](docs/GUI_VALIDATION.md) for the completed checks and control-state decisions.

## Setup on another machine

Use Python 3.11 with Tkinter. Install the dependencies and explicitly acquire the pretrained weights:

```cmd
python -m pip install -r requirements.txt
python scripts\setup_models.py
python main.py
```

Model acquisition needs internet access; normal inference uses local files. See [the user guide](docs/USER_GUIDE.md) for CUDA installation, folder handling and troubleshooting. This setup recipe has not yet been tested in a clean environment or packaged executable.

## Demonstrated behavior

| Video | Main result |
|---|---|
| clip01.mp4 | Two sideways looks by the foreground woman |
| clip02.mp4 | One phone event; two head-turn events for the same boy |
| clip03.mp4 | Two looks by the woman with glasses, including the final look |
| clip04.mp4 | Three head raises by the girl in gray |

These clips were used to tune thresholds. They are reference demonstrations, not held-out accuracy evidence. See [validation](docs/VALIDATION.md) for timings and reproduction commands.

## Project layout

```text
main.py             Desktop entry point
app/                Tkinter interface and SQLite persistence
src/                Detection, tracking, behavior, events and pipeline
configs/            Versioned, accepted thresholds
models/             Local weights; manifest.json is versioned
scripts/            Setup, evaluation and verification commands
tests/              Unit and integration tests
test_videos/        Four public-reference candidates and their hash manifest
assets/             Interface artwork, icons, and demonstration video (demo.mp4)
docs/               User guide, algorithm and validation reference
alerts/             Generated app history and screenshots (ignored)
reports/            Local evaluation evidence (ignored)
local_archive/      Preserved older project material (ignored)
checkpoitns_to_execution/  Frozen checkpoints, untouched (ignored)
```

Read [USER_GUIDE](docs/USER_GUIDE.md), [ALGORITHM](docs/ALGORITHM.md), and [VALIDATION](docs/VALIDATION.md). The original development notes are preserved locally rather than presented as current implementation documentation.

## Publication notes

The four `test_videos/` clips are intentionally eligible for Git, including their manifest and usage notes. Their stock-footage watermarks do not establish redistribution permission: availability and rights must be reviewed before public release. Model binaries and generated outputs are ignored. `models/manifest.json` identifies the expected weights and download sources.

The repository code retains its existing MIT license. Third-party model software, weights and footage have separate terms; the repository license does not grant rights to those materials. 
