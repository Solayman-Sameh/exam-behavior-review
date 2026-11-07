from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path=None):
    path = Path(path) if path else ROOT / 'configs/thresholds.yaml'
    with path.open(encoding='utf-8') as handle:
        config = yaml.safe_load(handle)
    if config['layer'] not in (0,1):
        raise ValueError('Only phone and head-turn layers are implemented.')
    for key in ('phone_persistence_s', 'episode_release_s', 'cooldown_seconds'):
        if config[key] <= 0:
            raise ValueError(f'{key} must be positive')
    if config['layer']>=1:
        for key in ('head_turn_threshold','head_baseline_s','head_min_episode_s',
                    'head_sustained_s','head_repeat_count','head_unknown_gap_s'):
            if config[key]<=0:
                raise ValueError(f'{key} must be positive')
        for key in ('head_eye_conf','head_min_eye_width'):
            value=config.get(key,0)
            if value<0 or (key=='head_eye_conf' and value>1):
                raise ValueError(f'{key} is outside its valid range')
        if config.get('head_forward_enabled',False):
            for key in ('head_forward_threshold','head_forward_face_threshold','head_forward_sustained_s'):
                if config.get(key,0)<=0:
                    raise ValueError(f'{key} must be positive with forward head review enabled')
    return config
