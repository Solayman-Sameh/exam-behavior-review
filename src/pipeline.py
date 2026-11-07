import json
import re
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.db import AlertDatabase
from .behavior import BehaviorAnalyzer
from .config import ROOT, load_config
from .detection import Detector
from .layered_events import LayeredEventEngine
from .head_turn import HeadTurnAnalyzer
from .tracking import Tracker


def render(frame, tracks, active):
    import cv2
    image = frame.copy()
    for person in tracks.persons:
        x1,y1,x2,y2 = map(int,person.box)
        color = (0,0,255) if person.track_id in active else (0,200,0)
        label = f'Review #{person.track_id}' if person.track_id in active else f'Person #{person.track_id}'
        cv2.rectangle(image,(x1,y1),(x2,y2),color,2)
        cv2.putText(image,label,(x1,max(18,y1-5)),cv2.FONT_HERSHEY_SIMPLEX,.5,color,1)
    for phone in tracks.phones:
        x1,y1,x2,y2 = map(int,phone.box)
        pw, ph = x2 - x1, y2 - y1
        if min(pw, ph) <= 0 or max(pw, ph) / min(pw, ph) > 3.0:
            continue
        cv2.rectangle(image,(x1,y1),(x2,y2),(0,165,255),2)
        cv2.putText(image,f'Phone {phone.conf:.2f}',(x1,max(18,y1-3)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,165,255),1)
    return image


def process_video(video_path, output_dir=None, config_path=None, callback=None, stop=None, detector=None):
    import cv2
    config = load_config(config_path)  # Reload on every video upload.
    video_path = Path(video_path).resolve()
    output_dir = Path(output_dir) if output_dir else ROOT / 'alerts'
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f'Cannot open video: {video_path.name}')
    writer = None
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            raise ValueError('Video has invalid frame rate')
        width,height = (int(capture.get(x)) for x in (cv2.CAP_PROP_FRAME_WIDTH,cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        detector = detector or Detector(config)
        tracker, behavior, engine = Tracker(fps,config), BehaviorAnalyzer(config), LayeredEventEngine(config)
        head = HeadTurnAnalyzer(config) if config['layer']>=1 else None
        database = AlertDatabase(output_dir/'cheating_alerts.db')
        run_id = uuid4().hex[:12]
        run_dir = output_dir/'runs'/run_id
        run_dir.mkdir(parents=True)
        writer = cv2.VideoWriter(str(run_dir/'annotated.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
        if not writer.isOpened():
            raise RuntimeError('Cannot create annotated MP4 output')
        screenshot_dir = output_dir/'screenshots'
        screenshot_dir.mkdir(exist_ok=True)
        frame_idx,events,counts = 0,[],Counter()
        started = time.monotonic()
        with (run_dir/'frames.jsonl').open('w',encoding='utf-8') as trace:
            while not (stop and stop.is_set()):
                ok,frame = capture.read()
                if not ok:
                    break
                # CFR test assets: timestamp derived from source rate, independent of inference speed.
                timestamp = frame_idx/fps
                detections = detector(frame)
                tracks = tracker.update(detections,frame)
                signals = behavior.update(tracks,width)
                head_states = head.update(tracks,timestamp,fps,frame.shape) if head else {}
                new_events = engine.update(signals,head_states,timestamp,fps)
                annotated = render(frame,tracks,engine.get_active_alerts())
                for event in new_events:
                    event_id = uuid4().hex[:8]
                    stem = re.sub(r'[^A-Za-z0-9_-]+','_',video_path.stem)[:20]
                    suffix='phone' if event['behavior_type']=='phone_detected' else 'head'
                    relative = Path('screenshots')/f'{stem}_t{event["track_id"]}_{suffix}_{timestamp:.2f}s_{event_id}.jpg'
                    screenshot = output_dir/relative
                    if not cv2.imwrite(str(screenshot),annotated,[cv2.IMWRITE_JPEG_QUALITY,config['screenshot_quality']]):
                        raise IOError('Screenshot could not be saved; alert was not persisted')
                    event.update(event_id=event_id,run_id=run_id,video_filename=video_path.name,
                                 wall_time=datetime.now(timezone.utc).isoformat(), screenshot_path=str(relative))
                    try:
                        event['id'] = database.insert_alert(event)
                    except Exception:
                        screenshot.unlink(missing_ok=True)
                        raise
                    events.append(event)
                    if callback:
                        callback('event',event)
                writer.write(annotated)
                for person in tracks.persons:
                    counts[person.track_id] += 1
                trace.write(json.dumps(dict(frame=frame_idx,time_s=timestamp,width=width,height=height,
                    persons=[dict(id=p.track_id,box=p.box,conf=p.conf,
                                  keypoints=p.keypoints.tolist() if p.keypoints is not None else None) for p in tracks.persons],
                    phones=[dict(id=p.track_id,box=p.box,conf=p.conf) for p in tracks.phones],
                    associated_persons=list(signals), active_alerts=sorted(engine.get_active_alerts()),
                    active_phone_alerts=sorted(engine.phone.get_active_alerts()),
                    active_head_alerts=sorted(engine.head.get_active_alerts()) if engine.head else [],
                    head_states={pid:asdict(state) for pid,state in head_states.items()},
                    raw_phone_detections=len(detections[1].boxes)))+'\n')
                if callback:
                    callback('frame',(annotated,frame_idx+1,total))
                frame_idx += 1
        elapsed = time.monotonic()-started
        summary = dict(run_id=run_id,video=video_path.name,frames=frame_idx,total_frames=total,
                       fps=fps,elapsed_s=elapsed,processing_fps=frame_idx/max(elapsed,.001),
                       cancelled=bool(stop and stop.is_set()), events=events,
                       track_observations=dict(counts),output_directory=str(run_dir))
        (run_dir/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        return summary
    finally:
        capture.release()
        if writer:
            writer.release()
