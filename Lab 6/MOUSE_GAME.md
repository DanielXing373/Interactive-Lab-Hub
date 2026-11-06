# Lab 6 — Mouse Game Implementation Specification

Build a three-player, shared-screen arcade game. One player aims, one swings the hammer, and one controls the light. All three share a score. Each round lasts up to 60 seconds and produces one leaderboard entry. Players decide who uses each controller before starting.

Values in this document are the defaults for the first playable build. Keep the timing and sensor calibration values configurable.

## 1. Hardware and controls

| Input | Reused hardware and repository reference | Interaction |
| --- | --- | --- |
| Aim | Pi 1 and the SparkFun Qwiic Joystick from Lab 4. See [Joystick](../Lab%204/README.md#joystick) and [joystick_test.py](../Lab%204/joystick_test.py). | Push up, down, left, or right to move the crosshair one hole. Return to center before the next move. The joystick button has no game action. |
| Attack | Pi 2 and the Qwiic/I²C proximity sensor reused from Lab 4's Patroller. See the [Patroller project record](../Lab%204/README.md#lab-overview), [Distance Sensor](../Lab%204/README.md#distance-sensor), and [distance_sensor_test.py](../Lab%204/distance_sensor_test.py). | Move a hand toward the sensor to swing once. Withdraw it before swinging again. Use the VCNL4040 reader after confirming the board model. It reads proximity counts, with higher readings indicating a closer object. |
| Light | Pi 3 and the reused USB webcam. See [Lab 4 camera_test.py](../Lab%204/camera_test.py) for OpenCV capture and the [MediaPipe Raspberry Pi example](https://github.com/google-ai-edge/mediapipe-samples/blob/main/examples/gesture_recognizer/raspberry_pi/recognize.py) for gesture recognition. | Hold an open palm to turn the game light on. Hold a closed fist to turn it off. The current light stays in place when the hand leaves the frame. Keep the physical area around the camera lit throughout play. |

### Input processing on each Pi

- **Aim.** Sample at approximately 30 Hz. Calibrate each axis's center, range, and polarity. Use a 30% normalized deflection to trigger a step and a 15% dead zone on both axes to rearm. If both axes cross the trigger threshold, use the axis with the larger absolute deflection and prefer horizontal on an exact tie. The board clamps movement at its edges. Pushing into an edge still consumes the step.
- **Attack.** Sample at approximately 30 Hz. Measure clear and near-hand readings on the actual setup and choose a near trigger threshold and a lower release threshold between those ranges. Require two consecutive samples at or above the trigger threshold to swing and two at or below the release threshold to rearm. Start disarmed until the sensor first sees a clear hand position.
- **Light.** Detect one hand using MediaPipe's `Open_Palm` and `Closed_Fist` categories. Start with a confidence threshold of 0.70 and require 200 ms of continuous recognition of the same category before publishing. An unrecognized frame resets the dwell timer. Publish once per newly confirmed pose. Removing the hand rearms pose recognition without sending a light change. A confirmed pose may be sent again after hand removal so it can set the light in a fresh round. The host treats repeated requests for the current light state as a no-op.

## 2. Round flow and scoring

| Setting | Default |
| --- | --- |
| Board | 3 rows × 3 columns |
| Round duration | 60 seconds |
| Starting cheese / score | 5 / 0 |
| Starting crosshair / light | Center hole / on |
| Spawn interval with light on / off | 2.8 s / 1.0 s |
| Long cheese-craving bar / short retreat bar | 1.6 s / 0.6 s |
| Global stun duration / cooldown | 1.2 s / 6.0 s |

1. **Ready screen.** Show the three controls, the leaderboard, and a Start button. Start opens a new round, resets the values above, clears the board and pending actions, and makes the stun available. Start the countdown immediately. The first mouse can appear after one lit spawn interval.
2. **Play.** A single mouse spawns at a time, in a uniformly random empty hole. Each hole holds at most one mouse. Reset the spawn timer to a full interval on a light change. When a spawn is due and the board is full, skip that spawn and schedule the next interval. The light controls spawn frequency, while a mouse's regular stage durations are the same in both light states.
3. **Finish.** End immediately when the countdown reaches zero or the cheese count reaches zero. Freeze gameplay and record one result. The result screen shows the round score, remaining cheese, elapsed time, and the leaderboard. A manual Play Again button starts a fresh round.

### Mouse lifecycle

| Stage | Behavior and feedback |
| --- | --- |
| Spawn | The mouse pops into an empty hole and becomes hittable immediately. The pop-in animation runs alongside the first timer. |
| Crave cheese | The mouse stays at its hole while a long progress bar fills. It is empty-handed throughout this stage. |
| Grab cheese | When the long bar fills, the mouse instantly changes to a pose holding one piece of cheese and begins retreating. The shared cheese total stays the same until it escapes. |
| Retreat | The mouse runs in place at its original hole while a visually distinct short progress bar fills. It is still hittable at that hole. |
| Leave | When the retreat bar fills, remove the mouse and deduct one cheese. Clamp the shared total at zero. |

A swing targets the hole under the crosshair at the time the host processes the action. A hit removes the mouse immediately and awards one point in any hittable stage, including retreat and stun. A mouse hit while holding cheese costs the team zero cheese. A miss produces swing feedback and changes neither score nor cheese. There is no combo multiplier.

### Light and global stun

- **Darkness is the scoring opportunity.** More mice appear, so the team can score faster if it can keep up.
- **Turning on the light can clear the board.** On an off-to-on transition with the skill ready, show one brief full-screen brightness pulse and an exclamation mark over each mouse. Freeze all mice in their current stages for 1.2 seconds, including their cheese possession and progress bars. Suspend spawning during that window. The crosshair, hammer, and 60-second round countdown remain active.
- **Resolve the stunned mice together.** When the stun ends, remove every stunned mouse still on the board. Each cheese-carrying mouse takes one cheese with it. Each empty-handed mouse disappears without taking cheese. Award zero points for disappearances. Resume spawning one full interval later at the rate for the current light state.
- **Cooldown starts when the stun begins.** The next stun becomes available 6 seconds after activation. Turning on the light during cooldown still changes the spawn rate. Keeping the light on when cooldown expires has no effect until the next off-to-on transition. Turning the light off during a stun changes the light immediately and leaves the active stun running through its original deadline.
- **Timing tradeoff.** An early stun saves cheese but can clear mice the team could have hit for points. A later stun can leave the team a short window to rescue cheese by hitting the carriers before they disappear.

## 3. Display and interaction feedback

- Show the countdown, current score, and cheese count above the 3×3 board. Keep the crosshair visible on empty and occupied holes and readable in both light states.
- Give mice distinct empty-handed, carrying, and stunned visuals. Use a cheese icon or sprite in addition to the retreat bar so possession is recognizable at a glance. Freeze the existing progress bar during a stun.
- Show a hammer strike at the targeted hole on every swing and distinguish hit from miss. Show a point increment on hit and a cheese decrement on escape. Stunned mice disappear in place when the effect ends.
- Show both the current light state and stun readiness. During cooldown, show seconds remaining. Use a steady brightness difference between light states and a single pulse on stun activation.
- Show results and leaderboard on the same shared screen. Use a keyboard-only development mode with arrow keys to aim, Space to attack, and O/P for light on/off. Ignore keyboard auto-repeat for these actions. Route simulated actions through the same game handlers as sensor actions.

## 4. Runtime and MQTT contract

Each Pi reads and interprets its own sensor and publishes to the course MQTT broker. A laptop runs the game host, subscribes to the three topics, and updates the shared browser through Flask and Socket.IO. The host owns all timers, scoring, and persistence. Only light state leaves the camera Pi. Use the broker and team namespace in the [Lab 6 assignment](README.md). Reference [app.py](app.py), [mqtt_bridge.py](mqtt_bridge.py), and [pixel_grid_publisher.py](pixel_grid_publisher.py) for the example server, MQTT bridge, and publisher.

| Topic | JSON payload |
| --- | --- |
| `IDD/<team>/mouse-game/aim` | `{"direction":"up"}` with one of `up`, `down`, `left`, or `right` |
| `IDD/<team>/mouse-game/attack` | `{"action":"swing"}` |
| `IDD/<team>/mouse-game/light` | `{"on":true}` for open palm or `{"on":false}` for closed fist |

Use non-retained messages with QoS 0 for these live inputs. Each Pi publishes only discrete actions and discards offline actions. The host ignores retained or malformed messages and inputs received outside an active round. MQTT and keyboard handlers enqueue input for the same host game loop.

Use a monotonic host clock and a single game loop. Process inputs in host receipt order. Advance due game timers to an input's receipt time before applying it. If a deadline and an input share the same timestamp, resolve the deadline first. When deadlines tie, use round expiry first, then stun completion, then mouse stage changes, then spawning. Resolve same-time mouse departures as a batch and end the round before any further spawn or input if cheese reaches zero. Never apply an action to a completed round.

Send complete state snapshots to the browser on connection and during play. Include round phase, time remaining, score, cheese count, crosshair coordinates, light state, cooldown, and each occupied hole's mouse phase, cheese possession, progress, and stun status. The browser renders the state and transient effects. Reconnecting to the browser should show the current round without restarting it.

Store one durable leaderboard entry per round on the host, with round ID, score, remaining cheese, elapsed time, and completion time. Use the round ID to prevent duplicate entries. Sort by score descending, then remaining cheese descending, then elapsed time descending. Break an exact tie by earliest completion. Keep the leaderboard across game-host restarts.

## 5. Single-developer workflow

1. **Verify inputs and MQTT.** Run each Lab 4 sensor smoke test, confirm the actual camera and proximity board, and calibrate the controllers. Publish one test action from each Pi and verify that the host receives it on the expected topic.
2. **Build one complete keyboard-controlled round.** Implement the game state and timers, shared display, light effect, end conditions, replay, and persistent leaderboard. Check the cases below before connecting hardware.
3. **Connect one device at a time.** Add the joystick, then proximity sensor, then USB gesture control. Confirm that all three can act together and that the display reflects their actions consistently.
4. **Playtest and document.** Compare all-light, all-dark, and active-switching rounds with the same players. Tune spawn and stage timings so active light use can compete with all-dark play. Test with at least two non-team participants and record their expectations, surprises, and suggested changes. Capture photos of the three Pi setups and photos or video of play. Complete the final Lab 6 README with the architecture diagram, MQTT topics, code explanations, and reflection. Save the Part B pixel grid screenshot and Pi setup photo separately.

### Acceptance cases

| Case | Expected result |
| --- | --- |
| Hold the joystick or hold a hand in proximity range | One move or one swing per activation. Returning to neutral or withdrawing the hand rearms the controller. |
| Hit a mouse during the short retreat bar | Score increases by one. Cheese remains unchanged. |
| Stun one empty-handed mouse and one cheese carrier, then leave both alone | Both disappear at stun end. The team loses one cheese and gains zero points. |
| Hit the carrier during that same stun | The hit earns one point. The remaining empty-handed mouse disappears without costing cheese. |
| Turn the light off during a stun, then turn it back on before cooldown expires | The current stun finishes on schedule. No second stun begins. |
| Leave the light on past the cooldown | The stun becomes ready. It fires only after the next off-to-on transition. |
| Time runs out during a stun | The round ends immediately. A later stun resolution does not change the result. |
| A carrier escapes with the last cheese | The round ends immediately and produces exactly one leaderboard entry. |
| Start another round or restart the host | A new round resets the board and all round counters. Existing leaderboard entries remain available. |
