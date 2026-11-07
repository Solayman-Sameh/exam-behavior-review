from .events import Episode


class HeadEventEngine:
    """Independent head episodes cannot suppress, overwrite or delay phone alerts."""
    def __init__(self,config):
        self.config=config
        self.episodes={}

    def update(self,states,time_s):
        fired=[]
        for pid in set(states)|set(self.episodes):
            state=states.get(pid)
            episode=self.episodes.setdefault(pid,Episode())
            visible_look=bool(state and state.looking)
            if episode.state=='ALERT':
                if visible_look:
                    episode.last_seen=time_s
                elif time_s-episode.last_seen>=self.config['head_alert_release_s']:
                    episode.state='COOLDOWN'
                    episode.cooldown_until=time_s+self.config['head_cooldown_s']
                continue
            if episode.state=='COOLDOWN':
                if time_s<episode.cooldown_until:
                    continue
                episode.state='NORMAL'
            if not state or not state.qualified:
                episode.state='CANDIDATE' if visible_look else 'NORMAL'
                continue
            episode.state='ALERT'
            episode.last_seen=time_s
            forward=state.direction=='forward'
            strength=min(1.,abs(state.vertical_delta if forward else state.delta)/(2.5*(self.config['head_forward_threshold'] if forward else self.config['head_turn_threshold'])))
            duration=self.config['head_forward_sustained_s'] if forward else self.config['head_sustained_s']
            persistence=min(1.,max(state.sustained_s/(1.5*duration),
                                   state.episodes/(self.config['head_repeat_count']+1)))
            score=min(.99,.45*strength+.4*persistence+(.15 if state.quality=='good' else .08))
            description=(f'Frontward head raise {state.vertical_delta:+.3f} shoulder widths; face-local pitch change {state.face_pitch_delta:+.3f}' if forward else f'Head shift {state.delta:+.3f} shoulder widths toward {state.direction} neighbor #{state.neighbor_id}')
            fired.append(dict(track_id=pid,behavior_type='head_raise' if forward else 'peer_directed_looking',confidence=score,
                video_time_s=time_s,evidence=(f'{description}; {state.sustained_s:.2f}s observed, '
                f'{state.episodes} distinct episodes ({state.reason}). '
                'Heuristic evidence score, not eye gaze or a cheating probability.')))
        return fired

    def get_active_alerts(self):
        return {pid for pid,episode in self.episodes.items() if episode.state in ('ALERT','COOLDOWN')}
