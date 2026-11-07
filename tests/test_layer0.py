import tempfile
import unittest
from pathlib import Path

from app.db import AlertDatabase
from src.behavior import BehaviorAnalyzer
from src.config import load_config
from src.events import EventEngine
from src.types import PhoneSignal, Track, TrackingResult


class Layer0Tests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_short_detection_never_alerts(self):
        engine = EventEngine(self.config)
        for frame in range(4):
            self.assertEqual(engine.update({1: PhoneSignal(1,2,.8)},frame/24,24),[])
        self.assertEqual(engine.update({},4/24,24),[])

    def test_continuous_episode_has_one_alert(self):
        engine = EventEngine(self.config)
        events = []
        for frame in range(300):
            events.extend(engine.update({1: PhoneSignal(1,2,.8)},frame/24,24))
        self.assertEqual(len(events),1)
        self.assertAlmostEqual(events[0]['video_time_s'],4/24)
        self.assertEqual(engine.get_active_alerts(),{1})

    def test_video_fps_independent_persistence(self):
        for fps in (12,24,30,60):
            engine = EventEngine(self.config)
            events = []
            for frame in range(fps):
                events.extend(engine.update({1: PhoneSignal(1,2,.8)},frame/fps,fps))
            self.assertEqual(len(events),1)
            self.assertGreaterEqual(events[0]['video_time_s']+1/fps+1e-9,self.config['phone_persistence_s'])

    def test_candidate_resets_on_missing_observation(self):
        engine = EventEngine(self.config)
        for frame in range(30):
            signals = {} if frame % 4 == 3 else {1: PhoneSignal(1,2,.8)}
            self.assertFalse(engine.update(signals,frame/24,24))

    def test_second_episode_after_release_and_cooldown(self):
        engine = EventEngine(self.config)
        events=[]
        for frame in range(180):
            signals = {1: PhoneSignal(1,2,.8)} if frame<20 or frame>=150 else {}
            events.extend(engine.update(signals,frame/24,24))
        self.assertEqual(len(events),2)

    def test_non_monotonic_time_rejected(self):
        engine=EventEngine(self.config)
        engine.update({},0,24)
        with self.assertRaises(ValueError):
            engine.update({},0,24)

    def test_weak_detection_cannot_start_alert_but_can_maintain_episode(self):
        engine = EventEngine(self.config)
        for frame in range(24):
            self.assertFalse(engine.update({1: PhoneSignal(1,2,.3)},frame/24,24))
        events=[]
        for frame in range(24,48):
            events.extend(engine.update({1: PhoneSignal(1,2,.8)},frame/24,24))
        self.assertEqual(len(events),1)
        for frame in range(48,240):
            self.assertFalse(engine.update({1: PhoneSignal(1,2,.2)},frame/24,24))
        self.assertEqual(engine.get_active_alerts(),{1})

    def test_thin_book_like_detection_is_excluded(self):
        tracks=TrackingResult([Track(1,(0,0,400,400),.9)],[Track(2,(100,200,220,218),.9)])
        self.assertFalse(BehaviorAnalyzer(self.config).update(tracks,768))

    def test_weak_detections_do_not_extend_expired_cooldown(self):
        engine=EventEngine(self.config)
        for frame in range(12):
            engine.update({1: PhoneSignal(1,2,.8)},frame/24,24)
        for frame in range(12,48):
            engine.update({},frame/24,24)
        for frame in range(48,240):
            engine.update({1: PhoneSignal(1,2,.2)},frame/24,24)
        self.assertFalse(engine.get_active_alerts())

    def test_correct_phone_owner_and_no_neighbor_required(self):
        tracks=TrackingResult([Track(1,(0,0,150,400),.9),Track(2,(180,0,400,400),.9)],
                              [Track(7,(320,300,350,330),.8)])
        signals=BehaviorAnalyzer(self.config).update(tracks,768)
        self.assertEqual(set(signals),{2})

    def test_ambiguous_owner_is_unknown(self):
        tracks=TrackingResult([Track(1,(0,0,200,300),.9),Track(2,(0,0,200,300),.9)],
                              [Track(7,(90,150,110,170),.8)])
        self.assertFalse(BehaviorAnalyzer(self.config).update(tracks,768))

    def test_far_phone_has_no_owner(self):
        tracks=TrackingResult([Track(1,(0,0,100,100),.9)],[Track(2,(500,300,520,320),.8)])
        self.assertFalse(BehaviorAnalyzer(self.config).update(tracks,768))

    def test_association_scales_with_resolution(self):
        def result(scale):
            tracks=TrackingResult([Track(1,tuple(v*scale for v in (180,0,400,400)),.9)],
                                  [Track(7,tuple(v*scale for v in (320,300,350,330)),.8)])
            return set(BehaviorAnalyzer(self.config).update(tracks,768*scale))
        self.assertEqual(result(1),result(2))

    def test_database_survives_reopen_and_preserves_separate_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'alerts.db'
            event=dict(event_id='a',run_id='r1',video_filename='clip02.mp4',track_id=2,
                       behavior_type='phone_detected',confidence=.8,evidence='review',video_time_s=.2,
                       wall_time='2026-11-03T00:00:00+00:00',screenshot_path='screenshots/a.jpg')
            first=AlertDatabase(path).insert_alert(event)
            reopened=AlertDatabase(path)
            self.assertEqual(reopened.get_alert_by_id(first)['screenshot_path'],'screenshots/a.jpg')
            event.update(event_id='b',run_id='r2')
            reopened.insert_alert(event)
            self.assertEqual(len(reopened.get_alerts()),2)
            reopened.clear_alerts()
            self.assertEqual(len(reopened.get_alerts()),0)


if __name__ == '__main__':
    unittest.main()
