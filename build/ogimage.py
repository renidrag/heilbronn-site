"""Social preview cards (og:image): a 1200×630 PNG per configuration, drawn
from that configuration's own figure.svg so the card and the page figure
can never disagree. Pillow only — no SVG rasterizer or system libraries.
Light-theme colors; link previews have no dark mode."""

import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
SS = 2                      # supersampling factor (Pillow draws without AA)
FIG = 550                   # figure box, in final pixels
FIG_X, FIG_Y = 40, (H - FIG) // 2
TEXT_X = 650

BG = "#fdfcfa"
FG = "#1c1c22"
MUTED = "#6a6a72"
ACCENT = "#b33c1a"
DOMAIN = "#a9a49b"
POINT = "#23232b"
POINT_RING = "#fdfcfa"

NS = "{http://www.w3.org/2000/svg}"


def _font(size):
    return ImageFont.load_default(size=size * SS)


def _pts(attr, scale, ox, oy):
    nums = [float(t) for t in re.split(r"[ ,]+", attr.strip())]
    return [(ox + nums[i] * scale, oy + nums[i + 1] * scale)
            for i in range(0, len(nums), 2)]


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def _draw_figure(img, svg_text):
    root = ET.fromstring(svg_text)
    style = root.find(f"{NS}style").text
    # Light palette: the first rule for each class wins (dark rules follow
    # inside the media query).
    colors = {}
    for k, c in re.findall(r"\.cc-(\d+)\{fill:(#[0-9a-f]{6})", style):
        colors.setdefault(k, c)
    vb = [float(t) for t in root.get("viewBox").split()]
    scale = FIG * SS / max(vb[2], vb[3])
    ox = FIG_X * SS + (FIG * SS - vb[2] * scale) / 2
    oy = FIG_Y * SS + (FIG * SS - vb[3] * scale) / 2

    groups = {g.get("class"): g for g in root.iter(f"{NS}g")}
    # Minimal triangles at fill-opacity .3, composited one by one so overlaps
    # darken as they do in the SVG.
    for poly in groups["mintris"].iter(f"{NS}polygon"):
        k = re.search(r"cc-(\d+)", poly.get("class")).group(1)
        tri = _pts(poly.get("points"), scale, ox, oy)
        x0, y0 = int(min(p[0] for p in tri)) - 4, int(min(p[1] for p in tri)) - 4
        x1, y1 = int(max(p[0] for p in tri)) + 5, int(max(p[1] for p in tri)) + 5
        patch = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        local = [(x - x0, y - y0) for x, y in tri]
        ImageDraw.Draw(patch).polygon(local, fill=_rgba(colors[k], 77))
        ImageDraw.Draw(patch).line(local + local[:1], fill=_rgba(colors[k], 255),
                                   width=round(2 * scale), joint="curve")
        img.alpha_composite(patch, dest=(x0, y0))

    draw = ImageDraw.Draw(img)
    for poly in groups["domain"].iter(f"{NS}polygon"):
        outline = _pts(poly.get("points"), scale, ox, oy)
        draw.line(outline + outline[:1], fill=DOMAIN, width=round(2.5 * scale) or 1,
                  joint="curve")
    for c in groups["points"].iter(f"{NS}circle"):
        cx = ox + float(c.get("cx")) * scale
        cy = oy + float(c.get("cy")) * scale
        r = float(c.get("r")) * scale * 1.6   # a 550px card needs bolder dots
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=POINT,
                     outline=POINT_RING, width=round(2.5 * scale * 1.6))


def card(svg_text, heading, value, status, footer):
    """Render one preview card; returns a PIL image (RGB, 1200×630)."""
    img = Image.new("RGBA", (W * SS, H * SS), BG)
    _draw_figure(img, svg_text)
    draw = ImageDraw.Draw(img)
    y = 150 * SS
    draw.text((TEXT_X * SS, y), "The Heilbronn problem", font=_font(32), fill=MUTED)
    y += 64 * SS
    draw.text((TEXT_X * SS, y), heading, font=_font(62), fill=FG)
    y += 100 * SS
    draw.text((TEXT_X * SS, y), value, font=_font(40), fill=FG)
    y += 66 * SS
    draw.text((TEXT_X * SS, y), status, font=_font(30), fill=ACCENT)
    draw.text((TEXT_X * SS, (H - 70) * SS), footer, font=_font(26), fill=MUTED)
    return img.resize((W, H), Image.LANCZOS).convert("RGB")


def _quantize(img, colors=112):
    """Palette PNG at a third the size of truecolor. The text colors get
    reserved slots: median cut alone drops the accent on single-hue figures."""
    pal = img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).getpalette()
    pal = pal[: colors * 3]
    for c in (BG, FG, MUTED, ACCENT):
        pal += list(_rgba(c, 0)[:3])
    ref = Image.new("P", (1, 1))
    ref.putpalette(pal)
    return img.quantize(palette=ref, dither=Image.Dither.NONE)


def write_card(path, svg_text, heading, value, status,
               footer="math.tejstead.com/heilbronn"):
    _quantize(card(svg_text, heading, value, status, footer)).save(path, optimize=True)
