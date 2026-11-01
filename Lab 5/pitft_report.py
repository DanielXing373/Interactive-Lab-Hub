"""
Part I: show a tarot report on the Mini PiTFT, landscape (240x135, rotation 90 as in the Lab 2 bird clock).
Button A (top) = previous page, B (bottom) = next.

    python pitft_report.py reports/20261031_A_tarot.json
    python pitft_report.py reports/20261031_A_tarot.json --flip     # if the picture is upside down

The screen is the demo presentation of the report. It only reads the JSON that tarot.py saved
(the real report, also printed to the console); it changes nothing and makes nothing up.
Pages: 1 last night's animals, 2 the card, 3+ Qwen's reading. Ctrl-C blanks the screen.
Wiring and panel settings are the same as Lab 2 (CS on GPIO5, DC GPIO25, backlight GPIO22).
"""
import argparse
import json
import pathlib
import time

import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import st7789

HERE = pathlib.Path(__file__).resolve().parent
W, H = 240, 135
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GOLD, WHITE, GREY = (255, 214, 102), (235, 235, 235), (150, 150, 150)

parser = argparse.ArgumentParser()
parser.add_argument("report", help="a reports/*_tarot.json file written by tarot.py")
parser.add_argument("--flip", action="store_true", help="rotate the picture 180 degrees")
args = parser.parse_args()
report = json.loads(pathlib.Path(args.report).read_text(encoding="utf-8"))


def font(size, bold=False):
    try:
        return ImageFont.truetype(BOLD if bold else FONT, size)
    except OSError:
        return ImageFont.load_default()


def wrap(text, f, width=W - 8):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if not line or f.getlength(test) <= width:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def blank():
    img = Image.new("RGB", (W, H), (10, 12, 20))
    return img, ImageDraw.Draw(img)


def stats_page():
    img, d = blank()
    title, small, body = font(14, True), font(10), font(12)
    left_w, right_x = 104, 114                      # left column: the night, right column: the animals
    y = 4
    d.text((4, y), "LAST NIGHT", font=title, fill=GOLD)
    y += 20
    for line in wrap(report["context"], small, left_w):
        d.text((4, y), line, font=small, fill=GREY)
        y += 12
    y += 4
    d.text((4, y), f"{report['from'][11:16]} - {report['to'][11:16]}", font=body, fill=WHITE)
    y += 16
    d.text((4, y), f"{report['looks']} looks", font=body, fill=WHITE)
    y = 6
    for animal, v in report["animals"].items():
        color = GOLD if animal == report["winner"] else WHITE
        d.text((right_x, y), animal, font=body, fill=color)
        d.text((W - 4, y), str(v["count"]), font=body, fill=color, anchor="ra")
        y += 14
        d.text((right_x + 6, y), v["suit"], font=small, fill=GREY)
        y += 15
    d.text((4, H - 22), f"{report['winner'] or 'no winner'} drew it", font=small, fill=GOLD)
    return img


def draw_steps():
    """How the card was drawn, rebuilt from the report's counts (same rule as tarot.py)."""
    winner = report["winner"]
    if winner:
        v = report["animals"][winner]
        rank = report["card"].split(" of ")[0]
        return [f"most: {winner} ({v['count']})",
                f"{winner} \u2192 {v['suit']}",
                f"{v['count']} mod 14 = {v['count'] % 14}",
                f"{v['count'] % 14} \u2192 {rank}"]
    quiet = all(v["count"] == 0 for v in report["animals"].values())
    return ["quiet night" if quiet else "a tie", "\u2192 Major Arcana", "picked by the date"]


def card_page():
    img, d = blank()
    card = Image.open(HERE / report["image"]).convert("RGB")
    card.thumbnail((W // 2, H - 6))                 # the card stands on the left, the math on the right
    img.paste(card, (6, 3))
    x = card.width + 14
    y = 8
    for line in draw_steps():
        d.text((x, y), line, font=font(11), fill=WHITE)
        y += 16
    y += 6
    for line in wrap(report["card"], font(13, True), W - x - 4):
        d.text((x, y), line, font=font(13, True), fill=GOLD)
        y += 17
    return img


def reading_pages():
    f, line_h = font(11), 14
    lines = wrap(report["reading"] or "(no reading)", f)
    first, rest = (H - 36) // line_h, (H - 18) // line_h
    chunks = [lines[:first]] + [lines[i:i + rest] for i in range(first, len(lines), rest)]
    pages = []
    for n, chunk in enumerate(chunks):
        img, d = blank()
        y = 4
        if n == 0:
            d.text((4, y), "TODAY", font=font(14, True), fill=GOLD)
            y += 19
        for line in chunk:
            d.text((4, y), line, font=f, fill=WHITE)
            y += line_h
        pages.append(img)
    return pages


pages = [stats_page(), card_page()] + reading_pages()
for i, page in enumerate(pages):
    ImageDraw.Draw(page).text((W - 3, H - 3), f"{i + 1}/{len(pages)}", font=font(9), fill=GREY, anchor="rd")

display = st7789.ST7789(board.SPI(), cs=digitalio.DigitalInOut(board.D5), dc=digitalio.DigitalInOut(board.D25),
                        rst=None, baudrate=64_000_000, width=135, height=240, x_offset=53, y_offset=40)
backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output(value=True)
buttons = []
for pin in (board.D23, board.D24):
    b = digitalio.DigitalInOut(pin)
    b.switch_to_input(pull=digitalio.Pull.UP)  # pressed reads False
    buttons.append(b)
rotation = 270 if args.flip else 90               # landscape; A and B stay top and bottom as in Lab 2

page, was = 0, [False, False]
display.image(pages[page], rotation)
print(f"showing {args.report} on the PiTFT: {len(pages)} pages, A = back, B = next, Ctrl-C to stop", flush=True)
try:
    while True:
        held = [not b.value for b in buttons]
        if held[0] and not was[0]:
            page = (page - 1) % len(pages)
            display.image(pages[page], rotation)
        if held[1] and not was[1]:
            page = (page + 1) % len(pages)
            display.image(pages[page], rotation)
        was = held
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    display.image(Image.new("RGB", (W, H)), rotation)
    backlight.value = False
