import numpy as np, subprocess, sys, wave
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 30, 17.0
BAR = 64
CW, CH = 14, 24
COLS, ROWS = W // CW, (H - BAR) // CH
OUT = sys.argv[1]
FONT = '/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf'
FONT_R = '/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf'
rng = np.random.default_rng(7)

RAMP = " .`'-:;~=+*!|/\\(){}[]?tfjrxnuvczXYUJCLQ0OZmwqpdbkhao#MW&8%B@"
font = ImageFont.truetype(FONT, 22, layout_engine=ImageFont.Layout.BASIC)
atlas = np.zeros((len(RAMP) + 128, CH, CW), np.float32)
chars = list(RAMP) + [chr(i) if 32 <= i < 127 else ' ' for i in range(128)]
for i, c in enumerate(chars):
    im = Image.new('L', (CW, CH)); ImageDraw.Draw(im).text((0, -2), c, font=font, fill=255)
    atlas[i] = np.asarray(im, np.float32) / 255
ASC = len(RAMP)  # offset for literal ascii

# grid coords (normalized by half width, y down)
cx = (np.arange(COLS) + 0.5) * CW
cy = (np.arange(ROWS) + 0.5) * CH
X, Y = np.meshgrid((cx - W / 2) / (W / 2), (cy - (H - BAR) / 2) / (W / 2))
jit = rng.random((ROWS, COLS))

def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

# ---------- eye ----------
ang_noise = rng.random(720)
def iris_streak(th):
    i = ((th + np.pi) / (2 * np.pi) * 720).astype(int) % 720
    return ang_noise[i] * 0.6 + ang_noise[(i * 3 + 11) % 720] * 0.4

def eye(x, y, t, pupil_r, lid):
    b = np.zeros_like(x); col = np.zeros(x.shape + (3,))
    r = np.hypot(x, y); th = np.arctan2(y, x)
    open_h = 0.62 * lid * np.clip(1 - (x / 1.05) ** 2, 0, None)
    inside = np.abs(y) < open_h
    # skin / background texture
    skin = 0.10 + 0.08 * np.sin(x * 9 + y * 5) + 0.05 * jit
    b[:] = skin; col[:] = (0.75, 0.48, 0.32)
    # sclera
    edge = smooth(0, 0.18, open_h - np.abs(y))
    scl = 0.30 + 0.25 * edge - 0.12 * np.abs(x)
    b = np.where(inside, scl, b); col[inside] = (0.80, 0.70, 0.66)
    # iris
    IR = 0.44
    ir = inside & (r < IR)
    st = iris_streak(th)
    rr = r / IR
    ib = (0.55 + 0.45 * st) * (0.55 + 0.6 * smooth(pupil_r / IR, 0.9, rr) * (1 - smooth(0.85, 1.0, rr)) + 0.2)
    ib *= edge * 0.6 + 0.4
    b = np.where(ir, np.clip(ib, 0, 1), b)
    icol = np.stack([0.98 - 0.2 * rr, 0.62 - 0.25 * rr + 0.1 * st, 0.30 - 0.12 * rr], -1)
    col[ir] = icol[ir]
    # pupil
    pu = inside & (r < pupil_r)
    b = np.where(pu, 0.0, b)
    # highlight
    hl = inside & (np.hypot(x + 0.13, y + 0.12) < 0.06)
    b = np.where(hl, 1.0, b); col[hl] = (1, 1, 0.95)
    return b, col, pu

# ---------- space + heart ----------
NS = 260
sx, sy = rng.uniform(-1.1, 1.1, NS), rng.uniform(-1.9, 1.9, NS)
sph, sbig = rng.uniform(0, 6.28, NS), rng.random(NS)

def beat(t):
    p = (t % 0.95)
    return np.exp(-((p - 0.05) / 0.05) ** 2) + 0.6 * np.exp(-((p - 0.27) / 0.05) ** 2)

def text_mask(lines, height_rows):
    sc = CH / CW
    w, h = COLS, int(height_rows * sc)
    f = ImageFont.truetype(FONT, 10, layout_engine=ImageFont.Layout.BASIC)
    out = []
    for s in lines:
        im = Image.new('L', (w * 4, h * 4))
        d = ImageDraw.Draw(im)
        size = 200
        while True:
            f = ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.BASIC)
            bb = d.textbbox((0, 0), s, font=f)
            if bb[2] - bb[0] < w * 4 * 0.96 and bb[3] - bb[1] < h * 4 * 0.97: break
            size -= 2
        f = ImageFont.truetype('/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-ExtraBold.ttf', size, layout_engine=ImageFont.Layout.BASIC)
        d.text(((w * 4 - (bb[2] - bb[0])) / 2 - bb[0], (h * 4 - (bb[3] - bb[1])) / 2 - bb[1]), s, font=f, fill=255)
        out.append(np.asarray(im.resize((w, height_rows), Image.LANCZOS), np.float32) / 255)
    return out

TXT = text_mask(['TE AMO'], 12) + text_mask(['Getse'], 19)

def space(t, zoom, heart_amt, text_t):
    x, y = X / zoom, Y / zoom
    b = np.zeros_like(X); col = np.zeros(X.shape + (3,)); ch = np.zeros(X.shape, int) - 1
    # stars
    gx = ((sx * zoom) * (W / 2) + W / 2) / CW
    gy = ((sy * zoom) * (W / 2) + (H - BAR) / 2) / CH
    for i in range(NS):
        c, r = int(gx[i]), int(gy[i])
        if not (0 <= c < COLS and 0 <= r < ROWS): continue
        tw = 0.45 + 0.55 * (0.5 + 0.5 * np.sin(t * (2 + sbig[i] * 3) + sph[i]))
        b[r, c] = max(b[r, c], tw); col[r, c] = (1, 0.95, 0.9)
        ch[r, c] = ASC + ord('+' if sbig[i] > 0.75 else ('*' if sbig[i] > 0.5 else '.'))
        if sbig[i] > 0.85 and tw > 0.7:
            for dc, dr, cc in ((-1, 0, '-'), (1, 0, '-'), (0, -1, '|'), (0, 1, '|'), (-2, 0, '-'), (2, 0, '-')):
                if 0 <= c + dc < COLS and 0 <= r + dr < ROWS:
                    b[r + dr, c + dc] = tw * 0.6; col[r + dr, c + dc] = (1, 0.9, 0.95); ch[r + dr, c + dc] = ASC + ord(cc)
    # heart
    if heart_amt > 0:
        s = 0.55 * heart_amt * (1 + 0.07 * beat(t))
        hx, hy = x / s, -(y + 0.62) / s + 0.1
        f = (hx ** 2 + (1.15 * hy - np.sqrt(np.abs(hx)) * 0.85) ** 2 - 1.0) * 0.5
        inside = f < 0
        depth = np.clip(-f * 4, 0, 1) ** 0.35
        light = np.clip(0.55 + 0.45 * (-0.5 * hx + 0.6 * hy), 0, 1)
        bands = 0.82 + 0.18 * np.sin((hy * 9 + t * 2.2))
        hb = np.clip((0.25 + 0.75 * depth) * light * bands + 0.08 * jit, 0, 1)
        spec = np.exp(-(((hx + 0.5) ** 2 + (hy - 0.85) ** 2) / 0.03))
        hb = np.clip(hb + spec, 0, 1)
        hc = np.stack([np.full_like(hx, 1.0), 0.25 + 0.35 * light + 0.4 * spec, 0.45 + 0.25 * light + 0.4 * spec], -1)
        glow = (~inside) & (f < 0.25)
        b = np.where(glow, np.maximum(b, 0.12), b); col[glow] = (1, 0.3, 0.5)
        b = np.where(inside, hb, b); col[inside] = hc[inside]; ch[inside | glow] = -1
    # big ascii text
    if text_t > 0:
        word = '@#%8&B@#M%W8'
        for li, m in enumerate(TXT):
            r0 = [ROWS - 35, ROWS - 22][li]
            reveal = np.clip(text_t * 1.3 - li * 0.6, 0, 1)
            cut = int(COLS * reveal)
            mm = m.copy(); mm[:, cut:] = 0
            on = mm > 0.15
            rs = slice(r0, r0 + m.shape[0])
            sub_b, sub_c, sub_ch = b[rs], col[rs], ch[rs]
            pul = 0.75 + 0.25 * beat(t)
            sub_b[on] = (0.75 + 0.25 * mm[on]) * pul
            sub_c[on] = (1.0, 0.55, 0.75) if li == 0 else (1.0, 0.78, 0.9)
            sub_b[~on] = 0; sub_ch[~on] = -1
            idx = (np.arange(COLS)[None, :] + np.arange(m.shape[0])[:, None] * 3) % len(word)
            lit = np.vectorize(lambda k: ASC + ord(word[k]))(idx)
            sub_ch[on] = lit[on]
    return b, col, ch

# ---------- render ----------
title_font = ImageFont.truetype(FONT_R, 26, layout_engine=ImageFont.Layout.BASIC)
def frame_bg():
    im = Image.new('RGB', (W, H), (12, 12, 16))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, BAR], fill=(232, 232, 236))
    d.text((24, 16), 'Eye -> Heart', font=title_font, fill=(90, 90, 100))
    for i, cx_ in enumerate((W - 150, W - 95, W - 40)):
        d.text((cx_, 14), ['—', '□', '✕'][i], font=title_font, fill=(90, 90, 100))
    return np.asarray(im, np.float32) / 255
BG = frame_bg()

flick = rng.random((ROWS, COLS))
def compose(b, col, ch, t):
    global flick
    if int(t * 12) != int((t - 1 / FPS) * 12):
        m = rng.random((ROWS, COLS)) < 0.15; flick = np.where(m, rng.random((ROWS, COLS)), flick)
    idx = np.clip((b * (len(RAMP) - 1) + (flick - 0.5) * 6), 0, len(RAMP) - 1).astype(int)
    idx = np.where(b < 0.04, 0, idx)
    idx = np.where(ch >= 0, ch, idx)
    g = atlas[idx]  # rows, cols, CH, CW
    inten = (0.35 + 0.75 * np.clip(b, 0, 1))[..., None]
    c = col * inten
    img = g[..., None] * c[:, :, None, None, :]
    img = img.transpose(0, 2, 1, 3, 4).reshape(ROWS * CH, COLS * CW, 3)
    out = BG.copy()
    out[BAR:BAR + img.shape[0], :img.shape[1]] = np.maximum(out[BAR:BAR + img.shape[0], :img.shape[1]], img)
    pil = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    glow = np.asarray(pil.filter(ImageFilter.GaussianBlur(9)), np.float32) / 255
    out = np.clip(out + glow * 0.55, 0, 1)
    return (out * 255).astype(np.uint8)

prompt_font = ImageFont.truetype(FONT, 30, layout_engine=ImageFont.Layout.BASIC)
def overlay_prompt(arr, t):
    if t < 13.6: return arr
    s = ">>> print('te amo, Getse')"
    n = min(len(s), int((t - 13.6) * 14))
    im = Image.fromarray(arr); d = ImageDraw.Draw(im)
    cur = '_' if int(t * 3) % 2 == 0 else ' '
    d.text((40, BAR + 24), s[:n] + cur, font=prompt_font, fill=(255, 170, 205))
    return np.asarray(im)

ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                       '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', OUT + '.noaudio.mp4'],
                      stdin=subprocess.PIPE)
N = int(DUR * FPS)
for k in range(N):
    t = k / FPS
    zoom_e = 1.0
    if t > 3.6: zoom_e = np.exp(min(t - 3.6, 3.4) * 1.05)
    lid = 1.0
    for bt in (2.2,):
        lid *= 1 - 0.95 * np.exp(-((t - bt) / 0.09) ** 2)
    pupil_r = 0.15 + 0.05 * smooth(2.8, 4.5, t)
    if t < 7.0:
        b, col, pu = eye(X / zoom_e, Y / zoom_e, t, pupil_r, lid)
        ch = np.full(X.shape, -1)
        # space visible inside pupil
        sz = zoom_e * pupil_r / 1.9
        sb, scol, sch = space(t, max(sz, 0.05), smooth(7.0, 10.0, t), 0)
        b = np.where(pu, sb, b); col[pu] = scol[pu]; ch = np.where(pu, sch, ch)
        # intro reveal
        rev = jit < t / 1.3
        b = np.where(rev, b, 0)
        if t > 6.4:  # fade eye out entirely
            fade = smooth(6.4, 7.0, t)
            b = np.where(pu, b, b * (1 - fade))
    else:
        z = (zoom_e * pupil_r / 1.9) * (1 + 0) if False else 1.0
        b, col, ch = space(t, 1.0, smooth(7.0, 10.0, t), smooth(10.5, 13.0, t))
        if t < 7.4:
            b *= smooth(7.0, 7.4, t) * 0.6 + 0.4
    if t > DUR - 0.6:
        b = b * (1 - smooth(DUR - 0.6, DUR, t) * 0.0)
    fr = overlay_prompt(compose(b, col, ch, t), t)
    ff.stdin.write(fr.tobytes())
    if k % 60 == 0: print(k, flush=True)
ff.stdin.close(); ff.wait()

# ---------- audio: song from user's recording ----------
SONG = sys.argv[2]
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', OUT + '.noaudio.mp4', '-t', str(DUR), '-i', SONG, '-map', '0:v', '-map', '1:a',
                '-c:v', 'copy', '-af', f'afade=t=in:d=0.3,afade=t=out:st={DUR-0.8}:d=0.8', '-c:a', 'aac', '-b:a', '192k', '-shortest', OUT], check=True)
print('done')
