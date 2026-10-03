"""Accept a set of card codes only after the same set repeats."""

from __future__ import annotations


class StableCodes:
    """Count consecutive identical code sets. One different frame starts over."""

    def __init__(self, frames: int = 15) -> None:
        if frames < 1:
            raise ValueError("frames must be at least 1")
        self.frames = frames
        self._seen: frozenset[str] | None = None
        self._count = 0

    def reset(self) -> None:
        self._seen = None
        self._count = 0

    def push(self, codes: frozenset[str]) -> frozenset[str] | None:
        if codes != self._seen:
            self._seen = codes
            self._count = 1
        else:
            self._count += 1
        if self._count >= self.frames:
            return codes
        return None
