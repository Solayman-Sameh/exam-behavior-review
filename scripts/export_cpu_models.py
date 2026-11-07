import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Optional FP32 ONNX export for CPU evaluation; original PT weights are retained."""
import torch
from ultralytics import YOLO
from src.config import ROOT


if __name__=='__main__':
    torch.set_num_threads(2)
    for name in ('yolo11n-pose.pt','yolo11n.pt'):
        path=ROOT/'models'/name
        if path.with_suffix('.onnx').exists():
            continue
        print('EXPORT',name,flush=True)
        YOLO(str(path)).export(format='onnx',imgsz=(448,768),opset=17,
                               simplify=False,dynamic=False,device='cpu')
