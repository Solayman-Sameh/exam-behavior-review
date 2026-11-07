from pathlib import Path
from .config import ROOT


class Detector:
    """Two local COCO-pretrained models; no implicit download at runtime."""

    def __init__(self, config):
        import torch
        from ultralytics import YOLO
        torch.set_num_threads(config.get('torch_threads', 4))
        self.config = config
        paths = [Path(config[k]) for k in ('person_weights', 'phone_weights')]
        paths = [p if p.is_absolute() else ROOT / p for p in paths]
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f'Missing pretrained model: {path}. Run setup_models.py first.')
        self.pose, self.objects = [YOLO(str(p)) for p in paths]
        if self.pose.names != {0: 'person'}:
            raise ValueError('Expected a COCO person pose model')
        if self.objects.names.get(67) != 'cell phone':
            raise ValueError('Expected COCO cell phone class 67')

    def __call__(self, frame):
        import math
        import torch
        device = self.config.get('device', 'cpu')
        if device in ('cuda', 0, '0') and not torch.cuda.is_available():
            device = 'cpu'
        imgsz = self.config.get('detector_imgsz', 'auto')
        if imgsz == 'auto' or str(imgsz).lower() in ('auto', 'native', 'none'):
            h, w = frame.shape[:2]
            imgsz = (math.ceil(h / 32) * 32, math.ceil(w / 32) * 32)
        common = dict(imgsz=imgsz, device=device, verbose=False)
        persons = self.pose.predict(frame, conf=self.config['person_conf'], iou=self.config['person_iou'], **common)[0]
        phones = self.objects.predict(frame, classes=[67], conf=self.config['phone_conf'], iou=self.config['phone_iou'], **common)[0]
        return persons, phones
