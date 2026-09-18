"""Tunable numbers for the bird-clock game.

World coordinates: origin at bottom-left, +x right, +y up.
That way a positive velocity is "up", matching the hold-to-flap design.
The renderer converts to PIL's top-left / +y-down when drawing.

Change values here after on-device testing. Game code should not hardcode sizes.

Later (not in this pass):
- Spawn coins / invincibility using ItemConfig
- Map real wall-clock into a sexagesimal / fruit-token score display
- Change pipes, palette, and rules by time of day
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenConfig:
    width: int = 240
    height: int = 135
    rotation: int = 90
    backlight_gpio: int = 22
    # ST7789 init matches Lab 2 screen_clock.py
    panel_width: int = 135
    panel_height: int = 240
    x_offset: int = 53
    y_offset: int = 40
    baudrate: int = 64_000_000
    cs_gpio: int = 5
    dc_gpio: int = 25


@dataclass(frozen=True)
class ButtonConfig:
    """MiniPiTFT: top button = start/retry, bottom button = flap."""

    start_gpio: int = 23  # button A, upper
    flap_gpio: int = 24  # button B, lower
    active_low: bool = True


@dataclass(frozen=True)
class BirdConfig:
    # Visible hitbox is this exact rectangle (no sprite inset).
    width: float = 8.0
    height: float = 8.0
    # Fixed x: pipes scroll, bird stays put.
    x: float = 32.0
    start_y: float = 64.0
    # Acceleration while the flap button is held (up).
    flap_accel: float = 260.0
    # Acceleration when released (negative = downward).
    gravity: float = -140.0
    max_up_speed: float = 70.0
    max_down_speed: float = -90.0
    # Death: extra downward accel so the bird leaves the screen.
    death_gravity: float = -220.0


@dataclass(frozen=True)
class PipeConfig:
    spawn_x: float = 240.0
    # Random mix: bi/uni rect, bi/uni triangle, plus a long bottom ground strip.
    # Dense on purpose: ~4-5 columns fit on the 240px screen for spectacle.
    # Left-edge spacing ≈ this value; 240/55 ≈ 4.4 obstacles visible at once.
    min_spacing: float = 48.0
    max_spacing: float = 68.0
    min_width: float = 36.0
    max_width: float = 58.0
    min_gap: float = 36.0
    max_gap: float = 88.0
    # Idle is harder: pipes more often, gaps tighter (still >= bird + gap_over_bird).
    idle_min_spacing: float = 44.0
    idle_max_spacing: float = 62.0
    idle_min_gap: float = 22.0
    idle_max_gap: float = 40.0
    # Gap is at least bird hitbox plus this many pixels (both modes).
    gap_over_bird: float = 10.0
    edge_margin: float = 6.0
    # Single-sided solid height (rect or triangle apex).
    uni_min_height: float = 28.0
    uni_max_height: float = 72.0
    # Continuous bottom bar lasting this many seconds at current scroll speed.
    ground_min_seconds: float = 5.0
    ground_max_seconds: float = 10.0
    ground_height: float = 18.0
    # Greybox entrance: solids stab in from the top / bottom edge once the
    # obstacle is fully past the right edge. Cosmetic only - collision and the
    # auto-pilot always use the final geometry, or the corridor would keep
    # shrinking after the pilot had already committed to it.
    # Headroom: an obstacle covers ~192px between entering and reaching the
    # bird, so even at play_max_speed there are ~3s before it matters.
    enter_seconds: float = 0.75
    # How far past the seated position the stab punches, as a fraction of the
    # solid's height. 1.2 = 120%, 1.0 = plain slide with no recoil.
    enter_peak: float = 1.13
    # Extra pixels inside the right edge before the stab starts. Raising it
    # plays the animation further into frame, at the cost of the obstacle
    # being invisible while it waits.
    enter_margin_x: float = 0.0
    # Spawn weights live per scene now, in scenes.py: a scene only rolls the
    # shapes it has art for.
    # Retry distance when the scene had nothing legal to spawn.
    spawn_retry_spacing: float = 20.0
    idle_speed: float = 34.0
    play_start_speed: float = 40.0
    play_speed_gain: float = 2.0
    play_max_speed: float = 72.0


@dataclass(frozen=True)
class ItemConfig:
    """Pickups. One box per item, triggers on overlap, never blocks flight.

    Play mode only: the idle number is a real wall clock, and a pickup that
    added score there would make the displayed time wrong.

    Seasonal art (butterfly, popsicle, maple leaf, ...) swaps by kind; the
    engine treats every kind the same except invincibility.
    """

    spawn_enabled: bool = True
    spawn_x: float = 240.0
    # Hitbox. Generous on purpose - difficulty is not the point here. It still
    # has to fit inside an obstacle gap, and past ~18 too many spawns get
    # skipped for want of room (6% skipped at 16, 10% at 22).
    size: float = 16.0
    # Drawn size, centred on the hitbox. Free to overlap walls: the pickup
    # reads as a separate layer, and collision never uses this number.
    sprite_size: float = 26.0
    min_spacing: float = 120.0
    max_spacing: float = 260.0
    # Retry sooner when the spawn column was blocked by an obstacle.
    retry_spacing: float = 24.0
    # Keep the hitbox this far clear of obstacle walls so it stays reachable
    # without grazing. The art may still overlap; only the hitbox is fenced.
    clearance: float = 3.0
    edge_margin: float = 8.0
    coin_score: int = 5
    invincible_seconds: float = 3.0
    # Invincibility stays off until the art and the HUD cue exist.
    invincible_chance: float = 0.0


@dataclass(frozen=True)
class ScoreConfig:
    """Idle uses a fake ticking score for now.

    Later: map a real wall-clock into this number, then render it in a
    sexagesimal / fruit-token display instead of raw digits.
    """

    points_per_second: int = 1
    idle_starts_at: int = 0
    play_starts_at: int = 0


@dataclass(frozen=True)
class DeathConfig:
    wait_before_idle_seconds: float = 10.0


@dataclass(frozen=True)
class AutoPilotConfig:
    """Idle flight: next pipe first, later pipes only as a weak tie-break.

    First action is one frame. If the search cannot clear the next gap,
    fall back to one-pipe greedy. Aim at the gap wall toward the following
    pipe (skim) instead of waiting to pass through the center.
    """

    aim_slack: float = 2.0
    look_ahead_min: float = 0.12
    hover_y: float = 67.0
    pipes_ahead: int = 3
    # Obstacles arriving within this many seconds also constrain the corridor.
    reaction_seconds: float = 2.0
    # Corridor intersection does the steering; a deep search only costs Pi time.
    chunks: int = 5
    chunk_seconds: float = 0.25
    sim_dt: float = 1.0 / 30.0
    crash_penalty: float = 1_000_000.0
    center_weight: float = 1.0
    exit_speed_weight: float = 0.02
    skim_margin: float = 2.0


@dataclass(frozen=True)
class LoopConfig:
    fps: float = 30.0


@dataclass(frozen=True)
class HudConfig:
    """Top-left feather clock, then left-edge button hints below it.

    Hints sit on rows 1.5 and 5 so they clear the clock row. Everything here
    is decoration: no hitboxes.
    """

    line_height: int = 14
    margin_x: int = 4
    clock_y: int = 1
    hint_top_y: int = 22
    # Button B sits low, near its physical position on the board.
    hint_bottom_y: int = 114
    # Feather placeholder size; swap for a sprite later.
    feather_w: int = 5
    feather_h: int = 8
    feather_text_gap: int = 2
    group_gap: int = 5
    best_margin_x: int = 4
    # Red feather in idle: month + day, no year.
    date_format: str = "%m/%d"
    # "+1" popup right of the white feather: jump up, then vanish.
    popup_gap: int = 4
    popup_seconds: float = 0.7
    popup_rise: int = 9


@dataclass(frozen=True)
class ColorConfig:
    background: str = "#101820"
    bird: str = "#F5D76E"
    bird_outline: str = "#FFFFFF"
    pipe: str = "#3D9970"
    hud: str = "#FFFFFF"
    hint: str = "#AAAAAA"
    death: str = "#FF6666"
    # Feather clock: date / hour / minute / second.
    feather_date: str = "#E4572E"
    feather_hour: str = "#F2C14E"
    feather_minute: str = "#4C9F70"
    feather_second: str = "#F2F2F2"
    score_popup: str = "#5CE08A"
    pickup: str = "#6FD3F2"
    pickup_invincible: str = "#C77DFF"


@dataclass(frozen=True)
class SkinConfig:
    """Where art lives. Anything missing falls back to greybox.

    Folder layout: bird_clock/<root>/<skin>/skin.json plus its PNGs, where
    <skin> comes from the active scene.
    """

    enabled: bool = True
    root: str = "assets"


@dataclass(frozen=True)
class SceneConfig:
    """Which scene (art + spawn pool) is live.

    scenes=None uses scenes.DEFAULT_SCENES. Set auto_by_date=False to pin the
    fallback and ignore the calendar.
    """

    auto_by_date: bool = True
    fallback: str = "spring"
    scenes: tuple = None


@dataclass(frozen=True)
class GameConfig:
    screen: ScreenConfig = ScreenConfig()
    buttons: ButtonConfig = ButtonConfig()
    bird: BirdConfig = BirdConfig()
    pipes: PipeConfig = PipeConfig()
    items: ItemConfig = ItemConfig()
    score: ScoreConfig = ScoreConfig()
    death: DeathConfig = DeathConfig()
    auto_pilot: AutoPilotConfig = AutoPilotConfig()
    loop: LoopConfig = LoopConfig()
    skin: SkinConfig = SkinConfig()
    scenes: SceneConfig = SceneConfig()
    hud: HudConfig = HudConfig()
    colors: ColorConfig = ColorConfig()
    # Floor/ceiling wrap: leaving the top enters the bottom, and vice versa.
    bounds_kill: bool = False
    vertical_wrap: bool = True
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font_size: int = 12


DEFAULT = GameConfig()
