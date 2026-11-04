# Observant Systems: Overnight Sensation

**Members:** Hong Yuan Cao (hc2343), Yun-Chung Liu (yl4445)

# Part 1

The Part 1 tests ran on a Raspberry Pi 5 with a USB webcam, using the lab's provided scripts.

## Part A.
### Set up your Pi for on-device AI

The Python dependencies are installed in `.venv`, and the YOLO26 nano model was exported to NCNN and tested. The webcam photo from this part is also used in Part D.

The `ollama list` output on the Pi confirms that both models are installed: `qwen3:0.6b` (522 MB) and `qwen3.5:0.8b` (1.3 GB).

[![Pi terminal showing ollama list](evidence/part-a-ollama-list.jpg)](evidence/part-a-ollama-list.jpg)

## Part B.
### See: recognize people in real time with YOLO

The USB webcam and `yolo_person.py` ran on the Raspberry Pi, with the live window viewed through VNC. The script uses the NCNN export of YOLO26 nano and a default confidence threshold of 0.4. The screenshot below shows one person detected with confidence 0.90.

![Live YOLO person detection on the Raspberry Pi, with confidence 0.90](evidence/part-b-person-default.png)

## Part C.
### See more: hands and pose with MediaPipe

I ran `hand_pose.py` on the Pi and tested the gestures through VNC. Changing the distance between my thumb and index finger changed the displayed percentage, and Quiet Coyote displayed the gesture label and set the percentage to 0%. The screenshot shows the tracked hand landmarks during a pinch at 0%.

![MediaPipe hand landmarks during a pinch, with the percentage at 0%](evidence/part-c-hand-pinch.png)

For my nighttime system, I could use body pose tracking to estimate how often I turn over or change position while sleeping. The Pi could log major position changes with timestamps and show a count and timeline in the morning. I would need to test how reliably it tracks movement in low light and when blankets cover the body.

## Part D.
### Reason: run Qwen on the Pi with Ollama

<details open>
<summary>Questions, recorded answers, timings, and comparison — October 25, 2026</summary>

These tests ran on the Raspberry Pi using the provided `ask_qwen.py`, with thinking off, temperature 0.3, and the default 120-token limit. The answers below are copied exactly from the output, including mistakes. Times are the script's elapsed request times, including any model loading and image processing; each is one observation, not an average. None of these answers hit the token limit. [Raw results and run metadata](evidence/part-d-20261025/results.json) are saved with the individual terminal outputs.

**Question 1 — history**

Prompt: `Tell me a bit about the history of Roosevelt Island.`

Model: `qwen3.5:0.8b`. Time: **30.4 seconds**.

> Roosevelt Island was originally built as a private residence for President William McKinley, who named it after himself. The island's history is largely tied to the 1920s and 30s when it became a popular summer resort for wealthy New Yorkers seeking escape from the city's heat.

This answer invents a history and includes none of the lab's four reference facts: Blackwell's Island, then Welfare Island, the Roosevelt Island name in 1973, and Cornell Tech's campus opening in 2017. The [National Park Service's history](https://www.nps.gov/places/blackwell-s-island-new-york-city.htm) documents the earlier names, the city's purchase in 1828, its prison and hospital uses, and the 1973 naming for Franklin D. Roosevelt. [Cornell Tech dates its campus opening to 2017](https://tech.cornell.edu/news/et-custom-timeline/cornell-tech-campus-opens-on-roosevelt-island/).

**Question 2 — reasoning from a supplied log**

Prompt: `A sample movement log contains events at 01:00, 01:15, and 03:00 on the same night. How many events are listed, and what is the longest gap between consecutive events? Use only this log.`

This is hypothetical test data, not a recorded night of sleep.

Model: `qwen3.5:0.8b`. Time: **7.7 seconds**.

> The log lists three distinct events occurring at 01:00, 01:15, and 03:00. The longest gap between these events is 2 hours (from 01:15 to 03:00).

The event count is correct, and it selects the correct pair of times, but the interval is wrong: 01:15 to 03:00 is **1 hour 45 minutes**. For the nighttime system, counts and durations should be calculated in code before the language model summarizes them.

**Question 3 — describing the Part A photo**

Prompt: `What is in this photo?`, using `--image snap.jpg`.

Model: `qwen3.5:0.8b`. Time: **30.5 seconds**.

> A black gaming controller with yellow cables and a USB hub plugged into it.

![The Part A photo sent to Qwen: a black game controller and yellow cables on a desk](evidence/part-d-20261025/snap.jpg)

The black controller and yellow cables are visible. The claim about a USB hub being plugged into the controller is not clearly supported by the photo. This is a useful rough description, but its claimed connections should not be treated as established facts.

**Repeat of Question 1 — smaller model**

Prompt: `Tell me a bit about the history of Roosevelt Island.`

Model: `qwen3:0.6b`. Time: **12.3 seconds**.

> Roosevelt Island was established in 1910 as a temporary refuge for the U.S. Navy during World War I. It became a significant location for military and civilian use, with the island serving as a base for the U.S. Army and Navy. After the war, it became a peaceful community, attracting people from all over the world. Today, it remains a popular destination for visitors and a symbol of peace and freedom.

The smaller model also includes none of the four reference facts, and its Navy-refuge story does not match the documented history linked above. It also gives four sentences despite the script asking for at most three. It was about **2.5 times faster** on this repeated prompt (12.3 versus 30.4 seconds), but neither history answer was reliable. These single end-to-end timings include loading effects, so they do not establish a general speed ratio. The supplied-log test was more constrained, yet still contained an arithmetic mistake; a confident answer is not enough to trust the device's conclusions.

</details>

## Part E.
### Connect: from YOLO readings to Qwen reasoning

### Recorded rerun — October 25, 2026

The pipeline ran on the Pi over SSH with `python yolo_to_qwen.py --headless --seconds 60`. This second run completed successfully, saved **14 changed readings**, and sent the log to `qwen3.5:0.8b` with thinking off. Qwen's response took **16.2 seconds**.

I was the only person in view. I entered, waved at the camera, moved closer and farther away, left the frame, and came back. These are my observations, rather than actions inferred from the detector log.

Evidence: [complete detector log](evidence/part-e-20261025-run2/watch_log.txt), [terminal output and Qwen's answer](evidence/part-e-20261025-run2/terminal-output.txt), [run metadata](evidence/part-e-20261025-run2/run.json), and [reported observations](evidence/part-e-20261025-run2/user-observations.json). The [first run's log](evidence/part-e-20261025-run1/watch_log.txt) and [output](evidence/part-e-20261025-run1/terminal-output.txt) are also preserved; the analysis below uses the rerun.

| Reading | Entries in the change log |
|---|---:|
| `nobody` | 5 |
| `1 person(s) at right/far` | 1 |
| `1 person(s) at center/close` | 5 |
| `1 person(s) at left/close` | 3 |

These are counts of logged changes, not counts of frames, visits, or seconds. At most one person was detected at a time. In this script, `close` means the person's bounding box is taller than 60% of the frame; it is not a measured physical distance.

The default question was: **How many people were there, what were they doing, and did anything change?**

Qwen's exact answer:

> There were 3 distinct individuals identified throughout the 60-second observation: one person was located at right/far, another at center/close, and a third at left/close. No significant changes occurred to their location or activity during this period.

The summary is wrong about both identity and change. I was one person moving through different positions, but Qwen treated the three position labels as three distinct individuals. The detector does not track identity, so the log alone cannot establish a count of unique visitors. Its "No significant changes" claim also contradicts the sequence from `nobody` to `right/far`, then `center/close` and `left/close`, with further presence changes.

My reported entry, exit, return, and distance changes broadly agree with the kinds of changes in the log, but I did not record timestamps for each action, so individual `nobody` entries cannot be assigned confidently to actual exits versus missed detections. A `nobody` reading only means the detector did not find a person in that sample. Waving is not encoded by this interpreter at all: Qwen receives only coarse position and presence labels, so it cannot identify that gesture from this log.

This run shows that getting the whole pipeline to execute does not guarantee an accurate summary. The interpreter limits what the model can know, and the model can still ignore changes that are explicitly present in its input. For an overnight system, counts and durations should be calculated directly from the log, and uncertain detections should remain uncertain in the report.

---

# Part 2: Desk Curfew

Desk Curfew holds you to a bedtime promise. Before bed, you set a curfew with the Mini PiTFT's buttons. Overnight, the webcam watches the empty desk chair (never the bed). In the morning, the screen lights up green if the chair stayed empty after curfew and red if not, and the top button shows a short message from Qwen. The device is just the Pi, the webcam and the PiTFT.

## Part F.
### Storyboard and ideas

The problem: saying "I'll be in bed by 12:30", then staying at the desk until 2 and never knowing how late it got. Desk Curfew turns the promise into one question the camera can answer: was anyone in the chair after the promised time?

We also considered a sleep-turn counter (from our Part C note), a fridge-raid log and a doorway counter. The first points a camera at a bed, the second watches roommates who never agreed and needs to tell people apart, which Part E showed the detector cannot do, and the third answers a question nobody asks in the morning. Desk Curfew builds on the one-person detection that worked in Part E.

![Hand-drawn Desk Curfew storyboard in three panels: before bed, the bottom button sets the curfew and the top button hands it over; while asleep, the camera looks at the chair every 10 seconds and logs changes, with the bed out of frame; when awake, the red screen shows the curfew was missed and the top button explains](assets/storyboard.jpg)

![Desk Curfew Verplank diagram](assets/verplank.svg)

## Prep for Part 2

Jovian said the storyboard was good overall but that the device's response could be improved. We put most of our later changes into the morning response: the whole screen now turns green or red so the answer can be read from bed, the details and Qwen's message appear only when you ask with the top button, and Qwen's wording is checked so it cannot drop the verdict or change a time.

The device sits on the small round table next to my desk, with the webcam facing my desk and chair; the bed is behind it and out of view. I am the person being observed and agreed to it. The overnight logger processes webcam frames in memory and saves only timestamped text readings and status entries, with no photos or videos saved.

<img src="assets/photos/0-placement.jpg" width="360" alt="The webcam on a round orange table, facing a desk and office chair">

*Where the device spends the night: the webcam faces the desk chair.*

Part E showed where the pipeline breaks, so we never ask Qwen to count. [`night_report.py`](night_report.py) calculates every time and duration in code, and Qwen only rewords the result. [`curfew.py`](curfew.py) discards Qwen's version if it changes a time, drops the verdict, or speaks as the person. The report says "someone", not who, since the detector cannot tell people apart. Short gaps in detection are merged, glimpses under 30 seconds are ignored but mentioned, and a heartbeat every ten minutes lets the report say when the camera was not watching.

The hand-off control went through three versions: the Qwiic joystick from Lab 4 (one more part to wire), then a wave at the camera using YOLO's pose model ([`wave_detect.py`](wave_detect.py)), which missed too many real waves and could not set a time, and finally the PiTFT's two buttons, as in our Lab 2 clock. Buttons are reliable, and the screen's backlight can turn fully off at night.

## Part G.
### The interaction before

The bottom button moves the curfew 15 minutes later, and the top button hands the night over. The device saves the promise, shows `GOODNIGHT` for three seconds, then turns the screen off so it stays dark all night. A press of the top button at night shows the curfew; holding the bottom button ends the night early.

<img src="assets/photos/1-bedtime-curfew.jpg" width="420" alt="The Mini PiTFT on the Raspberry Pi showing CURFEW 17:38, bottom: +15 min, top: goodnight, next to the webcam">

*The bedtime screen during a test night.*

Against Bellotti's five questions: you address the device only with a button (the camera never takes commands), the lit screen and the night-time `WATCHING` peek show it is paying attention, the actions are few, the curfew is repeated on screen before it goes dark and again in the morning, and a mistaken night can be ended with a long press. Missed detections and camera gaps are reported, not hidden.

## Part H.
### The observant system at night

![Desk Curfew pipeline from webcam to morning report](assets/pipeline.svg)

After the hand-off, [`curfew.py`](curfew.py) runs the lab's [`overnight.py`](overnight.py): one look every 10 seconds, people only, using the Part E `interpret()`. With the camera on the chair, any person in view means someone is at the desk. The log records changes plus a heartbeat, and is saved in `nights/` with the promise. [`test_night_report.py`](test_night_report.py) checks the morning calculations on made-up nights.

It needs the Lab 2 PiTFT library and `gpiod`, and the Lab 2 boot script must be stopped first because it holds the screen:

```
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ pip install adafruit-circuitpython-rgb-display 'gpiod>=2.2.2,<3'
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ pkill -f screen_boot_script.py
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ tmux new -s night
(.venv) pi@raspberrypi:~/Interactive-Lab-Hub/Lab 5 $ python curfew.py --curfew 00:30 --morning 08:00
```

<img src="assets/photos/2-night-peek.jpg" width="320" alt="A finger pressing the top PiTFT button; the screen shows WATCHING, curfew 17:38, until 17:40">

*Peeking at night; otherwise the screen stays dark.*

## Part I.
### The interaction after

When the night ends, the whole screen turns green (kept), red (missed) or amber (no data), with a short summary such as `MISSED +26 min / left 00:51 / back 1x`. It stays lit so it can be read from bed. The top button pages through Qwen's message, and a long press on the bottom button turns the screen off. The device never makes a sound, and a quiet night is reported plainly as a quiet night. We dropped the servo flag and spoken report from earlier drafts: the color does the flag's job, and our Pi had no speaker.

We ran two fake nights on October 29. In the first, Qwen wrote *"I was at the desk at 16:52, but it was already late by 16:53 when I stopped."* It kept the times, so it passed our times-only check, but it speaks as the device and never says the curfew was missed. The check now also requires the verdict and rejects first-person answers: the same lesson as Parts D and E. The second night was the first with the PiTFT working, and it revealed one more fix: the end time was a minute early because the log only records changes, so `curfew.py` now logs when it stops.

<img src="assets/photos/3-morning-writing-report.jpg" width="260" alt="PiTFT showing MISSED +1 min, writing report...">

*Qwen writing the message (16.9 s).*

<img src="assets/photos/4-morning-missed.jpg" width="260" alt="PiTFT filled red: MISSED +1 min, left 17:39, no returns">

*The red summary.*

<img src="assets/photos/5-message-page-1.jpg" width="260" alt="PiTFT showing page 1 of 2 of the morning message">

*Qwen's message, page 1.*

<img src="assets/photos/6-message-page-2.jpg" width="260" alt="PiTFT showing page 2 of 2: Nobody came back before I stopped at 17:39">

*Page 2, with the end-time error we then fixed.*

The video in the final documentation shows a full hand-off and morning from a third test night, this time with a green result.

### Real overnight run — October 31–November 1, 2026

We ran the system overnight on Hong's Pi using the terminal fallback and a background service, so recording continued independently of SSH. The earlier photos and videos show the PiTFT interaction on our teammate's setup. This run sampled the webcam approximately every 10 seconds and saved only text; no overnight photos or videos were saved.

| Item | Recorded result |
|---|---|
| Start | October 31, 11:56:30 PM EDT |
| Automatic stop | November 1, 8:00:00 AM EST |
| Elapsed recording time | 9 hours, 3 minutes, 30 seconds |
| Chosen curfew | November 1, 12:30 AM EDT |
| Log entries | 204 detection changes, 55 heartbeats, and 1 stop marker |
| Longest gap between entries | 10 minutes, 9 seconds; none exceeded the 15-minute logging-gap threshold |
| Calculated result | `MISSED +1 h 55 min`, with 3 return groups |

The clocks went back during this night, so the raw log, settings, and generated report use **UTC**. For example, the stored curfew `04:30` means 12:30 AM EDT, and the stop at `13:00` means 8:00 AM EST. The table above uses New York time. The process exited successfully after generating the morning report at about 8:00:31 AM EST.

Evidence: [complete night log](nights/2026-11-01-0356/night_log.jsonl), [curfew settings](nights/2026-11-01-0356/tonight.json), [generated report and original Qwen response](nights/2026-11-01-0356/report.json), [run metadata and timezone mapping](nights/2026-11-01-0356/recording-info.json), [terminal output](nights/2026-11-01-0356/terminal.log), and [reported lighting observation](nights/2026-11-01-0356/user-observations.jsonl).

The camera had a restricted side view, mainly of hands at the desk, with the bed out of the checked frame. Hong reported that the room lights were off at 1:32 AM EST; the exact switch-off time was not recorded. The Mac was configured to keep its screen on as a light source, but detection under that lighting was not independently validated. The final detection change was `nobody` at 1:29:27 AM EST, followed by heartbeats through 7:59:27 AM and the stop marker at 8:00 AM. Here, **`nobody` means no person was detected**, not proof that the chair was empty or that someone was asleep.

The reported 1 hour 55 minutes is an estimate from detection intervals after curfew. The code merges gaps shorter than two minutes, so the three return groups are not three independently verified physical visits. Qwen took 30.4 seconds and incorrectly changed the verdict to "Curfew kept" and the longest stay to "just under an hour and a half." The validation rejected that response and used the calculated template instead; both versions are preserved in the report. The run demonstrates that sensing, logging, stopping, and reporting worked overnight, while the limited view and lighting constrain what the detections can establish.

## Final documentation

It looks like a Pi with the PiTFT on top and a webcam facing the desk chair, dark all night and green or red in the morning. It works like the pipeline in Part H, and acts like the hand-off in Part G and the reveal in Part I.

The video shows the whole system in two clips, filmed on a shortened test night so that bedtime and morning are a few minutes apart. In the first clip, the screen shows a curfew of 18:30. Pressing the top button brings up `GOODNIGHT` with the curfew and the time it will stop watching (18:32), and then the screen goes dark; the clip ends on the webcam facing the empty desk chair. In the second clip, the night is over and the screen is green: `CURFEW KEPT`, `empty from 18:29`, `no returns`, because nobody sat in the chair during the test night.

<video src="assets/video/1-bedtime.mp4" controls width="320"></video>

[Clip 1: bedtime, setting the curfew and saying goodnight](assets/video/1-bedtime.mp4)

<video src="assets/video/2-morning.mp4" controls width="320"></video>

[Clip 2: morning, the green screen and Qwen's message](assets/video/2-morning.mp4)
