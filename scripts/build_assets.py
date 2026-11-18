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
CAPTION = "exploring  /  building the map r1 patrol r2 inspect r3 survey meeting up together"


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
# One 24 s loop, all animations share it:
#   0-9 s   explore: robots leave the dock; the map appears where they drive
#   ~6-15 s jobs:    r1 patrols, r2 inspects a crate, r3 surveys a corner
#   15-18 s meet:    robots park around the centre
#   18-22 s build:   each robot places its share of the DesBot mark's dots
#   22-24 s reset:   mark and map fade, robots return to the dock
CYCLE = 24.0
WALLS = [
    ((10, 10), (450, 10)), ((450, 10), (450, 240)), ((450, 240), (10, 240)), ((10, 240), (10, 10)),
    ((160, 10), (160, 140)),           # inner wall, top
    ((300, 110), (300, 240)),          # inner wall, bottom
]
BOXES = [(212, 34, 44, 30), (372, 46, 34, 34), (60, 120, 40, 26)]
for x, y, w, h in BOXES:
    WALLS += [((x, y), (x + w, y)), ((x + w, y), (x + w, y + h)),
              ((x + w, y + h), (x, y + h)), ((x, y + h), (x, y))]

SPEED = 86.0  # px/s while exploring
EXPLORE = [
    [(34, 224), (150, 212), (240, 212), (240, 88), (190, 88), (190, 40)],
    [(34, 200), (34, 36), (136, 36), (136, 100)],
    [(60, 230), (282, 230), (282, 96), (330, 96), (430, 96), (430, 222), (330, 222)],
]
# After exploring: (time, point) waypoints for each robot's own job, the meeting and the return.
LOGO_C, LOGO_S = (232, 128), 0.75
PARK = [(170, 128), (292, 70), (292, 188)]
AFTER = [
    [(8.0, (190, 120)), (10.0, (190, 40)), (12.0, (190, 120)), (14.0, (190, 40)), (15.0, (190, 40)),
     (17.0, PARK[0]), (22.6, PARK[0])],
    [(6.5, (80, 106)), (14.5, (80, 106)), (15.5, (120, 160)), (16.5, (200, 160)), (17.6, PARK[1]),
     (22.6, PARK[1])],
    [(10.2, (330, 150)), (11.4, (389, 98)), (14.6, (389, 98)), (15.6, (310, 96)), (16.4, (292, 104)),
     (17.6, PARK[2]), (22.6, PARK[2])],
]
JOBS = ["patrol", "inspect", "survey"]


def timeline(i):
    pts = EXPLORE[i]
    t, out = 0.0, [(0.0, pts[0])]
    for a, b in zip(pts, pts[1:]):
        t += math.dist(a, b) / SPEED
        out.append((t, b))
    explore_end = t
    out += AFTER[i]
    out.append((CYCLE, pts[0]))
    return out, explore_end


def motion_attrs(tl):
    """Polyline path plus keyPoints/keyTimes so the robot is at each waypoint on time."""
    d = [f"M{tl[0][1][0]} {tl[0][1][1]}"]
    cum = [0.0]
    for (_, a), (_, b) in zip(tl, tl[1:]):
        cum.append(cum[-1] + math.dist(a, b))
        d.append(f"L{b[0]} {b[1]}")
    total = cum[-1]
    kp = ";".join(f"{c / total:.4f}" for c in cum)
    kt = ";".join(f"{t / CYCLE:.4f}" for t, _ in tl)
    return "".join(d), kp, kt


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


# DesBot mark (200x200 source): (x, y, r, opacity). The last dot is the green core.
MARK = (
    [(52.79, y, 2.76, .65) for y in (19.49, 42.49, 65.5, 88.5, 111.5, 134.5, 157.51, 180.51)]
    + [(x, y, 2.3, .685) for x, y in ((74.06, 12.3), (103.11, 22.94), (126.68, 42.78), (142.21, 69.52),
                                      (147.67, 100), (142.21, 130.48), (126.68, 157.22), (103.11, 177.06),
                                      (74.06, 187.7))]
    + [(x, y, 2.76, .86) for x, y in ((70.61, 32.14), (93.04, 40.19), (111.44, 55.72), (123.52, 76.42),
                                      (127.55, 100), (123.52, 123.58), (111.44, 144.28), (93.04, 159.81),
                                      (70.61, 167.86))]
    + [(x, y, 3.22, 1.0) for x, y in ((66.59, 54.57), (81.54, 60.03), (93.9, 70.38), (101.67, 84.19),
                                      (104.54, 100), (101.67, 115.81), (93.9, 129.62), (81.54, 139.97),
                                      (66.59, 145.43))]
)


def kt(*ts):
    return ";".join(f"{t / CYCLE:.4f}" for t in ts)


def logo_dots(c):
    """Each robot carries the dots nearest to it from its parking spot into place."""
    cx, cy = LOGO_C
    placed = []
    for x, y, r, op in MARK:
        px, py = cx + (x - 100) * LOGO_S, cy + (y - 100) * LOGO_S
        owner = 0 if x < 60 else (1 if y < 100 else 2)
        placed.append((owner, px, py, r * LOGO_S * 1.25, op))
    out, count = [], [0, 0, 0]
    for owner, px, py, r, op in sorted(placed, key=lambda p: (p[0], p[2])):
        k = count[owner]
        count[owner] += 1
        start = 18.0 + k * 0.22
        land = start + 0.5
        ox, oy = PARK[owner]
        out.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r:.1f}" fill-opacity="{op}" opacity="0">'
            f'<animateTransform attributeName="transform" type="translate" dur="{CYCLE:g}s" repeatCount="indefinite" '
            f'values="{ox - px:.0f} {oy - py:.0f};{ox - px:.0f} {oy - py:.0f};0 0;0 0" keyTimes="{kt(0, start, land, CYCLE)}"/>'
            f'<animate attributeName="opacity" dur="{CYCLE:g}s" repeatCount="indefinite" '
            f'values="0;0;1;1;0;0" keyTimes="{kt(0, start, start + .1, 22.6, 23.4, CYCLE)}"/></circle>')
    core_x, core_y = cx + (70.04 - 100) * LOGO_S, cy
    out.append(
        f'<circle cx="{core_x:.1f}" cy="{core_y:.1f}" r="{7.48 * LOGO_S:.1f}" fill="{c["green"]}" opacity="0">'
        f'<animate attributeName="opacity" dur="{CYCLE:g}s" repeatCount="indefinite" '
        f'values="0;0;1;1;0;0" keyTimes="{kt(0, 21.0, 21.3, 22.6, 23.4, CYCLE)}"/></circle>')
    return "".join(out)


def phase_text(c, text, t_on, t_off):
    return (f'<text class="m" x="456" y="268" font-size="11" fill="{c["muted"]}" text-anchor="end" '
            f'letter-spacing=".5" opacity="0">{text}<animate attributeName="opacity" dur="{CYCLE:g}s" '
            f'repeatCount="indefinite" values="0;0;1;1;0;0" '
            f'keyTimes="{kt(0, t_on, t_on + .4, t_off - .4, t_off, CYCLE)}"/></text>')


def banner(theme, fonts):
    c = THEMES[theme]
    ox, oy = 708, 25
    walls = "".join(f"M{a[0]} {a[1]}L{b[0]} {b[1]}" for a, b in WALLS)
    reveal, bots = [], []
    for i in range(3):
        tl, explore_end = timeline(i)
        d, kp, ktimes = motion_attrs(tl)
        exp_d = "M" + "L".join(f"{x} {y}" for x, y in EXPLORE[i])
        reveal.append(
            f'<path d="{exp_d}" pathLength="1" stroke-dasharray="1 1" fill="none" stroke="#fff" '
            f'stroke-width="84" stroke-linecap="round" stroke-linejoin="round">'
            f'<animate attributeName="stroke-dashoffset" dur="{CYCLE:g}s" repeatCount="indefinite" '
            f'values="1;0;0;1" keyTimes="{kt(0, explore_end, 23.4, CYCLE)}"/></path>')
        motion = (f'dur="{CYCLE:g}s" repeatCount="indefinite" path="{d}" keyPoints="{kp}" '
                  f'keyTimes="{ktimes}" calcMode="linear"')
        bots.append(
            f'<g><animateMotion {motion} rotate="auto"/><use href="#bot"/></g>'
            f'<g><animateMotion {motion}/>'
            f'<text class="m" x="10" y="-11" font-size="10" fill="{c["green_text"]}">r{i + 1}</text></g>')
    captions = (phase_text(c, "exploring  /  building the map", 0, 7)
                + phase_text(c, "r1 " + JOBS[0] + "  /  r2 " + JOBS[1] + "  /  r3 " + JOBS[2], 7, 15)
                + phase_text(c, "meeting up", 15, 18)
                + phase_text(c, "building together", 18, 23.4))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300" role="img" aria-labelledby="t d">
<title id="t">{NAME}</title>
<desc id="d">{TITLE}. {LINE}. Animated top-down drawing: three robots explore and map a building, split up for separate jobs, then meet and assemble the DesBot logo together.</desc>
<style>{fonts}
.n{{font-family:PAlexandria,Alexandria,'Segoe UI',Helvetica,Arial,sans-serif;font-weight:600}}
.s{{font-family:PPlexSans,'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif}}
.m{{font-family:PPlexMono,'IBM Plex Mono',SFMono-Regular,Consolas,'Liberation Mono',monospace;font-weight:600}}
</style>
<defs>
<pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="{c['faint']}" stroke-opacity=".06" stroke-width="1"/></pattern>
<mask id="seen" maskUnits="userSpaceOnUse" x="0" y="0" width="460" height="250">{"".join(reveal)}</mask>
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
<g mask="url(#seen)"><animate attributeName="opacity" dur="{CYCLE:g}s" repeatCount="indefinite" values="1;1;.28;.28;0;0" keyTimes="{kt(0, 16, 18, 22.6, 23.4, CYCLE)}"/>
<path d="{walls}" fill="none" stroke="{c['faint']}" stroke-opacity=".14" stroke-width="2" stroke-linecap="square"/>
<path d="{map_points()}" fill="{c['blue']}" fill-opacity=".8"/>
</g>
<g fill="{c['blue']}">{logo_dots(c)}</g>
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
