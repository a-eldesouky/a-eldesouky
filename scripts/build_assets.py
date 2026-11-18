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
CAPTION = "/map  /scan  /plan"


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
        ("PPlexMono", FONT_DIR / "IBMPlexMono-SemiBold.ttf", TAG + CAPTION, None),
    ]
    out = []
    for fam, path, text, w in faces:
        data = font_b64(path, text, w)
        out.append(f"@font-face{{font-family:{fam};src:url(data:font/woff2;base64,{data}) format('woff2')}}")
    return "".join(out)


# ---------------------------------------------------------------- scene
# Local scene coordinates (0..460 x 0..250), translated into the banner.
WALLS = [
    ((10, 10), (450, 10)), ((450, 10), (450, 240)), ((450, 240), (10, 240)), ((10, 240), (10, 10)),
    ((160, 10), (160, 140)),           # inner wall, top
    ((300, 110), (300, 240)),          # inner wall, bottom
]
BOXES = [(212, 34, 44, 30), (372, 46, 34, 34), (60, 120, 40, 26)]
for x, y, w, h in BOXES:
    WALLS += [((x, y), (x + w, y)), ((x + w, y), (x + w, y + h)),
              ((x + w, y + h), (x, y + h)), ((x, y + h), (x, y))]

PATH_A = [(40, 200), (230, 200), (230, 88), (340, 88), (400, 160)]
PATH_B = [(124, 40), (124, 96), (40, 96)]


def rounded_path(pts, r=18):
    d = [f"M{pts[0][0]} {pts[0][1]}"]
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1, l2 = math.dist((x0, y0), (x1, y1)), math.dist((x1, y1), (x2, y2))
        rr = min(r, l1 / 2, l2 / 2)
        a = (x1 - (x1 - x0) / l1 * rr, y1 - (y1 - y0) / l1 * rr)
        b = (x1 + (x2 - x1) / l2 * rr, y1 + (y2 - y1) / l2 * rr)
        d.append(f"L{a[0]:.1f} {a[1]:.1f}Q{x1} {y1} {b[0]:.1f} {b[1]:.1f}")
    d.append(f"L{pts[-1][0]} {pts[-1][1]}")
    return "".join(d)


def ray_hit(o, ang, max_r=270):
    dx, dy = math.cos(ang), math.sin(ang)
    best = None
    for (x1, y1), (x2, y2) in WALLS:
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-9:
            continue
        t = ((x1 - o[0]) * ey - (y1 - o[1]) * ex) / den
        u = ((x1 - o[0]) * dy - (y1 - o[1]) * dx) / den
        if t > 0 and 0 <= u <= 1 and (best is None or t < best):
            best = t
    return best if best is not None and best < max_r else None


def scan_points(o, step_deg=2.0):
    rng = random.Random(7)
    pts = []
    a = 0.0
    while a < 360:
        t = ray_hit(o, math.radians(a))
        if t is not None:
            t += rng.gauss(0, 0.9)
            pts.append((o[0] + t * math.cos(math.radians(a)), o[1] + t * math.sin(math.radians(a))))
        a += step_deg
    return pts


def robot(x, y, heading_deg, stroke, fill):
    return (f'<g transform="translate({x} {y}) rotate({heading_deg:.1f})">'
            f'<rect x="-10" y="-7" width="20" height="14" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
            f'<path d="M3 -3.5L8 0L3 3.5" fill="none" stroke="{stroke}" stroke-width="1.6"/></g>')


def banner(theme, fonts):
    c = THEMES[theme]
    ox, oy = 708, 25
    end = PATH_A[-1]
    prev = PATH_A[-2]
    heading = math.degrees(math.atan2(end[1] - prev[1], end[0] - prev[0]))
    scan = scan_points(end)
    dots = "".join(f'<rect x="{x - 1.1:.1f}" y="{y - 1.1:.1f}" width="2.2" height="2.2"/>' for x, y in scan)
    walls = "".join(f"M{a[0]} {a[1]}L{b[0]} {b[1]}" for a, b in WALLS)
    rays = "".join(f"M{end[0]} {end[1]}L{x:.0f} {y:.0f}" for i, (x, y) in enumerate(scan) if i % 9 == 0)
    corners = "".join(f'<rect x="{x - 3}" y="{y - 3}" width="6" height="6"/>' for x, y in PATH_A[1:-1])
    b_end, b_prev = PATH_B[-1], PATH_B[-2]
    b_heading = math.degrees(math.atan2(b_end[1] - b_prev[1], b_end[0] - b_prev[0]))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300" role="img" aria-labelledby="t d">
<title id="t">{NAME}</title>
<desc id="d">{TITLE}. {LINE}. Top-down drawing of a robot path with LiDAR scan points.</desc>
<style>{fonts}
.n{{font-family:PAlexandria,Alexandria,'Segoe UI',Helvetica,Arial,sans-serif;font-weight:600}}
.s{{font-family:PPlexSans,'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif}}
.m{{font-family:PPlexMono,'IBM Plex Mono',SFMono-Regular,Consolas,'Liberation Mono',monospace;font-weight:600}}
.path{{stroke-dasharray:100;animation:draw 7s cubic-bezier(.45,0,.25,1) .4s both}}
.late{{animation:fade 1.2s ease-out 6.6s both}}
.robot{{animation:fade .6s ease-out 7.2s both}}
@keyframes draw{{from{{stroke-dashoffset:100}}to{{stroke-dashoffset:0}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@media (prefers-reduced-motion:reduce){{.path,.late,.robot{{animation:none}}}}
</style>
<defs><pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="{c['faint']}" stroke-opacity=".06" stroke-width="1"/></pattern></defs>
<rect width="1200" height="300" fill="{c['bg']}"/>
<rect x="64" y="72" width="40" height="4" fill="{c['green']}"/>
<text class="n" x="64" y="132" font-size="46" fill="{c['ink']}">{NAME}</text>
<text class="s" x="64" y="176" font-size="25" fill="{c['ink']}">{TITLE}</text>
<text class="s" x="64" y="210" font-size="19" fill="{c['muted']}">{LINE}</text>
<text class="m" x="64" y="252" font-size="13" fill="{c['green_text']}" letter-spacing=".5">{TAG}</text>
<g transform="translate({ox} {oy})">
<rect x="0" y="0" width="460" height="250" fill="url(#g)"/>
<path d="{walls}" fill="none" stroke="{c['faint']}" stroke-opacity=".16" stroke-width="2" stroke-linecap="square"/>
<path d="{rounded_path(PATH_B)}" fill="none" stroke="{c['faint']}" stroke-opacity=".35" stroke-width="1.6" stroke-dasharray="4 5"/>
<g stroke="{c['faint']}" stroke-opacity=".35">{robot(*b_end, b_heading, c['faint'], c['robot_fill'])}</g>
<path class="path" pathLength="100" d="{rounded_path(PATH_A)}" fill="none" stroke="{c['green']}" stroke-width="2.4" stroke-linecap="square"/>
<g class="late" fill="none" stroke="{c['green']}" stroke-width="1.4">{corners}</g>
<rect x="{PATH_A[0][0] - 4}" y="{PATH_A[0][1] - 4}" width="8" height="8" fill="{c['green']}"/>
<g class="late"><path d="{rays}" stroke="{c['blue']}" stroke-opacity=".12" stroke-width="1"/>
<g fill="{c['blue']}">{dots}</g></g>
<g class="robot">{robot(*end, heading, c['green'], c['robot_fill'])}</g>
<text class="m" x="456" y="268" font-size="11" fill="{c['muted']}" text-anchor="end" letter-spacing=".5">{CAPTION}</text>
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
