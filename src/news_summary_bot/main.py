"""経済・市場メディアの無料見出しを集め、Gemini無料APIで日本語要約するスクリプト。"""

import os
import sys
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai
from googleapiclient.http import MediaFileUpload

MAX_PER_SOURCE = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# name, RSS(優先), トップページ(フォールバック), 本文の無料度
SOURCES = [
    {
        "name": "Bloomberg",
        "rss": "https://feeds.bloomberg.com/markets/news.rss",
        "web": "https://www.bloomberg.com/markets",
        "paywall": "原則有料",
    },
    {
        "name": "WSJ",
        "rss": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
        "web": "https://www.wsj.com/news/latest-headlines",
        "paywall": "ほぼ有料",
    },
    {
        "name": "Financial Times",
        "rss": "https://www.ft.com/rss/home",
        "web": "https://www.ft.com/markets",
        "paywall": "有料",
    },
    {
        "name": "The Economist",
        "rss": "https://www.economist.com/finance-and-economics/rss.xml",
        "web": "https://www.economist.com/",
        "paywall": "有料",
    },
    {
        "name": "CNBC",
        "rss": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "web": "https://www.cnbc.com/",
        "paywall": "多く無料",
    },
    {
        "name": "MarketWatch",
        "rss": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "web": "https://www.marketwatch.com/",
        "paywall": "多く無料",
    },
    {
        "name": "Investing.com日本版",
        "rss": "https://jp.investing.com/rss/news.rss",
        "web": "https://jp.investing.com/news/",
        "paywall": "多く無料",
    },
]


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
            except Exception as e:
                print(f"[WARN] {src['name']} {label}取得失敗: {e}", file=sys.stderr)
        if not titles:
            print(
                f"[SKIP] {src['name']}: 見出しを取得できませんでした", file=sys.stderr
            )
            continue
        result[src["name"]] = titles[:MAX_PER_SOURCE]
    return result


def build_prompt(headlines: dict[str, list[str]]) -> str:
    paywall = {s["name"]: s["paywall"] for s in SOURCES}
    blocks = []
    for name, titles in headlines.items():
        lines = "\n".join(f"- {t}" for t in titles)
        blocks.append(f"## {name}(本文: {paywall[name]})\n{lines}")
    body = "\n\n".join(blocks)
    return f"""あなたは金融市場に詳しいアナリストです。以下は各メディアの本日の見出しです。
見出しのみから分かる範囲で、日本語で次の形式にまとめてください。見出しにない事実は推測で補わないこと。

1. 今日の全体像(3〜5行)
2. 主要テーマ別の整理(株式 / 金利・中央銀行 / 為替・商品 / 地政学・政策 / その他)
   - 複数媒体で共通して扱われている話題には【複数媒体】と付ける
3. 媒体ごとの特徴・注目見出し(各1〜2行。英語見出しは日本語訳を添える)
4. 今日注目すべきポイント(箇条書き3つ)

{body}
"""


import random
import re
import time

NON_RETRYABLE = {400, 401, 403, 404}  # 再試行しても直らないエラー


def with_retry(fn, max_attempts: int = 6):
    """503/429/通信エラーなどを、待ちを伸ばしながら再試行する。"""
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            m = re.search(r"Error code: (\d{3})", str(e))
            code = getattr(e, "status_code", None) or (int(m.group(1)) if m else None)
            if code in NON_RETRYABLE or attempt == max_attempts - 1:
                raise
            wait = 10 * 2**attempt + random.uniform(0, 5)  # 約10, 20, 40, 80, 160秒
            print(
                f"[WARN] {type(e).__name__} (code={code})。{wait:.0f}秒後に再試行 ({attempt + 1}/{max_attempts - 1})"
            )
            time.sleep(wait)


def summarize(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY が未設定です (.env を確認してください)")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    client = genai.Client(api_key=api_key)
    interaction = with_retry(
        lambda: client.interactions.create(model=model, input=prompt)
    )

    return interaction.output_text


SCOPES = [
    "https://www.googleapis.com/auth/drive"
]  # このアプリが作ったファイルのみ操作可
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def upload_md(path: Path) -> str:
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials = Path(__file__).parent.parent.parent / "credentials.json"
            flow = InstalledAppFlow.from_client_secrets_file(credentials, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("drive", "v3", credentials=creds)
        meta = {"name": path.name}
        media = MediaFileUpload(str(path), mimetype="text/markdown")
        f = (
            service.files()
            .create(body=meta, media_body=media, fields="id,webViewLink")
            .execute()
        )
        return f["webViewLink"]
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f"An error occurred: {error}")
