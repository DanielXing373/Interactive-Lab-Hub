"""Accept a set of card codes only after the same set repeats."""

from __future__ import annotations


class StableCodes:
    """Count consecutive identical code sets.

    A few bad frames are tolerated so brief Unknown flicker does not wipe
    progress. A different valid set still starts over immediately.
    """

    def __init__(self, frames: int = 15, miss_limit: int = 4) -> None:
        if frames < 1:
            raise ValueError("frames must be at least 1")
        self.frames = frames
        self.miss_limit = max(1, miss_limit)
        self._seen: frozenset[str] | None = None
        self._count = 0
        self._misses = 0

    @property
    def count(self) -> int:
        return self._count

    def reset(self) -> None:
        self._seen = None
        self._count = 0
        self._misses = 0

    def miss(self) -> None:
        """Note a non-qualifying frame. Reset only after several in a row."""
        if self._count == 0 and self._seen is None:
            return
        self._misses += 1
        if self._misses >= self.miss_limit:
            self.reset()

    def push(self, codes: frozenset[str]) -> frozenset[str] | None:
        self._misses = 0
        if codes != self._seen:
            self._seen = codes
            self._count = 1
        else:
            self._count += 1
        if self._count >= self.frames:
            return codes
        return None
