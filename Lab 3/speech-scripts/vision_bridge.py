"""Lock a camera reading once, when the hand reaches a new card window.

The lower part of the frame is the Pi's hole cards. The upper part is the
board. A window counts only the cards in its own zone:

- hole: exactly two known cards in the lower zone
- flop / turn / river: exactly the new board cards in the upper zone

An Unknown card in that zone resets the count. The same set must repeat for
``frames`` reads. After a window locks, later frames do not change those cards.
"""

from __future__ import annotations

import sys
from pathlib import Path

VISION_DIR = Path(__file__).resolve().parent.parent / "card vision"
if str(VISION_DIR) not in sys.path:
    sys.path.insert(0, str(VISION_DIR))

from stable_read import StableCodes
from zones import assign_zones, check_sample

from poker_player import Card, Phase, Player

_RANK = {
    "A": 14,
    "K": 13,
    "Q": 12,
    "J": 11,
    "10": 10,
    "9": 9,
    "8": 8,
    "7": 7,
    "6": 6,
    "5": 5,
    "4": 4,
    "3": 3,
    "2": 2,
}
_NEED_NEW = {"flop": 3, "turn": 1, "river": 1}


def code_to_card(code: str) -> Card | None:
    text = code.strip()
    if len(text) < 2:
        return None
    suit = text[-1].lower()
    rank = text[:-1].upper()
    if suit not in "shdc" or rank not in _RANK:
        return None
    return Card(_RANK[rank], suit)


def _signature(cards: list[Card]) -> frozenset[str]:
    return frozenset(f"{card.rank}{card.suit}" for card in cards)


class VisionBridge:
    def __init__(self, frames: int = 15) -> None:
        self.stable = StableCodes(frames)
        self._key: str | None = None

    def observe(self, player: Player, detections: list, image_height: int = 720) -> str | None:
        player.refresh_vision_window()
        key = player.vision_window
        if key != self._key:
            self._key = key
            self.stable.reset()
        if key is None:
            return None
        visible = self._zone_cards(detections, image_height, "pi_hole" if key == "hole" else "board")
        if visible is None or not self._qualifies(player, key, visible):
            self.stable.reset()
            return None
        if self.stable.push(_signature(visible)) is None:
            return None
        reply = self._commit(player, key, visible)
        if reply is None:
            self.stable.reset()
            return None
        player.vision_locked.add(key)
        player.vision_window = None
        self._key = None
        self.stable.reset()
        player._append(player.phase, "Pi", reply)
        return reply

    def _zone_cards(self, detections: list, image_height: int, zone_name: str) -> list[Card] | None:
        zones = assign_zones(detections, image_height=image_height)
        group = zones[zone_name]
        if any(item.get("card") == "Unknown" for item in group):
            return None
        return self._visible([item.get("card", "") for item in group])

    def _visible(self, codes: list[str]) -> list[Card] | None:
        cards: list[Card] = []
        for code in codes:
            if code == "Unknown":
                continue
            card = code_to_card(code)
            if card is None:
                return None
            cards.append(card)
        if len(set(cards)) != len(cards):
            return None
        return cards

    def _qualifies(self, player: Player, key: str, visible: list[Card]) -> bool:
        if key == "hole":
            return len(player.hole) == 0 and len(visible) == 2
        need = _NEED_NEW.get(key)
        if need is None or len(player.hole) != 2:
            return False
        seen = set(visible)
        known = set(player.board)
        if not known.issubset(seen):
            return False
        return len(seen - known) == need and len(seen) == len(known) + need

    def _commit(self, player: Player, key: str, visible: list[Card]) -> str | None:
        if key == "hole":
            before = len(player.hole)
            reply = player._set_hole(sorted(visible, key=lambda card: (card.rank, card.suit)))
            if len(player.hole) == 2 and before == 0:
                return reply
            return None
        known = set(player.hole) | set(player.board)
        added = sorted(set(visible) - known, key=lambda card: (card.rank, card.suit))
        if len(added) != _NEED_NEW[key]:
            return None
        before = len(player.board)
        reply = player._set_board(key, added)
        if len(player.board) == before + len(added):
            return reply
        return None


def _seen(code: str, x: int, y: int) -> dict:
    return {"card": code, "center": [x, y]}


def check_bridge() -> None:
    check_sample()
    player = Player()
    player.chips = {"human": 500, "pi": 500}
    player._deal()
    bridge = VisionBridge(frames=3)
    hole = [_seen("Jc", 455, 593), _seen("9c", 643, 605)]
    flicker = [_seen("4c", 455, 593), _seen("9c", 643, 605)]
    assert bridge.observe(player, hole) is None
    assert bridge.observe(player, flicker) is None
    assert bridge.observe(player, hole) is None
    assert bridge.observe(player, hole) is None
    reply = bridge.observe(player, hole)
    assert reply is not None and "jack" in reply.lower() and "nine" in reply.lower()
    assert player.vision_window is None
    assert bridge.observe(player, flicker) is None
    assert {card.rank for card in player.hole} == {11, 9}

    player.acted = {"human": True, "pi": True}
    player.street_in = {"human": 40, "pi": 40}
    flop = [
        _seen("Ah", 300, 270),
        _seen("Kd", 500, 280),
        _seen("2s", 700, 290),
        _seen("Jc", 455, 593),
        _seen("9c", 643, 605),
    ]
    assert bridge.observe(player, flop) is None
    assert bridge.observe(player, flop) is None
    flop_reply = bridge.observe(player, flop)
    assert flop_reply is not None and player.phase is Phase.FLOP
    assert len(player.board) == 3
    changed = [
        _seen("Ah", 300, 270),
        _seen("Kd", 500, 280),
        _seen("3s", 700, 290),
        _seen("Jc", 455, 593),
        _seen("9c", 643, 605),
    ]
    assert bridge.observe(player, changed) is None
    assert len(player.board) == 3
    print("vision bridge ok")


if __name__ == "__main__":
    check_bridge()
