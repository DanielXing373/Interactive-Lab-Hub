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
    # Shared flap flipbook in assets/pigeon/. Ping-pong 1-2-3-4-3-2 while vy>0.
    art_folder: str = "pigeon"
    frames: tuple = ("pigeon1.png", "pigeon2.png", "pigeon3.png", "pigeon4.png")
    anim_frame_seconds: float = 0.09
    # Uniform scale of the authored PNGs (not a stretch onto the hitbox).
    sprite_scale: float = 0.67


@dataclass(frozen=True)
class PipeConfig:
    spawn_x: float = 240.0
    # Random mix: bi/uni rect, bi/uni triangle, plus a long bottom ground strip.
    # Dense on purpose: ~4-5 columns fit on the 240px screen for spectacle.
    # Left-edge spacing ≈ this value; 240/55 ≈ 4.4 obstacles visible at once.
    # A scene may override via Scene.min_spacing / max_spacing (and idle
    # equivalents). Empty scene fields keep these defaults — spring does.
    min_spacing: float = 48.0
    max_spacing: float = 68.0
    min_width: float = 36.0
    max_width: float = 58.0
    min_gap: float = 32.0
    max_gap: float = 76.0
    # Idle is harder: pipes more often, gaps tighter (still >= bird + gap_over_bird).
    idle_min_spacing: float = 44.0
    idle_max_spacing: float = 62.0
    idle_min_gap: float = 22.0
    idle_max_gap: float = 40.0
    # Gap is at least bird hitbox plus this many pixels (both modes).
    gap_over_bird: float = 10.0
    edge_margin: float = 6.0
    # Single-sided solid height (rect or triangle apex).
    uni_min_height: float = 36.0
    uni_max_height: float = 84.0
    # Hanging vines are a thinner, shorter slot than the trees.
    vine_min_height: float = 22.0
    vine_max_height: float = 48.0
    vine_min_width: float = 12.0
    vine_max_width: float = 28.0
    # Continuous bottom/ceiling bar lasting this many seconds at current
    # scroll speed. One global default for every season; a scene may still
    # override via Scene.ground_seconds (christmas Santa strip is the
    # documented special case).
    ground_min_seconds: float = 2.0
    ground_max_seconds: float = 3.5
    ground_height: float = 18.0
    # Total loop for floor/ceiling strip animation. Frame time is this / N
    # files in skin.json. Two spring caterpillar frames therefore last 0.2s
    # each; a one-file strip stays static. Floor and ceiling share one clock.
    strip_anim_seconds: float = 0.4
    # Greybox entrance: solids stab in from the top / bottom edge once the
    # obstacle is fully past the right edge. Cosmetic only - collision and the
    # auto-pilot always use the final geometry, or the corridor would keep
    # shrinking after the pilot had already committed to it.
    # Headroom: an obstacle covers ~192px between entering and reaching the
    # bird, so even at play_max_speed there are ~3s before it matters.
    enter_seconds: float = 0.62
    # How far past the seated position the stab punches, as a fraction of the
    # solid's height. 1.2 = 120%, 1.0 = plain slide with no recoil.
    enter_peak: float = 1.08
    # Extra pixels inside the right edge before the stab starts. Raising it
    # plays the animation further into frame, at the cost of the obstacle
    # being invisible while it waits.
    enter_margin_x: float = 0.0
    # Spawn weights live per scene now, in scenes.py. Generic seasons share
    # the spring lottery; a later pack (christmas) may override. Spacing and
    # play vs idle speed stay here — one global logic, two modes.
    # Retry distance when the scene had nothing legal to spawn.
    spawn_retry_spacing: float = 20.0
    idle_speed: float = 34.0
    play_start_speed: float = 40.0
    play_speed_gain: float = 2.0
    play_max_speed: float = 72.0


@dataclass(frozen=True)
class ItemConfig:
    """Pickups. One box per item, triggers on overlap, never blocks flight.

    Play and idle both spawn pickups. Idle collecting is cosmetic: world
    "+n" at the sprite, but it must not add score or the wall-clock HUD
    would lie.

    Seasonal art (butterfly, popsicle, maple leaf, ...) swaps by kind; the
    engine treats every kind the same except invincibility.
    """

    spawn_enabled: bool = True
    spawn_x: float = 240.0
    # Scroll vs obstacles. Pickups spawn in the live corridor, then fly left
    # faster than pipes so they read as chasing the bird. Relative x vs the
    # spawn column is allowed to drift; auto-pilot is unchanged.
    speed_mul: float = 1.4
    # Hitbox. Generous on purpose - difficulty is not the point here. It still
    # has to fit inside an obstacle gap, and past ~18 too many spawns get
    # skipped for want of room (6% skipped at 16, 10% at 22).
    size: float = 16.0
    # Drawn size, centred on the hitbox. Free to overlap walls: the pickup
    # reads as a separate layer, and collision never uses this number.
    sprite_size: float = 26.0
    # Seconds per pickup animation frame. A two-file list (spring butterfly)
    # therefore loops in 0.5s. All on-screen pickups share one clock.
    anim_frame_seconds: float = 0.25
    # One-file pickups (summer popsicle) rotate about the image centre instead
    # of flipping frames. Multi-file lists ignore these and stay a flipbook.
    # skin.json pickup.<kind> may override per slot (set 0 to keep a still).
    swing_degrees: float = 30.0
    swing_seconds: float = 0.5
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
class FloaterConfig:
    """Non-interactive banners (christmas text). Not in the obstacle lottery."""

    spawn_x: float = 240.0
    interval_seconds: float = 10.0
    speed_mul: float = 1.6
    # Approximate art height, used only to keep the spawn band on-screen.
    spawn_height: float = 30.0
    cull_width: float = 160.0
    edge_margin: float = 18.0
    bob_pixels: float = 3.5
    bob_seconds: float = 1.4
    anim_frame_seconds: float = 0.4


@dataclass(frozen=True)
class ScoreConfig:
    """Idle HUD is the wall clock. Play copies it at start, then ticks alone."""

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
    skim_margin: float = 4.0
    # Treat solids as this many pixels taller in the idle search so a path
    # that only grazes the authored top is rejected (round canopies).
    solid_inflate: float = 3.0


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
    # Gem placeholder size; swap for a sprite later.
    feather_w: int = 7
    feather_h: int = 11
    feather_text_gap: int = 2
    group_gap: int = 5
    best_margin_x: int = 4
    # Red feather in idle: month + day, no year.
    date_format: str = "%m/%d"
    # "+1" HUD popup and world collect "+n": jump up, then vanish.
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
    # Clock digits: bright gold plus a dark stroke so they read on snow and night.
    clock_text: str = "#FFE566"
    clock_stroke: str = "#1A1208"
    hint: str = "#AAAAAA"
    death: str = "#FF6666"
    # Gems: date = mean(red, orange, yellow); hour = mean(green, cyan);
    # minute = blue; second = purple.
    feather_date: str = "#FF8C00"
    feather_hour: str = "#00FF80"
    feather_minute: str = "#3D8BFF"
    feather_second: str = "#C45CFF"
    score_popup: str = "#FFE566"
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
    floaters: FloaterConfig = FloaterConfig()
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
    font_size: int = 13


DEFAULT = GameConfig()
