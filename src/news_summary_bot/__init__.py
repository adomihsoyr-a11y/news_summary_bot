import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from news_summary_bot.llm_controler import build_prompt, summarize
from news_summary_bot.main import (
    build_frontmatter,
    collect_headlines,
    load_local_env,
)
from news_summary_bot.sources import JP_SOURCES, US_SOURCES


def out_file(file_name: str, content: str) -> None:
    """ファイルを出力する。"""
    out_dir = Path(os.getenv("OUTPUT_DIR", ".")).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / file_name
    out.write_text(
        content,
        encoding="utf-8",
    )
    print(f"\n保存しました: {out}")


def summarize_jp():
    """日本ニュースを要約する。"""
    headlines = collect_headlines(JP_SOURCES)
    if not headlines:
        sys.exit("見出しを1件も取得できませんでした")
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    summary = summarize(build_prompt(headlines, now, JP_SOURCES))
    summary = build_frontmatter(now, summary)

    out_file(f"jp_digest_{now:%Y-%m-%d}.md", summary)


def summarize_en():
    """USニュースを要約する。"""
    headlines = collect_headlines(US_SOURCES)
    if not headlines:
        sys.exit("見出しを1件も取得できませんでした")
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    summary = summarize(build_prompt(headlines, now, US_SOURCES))
    summary = build_frontmatter(now, summary)

    out_file(f"en_digest_{now:%Y-%m-%d}.md", summary)


def main() -> None:
    load_local_env()
    summarize_jp()
    summarize_en()
