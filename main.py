#!/usr/bin/env python3
"""World News - 25 November 2026. Draws a 1024x1024 newspaper cover in
pure Python 3.13 stdlib: own 5x7 bitmap font, own PNG encoder, no network,
no randomness, no clock. Deterministic: two runs write identical bytes."""

import os
import struct
import zlib

W, H = 1024, 1024
PAPER = (247, 242, 231)
INK = (26, 26, 26)
RED = (176, 32, 32)
BLUE = (31, 58, 95)

# 5x7 bitmap font, all caps + digits + punctuation. Each glyph: 7 rows of
# 5 characters, '#' = ink, '.' = empty.
FONT = {
    'A': (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'C': (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'E': ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    'F': ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    'G': (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    'H': ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'I': (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    'J': ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'M': ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    'N': ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'P': ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    'Q': (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    'R': ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    'S': (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    'U': ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'V': ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    'W': ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    'X': ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    'Y': ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    'Z': ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    '0': (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    '1': ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    '2': (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    '3': ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    '4': ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    '5': ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    '6': (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    '7': ("#####", "....#", "...#.", "...#.", "..#..", "..#..", "..#.."),
    '8': (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    '9': (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ',': (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ':': (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    ';': (".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."),
    '!': ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    '?': (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    '-': (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    '/': ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    '(': ("...##", "..#..", ".#...", ".#...", ".#...", "..#..", "...##"),
    ')': ("##...", "..#..", "...#.", "...#.", "...#.", "..#..", "##..."),
    '&': (".##..", "#..#.", "#..#.", ".#...", "#.#.#", "#..#.", ".##.#"),
    '%': ("#...#", "#..#.", "...#.", "..#..", ".#...", "#..#.", "#...#"),
    '+': (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    '=': (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    '"': (".#.#.", ".#.#.", ".#.#.", ".....", ".....", ".....", "....."),
    '$': ("..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."),
}


class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        r, g, b = bg
        for i in range(0, len(self.buf), 3):
            self.buf[i] = r
            self.buf[i + 1] = g
            self.buf[i + 2] = b

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i], self.buf[i + 1], self.buf[i + 2] = c

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.px(xx, yy, c)

    def hline(self, x, y, w, c, t=1):
        self.rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.rect(x, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            for a in range(t):
                for b in range(t):
                    self.px(x0 + a, y0 + b, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c, t=2):
        x, y, d = 0, r, 3 - 2 * r
        while x <= y:
            for px_, py_ in ((cx + x, cy + y), (cx - x, cy + y),
                             (cx + x, cy - y), (cx - x, cy - y),
                             (cx + y, cy + x), (cx - y, cy + x),
                             (cx + y, cy - x), (cx - y, cy - x)):
                for a in range(t):
                    for b in range(t):
                        self.px(px_ + a, py_ + b, c)
            if d < 0:
                d += 4 * x + 6
            else:
                d += 4 * (x - y) + 10
                y -= 1
            x += 1

    def fill_circle(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            dx = int((r * r - (yy - cy) ** 2) ** 0.5)
            self.rect(cx - dx, yy, 2 * dx + 1, 1, c)

    def text(self, s, x, y, scale, c):
        cx = x
        for ch in s:
            glyph = FONT.get(ch, FONT[' '])
            for row in range(7):
                bits = glyph[row]
                for col in range(5):
                    if bits[col] == '#':
                        self.rect(cx + col * scale, y + row * scale,
                                  scale, scale, c)
            cx += 6 * scale
        return cx - x

    def text_width(self, s, scale):
        return len(s) * 6 * scale - scale

    def text_centered(self, s, y, scale, c):
        w = self.text_width(s, scale)
        self.text(s, (self.w - w) // 2, y, scale, c)

    def wrap(self, s, scale, max_w):
        words = s.split(' ')
        lines, cur = [], ''
        for word in words:
            trial = (cur + ' ' + word).strip()
            if self.text_width(trial, scale) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines


def draw_globe(cv, cx, cy, r, c):
    cv.circle(cx, cy, r, c, 2)
    cv.hline(cx - r, cy, 2 * r, c, 2)
    cv.vline(cx, cy - r, 2 * r, c, 2)
    cv.line(cx - r + 6, cy - r + 8, cx + r - 6, cy + r - 8, c, 2)
    cv.line(cx + r - 6, cy - r + 8, cx - r + 6, cy + r - 8, c, 2)


def draw_ship(cv, x, y, c):
    # small cargo ship with flag and waves, for the lead story
    cv.rect(x + 20, y + 34, 150, 14, c)
    cv.line(x + 170, y + 34, x + 196, y + 48, c, 3)
    cv.line(x + 20, y + 34, x + 4, y + 48, c, 3)
    cv.rect(x + 60, y + 16, 44, 18, c)
    cv.rect(x + 66, y + 22, 8, 6, PAPER)
    cv.rect(x + 84, y + 22, 8, 6, PAPER)
    cv.vline(x + 118, y, 34, c, 3)
    cv.line(x + 118, y, x + 146, y + 8, RED, 3)
    cv.line(x + 146, y + 8, x + 118, y + 16, RED, 3)
    cv.hline(x + 10, y + 58, 60, BLUE, 3)
    cv.hline(x + 130, y + 58, 60, BLUE, 3)
    cv.hline(x + 40, y + 66, 60, BLUE, 3)
    cv.hline(x + 110, y + 66, 60, BLUE, 3)


def icon_chip(cv, x, y, s, c):
    # square chip with pins: tech trial
    cv.rect(x + s // 4, y + s // 4, s // 2, s // 2, c)
    cv.rect(x + s // 4 + 4, y + s // 4 + 4, s // 2 - 8, s // 2 - 8, PAPER)
    cv.rect(x + s // 2 - 4, y + s // 2 - 4, 8, 8, c)
    for i in range(3):
        off = s // 4 + i * (s // 4)
        cv.rect(x + off, y + 2, 4, s // 4 - 2, c)
        cv.rect(x + off, y + s - s // 4, 4, s // 4 - 2, c)
        cv.rect(x + 2, y + off, s // 4 - 2, 4, c)
        cv.rect(x + s - s // 4, y + off, s // 4 - 2, 4, c)


def icon_shield(cv, x, y, s, c):
    # shield with keyhole: cyberattack
    cx, cy = x + s // 2, y + s // 2
    pts = [(cx - s // 3, y + 6), (cx + s // 3, y + 6),
           (cx + s // 3, y + s // 2), (cx, y + s - 8),
           (cx - s // 3, y + s // 2)]
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        cv.line(x0, y0, x1, y1, c, 3)
    cv.fill_circle(cx, cy - 4, 6, c)
    cv.rect(cx - 3, cy, 6, 12, c)


def icon_cross(cv, x, y, s, c):
    # medical cross in a circle: Ebola evacuation
    cx, cy = x + s // 2, y + s // 2
    cv.circle(cx, cy, s // 2 - 4, c, 3)
    cv.rect(cx - 5, cy - 16, 10, 32, RED)
    cv.rect(cx - 16, cy - 5, 32, 10, RED)


def icon_tower(cv, x, y, s, c):
    # stepped tower with antenna: Riyadh strike
    cx = x + s // 2
    cv.rect(cx - 18, y + s - 22, 36, 16, c)
    cv.rect(cx - 13, y + s - 36, 26, 14, c)
    cv.rect(cx - 9, y + s - 50, 18, 14, c)
    cv.rect(cx - 2, y + 6, 4, s - 56, c)
    cv.fill_circle(cx, y + 6, 3, RED)
    cv.rect(cx - 13, y + s - 30, 6, 6, PAPER)
    cv.rect(cx + 4, y + s - 30, 6, 6, PAPER)
    cv.rect(cx - 13, y + s - 16, 6, 6, PAPER)
    cv.rect(cx + 4, y + s - 16, 6, 6, PAPER)


def icon_search(cv, x, y, s, c):
    # magnifier: corruption probe
    cx, cy = x + s // 2 - 4, y + s // 2 - 4
    cv.circle(cx, cy, s // 4, c, 3)
    cv.line(cx + 13, cy + 13, cx + 26, cy + 26, c, 5)
    cv.fill_circle(cx, cy, 4, RED)


LEAD_KICKER = "LEAD STORY - EUROPE"
LEAD_HEAD = ["ZELENSKIY CONFIRMS UKRAINE HIT",
             "RUSSIAN SHIP IN GULF OF FINLAND"]
LEAD_SUMMARY = ["KYIV TAKES RESPONSIBILITY FOR SATURDAY'S DRONE",
                "STRIKE ON A CARGO VESSEL; NORWAY URGES CAUTION."]

STORIES = [
    ("TECH - UNITED STATES", "HUAWEI GUILTY IN US TRADE-SECRETS TRIAL",
     "US JURY CONVICTS THE CHINESE TECH GIANT ON 10 OF 12 COUNTS AFTER A "
     "THREE-MONTH TRIAL IN NEW YORK.", "chip"),
    ("SECURITY - UNITED STATES", "CYBERATTACK HITS CIA AND SPY CHIEF'S OFFICE",
     "INTRUSION STRIKES A SYSTEM USED TO ANALYSE OPEN-SOURCE INTELLIGENCE, "
     "CNN REPORTS.", "shield"),
    ("HEALTH - AFRICA", "WHO PULLS EBOLA STAFF OUT OF CONGO HOSPITAL",
     "HEALTH WORKERS EVACUATED FROM AKWE IN ITURI AFTER THREE DAYS "
     "SHELTERING FROM FIERCE FIGHTING.", "cross"),
    ("MIDDLE EAST", "HOUTHI STRIKE HITS RIYADH TOWER, 11 HURT",
     "ATTACK ON THE SAUDI CAPITAL'S TALLEST TOWER WOUNDS 11, INCLUDING TWO "
     "INDIAN NATIONALS.", "tower"),
    ("ASIA - CHINA", "CHINA PROBES SHANGHAI PARTY CHIEF",
     "BEIJING OPENS A SHOCK CORRUPTION INVESTIGATION INTO SHANGHAI PARTY "
     "CHIEF CHEN JINING.", "search"),
]

ICONS = {"chip": icon_chip, "shield": icon_shield, "cross": icon_cross,
         "tower": icon_tower, "search": icon_search}

FOOTER = "SIX STORIES FROM AROUND THE WORLD - SOURCES: REUTERS, BBC, CNN"


def render():
    cv = Canvas(W, H, PAPER)
    # masthead with flanking globes
    cv.text("WORLD NEWS", (W - cv.text_width("WORLD NEWS", 9)) // 2, 30, 9, INK)
    draw_globe(cv, 150, 61, 30, BLUE)
    draw_globe(cv, 874, 61, 30, BLUE)
    cv.text_centered("WEDNESDAY 25 NOVEMBER 2026", 110, 3, RED)
    cv.hline(32, 146, W - 64, RED, 5)
    cv.hline(32, 156, W - 64, INK, 2)
    # lead story
    cv.text(LEAD_KICKER, 32, 174, 2, RED)
    cv.text(LEAD_HEAD[0], 32, 196, 4, INK)
    cv.text(LEAD_HEAD[1], 32, 234, 4, INK)
    cv.text(LEAD_SUMMARY[0], 32, 286, 3, INK)
    cv.text(LEAD_SUMMARY[1], 32, 317, 3, INK)
    draw_ship(cv, 792, 198, BLUE)
    cv.hline(32, 352, W - 64, INK, 2)
    # five stories
    y = 370
    for kicker, head, summary, icon in STORIES:
        cv.rect(32, y + 6, 76, 76, PAPER)
        cv.rect(32, y + 6, 76, 3, INK)
        cv.rect(32, y + 79, 76, 3, INK)
        cv.rect(32, y + 6, 3, 76, INK)
        cv.rect(105, y + 6, 3, 76, INK)
        ICONS[icon](cv, 38, y + 12, 64, BLUE)
        cv.text(kicker, 128, y + 10, 2, RED)
        cv.text(head, 128, y + 32, 3, INK)
        lines = cv.wrap(summary, 2, W - 32 - 128)
        for i, line in enumerate(lines[:2]):
            cv.text(line, 128, y + 60 + i * 18, 2, INK)
        y += 112
    # footer
    cv.hline(32, 940, W - 64, RED, 3)
    cv.text_centered(FOOTER, 954, 2, INK)
    cv.hline(32, 986, W - 64, INK, 2)
    cv.hline(32, 992, W - 64, INK, 2)
    return cv


def png_bytes(cv):
    raw = bytearray()
    for yy in range(cv.h):
        raw.append(0)
        raw += cv.buf[yy * cv.w * 3:(yy + 1) * cv.w * 3]

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body +
                struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            chunk(b"IEND", b""))


def main():
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    data = png_bytes(render())
    with open(os.path.join(out, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
