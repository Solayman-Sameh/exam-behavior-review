import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Run every frame of all four clips with the same configuration."""
import json
import argparse
import shutil
from pathlib import Path
from src.config import ROOT,load_config
from src.detection import Detector
from src.pipeline import process_video


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',default='layer1_headturn')
    parser.add_argument('--cache',action='store_true',help='Replay matching saved real detections; reruns tracking and all downstream code')
    parser.add_argument('--device',help='Evaluation-only device override; default YAML stays unchanged')
    args=parser.parse_args()
    output=ROOT/'reports'/args.name
    output.mkdir(parents=True,exist_ok=True)
    snapshot=output/'thresholds.yaml'
    if snapshot.exists():
        raise SystemExit('Choose a fresh evaluation name to preserve previous evidence.')
    shutil.copy2(ROOT/'configs'/'thresholds.yaml',snapshot)
    if args.device:
        import yaml
        config=load_config(snapshot);config['device']=args.device
        snapshot.write_text(yaml.safe_dump(config,sort_keys=False))
    config=load_config(snapshot)
    detector = None if args.cache else Detector(config)
    summaries=[]
    for video in sorted((ROOT/'test_videos').glob('clip*.mp4')):
        print(f'START {video.name}',flush=True)
        def progress(kind, value):
            if kind=='frame' and value[1]%100==0:
                print(f'  {value[1]}/{value[2]}',flush=True)
            elif kind=='event':
                print(f'  EVENT track={value["track_id"]} time={value["video_time_s"]:.2f}s score={value["confidence"]:.3f}',flush=True)
        if args.cache:
            from src.cache import CachedDetector
            detector=CachedDetector(ROOT/'reports'/'inference_cache'/(video.stem+'.json.gz'),config,video)
        summary=process_video(video,output,config_path=snapshot,callback=progress,detector=detector)
        summary['inference_source']='real_model_cache' if args.cache else 'live_model'
        summaries.append(summary)
        print(f'END {video.name}: {len(summary["events"])} events; {summary["processing_fps"]:.1f} fps',flush=True)
    (output/'evaluation.json').write_text(json.dumps(summaries,indent=2))
