# SmartAlarm — Project Roadmap & Review

> Auto-generated project review — March 2026
> Repository: `Group Project/`

---

## Table of Contents

1. [Current Project Status](#current-project-status)
2. [Existing Bugs & Issues](#existing-bugs--issues)
3. [Stage 1 — Fix All Existing Bugs](#stage-1--fix-all-existing-bugs)
4. [Stage 2 — Connect the Pi to the Flask Server](#stage-2--connect-the-pi-to-the-flask-server)
5. [Stage 3 — Complete the LCD Output (OutputHandler)](#stage-3--complete-the-lcd-output-outputhandler)
6. [Stage 4 — Complete All Hardware Inputs (InputHandler)](#stage-4--complete-all-hardware-inputs-inputhandler)
7. [Stage 5 — Build Wake-Up Games (Core Feature)](#stage-5--build-wake-up-games-core-feature)
8. [Stage 6 — Buzzer / Audio Feedback](#stage-6--buzzer--audio-feedback)
9. [Stage 7 — Web Dashboard — Alarm Management UI](#stage-7--web-dashboard--alarm-management-ui)
10. [Stage 8 — Testing](#stage-8--testing)
11. [Stage 9 — Deployment to Raspberry Pi](#stage-9--deployment-to-raspberry-pi)
12. [Stage 10 — Polish & Final Deployment](#stage-10--polish--final-deployment)
13. [Summary Timeline](#summary-timeline)

---

## Current Project Status

| Layer                        | File(s)                                 | Status                                                                 |
|------------------------------|-----------------------------------------|------------------------------------------------------------------------|
| **Flask Web Server**         | `app/__init__.py`, `app/routes.py`      | Login, registration, account management, device pairing API — mostly functional |
| **Database Models**          | `app/models.py`                         | User, Device, Alarm models — working                                   |
| **Forms**                    | `app/forms.py`                          | Login, Register, Pair, Reset, Delete forms — working                   |
| **Docker / Deployment**      | `Dockerfile`, `docker-compose.yml`      | Docker + MySQL production, SQLite dev mode — working                   |
| **Alarm Daemon**             | `alarm/main.py`, `alarm/alarmController.py` | Basic main loop, alarm checking, snooze, disarm — partially working |
| **Alarm State Machine**      | `alarm/alarmState.py`                   | WAITING and TRIGGERED states only — needs PLAYING_GAME state           |
| **Hardware Input**           | `alarm/InputHandler.py`                 | Single button (disarm) read via GrovePi — needs joystick + snooze      |
| **Hardware Output**          | `alarm/OutputHandler.py`                | **Empty stub** — LCD and buzzer not implemented                        |
| **Joystick Direction Logic** | `alarm/joystickDirection.py`            | Direction decoder written — not integrated into InputHandler            |
| **Flask API Client (Pi)**    | `alarm/FlaskAPIClient.py`              | `get_alarms()` works, `get_pairing_status()` has indentation bug       |
| **Component Examples**       | `alarm clock component examples.py`     | LCD, joystick, button, buzzer test functions — reference only           |
| **Wake-up Games**            | —                                       | **Not started** (only TODO comments)                                   |
| **Web Alarm Dashboard**      | `app/templates/alarm.html`              | **Empty file** — needs full UI                                         |

---

## Existing Bugs & Issues

These must be resolved before proceeding to new features.

### Bug 1: `FlaskAPIClient.py` — Indentation / missing exception handler

`get_pairing_status()` has code outside the `try` block and no `except` clause.

**Current (broken):**
```python
def get_pairing_status(self):
    ...
    try:
        response = requests.post(url, json=payload, timeout=TIMEOUT)
        data: dict = {}

    if response.headers.get("Content-Type") == "application/json":  # <-- outside try
        data = response.json()
    ...
    # NO except block
```

**Fixed:**
```python
def get_pairing_status(self):
    url = f"{self.base_url}/api/device/pairing-status"
    payload = {"serial_number": self.serial_number}

    try:
        response = requests.post(url, json=payload, timeout=TIMEOUT)
        data: dict = {}

        if response.headers.get("Content-Type") == "application/json":
            data = response.json()
        else:
            print("Failed to receive pairing status: " + response.text)

        return data

    except requests.RequestException as e:
        print("Pairing status request failed:", e)
        return None
```

### Bug 2: `pair_device.html` does not exist

`routes.py:137` renders `pair_device.html` but the template file was never created.
- **Fix:** Create `app/templates/pair_device.html` with a form that uses `{{ form.pairing_code }}`.

### Bug 3: `alarm.html` is empty

`routes.py:34` renders `alarm.html` for logged-in users. The file exists but is completely empty.
- **Fix:** Build the alarm dashboard UI (see Stage 7).

### Bug 4: `index.html` has no login/register forms

`routes.py` passes `login_form` and `register_form` to the template, but the HTML has no form elements.
- **Fix:** Add `<form>` blocks using Jinja2 template variables for both forms.

### Bug 5: Unused import in `forms.py`

Line 6: `from nbformat.validator import validators` is unused and pulls in an unnecessary dependency.
- **Fix:** Remove the import. Also remove `nbformat~=5.10.4` from `requirements.txt`.

### Bug 6: Snooze alarms are never checked

`alarmController.py:check_alarms()` iterates `self.alarms` but never iterates `self.snooze_alarms`.

**Fix — add snooze check in `check_alarms()`:**
```python
def check_alarms(self):
    current_minute = datetime.now().minute

    for alarm in self.alarms + self.snooze_alarms:  # <-- check both lists
        if self.state == AlarmState.WAITING and self.current_time == alarm:
            self.trigger_alarm(alarm)
            break

    if self.state == AlarmState.WAITING and current_minute != self.last_displayed_minute:
        self.last_displayed_minute = current_minute
        print(f"Current Time: {datetime.now().strftime('%H:%M')}")
```

### Bug 7: No SNOOZE input mapped

`InputHandler.check_inputs()` only maps a button to `DISARM`. There is no hardware input for `SNOOZE`.
- **Fix:** Add a second button pin, or implement long-press on the existing button to trigger `SNOOZE`.

### Bug 8: `main.py` hardcodes alarms

Alarms are manually appended. The `FlaskAPIClient` exists but is never used.
- **Fix:** Wire up `FlaskAPIClient` in `main.py` to fetch alarms from the server (see Stage 2).

### Bug 9: `.env.example` uses colon syntax

Line 7: `DEVELOPMENT_MODE: False` should be `DEVELOPMENT_MODE=False` for `python-dotenv` to parse it.

### Bug 10: Pin number mismatch

Assembly instructions say buzzer on **D4** and button on **D3**, but code uses buzzer on pin **3** and button on pin **5**.
- **Fix:** Reconcile all pin numbers between `Alarm Clock Assembly Instructions.md`, `alarm clock component examples.py`, and `InputHandler.py`.

---

## Stage 1 — Fix All Existing Bugs

**Estimated effort: 1–2 days**

### Checklist

- [ ] Fix `FlaskAPIClient.py` `get_pairing_status()` indentation and add `except` block
- [ ] Create `app/templates/pair_device.html` with pairing code form
- [ ] Add login/register form HTML to `app/templates/index.html` using Jinja2
- [ ] Fix `check_alarms()` to also iterate `self.snooze_alarms`
- [ ] Remove unused `from nbformat.validator import validators` from `forms.py`
- [ ] Remove `nbformat~=5.10.4` from `requirements.txt`
- [ ] Fix `.env.example` line 7: change `DEVELOPMENT_MODE: False` to `DEVELOPMENT_MODE=False`
- [ ] Reconcile pin numbers across all files and assembly docs
- [ ] Set `FlaskAPIClient.base_url` to a real value (e.g., from environment variable)

---

## Stage 2 — Connect the Pi to the Flask Server

**Estimated effort: 2–3 days**

The alarm daemon (`alarm/main.py`) currently hardcodes alarms and does not talk to the Flask server. This stage bridges that gap.

### Checklist

- [ ] Import and initialise `FlaskAPIClient` in `main.py` with the serial number
- [ ] Load the server URL from a config file or environment variable on the Pi
- [ ] Implement the full **pairing flow** on the Pi side:
  1. On first boot → call `POST /api/device/request-pairing-code`
  2. Display the 6-digit pairing code on the LCD
  3. Poll `POST /api/device/pairing-status` every few seconds
  4. Once status is `"paired"` → proceed to alarm sync
- [ ] **Sync alarms**: Call `POST /api/device/get-alarms` periodically (e.g., every 60 seconds) and update `alarm_controller.alarms`
- [ ] **Send heartbeats**: Call `POST /api/device/heartbeat` every ~30 seconds so the web dashboard knows the device is online
- [ ] Handle network failures gracefully — if WiFi drops, keep running with the last known alarms
- [ ] Store paired status locally so the Pi doesn't re-pair on every reboot

### Example integration in `main.py`:
```python
from FlaskAPIClient import FlaskAPIClient

SERIAL_NUMBER = "12345"
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:5000")

client = FlaskAPIClient(SERIAL_NUMBER)
client.base_url = SERVER_URL

# Sync alarms every 60 seconds
last_sync = 0
SYNC_INTERVAL = 60

while True:
    input_handler.check_inputs()
    # ... existing alarm/state logic ...

    if time.time() - last_sync > SYNC_INTERVAL:
        fetched = client.get_alarms()
        if fetched is not None:
            alarm_controller.alarms = fetched
        last_sync = time.time()

    time.sleep(0.1)
```

---

## Stage 3 — Complete the LCD Output (OutputHandler)

**Estimated effort: 2–3 days**

The `OutputHandler` class is currently empty. It must drive the **Seeed Studio Grove RGB LCD v4.0/5.0** (16 characters × 2 lines, I2C) and the **buzzer**.

### Checklist

- [ ] Import `grove_rgb_lcd` (setText, setRGB) and `grovepi` into `OutputHandler`
- [ ] Initialise I2C addresses in `__init__`
- [ ] Implement `display_time(time_str)` — show `HH:MM` on line 1, date or status on line 2, blue/white backlight
- [ ] Implement `display_alarm_triggered(alarm_time)` — show "ALARM!" on line 1, alarm time on line 2, **flash red backlight**
- [ ] Implement `display_pairing_code(code)` — show "Pair Code:" on line 1, the 6-digit code on line 2
- [ ] Implement `display_game_prompt(line1, line2)` — show game content on both lines
- [ ] Implement `display_game_success()` — show "Correct!" with green backlight
- [ ] Implement `display_game_fail()` — show "Wrong!" with red backlight
- [ ] Implement `clear_display()` — reset LCD and backlight
- [ ] Replace **all** `print()` calls in `alarmController.py` with `OutputHandler` method calls
- [ ] Pass `OutputHandler` instance to `AlarmController.__init__`

### LCD display constraints (important for game design):
- **16 characters per line, 2 lines only**
- All game UIs must fit within this limitation
- Use scrolling or paging for longer messages

### Example `OutputHandler`:
```python
from grove_rgb_lcd import setText, setRGB

class OutputHandler:
    def __init__(self):
        self.set_backlight(255, 255, 255)  # Default white

    def set_backlight(self, r, g, b):
        setRGB(r, g, b)

    def display_time(self, time_str):
        setText(f"Time: {time_str}\nSmartAlarm")
        self.set_backlight(50, 50, 255)

    def display_alarm_triggered(self, alarm_time):
        setText(f"!! ALARM !!\n{alarm_time}")
        self.set_backlight(255, 0, 0)

    def display_pairing_code(self, code):
        setText(f"Pair Code:\n{code}")
        self.set_backlight(255, 255, 0)

    def display_game(self, line1, line2=""):
        setText(f"{line1}\n{line2}")

    def clear(self):
        setText("")
        self.set_backlight(0, 0, 0)
```

---

## Stage 4 — Complete All Hardware Inputs (InputHandler)

**Estimated effort: 1–2 days**

Currently `InputHandler` only reads one button (DISARM). It needs joystick + snooze support.

### Checklist

- [ ] Add new `InputOption` enum values:
  ```python
  class InputOption(Enum):
      NONE = 0
      DISARM = 1
      SNOOZE = 2
      JOYSTICK_UP = 3
      JOYSTICK_DOWN = 4
      JOYSTICK_LEFT = 5
      JOYSTICK_RIGHT = 6
      JOYSTICK_CLICK = 7
  ```
- [ ] Add a **second button** for snooze (or implement long-press detection on the existing button)
- [ ] Initialise **joystick analog pins** (A0 for X, A1 for Y) in `__init__`
- [ ] Integrate `joystickDirection.directionRead(x, y)` into `check_inputs()`
- [ ] Detect joystick click (X ≥ 1020)
- [ ] Add **debouncing** — ignore repeated triggers within ~200ms
- [ ] Update `main.py` to pass joystick inputs to the game engine (Stage 5)

### Pin mapping (reconciled with assembly docs):
| Component      | Port   | Pin Variable        |
|----------------|--------|---------------------|
| Button (Disarm)| D3     | `self.disarm_button = 3` |
| Buzzer         | D4     | `self.buzzer_pin = 4`    |
| Joystick X     | A0     | `self.joy_x = 0`         |
| Joystick Y     | A1     | `self.joy_y = 1`         |
| LCD            | I2C-1  | (handled by grove_rgb_lcd) |

### Example updated `check_inputs()`:
```python
import time as _time
from joystickDirection import directionRead

class InputHandler:
    def __init__(self):
        self.current_action = InputOption.NONE
        self.disarm_button = 3
        self.snooze_button = 5   # Second button or same with long-press
        self.joy_x = 0
        self.joy_y = 1
        self._last_input_time = 0
        self._debounce_ms = 200

        grovepi.pinMode(self.disarm_button, "INPUT")
        grovepi.pinMode(self.snooze_button, "INPUT")
        grovepi.pinMode(self.joy_x, "INPUT")
        grovepi.pinMode(self.joy_y, "INPUT")

    def check_inputs(self):
        self.current_action = InputOption.NONE
        now = _time.time() * 1000

        if now - self._last_input_time < self._debounce_ms:
            return

        try:
            if grovepi.digitalRead(self.disarm_button) == 1:
                self.current_action = InputOption.DISARM
            elif grovepi.digitalRead(self.snooze_button) == 1:
                self.current_action = InputOption.SNOOZE
            else:
                x = grovepi.analogRead(self.joy_x)
                y = grovepi.analogRead(self.joy_y)

                if x >= 1020:
                    self.current_action = InputOption.JOYSTICK_CLICK
                else:
                    direction = directionRead(x, y)
                    direction_map = {
                        "UP": InputOption.JOYSTICK_UP,
                        "DOWN": InputOption.JOYSTICK_DOWN,
                        "LEFT": InputOption.JOYSTICK_LEFT,
                        "RIGHT": InputOption.JOYSTICK_RIGHT,
                    }
                    self.current_action = direction_map.get(direction, InputOption.NONE)

            if self.current_action != InputOption.NONE:
                self._last_input_time = now

        except IOError:
            print("InputHandler: I/O Error reading pins")
```

---

## Stage 5 — Build Wake-Up Games (Core Feature)

**Estimated effort: 5–7 days**

This is the **main feature** of the smart alarm. When the alarm triggers and the user presses DISARM, they must complete a mini-game before the alarm stops — preventing them from going back to sleep.

### 5.1 — Add PLAYING_GAME state

- [ ] Add `PLAYING_GAME = 3` to `AlarmState` enum in `alarmState.py`

### 5.2 — Create game folder structure

```
alarm/games/
    __init__.py
    base_game.py          # Abstract base class for all games
    math_game.py          # Arithmetic puzzle
    sequence_game.py      # Memory sequence replay
    direction_game.py     # Simon-says with joystick directions
    game_manager.py       # Picks and instantiates a random game
```

### 5.3 — Implement `BaseGame` (abstract class)

```python
# alarm/games/base_game.py
from abc import ABC, abstractmethod

class BaseGame(ABC):
    """
    Abstract base class that all wake-up games must inherit from.
    Each game receives references to the OutputHandler (LCD) and
    the current InputOption from InputHandler.
    """

    def __init__(self, output_handler):
        self.output = output_handler
        self.completed = False

    @abstractmethod
    def start(self):
        """Initialise the game state and show first prompt on LCD."""
        pass

    @abstractmethod
    def update(self, current_input):
        """Called each tick of the main loop. Process input, update LCD."""
        pass

    def is_complete(self) -> bool:
        """Return True when the player has won the game."""
        return self.completed
```

### 5.4 — Implement Game 1: Maths Puzzle

**How it works on the 16×2 LCD:**
```
Line 1: "9 x 8 = ?"
Line 2: ">72<    76"    ← joystick LEFT/RIGHT to select, CLICK to confirm
```

- [ ] Generate random arithmetic (addition, subtraction, multiplication)
- [ ] Generate one correct answer and one wrong answer (placed randomly left/right)
- [ ] Joystick LEFT/RIGHT moves the `>` selector between the two options
- [ ] Joystick CLICK confirms the selection
- [ ] Correct → game complete, alarm stops
- [ ] Wrong → generate a new question, flash red backlight briefly
- [ ] Require 3 correct answers in a row to fully dismiss

### 5.5 — Implement Game 2: Memory Sequence

**How it works:**
1. LCD shows a sequence of directions one at a time: `"Remember: UP"`, `"Remember: LEFT"`, etc.
2. Backlight changes color per direction (UP=blue, DOWN=green, LEFT=yellow, RIGHT=red)
3. After showing all steps, LCD says `"Your turn! 1/3"`
4. User must replay the sequence using the joystick
5. One wrong input → restart the sequence
6. Start with 3 steps; increase by 1 each time the alarm goes off (stored in memory)

### 5.6 — Implement Game 3: Direction Match (Simon Says)

**How it works:**
```
Line 1: "Point joystick"
Line 2: ">>> RIGHT >>>"
```

- [ ] LCD shows a random direction
- [ ] User must push joystick in that direction within 3 seconds
- [ ] Correct → next round (repeat 3–5 times to dismiss)
- [ ] Wrong or timeout → restart from round 1
- [ ] Backlight flashes green for correct, red for wrong

### 5.7 — Implement `GameManager`

```python
# alarm/games/game_manager.py
import random
from games.math_game import MathGame
from games.sequence_game import SequenceGame
from games.direction_game import DirectionGame

class GameManager:
    GAME_CLASSES = [MathGame, SequenceGame, DirectionGame]

    @staticmethod
    def get_random_game(output_handler):
        """Return a random game instance, ready to start."""
        game_class = random.choice(GameManager.GAME_CLASSES)
        return game_class(output_handler)
```

### 5.8 — Integrate games into `AlarmController`

- [ ] Modify `disarm_alarm()`:
  ```python
  def disarm_alarm(self):
      self.state = AlarmState.PLAYING_GAME
      self.current_game = GameManager.get_random_game(self.output_handler)
      self.current_game.start()
  ```
- [ ] Add game update logic to the main loop in `main.py`:
  ```python
  if alarm_controller.state == AlarmState.PLAYING_GAME:
      alarm_controller.current_game.update(input_handler.current_action)
      if alarm_controller.current_game.is_complete():
          alarm_controller.stop_alarm()
  ```
- [ ] On snooze, skip the game and just add +5 minutes (existing behaviour)

---

## Stage 6 — Buzzer / Audio Feedback

**Estimated effort: 1 day**

### Checklist

- [ ] Add buzzer control methods to `OutputHandler`:
  - `start_alarm_sound()` — repeating tone via PWM on buzzer pin
  - `stop_alarm_sound()` — silence the buzzer
  - `beep_correct()` — short beep (100ms)
  - `beep_wrong()` — long buzz (500ms)
  - `play_victory()` — short ascending melody
- [ ] Wire buzzer calls into `AlarmController`:
  - `trigger_alarm()` → `output.start_alarm_sound()`
  - `stop_alarm()` → `output.stop_alarm_sound()`
  - `snooze_alarm()` → `output.stop_alarm_sound()`
- [ ] Wire buzzer calls into game logic:
  - Correct answer → `output.beep_correct()`
  - Wrong answer → `output.beep_wrong()`
  - Game complete → `output.play_victory()`

### Example buzzer code (from your component examples):
```python
import grovepi
import time

BUZZER_PIN = 4
grovepi.pinMode(BUZZER_PIN, "OUTPUT")

def start_alarm_sound(self):
    grovepi.digitalWrite(BUZZER_PIN, 1)

def stop_alarm_sound(self):
    grovepi.digitalWrite(BUZZER_PIN, 0)

def beep_correct(self):
    grovepi.digitalWrite(BUZZER_PIN, 1)
    time.sleep(0.1)
    grovepi.digitalWrite(BUZZER_PIN, 0)
```

---

## Stage 7 — Web Dashboard — Alarm Management UI

**Estimated effort: 3–4 days**

### 7.1 — Build `alarm.html` template

Currently empty. Needs:

- [ ] Display current user's paired device(s) and online/offline status
- [ ] List all alarms with time, enabled/disabled toggle, and delete button
- [ ] "Add alarm" form with a time picker
- [ ] Optional: display game statistics (completion times, snooze counts)

### 7.2 — Add Flask routes for alarm CRUD

- [ ] `POST /alarm/add` — create a new alarm for the user's device
  ```python
  @app.route("/alarm/add", methods=["POST"])
  @login_required
  def add_alarm():
      time_str = request.form.get("time")
      device_serial = request.form.get("device_serial")
      # Create Alarm object and save to DB
      ...
  ```
- [ ] `POST /alarm/toggle/<id>` — enable or disable an alarm
- [ ] `POST /alarm/delete/<id>` — remove an alarm
- [ ] `GET /alarm/list` — return alarms as JSON (for AJAX updates)

### 7.3 — Create `pair_device.html`

This template is referenced but missing:

```html
<!-- app/templates/pair_device.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Pair Device</title>
</head>
<body>
    <h1>Pair a New Device</h1>
    <form method="POST">
        {{ form.hidden_tag() }}
        {{ form.pairing_code.label }} {{ form.pairing_code() }}
        {{ form.submit() }}
    </form>
</body>
</html>
```

---

## Stage 8 — Testing

**Estimated effort: 2–3 days**

### 8.1 — Unit tests (no hardware required)

- [ ] Test all three game classes with mocked InputOption values
- [ ] Test `AlarmController` state transitions:
  - WAITING → TRIGGERED → PLAYING_GAME → WAITING
  - WAITING → TRIGGERED → snooze → WAITING (+ snooze alarm added)
- [ ] Test `AlarmController.check_alarms()` with known times
- [ ] Test `joystickDirection.directionRead()` with boundary values

### 8.2 — API tests (Flask test client)

- [ ] Test `POST /api/device/request-pairing-code` — valid and invalid serial numbers
- [ ] Test `POST /api/device/pairing-status` — all three states (pairing, paired, expired)
- [ ] Test `POST /api/device/heartbeat` — valid device, invalid device
- [ ] Test `POST /api/device/get-alarms` — paired device, unpaired device
- [ ] Test login, registration, logout flows
- [ ] Test alarm CRUD routes (add, toggle, delete)

### 8.3 — Integration tests (on Raspberry Pi)

- [ ] Verify LCD displays correctly in all modes (time, alarm, pairing, game)
- [ ] Verify joystick reads correctly in all 4 directions + click
- [ ] Verify buttons trigger DISARM and SNOOZE
- [ ] Verify buzzer sounds on alarm and stops on dismiss/snooze
- [ ] Test full flow: set alarm on website → alarm triggers on Pi → play game → dismiss
- [ ] Test edge cases: midnight rollover, two alarms at the same time, WiFi disconnect

### Suggested test framework:
```
pip install pytest pytest-flask
```

---

## Stage 9 — Deployment to Raspberry Pi

**Estimated effort: 1–2 days**

### 9.1 — Prepare the Raspberry Pi

- [ ] Flash **Raspberry Pi OS** (Lite or Desktop) onto SD card
- [ ] Enable I2C: `sudo raspi-config` → Interface Options → I2C → Enable
- [ ] Enable SSH (for remote access): `sudo raspi-config` → Interface Options → SSH
- [ ] Connect to WiFi

### 9.2 — Install GrovePi

```bash
# Option A: Official installer (may fail on newer OS — see Bug notes)
curl -kL dexterindustries.com/update_grovepi | bash

# Option B: Manual install from GitHub (more reliable)
git clone https://github.com/DexterInd/GrovePi.git
cd GrovePi/Script
sudo bash install.sh
```

### 9.3 — Deploy the alarm code

```bash
# Clone your repository
git clone <your-repo-url> ~/smartalarm
cd ~/smartalarm

# Install Python dependencies
pip3 install -r requirements.txt

# Set the server URL
export SERVER_URL="http://<your-server-ip>:5000"
```

### 9.4 — Auto-start on boot (systemd service)

Create `/etc/systemd/system/smartalarm.service`:

```ini
[Unit]
Description=SmartAlarm Clock Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/pi/smartalarm/alarm/main.py
WorkingDirectory=/home/pi/smartalarm/alarm
Restart=always
RestartSec=5
User=pi
Environment=SERVER_URL=http://<your-server-ip>:5000

[Install]
WantedBy=multi-party.target
```

Then enable it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smartalarm
sudo systemctl start smartalarm

# Check status:
sudo systemctl status smartalarm

# View logs:
journalctl -u smartalarm -f
```

### 9.5 — Deploy the Flask server

**Option A: Docker on a cloud VM (recommended for production)**
```bash
scp .env docker-compose.yml Dockerfile requirements.txt app/ user@server:~/smartalarm/
ssh user@server
cd ~/smartalarm
docker-compose up -d
```

**Option B: Run on the Pi itself (for local-only / demo mode)**
```bash
cd ~/smartalarm
export DEVELOPMENT_MODE=True
python3 run_dev_server.py
```

---

## Stage 10 — Polish & Final Deployment

**Estimated effort: 1–2 days**

### Checklist

- [ ] **Secure the API**: Add API key or token authentication for all `/api/device/*` endpoints so only your physical devices can call them
- [ ] **Proper logging**: Replace all `print()` statements with Python `logging` module
- [ ] **Graceful offline mode**: If the Pi loses WiFi, cache the last known alarms locally (e.g., in a JSON file) and keep running
- [ ] **Error handling**: Add try/except around all hardware I/O calls and API calls
- [ ] **Physical enclosure**: Design and build/3D-print a case for the Raspberry Pi + GrovePi + components
- [ ] **README.md**: Complete setup instructions, architecture diagram, screenshots
- [ ] **Demo video**: Record a full walkthrough — set alarm on web, alarm triggers, play game, dismiss
- [ ] **Code cleanup**: Remove all TODO comments, commented-out code, and debug prints
- [ ] **Environment variable validation**: Ensure all required env vars are present at startup with clear error messages

---

## Summary Timeline

| Stage | Task                                | Est. Time   | Priority  |
|-------|-------------------------------------|-------------|-----------|
| 1     | Fix all existing bugs               | 1–2 days    | 🔴 Critical |
| 2     | Connect Pi ↔ Flask server           | 2–3 days    | 🔴 Critical |
| 3     | LCD output handler                  | 2–3 days    | 🔴 Critical |
| 4     | Complete input handler              | 1–2 days    | 🔴 Critical |
| 5     | **Build wake-up games**             | 5–7 days    | 🔴 Critical |
| 6     | Buzzer / audio feedback             | 1 day       | 🟡 Important |
| 7     | Web alarm dashboard UI              | 3–4 days    | 🟡 Important |
| 8     | Testing                             | 2–3 days    | 🟡 Important |
| 9     | Deploy to Raspberry Pi              | 1–2 days    | 🔴 Critical |
| 10    | Polish & final deployment           | 1–2 days    | 🟢 Nice-to-have |
|       | **Total**                           | **~19–29 days** |        |

### Recommended order of work:
1. **Stage 1** (bugs) → must be done first
2. **Stages 3 + 4** (hardware I/O) → can be done in parallel by different team members
3. **Stage 5** (games) → the biggest task, start as soon as I/O works
4. **Stage 2** (Pi ↔ server) → can be done in parallel with Stage 5
5. **Stage 6** (buzzer) → quick win, do alongside Stage 5
6. **Stage 7** (web UI) → can be done by a frontend-focused team member in parallel
7. **Stage 8** (testing) → ongoing, but formal testing after Stages 5 + 7
8. **Stage 9** (deploy) → once everything works locally
9. **Stage 10** (polish) → final week

---

*End of roadmap. Good luck with the SmartAlarm project!*

