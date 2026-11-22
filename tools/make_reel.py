"""Turn a rendered card post folder (01.jpg, 02.jpg, ...) into a 9:16 Instagram reel (reel.mp4).

Usage: python3 tools/make_reel.py posts/<date>/<post_id> [posts/<date>/<post_id> ...]
Needs: ffmpeg, Pillow, Noto Sans CJK fonts.
"""
import subprocess, sys, tempfile, pathlib
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG = (13, 13, 13)
LIME = (200, 255, 46)
GRAY = (150, 150, 150)
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
COVER_SEC, CARD_SEC, LAST_SEC, FADE = 2.5, 4.5, 2.5, 0.3


def kr_index(path):
    for i in range(10):
        try:
            if "KR" in ImageFont.truetype(path, 10, index=i).getname()[0]:
                return i
        except Exception:
            break
    return 0


def frame(card_path, out_path, idx, total):
    canvas = Image.new("RGB", (W, H), BG)
    card = Image.open(card_path).convert("RGB").resize((1080, 1350))
    top = (H - 1350) // 2
    canvas.paste(card, (0, top))
    d = ImageDraw.Draw(canvas)
    fb = ImageFont.truetype(FONT, 54, index=kr_index(FONT))
    fr = ImageFont.truetype(FONT_REG, 36, index=kr_index(FONT_REG))
    d.text((W / 2, top / 2 - 10), "뷰티와야수", font=fb, fill=LIME, anchor="mm")
    d.text((W / 2, top / 2 + 52), "남자 피부 1분 꿀팁", font=fr, fill=GRAY, anchor="mm")
    # progress bar
    bar_y = top + 1350 + 60
    seg = (W - 160) / total
    for i in range(total):
        x0 = 80 + i * seg + 6
        d.rounded_rectangle((x0, bar_y, x0 + seg - 12, bar_y + 10), radius=5,
                            fill=LIME if i <= idx else (60, 60, 60))
    d.text((W / 2, bar_y + 90), "저장해두고 천천히 보기", font=fr, fill=(220, 220, 220), anchor="mm")
    d.text((W / 2, bar_y + 150), "@beauty_n_yyasu", font=fr, fill=GRAY, anchor="mm")
    canvas.save(out_path, quality=95)


def make_reel(post_dir):
    post_dir = pathlib.Path(post_dir)
    cards = sorted(post_dir.glob("[0-9][0-9].jpg"))
    if not cards:
        raise SystemExit(f"no cards in {post_dir}")
    n = len(cards)
    durs = [COVER_SEC] + [CARD_SEC] * (n - 2) + [LAST_SEC] if n > 1 else [COVER_SEC]
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for i, c in enumerate(cards):
            fp = pathlib.Path(tmp) / f"f{i:02d}.jpg"
            frame(c, fp, i, n)
            frames.append(fp)
        cmd = ["ffmpeg", "-y", "-loglevel", "error"]
        for fp, dur in zip(frames, durs):
            cmd += ["-loop", "1", "-t", str(dur + FADE), "-framerate", "30", "-i", str(fp)]
        cmd += ["-f", "lavfi", "-t", str(sum(durs) + FADE), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        filt, prev, offset = [], "[0:v]", 0.0
        for i in range(1, n):
            offset += durs[i - 1]
            out = f"[v{i}]"
            filt.append(f"{prev}[{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.2f}{out}")
            prev = out
        vmap = prev if n > 1 else "[0:v]"
        if filt:
            cmd += ["-filter_complex", ";".join(filt)]
        cmd += ["-map", vmap, "-map", f"{n}:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-shortest",
                "-movflags", "+faststart", str(post_dir / "reel.mp4")]
        subprocess.run(cmd, check=True)
    return post_dir / "reel.mp4"


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(make_reel(p))
