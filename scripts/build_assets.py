#!/usr/bin/env python3
"""Generate the profile banner and icon SVGs in assets/ (dark and light).

The banner embeds small WOFF2 subsets of Alexandria, IBM Plex Sans and
IBM Plex Mono so it renders the same for every visitor (GitHub serves SVGs
as <img>, which cannot load external fonts).

Usage: python3 scripts/build_assets.py [FONT_DIR]
"""
import base64
import io
import math
import random
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".local/share/fonts/desbot"

THEMES = {
    "dark": dict(bg="#16191D", ink="#EEF0F1", muted="#9AA3AB", faint="#EEF0F1",
                 green="#2FB36E", green_text="#2FB36E", blue="#4A9EFF", robot_fill="#16191D"),
    "light": dict(bg="#EEF0F1", ink="#15181C", muted="#4A525A", faint="#15181C",
                  green="#1A7442", green_text="#1A7442", blue="#4A9EFF", robot_fill="#EEF0F1"),
}

NAME = "Abdelrahman Eldesouky"
TITLE = "Senior Robotics Software Engineer"
LINE = "Multi-robot autonomy and navigation on real robots"
TAG = "ROS 2  /  C++  /  Nav2"
# Every string the mono font must cover (subsetting only).
CAPTION = "exploring  /  mapping maps merged r1 patrol r2 inspect r3 survey building the H together fetching the pieces hello from the map"


# ---------------------------------------------------------------- fonts
def font_b64(path, text, wght=None):
    font = TTFont(path)
    if wght is not None and "fvar" in font:
        font = instancer.instantiateVariableFont(font, {"wght": wght})
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.hinting = False
    opts.desubroutinize = True
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = []
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def font_css():
    faces = [
        ("PAlexandria", FONT_DIR / "Alexandria-Variable.ttf", NAME, 600),
        ("PPlexSans", FONT_DIR / "IBMPlexSans-Variable.ttf", TITLE + LINE, 400),
        ("PPlexMono", FONT_DIR / "IBMPlexMono-SemiBold.ttf", TAG + CAPTION + "r123", None),
    ]
    out = []
    for fam, path, text, w in faces:
        data = font_b64(path, text, w)
        out.append(f"@font-face{{font-family:{fam};src:url(data:font/woff2;base64,{data}) format('woff2')}}")
    return "".join(out)


# ---------------------------------------------------------------- scene
# Local scene coordinates (0..460 x 0..250), translated into the banner.
# One 34 s loop; every animation shares it:
#   0-7 s     explore: each robot starts in its own corner; walls appear where it drives
#   7-8.5 s   the three maps merge into one complete map; loose items show up on it
#   8.5-12.5  jobs: r1 patrols, r2 inspects a crate, r3 surveys a room
#   12.5-18   build the H together: r1 left |, r3 right |, r2 the crossbar
#   18-25     fetch: r1 carries the i stem, r2 the dot, r3 one ^ and then the other
#   25-30     all three stand under "Hi ^^"; then fade and drive back to their corners
CYCLE = 34.0
WALLS = [
    ((10, 10), (450, 10)), ((450, 10), (450, 240)), ((450, 240), (10, 240)), ((10, 240), (10, 10)),
    ((160, 10), (160, 140)),           # inner wall, top
    ((300, 110), (300, 240)),          # inner wall, bottom
]
BOXES = [(212, 34, 44, 30), (372, 46, 34, 34), (60, 120, 40, 26)]
for x, y, w, h in BOXES:
    WALLS += [((x, y), (x + w, y)), ((x + w, y), (x + w, y + h)),
              ((x + w, y + h), (x, y + h)), ((x, y + h), (x, y))]

EXPLORE_SPEED = 86.0
EXPLORE = [
    [(30, 222), (270, 222), (270, 170), (190, 170), (190, 80), (285, 80)],   # r1: bottom and centre
    [(30, 30), (140, 30), (140, 110), (40, 110)],                            # r2: top-left room
    [(430, 222), (330, 222), (330, 140), (430, 140), (430, 30), (330, 30)],  # r3: right room
]
MAP_MERGED = (7.0, 8.5)
SHOW_END, RESET = 30.0, 31.0
JOBS = ["patrol", "inspect", "survey"]

# Word geometry: "Hi ^^" on the open floor, bottom-left.
STEM_C, DOT_C, CARET1_C, CARET2_C = (125, 191.5), (125, 154), (173, 180.5), (219, 180.5)
# Items lying on the map: (name, pickup point, drop point).
ITEMS = {"stem": ((100, 70), STEM_C), "dot": ((230, 100), DOT_C),
         "caret1": ((265, 215), CARET1_C), "caret2": ((265, 160), CARET2_C)}


class Plan:
    """Timed waypoints for one robot, plus the strokes it draws and the items it carries."""

    def __init__(self, start):
        self.pts = [(0.0, start)]
        self.ink = []      # (t0, t1, a, b)
        self.carry = {}    # item -> list of (t, p) while carried

    @property
    def t(self):
        return self.pts[-1][0]

    @property
    def p(self):
        return self.pts[-1][1]

    def go(self, p, speed=90.0, draw=False):
        a, t0 = self.p, self.t
        self.pts.append((t0 + math.dist(a, p) / speed, p))
        if draw:
            self.ink.append((t0, self.t, a, p))
        return self

    def wait(self, until):
        if until > self.t:
            self.pts.append((until, self.p))
        return self

    def pause(self, secs):
        return self.wait(self.t + secs)

    def carry_to(self, item, route, speed=80.0):
        track = [(self.t, self.p)]
        for p in route:
            self.go(p, speed)
            track.append((self.t, p))
        self.carry.setdefault(item, []).extend(track)   # a carry can be split into legs
        return self.pause(0.3)


def plans():
    r = [Plan(EXPLORE[i][0]) for i in range(3)]
    for plan, route in zip(r, EXPLORE):
        for p in route[1:]:
            plan.go(p, EXPLORE_SPEED)
    r1, r2, r3 = r
    # Jobs
    r1.go((190, 80), 50).go((285, 80), 50).go((190, 80), 50).wait(12.6)
    r2.go((80, 108)).wait(12.0)
    r3.go((330, 96)).go((389, 96)).wait(11.4)
    # Gather at the H
    r1.go((190, 150)).go((50, 213)).wait(15.5)
    r2.go((40, 108)).go((30, 125)).go((30, 183)).wait(16.9)
    r3.go((310, 96)).go((290, 100)).go((250, 150)).go((95, 213)).wait(15.5)
    # Build the H together
    r1.go((50, 153), 50, draw=True)
    r3.go((95, 153), 50, draw=True)
    r2.go((50, 183), 60).go((95, 183), 55, draw=True)
    # Fetch the rest
    r1.wait(18.0).go((130, 148)).go((130, 95)).go((100, 70)).pause(0.4)
    r1.carry_to("stem", [(130, 95), (130, 150), STEM_C])
    r1.go((125, 228)).go((72, 228))
    r2.go((140, 183)).go((190, 150)).go((230, 100)).pause(0.4)
    r2.carry_to("dot", [(190, 150)]).wait(r1.carry["stem"][-1][0] + 0.2)
    r2.carry_to("dot", [(190, 150), (140, 140), DOT_C])
    r2.go((110, 165)).go((110, 228)).go((125, 228))
    r3.wait(17.9).go((150, 140)).go((240, 150)).go((265, 215)).pause(0.4)
    r3.carry_to("caret1", [CARET1_C])
    r3.go((265, 160)).pause(0.4)
    r3.carry_to("caret2", [CARET2_C])
    r3.go((250, 205)).go((196, 228))
    for i, plan in enumerate(r):
        assert plan.t <= SHOW_END, (i, plan.t)
        plan.wait(SHOW_END).wait(RESET + 0.5).pts.append((CYCLE, EXPLORE[i][0]))
    return r


def kt(*ts):
    return ";".join(f"{t / CYCLE:.4f}" for t in ts)


def anim(attr, values, times):
    return (f'<animate attributeName="{attr}" dur="{CYCLE:g}s" repeatCount="indefinite" '
            f'values="{values}" keyTimes="{kt(*times)}"/>')


def motion_attrs(tl):
    """Polyline path plus keyPoints/keyTimes so the robot is at each waypoint on time."""
    d = [f"M{tl[0][1][0]} {tl[0][1][1]}"]
    cum = [0.0]
    for (_, a), (_, b) in zip(tl, tl[1:]):
        cum.append(cum[-1] + math.dist(a, b))
        d.append(f"L{b[0]} {b[1]}")
    total = cum[-1]
    kp = ";".join(f"{c / total:.4f}" for c in cum)
    return "".join(d), kp, kt(*(t for t, _ in tl))


def map_points(spacing=6.0):
    """Wall hits as a merged LiDAR map: one compact path of 2x2 squares."""
    rng = random.Random(7)
    out = []
    for (x1, y1), (x2, y2) in WALLS:
        length = math.dist((x1, y1), (x2, y2))
        for k in range(int(length // spacing) + 1):
            t = k * spacing / length
            x = x1 + (x2 - x1) * t + rng.gauss(0, 0.8)
            y = y1 + (y2 - y1) * t + rng.gauss(0, 0.8)
            out.append(f"M{x - 1:.0f} {y - 1:.0f}h2v2h-2z")
    return "".join(out)


def dotted(a, b, spacing=5.0, size=3.0):
    length = math.dist(a, b)
    out = []
    for k in range(int(length // spacing) + 1):
        t = k * spacing / length
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        out.append(f"M{x - size / 2:.1f} {y - size / 2:.1f}h{size}v{size}h-{size}z")
    return "".join(out)


ITEM_SHAPES = {
    "stem": dotted((0, -21.5), (0, 21.5)),
    "dot": "M-3 -3h6v6h-6z",
    "caret1": dotted((-18, 12.5), (0, -12.5)) + dotted((0, -12.5), (18, 12.5)),
}
ITEM_SHAPES["caret2"] = ITEM_SHAPES["caret1"]


def item_svg(c, name, track):
    """An item lies at its pickup point, rides along while carried, then stays where it was dropped."""
    pick, drop = ITEMS[name]
    pts = [(0.0, pick)] + track + [(RESET - 0.01, drop), (CYCLE, pick)]
    # keyTimes must strictly increase: nudge equal times apart.
    clean = []
    for t, p in pts:
        if clean and t <= clean[-1][0]:
            t = clean[-1][0] + 0.001
        clean.append((t, p))
    values = ";".join(f"{x:g} {y:g}" for _, (x, y) in clean)
    return (f'<path d="{ITEM_SHAPES[name]}" fill="{c["green"]}" opacity="0">'
            f'<animateTransform attributeName="transform" type="translate" dur="{CYCLE:g}s" '
            f'repeatCount="indefinite" values="{values}" keyTimes="{kt(*(t for t, _ in clean))}"/>'
            f'{anim("opacity", "0;0;1;1;0;0", (0, MAP_MERGED[0] + .5, MAP_MERGED[1], SHOW_END, RESET, CYCLE))}'
            f'</path>')


def phase_text(c, text, t_on, t_off):
    return (f'<text class="m" x="456" y="268" font-size="11" fill="{c["muted"]}" text-anchor="end" '
            f'letter-spacing=".5" opacity="0">{text}'
            f'{anim("opacity", "0;0;1;1;0;0", (0, t_on, t_on + .3, t_off - .3, t_off, CYCLE))}</text>')


def banner(theme, fonts):
    c = THEMES[theme]
    ox, oy = 708, 25
    walls = "".join(f"M{a[0]} {a[1]}L{b[0]} {b[1]}" for a, b in WALLS)
    reveal, ink, bots, items, ink_dots = [], [], [], [], []
    for i, plan in enumerate(plans()):
        explore_end = plan.pts[len(EXPLORE[i]) - 1][0]
        exp_d = "M" + "L".join(f"{x} {y}" for x, y in EXPLORE[i])
        reveal.append(
            f'<path d="{exp_d}" pathLength="1" stroke-dasharray="1 1" fill="none" stroke="#fff" '
            f'stroke-width="110" stroke-linecap="round" stroke-linejoin="round">'
            f'{anim("stroke-dashoffset", "1;0;0;1", (0, explore_end, RESET, CYCLE))}</path>')
        for t0, t1, a, b in plan.ink:
            ink_dots.append(dotted(a, b))
            ink.append(
                f'<path d="M{a[0]} {a[1]}L{b[0]} {b[1]}" pathLength="1" stroke-dasharray="1 1" '
                f'stroke="#fff" stroke-width="8" fill="none">'
                f'{anim("stroke-dashoffset", "1;1;0;0;1", (0, t0, t1, RESET, CYCLE))}</path>')
        for name, track in plan.carry.items():
            items.append(item_svg(c, name, track))
        d, kp, ktimes = motion_attrs(plan.pts)
        motion = (f'dur="{CYCLE:g}s" repeatCount="indefinite" path="{d}" keyPoints="{kp}" '
                  f'keyTimes="{ktimes}" calcMode="linear"')
        bots.append(
            f'<g><animateMotion {motion} rotate="auto"/><use href="#bot"/></g>'
            f'<g><animateMotion {motion}/>'
            f'<text class="m" x="10" y="-11" font-size="10" fill="{c["green_text"]}">r{i + 1}</text></g>')
    m0, m1 = MAP_MERGED
    captions = (phase_text(c, "exploring  /  mapping", 0, m0)
                + phase_text(c, "maps merged", m0, m1)
                + phase_text(c, "r1 " + JOBS[0] + "  /  r2 " + JOBS[1] + "  /  r3 " + JOBS[2], m1, 12.5)
                + phase_text(c, "building the H together", 12.5, 18.0)
                + phase_text(c, "fetching the pieces", 18.0, 25.0)
                + phase_text(c, "hello from the map", 25.0, SHOW_END))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300" role="img" aria-labelledby="t d">
<title id="t">{NAME}</title>
<desc id="d">{TITLE}. {LINE}. Animated top-down drawing: three robots start in different corners and merge one map, split up for separate jobs, build the letter H together, fetch the remaining pieces from around the map, and line up under the words Hi ^^.</desc>
<style>{fonts}
.n{{font-family:PAlexandria,Alexandria,'Segoe UI',Helvetica,Arial,sans-serif;font-weight:600}}
.s{{font-family:PPlexSans,'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif}}
.m{{font-family:PPlexMono,'IBM Plex Mono',SFMono-Regular,Consolas,'Liberation Mono',monospace;font-weight:600}}
</style>
<defs>
<pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="{c['faint']}" stroke-opacity=".06" stroke-width="1"/></pattern>
<mask id="seen" maskUnits="userSpaceOnUse" x="0" y="0" width="460" height="250">{"".join(reveal)}<rect width="460" height="250" fill="#fff" opacity="0">{anim("opacity", "0;0;1;1;0;0", (0, m0, m1, RESET, RESET + .01, CYCLE))}</rect></mask>
<mask id="ink" maskUnits="userSpaceOnUse" x="0" y="0" width="460" height="250">{"".join(ink)}</mask>
<g id="bot">
<path d="M0 0L26 -9A27 27 0 0 1 26 9Z" fill="{c['blue']}" fill-opacity=".22"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="2.4s" repeatCount="indefinite"/></path>
<rect x="-10" y="-7" width="20" height="14" fill="{c['robot_fill']}" stroke="{c['green']}" stroke-width="1.6"/>
<path d="M3 -3.5L8 0L3 3.5" fill="none" stroke="{c['green']}" stroke-width="1.6"/>
</g>
</defs>
<rect width="1200" height="300" fill="{c['bg']}"/>
<rect x="64" y="72" width="40" height="4" fill="{c['green']}"/>
<text class="n" x="64" y="132" font-size="46" fill="{c['ink']}">{NAME}</text>
<text class="s" x="64" y="176" font-size="25" fill="{c['ink']}">{TITLE}</text>
<text class="s" x="64" y="210" font-size="19" fill="{c['muted']}">{LINE}</text>
<text class="m" x="64" y="252" font-size="13" fill="{c['green_text']}" letter-spacing=".5">{TAG}</text>
<g transform="translate({ox} {oy})">
<rect x="0" y="0" width="460" height="250" fill="url(#g)"/>
<g mask="url(#seen)">{anim("opacity", "1;1;.3;.3;0;0", (0, 13.0, 15.0, SHOW_END, RESET, CYCLE))}
<path d="{walls}" fill="none" stroke="{c['faint']}" stroke-opacity=".14" stroke-width="2" stroke-linecap="square"/>
<path d="{map_points()}" fill="{c['blue']}" fill-opacity=".8"/>
</g>
<g mask="url(#ink)">{anim("opacity", "1;1;0;0", (0, SHOW_END, RESET, CYCLE))}<path d="{"".join(ink_dots)}" fill="{c['green']}"/></g>
{"".join(items)}
{"".join(bots)}
{captions}
</g>
</svg>
'''


# ---------------------------------------------------------------- icons
def icon(kind, theme):
    c = THEMES[theme]
    ink, g, b = c["ink"], c["green"], c["blue"]
    sw = 'stroke-width="2" fill="none" stroke-linecap="square"'
    body = {
        "multi-robot": (
            f'<path d="M14 16L34 16M14 16L24 34M34 16L24 34" stroke="{b}" stroke-width="1.6" stroke-dasharray="2 3" fill="none"/>'
            f'<rect x="8" y="11" width="12" height="10" {sw} stroke="{ink}"/>'
            f'<rect x="28" y="11" width="12" height="10" {sw} stroke="{ink}"/>'
            f'<rect x="18" y="29" width="12" height="10" {sw} stroke="{g}"/>'),
        "navigation": (
            f'<path d="M6 42V6M6 42H42" {sw} stroke="{ink}" stroke-opacity=".5"/>'
            f'<path d="M12 36L12 24Q12 20 16 20L28 20Q32 20 32 16L32 10" {sw} stroke="{g}"/>'
            f'<rect x="9" y="33" width="6" height="6" fill="{g}"/>'
            f'<path d="M28 13L32 7L36 13" {sw} stroke="{g}"/>'),
        "perception": (
            f'<rect x="20" y="20" width="8" height="8" {sw} stroke="{g}"/>'
            f'<path d="M24 10A14 14 0 0 1 38 24M24 38A14 14 0 0 1 10 24" {sw} stroke="{ink}"/>'
            + "".join(f'<rect x="{24 + 19 * math.cos(math.radians(a)) - 1.2:.1f}" y="{24 + 19 * math.sin(math.radians(a)) - 1.2:.1f}" width="2.4" height="2.4" fill="{b}"/>'
                      for a in range(-80, 270, 22))),
        "edge-ci": (
            f'<rect x="13" y="13" width="22" height="22" {sw} stroke="{ink}"/>'
            f'<path d="M19 13V7M24 13V7M29 13V7M19 41V35M24 41V35M29 41V35M13 19H7M13 24H7M13 29H7M41 19H35M41 24H35M41 29H35" stroke="{ink}" stroke-width="2" fill="none"/>'
            f'<path d="M18.5 24.5L22.5 28.5L30 20" {sw} stroke="{g}"/>'),
    }[kind]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
            f'{body}</svg>\n')


def main():
    ASSETS.mkdir(exist_ok=True)
    fonts = font_css()
    for theme in THEMES:
        (ASSETS / f"banner-{theme}.svg").write_text(banner(theme, fonts))
        for kind in ("multi-robot", "navigation", "perception", "edge-ci"):
            (ASSETS / f"icon-{kind}-{theme}.svg").write_text(icon(kind, theme))
    for p in sorted(ASSETS.glob("*.svg")):
        print(f"{p.stat().st_size:>7}  {p.name}")


if __name__ == "__main__":
    main()
