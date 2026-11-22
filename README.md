# bny-cards

@beauty_n_yyasu(뷰티와야수) 인스타그램 카드 이미지 저장소 + 게시 대기열.

- `CONTENT_GUIDE.md` — 콘텐츠 기준
- `tools/render.py` — `python3 tools/render.py posts/<날짜>/posts.json posts/<날짜>` 로 카드 렌더링 (Noto Sans CJK KR, /usr/bin/google-chrome, playwright)
- `posts/<YYYY-MM-DD>/` — 날짜별 posts.json, 게시물 폴더(01.jpg~, caption.txt)
- `tools/make_reel.py` — `python3 tools/make_reel.py posts/<날짜>/posts.json <post_id>` 로 슬라이드 내용을 여러 컷(큰 글씨·숫자 강조·빠른 전환)으로 쪼갠 9:16 릴스(reel.mp4) 생성
- `queue.json` — Make가 읽는 게시 대기열. 항목: date, slot(HH:MM, KST), post_id, status(ready/posted), type(carousel/reel), caption, images(raw URL 배열), video(reel일 때 mp4 raw URL)

이미지 공개 주소: `https://raw.githubusercontent.com/beautynyyasu/bny-cards/main/posts/<날짜>/<post_id>/NN.jpg`
