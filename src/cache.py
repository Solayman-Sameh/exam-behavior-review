"""Reproducible raw model inference cache; behavior thresholds are never cached."""
import gzip
import hashlib
import json
from pathlib import Path

DETECTOR_KEYS = ('person_weights','phone_weights','detector_imgsz','person_conf',
                 'phone_conf','person_iou','phone_iou')


class RecordingDetector:
    def __init__(self, detector, config, video):
        self.detector=detector
        self.data={'schema':1,'video_sha256':hashlib.sha256(Path(video).read_bytes()).hexdigest(),
                   'detection_config':{k:config[k] for k in DETECTOR_KEYS},'frames':[]}

    def __call__(self, frame):
        persons,phones=self.detector(frame)
        self.data['frames'].append({'shape':list(frame.shape),
            'persons':persons.boxes.cpu().numpy().data.tolist(),
            'keypoints':persons.keypoints.cpu().numpy().data.tolist(),
            'phones':phones.boxes.cpu().numpy().data.tolist()})
        return persons,phones

    def save(self,path):
        with gzip.open(path,'wt',encoding='utf-8') as handle:
            json.dump(self.data,handle,separators=(',',':'))


class CachedDetector:
    def __init__(self,path,config,video):
        with gzip.open(path,'rt',encoding='utf-8') as handle:
            data=json.load(handle)
        if data['schema']!=1 or data['video_sha256']!=hashlib.sha256(Path(video).read_bytes()).hexdigest():
            raise ValueError('Inference cache does not match video')
        if data['detection_config']!={k:config[k] for k in DETECTOR_KEYS}:
            raise ValueError('Inference cache does not match detector settings')
        self.frame_count=len(data['frames'])
        self.frames=iter(data['frames'])

    def __call__(self,frame):
        import numpy as np
        from ultralytics.engine.results import Results
        row=next(self.frames)
        if list(frame.shape)!=row['shape']:
            raise ValueError('Frame shape differs from inference cache')
        persons=Results(frame,path='',names={0:'person'},
            boxes=np.asarray(row['persons'],dtype=np.float32).reshape(-1,6),
            keypoints=np.asarray(row['keypoints'],dtype=np.float32).reshape(-1,17,3))
        phones=Results(frame,path='',names={67:'cell phone'},
            boxes=np.asarray(row['phones'],dtype=np.float32).reshape(-1,6))
        return persons,phones
