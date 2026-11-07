"""Optional FP32 CPU backend for the same weights, native 768x432 test clips."""
from pathlib import Path
from .config import ROOT


class OnnxDetector:
    def __init__(self,config):
        import onnxruntime as ort
        import torch
        torch.set_num_threads(2)
        self.config=config
        options=ort.SessionOptions()
        options.intra_op_num_threads=2
        options.inter_op_num_threads=1
        self.sessions=[]
        for key in ('person_weights','phone_weights'):
            path=Path(config[key]).with_suffix('.onnx')
            if not path.is_absolute():path=ROOT/path
            self.sessions.append(ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']))

    def __call__(self,frame):
        import numpy as np
        import torch
        from ultralytics.data.augment import LetterBox
        from ultralytics.utils import ops
        from ultralytics.engine.results import Results
        if frame.shape[:2]!=(432,768) or self.config['detector_imgsz']!='auto':
            raise ValueError('This optional CPU export supports native 768x432 clips only; use the standard PT detector for other sizes.')
        image=LetterBox(new_shape=(448,768),auto=False,stride=32)(image=frame)
        tensor=np.ascontiguousarray(image[:,:,::-1].transpose(2,0,1)[None],dtype=np.float32)/255.
        results=[]
        for i,session in enumerate(self.sessions):
            raw=session.run(None,{session.get_inputs()[0].name:tensor})[0]
            prediction=ops.non_max_suppression(torch.from_numpy(raw),
                conf_thres=self.config['person_conf' if i==0 else 'phone_conf'],
                iou_thres=self.config['person_iou' if i==0 else 'phone_iou'],
                classes=[0] if i==0 else [67],nc=1 if i==0 else 80)[0]
            ops.scale_boxes((448,768),prediction[:,:4],frame.shape)
            kwargs={}
            if i==0:
                keypoints=prediction[:,6:].reshape(-1,17,3)
                ops.scale_coords((448,768),keypoints,frame.shape)
                kwargs['keypoints']=keypoints
            results.append(Results(frame,path='',names={0:'person'} if i==0 else {67:'cell phone'},
                                   boxes=prediction[:,:6],**kwargs))
        return tuple(results)
