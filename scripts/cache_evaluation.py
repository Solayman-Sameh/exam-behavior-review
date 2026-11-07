import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Record real CPU inference and original phone-engine baseline in one pass."""
import json
import shutil
from src.config import ROOT,load_config
from src.detection import Detector
from src.cache import RecordingDetector
from src.pipeline import process_video


if __name__=='__main__':
    import yaml
    import cv2
    cv2.setNumThreads(1)
    output=ROOT/'reports'/'accepted_phone_onnx'
    output.mkdir(parents=True,exist_ok=False)
    cache_dir=ROOT/'reports'/'inference_cache'
    cache_dir.mkdir(exist_ok=True)
    config=load_config()
    config['device']='cpu'
    config['torch_threads']=4
    config['layer']=0
    snapshot=output/'thresholds.yaml'
    snapshot.write_text(yaml.safe_dump(config,sort_keys=False))
    from src.onnx_backend import OnnxDetector
    model=OnnxDetector(config)
    summaries=[]
    for video in sorted((ROOT/'test_videos').glob('clip*.mp4')):
        recorder=RecordingDetector(model,config,video)
        print('START',video.name,flush=True)
        def callback(kind,value):
            if kind=='frame' and value[1]%10==0:
                recorder.save(cache_dir/(video.stem+'.partial.json.gz'))
            if kind=='frame' and value[1]%50==0:
                print(' FRAME',value[1],flush=True)
            if kind=='event':print(' EVENT',value['behavior_type'],value['track_id'],value['video_time_s'],flush=True)
        result=process_video(video,output,config_path=snapshot,callback=callback,detector=recorder)
        recorder.save(cache_dir/(video.stem+'.json.gz'))
        summaries.append(result)
        print('END',video.name,len(result['events']),'events',flush=True)
    (output/'evaluation.json').write_text(json.dumps(summaries,indent=2))
