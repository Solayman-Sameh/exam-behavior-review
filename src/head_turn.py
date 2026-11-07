"""Quality-gated, camera-relative head motion; no eye-gaze or misconduct inference."""
from collections import deque
from dataclasses import dataclass,field
from statistics import median
import math


@dataclass
class HeadState:
    track_id: int
    quality: str = 'unusable'
    ratio: float | None = None
    offset: float | None = None
    baseline: float | None = None
    delta: float | None = None
    direction: str | None = None
    neighbor_id: int | None = None
    looking: bool = False
    sustained_s: float = 0
    episodes: int = 0
    qualified: bool = False
    reason: str = 'unknown_keypoints'
    vertical_delta: float | None = None
    face_pitch_delta: float | None = None


@dataclass
class HeadMemory:
    enrolled_at: float
    samples: list = field(default_factory=list)
    baseline: float | None = None
    baseline_y: float | None = None
    last_valid: float | None = None
    target: int | None = None
    direction: str | None = None
    evidence_s: float = 0
    good_evidence_s: float = 0
    neutral_s: float = 0
    counted: bool = False
    episodes: deque = field(default_factory=deque)
    last_seen: float = 0
    count_blocked: bool = False
    baseline_pitch: dict = field(default_factory=dict)
    face_samples: list = field(default_factory=list)


class HeadTurnAnalyzer:
    def __init__(self,config):
        self.config=config
        self.memories={}
        self.last_time=None

    def features(self,person,frame_shape):
        kp=person.keypoints
        if kp is None or len(kp)!=17:
            return None
        conf=self.config['head_keypoint_conf']
        h,w=frame_shape[:2]
        def valid(i):
            return (len(kp[i])>=3 and all(math.isfinite(float(v)) for v in kp[i]) and kp[i][2]>=conf
                    and 0<float(kp[i][0])<w and 0<float(kp[i][1])<h)
        if not all(valid(i) for i in (0,5,6)) or not any(valid(i) for i in (1,2,3,4)):
            return None
        # Small/occluded faces cannot support rapid head-movement alerts.
        eye_conf=self.config.get('head_eye_conf',0)
        if not all(valid(i) and kp[i][2]>=eye_conf for i in (1,2)):
            return None
        eye_width=math.dist(kp[1][:2],kp[2][:2])
        if eye_width<self.config.get('head_min_eye_width',0)*w/768:
            return None
        if person.box[3]-person.box[1] < h*self.config['head_min_person_height_fraction']:
            return None
        shoulder_width=abs(float(kp[5][0]-kp[6][0]))
        if shoulder_width<self.config['head_min_shoulder_width']*w/768:
            return None
        cx=float(kp[5][0]+kp[6][0])/2
        cy=float(kp[5][1]+kp[6][1])/2
        offset=(float(kp[0][0])-cx)/shoulder_width
        vertical=(float(kp[0][1])-cy)/shoulder_width
        ear_ratio=None
        if valid(3) and valid(4):
            ear_width=abs(float(kp[3][0]-kp[4][0]))
            if ear_width>=self.config['head_min_ear_width']*w/768:
                ear_ratio=max(-1.,min(1.,(float(kp[0][0])-(float(kp[3][0])+float(kp[4][0]))/2)/ear_width))
        # Nose/ear vertical position normalized by eye separation: a face-local
        # check against shoulder jitter. Never infer a turn from ear absence.
        pitch={i:(float(kp[0][1])-float(kp[i][1]))/max(eye_width,1) for i in (3,4) if valid(i)}
        return dict(offset=offset,vertical=vertical,ear_ratio=ear_ratio,cx=cx,cy=cy,pitch=pitch,
                    quality='good' if ear_ratio is not None else 'partial')

    def neighbor(self,person,direction,tracking,features,width):
        own=features[person.track_id]
        candidates=[]
        for other in tracking.persons:
            if other.track_id==person.track_id:
                continue
            target=features.get(other.track_id)
            if target is None:
                # A neighbor need not expose their face. Use tracked body geometry.
                x1,y1,x2,y2=other.box
                target={'cx':(x1+x2)/2,'cy':(y1+y2)/2}
                kp=other.keypoints
                if kp is not None and len(kp)==17 and all(
                    len(kp[i])>=3 and kp[i][2]>=self.config['head_keypoint_conf']
                    and kp[i][0]>0 and kp[i][1]>0 for i in (5,6)):
                    target={'cx':float(kp[5][0]+kp[6][0])/2,'cy':float(kp[5][1]+kp[6][1])/2}
            dx=target['cx']-own['cx']
            if (direction=='right' and dx<=0) or (direction=='left' and dx>=0):
                continue
            if abs(dx)>self.config['head_neighbor_max_distance']*width/768:
                continue
            own_height=person.box[3]-person.box[1]
            target_height=other.box[3]-other.box[1]
            ratio=target_height/max(own_height,1)
            if not self.config['head_neighbor_min_height_ratio']<=ratio<=self.config['head_neighbor_max_height_ratio']:
                continue
            if abs(target['cy']-own['cy'])>self.config['head_neighbor_row_tolerance']*max(own_height,target_height):
                continue
            candidates.append((abs(dx),other.track_id))
        return min(candidates)[1] if candidates else None

    @staticmethod
    def _clear_look(memory):
        memory.target=None
        memory.direction=None
        memory.evidence_s=0
        memory.good_evidence_s=0
        memory.neutral_s=0
        memory.counted=False

    def update(self,tracking,time_s,fps,frame_shape):
        if self.last_time is not None and time_s<=self.last_time:
            raise ValueError('Head timestamps must increase strictly')
        dt=1/fps if self.last_time is None else min(time_s-self.last_time,1/fps)
        self.last_time=time_s
        features={p.track_id:f for p in tracking.persons if (f:=self.features(p,frame_shape)) is not None}
        states={}
        for person in tracking.persons:
            pid=person.track_id
            memory=self.memories.setdefault(pid,HeadMemory(time_s))
            memory.last_seen=time_s
            state=HeadState(pid)
            states[pid]=state
            while memory.episodes and time_s-memory.episodes[0][0]>self.config['head_repeat_window_s']:
                memory.episodes.popleft()
            feature=features.get(pid)
            if feature is None:
                if memory.last_valid is None or time_s-memory.last_valid>self.config['head_unknown_gap_s']:
                    memory.count_blocked=memory.count_blocked or memory.counted
                    self._clear_look(memory)
                continue
            if memory.last_valid is not None and time_s-memory.last_valid>self.config['head_unknown_gap_s']:
                memory.count_blocked=memory.count_blocked or memory.counted
                self._clear_look(memory)
            memory.last_valid=time_s
            state.quality=feature['quality']
            state.ratio=feature['ear_ratio']
            state.offset=feature['offset']
            if memory.baseline is None:
                memory.samples.append((time_s,feature['offset'],feature['vertical']))
                memory.face_samples.append(feature['pitch'])
                if len(memory.samples)<self.config['head_baseline_min_samples'] or time_s-memory.samples[0][0]<self.config['head_baseline_s']:
                    state.reason='calibrating'
                    continue
                memory.baseline=median(v[1] for v in memory.samples)
                memory.baseline_y=median(v[2] for v in memory.samples)
                # Retain the ears reliably observed throughout enrollment.
                # A visibility change must not change the reference geometry.
                anchors=set.intersection(*(set(v) for v in memory.face_samples))
                memory.baseline_pitch={i:median(v[i] for v in memory.face_samples) for i in anchors}
                memory.samples.clear()
                memory.face_samples.clear()
            state.baseline=memory.baseline
            state.delta=feature['offset']-memory.baseline
            if abs(state.delta)>=self.config['head_turn_threshold']:
                state.direction='right' if state.delta>0 else 'left'
            vertical_change=feature['vertical']-memory.baseline_y
            state.vertical_delta=vertical_change
            pitch_changes=([feature['pitch'][i]-baseline for i,baseline in memory.baseline_pitch.items()]
                           if memory.baseline_pitch.keys() <= feature['pitch'].keys() else [])
            state.face_pitch_delta=median(pitch_changes) if pitch_changes else None
            looking_up=(vertical_change < -self.config['head_upward_threshold'] and
                        abs(vertical_change)>=abs(state.delta)*self.config['head_upward_dominance_ratio'])
            if state.direction and not looking_up:
                state.neighbor_id=self.neighbor(person,state.direction,tracking,features,frame_shape[1])
            state.looking=state.neighbor_id is not None
            # Frontward head raises need their own route: lateral neighbor
            # matching cannot describe a student seated directly ahead.
            # This records a head raise for review, not measured paper gaze.
            forward=(self.config.get('head_forward_enabled',False) and
                     vertical_change <= -self.config['head_forward_threshold'] and
                     state.face_pitch_delta is not None and
                     state.face_pitch_delta <= -self.config['head_forward_face_threshold'])
            if forward:
                state.direction='forward'
                state.neighbor_id=None
                state.looking=True
            if state.looking:
                if memory.target!=state.neighbor_id or memory.direction!=state.direction:
                    self._clear_look(memory)
                    memory.target=state.neighbor_id
                    memory.direction=state.direction
                memory.neutral_s=0
                memory.evidence_s+=dt
                if state.quality=='good':memory.good_evidence_s+=dt
                quality_ready=(self.config['head_allow_partial_alerts'] or
                               (state.quality=='good' and memory.good_evidence_s>=self.config['head_min_good_evidence_s']))
                if memory.evidence_s>=self.config['head_min_episode_s'] and quality_ready and not memory.counted and not memory.count_blocked:
                    memory.episodes.append((time_s,memory.target,memory.direction))
                    memory.counted=True
                state.sustained_s=memory.evidence_s
                state.episodes=sum(1 for _,target,direction in memory.episodes if target==memory.target and direction==memory.direction)
                repeated=(state.episodes>=self.config['head_repeat_count'] and
                          memory.evidence_s>=self.config['head_min_episode_s'])
                duration=self.config.get('head_forward_sustained_s',self.config['head_sustained_s']) if state.direction=='forward' else self.config['head_sustained_s']
                sustained=state.sustained_s>=max(duration,self.config['head_min_episode_s'])
                state.qualified=repeated or sustained
                state.reason='repeated' if repeated else ('sustained' if sustained else 'candidate')
                if state.qualified and not quality_ready:
                    state.qualified=False
                    state.reason='quality_limited_candidate'
            else:
                memory.neutral_s+=dt
                if memory.neutral_s>=self.config['head_episode_release_s']:
                    self._clear_look(memory)
                    memory.count_blocked=False
                state.reason='upward' if looking_up else ('no_neighbor' if state.direction else 'neutral')
        for pid,memory in list(self.memories.items()):
            if pid not in states and time_s-memory.last_seen>self.config['head_unknown_gap_s']:
                memory.count_blocked=memory.count_blocked or memory.counted
                self._clear_look(memory)
            if time_s-memory.last_seen>self.config['head_state_expiry_s']:
                del self.memories[pid]
        return states
