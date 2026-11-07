from .events import EventEngine as PhoneEventEngine
from .head_events import HeadEventEngine


class LayeredEventEngine:
    def __init__(self,config):
        self.phone=PhoneEventEngine(config)
        self.head=HeadEventEngine(config) if config['layer']>=1 else None

    def update(self,signals,head_states,time_s,fps):
        events=self.phone.update(signals,time_s,fps)
        if self.head:
            events+=self.head.update(head_states,time_s)
        return events

    def get_active_alerts(self):
        active=self.phone.get_active_alerts()
        return active|self.head.get_active_alerts() if self.head else active
