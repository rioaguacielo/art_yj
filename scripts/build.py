#!/usr/bin/env python3
"""여주예총 사이트 생성기.

content/<게시판>/*.md 글, content/associations/*.md 회원단체 소개와 templates/ 를 읽어
_site/ 에 완성된 HTML을 만듭니다. GitHub Actions(.github/workflows/deploy.yml)가
글이 올라올 때마다 자동으로 실행합니다.

로컬 실행:  python3 scripts/build.py   (필요 패키지: pyyaml, jinja2, markdown)
"""
import datetime as dt
import os
import re
import shutil
import sys
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
KST = dt.timezone(dt.timedelta(hours=9))
STATIC_DIRS = ["css", "images", "uploads"]


def load_site():
    site = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
    base = os.environ.get("BASEURL", site.get("baseurl", "")) or ""
    return site, base.rstrip("/")


def parse_date(v):
    if isinstance(v, dt.datetime):
        d = v
    elif isinstance(v, dt.date):
        d = dt.datetime(v.year, v.month, v.day)
    elif isinstance(v, str) and v.strip():
        s = v.strip().replace(".", "-").replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                d = dt.datetime.strptime(s[:19], fmt)
                break
            except ValueError:
                continue
        else:
            d = dt.datetime(1970, 1, 1)
    else:
        d = dt.datetime(1970, 1, 1)
    return d.replace(tzinfo=None)


def read_md(path: Path):
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        body = m.group(2)
    return meta, body


def human_size(n):
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f}MB"
    return f"{max(1, round(n / 1024))}KB"


def fix_urls(html, base):
    if not base:
        return html
    return re.sub(r'(src|href)=(["\'])/(?!/)(?!' + re.escape(base.lstrip("/")) + r'/)', rf'\1=\2{base}/', html)


def to_html(body, base):
    body = (body or "").strip()
    if not body:
        return ""
    html = body if body.startswith("<") else markdown.markdown(body, extensions=["extra", "nl2br", "sane_lists"])
    return fix_urls(html, base)


def plain(html, n=110):
    t = re.sub(r"<[^>]+>", " ", html)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n].rstrip() + "…"


def load_posts(site, base):
    posts_by_board = {}
    for key in site["boards"]:
        folder = ROOT / "content" / key
        posts = []
        for f in sorted(folder.glob("*.md")) if folder.exists() else []:
            meta, body = read_md(f)
            if meta.get("draft"):
                continue
            html = to_html(body, base)
            date = parse_date(meta.get("date"))
            atts = []
            for a in meta.get("attachments") or []:
                path, name = (a.get("file") or a.get("path"), a.get("name")) if isinstance(a, dict) else (str(a), None)
                if not path:
                    continue
                local = ROOT / path.lstrip("/")
                atts.append({"name": name or Path(path).name, "url": base + path if path.startswith("/") else path,
                             "size": human_size(local.stat().st_size) if local.exists() else None})
            thumb = meta.get("thumbnail")
            if thumb:
                thumb = base + thumb if str(thumb).startswith("/") else thumb
            else:
                m = re.search(r'<img[^>]+src=["\']([^"\']+)', html)
                thumb = m.group(1) if m else None
            images = re.findall(r'<img[^>]+src=["\']([^"\']+)', html)
            posts.append({
                "slug": f.stem, "board": key,
                "title": str(meta.get("title") or f.stem),
                "author": meta.get("author") or site["title"],
                "date": date,
                "date_str": date.strftime("%Y.%m.%d"),
                "date_full": date.strftime("%Y.%m.%d %H:%M"),
                "day": date.strftime("%d"), "month": date.strftime("%Y.%m"),
                "html": html, "summary": plain(html), "attachments": atts,
                "thumb": thumb, "images": images,
                "place": meta.get("place") or "", "period": meta.get("period") or "",
                "url": f"{base}/{key}/{f.stem}/",
            })
        posts.sort(key=lambda p: p["date"], reverse=True)
        posts_by_board[key] = posts
    return posts_by_board


def load_associations(base):
    items = []
    for f in sorted((ROOT / "content" / "associations").glob("*.md")):
        meta, body = read_md(f)
        if meta.get("draft"):
            continue
        items.append({**meta, "key": f.stem, "html": to_html(body, base),
                      "image": (base + meta["image"]) if str(meta.get("image") or "").startswith("/") else meta.get("image"),
                      "url": f"{base}/members/{f.stem}/"})
    items.sort(key=lambda a: a.get("order", 99))
    return items


def main():
    site, base = load_site()
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    build_id = dt.datetime.now(KST).strftime("%Y%m%d%H%M")
    boards = {k: {"key": k, **v} for k, v in site["boards"].items()}
    posts = load_posts(site, base)
    assocs = load_associations(base)
    # 첫 화면 사진: 갤러리 글마다 대표 사진 1장씩(최신순), 모자라면 행사 글 사진
    photos = [p["thumb"] for p in posts.get("gallery", []) if p["thumb"]]
    photos += [p["thumb"] for p in posts.get("events", []) if p["thumb"] and p["thumb"] not in photos]
    common = {"site": site, "base": base, "build_id": build_id, "boards": boards, "posts": posts,
              "assocs": assocs, "photos": photos, "year": dt.datetime.now(KST).year}

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for d in STATIC_DIRS:
        if (ROOT / d).exists():
            shutil.copytree(ROOT / d, OUT / d, ignore=shutil.ignore_patterns(".gitkeep"))
    (OUT / ".nojekyll").write_text("")

    def write(rel, html):
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")

    for name, out in {"home": "index.html", "about": "about.html", "404": "404.html"}.items():
        write(out, env.get_template(f"pages/{name}.html").render(nav=name, **common))

    write("members/index.html", env.get_template("members.html").render(nav="members", **common))
    for i, a in enumerate(assocs):
        write(f"members/{a['key']}/index.html", env.get_template("member.html").render(
            nav="members", a=a, prev=assocs[i - 1] if i > 0 else None,
            next=assocs[i + 1] if i + 1 < len(assocs) else None, **common))

    count = 0
    for key, board in boards.items():
        lst = posts[key]
        ctx = dict(common, board=board, nav=key)
        write(f"{key}/index.html", env.get_template("board.html").render(items=lst, **ctx))
        for i, p in enumerate(lst):
            write(f"{key}/{p['slug']}/index.html", env.get_template("post.html").render(
                post=p, prev=lst[i + 1] if i + 1 < len(lst) else None, next=lst[i - 1] if i > 0 else None, **ctx))
            count += 1
    print(f"built {count} posts, {len(assocs)} associations -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
