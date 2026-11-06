"""Hardware-independent input interpretation for the three Pi controllers.

Each class takes raw readings and returns a discrete action (or None), so the
rearm/debounce rules can be unit-tested on a laptop.
"""

import config


class JoystickStepper:
    """One step per push; returns to the dead zone before the next step."""

    def __init__(self, center_x, center_y, invert_x=None, invert_y=None,
                 trigger=None, deadzone=None, full_scale=1023):
        self.center_x = center_x
        self.center_y = center_y
        self.range_x = max(center_x, full_scale - center_x) or 1
        self.range_y = max(center_y, full_scale - center_y) or 1
        self.sign_x = -1 if (config.JOY_INVERT_X if invert_x is None else invert_x) else 1
        self.sign_y = -1 if (config.JOY_INVERT_Y if invert_y is None else invert_y) else 1
        self.trigger = config.JOY_TRIGGER if trigger is None else trigger
        self.deadzone = config.JOY_DEADZONE if deadzone is None else deadzone
        self.armed = True

    def normalize(self, raw_x, raw_y):
        nx = self.sign_x * (raw_x - self.center_x) / self.range_x
        ny = self.sign_y * (raw_y - self.center_y) / self.range_y
        return nx, ny

    def update(self, raw_x, raw_y):
        nx, ny = self.normalize(raw_x, raw_y)
        if not self.armed:
            if abs(nx) < self.deadzone and abs(ny) < self.deadzone:
                self.armed = True
            return None
        x_hit = abs(nx) >= self.trigger
        y_hit = abs(ny) >= self.trigger
        if not (x_hit or y_hit):
            return None
        self.armed = False
        if x_hit and (not y_hit or abs(nx) >= abs(ny)):
            return "right" if nx > 0 else "left"
        # Positive normalized Y means "up" after any inversion.
        return "up" if ny > 0 else "down"


class ProximitySwing:
    """Swing after N samples at/above trigger; rearm after N at/below release."""

    def __init__(self, trigger=None, release=None, confirm=None):
        self.trigger = config.PROX_TRIGGER if trigger is None else trigger
        self.release = config.PROX_RELEASE if release is None else release
        self.confirm = config.PROX_CONFIRM if confirm is None else confirm
        self.armed = False
        self.near_count = 0
        self.clear_count = 0

    def update(self, prox):
        if self.armed:
            self.near_count = self.near_count + 1 if prox >= self.trigger else 0
            if self.near_count >= self.confirm:
                self.armed = False
                self.near_count = 0
                self.clear_count = 0
                return "swing"
        else:
            self.clear_count = self.clear_count + 1 if prox <= self.release else 0
            if self.clear_count >= self.confirm:
                self.armed = True
                self.clear_count = 0
        return None


def openness_from_ratios(ratios, closed=None, opened=None):
    """Map per-finger tip/knuckle distance ratios to a 0-100 hand openness."""
    closed = config.HAND_CLOSED_RATIO if closed is None else closed
    opened = config.HAND_OPEN_RATIO if opened is None else opened
    span = (opened - closed) or 1.0
    levels = [min(max((r - closed) / span, 0.0), 1.0) for r in ratios]
    return 100.0 * sum(levels) / len(levels)


class BrightnessFilter:
    """Smooth raw hand openness and decide when to publish a brightness.

    `level` is 0-100, or None when no hand is visible (the light stays put).
    Returns the integer brightness to publish, or None.
    """

    def __init__(self, smoothing=None, step=None, publish_hz=None):
        self.smoothing = config.LIGHT_SMOOTHING if smoothing is None else smoothing
        self.step = config.LIGHT_STEP if step is None else step
        hz = config.LIGHT_PUBLISH_HZ if publish_hz is None else publish_hz
        self.min_gap = 1.0 / hz if hz > 0 else 0.0
        self.smoothed = None
        self.last_sent = None
        self.last_time = None

    def update(self, level, now):
        if level is None:
            self.smoothed = None
            self.last_sent = None
            return None
        if self.smoothed is None:
            self.smoothed = level
        else:
            self.smoothed += self.smoothing * (level - self.smoothed)
        value = int(round(self.smoothed / self.step) * self.step)
        value = min(max(value, 0), 100)
        if value == self.last_sent:
            return None
        if self.last_time is not None and now - self.last_time < self.min_gap:
            return None
        self.last_sent = value
        self.last_time = now
        return value
