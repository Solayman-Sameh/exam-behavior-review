import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Inspect head signals from real cached inference without re-running the model."""
import argparse,json,cv2
from dataclasses import asdict
from collections import Counter
from src.cache import CachedDetector
from src.config import ROOT,load_config
from src.head_turn import HeadTurnAnalyzer
from src.head_events import HeadEventEngine
from src.tracking import Tracker


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--clip',default='clip01')
    args=parser.parse_args()
    config=load_config()
    video=ROOT/'test_videos'/(args.clip+'.mp4')
    cache=ROOT/'reports'/'inference_cache'/(args.clip+'.json.gz')
    if not cache.exists():cache=cache.with_name(args.clip+'.partial.json.gz')
    detector=CachedDetector(cache,config,video)
    capture=cv2.VideoCapture(str(video));fps=capture.get(cv2.CAP_PROP_FPS)
    tracker=Tracker(fps,config);head=HeadTurnAnalyzer(config);events=HeadEventEngine(config)
    rows=[];fired=[];i=0
    while True:
        ok,frame=capture.read()
        if not ok or i>=detector.frame_count:break
        tracks=tracker.update(detector(frame),frame)
        states=head.update(tracks,i/fps,fps,frame.shape)
        fired.extend(events.update(states,i/fps))
        rows.append(dict(frame=i,time=i/fps,states={pid:asdict(s) for pid,s in states.items()}))
        if i%24==0:
            print(round(i/fps,2),[(pid,s.quality,round(s.delta,3) if s.delta is not None else None,s.direction,s.neighbor_id,s.reason,round(s.sustained_s,2),s.episodes) for pid,s in states.items()],flush=True)
        i+=1
    capture.release()
    path=ROOT/'reports'/(args.clip+'_head_diagnostics.json')
    path.write_text(json.dumps(dict(events=fired,frames=rows),indent=2))
    print('EVENTS',fired,flush=True)
