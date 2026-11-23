"""Build a fast-cut 9:16 reel (reel.mp4) from a post's slide data.

Each card is split into several short cuts (hook, one point per cut, big type,
numbers highlighted), each with a quick punch-in, then hard-cut together.

Usage: python3 tools/make_reel.py posts/<date>/posts.json <post_id> [<post_id> ...]
Output: posts/<date>/<post_id>/reel.mp4
Needs: playwright + /usr/bin/google-chrome, ffmpeg, numpy, scipy, Noto Sans CJK KR.
Audio: original beat + whoosh/pop on every cut (tools/bgm.py), copyright-free.
"""
import html, json, pathlib, re, subprocess, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bgm import make_audio

W, H, FPS = 1080, 1920, 30
LIME = "#C8FF2E"
HANDLE = "@beauty_n_yyasu"
DUR = {"hook": 1.9, "sub": 1.3, "title": 1.0, "item": 2.1, "vs": 1.7, "result": 1.4, "cta": 1.8, "handle": 1.4}

CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#0D0D0D;color:#fff;font-family:'Noto Sans CJK KR',sans-serif;
 word-break:keep-all;overflow:hidden;position:relative}}
.top{{position:absolute;top:120px;left:80px;right:80px}}
.brand{{font-size:40px;font-weight:900;color:{LIME}}}
.bar{{position:absolute;top:200px;left:80px;right:80px;height:10px;background:#2a2a2a;border-radius:5px}}
.bar i{{display:block;height:100%;background:{LIME};border-radius:5px}}
.mid{{position:absolute;left:80px;right:80px;top:50%;transform:translateY(-50%)}}
.foot{{position:absolute;bottom:150px;left:0;right:0;text-align:center;font-size:36px;color:#8a8a8a;font-weight:500}}
.pill{{display:inline-block;background:{LIME};color:#0D0D0D;font-weight:900;font-size:54px;padding:10px 28px;margin-bottom:44px}}
.huge{{font-size:132px;font-weight:900;line-height:1.18;letter-spacing:-4px;white-space:pre-line}}
.big{{font-size:104px;font-weight:900;line-height:1.2;letter-spacing:-3px;white-space:pre-line}}
.num{{font-size:230px;font-weight:900;line-height:1;color:{LIME};letter-spacing:-8px;margin-bottom:40px}}
.desc{{font-size:56px;font-weight:500;line-height:1.5;color:#d8d8d8;margin-top:48px}}
.ghost{{font-size:58px;font-weight:700;color:#777;margin-bottom:36px;white-space:pre-line}}
.hl{{color:{LIME}}}
.mark{{background:{LIME};color:#0D0D0D;padding:0 12px;box-decoration-break:clone;-webkit-box-decoration-break:clone}}
.uline{{width:160px;height:16px;background:{LIME};margin-bottom:48px}}
.letter{{font-size:260px;font-weight:900;line-height:1;margin-bottom:30px}}
.handle{{display:inline-block;border:6px solid {LIME};color:{LIME};font-size:66px;font-weight:900;padding:22px 40px;margin-top:70px}}
"""

NUM_RE = re.compile(r"(\d[\d,.~]*\s?(?:%|배|분|시간|초|번|개|주|일|만|천|억|원|건|세|살|cm|mm|kg)?[↑↓]?)")


def esc(s):
    return html.escape(s)


def hl_nums(s):
    return NUM_RE.sub(lambda m: f'<span class="hl">{m.group(1)}</span>', esc(s))


def is_numeric(tag):
    return bool(tag) and bool(re.search(r"\d", tag))


def cuts_for(post):
    cuts = []
    for s in post["slides"]:
        t = s["type"]
        if t == "cover":
            cuts.append(("hook", f'<div class="pill">{esc(s.get("tag", ""))}</div><div class="huge">{hl_nums(s["headline"])}</div>'))
            if s.get("sub"):
                cuts.append(("sub", f'<div class="ghost">{esc(s["headline"])}</div><div class="big"><span class="mark">{esc(s["sub"])}</span></div>'))
        elif t == "steps":
            cuts.append(("title", f'<div class="uline"></div><div class="huge">{esc(s["title"])}</div>'))
            for name, tag, desc in s["items"]:
                if is_numeric(tag):
                    body = f'<div class="num">{esc(tag)}</div><div class="big">{esc(name)}</div>'
                else:
                    pill = f'<div class="pill">{esc(tag)}</div>' if tag else ""
                    body = f'{pill}<div class="big">{hl_nums(name)}</div>'
                body += f'<div class="desc">{hl_nums(desc)}</div>'
                cuts.append(("item", body))
        elif t == "versus":
            if s.get("title"):
                cuts.append(("title", f'<div class="uline"></div><div class="huge">{esc(s["title"])}</div>'))
            for key, col in (("a", "hl"), ("b", "")):
                lines = "<br>".join(esc(x) for x in s.get(f"{key}_lines", []))
                cuts.append(("vs", f'<div class="letter {col}">{esc(s[key + "_title"])}</div><div class="big">{lines}</div>'))
            if s.get("a_res") or s.get("b_res"):
                cuts.append(("result", f'<div class="big">A <span class="mark">{esc(s.get("a_res", ""))}</span></div><div class="desc">B {esc(s.get("b_res", ""))}</div>'))
        elif t == "cta":
            cuts.append(("cta", f'<div class="uline"></div><div class="huge">{hl_nums(s["headline"])}</div>'))
            cuts.append(("handle", f'<div class="big">저장하고\n친구 태그</div><div class="handle">{HANDLE}</div>'))
    return cuts


def page(body, i, n):
    pct = (i + 1) / n * 100
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
            f'<div class="top"><span class="brand">뷰티와야수</span></div><div class="bar"><i style="width:{pct:.1f}%"></i></div>'
            f'<div class="mid">{body}</div><div class="foot">{HANDLE}</div></body></html>')


def build(posts_json, post_id, keep_frames=None):
    posts_json = pathlib.Path(posts_json)
    post = next(p for p in json.loads(posts_json.read_text()) if p["id"] == post_id)
    out_dir = posts_json.parent / post_id
    out_dir.mkdir(exist_ok=True)
    cuts = cuts_for(post)
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        tmp = pathlib.Path(tmp)
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
        pg = b.new_page(viewport={"width": W, "height": H})
        segs = []
        for i, (kind, body) in enumerate(cuts):
            png = tmp / f"c{i:02d}.png"
            pg.set_content(page(body, i, len(cuts)))
            pg.wait_for_timeout(80)
            pg.screenshot(path=str(png))
            if keep_frames:
                pathlib.Path(keep_frames).mkdir(parents=True, exist_ok=True)
                (pathlib.Path(keep_frames) / png.name).write_bytes(png.read_bytes())
            frames = int(DUR[kind] * FPS)
            seg = tmp / f"s{i:02d}.mp4"
            zoom = ("zoompan=z='max(1.0,1.07-0.012*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                    f":d={frames}:s={W}x{H}:fps={FPS}")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-vf", zoom,
                            "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            "-pix_fmt", "yuv420p", str(seg)], check=True)
            segs.append(seg)
        b.close()
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs))
        total = sum(DUR[k] for k, _ in cuts)
        times, acc = [], 0.0
        for k, _ in cuts:
            times.append(acc)
            acc += DUR[k]
        wav = make_audio(times[1:], total, str(tmp / "bgm.wav"))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-i", wav,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
                        "-movflags", "+faststart", str(out_dir / "reel.mp4")], check=True)
    return out_dir / "reel.mp4", len(cuts), round(total, 1)


if __name__ == "__main__":
    src = sys.argv[1]
    for pid in sys.argv[2:]:
        print(*build(src, pid))
