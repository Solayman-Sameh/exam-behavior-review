from types import SimpleNamespace
from .types import Track, TrackingResult


class Tracker:
    """ByteTrack instances are recreated for each video; IDs are class-local."""

    def __init__(self, fps, config):
        from ultralytics.trackers.byte_tracker import BYTETracker
        args = SimpleNamespace(**{k: config[k] for k in (
            'track_high_thresh', 'track_low_thresh', 'new_track_thresh',
            'track_buffer', 'match_thresh')}, fuse_score=True)
        # Ultralytics scales buffers by fps / 30; config counts source frames.
        args.track_buffer = round(config['track_buffer'] * 30 / fps)
        try:
            self.persons = BYTETracker(args, frame_rate=fps)
            self.phones = BYTETracker(args, frame_rate=fps)
        except TypeError:
            self.persons = BYTETracker(args)
            self.phones = BYTETracker(args)

    @staticmethod
    def _update(tracker, result, frame):
        rows = tracker.update(result.boxes.cpu().numpy(), frame)
        keypoints = result.keypoints.cpu().numpy().data if result.keypoints is not None else None
        tracks = []
        for row in rows:
            index = int(row[-1])
            kp = keypoints[index] if keypoints is not None else None
            tracks.append(Track(int(row[4]), tuple(float(x) for x in row[:4]), float(row[5]), kp))
        return tracks

    def update(self, detections, frame):
        persons, phones = detections
        phone_tracks = self._update(self.phones, phones, frame)
        valid_phones = [
            p for p in phone_tracks
            if min(p.box[2] - p.box[0], p.box[3] - p.box[1]) > 0 and
            max(p.box[2] - p.box[0], p.box[3] - p.box[1]) / min(p.box[2] - p.box[0], p.box[3] - p.box[1]) <= 3.0
        ]
        return TrackingResult(self._update(self.persons, persons, frame), valid_phones)
