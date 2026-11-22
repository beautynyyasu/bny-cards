"""Render beauty_n_beast carousel cards (1080x1350) from posts.json."""
import json, sys, html, pathlib
from playwright.sync_api import sync_playwright

HANDLE = "@beauty_n_yyasu"
BRAND = "뷰티와야수"
ACCENT = "#C8FF2E"

CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;height:1350px;background:#0D0D0D;color:#fff;
 font-family:'Noto Sans CJK KR',sans-serif;position:relative;overflow:hidden;word-break:keep-all}}
.top{{position:absolute;top:56px;left:72px;right:72px;display:flex;justify-content:space-between;
 font-size:30px;font-weight:700;letter-spacing:1px;color:#8a8a8a}}
.top b{{color:{ACCENT}}}
.foot{{position:absolute;bottom:56px;left:72px;right:72px;display:flex;justify-content:space-between;
 font-size:28px;color:#6d6d6d;font-weight:500}}
.big{{position:absolute;top:150px;left:56px;font-size:300px;font-weight:900;line-height:1;
 color:#1c1c1c;letter-spacing:-8px;white-space:nowrap}}
.tag{{display:inline-block;background:{ACCENT};color:#0D0D0D;font-size:40px;font-weight:900;padding:10px 22px;margin-bottom:34px}}
.cover{{position:absolute;left:72px;right:72px;bottom:190px}}
.headline{{font-size:92px;font-weight:900;line-height:1.22;letter-spacing:-2px;white-space:pre-line}}
.sub{{margin-top:34px;font-size:56px;font-weight:700;color:{ACCENT}}}
.bar{{width:120px;height:12px;background:{ACCENT};margin-bottom:30px}}
.wrap{{position:absolute;top:150px;left:72px;right:72px}}
.title{{font-size:72px;font-weight:900;letter-spacing:-1px;margin-bottom:50px}}
.item{{border-top:2px solid #2a2a2a;padding:34px 0}}
.item:last-child{{border-bottom:2px solid #2a2a2a}}
.ih{{display:flex;align-items:baseline;gap:22px}}
.in{{font-size:48px;font-weight:900}}
.it{{font-size:32px;font-weight:700;color:#0D0D0D;background:{ACCENT};padding:2px 14px}}
.id{{margin-top:14px;font-size:36px;line-height:1.5;color:#c9c9c9}}
.vs{{position:absolute;top:260px;bottom:190px;left:72px;right:72px;display:flex;gap:36px;align-items:stretch}}
.col{{flex:1;border:3px solid #2e2e2e;padding:60px 40px;display:flex;flex-direction:column;gap:30px}}
.col.a{{border-color:{ACCENT}}}
.ct{{font-size:180px;font-weight:900;line-height:1}}
.col.a .ct{{color:{ACCENT}}}
.cl{{font-size:44px;font-weight:700;line-height:1.35}}
.vsmark{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#0D0D0D;
 font-size:64px;font-weight:900;color:#fff;padding:10px 18px}}
.note{{position:absolute;left:72px;right:72px;bottom:120px;font-size:26px;color:#7a7a7a;line-height:1.4}}
.vt{{position:absolute;top:130px;left:72px;right:72px;font-size:60px;font-weight:900;letter-spacing:-1px}}
.vres{{font-size:40px;font-weight:900;color:#0D0D0D;background:{ACCENT};padding:6px 14px;align-self:flex-start;margin-top:auto}}
.col.b .vres{{background:#3a3a3a;color:#fff}}
.cta{{position:absolute;left:72px;right:72px;top:50%;transform:translateY(-50%)}}
.cta .headline{{font-size:110px}}
.cta .sub{{font-size:44px;color:#bdbdbd;white-space:pre-line;line-height:1.5;font-weight:500}}
.handle{{margin-top:60px;display:inline-block;border:3px solid {ACCENT};color:{ACCENT};font-size:48px;font-weight:900;padding:16px 30px}}
"""

def e(s):
    return html.escape(s)

def slide_html(s, idx, total):
    top = f'<div class="top"><span><b>{BRAND}</b></span><span>{idx}/{total}</span></div>'
    foot = f'<div class="foot"><span>{HANDLE}</span><span>꾸며라 좀 👊</span></div>'
    t = s["type"]
    if t == "cover":
        body = (f'<div class="big">{e(s.get("big",""))}</div><div class="cover">'
                f'<div class="tag">{e(s["tag"])}</div><div class="headline">{e(s["headline"])}</div>'
                f'<div class="sub">{e(s["sub"])}</div></div>')
    elif t == "steps":
        items = "".join(
            f'<div class="item"><div class="ih"><span class="in">{e(n)}</span>'
            + (f'<span class="it">{e(tg)}</span>' if tg else "")
            + f'</div><div class="id">{e(d)}</div></div>' for n, tg, d in s["items"])
        body = f'<div class="wrap"><div class="bar"></div><div class="title">{e(s["title"])}</div>{items}</div>'
    elif t == "versus":
        def col(cls, title, lines, res):
            ls = "".join(f'<div class="cl">{e(l)}</div>' for l in lines)
            r = f'<div class="vres">{e(res)}</div>' if res else ""
            return f'<div class="col {cls}"><div class="ct">{e(title)}</div>{ls}{r}</div>'
        vt = f'<div class="vt">{e(s["title"])}</div>' if s.get("title") else ""
        body = (f'{vt}<div class="vs">{col("a", s["a_title"], s["a_lines"], s.get("a_res"))}{col("b", s["b_title"], s["b_lines"], s.get("b_res"))}'
                f'<div class="vsmark">VS</div></div>')
    elif t == "cta":
        body = (f'<div class="cta"><div class="bar"></div><div class="headline">{e(s["headline"])}</div>'
                f'<div class="sub">{e(s["sub"])}</div><div class="handle">{HANDLE} 팔로우</div></div>')
    else:
        raise ValueError(t)
    if s.get('note'): body += f'<div class="note">{e(s["note"])}</div>'
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{top}{body}{foot}</body></html>'

def main(src, out):
    posts = json.loads(pathlib.Path(src).read_text())
    outdir = pathlib.Path(out); outdir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for post in posts:
            d = outdir / post["id"]; d.mkdir(exist_ok=True)
            n = len(post["slides"])
            for i, s in enumerate(post["slides"], 1):
                pg.set_content(slide_html(s, i, n)); pg.wait_for_timeout(150)
                pg.screenshot(path=str(d / f"{i:02d}.jpg"), type="jpeg", quality=92)
            (d / "caption.txt").write_text(post["caption"])
        b.close()

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
