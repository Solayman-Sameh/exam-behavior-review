import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Validate completed evaluation artifacts; no model rerun or synthetic accuracy claim."""
import argparse
import json
from pathlib import Path

import cv2
import os
from app.db import AlertDatabase
from src.config import ROOT
from src.config import load_config
from src.behavior import BehaviorAnalyzer
from src.layered_events import LayeredEventEngine
from src.head_turn import HeadTurnAnalyzer
from src.types import Track,TrackingResult


def verify(directory):
    directory=Path(directory).resolve()
    summaries=json.loads((directory/'evaluation.json').read_text())
    if len(summaries)!=4:
        raise AssertionError('Expected four completed clip summaries')
    database=AlertDatabase(directory/'cheating_alerts.db')
    records=database.get_alerts(limit=10000)
    checks=[]
    config=load_config(directory/'thresholds.yaml')
    for summary in summaries:
        run=directory/'runs'/summary['run_id']
        trace=[json.loads(line) for line in (run/'frames.jsonl').read_text().splitlines()]
        import numpy as np
        analyzer,engine=BehaviorAnalyzer(config),LayeredEventEngine(config)
        head=HeadTurnAnalyzer(config) if config['layer']>=1 else None
        replay_events=[]
        for row in trace:
            tracks=TrackingResult(*[[Track(t['id'],tuple(t['box']),t['conf'],
                np.asarray(t['keypoints']) if t.get('keypoints') is not None else None) for t in row[key]] for key in ('persons','phones')])
            width,height=row.get('width',768),row.get('height',432)
            states=head.update(tracks,row['time_s'],summary['fps'],(height,width,3)) if head else {}
            replay_events.extend(engine.update(analyzer.update(tracks,width),states,row['time_s'],summary['fps']))
            if sorted(engine.get_active_alerts())!=row['active_alerts']:
                raise AssertionError('Current episode logic disagrees with rendered alert state')
        original=[(e['track_id'],e['behavior_type'],e['video_time_s']) for e in summary['events']]
        replay=[(e['track_id'],e['behavior_type'],e['video_time_s']) for e in replay_events]
        if original!=replay:
            raise AssertionError('Current logic disagrees with recorded event transitions')
        if summary['cancelled'] or len(trace)!=summary['total_frames'] or summary['frames']!=len(trace):
            raise AssertionError(f'Incomplete evaluation: {summary["video"]}')
        capture=cv2.VideoCapture(str(run/'annotated.mp4'))
        count=0
        while True:
            ok,_=capture.read()
            if not ok:
                break
            count+=1
        capture.release()
        if count!=len(trace):
            raise AssertionError('Annotated output frame count differs from source trace')
        for event in summary['events']:
            matching=[r for r in records if r['event_id']==event['event_id']]
            if len(matching)!=1:
                raise AssertionError('Event missing from DB or duplicated')
            # Python file I/O supports long Windows paths that OpenCV's
            # filename-based image reader may reject.
            image_path=directory/event['screenshot_path']
            if os.name=='nt':
                image_path=Path('\\\\?\\'+str(image_path))
            image=cv2.imdecode(np.frombuffer(image_path.read_bytes(),dtype=np.uint8),cv2.IMREAD_COLOR)
            if image is None:
                raise AssertionError('Screenshot missing or corrupt')
            red=(image[:,:,2]>150)&(image[:,:,1]<80)&(image[:,:,0]<80)
            if red.sum()<100:
                raise AssertionError('Expected visible red annotation')
        counts=summary['track_observations']
        full_coverage=[int(k) for k,v in counts.items() if v==len(trace)]
        checks.append(dict(video=summary['video'],frames=len(trace),decoded_output_frames=count,
                           alerts=len(summary['events']),full_frame_track_ids=full_coverage,
                           phone_alerts=sum(e['behavior_type']=='phone_detected' for e in summary['events']),
                           head_alerts=sum(e['behavior_type']!='phone_detected' for e in summary['events']),
                           times_s=[e['video_time_s'] for e in summary['events']]))
    expected={'clip01.mp4':0,'clip02.mp4':1,'clip03.mp4':0,'clip04.mp4':0}
    alert_counts_match=all(c['phone_alerts']==expected[c['video']] for c in checks)
    result=dict(artifact_integrity_pass=True,current_logic_replay_matches=True,demonstration_alert_counts_match=alert_counts_match,
                total_frames=sum(c['frames'] for c in checks),database_alerts=len(records),clips=checks,
                gui_verified_here=False,phone_stage_user_accepted=True,
                all_visible_people_identity_stability_verified=False)
    (directory/'verification.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('directory',nargs='?',default=str(ROOT/'reports'/'relocation_validation'))
    args=parser.parse_args()
    print(json.dumps(verify(args.directory),indent=2))
