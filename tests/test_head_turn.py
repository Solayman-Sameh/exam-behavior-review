import unittest
import numpy as np
from pathlib import Path
import hashlib,json,yaml
from src.config import load_config
from src.head_turn import HeadTurnAnalyzer
from src.head_events import HeadEventEngine
from src.layered_events import LayeredEventEngine
from src.types import Track,TrackingResult,PhoneSignal


def person(pid,cx,dx=0,dy=0,visible=True):
    kp=np.zeros((17,3),dtype=np.float32)
    for i,x,y in [(0,cx+dx,140+dy),(1,cx+dx-12,132+dy),(2,cx+dx+12,132+dy),
                  (3,cx-20,140),(4,cx+20,140),(5,cx-60,200),(6,cx+60,200)]:
        kp[i]=[x,y,.95 if visible else .05]
    return Track(pid,(cx-80,80,cx+80,400),.95,kp)


class HeadTurnTests(unittest.TestCase):
    def setUp(self):
        self.config=load_config()
        self.config['layer']=1
        self.analyzer=HeadTurnAnalyzer(self.config)
        self.engine=HeadEventEngine(self.config)
        self.frame=0
        self.events=[]

    def step(self,dx=0,dy=0,visible=True,neighbor=True,frames=1):
        state=None
        for _ in range(frames):
            people=[person(1,180,dx,dy,visible)]
            if neighbor:people.append(person(2,480))
            now=self.frame/24
            states=self.analyzer.update(TrackingResult(people),now,24,(432,768,3))
            self.events.extend(self.engine.update(states,now))
            state=states[1]
            self.frame+=1
        return state

    def enroll(self):
        self.step(frames=24)

    def test_single_brief_glance_does_not_alert(self):
        self.enroll();self.step(dx=24,frames=8);self.step(frames=30)
        self.assertFalse(self.events)

    def test_repeat_rule_requires_minimum_evidence_for_each_new_look(self):
        self.enroll()
        for _ in range(3):
            self.step(dx=24,frames=12);self.step(frames=12)
        self.assertEqual(len(self.events),2)
        self.assertGreaterEqual(self.events[1]['video_time_s'],3.3)
        self.assertEqual(self.events[0]['behavior_type'],'peer_directed_looking')
        self.assertEqual(self.events[0]['track_id'],1)

    def test_two_glances_trigger_repeat_rule(self):
        self.enroll()
        for _ in range(2):
            self.step(dx=24,frames=12);self.step(frames=12)
        self.assertEqual(len(self.events),1)
        self.assertEqual(self.events[0]['behavior_type'],'peer_directed_looking')

    def test_long_peer_look_triggers_once(self):
        self.enroll();self.step(dx=24,frames=180)
        self.assertEqual(len(self.events),1)
        self.assertGreaterEqual(self.events[0]['video_time_s'],1.8)
        self.assertLess(self.events[0]['video_time_s'],2.0)

    def test_no_neighbor_means_no_head_event(self):
        self.enroll();self.step(dx=24,neighbor=False,frames=120)
        self.assertFalse(self.events)

    def test_upward_motion_suppresses_candidate(self):
        self.config['head_forward_enabled']=False
        self.enroll();self.step(dx=24,dy=-30,frames=120)
        self.assertFalse(self.events)

    def test_unknown_gap_cannot_manufacture_repeated_looks(self):
        self.enroll()
        for _ in range(4):
            self.step(dx=24,frames=12)
            self.step(visible=False,frames=12)
        self.assertFalse(self.events)

    def test_missing_keypoints_do_not_add_duration(self):
        self.enroll();self.step(dx=24,frames=12)
        self.step(visible=False,frames=120)
        state=self.step(dx=24,frames=12)
        self.assertLess(state.sustained_s,1)
        self.assertFalse(self.events)

    def test_default_profile_is_calibrated_as_neutral(self):
        self.step(dx=30,frames=150)
        self.assertFalse(self.events)

    def test_camera_scale_invariance(self):
        self.enroll()
        a=person(1,180,24)
        feature=self.analyzer.features(a,(432,768,3))
        a.box=tuple(x*2 for x in a.box);a.keypoints[:,:2]*=2
        scaled=self.analyzer.features(a,(864,1536,3))
        self.assertAlmostEqual(feature['offset'],scaled['offset'])

    def test_repeated_episodes_expire(self):
        self.enroll()
        for _ in range(3):
            self.step(dx=24,frames=12);self.step(frames=400)
        self.assertFalse(self.events)

    def test_phone_engine_stays_independent(self):
        engine=LayeredEventEngine(self.config)
        events=[]
        for frame in range(100):
            events.extend(engine.update({1:PhoneSignal(1,4,.9)},{},frame/24,24))
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['behavior_type'],'phone_detected')

    def test_user_accepted_phone_settings_and_sources_preserved(self):
        root=Path(__file__).resolve().parents[1]
        accepted=yaml.safe_load((root/'docs/accepted_baseline/thresholds.yaml').read_text())
        for key,value in accepted.items():
            if key!='layer':self.assertEqual(self.config[key],value,key)
        hashes=json.loads((root/'docs/accepted_baseline/source_hashes.json').read_text())
        for name in ('src/behavior.py','src/events.py','src/detection.py','src/tracking.py'):
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),hashes[name],name)

    def test_neighbor_can_have_occluded_face(self):
        self.enroll()
        other=person(2,480)
        other.keypoints[:5,2]=0
        state=None
        for _ in range(100):
            now=self.frame/24
            states=self.analyzer.update(TrackingResult([person(1,180,24),other]),now,24,(432,768,3))
            self.events.extend(self.engine.update(states,now));self.frame+=1
            state=states[1]
        self.assertEqual(state.neighbor_id,2)
        self.assertEqual(len(self.events),1)

    def test_missing_ears_do_not_block_supported_side_look(self):
        self.enroll()
        for _ in range(150):
            subject=person(1,180,24)
            subject.keypoints[3:5,2]=0
            now=self.frame/24
            states=self.analyzer.update(TrackingResult([subject,person(2,480)]),now,24,(432,768,3))
            self.events.extend(self.engine.update(states,now));self.frame+=1
        self.assertTrue(states[1].looking)
        self.assertEqual(states[1].reason,'sustained')
        self.assertEqual(len(self.events),1)

    def test_forward_head_raise_has_separate_honest_label(self):
        self.enroll();self.step(dy=-30,frames=24)
        self.assertEqual(len(self.events),1)
        self.assertEqual(self.events[0]['behavior_type'],'head_raise')
        self.assertNotIn('neighbor #',self.events[0]['evidence'])

    def test_shoulder_jitter_alone_does_not_create_forward_alert(self):
        self.enroll()
        for _ in range(100):
            subject=person(1,180)
            subject.keypoints[5:7,1]+=40
            now=self.frame/24
            states=self.analyzer.update(TrackingResult([subject]),now,24,(432,768,3))
            self.events.extend(self.engine.update(states,now));self.frame+=1
        self.assertFalse(self.events)

    def test_small_or_unreliable_eyes_do_not_alert(self):
        self.enroll()
        for _ in range(100):
            subject=person(1,180,24)
            subject.keypoints[1,2]=.35
            now=self.frame/24
            states=self.analyzer.update(TrackingResult([subject,person(2,480)]),now,24,(432,768,3))
            self.events.extend(self.engine.update(states,now));self.frame+=1
        self.assertFalse(self.events)

    def test_second_short_look_alerts_before_truncated_video_end(self):
        self.enroll();self.step(dx=24,frames=24);self.step(frames=36)
        self.step(dx=24,frames=18)
        self.assertEqual(len(self.events),2)

    def test_subsecond_noise_cannot_bypass_forward_minimum_episode(self):
        self.config['head_forward_sustained_s']=.1
        self.enroll();self.step(dy=-30,frames=6);self.step(frames=24)
        self.assertFalse(self.events)

    def test_ear_anchor_does_not_change_when_other_ear_appears(self):
        self.enroll()
        # Both anchors enrolled; losing one is not a forward movement.
        for _ in range(48):
            subject=person(1,180)
            subject.keypoints[3,2]=0
            now=self.frame/24
            states=self.analyzer.update(TrackingResult([subject]),now,24,(432,768,3))
            self.events.extend(self.engine.update(states,now));self.frame+=1
        self.assertFalse(self.events)

    def test_lost_enrolled_ear_cannot_change_forward_pitch_reference(self):
        self.enroll()
        for _ in range(48):
            subject=person(1,180,dy=-30)
            subject.keypoints[3,2]=0
            now=self.frame/24
            states=self.analyzer.update(TrackingResult([subject]),now,24,(432,768,3))
            self.events.extend(self.engine.update(states,now));self.frame+=1
        self.assertFalse(self.events)


if __name__=='__main__':
    unittest.main()
