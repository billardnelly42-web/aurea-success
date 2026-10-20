#!/usr/bin/env python3
"""Rendu des visuels Aurea Success (1080x1350) : Pensée du jour + Note.

Usage:
  python3 render_aurea.py content.json out_dir [--fonts DIR] [--theme light|dark]

content.json :
{
  "date": "2026-10-20",
  "page": 1,
  "pensee": "Texte ... <mark>phrase clé</mark> suite.",
  "note_titre": "(facultatif) Phrase-choc de la note",
  "note_texte": "(facultatif) Développement de la note."
}
Produit out_dir/<date>-pensee.png et out_dir/<date>-pensee.jpg (et out_dir/<date>-note.png si la note est fournie).
Reproduit les templates Main.dc.html / Citation1.dc.html du canvas Aurea Success.
"""
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
PAD_TOP, PAD_X, PAD_BOTTOM = 88, 96, 160
CONTENT_W = W - 2 * PAD_X
FOOTER_H = 120

CREAM = (0xED, 0xE7, 0xD6)
CREAM_LIGHT = (0xF6, 0xF1, 0xE3)
INK = (0x0B, 0x0C, 0x0A)
OLIVE = (0x2E, 0x33, 0x28)
GOLD = (0xC9, 0xA8, 0x4C)
GOLD_LIGHT = (0xD8, 0xBE, 0x65)
MARK_INK = INK  # couleur du texte surligné (toujours sombre sur l'or)


def set_theme(name):
    """'light' (crème, défaut) ou 'dark' (DA Aurea sombre)."""
    global CREAM, CREAM_LIGHT, INK, OLIVE
    if name == "dark":
        CREAM = (0x0B, 0x0C, 0x0A)
        CREAM_LIGHT = (0x2E, 0x33, 0x28)
        INK = (0xED, 0xE7, 0xD6)
        OLIVE = (0xB8, 0xB3, 0x9F)
    else:
        CREAM = (0xED, 0xE7, 0xD6)
        CREAM_LIGHT = (0xF6, 0xF1, 0xE3)
        INK = (0x0B, 0x0C, 0x0A)
        OLIVE = (0x2E, 0x33, 0x28)

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def fonts_dir(argv):
    if "--fonts" in argv:
        return argv[argv.index("--fonts") + 1]
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


class Fonts:
    def __init__(self, d):
        self.d = d

    def cormorant(self, size, weight=500, italic=False):
        name = "CormorantGaramond-Italic.ttf" if italic else "CormorantGaramond.ttf"
        f = ImageFont.truetype(os.path.join(self.d, name), size)
        f.set_variation_by_axes([weight])
        return f

    def rajdhani(self, size):
        return ImageFont.truetype(os.path.join(self.d, "Rajdhani-SemiBold.ttf"), size)


def background():
    """Crème + halo radial (ellipse 72% x 52% centrée à 50% / 44%)."""
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = 0.5 * W, 0.44 * H
    rx, ry = 0.72 * W, 0.52 * H
    d = np.sqrt(((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2)
    a = np.clip(1.0 - d / 0.72, 0.0, 1.0)[..., None]
    base = np.array(CREAM, dtype=np.float32)
    light = np.array(CREAM_LIGHT, dtype=np.float32)
    img = base * (1 - a) + light * a
    return Image.fromarray(img.astype(np.uint8), "RGB")


def draw_tracked(draw, x, y, text, font, fill, spacing):
    """Texte avec letter-spacing CSS (espacement ajouté après chaque caractère)."""
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + spacing
    return x


def tracked_width(text, font, spacing):
    return sum(font.getlength(ch) + spacing for ch in text)


def tokenize(text):
    """Découpe en mots avec indicateur <mark>."""
    tokens = []
    for part, in_mark in _split_marks(text):
        for word in part.split():
            tokens.append((word, in_mark))
    return tokens


def _split_marks(text):
    out = []
    pos = 0
    for m in re.finditer(r"<mark>(.*?)</mark>", text, flags=re.S):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(1), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out


MARK_PAD = 10   # padding horizontal du <mark>
MARK_MARGIN = -4  # margin horizontal du <mark>


def line_width(words, font_normal, font_mark, space_w):
    """Largeur d'une ligne, en comptant le padding+margin des fragments surlignés."""
    w = 0.0
    prev_mark = None
    for i, (word, mark) in enumerate(words):
        f = font_mark if mark else font_normal
        if i > 0:
            w += space_w
        if mark and prev_mark is not True:
            w += MARK_PAD + MARK_MARGIN
        w += f.getlength(word)
        if mark and (i == len(words) - 1 or not words[i + 1][1]):
            w += MARK_PAD + MARK_MARGIN
        prev_mark = mark
    return w


def wrap(tokens, font_normal, font_mark, max_w):
    space_w = font_normal.getlength(" ")
    lines, cur = [], []
    for tok in tokens:
        trial = cur + [tok]
        if cur and line_width(trial, font_normal, font_mark, space_w) > max_w:
            lines.append(cur)
            cur = [tok]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def draw_paragraph(img, draw, x0, y_top, lines, font_normal, font_mark, line_h, color, mark_pad):
    """Dessine des lignes ; retourne la hauteur occupée. Surlignage = zone de contenu de la police."""
    asc, desc = font_normal.getmetrics()
    asc_m, desc_m = font_mark.getmetrics()
    space_w = font_normal.getlength(" ")
    y = y_top
    for words in lines:
        half_leading = (line_h - (asc + desc)) / 2
        baseline = y + half_leading + asc
        # 1) rectangles de surlignage
        x = x0
        i = 0
        while i < len(words):
            word, mark = words[i]
            if i > 0:
                x += space_w
            if mark:
                seg_start = x
                run_w = 0.0
                j = i
                while j < len(words) and words[j][1]:
                    if j > i:
                        run_w += space_w
                    run_w += font_mark.getlength(words[j][0])
                    j += 1
                rect_x0 = seg_start + MARK_MARGIN
                rect_x1 = seg_start + MARK_MARGIN + mark_pad + run_w + mark_pad
                top = baseline - asc_m
                bottom = baseline + desc_m
                draw.rounded_rectangle([rect_x0, top, rect_x1, bottom], radius=4, fill=GOLD_LIGHT)
                x = seg_start + (mark_pad + MARK_MARGIN) + run_w + (mark_pad + MARK_MARGIN)
                i = j
            else:
                x += font_normal.getlength(word)
                i += 1
        # 2) texte
        x = x0
        i = 0
        while i < len(words):
            word, mark = words[i]
            if i > 0:
                x += space_w
            if mark:
                x += mark_pad + MARK_MARGIN
                j = i
                while j < len(words) and words[j][1]:
                    if j > i:
                        x += space_w
                    draw.text((x, baseline), words[j][0], font=font_mark, fill=MARK_INK, anchor="ls")
                    x += font_mark.getlength(words[j][0])
                    j += 1
                x += mark_pad + MARK_MARGIN
                i = j
            else:
                draw.text((x, baseline), word, font=font_normal, fill=color, anchor="ls")
                x += font_normal.getlength(word)
                i += 1
        y += line_h
    return y - y_top


def frame(fonts, header_right):
    img = background()
    draw = ImageDraw.Draw(img)
    f_label = fonts.rajdhani(22)
    # En-tête
    label_h = 28  # line box approx de Rajdhani 22px
    draw_tracked(draw, PAD_X, PAD_TOP + 3, "AUREA SUCCESS", f_label, OLIVE, 6)
    w = tracked_width(header_right.upper(), f_label, 6)
    draw_tracked(draw, W - PAD_X - w + 6, PAD_TOP + 3, header_right.upper(), f_label, OLIVE, 6)
    rule_y = PAD_TOP + label_h + 28
    draw.rectangle([PAD_X, rule_y, W - PAD_X, rule_y], fill=GOLD)
    # Pied de page
    foot_top = H - FOOTER_H
    draw.rectangle([PAD_X, foot_top, W - PAD_X, foot_top], fill=GOLD)
    mid = foot_top + FOOTER_H / 2
    draw_tracked(draw, PAD_X, mid - 14, "@AUREA.SUCCESS", f_label, OLIVE, 5)
    f_aurea = fonts.cormorant(32, 600)
    aw = tracked_width("AUREA", f_aurea, 9)
    draw_tracked(draw, W - PAD_X - aw + 9, mid - 18, "AUREA", f_aurea, INK, 9)
    content_top = rule_y + 1
    content_bottom = H - PAD_BOTTOM
    return img, draw, content_top, content_bottom


def render_pensee(fonts, date_label, page, text):
    img, draw, c_top, c_bottom = frame(fonts, f"Page {page}")
    f_date = fonts.rajdhani(26)
    f_title = fonts.cormorant(92, 500, italic=True)
    f_body = fonts.cormorant(54, 500)
    f_body_m = fonts.cormorant(54, 600)
    body_lh = round(54 * 1.32)
    lines = wrap(tokenize(text), f_body, f_body_m, CONTENT_W)
    date_h, title_h = 34, round(92 * 1.05)
    block_h = date_h + 12 + title_h + 36 + 2 + 44 + body_lh * len(lines)
    y = c_top + (c_bottom - c_top - block_h) / 2
    draw_tracked(draw, PAD_X, y + 4, date_label.upper(), f_date, OLIVE, 5)
    y += date_h + 12
    asc, desc = f_title.getmetrics()
    draw.text((PAD_X - 2, y + (title_h - (asc + desc)) / 2 + asc), "Pensée du jour", font=f_title, fill=INK, anchor="ls")
    y += title_h + 36
    draw.rectangle([PAD_X, y, PAD_X + 72, y + 2], fill=GOLD)
    y += 2 + 44
    draw_paragraph(img, draw, PAD_X, y, lines, f_body, f_body_m, body_lh, INK, MARK_PAD)
    return img


def render_note(fonts, num, titre, texte):
    img, draw, c_top, c_bottom = frame(fonts, f"Note {num}")
    f_h = fonts.cormorant(66, 600)
    h_lh = round(66 * 1.28)
    f_body = fonts.cormorant(52, 500)
    body_lh = round(52 * 1.32)
    h_lines = wrap(tokenize(f"<mark>{titre}</mark>"), f_h, f_h, CONTENT_W)
    b_lines = wrap(tokenize(texte), f_body, f_body, CONTENT_W)
    block_h = h_lh * len(h_lines) + 44 + 2 + 40 + body_lh * len(b_lines)
    y = c_top + (c_bottom - c_top - block_h) / 2
    draw_paragraph(img, draw, PAD_X, y, h_lines, f_h, f_h, h_lh, INK, 12)
    y += h_lh * len(h_lines) + 44
    draw.rectangle([PAD_X, y, PAD_X + 72, y + 2], fill=GOLD)
    y += 2 + 40
    draw_paragraph(img, draw, PAD_X, y, b_lines, f_body, f_body, body_lh, INK, MARK_PAD)
    return img


def date_label(iso):
    import datetime as dt
    d = dt.date.fromisoformat(iso)
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        sys.exit(1)
    content = json.load(open(argv[1], encoding="utf-8"))
    out_dir = argv[2]
    if "--theme" in argv:
        set_theme(argv[argv.index("--theme") + 1])
    os.makedirs(out_dir, exist_ok=True)
    fonts = Fonts(fonts_dir(argv))
    date = content["date"]
    page = int(content["page"])
    p = render_pensee(fonts, date_label(date), page, content["pensee"])
    p_path = os.path.join(out_dir, f"{date}-pensee.png")
    p.save(p_path, "PNG", optimize=True)
    print(p_path)
    # JPEG pour la publication (TikTok refuse le PNG ; Instagram accepte les deux)
    j_path = os.path.join(out_dir, f"{date}-pensee.jpg")
    p.convert("RGB").save(j_path, "JPEG", quality=95, optimize=True, subsampling=0)
    print(j_path)
    # La Note est facultative : rendue seulement si les deux champs sont fournis.
    if content.get("note_titre") and content.get("note_texte"):
        n = render_note(fonts, page, content["note_titre"], content["note_texte"])
        n_path = os.path.join(out_dir, f"{date}-note.png")
        n.save(n_path, "PNG", optimize=True)
        print(n_path)


if __name__ == "__main__":
    main(sys.argv)
