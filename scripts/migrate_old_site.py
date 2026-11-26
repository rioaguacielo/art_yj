#!/usr/bin/env python3
"""기존 홈페이지(yeojuart.co.kr, 그누보드4)의 게시글을 한 번 옮겨 옵니다.

- 공지사항(f1) → content/notice, 행사·축제(e1) → content/events, 포토갤러리(e2) → content/gallery
- 본문 사진은 uploads/migrated/<게시판>/, 첨부파일은 uploads/migrated/files/ 에 저장합니다.
- 이미 옮긴 글(같은 wr_id)은 건너뛰므로 여러 번 실행해도 안전합니다.
- 모두 끝나면 data/migrated.txt 를 만들고, 그 뒤로는 아무것도 하지 않습니다.

GitHub Actions(.github/workflows/deploy.yml)가 배포할 때 실행합니다.
"""
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD = "http://www.yeojuart.co.kr"
BOARDS = {"f1": "notice", "e1": "events", "e2": "gallery"}
MARKER = ROOT / "data" / "migrated.txt"
UA = {"User-Agent": "Mozilla/5.0 (art_yj migration)"}


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
    return data if binary else data.decode("cp949", errors="replace")


def list_ids(bo):
    ids, page = [], 1
    while page < 40:
        h = fetch(f"{OLD}/bbs/board.php?bo_table={bo}&page={page}")
        found = [int(x) for x in re.findall(rf"bo_table={bo}&(?:amp;)?wr_id=(\d+)", h)]
        new = [i for i in dict.fromkeys(found) if i not in ids]
        if not new:
            break
        ids += new
        page += 1
    return sorted(set(ids), reverse=True)


ALLOWED = {"p", "br", "img", "a", "strong", "b", "em", "i", "u", "ul", "ol", "li", "table", "tr", "td", "th", "tbody", "thead", "h3", "h4", "blockquote"}


def clean_html(s):
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<(script|style|xml|xmp)\b.*?</\1>", "", s, flags=re.S | re.I)

    def tag(m):
        closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3) or ""
        if name not in ALLOWED:
            return "<br />" if name == "div" and closing else ""
        if closing:
            return f"</{name}>"
        if name == "img":
            src = re.search(r"""src=['"]?([^'"\s>]+)""", attrs)
            return f'<img src="{src.group(1)}" alt="" />' if src else ""
        if name == "a":
            href = re.search(r"""href=['"]?([^'"\s>]+)""", attrs)
            h = href.group(1) if href else ""
            if not h.startswith("http"):
                return ""
            return f'<a href="{h}" rel="noopener">'
        return f"<{name}>"

    s = re.sub(r"<(/?)([a-zA-Z0-9]+)([^>]*)>", tag, s)
    s = re.sub(r"(<br />\s*){3,}", "<br /><br />", s)
    s = re.sub(r"<p>\s*</p>", "", s)
    s = s.replace("&nbsp;", " ")
    s = re.sub(r"[ \t]+", " ", s)
    # 열고 닫는 태그 개수 맞추기(a 태그)
    if s.count("<a ") > s.count("</a>"):
        s += "</a>" * (s.count("<a ") - s.count("</a>"))
    s = s.replace("</a>", "", max(0, s.count("</a>") - s.count("<a ")))
    return s.strip()


def safe_name(name, fallback):
    base = Path(name).name
    ext = Path(base).suffix.lower()[:6] or ".bin"
    if re.fullmatch(r"[A-Za-z0-9._-]+", base) and len(base) < 120:
        return base
    return fallback + ext


def yq(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def migrate_post(bo, board, wr):
    out = ROOT / "content" / board
    if list(out.glob(f"*-{wr}.md")):
        return "skip"
    h = fetch(f"{OLD}/bbs/board.php?bo_table={bo}&wr_id={wr}")
    t = re.search(r"<title>(.*?)</title>", h, re.S | re.I)
    parts = html.unescape(t.group(1)).split(" > ") if t else []
    title = " > ".join(parts[2:]).strip() if len(parts) >= 3 else ""
    if not title:
        return "notitle"
    d = re.search(r"(\d{2,4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})", h)
    if d:
        y = int(d.group(1))
        y = y + 2000 if y < 100 else y
        date = f"{y:04d}-{d.group(2)}-{d.group(3)} {d.group(4)}:{d.group(5)}"
        day = f"{y:04d}-{d.group(2)}-{d.group(3)}"
    else:
        date, day = "2000-01-01 00:00", "2000-01-01"

    c = re.search(r"""id=["']?writeContents["']?[^>]*>(.*?)<!--\s*테러 태그 방지용""", h, re.S)
    content = c.group(1) if c else ""

    # 본문 사진: 그누보드 첨부 이미지(본문 위에 따로 붙는 것 포함)
    img_dir = ROOT / "uploads" / "migrated" / board
    img_dir.mkdir(parents=True, exist_ok=True)
    srcs = list(dict.fromkeys(re.findall(rf"""src=['"]\.\./data/file/{bo}/(?!thumb)([^'"]+)['"]""", h)))
    editor = list(dict.fromkeys(re.findall(r"""src=['"](?:https?://www\.yeojuart\.co\.kr)?/?(?:\.\./)?(data/(?:editor|geditor|cheditor\d*)/[^'"]+)['"]""", content)))
    new_src = {}
    for i, f in enumerate(srcs + editor, 1):
        rel = f if f.startswith("data/") else f"data/file/{bo}/{f}"
        name = safe_name(urllib.parse.unquote(f), f"{wr}-{i}")
        dest = img_dir / name
        if not dest.exists():
            try:
                dest.write_bytes(fetch(f"{OLD}/{urllib.parse.quote(rel)}", binary=True))
            except Exception as e:
                print(f"  img fail {rel}: {e}")
                continue
        new_src[f] = f"/uploads/migrated/{board}/{name}"
    body = clean_html(content)

    def remap(m):
        src = m.group(1)
        k = re.sub(r"^(?:https?://www\.yeojuart\.co\.kr)?/?(?:\.\./)?", "", src)
        if k.startswith(f"data/file/{bo}/"):
            k = k[len(f"data/file/{bo}/"):]
        return f'src="{new_src.get(k, src)}"'

    body = re.sub(r'src="([^"]+)"', remap, body)
    in_body = [n for o, n in new_src.items() if n in body]
    lead = "".join(f'<p><img src="{n}" alt="" /></p>' for n in new_src.values() if n not in in_body)
    body = lead + body

    # 첨부파일
    files_dir = ROOT / "uploads" / "migrated" / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    atts = []
    for b2, w2, no, fname in re.findall(r"file_download\('\./download\.php\?bo_table=(\w+)&(?:amp;)?wr_id=(\d+)&(?:amp;)?no=(\d+)',\s*'([^']*)'\)", h):
        fname = html.unescape(fname)
        ext = Path(fname).suffix.lower()[:6] or ".bin"
        dest = files_dir / f"{board}-{wr}-{no}{ext}"
        if not dest.exists():
            try:
                data = fetch(f"{OLD}/bbs/download.php?bo_table={b2}&wr_id={w2}&no={no}", binary=True)
                if len(data) < 50:
                    raise ValueError("empty")
                dest.write_bytes(data)
            except Exception as e:
                print(f"  file fail {fname}: {e}")
                continue
        atts.append((f"/uploads/migrated/files/{dest.name}", fname))

    lines = ["---", f"title: {yq(title)}", f"date: {date}", "author: 여주예총"]
    if atts:
        lines.append("attachments:")
        for path, name in atts:
            lines += [f"  - file: {path}", f"    name: {yq(name)}"]
    lines += ["migrated_from: " + yq(f"{OLD}/bbs/board.php?bo_table={bo}&wr_id={wr}"), "---", body, ""]
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{day}-{wr}.md").write_text("\n".join(lines), encoding="utf-8")
    return "ok"


def main():
    if MARKER.exists():
        print("already migrated")
        return 0
    total = fails = 0
    for bo, board in BOARDS.items():
        try:
            ids = list_ids(bo)
        except Exception as e:
            print(f"list fail {bo}: {e}")
            fails += 1
            continue
        print(f"{bo} -> {board}: {len(ids)} posts")
        for wr in ids:
            try:
                r = migrate_post(bo, board, wr)
                if r == "ok":
                    total += 1
                elif r != "skip":
                    print(f"  {bo}/{wr}: {r}")
            except Exception as e:
                print(f"  {bo}/{wr} fail: {e}")
                fails += 1
            time.sleep(0.15)
    print(f"migrated {total} post(s), {fails} failure(s)")
    if fails == 0:
        MARKER.parent.mkdir(exist_ok=True)
        MARKER.write_text("기존 사이트 게시글 이전 완료. 이 파일을 지우면 빠진 글만 다시 옮겨 옵니다.\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
