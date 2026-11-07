import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Compare phone behavior frame-for-frame against the accepted-code baseline."""
import json
from pathlib import Path
from src.config import ROOT


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,default=ROOT/'reports/accepted_baseline')
    parser.add_argument('--current',type=Path,default=ROOT/'reports/relocation_validation')
    args=parser.parse_args()
    old,new=args.baseline,args.current
    baseline=json.loads((old/'evaluation.json').read_text())
    current=json.loads((new/'evaluation.json').read_text())
    checks=[]
    for before,after in zip(baseline,current):
        assert before['video']==after['video']
        def events(summary):
            return [(e['track_id'],e['video_time_s'],e['confidence'],e['evidence'])
                    for e in summary['events'] if e['behavior_type']=='phone_detected']
        assert events(before)==events(after),f'Phone event regression: {before["video"]}'
        def frames(root,summary):
            return [json.loads(line) for line in (root/'runs'/summary['run_id']/'frames.jsonl').read_text().splitlines()]
        first,second=frames(old,before),frames(new,after)
        assert len(first)==len(second)
        for a,b in zip(first,second):
            for key in ('associated_persons','active_phone_alerts','phones','persons'):
                assert a[key]==b[key],f'{before["video"]} frame {a["frame"]}: changed {key}'
        checks.append({'video':before['video'],'frames_compared':len(first),'identical_phone_behavior':True,
                       'phone_alerts':len(events(after))})
    result={'pass':True,'total_frames':sum(c['frames_compared'] for c in checks),'clips':checks}
    (new/'phone_regression.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
