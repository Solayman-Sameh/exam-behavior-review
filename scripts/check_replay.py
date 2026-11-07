"""Hidden-window checks against real saved annotated videos; no model inference."""
import sys,json,time,hashlib
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.tkinter_app import CheatingAlertApp
sys.path.insert(0,str(ROOT/'scripts'))
from check_gui import fake_pipeline,pump,settle

out=ROOT/'reports/replay_validation';out.mkdir(exist_ok=True)
root=tk.Tk();root.withdraw();errors=[]
root.report_callback_exception=lambda *args:errors.append(str(args))
app=CheatingAlertApp(root,out/f'fixtures-{time.time_ns()}')
summaries=json.loads((ROOT/'reports/gui_live_validation/evaluation.json').read_text())
checks=[]
try:
    with patch('app.tkinter_app.process_video',side_effect=AssertionError('Replay must never invoke inference')):
        for summary in summaries:
            app.video_path=ROOT/'test_videos'/summary['video']
            app._finish('complete',summary)
            assert str(app.play['state'])=='normal'
            before=len(app.db.get_alerts());history=len(app.history.records)
            app.toggle_play()
            assert app.phase=='replaying' and app.replay_index==1
            cap=cv2.VideoCapture(str(Path(summary['output_directory'])/'annotated.mp4'))
            ok,first=cap.read();cap.release();assert ok
            assert app.preview_image.tobytes()==first[:,:,::-1].tobytes()
            assert app.progress['value']<100 and str(app.stop_button['state'])=='normal'
            app.toggle_play();assert app.phase=='replay_paused'
            frozen=app.preview_image.tobytes();index=app.replay_index
            settle(root,.1)
            assert app.replay_index==index and app.preview_image.tobytes()==frozen
            app.toggle_play();assert app.phase=='replaying'
            app.replay_started-=60 # Accelerate the remaining frames for the test only.
            pump(root,lambda:app.phase=='complete',timeout=30)
            assert app.replay_index==summary['frames'] and app.progress['value']==100
            assert app.replay_capture is None and str(app.play['state'])=='normal'
            final=app.preview_image.tobytes();settle(root,.05);assert app.preview_image.tobytes()==final
            app.toggle_play();assert app.replay_index==1
            app.request_stop();assert app.phase=='complete' and app.replay_capture is None
            app.toggle_play();app.clear()
            assert app.phase=='idle' and app.preview_image is None and app.replay_capture is None
            assert str(app.play['state'])=='disabled'
            assert len(app.db.get_alerts())==before and len(app.history.records)==history
            checks.append(dict(video=summary['video'],frames_replayed=summary['frames'],pause_resume=True,restart_stop_clear=True,no_new_alerts=True))
        # Normal scheduling is paced rather than a fast decode loop.
        app._finish('complete',summaries[0]);app.toggle_play();settle(root,.15)
        assert 2<=app.replay_index<=8,app.replay_index
        app.request_stop()
        missing=dict(summaries[0],output_directory=str(out/'missing'))
        app._finish('complete',missing);app.toggle_play()
        assert app.phase=='complete' and app.replay_capture is None and app.status.get().startswith('Unable to replay')
        app._finish('complete',dict(summaries[0],cancelled=True))
        assert str(app.play['state'])=='disabled'
        app._finish('complete',summaries[0]);app.toggle_play()
    with patch('app.tkinter_app.process_video',fake_pipeline):
        app.start_video('new-upload.mp4')
        assert app.replay_capture is None
        pump(root,lambda:not app.running)
        assert app.phase=='complete'
    app._finish('complete',summaries[0]);app.toggle_play()
    app.close();assert app.replay_capture is None
    assert not errors,errors
    result=dict(passed=True,windows_shown=False,visual_layout_checked=False,clips=checks,normal_speed_scheduling=True,missing_file_recovery=True,cancelled_run_not_replayed=True,new_upload_stops_replay=True,close_releases_video=True,no_callback_errors=True)
    (out/'replay_checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:
    app.control.cancel()
    if app.worker:app.worker.join(5)
    try:
        if root.winfo_exists():app._destroy()
    except tk.TclError:pass
