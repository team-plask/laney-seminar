#!/usr/bin/env python3
"""
fetch_naver_blog.py — 네이버 블로그 전체 글 수집 스크립트

Usage:
    python3 fetch_naver_blog.py --blog-id <id> --outdir <dir> [--max-posts 200] [--delay 0.5] [--since YYYY-MM-DD]
"""

import argparse
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _make_request(url: str, headers: dict, timeout: int = 15):
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_text(url: str, headers: dict, timeout: int = 15, retries: int = 1) -> str | None:
    for attempt in range(retries + 1):
        try:
            with _make_request(url, headers, timeout) as resp:
                charset = "utf-8"
                ct = resp.headers.get("Content-Type", "")
                m = re.search(r"charset=([^\s;]+)", ct, re.I)
                if m:
                    charset = m.group(1)
                return resp.read().decode(charset, errors="replace")
        except Exception as e:
            if attempt == retries:
                return None
            time.sleep(1)
    return None


def fetch_json(url: str, headers: dict, timeout: int = 15, retries: int = 1) -> dict | None:
    text = fetch_text(url, headers, timeout, retries)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Post list collection
# ---------------------------------------------------------------------------

def fetch_post_list(blog_id: str, max_posts: int, delay: float, since: str | None) -> list[dict]:
    """Return list of {logNo, title, date} dicts from the mobile API."""
    posts: list[dict] = []
    page = 1
    item_count = 30
    seen: set[str] = set()

    since_dt = None
    if since:
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"[warn] --since format invalid, ignoring: {since}")

    while len(posts) < max_posts:
        url = (
            f"https://m.blog.naver.com/api/blogs/{blog_id}/post-list"
            f"?categoryNo=0&itemCount={item_count}&page={page}"
        )
        headers = {
            "User-Agent": MOBILE_UA,
            "Referer": f"https://m.blog.naver.com/{blog_id}",
            "Accept": "application/json, text/plain, */*",
        }
        data = fetch_json(url, headers)

        if data is None or not data.get("isSuccess"):
            print(f"[warn] page {page}: API returned non-success or error")
            break

        items = data.get("result", {}).get("items", [])
        if not items:
            break

        for item in items:
            log_no = str(item.get("logNo", ""))
            title = item.get("titleWithInspectMessage", item.get("title", ""))
            add_date = item.get("addDate", "")
            # addDate format: "2024-05-17 10:30:00" or epoch ms
            date_str = _parse_add_date(add_date)

            if log_no in seen:
                continue
            seen.add(log_no)

            if since_dt and date_str:
                try:
                    post_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if post_dt < since_dt:
                        continue
                except ValueError:
                    pass

            posts.append({"logNo": log_no, "title": title, "date": date_str})
            if len(posts) >= max_posts:
                break

        page += 1
        if delay > 0:
            time.sleep(delay)

    return posts


def _parse_add_date(add_date) -> str:
    if isinstance(add_date, (int, float)):
        # epoch milliseconds
        try:
            dt = datetime.fromtimestamp(add_date / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return str(add_date)
    if isinstance(add_date, str):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", add_date)
        if m:
            return m.group(1)
    return str(add_date)


# ---------------------------------------------------------------------------
# RSS fallback
# ---------------------------------------------------------------------------

def fetch_rss_posts(blog_id: str) -> list[dict]:
    """Return minimal post list from RSS (fallback, recent only)."""
    url = f"https://rss.blog.naver.com/{blog_id}.xml"
    headers = {"User-Agent": MOBILE_UA}
    text = fetch_text(url, headers)
    if text is None:
        return []
    items = []
    for item_block in re.findall(r"<item>(.*?)</item>", text, re.DOTALL):
        guid_m = re.search(r"<guid>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</guid>", item_block, re.DOTALL)
        link_m = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", item_block, re.DOTALL)
        title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item_block, re.DOTALL)
        pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item_block, re.DOTALL)
        # Prefer <guid> (clean permalink); the <link> now carries ?fromRss= query
        # params, and both are CDATA-wrapped, so match the logNo anywhere in the path
        # rather than anchoring to the end of the string.
        ref = (guid_m.group(1) if guid_m else link_m.group(1) if link_m else "").strip()
        if not ref:
            continue
        link = link_m.group(1).strip() if link_m else ref
        log_no_m = re.search(r"/(\d+)(?:[/?#]|$)", ref)
        if not log_no_m:
            continue
        log_no = log_no_m.group(1)
        title = html.unescape((title_m.group(1) if title_m else "").strip())
        date_str = _parse_pubdate(pub_m.group(1) if pub_m else "")
        items.append({"logNo": log_no, "title": title, "date": date_str})
    return items


def _parse_pubdate(pubdate: str) -> str:
    # RFC 822: "Thu, 17 May 2024 10:30:00 +0900"
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(pubdate.strip())
        return dt.strftime("%Y-%m-%d")
    except Exception:
        m = re.search(r"(\d{4})", pubdate)
        return pubdate.strip() if m else ""


# ---------------------------------------------------------------------------
# Post body fetching & parsing
# ---------------------------------------------------------------------------

def _extract_div_content(html_text: str, pattern: str) -> str | None:
    """Find the first <div> whose opening tag matches `pattern` and return its
    full inner content using a depth counter (handles deeply nested divs)."""
    m = re.search(pattern, html_text, re.DOTALL | re.I)
    if not m:
        return None
    fragment = html_text[m.end():]
    depth = 1
    pos = 0
    while depth > 0 and pos < len(fragment):
        open_m = re.search(r"<div[\s>]", fragment[pos:])
        close_m = re.search(r"</div\s*>", fragment[pos:])
        if close_m and (not open_m or close_m.start() < open_m.start()):
            depth -= 1
            if depth == 0:
                return fragment[:pos + close_m.start()]
            pos += close_m.end()
        elif open_m:
            depth += 1
            pos += open_m.end()
        else:
            break
    return fragment[:pos] if pos > 0 else None


def fetch_post_body(blog_id: str, log_no: str, delay: float) -> dict:
    """Fetch and parse a single blog post. Returns {text, images, parse}."""
    url = f"https://m.blog.naver.com/{blog_id}/{log_no}"
    headers = {
        "User-Agent": MOBILE_UA,
        "Referer": f"https://m.blog.naver.com/{blog_id}",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    html_text = fetch_text(url, headers, retries=1)
    if delay > 0:
        time.sleep(delay)
    if html_text is None:
        return {"text": "", "images": [], "parse": "failed"}

    parse_mode = "failed"
    text = ""
    images: list[str] = []

    # SmartEditor (se-main-container) — most modern posts
    content = _extract_div_content(
        html_text,
        r'<div[^>]+class="[^"]*\bse-main-container\b[^"]*"[^>]*>',
    )
    if content is not None:
        parse_mode = "se"
        text = _extract_text(content)
        images = _extract_images(content)
    else:
        # Legacy: post-view class
        content = _extract_div_content(
            html_text,
            r'<div[^>]+class="[^"]*\bpost-view\b[^"]*"[^>]*>',
        )
        if content is None:
            # Legacy: viewTypeSelector id
            content = _extract_div_content(
                html_text,
                r'<div[^>]+id="viewTypeSelector"[^>]*>',
            )
        if content is not None:
            parse_mode = "legacy"
            text = _extract_text(content)
            images = _extract_images(content)
        else:
            # Widest fallback: full body
            body_match = re.search(r"<body[^>]*>(.*?)</body>", html_text, re.DOTALL)
            if body_match:
                parse_mode = "legacy"
                text = _extract_text(body_match.group(1))
                images = _extract_images(body_match.group(1))

    md = _extract_md(content if content is not None else "") if parse_mode != "failed" else ""
    return {"text": text, "md": md, "images": images, "parse": parse_mode}


def _extract_md(fragment: str) -> str:
    """SmartEditor/legacy HTML → Markdown, preserving structure and IMAGE POSITION.

    Naver posts carry their meaning in structure (headings, quotes, and where each photo
    sits between paragraphs). Flattening to plain text loses that, so we keep a markdown
    twin: headings → `#`, quotes → `>`, list items → `-`, links → `[t](u)`, bold → `**`,
    and every in-body image → `![](url)` AT ITS POSITION. This is the canonical body for
    excerpts, related-post bands, and any future self-hosted post page.
    """
    if not fragment:
        return ""
    s = fragment
    # Drop non-content
    s = re.sub(r"<script[^>]*>.*?</script>", " ", s, flags=re.DOTALL | re.I)
    s = re.sub(r"<style[^>]*>.*?</style>", " ", s, flags=re.DOTALL | re.I)
    # Images FIRST (before tags are stripped) — keep them inline where they appear
    def _img_sub(m: re.Match) -> str:
        attrs = m.group(1)
        for attr_name in ("data-lazy-src", "src"):
            a = re.search(rf'{attr_name}=["\']([^"\']+)["\']', attrs, re.I)
            if a:
                src = a.group(1).strip()
                if _is_naver_image(src):
                    return f"\n\n![]({_normalize_image_url(src)})\n\n"
                return ""
        return ""
    s = re.sub(r"<img\b([^>]*)>", _img_sub, s, flags=re.I | re.DOTALL)
    # Links → [text](url); an anchor with no text (image wrapper / "#" placeholder) is noise
    def _a_sub(m: re.Match) -> str:
        label = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        href = m.group(1).strip()
        if not label or href.startswith("#"):
            return label
        return f"[{label}]({href})"
    s = re.sub(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        _a_sub,
        s,
        flags=re.DOTALL | re.I,
    )
    # Inline emphasis
    s = re.sub(r"</?(?:strong|b)\b[^>]*>", "**", s, flags=re.I)
    s = re.sub(r"</?(?:em|i)\b[^>]*>", "*", s, flags=re.I)
    # Headings — real h1..h6 and SmartEditor title modules
    s = re.sub(r'<div[^>]+class="[^"]*\bse-title-text\b[^"]*"[^>]*>', "\n\n## ", s, flags=re.I)
    s = re.sub(r"<h([1-6])\b[^>]*>", lambda m: "\n\n" + "#" * int(m.group(1)) + " ", s, flags=re.I)
    s = re.sub(r"</h[1-6]>", "\n\n", s, flags=re.I)
    # Quotes
    s = re.sub(r'<div[^>]+class="[^"]*\bse-quotation\b[^"]*"[^>]*>', "\n\n> ", s, flags=re.I)
    s = re.sub(r"<blockquote\b[^>]*>", "\n\n> ", s, flags=re.I)
    s = re.sub(r"</blockquote>", "\n\n", s, flags=re.I)
    # Lists
    s = re.sub(r"<li\b[^>]*>", "\n- ", s, flags=re.I)
    # Horizontal rules (se-horizontalLine)
    s = re.sub(r'<div[^>]+class="[^"]*\bse-horizontalLine\b[^"]*"[^>]*>', "\n\n---\n\n", s, flags=re.I)
    # Block boundaries → paragraph breaks
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(?:p|div|section|figure|figcaption|tr|table|ul|ol)>", "\n\n", s, flags=re.I)
    # Strip whatever tags remain, unescape, clean invisibles
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[​‌‍﻿]", "", s)
    # Whitespace hygiene: trim lines, collapse 3+ blank lines, dedupe repeated images
    s = re.sub(r"[ \t]+", " ", s)
    lines = [ln.strip() for ln in s.split("\n")]
    out: list[str] = []
    pending_quote = False  # a bare ">" marker adopts the next text line (se-quotation)
    for ln in lines:
        if ln == ">":
            pending_quote = True
            continue
        if ln in ("**", "*"):
            continue  # emphasis tag that spanned block elements — leaves a stray marker
        if not ln:
            if out and not out[-1]:
                continue  # collapse blank runs
            out.append(ln)
            continue
        if pending_quote:
            ln = f"> {ln}"
            pending_quote = False
        if ln.startswith("![](") and out and out[-1] == ln:
            continue  # same image emitted twice (lazy-src duplicates)
        out.append(ln)
    return "\n".join(out).strip()


def _extract_text(fragment: str) -> str:
    # Remove scripts and styles
    fragment = re.sub(r"<script[^>]*>.*?</script>", " ", fragment, flags=re.DOTALL | re.I)
    fragment = re.sub(r"<style[^>]*>.*?</style>", " ", fragment, flags=re.DOTALL | re.I)
    # Remove tags
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    # Unescape HTML entities
    fragment = html.unescape(fragment)
    # Drop zero-width/invisible chars (SmartEditor peppers &#8203; everywhere)
    fragment = re.sub(r"[​‌‍﻿]", "", fragment)
    # Normalize whitespace: collapse runs, strip per-line, drop blank-line runs
    fragment = re.sub(r"[ \t]+", " ", fragment)
    lines = [ln.strip() for ln in fragment.split("\n")]
    fragment = "\n".join(ln for ln in lines if ln)
    return fragment.strip()


def _extract_images(fragment: str) -> list[str]:
    imgs: list[str] = []
    seen: set[str] = set()
    # Match src and data-lazy-src attributes on <img> tags
    for tag in re.finditer(r"<img\b([^>]*)>", fragment, re.I | re.DOTALL):
        attrs = tag.group(1)
        for attr_name in ("data-lazy-src", "src"):
            m = re.search(rf'{attr_name}=["\']([^"\']+)["\']', attrs, re.I)
            if m:
                src = m.group(1).strip()
                if _is_naver_image(src):
                    normalized = _normalize_image_url(src)
                    if normalized not in seen:
                        seen.add(normalized)
                        imgs.append(normalized)
                    break
    return imgs


_NAVER_IMG_DOMAINS = re.compile(
    r"(?:postfiles|blogfiles|mblogthumb|blogpfthumb|cdnthumb)[\w\d]*\.pstatic\.net",
    re.I,
)


def _is_naver_image(url: str) -> bool:
    return bool(_NAVER_IMG_DOMAINS.search(url))


def _normalize_image_url(url: str) -> str:
    # Replace or add ?type= query param with w966 for high-res
    if "?" in url:
        url = re.sub(r"(?<=\?|&)type=[^&]*", "type=w966", url)
        if "type=" not in url:
            url = url + "&type=w966"
    else:
        url = url + "?type=w966"
    return url


# ---------------------------------------------------------------------------
# Output / persistence
# ---------------------------------------------------------------------------

def load_existing(posts_path: str) -> dict[str, dict]:
    if not os.path.exists(posts_path):
        return {}
    try:
        with open(posts_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {str(p["logNo"]): p for p in data if "logNo" in p}
    except Exception:
        return {}


def save_posts(posts_path: str, posts: dict[str, dict]):
    os.makedirs(os.path.dirname(posts_path), exist_ok=True)
    ordered = sorted(posts.values(), key=lambda p: p.get("date", ""), reverse=True)
    with open(posts_path, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="네이버 블로그 전체 글 수집기")
    parser.add_argument("--blog-id", required=True, help="블로그 아이디 (URL의 {blogId})")
    parser.add_argument("--outdir", required=True, help="출력 루트 디렉터리")
    parser.add_argument("--max-posts", type=int, default=200, help="최대 수집 글 수 (기본 200)")
    parser.add_argument("--delay", type=float, default=0.5, help="요청 간 대기 초 (기본 0.5)")
    parser.add_argument("--since", default=None, help="이 날짜 이후 글만 수집 (YYYY-MM-DD)")
    parser.add_argument(
        "--rss-only",
        action="store_true",
        help="비공개 post-list API를 쓰지 않고 RSS(최근 글)만 수집 — org-evidence 계약의 기본 경로",
    )
    parser.add_argument(
        "--owner-authorized",
        action="store_true",
        help=(
            "소유자가 자기 블로그 수집을 승인했음을 확인하는 플래그. "
            "이게 없으면 스크립트는 실행을 거부한다 (아래 robots 게이트 참조)."
        ),
    )
    args = parser.parse_args()

    # ---- robots gate -------------------------------------------------------
    # 실측(2026-08-25) blog.naver.com / m.blog.naver.com / rss.blog.naver.com:
    #   - `Claude-User` 그룹 없음
    #   - `ClaudeBot`, `Claude-SearchBot` → Disallow: /  (이름 명시)
    #   - 상단 주석: "BOT ACCESS FOR THE PURPOSES OF AI TRAINING AND
    #     RETRIEVAL-AUGMENTED GENERATION (RAG) IS STRICTLY PROHIBITED."
    # 게다가 이 스크립트는 모바일 Safari UA를 흉내 내므로(MOBILE_UA) 스킬이 금지한
    # user-agent 위장에 해당한다. 따라서 제3자 블로그 수집 용도로는 실행 금지.
    # 유일하게 허용되는 경로는 **소유자 본인이 자기 블로그를 내보내는 경우**이고,
    # 그때는 --owner-authorized 로 명시하고 report.md 에 근거를 남긴다.
    if not args.owner_authorized:
        print(
            "[refused] blog.naver.com robots가 Claude 에이전트를 차단하고 AI/RAG 목적 수집을\n"
            "          명시적으로 금지합니다. 이 스크립트는 기본적으로 실행되지 않습니다.\n"
            "          - 소유자 경로: 원장님의 스마트플레이스/블로그 관리자 내보내기를 받아\n"
            "            .scrape-out/{slug}/owner/ 에 넣고 source=\"owner-provided\"로 기록\n"
            "          - 소유자가 자기 블로그 수집을 승인한 경우에만 --owner-authorized 사용\n"
            "          근거: skills/org-scrape/references/claude-browser.md (Rule 3, intent check)"
        )
        raise SystemExit(2)
    print("[warn] --owner-authorized: 소유자 승인 전제로 진행합니다. report.md에 근거를 남기세요.")

    blog_id = args.blog_id
    posts_path = os.path.join(args.outdir, "naver_blog", blog_id, "posts.json")

    print(f"[info] 블로그: {blog_id}")
    print(f"[info] 출력 경로: {posts_path}")

    # 1. Load existing
    existing = load_existing(posts_path)
    print(f"[info] 기존 수집본: {len(existing)}개")

    # 2. Fetch post list
    print("[info] 글 목록 수집 중...")
    if args.rss_only:
        print("[info] --rss-only: 비공개 API 생략, RSS만 사용")
        post_list = fetch_rss_posts(blog_id)[: args.max_posts]
    else:
        post_list = fetch_post_list(blog_id, args.max_posts, args.delay, args.since)
        if not post_list:
            print("[warn] API로 글 목록 수집 실패. RSS 폴백 시도...")
            post_list = fetch_rss_posts(blog_id)

    if not post_list:
        print("[error] 글 목록을 가져올 수 없습니다.")
        return

    print(f"[info] 글 목록 {len(post_list)}개 확인")

    # 3. Fetch bodies for new posts
    new_count = 0
    skip_count = 0
    failed: list[str] = []

    for i, item in enumerate(post_list):
        log_no = str(item["logNo"])

        # Skip posts already collected — UNLESS the stored record predates a schema
        # addition (e.g. no `md` body). Backfilling keeps one corpus consistent instead
        # of forcing a full re-crawl after a parser upgrade.
        if log_no in existing and existing[log_no].get("md"):
            skip_count += 1
            continue

        print(f"[{i+1}/{len(post_list)}] 수집 중: {item['title'][:50]} (logNo={log_no})")
        try:
            body = fetch_post_body(blog_id, log_no, args.delay)
        except Exception as e:
            print(f"  [error] 예외 발생: {e}")
            body = {"text": "", "md": "", "images": [], "parse": "failed"}

        if body["parse"] == "failed":
            failed.append(log_no)

        post_record = {
            "logNo": log_no,
            "title": item["title"],
            "date": item["date"],
            "url": f"https://blog.naver.com/{blog_id}/{log_no}",
            "text": body["text"],
            # Markdown twin — structure + image positions preserved. Prefer this over
            # `text` when writing excerpts / related-post bands / any post rendering.
            "md": body.get("md", ""),
            "text_length": len(body["text"]),
            "images": body["images"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "parse": body["parse"],
        }
        existing[log_no] = post_record
        new_count += 1

        # Save incrementally every 10 posts
        if new_count % 10 == 0:
            save_posts(posts_path, existing)

    # 4. Final save
    save_posts(posts_path, existing)

    # 5. Summary
    print("\n========== 수집 요약 ==========")
    print(f"총 글 수:     {len(post_list)}")
    print(f"신규 수집:    {new_count}")
    print(f"스킵 (기존):  {skip_count}")
    print(f"파싱 실패:    {len(failed)}")
    if failed:
        print(f"실패 logNo:   {', '.join(failed)}")
    print(f"저장 경로:    {posts_path}")
    print("================================")


if __name__ == "__main__":
    main()
