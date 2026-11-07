"""GUI lifecycle checks, separate from the frozen detection tests.

Use --real-clips for fresh inference through the actual GUI worker on all clips.
Artifacts are isolated under reports/; the user's app history is never changed.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import threading
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from app.tkinter_app import CheatingAlertApp, TITLE
from app.playback import PlaybackControl
from app.presentation import local_timestamp
from src.config import ROOT


def pump(root, condition, timeout=10):
    deadline = time.monotonic() + timeout
    while not condition():
        root.update()
        if time.monotonic() > deadline:
            raise AssertionError('Timed out waiting for GUI state')
        time.sleep(.005)
    root.update()


def settle(root, seconds=.15):
    deadline = time.monotonic() + seconds
    pump(root, lambda: time.monotonic() >= deadline, timeout=seconds + 2)


def fake_pipeline(path, output, callback, stop):
    time.sleep(.12)
    for index in range(1, 41):
        if stop.is_set():
            break
        callback('frame', (np.full((120, 160, 3), index, dtype=np.uint8), index, 40))
        time.sleep(.01)
    return dict(cancelled=stop.is_set(), events=[], frames=index if not stop.is_set() else index-1, total_frames=40)


def run_checks(root, app):
    checks = []
    errors = []
    root.report_callback_exception = lambda *args: errors.append(str(args))
    assert app.status.get() == 'Ready'
    assert str(app.play['state']) == str(app.stop_button['state']) == 'disabled'
    assert str(app.clear_button['state']) == 'normal'
    checks.append('idle controls and empty history')

    control = PlaybackControl()
    control.pause()
    blocked, finished = threading.Event(), threading.Event()
    worker = threading.Thread(target=lambda: (control.frame_boundary(blocked.set), finished.set()))
    worker.start()
    assert blocked.wait(1) and not finished.is_set()
    control.cancel()
    worker.join(1)
    assert finished.is_set() and control.stop.is_set()
    checks.append('stop wakes the paused worker')

    with patch('app.tkinter_app.process_video', fake_pipeline):
        app.start_video('fixture.mp4')
        assert app.phase == 'loading'
        assert str(app.upload['state']) == str(app.about_button['state']) == str(app.clear_button['state']) == 'disabled'
        assert str(app.stop_button['state']) == 'normal'
        assert app.preview_image is None
        assert root.title() == f'{TITLE} — fixture.mp4'
        pump(root, lambda: app.phase == 'processing')
        app.toggle_play()
        pump(root, lambda: app.phase == 'paused')
        frozen = app.progress_text.get()
        settle(root, .2)
        assert app.progress_text.get() == frozen
        app.toggle_play()
        pump(root, lambda: not app.running)
        assert app.progress['value'] == 100 and app.preview_image is not None
        assert root.title() == TITLE
        last = app.preview_image.tobytes()
        settle(root)
        assert app.preview_image.tobytes() == last
        checks.append('loading → processing → acknowledged pause → resume → complete; final frame held')

        app.start_video('clear.mp4')
        pump(root, lambda: app.phase == 'processing')
        app.toggle_play()
        pump(root, lambda: app.phase == 'paused')
        app.clear()
        assert app.status.get() == 'Ready' and app.preview_image is None
        assert str(app.upload['state']) == 'disabled'
        pump(root, lambda: not app.running)
        assert app.status.get() == 'Ready' and app.preview_image is None
        assert app.progress['value'] == 0
        checks.append('clear while paused cancels safely and suppresses stale frames')

        app.start_video('loading-stop.mp4')
        app.request_stop()
        pump(root, lambda: not app.running)
        assert app.last_result['cancelled']
        checks.append('stop during model loading')

        app.start_video('stop.mp4')
        pump(root, lambda: app.phase == 'processing')
        app.request_stop()
        pump(root, lambda: not app.running)
        assert app.last_result['cancelled']
        checks.append('stop during processing')

        with patch('app.tkinter_app.messagebox.askyesno', return_value=False) as question:
            app.start_video('decline-close.mp4')
            app.close()
            question.assert_called_once()
            assert app.running and not app.closing and not app.stop.is_set()
            app.request_stop()
            pump(root, lambda: not app.running)
        checks.append('declining close preserves the active worker')

    with patch('app.tkinter_app.process_video', side_effect=RuntimeError('Example missing model')):
        app.start_video('bad.mp4')
        pump(root, lambda: not app.running)
        assert app.phase == 'error' and 'Example missing model' in app.status.get()
        assert app.status_bar['background'] == '#F8E7E4'
        assert str(app.upload['state']) == 'normal'
        assert not [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    checks.append('processing error is inline and resets controls without a popup')

    (app.output / 'screenshots').mkdir(exist_ok=True)
    Image.new('RGB', (320, 180), 'navy').save(app.output / 'screenshots' / 'fixture.png')
    records = []
    for i, kind in enumerate(('phone_detected', 'peer_directed_looking', 'head_raise')):
        event = dict(event_id=f'gui-fixture-{i}', run_id='fixture', video_filename='fixture.mp4',
                     track_id=i+1, behavior_type=kind, confidence=.714, evidence='GUI fixture only',
                     video_time_s=1.5, wall_time='2026-11-05T20:35:00+00:00', screenshot_path='screenshots/fixture.png')
        event['id'] = app.db.insert_alert(event)
        records.append(event)
        app.events.put(('event', event))
    pump(root, lambda: len(app.toasts) == 3)
    assert len(app.history.records) == 3
    app.history.select(records[0]['id'])
    root.update()
    assert app.screenshot_image is not None and app.screenshot_panel.winfo_ismapped()
    assert app.db.get_alert_by_id(records[0]['id'])['behavior_type'] == 'phone_detected'
    app.clear()
    assert len(app.history.records) == 3 and app.screenshot_image is not None
    for event in records:
        app._show_toast(event)
    pump(root, lambda: not app.toasts, timeout=6)
    checks.append('all behavior labels; stacked 5-second toasts; inline screenshot; Clear preserves SQLite/history')

    unavailable = dict(records[0], screenshot_path='../../outside.png')
    app.view_screenshot(unavailable)
    assert app.screenshot_image is None and 'Screenshot unavailable' in app.status.get()
    corrupt = app.output / 'screenshots' / 'corrupt.jpg'
    corrupt.write_bytes(b'not-an-image')
    app.view_screenshot(dict(records[0], screenshot_path='screenshots/corrupt.jpg'))
    assert app.screenshot_image is None
    app.view_screenshot(records[0])
    assert app.screenshot_image is not None
    checks.append('missing, escaped and corrupt image paths fail inline; valid selection recovers')

    assert '•' in local_timestamp('2026-11-05T20:35:00+00:00')
    assert local_timestamp('invalid') == 'invalid'
    assert local_timestamp('2026-11-05T20:35:00') == local_timestamp('2026-11-05T20:35:00+00:00')
    checks.append('local timestamps and legacy UTC timestamps')

    # Virtual table draws a bounded visible slice, regardless of total history.
    many = [dict(records[i % 3], id=100+i) for i in range(2000)]
    app.history.set_records(many)
    app.history.select(2099)
    root.update()
    assert app.history.selected_id == 2099 and len(app.history.canvas.find_all()) < 300
    app.refresh_history()
    checks.append('large history scroll/selection and bounded rendering')

    root.geometry('1100x650')
    root.update()
    assert app.disclaimer.winfo_ismapped()
    assert app.preview.winfo_width() > 300 and app.screenshot.winfo_height() > 100
    app.toggle_fullscreen()
    root.update()
    assert root.attributes('-fullscreen')
    app.toggle_fullscreen()
    root.update()
    app.show_about()
    root.update()
    assert root.grab_current() == app.about_window
    app.about_window.grab_release()
    app.about_window.destroy()
    app.about_window = None
    assert not errors, errors
    checks.append('minimum size, fullscreen return, modal About, no Tk callback exceptions')
    return checks


def real_clips(root, app, output):
    summaries = []
    baseline = json.loads((ROOT / 'docs/accepted_baseline/evaluation.json').read_text())
    for video in sorted((ROOT / 'test_videos').glob('clip*.mp4')):
        print('GUI LIVE START', video.name, flush=True)
        app.start_video(video)
        pump(root, lambda: app.phase != 'loading', timeout=120)
        assert app.phase == 'processing', app.status.get()
        app.toggle_play()
        pump(root, lambda: app.phase == 'paused', timeout=15)
        progress = app.progress_text.get()
        settle(root, .3)
        assert progress == app.progress_text.get()
        app.toggle_play()
        pump(root, lambda: not app.running, timeout=240)
        result = app.last_result
        assert result and not result['cancelled'], app.status.get()
        assert result['frames'] == result['total_frames'] and app.preview_image is not None
        assert app.progress['value'] == 100
        for event in result['events']:
            app.history.select(event['id'])
            root.update()
            assert app.screenshot_image is not None, app.status.get()
        expected = next(s for s in baseline if s['video'] == video.name)
        def signature(summary):
            return [(e['track_id'], e['behavior_type'], e['video_time_s'], e['confidence'], e['evidence']) for e in summary['events']]
        assert signature(result) == signature(expected), f'Event regression: {video.name}'
        summaries.append(result)
        print('GUI LIVE PASS', video.name, result['frames'], len(result['events']), flush=True)
        count = len(app.history.records)
        app.clear()
        assert len(app.history.records) == count and app.status.get() == 'Ready'
    shutil.copy2(ROOT / 'configs/thresholds.yaml', output / 'thresholds.yaml')
    (output / 'evaluation.json').write_text(json.dumps(summaries, indent=2))
    return {'clips': len(summaries), 'frames': sum(s['frames'] for s in summaries),
            'events': sum(len(s['events']) for s in summaries), 'matches_accepted_events': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--real-clips', action='store_true')
    parser.add_argument('--name', default='gui_validation')
    args = parser.parse_args()
    output = ROOT / 'reports' / args.name
    if args.real_clips and ((output / 'runs').exists() or (output / 'evaluation.json').exists()):
        parser.error('Choose a fresh --name to preserve earlier live-run evidence.')
    output.mkdir(parents=True, exist_ok=True)
    data = output if args.real_clips else output / f'fixtures-{time.time_ns()}'
    root = tk.Tk()
    root.withdraw()
    app = CheatingAlertApp(root, data)
    # Keep widgets mapped for layout checks, but never steal foreground focus.
    root.deiconify()
    result = {}
    try:
        if args.real_clips:
            result['live'] = real_clips(root, app, output)
        else:
            result['checks'] = run_checks(root, app)
            # Accept close while paused; wait for the real non-daemon worker to exit.
            with patch('app.tkinter_app.process_video', fake_pipeline), patch('app.tkinter_app.messagebox.askyesno', return_value=True):
                app.start_video('close-paused.mp4')
                pump(root, lambda: app.phase == 'processing')
                app.toggle_play()
                pump(root, lambda: app.phase == 'paused')
                app.close()
                while app.worker.is_alive():
                    root.update()
                    time.sleep(.01)
                result['checks'].append('confirmed close safely joins a paused worker')
        result['pass'] = True
    finally:
        app.control.cancel()
        if app.worker:
            app.worker.join(timeout=15)
        try:
            if root.winfo_exists():
                app._destroy()
        except tk.TclError:
            pass
        (output / 'gui_checks.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
