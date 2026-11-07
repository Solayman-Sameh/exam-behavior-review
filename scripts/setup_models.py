import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Explicit online setup; the application itself never downloads weights."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    destination = ROOT/'models'
    destination.mkdir(exist_ok=True)
    manifest = {}
    for name in ('yolo11n-pose.pt','yolo11n.pt'):
        path = destination/name
        url = f'https://github.com/ultralytics/assets/releases/download/v8.3.0/{name}'
        if not path.exists():
            with urllib.request.urlopen(url,timeout=60) as response:
                data = response.read()
            temporary = path.with_suffix('.part')
            temporary.write_bytes(data)
            temporary.replace(path)
        manifest[name] = dict(url=url,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
        print(name,manifest[name]['bytes'])
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2))
