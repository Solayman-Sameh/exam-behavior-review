from math import hypot
from .types import PhoneSignal


class BehaviorAnalyzer:
    """Layer 0: conservative, resolution-scaled phone ownership association."""

    def __init__(self, config):
        self.config = config

    def update(self, tracking, frame_width):
        signals = {}
        for phone in tracking.phones:
            phone_width = phone.box[2]-phone.box[0]
            phone_height = phone.box[3]-phone.box[1]
            if min(phone_width,phone_height) <= 0:
                continue
            if max(phone_width,phone_height)/min(phone_width,phone_height) > self.config['phone_max_aspect_ratio']:
                continue
            px = (phone.box[0] + phone.box[2]) / 2
            py = (phone.box[1] + phone.box[3]) / 2
            candidates = []
            for person in tracking.persons:
                x1, y1, x2, y2 = person.box
                width, height = x2-x1, y2-y1
                margin = self.config['association_box_margin']
                if not (x1-width*margin <= px <= x2+width*margin and
                        y1-height*margin <= py <= y2+height*margin):
                    continue
                distance = hypot(px-(x1+x2)/2, py-(y1+y2)/2)
                if distance > self.config['phone_person_max_distance'] * frame_width / 768:
                    continue
                candidates.append((distance / max(width, height, 1), person.track_id))
            candidates.sort()
            if not candidates:
                continue
            if len(candidates) > 1 and candidates[1][0]-candidates[0][0] < self.config['association_ambiguity_margin']:
                continue  # Ambiguous ownership is unknown, never assigned arbitrarily.
            person_id = candidates[0][1]
            signal = PhoneSignal(person_id, phone.track_id, phone.conf)
            if person_id not in signals or signals[person_id].confidence < phone.conf:
                signals[person_id] = signal
        return signals
