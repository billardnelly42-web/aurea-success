import json, os, re, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
# Usage : python3 -I pensee.py content.json out_dir fonts_dir
W, H = 1080, 1350
PX, CW = 96, 1080 - 192
CREAM, LIGHT = (237, 231, 214), (246, 241, 227)
INK, OLIVE, GOLD, GOLDL = (11, 12, 10), (46, 51, 40), (201, 168, 76), (216, 190, 101)
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
content, out_dir, fd = json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2], sys.argv[3]

def corm(size, weight=500, italic=False):
    f = ImageFont.truetype(os.path.join(fd, "CormorantGaramond-Italic.ttf" if italic else "CormorantGaramond.ttf"), size)
    f.set_variation_by_axes([weight]); return f
def raj(size): return ImageFont.truetype(os.path.join(fd, "Rajdhani-SemiBold.ttf"), size)
def tracked(draw, x, y, text, font, fill, sp):
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill); x += font.getlength(ch) + sp
def twidth(text, font, sp): return sum(font.getlength(c) + sp for c in text)
def tokens(text):
    out, pos = [], 0
    for m in re.finditer(r"<mark>(.*?)</mark>", text, flags=re.S):
        out += [(w, False) for w in text[pos:m.start()].split()]
        out += [(w, True) for w in m.group(1).split()]; pos = m.end()
    out += [(w, False) for w in text[pos:].split()]
    return out
PAD, MAR = 10, -4
def lwidth(words, fn, fm, sw):
    w, prev = 0.0, None
    for i, (word, mk) in enumerate(words):
        if i > 0: w += sw
        if mk and prev is not True: w += PAD + MAR
        w += (fm if mk else fn).getlength(word)
        if mk and (i == len(words) - 1 or not words[i + 1][1]): w += PAD + MAR
        prev = mk
    return w
def wrap(toks, fn, fm, maxw):
    sw, lines, cur = fn.getlength(" "), [], []
    for t in toks:
        if cur and lwidth(cur + [t], fn, fm, sw) > maxw: lines.append(cur); cur = [t]
        else: cur = cur + [t]
    if cur: lines.append(cur)
    return lines
def paragraph(draw, x0, y, lines, fn, fm, lh):
    asc, desc = fn.getmetrics(); am, dm = fm.getmetrics(); sw = fn.getlength(" ")
    for words in lines:
        base = y + (lh - (asc + desc)) / 2 + asc
        for pass_ in (0, 1):
            x, i = x0, 0
            while i < len(words):
                word, mk = words[i]
                if i > 0: x += sw
                if mk:
                    j, run = i, 0.0
                    while j < len(words) and words[j][1]:
                        run += (sw if j > i else 0) + fm.getlength(words[j][0]); j += 1
                    if pass_ == 0:
                        draw.rounded_rectangle([x + MAR, base - am, x + MAR + PAD + run + PAD, base + dm], radius=4, fill=GOLDL)
                    else:
                        xx = x + PAD + MAR
                        for k in range(i, j):
                            if k > i: xx += sw
                            draw.text((xx, base), words[k][0], font=fm, fill=INK, anchor="ls"); xx += fm.getlength(words[k][0])
                    x += (PAD + MAR) + run + (PAD + MAR); i = j
                else:
                    if pass_ == 1: draw.text((x, base), word, font=fn, fill=INK, anchor="ls")
                    x += fn.getlength(word); i += 1
        y += lh
ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
d = np.sqrt(((xs - 0.5 * W) / (0.72 * W)) ** 2 + ((ys - 0.44 * H) / (0.52 * H)) ** 2)
a = np.clip(1.0 - d / 0.72, 0, 1)[..., None]
img = Image.fromarray((np.array(CREAM, dtype=np.float32) * (1 - a) + np.array(LIGHT, dtype=np.float32) * a).astype(np.uint8), "RGB")
draw = ImageDraw.Draw(img)
fl = raj(22); page = int(content["page"]); date = content["date"]
tracked(draw, PX, 91, "AUREA SUCCESS", fl, OLIVE, 6)
hr = f"PAGE {page}"; tracked(draw, W - PX - twidth(hr, fl, 6) + 6, 91, hr, fl, OLIVE, 6)
draw.rectangle([PX, 144, W - PX, 144], fill=GOLD)
draw.rectangle([PX, H - 120, W - PX, H - 120], fill=GOLD)
tracked(draw, PX, H - 60 - 14, "@AUREA.SUCCESS", fl, OLIVE, 5)
fa = corm(32, 600); tracked(draw, W - PX - twidth("AUREA", fa, 9) + 9, H - 60 - 18, "AUREA", fa, INK, 9)
import datetime as dt
dd = dt.date.fromisoformat(date); label = f"{JOURS[dd.weekday()]} {dd.day} {MOIS[dd.month - 1]} {dd.year}".upper()
fb, fbm, ft = corm(54, 500), corm(54, 600), corm(92, 500, True)
lh = round(54 * 1.32); lines = wrap(tokens(content["pensee"]), fb, fbm, CW)
th = round(92 * 1.05); block = 34 + 12 + th + 36 + 2 + 44 + lh * len(lines)
y = 145 + (H - 160 - 145 - block) / 2
tracked(draw, PX, y + 4, label, raj(26), OLIVE, 5); y += 46
asc, desc = ft.getmetrics(); draw.text((PX - 2, y + (th - (asc + desc)) / 2 + asc), "Pensée du jour", font=ft, fill=INK, anchor="ls")
y += th + 36; draw.rectangle([PX, y, PX + 72, y + 2], fill=GOLD); y += 46
paragraph(draw, PX, y, lines, fb, fbm, lh)
os.makedirs(out_dir, exist_ok=True)
img.save(os.path.join(out_dir, f"{date}-pensee.png"), "PNG", optimize=True)
img.save(os.path.join(out_dir, f"{date}-pensee.jpg"), "JPEG", quality=95, optimize=True, subsampling=0)
print(os.path.join(out_dir, f"{date}-pensee.jpg"))
