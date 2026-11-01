"""経済・市場メディアの無料見出しを集め、Gemini無料APIで日本語要約するスクリプト。"""

import datetime
import json
import sys

import feedparser
import requests
from bs4 import BeautifulSoup

from news_summary_bot.llm_controler import DigestOutput

from .sources import SOURCES

MAX_PER_SOURCE = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def fetch_rss(url: str) -> list[str]:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    return [e.title.strip() for e in feed.entries if getattr(e, "title", None)]


def fetch_web(url: str) -> list[str]:
    """RSSが使えない場合の簡易フォールバック: 見出しタグ内のリンク文字列を拾う。"""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    titles, seen = [], set()
    for tag in soup.select("h1, h2, h3"):
        text = tag.get_text(" ", strip=True)
        if len(text) >= 15 and text not in seen:  # 短すぎるメニュー文言を除外
            seen.add(text)
            titles.append(text)
    return titles


def collect_headlines() -> dict[str, list[str]]:
    result = {}
    for src in SOURCES:
        titles: list[str] = []
        for label, func, url in (
            ("RSS", fetch_rss, src["rss"]),
            ("WEB", fetch_web, src["web"]),
        ):
            try:
                titles = func(url)
                if titles:
                    print(f"[OK]   {src['name']}: {len(titles)}件 ({label})")
                    break
            except (requests.exceptions.RequestException, OSError) as e:
                print(f"[WARN] {src['name']} {label}取得失敗: {e}", file=sys.stderr)
        if not titles:
            print(
                f"[SKIP] {src['name']}: 見出しを取得できませんでした", file=sys.stderr
            )
            continue
        result[src["name"]] = titles[:MAX_PER_SOURCE]
    return result


def build_frontmatter(now: datetime.datetime, content: DigestOutput) -> str:
    """Astro用フロントマター。値はJSON文字列で引用するので、コロンや引用符を含んでもYAMLが壊れない。"""
    q = lambda v: json.dumps(v, ensure_ascii=False)
    return (
        "---\n"
        f"title: {q(f'{now:%Y-%m-%d} {content.title}')}\n"
        f"description: {q(content.description)}\n"
        f"pubDate: {now:%Y-%m-%d %H:%M}\n"
        "---\n\n"
        f"{content.body}\n"
    )
