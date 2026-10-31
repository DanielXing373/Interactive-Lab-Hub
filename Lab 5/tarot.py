"""
The morning card. The animals at the waterhole draw a tarot card overnight; Qwen reads it.

    python tarot.py logs/amboseli.jsonl
    python tarot.py logs/amboseli.jsonl --question "Will my presentation go well?"
    python tarot.py logs/amboseli.jsonl --suits elephant=Pentacles,zebra=Swords,cow=Wands,bird=Cups
    python tarot.py logs/amboseli.jsonl --no-keywords        # let Qwen rely on its own tarot knowledge
    python tarot.py logs/amboseli.jsonl --dry-run            # draw the card, do not ask Qwen

The draw:
    Each of the four animals stands for a suit. Its count is the sum of how many were in view
    over every look of the night. The animal with the highest count picks the suit, and its count
    mod 14 picks the card: 0 Ace, 1 Two, ... 9 Ten, 10 Page, 11 Knight, 12 Queen, 13 King.
    A night with none of the four animals, or a tie for first place, draws one of the 22 Major Arcana
    instead. That draw is seeded by the night's numbers, so the same log always gives the same card.

Prints the night, the card and the reading, and saves everything for the display to
reports/<log name>_tarot.json. Card keywords come from tarot_cards.md, images from tarot/.
"""
import argparse
import json
import pathlib
import random
import re
import sys
import time

import requests

HERE = pathlib.Path(__file__).parent
RANKS = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Page", "Knight", "Queen", "King"]
SUIT_MEANING = {
    "Wands": "fire: energy, ambition, action",
    "Cups": "water: feelings, love, relationships",
    "Swords": "air: thoughts, decisions, conflict",
    "Pentacles": "earth: work, money, the body, steadiness",
}

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("log", help="a logs/<name>.jsonl written by watch.py")
parser.add_argument("--suits", default="elephant=Pentacles,giraffe=Wands,zebra=Swords,bird=Cups",
                    help="four animal=Suit pairs; animals are COCO class names")
parser.add_argument("--question", default="What does today hold for me?", help="the question asked before bed")
parser.add_argument("--context", default="a waterhole in Amboseli, Kenya, below Mount Kilimanjaro")
parser.add_argument("--sentences", type=int, default=4, help="length of the reading")
parser.add_argument("--lang", default="English")
parser.add_argument("--no-keywords", action="store_true", help="do not give Qwen the card's keywords")
parser.add_argument("--seed", type=int, help="override the seed of a Major Arcana draw")
parser.add_argument("--model", default="qwen3.5:0.8b")
parser.add_argument("--max-tokens", type=int, default=300)
parser.add_argument("--temperature", type=float, default=0.5)
parser.add_argument("--dry-run", action="store_true", help="draw the card and show the prompt, do not ask Qwen")
parser.add_argument("--ollama", default="http://localhost:11434")
args = parser.parse_args()

suits = dict(pair.split("=") for pair in args.suits.split(","))
if len(suits) != 4 or set(suits.values()) != set(SUIT_MEANING):
    raise SystemExit("--suits needs four animals, one for each of Wands, Cups, Swords and Pentacles")

keywords = {}
for line in (HERE / "tarot_cards.md").read_text(encoding="utf-8").splitlines():
    if line.startswith("- ") and ":" in line:
        name, words = line[2:].split(":", 1)
        keywords[name.strip()] = words.strip()
majors = list(keywords)[:22]

entries = [json.loads(line) for line in open(args.log, encoding="utf-8") if line.strip()]
looks = [e for e in entries if e.get("type") == "frame"]
if not looks:
    raise SystemExit(f"no looks in {args.log}")
first, last = looks[0]["t"], looks[-1]["t"]

night = {}
for animal in suits:
    present = [e for e in looks if animal in e["counts"]]
    night[animal] = {
        "suit": suits[animal],
        "count": sum(e["counts"][animal] for e in present),
        "looks": len(present),
        "most_at_once": max((e["counts"][animal] for e in present), default=0),
        "first_seen": present[0]["t"][11:16] if present else None,
    }

ranked = sorted(night, key=lambda a: -night[a]["count"])
top, second = night[ranked[0]]["count"], night[ranked[1]]["count"]
if top == 0 or top == second:
    seed = args.seed if args.seed is not None else sum(v["count"] for v in night.values()) * 1000 + len(looks)
    card = random.Random(seed).choice(majors)
    if top == 0:
        why = "None of the four animals came, so the night itself drew a card from the Major Arcana."
    else:
        tied = " and ".join(a for a in ranked if night[a]["count"] == top)
        why = f"The {tied} tied with {top} each, so the tie drew a card from the Major Arcana."
    winner = None
else:
    winner = ranked[0]
    rank = RANKS[top % 14]
    card = f"{rank} of {suits[winner]}"
    why = (f"The {winner} came most ({top} in total), which picks the suit of {suits[winner]}; "
           f"{top} mod 14 = {top % 14}, which is the {rank}.")

slug = re.sub(r"[^a-z0-9]+", "_", card.lower()).strip("_")
image = HERE / "tarot" / f"{slug}.jpg"

lines = [f"Watched {args.context} from {first[11:16]} to {last[11:16]}, {len(looks)} looks."]
for a in ranked:
    v = night[a]
    seen = f"first seen {v['first_seen']}, at most {v['most_at_once']} at once" if v["looks"] else "never seen"
    lines.append(f"- {a} ({v['suit']}): {v['count']} in total over {v['looks']} looks, {seen}")
summary = "\n".join(lines)
print(f"{summary}\n\n{why}\nCard: {card}  ({keywords[card]})\nImage: {image.relative_to(HERE).as_posix()}"
      + ("" if image.exists() else "  (missing!)"))

system = (f"You are a gentle tarot reader living inside a small device that watched {args.context} overnight "
          f"while its owner slept. The animals at the waterhole drew today's card. Speak warmly and simply. "
          f"Only mention animals listed in the data. Upright meanings only. Answer in {args.lang}.")
suit_lines = "\n".join(f"- {a} stands for {s} ({SUIT_MEANING[s]})" for a, s in suits.items())
card_line = f"The card: {card}." if args.no_keywords else f"The card: {card}. Its meaning: {keywords[card]}."
prompt = (f"Last night:\n{summary}\n\nThe animals and their suits:\n{suit_lines}\n\nHow the card was drawn: {why}\n\n"
          f"{card_line}\n\nThe owner asked before bed: \"{args.question}\"\n\n"
          f"Write a reading of exactly {args.sentences} sentences: name the card, explain what it means for today, "
          f"answer the owner's question, and "
          + (f"say that the {winner} drew it last night." if winner else
             "say that no single animal drew it: " + ("the quiet night did." if top == 0 else "a tie did.")))

result = {"log": args.log, "context": args.context, "from": first, "to": last, "looks": len(looks),
          "animals": night, "winner": winner, "card": card, "keywords": keywords[card],
          "image": image.relative_to(HERE).as_posix(), "why": why, "question": args.question,
          "model": args.model, "reading": None}

if args.dry_run:
    print(f"\n[system]\n{system}\n\n[prompt]\n{prompt}")
    raise SystemExit

t0 = time.time()
r = requests.post(f"{args.ollama}/api/generate", timeout=900, json={
    "model": args.model, "system": system, "prompt": prompt, "think": False, "stream": False,
    "options": {"temperature": args.temperature, "num_predict": args.max_tokens, "num_ctx": 4096}})
r.raise_for_status()
result["reading"] = r.json()["response"].strip()
result["seconds"] = round(time.time() - t0, 1)

out = HERE / "reports" / f"{pathlib.Path(args.log).stem}_tarot.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"\n{result['reading']}\n\n[{args.model}, {result['seconds']} s, saved to {out.relative_to(HERE).as_posix()}]")
