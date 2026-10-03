#!/usr/bin/env python3
"""Texas Hold'em voice state machine. The Pi is the player. The human deals.

Session fields (they survive every hand): small_blind, big_blind, chips.
The phase enum is only where we are in the current hand. Questions about
chips, the board, hole cards, and win rate are self-loops: they answer and
stay in the same phase.

    python poker_player.py --text
    python poker_player.py --check
    python poker_player.py

The microphone and camera run together. After deal, and again when a street
closes, the camera reads until the same cards repeat. That reading is locked
for the street. Pass --no-camera to use the microphone alone.

``alt_personality`` is the switch for a second persona. Both personas use the
same sentences for now. Hole cards and win rate stay truthful either way.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import zlib
from datetime import datetime
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from pathlib import Path

SAMPLE_RATE = 16000
LAB_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAD = LAB_DIR / "models" / "silero_vad.onnx"
DEFAULT_VOICE = LAB_DIR / "voices" / "en_US-lessac-medium.onnx"
TRANSCRIPTS = LAB_DIR / "transcripts"
BET_SILENCE = 1.2
EQUITY_ITERS = 200

STREET = ("preflop", "flop", "turn", "river")
_RANK_NAME = {
    2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "jack", 12: "queen", 13: "king", 14: "ace",
}
_RANK_VALUE = {name: rank for rank, name in _RANK_NAME.items()}
_RANK_VALUE["10"] = 10
_SUIT_NAME = {"s": "spades", "h": "hearts", "d": "diamonds", "c": "clubs"}
_SUIT_VALUE = {name: suit for suit, name in _SUIT_NAME.items()}
for _short, _full in (("spade", "spades"), ("heart", "hearts"), ("diamond", "diamonds"), ("club", "clubs")):
    _SUIT_VALUE[_short] = _SUIT_VALUE[_full]

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_CARD_RE = re.compile(
    r"\b(?P<rank>ace|king|queen|jack|ten|two|three|four|five|six|seven|eight|nine|10|[2-9])"
    r"\s+(?:of\s+)?(?P<suit>spades|hearts|diamonds|clubs|spade|heart|diamond|club)\b"
)
_AMOUNT_RE = re.compile(
    r"\b(?P<num>\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    r"fifty|sixty|seventy|eighty|ninety|hundred)\b"
)


class Phase(Enum):
    IDLE = "idle"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    AWAIT_AMOUNT = "await_amount"
    AWAIT_CONFIRM = "await_confirm"


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    def __str__(self) -> str:
        return f"{_RANK_NAME[self.rank]} of {_SUIT_NAME[self.suit]}"


def _normalize(text: str) -> str:
    cleaned = text.lower().replace("-", " ")
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _straight_high(ranks: list[int]) -> int | None:
    values = set(ranks)
    if 14 in values:
        values.add(1)
    for high in range(14, 4, -1):
        if {high, high - 1, high - 2, high - 3, high - 4} <= values:
            return 5 if high == 5 else high
    return None


def _rank_five(cards: list[Card]) -> tuple:
    ranks = sorted((card.rank for card in cards), reverse=True)
    counts = Counter(ranks)
    groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    pattern = tuple(sorted(counts.values(), reverse=True))
    flush = len({card.suit for card in cards}) == 1
    straight = _straight_high(ranks)
    if flush and straight:
        return (8, straight)
    if pattern == (4, 1):
        return (7, groups[0][0], groups[1][0])
    if pattern == (3, 2):
        return (6, groups[0][0], groups[1][0])
    if flush:
        return (5, *ranks)
    if straight:
        return (4, straight)
    if pattern == (3, 1, 1):
        return (3, groups[0][0], groups[1][0], groups[2][0])
    if pattern == (2, 2, 1):
        pair_a, pair_b = sorted((groups[0][0], groups[1][0]), reverse=True)
        return (2, pair_a, pair_b, groups[2][0])
    if pattern == (2, 1, 1, 1):
        return (1, groups[0][0], groups[1][0], groups[2][0], groups[3][0])
    return (0, *ranks)


def best_rank(cards: list[Card]) -> tuple:
    return max(_rank_five(list(five)) for five in combinations(cards, 5))


def _deck() -> list[Card]:
    return [Card(rank, suit) for rank in range(2, 15) for suit in "shdc"]


def equity(hero: list[Card], board: list[Card], iterations: int = EQUITY_ITERS, seed: int = 0) -> float:
    """Win rate of hero against one random hand. Ties count as half a win."""
    rng = random.Random(seed)
    used = set(hero + board)
    deck = [card for card in _deck() if card not in used]
    need = 2 + (5 - len(board))
    wins = ties = 0
    for _ in range(iterations):
        draw = rng.sample(deck, need)
        opponent = draw[:2]
        full = board + draw[2:]
        hero_rank = best_rank(hero + full)
        opp_rank = best_rank(opponent + full)
        if hero_rank > opp_rank:
            wins += 1
        elif hero_rank == opp_rank:
            ties += 1
    return (wins + 0.5 * ties) / iterations


def extract_cards(text: str) -> list[Card]:
    found = []
    for match in _CARD_RE.finditer(text):
        found.append(Card(_RANK_VALUE[match.group("rank")], _SUIT_VALUE[match.group("suit")]))
    return found


def _word_amount(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    if token in _ONES:
        return _ONES[token]
    if token in _TENS:
        return _TENS[token]
    if token == "hundred":
        return 100
    return None


def extract_amounts(text: str) -> list[int]:
    """Chip amounts left after card phrases are removed."""
    stripped = _CARD_RE.sub(" ", text)
    amounts = []
    tokens = _AMOUNT_RE.findall(stripped)
    index = 0
    while index < len(tokens):
        value = _word_amount(tokens[index])
        if value is None:
            index += 1
            continue
        if index + 1 < len(tokens) and tokens[index + 1] == "hundred" and value < 10:
            value *= 100
            index += 1
        elif (
            index + 2 < len(tokens)
            and tokens[index + 1] == "hundred"
            and _word_amount(tokens[index + 2]) in range(1, 100)
        ):
            value = value * 100 + _word_amount(tokens[index + 2])
            index += 2
        amounts.append(value)
        index += 1
    return amounts


def bound_amount(text: str) -> int | None | tuple[int, ...]:
    """The number attached to this utterance.

    A number after ``to`` wins. One leftover number is that amount.
    Two or more leftovers are returned as a tuple so the caller can ask.
    """
    stripped = _CARD_RE.sub(" ", text)
    directed = re.search(r"\bto\s+([a-z0-9]+)\b", stripped)
    if directed:
        value = _word_amount(directed.group(1))
        if value is not None:
            return value
    amounts = extract_amounts(text)
    if not amounts:
        return None
    if len(amounts) == 1:
        return amounts[0]
    return tuple(amounts)


def _looks_like_question(text: str) -> bool:
    return bool(
        re.search(r"\b(what|whats|how|why|where|status)\b", text)
        or re.search(r"\b(odds|equity|chance|waiting|next)\b", text)
        or "win rate" in text
        or "your turn" in text
        or "my turn" in text
    )


def _verbs(text: str) -> list[str]:
    return [verb for verb in ("fold", "check", "call", "raise", "bet") if re.search(rf"\b{verb}\b", text)]


_REPEAT_EN = re.compile(
    r"\b(repeat|pardon)\b|say (that|it) again|come again|what did you say|"
    r"didn t (hear|catch)|did not (hear|catch)|one more time|i missed that"
)
_REPEAT_ZH = ("没听清", "再说一遍", "再来一遍", "再讲一遍", "重复一下", "重复一遍", "重复")
_ECHO_STOP = {
    "a", "an", "the", "and", "to", "of", "is", "are", "am", "i", "you", "me", "my",
    "we", "it", "for", "in", "on", "or",
}


def _is_repeat(raw: str) -> bool:
    if any(phrase in raw for phrase in _REPEAT_ZH):
        return True
    return bool(_REPEAT_EN.search(_normalize(raw)))


def _is_echo(heard: str, spoken: str | None) -> bool:
    """True when the mic likely caught the Pi's own last line.

    Short commands like ``I have 1500`` must not match a longer reply that
    merely shares a few words. Real echo is a long noisy paraphrase of the
    previous TTS line.
    """
    if not spoken:
        return False
    a = _normalize(heard)
    b = _normalize(spoken)
    if not a or not b:
        return False
    if len(a) >= 20 and (a in b or b in a):
        return True
    left = set(a.split()) - _ECHO_STOP
    right = set(b.split()) - _ECHO_STOP
    if len(left) < 4:
        return False
    overlap = len(left & right)
    if overlap / len(left) < 0.7:
        return False
    if len(right) >= 4 and overlap / len(right) < 0.35:
        return False
    return True

class Player:
    """One sitting: blinds and stacks outside the hand, phase inside it."""

    def __init__(self, alt_personality: bool = False, record_dir: Path | None = None) -> None:
        self.alt_personality = alt_personality
        self.record_dir = record_dir
        self.small_blind = 10
        self.big_blind = 20
        self.chips: dict[str, int | None] = {"human": 500, "pi": 500}
        self.phase = Phase.IDLE
        self.resume = Phase.IDLE
        self.pending: dict | None = None
        self.lines: list[str] = []
        self.hands: list[list[str]] = []
        self.hand_start: int | None = None
        self.hand_count = 0
        self.last_spoken: str | None = None
        self.last_transcript: Path | None = None
        self.vision_window: str | None = None
        self.vision_locked: set[str] = set()
        self._clear_cards()
        if record_dir is not None:
            record_dir.mkdir(parents=True, exist_ok=True)
            self.hand_count = len(list(record_dir.glob("hand_*.txt")))
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with (record_dir / "session.txt").open("a", encoding="utf-8") as handle:
                handle.write(f"\n===== sitting {stamp} =====\n")

    def _clear_cards(self) -> None:
        self.pot = 0
        self.hole: list[Card] = []
        self.board: list[Card] = []
        self.street_in = {"human": 0, "pi": 0}
        self.acted = {"human": False, "pi": False}
        self.vision_window = None
        self.vision_locked = set()

    def refresh_vision_window(self) -> None:
        """Open a one-shot camera read when the hand is waiting for cards."""
        key = None
        if self.phase is Phase.PREFLOP and len(self.hole) != 2:
            key = "hole"
        elif len(self.hole) == 2 and self._betting_closed():
            key = {"preflop": "flop", "flop": "turn", "turn": "river"}.get(self.phase.value)
        if key is None or key in self.vision_locked:
            self.vision_window = None
            return
        self.vision_window = key

    def greeting(self) -> str:
        line = self._say(
            f"Blinds are {self.small_blind} and {self.big_blind}. "
            "We each have 500 chips. Say deal."
        )
        self._append(Phase.IDLE, "Pi", line)
        return line

    def status(self) -> str:
        return (
            f"phase={self.phase.value} sb={self.small_blind} bb={self.big_blind} "
            f"you={self.chips['human']} pi={self.chips['pi']} pot={self.pot} "
            f"street_you={self.street_in['human']} street_pi={self.street_in['pi']} "
            f"hole={len(self.hole)} board={len(self.board)}"
        )

    def on_heard(self, raw: str) -> str:
        text = raw.strip()
        if not text:
            return ""
        if _is_echo(text, self.last_spoken):
            return ""
        user_phase = self.phase
        if _is_repeat(text):
            reply = self.last_spoken or "I have not said anything yet."
        else:
            reply = self._respond(text)
            if reply.startswith("New hand."):
                self.hand_start = len(self.lines)
        self._append(user_phase, "You", text)
        self._append(self.phase, "Pi", reply)
        if user_phase is not Phase.IDLE and self.phase is Phase.IDLE:
            self._save_hand()
        return reply

    def _respond(self, raw: str) -> str:
        text = _normalize(raw)
        if not text:
            return self._say("I didn't catch that.")
        if self.phase is Phase.AWAIT_CONFIRM:
            return self._on_confirm(text)
        if self.phase is Phase.AWAIT_AMOUNT:
            return self._on_amount(text)
        query = self._query(text)
        if query:
            return query
        if self.phase is Phase.SHOWDOWN:
            return self._on_showdown(text)
        if self.phase is Phase.IDLE:
            return self._on_idle(text)
        return self._on_street(text)

    def _append(self, phase: Phase, speaker: str, text: str) -> None:
        line = f"[{phase.value}] {speaker}: {text}"
        self.lines.append(line)
        if speaker == "Pi":
            self.last_spoken = text
        if self.record_dir is None:
            return
        with (self.record_dir / "session.txt").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _save_hand(self) -> None:
        if self.hand_start is None:
            return
        chunk = self.lines[self.hand_start:]
        self.hands.append(chunk)
        self.hand_start = None
        self.hand_count += 1
        if self.record_dir is None:
            return
        path = self.record_dir / f"hand_{self.hand_count:03d}.txt"
        path.write_text("\n".join(chunk) + "\n", encoding="utf-8")
        self.last_transcript = path

    def _say(self, text: str) -> str:
        # Second persona plugs in here. The bool is the only switch.
        books = {False: text, True: text}
        return books[self.alt_personality]

    def _live(self) -> Phase:
        if self.phase in (Phase.AWAIT_AMOUNT, Phase.AWAIT_CONFIRM):
            return self.resume
        return self.phase

    def _query(self, text: str) -> str | None:
        if not _looks_like_question(text):
            return None
        if any(
            phrase in text
            for phrase in (
                "wait", "waiting", "next", "status", "where are we",
                "what now", "what should", "your turn", "my turn", "doing",
            )
        ):
            return self._say(self._waiting_line())
        if any(word in text for word in ("win rate", "equity", "odds", "chance")):
            return self._say(self._equity_line())
        if any(word in text for word in ("board", "table", "community")):
            return self._say(self._board_line())
        if "your hand" in text or ("card" in text and "you" in text):
            return self._say(self._hole_line())
        if re.search(r"\bpot\b", text):
            return self._say(f"The pot is {self.pot}.")
        if re.search(r"\b(my stack|do i have|chips do i)\b", text) or ("i have" in text and "chip" in text):
            return self._say(self._chips_line("human"))
        if "chip" in text or "stack" in text:
            return self._say(self._chips_line("pi"))
        return self._say(
            "Ask what I am waiting for, or about chips, the board, my cards, or my win rate."
        )

    def _waiting_line(self) -> str:
        """Plain-English answer for 'what are you waiting for'."""
        if self.phase is Phase.AWAIT_AMOUNT:
            return "I still need the bet amount."
        if self.phase is Phase.AWAIT_CONFIRM:
            return "Say one of those amounts again, or say no."
        phase = self._live()
        if phase is Phase.IDLE:
            if self.chips["human"] is None or self.chips["pi"] is None:
                return "Tell me both stacks, then say deal."
            return "Say deal when you are ready."
        if phase is Phase.SHOWDOWN:
            return "Showdown. Tell me who won: you, me, or split."
        if len(self.hole) != 2:
            return "I am waiting for my two hole cards. Take your time."
        if self._betting_closed():
            if phase is Phase.RIVER:
                return "This street is closed. Tell me who won after showdown starts."
            nxt = {"preflop": "flop", "flop": "turn", "turn": "river"}[phase.value]
            return f"I am waiting for the {nxt}. Take your time."
        if self._pi_should_act():
            return "It is my turn to act."
        gap = self.street_in["pi"] - self.street_in["human"]
        street = phase.value
        if gap > 0:
            return f"We are on the {street}. It is {gap} to call. Your action."
        return f"We are on the {street}. Your action."

    def _chips_line(self, who: str) -> str:
        stack = self.chips[who]
        if stack is None:
            return "Tell me both stacks first."
        phase = self._live()
        name = "I have" if who == "pi" else "You have"
        if phase is Phase.IDLE:
            return f"{name} {stack} chips. Blinds are {self.small_blind} and {self.big_blind}."
        if stack == 0:
            subject = "I am" if who == "pi" else "You are"
            return f"{subject} all in. The pot is {self.pot}."
        return f"{name} {stack} chips. The pot is {self.pot}."

    def _board_line(self) -> str:
        if not self.board:
            return "There are no community cards yet."
        listed = ", ".join(str(card) for card in self.board)
        return f"The board is {listed}."

    def _hole_line(self) -> str:
        if len(self.hole) != 2:
            return "You have not told me my cards."
        return f"I have {self.hole[0]} and {self.hole[1]}."

    def _equity_line(self) -> str:
        percent = self.equity_percent()
        if percent is None:
            return "Tell me my cards before I can estimate."
        return f"About {percent} percent against a random hand."

    def equity_percent(self) -> int | None:
        if len(self.hole) != 2:
            return None
        key = " ".join(f"{card.rank}{card.suit}" for card in self.hole + self.board)
        seed = zlib.adler32(key.encode())
        return round(100 * equity(self.hole, self.board, EQUITY_ITERS, seed))

    def _on_idle(self, text: str) -> str:
        if _verbs(text):
            return self._say("There is no hand. Say deal to start.")
        blinds = self._parse_blinds(text)
        if blinds is not None:
            return blinds
        stacks = self._parse_stacks(text)
        if stacks is not None:
            return stacks
        if re.search(r"\b(deal|new hand)\b", text):
            return self._deal()
        return self._say("Say deal.")

    def _parse_blinds(self, text: str) -> str | None:
        if "blind" not in text:
            return None
        if self.phase is not Phase.IDLE and self._live() is not Phase.IDLE:
            return self._say("Finish this hand before changing the blinds.")
        amounts = extract_amounts(text)
        if len(amounts) < 2:
            return self._say("Tell me the small blind and the big blind.")
        small, big = amounts[0], amounts[1]
        if small <= 0 or big <= small:
            return self._say("The big blind has to be larger than the small blind.")
        self.small_blind = small
        self.big_blind = big
        return self._say(f"Blinds are {small} and {big}.")

    def _parse_stacks(self, text: str) -> str | None:
        cards = extract_cards(text)
        if cards:
            return None
        amount = bound_amount(text)
        looks_stack = "stack" in text or re.search(r"\b(your stack|you have|my stack|i have)\b", text)
        if self.phase is not Phase.IDLE:
            if looks_stack and (isinstance(amount, int) or "stack" in text):
                return self._say("Stacks are already in this hand.")
            return None
        if isinstance(amount, tuple) or not isinstance(amount, int):
            if looks_stack:
                return self._say("Tell me one stack size.")
            return None
        if re.search(r"\b(your stack|you have)\b", text):
            who = "pi"
        elif re.search(r"\b(my stack|i have)\b", text):
            who = "human"
        else:
            return None
        if amount < self.big_blind:
            return self._say("A stack has to cover at least the big blind.")
        self.chips[who] = amount
        if who == "pi":
            return self._say(f"I have {amount} chips.")
        return self._say(f"You have {amount} chips.")

    def _deal(self) -> str:
        if self.chips["human"] is None or self.chips["pi"] is None:
            return self._say("Tell me both stacks first.")
        if self.chips["human"] < self.small_blind or self.chips["pi"] < self.big_blind:
            return self._say("A stack cannot post its blind.")
        self._clear_cards()
        self.chips["human"] -= self.small_blind
        self.chips["pi"] -= self.big_blind
        self.street_in = {"human": self.small_blind, "pi": self.big_blind}
        self.pot = self.small_blind + self.big_blind
        self.acted = {"human": False, "pi": False}
        self.phase = Phase.PREFLOP
        return self._say(
            f"New hand. You post {self.small_blind}. I post {self.big_blind}. "
            "I am waiting for my two hole cards. Take your time."
        )

    def _on_street(self, text: str) -> str:
        if re.search(r"\b(deal|new hand)\b", text) and "card" not in text:
            return self._say("Finish this hand before the next deal.")
        if "blind" in text:
            return self._say("Finish this hand before changing the blinds.")
        stacks = self._parse_stacks(text)
        if stacks is not None:
            return stacks
        hole = self._maybe_hole(text)
        if hole is not None:
            return hole
        board = self._maybe_board(text)
        if board is not None:
            return board
        verbs = _verbs(text)
        if "all in" in text and not verbs:
            verbs = ["raise"] if self.street_in["pi"] > self.street_in["human"] else ["bet"]
        if len(verbs) > 1:
            return self._say("Say one action: fold, check, call, bet, or raise.")
        if not verbs:
            if len(self.hole) != 2 or self._betting_closed():
                return self._say(self._waiting_line())
            if extract_cards(text):
                return self._say("Tell me which street those cards belong to.")
            return self._say("Say fold, check, call, bet, or raise. Or ask what I am waiting for.")
        if len(self.hole) != 2:
            return self._say("I am waiting for my two hole cards before anyone acts.")
        if self._betting_closed():
            return self._say(self._closed_hint())
        return self._human_action(verbs[0], text)
    def _maybe_hole(self, text: str) -> str | None:
        if not re.search(r"\b(your cards|you have|your hand)\b", text):
            return None
        cards = extract_cards(text)
        if not cards:
            return None
        if len(cards) != 2:
            return self._say("Tell me exactly two cards.")
        return self._set_hole(cards)

    def _set_hole(self, cards: list[Card]) -> str:
        if len(set(cards)) != 2:
            return self._say("A card cannot appear twice.")
        if any(card in self.board for card in cards):
            return self._say("That card is already on the board.")
        self.hole = cards
        spoken = f"I have {cards[0]} and {cards[1]}."
        if self.acted["human"] or self.acted["pi"]:
            return self._say(f"{spoken} The pot stays {self.pot}.")
        return self._say(f"{spoken} Your action.")

    def _maybe_board(self, text: str) -> str | None:
        street = None
        for name in ("flop", "turn", "river", "board"):
            if re.search(rf"\b{name} is\b", text):
                street = name
                break
        if street is None:
            return None
        cards = extract_cards(text)
        if street == "board":
            street = {3: "flop", 4: "turn", 5: "river"}.get(len(cards), "board")
        return self._set_board(street, cards)

    def _set_board(self, street: str, cards: list[Card]) -> str:
        if len(self.hole) != 2:
            return self._say("Tell me my cards first.")
        if not self._betting_closed():
            return self._say("Finish the betting before the next card.")
        expected = {"flop": 3, "turn": 1, "river": 1}.get(street)
        needed = {"flop": Phase.PREFLOP, "turn": Phase.FLOP, "river": Phase.TURN}.get(street)
        if expected is None or needed is None:
            return self._say("Tell me the flop, the turn, or the river.")
        if self.phase is not needed:
            return self._say(f"The {street} does not come now.")
        if len(cards) != expected:
            noun = "three cards" if expected == 3 else "one card"
            return self._say(f"The {street} needs {noun}.")
        if len(set(cards)) != len(cards) or any(card in self.hole or card in self.board for card in cards):
            return self._say("That card is already out.")
        self.board.extend(cards)
        self.phase = {"flop": Phase.FLOP, "turn": Phase.TURN, "river": Phase.RIVER}[street]
        self.street_in = {"human": 0, "pi": 0}
        self.acted = {"human": False, "pi": False}
        listed = ", ".join(str(card) for card in self.board)
        lead = f"The board is {listed}."
        if self.chips["human"] == 0 or self.chips["pi"] == 0:
            if self.phase is Phase.RIVER:
                self.phase = Phase.SHOWDOWN
                return self._say(f"{lead} Showdown. Tell me who won.")
            nxt = {Phase.FLOP: "turn", Phase.TURN: "river"}[self.phase]
            return self._say(f"{lead} I am waiting for the {nxt}. Take your time.")
        return self._finish(lead)
    def _human_action(self, verb: str, text: str) -> str:
        if len(self.hole) != 2:
            return self._say("Tell me my cards before I act.")
        amount = bound_amount(text)
        if verb == "fold":
            return self._human_fold()
        if verb == "check":
            if isinstance(amount, (int, tuple)):
                return self._say("Say check with no amount.")
            if self.street_in["human"] != self.street_in["pi"]:
                gap = self.street_in["pi"] - self.street_in["human"]
                return self._say(f"You cannot check. It is {gap} to call.")
            self._commit("human", self.street_in["human"])
            return self._finish("You check.")
        if verb == "call":
            gap = self.street_in["pi"] - self.street_in["human"]
            if gap <= 0:
                return self._say("There is nothing to call.")
            if isinstance(amount, tuple):
                return self._hold_confirm("call", amount)
            if isinstance(amount, int) and amount != gap and amount != self.street_in["pi"]:
                return self._say(f"It is {gap} to call.")
            target = min(self.street_in["pi"], self.street_in["human"] + self.chips["human"])
            self._commit("human", target)
            spoken = "You call all in." if self.chips["human"] == 0 else "You call."
            return self._finish(spoken)
        if verb == "bet":
            if self.street_in["pi"] != 0 or self.street_in["human"] != 0:
                return self._say("There is already a bet. Say call, or raise to an amount.")
            if isinstance(amount, tuple):
                return self._hold_confirm("bet", amount)
            if amount is None:
                return self._hold_amount("bet")
            return self._bet_or_raise("bet", amount)
        if isinstance(amount, tuple):
            return self._hold_confirm("raise", amount)
        if amount is None:
            return self._hold_amount("raise")
        return self._bet_or_raise("raise", amount)

    def _bet_or_raise(self, verb: str, amount: int) -> str:
        if verb == "bet":
            minimum = self.big_blind
            if amount < minimum and amount < self.chips["human"]:
                return self._say(f"The minimum bet is {minimum}.")
            target = min(amount, self.chips["human"])
            self._commit("human", target)
            spoken = "You bet all in." if self.chips["human"] == 0 else f"You bet {target}."
            return self._finish(spoken)
        if self.street_in["human"] == 0 and self.street_in["pi"] == 0:
            return self._say("There is no bet to raise. Say bet and an amount.")
        minimum = self.street_in["pi"] + self.big_blind
        short = self.street_in["human"] + self.chips["human"]
        if amount < minimum and amount < short:
            return self._say(f"A raise must be to at least {minimum}.")
        if amount <= self.street_in["human"]:
            return self._say(f"A raise has to be more than {self.street_in['human']}.")
        target = min(amount, short)
        self._commit("human", target)
        spoken = "You raise all in." if self.chips["human"] == 0 else f"You raise to {target}."
        return self._finish(spoken)

    def _hold_amount(self, verb: str) -> str:
        self.resume = self.phase
        self.pending = {"verb": verb}
        self.phase = Phase.AWAIT_AMOUNT
        if verb == "bet":
            return self._say("Bet how many?")
        return self._say("Raise to how many?")

    def _hold_confirm(self, verb: str, options: tuple[int, ...]) -> str:
        self.resume = self.phase
        self.pending = {"verb": verb, "options": options}
        self.phase = Phase.AWAIT_CONFIRM
        left, right = options[0], options[-1]
        return self._say(f"Do you mean {left} or {right}? Say the amount again.")

    def _on_amount(self, text: str) -> str:
        query = self._query(text)
        if query:
            return self._say(f"{query} I still need the amount.")
        if re.search(r"\bfold\b", text):
            self.phase = self.resume
            self.pending = None
            return self._human_fold()
        verbs = _verbs(text)
        amount = bound_amount(text)
        if isinstance(amount, tuple):
            return self._hold_confirm(self.pending["verb"], amount)
        if not isinstance(amount, int):
            return self._say("Say one number.")
        verb = verbs[0] if verbs else self.pending["verb"]
        self.phase = self.resume
        self.pending = None
        return self._human_action(verb, f"{verb} {amount}")

    def _on_confirm(self, text: str) -> str:
        query = self._query(text)
        if query:
            return self._say(f"{query} Say the amount again.")
        if re.search(r"\b(no|cancel|fold)\b", text) and bound_amount(text) is None:
            self.phase = self.resume
            self.pending = None
            if re.search(r"\bfold\b", text):
                return self._human_fold()
            return self._say("Cancelled. Say the action again.")
        amount = bound_amount(text)
        if not isinstance(amount, int):
            return self._say("Say one of those amounts.")
        verb = self.pending["verb"]
        self.phase = self.resume
        self.pending = None
        return self._human_action(verb, f"{verb} to {amount}" if verb == "raise" else f"{verb} {amount}")

    def _human_fold(self) -> str:
        won = self.pot
        self.chips["pi"] += won
        self.pot = 0
        self._end_hand()
        return self._say(f"You fold. I take the pot of {won}.")

    def _pi_fold(self) -> str:
        won = self.pot
        self.chips["human"] += won
        self.pot = 0
        self._end_hand()
        return f"I fold. You take the pot of {won}."

    def _end_hand(self) -> None:
        self._clear_cards()
        self.pending = None
        self.phase = Phase.IDLE

    def _commit(self, who: str, target: int) -> None:
        other = "pi" if who == "human" else "human"
        current = self.street_in[who]
        delta = target - current
        if delta < 0 or delta > self.chips[who]:
            raise RuntimeError(f"bad commit {who} {current} -> {target}")
        self.chips[who] -= delta
        self.pot += delta
        self.street_in[who] = target
        self.acted[who] = True
        if target > self.street_in[other]:
            self.acted[other] = False

    def _pi_should_act(self) -> bool:
        if self.phase.value not in STREET or len(self.hole) != 2 or self.chips["pi"] == 0:
            return False
        if self.street_in["human"] > self.street_in["pi"]:
            return True
        if self.chips["human"] == 0:
            return False
        if self.acted["pi"] or self.street_in["human"] != self.street_in["pi"]:
            return False
        if self.phase is Phase.PREFLOP:
            return self.acted["human"]
        return not self.acted["human"]

    def _betting_closed(self) -> bool:
        if self.phase.value not in STREET:
            return False
        if self._pi_should_act():
            return False
        if self.chips["human"] == 0 or self.chips["pi"] == 0:
            return self.street_in["human"] <= self.street_in["pi"] or self.chips["pi"] == 0
        if self.phase is not Phase.PREFLOP and not self.acted["human"]:
            return False
        return self.acted["human"] and self.acted["pi"] and self.street_in["human"] == self.street_in["pi"]

    def _closed_hint(self) -> str:
        if self.phase is Phase.RIVER:
            return "Showdown is next. Say who won after the river action is done."
        nxt = {"preflop": "flop", "flop": "turn", "turn": "river"}[self.phase.value]
        return f"This street is closed. I am waiting for the {nxt}."

    def _finish(self, lead: str) -> str:
        parts = [lead]
        if self.phase is Phase.IDLE:
            return self._say(lead)
        if self._pi_should_act():
            parts.append(self._pi_act())
        if self.phase is Phase.IDLE:
            return self._say(" ".join(parts))
        tail = self._closed_tail()
        if tail:
            parts.append(tail)
        return self._say(" ".join(parts))

    def _pi_act(self) -> str:
        percent = self.equity_percent()
        assert percent is not None
        chance = percent / 100
        gap = self.street_in["human"] - self.street_in["pi"]
        stack = self.chips["pi"]
        if gap > 0 and gap >= stack:
            if chance < 0.45:
                return self._pi_fold()
            self._commit("pi", self.street_in["pi"] + stack)
            return "I call all in."
        if gap > 0 and chance < 0.40:
            return self._pi_fold()
        if gap > 0 and chance < 0.65:
            self._commit("pi", self.street_in["human"])
            return "I call."
        if gap > 0:
            return self._pi_raise_or_call(chance, stack)
        # Already matched. An unopened street can be bet. A matched bet can only be checked or raised.
        if self.street_in["pi"] == 0:
            if chance < 0.50 or stack == 0:
                self._commit("pi", 0)
                return "I check."
            amount = min(max(self.big_blind, self.pot // 2), stack)
            self._commit("pi", amount)
            if self.chips["pi"] == 0:
                return f"I bet all in, {amount}."
            return f"I bet {amount}."
        if chance < 0.65:
            self._commit("pi", self.street_in["pi"])
            return "I check."
        return self._pi_raise_or_call(chance, stack)

    def _pi_raise_or_call(self, chance: float, stack: int) -> str:
        extra = max(self.big_blind, self.pot // 2)
        target = min(self.street_in["human"] + extra, self.street_in["pi"] + stack)
        minimum = max(self.street_in["human"], self.street_in["pi"]) + self.big_blind
        if target < minimum or target <= self.street_in["pi"]:
            if self.street_in["human"] > self.street_in["pi"]:
                self._commit("pi", min(self.street_in["human"], self.street_in["pi"] + stack))
                return "I call all in." if self.chips["pi"] == 0 else "I call."
            self._commit("pi", self.street_in["pi"])
            return "I check."
        self._commit("pi", target)
        if self.chips["pi"] == 0:
            return f"I raise all in to {target}."
        return f"I raise to {target}."

    def _closed_tail(self) -> str:
        if not self._betting_closed():
            return ""
        if self.phase is Phase.RIVER:
            self.phase = Phase.SHOWDOWN
            return "Showdown. Tell me who won."
        nxt = {"preflop": "flop", "flop": "turn", "turn": "river"}[self.phase.value]
        return f"I am waiting for the {nxt}. Take your time."

    def _on_showdown(self, text: str) -> str:
        if re.search(r"\b(you win|you won)\b", text):
            return self._award("pi")
        if re.search(r"\b(i win|i won)\b", text):
            return self._award("human")
        if re.search(r"\b(split|tie|chop)\b", text):
            return self._split()
        if re.search(r"\b(deal|new hand)\b", text):
            return self._say("Tell me who won before the next deal.")
        return self._say("Tell me who won: you, me, or split.")

    def _award(self, who: str) -> str:
        won = self.pot
        self.chips[who] += won
        self.pot = 0
        self._end_hand()
        if who == "pi":
            return self._say(f"I take the pot of {won}.")
        return self._say(f"You take the pot of {won}.")

    def _split(self) -> str:
        human_share = self.pot // 2 + self.pot % 2
        pi_share = self.pot // 2
        self.chips["human"] += human_share
        self.chips["pi"] += pi_share
        self.pot = 0
        self._end_hand()
        odd = " You take the odd chip." if human_share != pi_share else ""
        return self._say(f"Split. You take {human_share}. I take {pi_share}.{odd}")

    def _known_cards(self) -> set[Card]:
        return set(self.hole + self.board)


def _check_evaluator() -> None:
    def card(text: str) -> Card:
        return extract_cards(text)[0]

    wheel = [card(c) for c in ("ace of spades", "two of hearts", "three of clubs", "four of diamonds", "five of spades")]
    six_high = [card(c) for c in ("two of spades", "three of hearts", "four of clubs", "five of diamonds", "six of spades")]
    assert best_rank(six_high) > best_rank(wheel)
    royal = [card(c) for c in ("ace of spades", "king of spades", "queen of spades", "jack of spades", "ten of spades")]
    quads = [card(c) for c in ("nine of clubs", "nine of diamonds", "nine of hearts", "nine of spades", "two of clubs")]
    assert best_rank(royal) > best_rank(quads)
    aces = [card(c) for c in ("ace of hearts", "ace of clubs", "two of diamonds", "three of spades", "four of hearts")]
    kings = [card(c) for c in ("king of hearts", "king of clubs", "ace of diamonds", "queen of spades", "jack of hearts")]
    assert best_rank(aces) > best_rank(kings)
    assert bound_amount("i raise your 20 to 50") == 50
    assert bound_amount("i bet 40 and 50") == (40, 50)
    assert extract_amounts("your cards are the ten of spades and the seven of hearts") == []
    odd = Player()
    odd.chips = {"human": 0, "pi": 0}
    odd.pot = 31
    assert odd._split() == "Split. You take 16. I take 15. You take the odd chip."
    assert odd.chips == {"human": 16, "pi": 15}


def _play(lines: list[str], alt_personality: bool = False) -> list[str]:
    player = Player(alt_personality=alt_personality)
    return [player.on_heard(line) for line in lines]


def _expect(name: str, lines: list[str], replies: list[str], alt_personality: bool = False) -> None:
    actual = _play(lines, alt_personality)
    if actual != replies:
        details = "\n".join(
            f"  {heard!r}\n    expected: {want}\n    actual:   {got}"
            for heard, want, got in zip(lines, replies, actual)
            if want != got
        )
        raise AssertionError(f"{name}\n{details}")


DEAL_LINE = (
    "New hand. You post 10. I post 20. "
    "I am waiting for my two hole cards. Take your time."
)
WAIT_FLOP = "I am waiting for the flop. Take your time."
WAIT_TURN = "I am waiting for the turn. Take your time."
WAIT_RIVER = "I am waiting for the river. Take your time."


def _check_dialogues() -> None:
    same = [
        "you have 1500",
        "I have 1500",
        "deal",
        "your cards are the ace of spades and the king of hearts",
        "what cards do you have",
    ]
    if _play(same, False) != _play(same, True):
        raise AssertionError("alt personality changed a line")

    _expect("setup and idle questions", [
        "how many chips do you have",
        "what is on the board",
        "what cards do you have",
        "what is your win rate",
        "I fold",
        "blinds are 10 and 20",
        "you have 1500",
        "I have 1500",
        "how many chips do you have",
        "how many chips do I have",
    ], [
        "I have 500 chips. Blinds are 10 and 20.",
        "There are no community cards yet.",
        "You have not told me my cards.",
        "Tell me my cards before I can estimate.",
        "There is no hand. Say deal to start.",
        "Blinds are 10 and 20.",
        "I have 1500 chips.",
        "You have 1500 chips.",
        "I have 1500 chips. Blinds are 10 and 20.",
        "You have 1500 chips. Blinds are 10 and 20.",
    ])

    _expect("bad blinds and stacks", [
        "blinds are 20 and 10",
        "blinds are five",
        "you have 5",
        "you have 1500",
        "deal",
    ], [
        "The big blind has to be larger than the small blind.",
        "Tell me the small blind and the big blind.",
        "A stack has to cover at least the big blind.",
        "I have 1500 chips.",
        DEAL_LINE,
    ])

    player = Player()
    script = [
        "you have 1500",
        "I have 1500",
        "deal",
        "your cards are the ten of spades and the seven of hearts",
        "what is the pot",
        "how many chips do you have if the bet is 50",
        "I check",
        "I raise your 20 to 50",
    ]
    replies = [player.on_heard(line) for line in script]
    assert replies[2] == DEAL_LINE
    assert replies[3] == "I have ten of spades and seven of hearts. Your action."
    assert replies[4] == "The pot is 30."
    assert replies[5] == "I have 1480 chips. The pot is 30."
    assert replies[6] == "You cannot check. It is 10 to call."
    assert replies[7].startswith("You raise to 50.")
    assert player.street_in["human"] == 50
    assert player.chips["human"] == 1450

    waiting = Player()
    for line in ("you have 1500", "I have 1500", "deal"):
        waiting.on_heard(line)
    # Echo of the deal line must not steal the turn.
    assert waiting.on_heard(
        "New hand. You post 10. I post 20. Tell me my cards."
    ) == ""
    assert waiting.phase is Phase.PREFLOP
    assert waiting.hole == []
    assert waiting.on_heard("what are you waiting for") == (
        "I am waiting for my two hole cards. Take your time."
    )
    assert waiting.on_heard("I check") == (
        "I am waiting for my two hole cards before anyone acts."
    )
    # Mid-hand "you have ..." without real cards is not a stack command.
    assert waiting.on_heard("You have not told me my cards.") == (
        "I am waiting for my two hole cards. Take your time."
    )

    _expect("raise needs a number, and a question does not spend chips", [
        "you have 1500",
        "I have 1500",
        "deal",
        "your cards are the ace of clubs and the ace of diamonds",
        "I raise",
        "what cards do you have",
        "how many chips do you have",
        "fifty",
    ], [
        "I have 1500 chips.",
        "You have 1500 chips.",
        DEAL_LINE,
        "I have ace of clubs and ace of diamonds. Your action.",
        "Raise to how many?",
        "I have ace of clubs and ace of diamonds. I still need the amount.",
        "I have 1480 chips. The pot is 30. I still need the amount.",
        "You raise to 50. I raise to 85.",
    ])

    _expect("two amounts wait, to-binds the number after to", [
        "you have 1500",
        "I have 1500",
        "deal",
        "your cards are the ace of clubs and the king of diamonds",
        "I raise 40 or 50",
        "what is the pot",
        "no",
        "I raise your twenty to fifty",
    ], [
        "I have 1500 chips.",
        "You have 1500 chips.",
        DEAL_LINE,
        "I have ace of clubs and king of diamonds. Your action.",
        "Do you mean 40 or 50? Say the amount again.",
        "The pot is 30. Say the amount again.",
        "Cancelled. Say the action again.",
        "You raise to 50. I raise to 85.",
    ])

    _expect("illegal action, short raise, wrong call, skipped street", [
        "you have 1500",
        "I have 1500",
        "deal",
        "your cards are the ace of spades",
        "your cards are the ace of spades and the ace of spades",
        "your cards are the ace of spades and the king of hearts",
        "I check",
        "I raise to 30",
        "I call 5",
        "I check and raise",
        "I call",
        "turn is the two of spades",
        "flop is the two of clubs and the three of diamonds",
        "flop is the ace of spades, the four of diamonds, and the five of clubs",
        "blinds are 50 and 100",
        "you have 900",
    ], [
        "I have 1500 chips.",
        "You have 1500 chips.",
        DEAL_LINE,
        "Tell me exactly two cards.",
        "A card cannot appear twice.",
        "I have ace of spades and king of hearts. Your action.",
        "You cannot check. It is 10 to call.",
        "A raise must be to at least 40.",
        "It is 10 to call.",
        "Say one action: fold, check, call, bet, or raise.",
        f"You call. I check. {WAIT_FLOP}",
        "The turn does not come now.",
        "The flop needs three cards.",
        "That card is already out.",
        "Finish this hand before changing the blinds.",
        "Stacks are already in this hand.",
    ])

    _expect("checkdown, showdown questions, stacks survive the next hand", [
        "you have 200",
        "I have 200",
        "deal",
        "your cards are the seven of hearts and the two of clubs",
        "I call",
        "flop is the ace of spades, the king of diamonds, and the queen of clubs",
        "I check",
        "turn is the three of hearts",
        "I check",
        "river is the nine of clubs",
        "I check",
        "what is your win rate",
        "what is on the board",
        "deal",
        "I win",
        "how many chips do you have",
        "how many chips do I have",
        "deal",
        "your cards are the ace of clubs and the ace of diamonds",
        "I fold",
    ], [
        "I have 200 chips.",
        "You have 200 chips.",
        DEAL_LINE,
        "I have seven of hearts and two of clubs. Your action.",
        f"You call. I check. {WAIT_FLOP}",
        "The board is ace of spades, king of diamonds, queen of clubs. I check.",
        f"You check. {WAIT_TURN}",
        "The board is ace of spades, king of diamonds, queen of clubs, three of hearts. I check.",
        f"You check. {WAIT_RIVER}",
        "The board is ace of spades, king of diamonds, queen of clubs, three of hearts, nine of clubs. I check.",
        "You check. Showdown. Tell me who won.",
        "About 9 percent against a random hand.",
        "The board is ace of spades, king of diamonds, queen of clubs, three of hearts, nine of clubs.",
        "Tell me who won before the next deal.",
        "You take the pot of 40.",
        "I have 180 chips. Blinds are 10 and 20.",
        "You have 220 chips. Blinds are 10 and 20.",
        DEAL_LINE,
        "I have ace of clubs and ace of diamonds. Your action.",
        "You fold. I take the pot of 30.",
    ])

    _expect("split, all in, and a weak fold", [
        "you have 40",
        "I have 40",
        "deal",
        "your cards are the ace of spades and the ace of hearts",
        "I raise to 40",
        "how many chips do you have",
        "flop is the two of clubs, the three of diamonds, and the four of hearts",
        "turn is the five of spades",
        "river is the nine of clubs",
        "split",
    ], [
        "I have 40 chips.",
        "You have 40 chips.",
        DEAL_LINE,
        "I have ace of spades and ace of hearts. Your action.",
        f"You raise all in. I call all in. {WAIT_FLOP}",
        "I am all in. The pot is 80.",
        f"The board is two of clubs, three of diamonds, four of hearts. {WAIT_TURN}",
        f"The board is two of clubs, three of diamonds, four of hearts, five of spades. {WAIT_RIVER}",
        "The board is two of clubs, three of diamonds, four of hearts, five of spades, nine of clubs. Showdown. Tell me who won.",
        "Split. You take 40. I take 40.",
    ])

    folded = _play([
        "you have 1500",
        "I have 1500",
        "deal",
        "your cards are the seven of hearts and the two of clubs",
        "I raise to 80",
    ])
    assert folded[-1] == "You raise to 80. I fold. You take the pot of 100."

    minimum = _play([
        "you have 1500",
        "I have 1500",
        "deal",
        "your cards are the seven of hearts and the two of clubs",
        "I call",
        "flop is the ace of spades, the king of diamonds, and the queen of clubs",
        "I bet",
        "I bet 10",
        "I fold",
    ])
    assert minimum[-3] == "Bet how many?"
    assert minimum[-2] == "The minimum bet is 20."
    assert minimum[-1] == "You fold. I take the pot of 40."
    _check_record()


def _check_record() -> None:
    import tempfile

    quiet = Player()
    assert quiet.on_heard("repeat") == "I have not said anything yet."

    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        player = Player(record_dir=directory)
        greeting = player.greeting()
        assert player.on_heard("pardon") == greeting
        script = [
            "you have 1500",
            "I have 1500",
            "deal",
            "your cards are the ace of clubs and the ace of diamonds",
            "I raise",
        ]
        for line in script:
            player.on_heard(line)
        prompt = player.last_spoken
        status = player.status()
        assert player.on_heard("what did you say") == prompt
        assert player.on_heard("没听清，再来一遍") == prompt
        assert player.status() == status
        assert player.phase is Phase.AWAIT_AMOUNT
        closing = player.on_heard("I fold")
        assert closing == "You fold. I take the pot of 30."
        assert len(player.hands) == 1
        hand = (directory / "hand_001.txt").read_text(encoding="utf-8")
        assert "[idle] You: deal" in hand
        assert "[preflop] Pi: New hand. You post 10. I post 20. I am waiting for my two hole cards. Take your time." in hand
        assert "[preflop] You: I raise" in hand
        assert "You fold. I take the pot of 30." in hand
        assert "you have 1500" not in hand
        session = (directory / "session.txt").read_text(encoding="utf-8")
        assert greeting in session
        assert "[idle] You: you have 1500" in session
        assert "没听清，再来一遍" in session


def _probe(lines: list[str]) -> None:
    player = Player(record_dir=TRANSCRIPTS)
    print(player.greeting())
    print(player.status())
    for line in lines:
        print(f"> {line}")
        print(player.on_heard(line))
        print(player.status())


def run_text(alt_personality: bool, trace: bool) -> None:
    player = Player(alt_personality=alt_personality, record_dir=TRANSCRIPTS)
    which = "alt placeholder, same lines" if alt_personality else "default"
    print(f"personality: {which}")
    print(player.greeting())
    if trace:
        print(player.status())
    while True:
        try:
            heard = input("> ")
        except EOFError:
            print()
            return
        if heard.strip().lower() in {"quit", "exit"}:
            return
        print(player.on_heard(heard))
        if trace:
            print(player.status())


def _watch_cards(player: Player, speech_q, stop, frames: int, flip: str) -> None:
    """Read the camera only while a card window is open. Speak from the mic thread."""
    vision_dir = Path(__file__).resolve().parent.parent / "card vision"
    if str(vision_dir) not in sys.path:
        sys.path.insert(0, str(vision_dir))
    import cv2
    import card_vision
    from vision_bridge import VisionBridge

    cap = card_vision.open_usb_camera()
    bridge = VisionBridge(frames=frames)
    flips = {"horizontal": 1, "vertical": 0, "both": -1}
    try:
        while not stop.is_set():
            ok, frame = cap.read()
            if not ok or frame is None:
                stop.wait(0.2)
                continue
            if flip in flips:
                frame = cv2.flip(frame, flips[flip])
            player.refresh_vision_window()
            if player.vision_window is None:
                stop.wait(0.2)
                continue
            detections = card_vision.detect_cards(frame)
            zones = card_vision.assign_zones(detections, image_height=frame.shape[0])
            reply = bridge.observe(player, zones)
            if reply:
                speech_q.put(reply)
    finally:
        cap.release()


def run_voice(
    alt_personality: bool,
    model: str,
    vad_model: Path,
    voice: Path,
    min_silence: float,
    camera: bool = True,
    vision_frames: int = 15,
    flip: str = "horizontal",
) -> None:
    import queue
    import threading
    import time

    import numpy as np
    import sherpa_onnx
    import sounddevice as sd
    from faster_whisper import WhisperModel
    from piper import PiperVoice

    for path, what in ((vad_model, "VAD model"), (voice, "Piper voice")):
        if not path.is_file():
            sys.exit(f"{what} not found at {path}. Run ./setup.sh first.")
    print("Loading models...", flush=True)
    recognizer = WhisperModel(model, device="cpu", compute_type="int8")
    piper = PiperVoice.load(str(voice))
    player = Player(alt_personality=alt_personality, record_dir=TRANSCRIPTS)

    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = str(vad_model)
    config.silero_vad.min_silence_duration = min_silence
    config.sample_rate = SAMPLE_RATE
    window = config.silero_vad.window_size

    stream_holder: dict = {}
    vad_holder: dict = {
        "vad": sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)
    }
    speaking = threading.Event()
    listen_after = 0.0
    buffer = np.empty(0, dtype=np.float32)

    def flush_mic() -> None:
        mic = stream_holder.get("stream")
        if mic is None:
            return
        try:
            for _ in range(8):
                available = mic.read_available
                if not available:
                    break
                mic.read(available)
        except Exception:
            pass

    def reset_listen() -> None:
        nonlocal buffer, listen_after
        buffer = np.empty(0, dtype=np.float32)
        vad_holder["vad"] = sherpa_onnx.VoiceActivityDetector(
            config, buffer_size_in_seconds=30
        )
        listen_after = time.monotonic() + 0.4

    def say(text: str) -> None:
        nonlocal listen_after
        if not text:
            return
        speaking.set()
        try:
            print(f"Pi: {text}", flush=True)
            for audio_chunk in piper.synthesize(text):
                audio = np.frombuffer(audio_chunk.audio_int16_bytes, dtype=np.int16)
                sd.play(audio, samplerate=audio_chunk.sample_rate)
                sd.wait()
            flush_mic()
            time.sleep(0.2)
            flush_mic()
        finally:
            reset_listen()
            speaking.clear()

    speech_q: queue.Queue[str] = queue.Queue()
    stop = threading.Event()
    if camera:
        watcher = threading.Thread(
            target=_watch_cards,
            args=(player, speech_q, stop, vision_frames, flip),
            daemon=True,
        )
        watcher.start()
        print(f"Camera on. A card window locks after {vision_frames} matching reads.", flush=True)

    def drain() -> None:
        while True:
            try:
                say(speech_q.get_nowait())
            except queue.Empty:
                return

    say(player.greeting())
    samples_per_read = int(0.1 * SAMPLE_RATE)
    try:
        with sd.InputStream(channels=1, dtype="float32", samplerate=SAMPLE_RATE) as stream:
            stream_holder["stream"] = stream
            while True:
                drain()
                chunk, _ = stream.read(samples_per_read)
                if speaking.is_set() or time.monotonic() < listen_after:
                    # Drop speaker bleed and the short settle window after TTS.
                    buffer = np.empty(0, dtype=np.float32)
                    continue
                buffer = np.concatenate([buffer, chunk.reshape(-1)])
                vad = vad_holder["vad"]
                while len(buffer) > window:
                    vad.accept_waveform(buffer[:window])
                    buffer = buffer[window:]
                while not vad.empty():
                    utterance = np.array(vad.front.samples, dtype=np.float32)
                    vad.pop()
                    if speaking.is_set() or time.monotonic() < listen_after:
                        continue
                    segments, _ = recognizer.transcribe(utterance, beam_size=1)
                    heard = " ".join(part.text.strip() for part in segments)
                    if not heard:
                        continue
                    print(f"Heard: {heard}", flush=True)
                    reply = player.on_heard(heard)
                    if reply:
                        say(reply)
                    else:
                        print("(ignored echo or empty)", flush=True)
    finally:
        stop.set()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text", action="store_true")
    parser.add_argument("--trace", action="store_true", help="print the session fields after each reply")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--probe", nargs="*", help=argparse.SUPPRESS)
    parser.add_argument("--alt-personality", action="store_true")
    parser.add_argument("--model", default="tiny.en")
    parser.add_argument("--vad-model", type=Path, default=DEFAULT_VAD)
    parser.add_argument("--voice", type=Path, default=DEFAULT_VOICE)
    parser.add_argument("--min-silence", type=float, default=BET_SILENCE)
    parser.add_argument("--no-camera", action="store_true", help="microphone only")
    parser.add_argument("--vision-frames", type=int, default=15)
    parser.add_argument(
        "--flip",
        choices=("horizontal", "vertical", "both", "none"),
        default="horizontal",
    )
    args = parser.parse_args()
    if args.probe is not None:
        _probe(args.probe)
        return
    if args.check:
        _check_evaluator()
        _check_dialogues()
        from vision_bridge import check_bridge
        check_bridge()
        print("check ok")
        return
    if args.text:
        run_text(args.alt_personality, args.trace)
        return
    run_voice(
        args.alt_personality,
        args.model,
        args.vad_model,
        args.voice,
        args.min_silence,
        camera=not args.no_camera,
        vision_frames=args.vision_frames,
        flip=args.flip,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
