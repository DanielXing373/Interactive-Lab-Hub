# Final Project: B'Wave Mechanical Magic — Build Notes

> Status: v3 (2026-11-24). Arms printed and glued to the swing-servo horns. Bracket v3 raises each servo per layer so the arms no longer touch at the far end.
>
> Simulator (measured dimensions, 15 mm layer pitch, before bracket v3): https://claude.ai/artifact/RSUVDBuvrbHuEkYq2YyT6w

## 1. Design decisions

| Item | Decision |
|---|---|
| Mounting | Tilted stand, reusing a laptop stand as the drawing board; mechanism on the front, Pi and power on the back |
| Layering | Columns on the arms (15 mm steps) plus bracket v3 raising the swing servos per layer (S0 +9 / S1 +6 / S2 +3 / S3 0 mm) |
| Swing-axis spacing | 34 mm |
| Layer pitch | **18 mm** = 15 (columns) + 3 (bracket lift). At 15 mm the flip-servo back (sticks out 1.1 mm behind its arm) was only 1.2 mm from the next arm's plate and the arms touched at the far end. Now 4.2 mm, beam to beam 5.3 mm |
| Flip-servo seat | 3-face locating: body bottom on the bar, far end against the end wall, front face on the 1.6 mm plate. Wire end and board side open, ears untouched. Push into the corner, then glue |
| Arm length | Swing axis to card bottom edge: 150 mm |
| Column heights | Front card 45 / 2nd 30 / 3rd 15 / back 0 mm |
| Gimmick card | 3rd from the front (`GIMMICK = 2`) |
| Reveal-2 direction | Opposite in the two branches (hearts left, diamonds right) |
| Driver board | SparkFun Servo pHAT from Lab 4 (16 channels, 8 used) |
| Swing-servo mounting | Body bottom sits flat on the pocket floor (no glue underneath). Push all four into the same corner, hold, and put superglue along the top of the side-wall gap. Wall tops are 1 mm below the ears, no screw holes |
| Card clips | Not printed. Off-the-shelf clips glued onto the flip-servo horns |
| Swing servo | Miuzei MS24-F (20 kg, **270°**, 25T spline d5.9) |

Collision checks (all four states, both branches): adjacent layers never overlap; closest arm to a neighboring column is about 8 mm.

Renders:

- Far-end gap, before vs. now: [cad/renders/bracket_v3_side_gap.png](cad/renders/bracket_v3_side_gap.png)
- Assembly, stacked: [cad/renders/overview_v3_stacked.png](cad/renders/overview_v3_stacked.png)
- Assembly, blanks spread: [cad/renders/overview_v3_fanned.png](cad/renders/overview_v3_fanned.png)
- Bracket v3: [cad/renders/part_bracket_v3.png](cad/renders/part_bracket_v3.png)

## 2. Print list

STLs are in [cad/stl/](cad/stl/); the source is [cad/bwave_parts.scad](cad/bwave_parts.scad) (OpenSCAD, set `PART` and export).

| # | Part | File | Qty | Orientation / notes |
|---|---|---|---|---|
| 1 | Swing-servo bracket | `bracket.stl` | 1 | Floor on the bed, pockets up, no supports. About 148 × 67 × 38 mm, 15–20% infill. v3: floor with per-layer lift, walls 1 mm below the ears, no screw holes |
| 2 | Arm, front card | `arm0.stl` | 1 | Already in print orientation: front plate on the bed, column up, no supports. v2: no wire groove; beam end no longer sticks into the flip-servo space |
| 3 | Arm, 2nd card | `arm1.stl` | 1 | Same |
| 4 | Arm, 3rd card (gimmick) | `arm2.stl` | 1 | Same |
| 5 | Arm, back card | `arm3.stl` | 1 | Same |

Print settings: PLA, 0.2 mm layers, 3 walls, 20–30% infill (30% for the arms).

## 3. Dimensions

Measured values are at the top of `bwave_parts.scad` ("measured" = from the 11/18 sketches, "est." = not measured yet). Sketches and photos are in [measurements/](measurements/).

**Swing servo MS24-F**: body 40.4 × 20.2, body top 39.3, spline top 46.5, ear underside 28, length with ears 54.6, shaft ≈9 from the near end, wire block 4 high sticking out 3.2. Horn `HORN_TOP` / `HORN_D` are estimates (preview only).

**Flip servo MG90S**: body length 22.7, length with ears 32.3, thickness ≈12; boss 7 + spline 5 above the body top.

The seat locates by contact on three faces, not by a press fit. All four seats are identical, so any dimension error shifts all four cards the same way and the stack stays aligned.

Not measured yet; these only move the cards as a group (alignment is unaffected):
- Body height `FL_H`: card height.
- Shaft to wire end `FL_SHAFT`: card left/right position.
- Horn top above body top `FL_ABOVE`: card height.

**Clips** (measure after gluing to the horns): horn top to card bottom edge `CLIP_OFF`, clip thickness `CLIP_T` (must stay below the 18 mm pitch).

## 4. Shopping list

| # | Use | Item | Qty | Notes |
|---|---|---|---|---|
| 1 | Swing servos | Bought: Miuzei MS24-F 20 kg digital servo (270°) | — | 500–2500 µs = 270°, center 1500 µs |
| 2 | Flip servos | [Beffkkip MG90S metal gear, 8-pack](https://www.amazon.com/MG90S-Servo-Motor-Helicopter-Arduino/dp/B01JY3H4MA) | 1 box | 4 used + 4 spares. Check each turns a full 180° before gluing |
| 3 | Extension leads | [Yiqigou 30 cm servo extensions, 10-pack](https://www.amazon.com/10pcs-Female-Servo-Extension-Futaba/dp/B07NJB58XC) | 1 pack | Flip-servo leads run along the arms to the driver board |
| 4 | Servo power | Power bank (USB-C 5 V ≥ 3 A) | 1 | Servos only, into the Servo pHAT USB-C. Ideally with a low-current mode, or it may shut off while servos idle |
| 5 | Pi power | Power bank or official Pi 5 supply | 1 | Separate from servo power |
| 6 | Measuring | Digital calipers | 1 | Not needed if the school has one |

**Not needed**: Adafruit driver board, 10 A supply (using the Lab 4 Servo pHAT + power bank); screws (glue instead).

## 5. To do / notes

- [ ] Power the Servo pHAT separately from the Pi: cut the isolation jumper; check the SparkFun hookup guide first.
- [ ] Power bank test: run for 30 minutes and see whether it shuts off.
- [ ] Before gluing the swing servos, power them and confirm each one sweeps its full range. Superglue is permanent.
- [ ] Glue S3 (lowest pocket) first, fit its arm and run it slowly through its range to check the far end, then glue the others.
- [ ] Re-tune the blank-spread angles: they are old simulator defaults (set when the gimmick card was last); in stage 4 a blank hides the gimmick card.
- [ ] Tune the gimmick-card exit angle (currently 40°).
- [ ] Glue: keep it away from output shafts, horns and spline holes; do not let thin superglue wick into servo case seams.
- [ ] Interaction method still open.
- [ ] Swing servos are 270°: one PCA9685 step at 50 Hz is about 4.9 µs ≈ 0.66°, about 2.7 mm at the card corner. Reveal 1 at 3.5° is only ~5 steps; check the reveal width is stable.
- [ ] Clip on horn: take the horn off and glue the clip flat, centered on the horn; keep glue out of the spline hole.
