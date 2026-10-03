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
from zones import check_sample

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
# Flop is the first three board cards. Turn and river each add one,
# so the board zone must show 4 cards, then 5.
_NEED_NEW = {"flop": 3, "turn": 1, "river": 1}
_BOARD_TOTAL = {"flop": 3, "turn": 4, "river": 5}


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

    def observe(self, player: Player, zones: dict) -> str | None:
        """Lock the open window from a zone dict. Tests can pass that dict without OpenCV.

        ``zones`` is the ``assign_zones`` result: ``pi_hole`` below the line,
        ``board`` above it. Only the open window's zone is read.
        """
        player.refresh_vision_window()
        key = player.vision_window
        if key != self._key:
            self._key = key
            self.stable.reset()
        if key is None:
            return None
        visible = self._zone_cards(zones, "pi_hole" if key == "hole" else "board")
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

    def _zone_cards(self, zones: dict, zone_name: str) -> list[Card] | None:
        group = zones.get(zone_name) or []
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
        total = _BOARD_TOTAL.get(key)
        need = _NEED_NEW.get(key)
        if total is None or need is None or len(player.hole) != 2:
            return False
        if len(player.board) != total - need or len(visible) != total:
            return False
        seen = set(visible)
        known = set(player.board)
        if not known.issubset(seen):
            return False
        return len(seen - known) == need

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


def _zones(pi_hole: list, board: list) -> dict:
    return {"pi_hole": pi_hole, "board": board}


def _close_street(player: Player) -> None:
    amount = max(player.street_in["human"], player.street_in["pi"])
    player.street_in = {"human": amount, "pi": amount}
    player.acted = {"human": True, "pi": True}


def check_bridge() -> None:
    check_sample()
    player = Player()
    player.chips = {"human": 500, "pi": 500}
    player._deal()
    bridge = VisionBridge(frames=3)
    hole_cards = [_seen("Jc", 455, 593), _seen("9c", 643, 605)]
    # These sit in the board zone. They must not become hole cards.
    upper = [_seen("Ah", 300, 270), _seen("Kd", 500, 280), _seen("2s", 700, 290)]
    hole = _zones(hole_cards, upper)
    flicker = _zones([_seen("4c", 455, 593), _seen("9c", 643, 605)], upper)
    assert bridge.observe(player, hole) is None
    assert bridge.observe(player, flicker) is None
    assert bridge.observe(player, hole) is None
    assert bridge.observe(player, hole) is None
    reply = bridge.observe(player, hole)
    assert reply is not None and "jack" in reply.lower() and "nine" in reply.lower()
    assert player.vision_window is None
    assert {card.rank for card in player.hole} == {11, 9}
    assert player.board == []
    other_hole = _zones([_seen("Qs", 455, 593), _seen("3d", 643, 605)], upper)
    assert bridge.observe(player, other_hole) is None
    assert {card.rank for card in player.hole} == {11, 9}

    _close_street(player)
    # A card that exists only in pi_hole must not join the flop.
    flop = _zones(
        hole_cards + [_seen("Qs", 800, 610)],
        [_seen("Ah", 300, 270), _seen("Kd", 500, 280), _seen("2s", 700, 290)],
    )
    assert bridge.observe(player, flop) is None
    unknown = _zones(hole_cards, [_seen("Ah", 300, 270), _seen("Kd", 500, 280), _seen("Unknown", 700, 290)])
    assert bridge.observe(player, unknown) is None
    assert bridge.observe(player, flop) is None
    assert bridge.observe(player, flop) is None
    flop_reply = bridge.observe(player, flop)
    assert flop_reply is not None and player.phase is Phase.FLOP
    assert {card.rank for card in player.board} == {14, 13, 2}
    assert all(card.rank != 12 for card in player.board)
    changed = _zones(hole_cards, [_seen("Ah", 300, 270), _seen("Kd", 500, 280), _seen("3s", 700, 290)])
    assert bridge.observe(player, changed) is None
    assert {card.rank for card in player.board} == {14, 13, 2}
    assert {card.rank for card in player.hole} == {11, 9}

    _close_street(player)
    turn = _zones(
        [_seen("Qs", 800, 610)],
        [
            _seen("Ah", 300, 270),
            _seen("Kd", 500, 280),
            _seen("2s", 700, 290),
            _seen("7h", 880, 300),
        ],
    )
    assert bridge.observe(player, turn) is None
    assert bridge.observe(player, turn) is None
    turn_reply = bridge.observe(player, turn)
    assert turn_reply is not None and player.phase is Phase.TURN
    assert len(player.board) == 4
    assert {card.rank for card in player.board} == {14, 13, 2, 7}
    replaced = _zones(
        [_seen("Qs", 800, 610)],
        [
            _seen("Ah", 300, 270),
            _seen("Kd", 500, 280),
            _seen("2s", 700, 290),
            _seen("8c", 880, 300),
        ],
    )
    assert bridge.observe(player, replaced) is None
    assert {card.rank for card in player.board} == {14, 13, 2, 7}

    spoken = Player()
    spoken.chips = {"human": 500, "pi": 500}
    spoken._deal()
    heard = spoken.on_heard("your cards are the ace of spades and the king of hearts")
    assert "ace" in heard.lower() and "king" in heard.lower()
    _close_street(spoken)
    heard = spoken.on_heard("flop is the ace of hearts, the king of diamonds, and the two of spades")
    assert spoken.phase is Phase.FLOP
    assert {card.rank for card in spoken.board} == {14, 13, 2}
    quiet = VisionBridge(frames=1)
    camera = _zones(
        [_seen("2c", 400, 600), _seen("3d", 620, 610)],
        [_seen("Qh", 300, 270), _seen("Js", 500, 280), _seen("9d", 700, 290)],
    )
    assert quiet.observe(spoken, camera) is None
    assert {card.rank for card in spoken.hole} == {14, 13}
    assert {card.rank for card in spoken.board} == {14, 13, 2}
    print("vision bridge ok")


if __name__ == "__main__":
    check_bridge()
