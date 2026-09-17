"""Bird AABBs vs pipe solids. Wrap is split first so a seam-crossing bird
is never one inverted box (top < bottom), which would skip real hits.
"""

from typing import List, Sequence, Tuple

Point = Tuple[float, float]
Span = Tuple[float, float]
Hitbox = Tuple[float, float, float, float]  # left, bottom, right, top

_EPS = 1e-7


def wrap_y_spans(y: float, height: float, screen_h: float, wrap: bool) -> List[Span]:
    """Unwrapped [bottom, top] pieces. Each has top >= bottom."""
    if height <= _EPS:
        return []
    if not wrap or y + height <= screen_h + _EPS:
        return [(y, y + height)]
    upper = (y, screen_h)
    lower = (0.0, y + height - screen_h)
    spans = []
    if upper[1] - upper[0] > _EPS:
        spans.append(upper)
    if lower[1] - lower[0] > _EPS:
        spans.append(lower)
    return spans


def bottom_triangle(x: float, width: float, gap_bottom: float) -> Tuple[Point, Point, Point]:
    """Base on the floor, apex at the gap. Empty if the solid has no height."""
    return ((x, 0.0), (x + width, 0.0), (x + width * 0.5, gap_bottom))


def top_triangle(
    x: float, width: float, gap_top: float, screen_h: float
) -> Tuple[Point, Point, Point]:
    """Base on the ceiling, apex at the gap."""
    return ((x, screen_h), (x + width, screen_h), (x + width * 0.5, gap_top))


def _project(points: Sequence[Point], ax: float, ay: float) -> Span:
    dots = [p[0] * ax + p[1] * ay for p in points]
    return (min(dots), max(dots))


def _separated(a: Span, b: Span) -> bool:
    return a[1] < b[0] - _EPS or b[1] < a[0] - _EPS


def aabb_hits_triangle(box: Hitbox, tri: Tuple[Point, Point, Point]) -> bool:
    left, bottom, right, top = box
    if right < left - _EPS or top < bottom - _EPS:
        # Inverted / seam-straddling box. Caller must split wrap first.
        return False
    area2 = abs(
        (tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1])
        - (tri[2][0] - tri[0][0]) * (tri[1][1] - tri[0][1])
    )
    if area2 < _EPS:
        return False

    rect = ((left, bottom), (right, bottom), (right, top), (left, top))
    axes = [(1.0, 0.0), (0.0, 1.0)]
    for i in range(3):
        x0, y0 = tri[i]
        x1, y1 = tri[(i + 1) % 3]
        axes.append((y0 - y1, x1 - x0))

    for ax, ay in axes:
        n2 = ax * ax + ay * ay
        if n2 < _EPS:
            continue
        n = n2 ** 0.5
        axis = (ax / n, ay / n)
        if _separated(_project(rect, *axis), _project(tri, *axis)):
            return False
    return True


def hits_rect_pipe(box: Hitbox, x: float, width: float, gap_bottom: float, gap_top: float) -> bool:
    left, bottom, right, top = box
    if right < left - _EPS or top < bottom - _EPS:
        return False
    if right < x or left > x + width:
        return False
    in_gap = bottom >= gap_bottom and top <= gap_top
    return not in_gap


def hits_triangle_pipe(
    box: Hitbox,
    x: float,
    width: float,
    gap_bottom: float,
    gap_top: float,
    screen_h: float,
    has_bottom: bool = True,
    has_top: bool = True,
) -> bool:
    left, bottom, right, top = box
    if right < left - _EPS or top < bottom - _EPS:
        return False
    if right < x or left > x + width:
        return False
    if has_bottom and gap_bottom > _EPS:
        if aabb_hits_triangle(box, bottom_triangle(x, width, gap_bottom)):
            return True
    if has_top and gap_top < screen_h - _EPS:
        if aabb_hits_triangle(box, top_triangle(x, width, gap_top, screen_h)):
            return True
    return False


def hits_pipe(
    box: Hitbox,
    x: float,
    width: float,
    gap_bottom: float,
    gap_top: float,
    screen_h: float,
    shape: str = "triangle",
    has_bottom: bool = True,
    has_top: bool = True,
) -> bool:
    if shape == "rect":
        if not has_bottom and not has_top:
            return False
        left, bottom, right, top = box
        if right < x or left > x + width:
            return False
        if has_bottom and has_top:
            return hits_rect_pipe(box, x, width, gap_bottom, gap_top)
        if has_bottom and bottom < gap_bottom:
            return True
        if has_top and top > gap_top:
            return True
        return False
    return hits_triangle_pipe(
        box, x, width, gap_bottom, gap_top, screen_h, has_bottom, has_top
    )
