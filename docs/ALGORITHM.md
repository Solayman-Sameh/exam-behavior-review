# Algorithm and threshold reference

## Pipeline

Source frame -> two pretrained YOLO11n models -> separate ByteTrack person/phone tracking -> independent phone and head signals -> temporal event engines -> red/green rendering -> screenshot -> SQLite record -> Tkinter event queue.

The source-time clock for the included constant-frame-rate clips is frame index / FPS. Event timing is independent of inference speed. No behavior model was trained. No inference rule uses a filename, fixed track ID, manual review crop or target timestamp.

## Phone evidence

The pose model detects people and 17 COCO body keypoints; it cannot detect phones. A separate COCO object model supplies class 67 phones. Phone aspect ratios above 3 are rejected. Candidate ownership requires the phone center to lie inside the person box and within a resolution-scaled distance. Competing, similarly plausible owners yield unknown ownership.

An event begins after about 0.2083 seconds of observations meeting the onset confidence of 0.50. Weaker continued tracked detections may maintain an existing episode but cannot start one. The phone engine has its own release and cooldown; head evidence cannot suppress it or require it to have a neighbor.

## Head evidence

The nose and shoulder keypoints must be valid. Both eye keypoints need confidence >=0.60 and eye separation >=20 pixels at 768px frame width; the spatial threshold scales with resolution. A usable shoulder width and sufficiently large person are also required.

Let shoulder center be `(cx, cy)` and horizontal shoulder separation be `s`:

```text
horizontal offset = (nose_x - cx) / s
vertical offset   = (nose_y - cy) / s
```

Neutral medians are enrolled over at least 0.25 seconds and 6 valid samples. The system assumes initially ordinary posture; movement during enrollment can bias this reference.

### Sideways looks

A horizontal shift of at least 0.12 shoulder widths selects image-left or image-right. A plausible tracked neighbor must exist in that direction, subject to distance, body-size and row-position checks. This is approximate image geometry, not a measured gaze ray or desk segmentation. Upward-dominant movement is suppressed on this sideways route.

The engine can qualify 0.85 seconds of observed evidence, or two distinct looks toward the same neighbor/direction in a 15-second window. Each look needs at least 0.35 seconds of current evidence; a previous repeated pattern cannot bypass that minimum. Neutral observations separate episodes. Unknown observations do not add duration or manufacture extra looks.

### Forward head raises

This separate route addresses a head lift that sideways neighbor matching cannot describe. It requires an upward nose displacement of 0.10 shoulder widths and a confirming nose-to-ear vertical change of 0.45 eye widths from enrollment. The enrolled ear reference is fixed; losing an enrolled ear produces unknown confirmation rather than switching reference geometry. Missing ears alone are never evidence of a look.

At least 0.35 seconds of observed evidence is required. The event is `head_raise`, with no asserted paper target. This can also flag ordinary frontward looking; it does not prove copying or distinguish an invigilator glance in every scene.

### Event persistence and output

Head neutral-episode separation is 0.25s. Alert release and cooldown are each 0.35s. Alert boxes remain active during cooldown, so box duration is not the same as measured look duration. Phone and head states are separate.

Screenshots use the rendered red-box frame. A failed image write does not insert a database event. Each event stores run/event IDs, filename, track ID, source time, UTC recording time, behavior, score, evidence and screenshot path. Head scores combine normalized movement, persistence/repetition and geometry quality; they are heuristic evidence scores. Phone scores come from detector evidence. Neither is a cheating probability.

## Configuration

`configs/thresholds.yaml` is the runtime source of truth. `configs/head_turn_defaults.yaml` is a matching reference, not an automatic override. `layer: 0` disables head analysis; `layer: 1` enables it. Device 0 prefers CUDA, and `detector_imgsz: auto` uses native dimensions rounded to model stride.

The complete accepted configuration is listed in [THRESHOLDS.md](THRESHOLDS.md). Keep these files unchanged during UI-only work. Any behavior change should receive focused tests plus a four-clip regression, with new results saved under a fresh report name.

## Boundaries

Existing background ID fragmentation, small/occluded faces, changing camera geometry and non-neutral enrollment remain limitations. Forward raises are intentionally review candidates. Leaning, paper exchange, hidden notes, eye tracking, person recognition and advanced neighbor/desk validation are not implemented. The four development clips do not establish general event precision, recall or false-alert rates.
