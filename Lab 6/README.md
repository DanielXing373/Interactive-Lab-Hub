# Distributed Interaction

**NAMES OF COLLABORATORS HERE**

For submission, replace this section with your documentation!

---

## Prep

1. Pull the new changes
2. Read: [The Presence Table](https://dl.acm.org/doi/10.1145/1935701.1935800) ([video](https://vimeo.com/15932020))

## Overview

Build interactive systems where **multiple devices communicate over a network** using MQTT messaging. Work in teams of 3+ with Raspberry Pis.

**Parts:**
- A: Learn MQTT messaging
- B: Try collaborative pixel grid demo  
- C: Build your own distributed system

---

## Part A: MQTT Messaging

MQTT = lightweight messaging for IoT. Publish/subscribe model with central broker.

**Concepts:**
- **Broker**: `farlab.infosci.cornell.edu:1883`
- **Topic**: Like `IDD/bedroom/temperature` (use `#` wildcard)
- **Publish/Subscribe**: Send and receive messages

**Install MQTT tools on your Pi:**
```bash
sudo apt-get update
sudo apt-get install -y mosquitto-clients
```

**Test it:**

**Subscribe to messages (listener):**
```bash
mosquitto_sub -h farlab.infosci.cornell.edu -p 1883 -t 'IDD/#' -u idd -P 'device@theFarm'
```

**Publish a message (sender):**
```bash
mosquitto_pub -h farlab.infosci.cornell.edu -p 1883 -t 'IDD/test/yourname' -m 'Hello!' -u idd -P 'device@theFarm'
```

> **💡 Tips:**
> - Replace `yourname` with your actual name in the topic
> - Use single quotes around the password: `'device@theFarm'`
> - For your own projects, publish under your team's topic space: `IDD/<yourteam>/...` (for example `IDD/team3/bedroom/light`). Everyone shares one broker login, so anything you publish can reach everyone's projects.

**🔧 Debug Tool:** View all MQTT messages in real-time at `http://farlab.infosci.cornell.edu:5001`

![MQTT Explorer showing messages](imgs/MQTT-explorer.png)

**💡 Brainstorm 5 ideas for messaging between devices**

- **Three-player mouse game:** Pi 1's joystick moves the crosshair, Pi 2's proximity sensor swings the hammer when a hand comes close, and Pi 3's camera turns the game light on or off with an open palm or a fist. Each Pi publishes its move, and a laptop shows the shared game screen. Topics: `IDD/<team>/mouse-game/aim`, `IDD/<team>/mouse-game/attack`, `IDD/<team>/mouse-game/light`.
- **Roommate court across rooms:** building on our Lab 3 Mini Judge, one roommate files a complaint by voice on their Pi. The other roommate's Pi shows it and lets them answer with yes or no buttons, and the verdict appears on both screens. Topics: `IDD/<team>/court/complaint`, `IDD/<team>/court/reply`, `IDD/<team>/court/verdict`.
- **Friends' sky clock:** building on our Lab 2 sun and moon clock, each Pi publishes its local time of day, and every Pi shows a sun or moon for each friend, so you can see at a glance whether a friend far away is awake. Topic: `IDD/<team>/sky/<name>`, with messages like `day` or `night`.
- **Desk presence board:** inspired by the Presence Table reading, a camera or proximity sensor publishes whether someone is at their desk. The other Pis light up a dot for each friend who is there, a simple cue to say hi or study together. Topic: `IDD/<team>/presence/<name>`, with messages `here` or `away`.
- **Quiet please signal:** tap the capacitive sensor when you start studying, and the other Pis in the apartment show "Quiet please" until you tap it again. Topic: `IDD/<team>/quiet`, with messages `on` or `off`.

MQTT agrees on almost nothing in advance: you invent the topics and what the messages mean. Smart-home standards like Matter fix the vocabulary instead (every "light" behaves the same). Keep this trade-off in mind when you design your topics in Part C.

---

## Part B: Collaborative Pixel Grid

Each Pi = one pixel, controlled by RGB sensor, displayed in real-time grid.

**Architecture:** `Pi (sensor) → MQTT → Server → Web Browser`

**Setup:**

1. **Sensor**

#### Light/Proximity/Gesture sensor (APDS-9960)
We use this sensor [Adafruit APDS-9960](https://www.adafruit.com/product/3595) for this exmaple to detect light (also RGB)
 
<img src="https://cdn-shop.adafruit.com/970x728/3595-06.jpg" width=200>

Connect it to your pi with Qwiic connector


<img src="imgs/IMG_0270.jpg" height="200" />
We need to use the screen to display the color detection, so we need to stop the running piscreen.service to make your screen available again

```bash
# stop the screen service
sudo systemctl stop piscreen.service
```

if you want to restart the screen service
```bash
# start the screen service
sudo systemctl start piscreen.service
```
 
2. **Server** (one person on laptop):
```bash
cd "Lab 6"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-server.txt
python app.py
```

2. **View in browser:**
   - Grid: `http://farlab.infosci.cornell.edu:5000`
   - Controller: `http://farlab.infosci.cornell.edu:5000/controller`

3. **Pi publisher** (everyone on their Pi):
```bash
# First time setup - create virtual environment
cd "Lab 6"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-pi.txt

# Run the publisher
python pixel_grid_publisher.py
```

Hold colored objects near sensor to change your pixel!

![Pixel grid with two devices](imgs/two-devices-grid.png)

**📸 Include: Screenshot of grid + photo of your Pi setup**

<img src="imgs/part-b-grid-pink.jpg" alt="The class pixel grid open in a browser, with the Pi and its color sensor in front of the laptop. The bottom right pixel is pink, matching the Pi's screen." width="640">

Our pixel (bottom right) matches the pink on the Pi's screen.

<img src="imgs/part-b-grid-purple.jpg" alt="The same pixel grid after a different color is held under the sensor. The bottom right pixel and the Pi's screen are now light purple." width="640">

With a different color under the sensor, our pixel and the Pi's screen both turn light purple.

<img src="imgs/part-b-pi-setup.jpg" alt="Close-up of the Raspberry Pi with the Mini PiTFT showing the color data it sends, and a hand holding the APDS-9960 color sensor connected by a cable" width="480">

Our setup: the APDS-9960 color sensor plugs into the STEMMA QT port under the Mini PiTFT, and the screen shows the color data the Pi sends.

---

## Part C: Make Your Own

**Requirements:**
- 3+ people, 3+ Pis
- Each Pi contributes sensor input via MQTT
- Meaningful or fun interaction

**Ideas:**

**Sensor Fortune Teller**
- Each Pi sends 0-255 from different sensor
- Server generates fortunes from combined values

**Frankenstories**
- Sensor events → story elements (not text!)
- Red = danger, gesture up = climbed, distance <10cm = suddenly

**Distributed Instrument**
- Each Pi = one musical parameter
- Only works together

**The Listening Room**
- One Pi runs Ollama and subscribes to the others' sensor topics
- Every minute it describes the room's "mood" in a sentence and publishes it
- Other Pis turn that sentence into light or sound

**Others:** Games, presence display, mood ring

### Deliverables

Replace this README with your documentation:

**1. Project Description**
It is a 3-player game. There will be mice trying to steal cheese, and players are there to protect the chesse.
Players have three roles, and they each take one during the game. 

The first role does the aiming in the game. They use a joystick to move the crosshair up, down, left, and right.

The second role does the attacking. When a mouse is aimed, they can move their palm closer to the distance sensor. That translates into attacking the mouse. A successful attack gives points, and combos give extra points. However, a miss cancels the combo.

The last role controls the light. They don't act proactively control the game. However, their job is crucial for a high score that will be show on the leaderboard after the game. Mice comes out more often when it is dark outside. Therefore, to reach a higher score, players might want to reduce the lighting. On the other hand, darkness makes everything more difficult. So when the team is having a hard time, the player can use the stun by turning the light back on. Mice on the screen will be stunned so that the team doesn't lose cheese or combo. In addition, when a red mouse shows up, the team need three attacks to kill it. This is also a good time to use the stun. 

**2. Architecture Diagram**
- Hardware, connections, data flow
- Label input/computation/output

**3. Build Documentation**
<code>
<pi screens>
<set up>

**4. User Testing**
<video here>

**5. Reflection**
- What worked well?
- The game mechanism is quite intuitive, which worked well. Actions and change in status in the game all have sound effects and visual effects, making the game easy to understand, with new ways of interaction. When the light is off, mice will be somewhat transparent, which also builds to the difficulty of the games. In general, multiple ways of providing feedback to the players worked pretty well. 
- Challenges with distributed interaction?
- The biggest challenge is the collaboration between players. The game runs too fast, and it is quite difficult overall, which makes the collaboration hard and sometimes impossible. Also, the latency is creating problems for precise control of the system. Sometimes one action in the game got delayed, so other actions got queued up which created a mess, like losing a combo. 
- How did sensor events work?
- They worked pretty well after several rounds of calibration, like the orientation of the joystick, the distance threshold of the distance sensor, and the sensitivity of the camera when palm closes and opens up. Admittedly, there are still lots of improvements available, but till this point
- What would you improve?
- The game balance. It is way too hard for three players to collaborate.
- The hit action. It is quite bland to use the distance sensor. By that, I mean the user doesn't get any instant physical feedback like the joystick provides.
- 
- Where did computation happen in your system, and why there? (If you used a language model: did it run on every event, or only at setup?)
- The computation happens at the laptop. For a game like this, it is better to just take inputs from the devices, make the computation, and exhibit the result on the server alone, which here is the laptop screen. If we put it on a Pi for example, the screen would be small, and discrepancies between latencies would create unequal experiences for the players. 

## Submission Checklist

Before submitting:
- [ ] Delete prep/instructions above
- [ ] Add YOUR project documentation
- [ ] Include photos/videos/diagrams  
- [ ] Document user testing with non-team members
- [ ] Add reflection on learnings
- [ ] List team names at top

**Your README = story of what YOU built!**

---

Resources: [MQTT Guide](https://www.hivemq.com/mqtt-essentials/) | [Paho Python](https://www.eclipse.org/paho/index.php?page=clients/python/docs/index.php) | [Flask-SocketIO](https://flask-socketio.readthedocs.io/)
