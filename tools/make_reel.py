"""Build a fast-cut 9:16 reel (reel.mp4) from a post's slide data.

Each card is split into short cuts (one point per cut, big type, numbers highlighted).
Variety to keep people watching: transitions rotate between cuts, numbers count up,
the hook reveals line by line, section titles and the ending flip to a lime background,
and an original beat with a whoosh/pop on every cut runs underneath (tools/bgm.py).

Usage: python3 tools/make_reel.py posts/<date>/posts.json <post_id> [<post_id> ...]
Output: posts/<date>/<post_id>/reel.mp4
Narration: if ELEVENLABS_API_KEY is set, each cut gets a voice line (ElevenLabs, voice ELEVENLABS_VOICE_ID)
  and the cut stretches to fit it; posts.json may give post['narration'] = one line per cut (audio tags like [excited] ok).
Needs: playwright + /usr/bin/google-chrome, ffmpeg >= 5, numpy, scipy, Noto Sans CJK KR.
"""
import html, json, os, pathlib, re, subprocess, sys, tempfile, urllib.request
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bgm import make_audio

W, H, FPS = 1080, 1920, 30
LIME = "#C8FF2E"
HANDLE = "@beauty_n_yyasu"
DUR = {"hook": 2.1, "sub": 1.4, "title": 1.1, "item": 2.2, "vs": 1.7, "result": 1.6, "cta": 1.9, "handle": 1.5}
T = 0.22  # transition length
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "h5eZa8VFAq0EQ8E81dfL")
TTS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_v3")
TRANSITIONS = ["slideleft", "zoomin", "slideup", "wipeleft", "circleopen", "slideright",
               "fadewhite", "smoothup", "coverleft", "radial", "slidedown", "revealleft"]

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
.num{{font-size:250px;font-weight:900;line-height:1;color:{LIME};letter-spacing:-8px;margin-bottom:40px}}
.desc{{font-size:56px;font-weight:500;line-height:1.5;color:#d8d8d8;margin-top:48px}}
.ghost{{font-size:58px;font-weight:700;color:#777;margin-bottom:36px;white-space:pre-line}}
.hl{{color:{LIME}}}
.mark{{background:{LIME};color:#0D0D0D;padding:0 12px;box-decoration-break:clone;-webkit-box-decoration-break:clone}}
.uline{{width:160px;height:16px;background:{LIME};margin-bottom:48px}}
.letter{{font-size:260px;font-weight:900;line-height:1;margin-bottom:30px}}
.handle{{display:inline-block;border:6px solid {LIME};color:{LIME};font-size:66px;font-weight:900;padding:22px 40px;margin-top:70px}}
body.inv{{background:{LIME};color:#0D0D0D}}
.inv .brand,.inv .hl{{color:#0D0D0D}}
.inv .bar{{background:rgba(0,0,0,.15)}} .inv .bar i{{background:#0D0D0D}}
.inv .uline{{background:#0D0D0D}} .inv .foot{{color:rgba(0,0,0,.55)}}
.inv .mark{{background:#0D0D0D;color:{LIME}}} .inv .handle{{border-color:#0D0D0D;color:#0D0D0D}}
.inv .desc{{color:#222}}
"""

NUM_RE = re.compile(r"(\d[\d,.~]*\s?(?:%|배|분|시간|초|번|개|주|일|만|천|억|원|건|세|살|cm|mm|kg)?[↑↓]?)")
COUNT_RE = re.compile(r"^(\d+(?:\.\d+)?)(\D*)$")


def esc(s):
    return html.escape(s)


def hl_nums(s):
    return NUM_RE.sub(lambda m: f'<span class="hl">{m.group(1)}</span>', esc(s))


def count_frames(tag, steps=8):
    """'35.8%' -> ['4.4%', ..., '35.8%'] for a count-up; None if not a plain number."""
    m = COUNT_RE.match(tag.strip())
    if not m:
        return None
    num, rest = m.group(1), m.group(2)
    dec = len(num.split(".")[1]) if "." in num else 0
    v = float(num)
    return [f"{v * k / steps:.{dec}f}{rest}" for k in range(1, steps + 1)]


def cuts_for(post):
    """Each cut = dict(kind, frames=[(body, seconds or None)], inv)."""
    cuts = []
    for s in post["slides"]:
        t = s["type"]
        if t == "cover":
            lines = s["headline"].split("\n")
            pill = f'<div class="pill">{esc(s.get("tag", ""))}</div>'
            frames = []
            if len(lines) > 1:
                frames.append((pill + f'<div class="huge">{hl_nums(lines[0])}</div>', 0.7))
            frames.append((pill + f'<div class="huge">{hl_nums(s["headline"])}</div>', None))
            cuts.append(dict(kind="hook", frames=frames, inv=False, say=strip_marks(s["headline"])))
            if s.get("sub"):
                cuts.append(dict(kind="sub", inv=False, say=strip_marks(s["sub"]), frames=[(
                    f'<div class="ghost">{esc(s["headline"])}</div><div class="big"><span class="mark">{esc(s["sub"])}</span></div>', None)]))
        elif t == "steps":
            cuts.append(dict(kind="title", inv=True, say=strip_marks(s["title"]), frames=[(f'<div class="uline"></div><div class="huge">{esc(s["title"])}</div>', None)]))
            for name, tag, desc in s["items"]:
                tail = f'<div class="desc">{hl_nums(desc)}</div>'
                cf = count_frames(tag) if tag else None
                if cf:
                    frames = [(f'<div class="num">{esc(v)}</div><div class="big">{esc(name)}</div>{tail}', 0.05) for v in cf[:-1]]
                    frames.append((f'<div class="num">{esc(cf[-1])}</div><div class="big">{esc(name)}</div>{tail}', None))
                elif tag and re.search(r"\d", tag):
                    frames = [(f'<div class="num">{esc(tag)}</div><div class="big">{esc(name)}</div>{tail}', None)]
                else:
                    pill = f'<div class="pill">{esc(tag)}</div>' if tag else ""
                    frames = [(f'{pill}<div class="big">{hl_nums(name)}</div>', 0.6),
                              (f'{pill}<div class="big">{hl_nums(name)}</div>{tail}', None)]
                say = f"{strip_marks(tag)}, {strip_marks(name)}" if tag and re.search(r"\\d", tag) else strip_marks(name)
                cuts.append(dict(kind="item", inv=False, frames=frames, say=say))
        elif t == "versus":
            if s.get("title"):
                cuts.append(dict(kind="title", inv=True, say=strip_marks(s["title"]), frames=[(f'<div class="uline"></div><div class="huge">{esc(s["title"])}</div>', None)]))
            for key, col in (("a", "hl"), ("b", "")):
                lines = "<br>".join(esc(x) for x in s.get(f"{key}_lines", []))
                cuts.append(dict(kind="vs", inv=False, say=strip_marks(s[key + "_title"] + ", " + ", ".join(s.get(key + "_lines", []))), frames=[(f'<div class="letter {col}">{esc(s[key + "_title"])}</div><div class="big">{lines}</div>', None)]))
            if s.get("a_res") or s.get("b_res"):
                cuts.append(dict(kind="result", inv=True, say=strip_marks(s.get("a_res", "")), frames=[(
                    f'<div class="big">A <span class="mark">{esc(s.get("a_res", ""))}</span></div><div class="desc">B {esc(s.get("b_res", ""))}</div>', None)]))
        elif t == "cta":
            cuts.append(dict(kind="cta", inv=False, say=strip_marks(s["headline"]), frames=[(f'<div class="uline"></div><div class="huge">{hl_nums(s["headline"])}</div>', None)]))
            cuts.append(dict(kind="handle", inv=True, say="", frames=[(f'<div class="big">저장하고\n친구 태그</div><div class="handle">{HANDLE}</div>', None)]))
    return cuts


def strip_marks(t):
    return re.sub(r"[“”\"‘’'\[\]()①②③④⑤⑥⑦⑧⑨⑩]", "", t).replace("\n", " ").strip()


def narration_for(post, cuts):
    """One short line per cut. posts.json may override with post['narration'] (list, one per cut)."""
    if post.get("narration") and len(post["narration"]) == len(cuts):
        return post["narration"]
    lines = []
    for c in cuts:
        k, txt = c["kind"], c.get("say", "")
        if k == "hook":
            lines.append(f"[excited] {txt}")
        elif k in ("title", "result"):
            lines.append(f"[emphatic] {txt}")
        elif k == "handle":
            lines.append("[excited] 저장하고, 친구 태그! 꾸며라 좀!")
        else:
            lines.append(txt)
    return lines


def tts(text, out_mp3):
    key = os.environ["ELEVENLABS_API_KEY"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128"
    body = json.dumps({"text": text, "model_id": TTS_MODEL, "language_code": "ko"}).encode()
    req = urllib.request.Request(url, data=body, headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        pathlib.Path(out_mp3).write_bytes(r.read())
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out_mp3)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def page(body, i, n, inv):
    pct = (i + 1) / n * 100
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body class="{"inv" if inv else ""}">'
            f'<div class="top"><span class="brand">뷰티와야수</span></div><div class="bar"><i style="width:{pct:.1f}%"></i></div>'
            f'<div class="mid">{body}</div><div class="foot">{HANDLE}</div></body></html>')


def run(cmd):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + cmd, check=True)


def build(posts_json, post_id, keep_frames=None):
    posts_json = pathlib.Path(posts_json)
    post = next(p for p in json.loads(posts_json.read_text()) if p["id"] == post_id)
    out_dir = posts_json.parent / post_id
    out_dir.mkdir(exist_ok=True)
    cuts = cuts_for(post)
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        tmp = pathlib.Path(tmp)
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
        pg = b.new_page(viewport={"width": W, "height": H})
        voice = []  # (mp3 path or None) per cut
        if os.environ.get("ELEVENLABS_API_KEY"):
            for i, line in enumerate(narration_for(post, cuts)):
                if not line.strip():
                    voice.append((None, 0.0)); continue
                mp3 = tmp / f"n{i:02d}.mp3"
                voice.append((mp3, tts(line, mp3)))
        else:
            voice = [(None, 0.0)] * len(cuts)
        segs, durs = [], []
        for i, cut in enumerate(cuts):
            total = max(DUR[cut["kind"]], voice[i][1] + 0.45)
            fixed = sum(d for _, d in cut["frames"] if d)
            pngs = []
            for j, (body, d) in enumerate(cut["frames"]):
                png = tmp / f"c{i:02d}_{j:02d}.png"
                pg.set_content(page(body, i, len(cuts), cut["inv"]))
                pg.wait_for_timeout(60)
                pg.screenshot(path=str(png))
                pngs.append((png, d if d else max(0.5, total - fixed)))
            if keep_frames:
                kf = pathlib.Path(keep_frames); kf.mkdir(parents=True, exist_ok=True)
                (kf / f"c{i:02d}.png").write_bytes(pngs[-1][0].read_bytes())
            seg = tmp / f"s{i:02d}.mp4"
            seg_len = sum(d for _, d in pngs)
            if len(pngs) == 1:
                frames = int(seg_len * FPS)
                z = "max(1.0,1.08-0.014*on)" if i % 2 == 0 else "min(1.04,1.0+0.0012*on)"
                run(["-loop", "1", "-i", str(pngs[0][0]), "-vf",
                     f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}",
                     "-frames:v", str(frames)] + enc + [str(seg)])
            else:
                lst = tmp / f"l{i:02d}.txt"
                lst.write_text("".join(f"file '{p}'\nduration {d:.3f}\n" for p, d in pngs) + f"file '{pngs[-1][0]}'\n")
                run(["-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"fps={FPS},scale={W}:{H}",
                     "-t", f"{seg_len:.3f}"] + enc + [str(seg)])
            segs.append(seg)
            durs.append(seg_len)
        b.close()
        # join with rotating transitions
        inputs, filt, prev, off, offsets = [], [], "[0:v]", 0.0, []
        for s in segs:
            inputs += ["-i", str(s)]
        for k in range(1, len(segs)):
            off += durs[k - 1] - (T if k > 1 else T)
            if k > 1:
                pass
            offsets.append(off)
            tr = TRANSITIONS[(k - 1) % len(TRANSITIONS)]
            filt.append(f"{prev}[{k}:v]xfade=transition={tr}:duration={T}:offset={off:.3f}[v{k}]")
            prev = f"[v{k}]"
        total = sum(durs) - T * (len(segs) - 1)
        wav = make_audio([o + T / 2 for o in offsets], total, str(tmp / "bgm.wav"))
        starts = [0.0] + offsets
        vin = [(p, st) for (p, _), st in zip(voice, starts) if p]
        audio_in = ["-i", wav]
        for p, _ in vin:
            audio_in += ["-i", str(p)]
        a0 = len(segs)
        if vin:
            parts = [f"[{a0}:a]volume=0.35[bg]"]
            labels = ["[bg]"]
            for j, (_, st) in enumerate(vin):
                ms = int((st + 0.12) * 1000)
                parts.append(f"[{a0 + 1 + j}:a]aresample=44100,adelay={ms}|{ms},volume=1.6[n{j}]")
                labels.append(f"[n{j}]")
            parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first,alimiter=limit=0.95[aout]")
            amap = "[aout]"
            filt += parts
        else:
            amap = f"{a0}:a"
        run(inputs + audio_in + ["-filter_complex", ";".join(filt), "-map", prev, "-map", amap]
            + enc + ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest",
                     "-movflags", "+faststart", "-use_editlist", "0", str(out_dir / "reel.mp4")])
    return out_dir / "reel.mp4", len(cuts), round(total, 1)


if __name__ == "__main__":
    src = sys.argv[1]
    for pid in sys.argv[2:]:
        print(*build(src, pid))
