from dataclasses import dataclass


@dataclass
class Episode:
    state: str = 'NORMAL'
    evidence_s: float = 0
    last_seen: float = -1
    cooldown_until: float = 0
    peak_confidence: float = 0


class EventEngine:
    """Per-person/per-behavior episodes measured using video time, never CPU speed."""

    def __init__(self, config):
        self.config = config
        self.episodes = {}
        self.last_time = None

    def update(self, signals, time_s, fps):
        if self.last_time is not None and time_s <= self.last_time:
            raise ValueError('Frame timestamps must increase strictly')
        dt = 1/fps if self.last_time is None else time_s-self.last_time
        self.last_time = time_s
        fired = []
        keys = set(self.episodes) | {(pid, 'phone_detected') for pid in signals}
        for key in keys:
            episode = self.episodes.setdefault(key, Episode())
            signal = signals.get(key[0])
            present = signal is not None
            if not present:
                # Missing observations do not contribute evidence; require continuous
                # evidence to start an episode but tolerate short gaps after alert.
                if episode.state == 'CANDIDATE':
                    episode.state, episode.evidence_s, episode.peak_confidence = 'NORMAL', 0, 0
                elif episode.state == 'ALERT' and time_s-episode.last_seen >= self.config['episode_release_s']:
                    episode.state = 'COOLDOWN'
                    episode.cooldown_until = time_s + self.config['cooldown_seconds']
                elif episode.state == 'COOLDOWN' and time_s >= episode.cooldown_until:
                    episode.state = 'NORMAL'
                    episode.evidence_s = 0
                    episode.peak_confidence = 0
                continue
            episode.last_seen = time_s
            if episode.state == 'COOLDOWN':
                if time_s < episode.cooldown_until:
                    continue
                episode.state, episode.evidence_s, episode.peak_confidence = 'NORMAL', 0, 0
            if episode.state != 'ALERT' and signal.confidence < self.config['phone_alert_min_confidence']:
                if episode.state == 'CANDIDATE':
                    episode.state, episode.evidence_s, episode.peak_confidence = 'NORMAL', 0, 0
                continue
            if episode.state == 'NORMAL':
                episode.state = 'CANDIDATE'
            if episode.state == 'CANDIDATE':
                episode.evidence_s += min(dt, 1/fps)
                episode.peak_confidence = max(episode.peak_confidence, signal.confidence)
                if episode.evidence_s + 1e-9 >= self.config['phone_persistence_s']:
                    episode.state = 'ALERT'
                    fired.append(dict(track_id=key[0], behavior_type=key[1],
                                      confidence=episode.peak_confidence, video_time_s=time_s,
                                      evidence=f'Phone #{signal.phone_id} spatially associated for {episode.evidence_s:.3f}s. Detector score; not a cheating probability.'))
        return fired

    def get_active_alerts(self):
        return {key[0] for key, value in self.episodes.items() if value.state in ('ALERT', 'COOLDOWN')}
