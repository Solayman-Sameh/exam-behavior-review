from dataclasses import dataclass, field
from typing import Any


@dataclass
class Track:
    track_id: int
    box: tuple[float, float, float, float]
    conf: float
    keypoints: Any = None


@dataclass
class TrackingResult:
    persons: list[Track] = field(default_factory=list)
    phones: list[Track] = field(default_factory=list)


@dataclass
class PhoneSignal:
    person_id: int
    phone_id: int
    confidence: float

