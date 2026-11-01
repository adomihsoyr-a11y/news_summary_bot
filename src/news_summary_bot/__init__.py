import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from news_summary_bot.llm_controler import build_prompt, summarize
from news_summary_bot.main import build_frontmatter, collect_headlines


def load_local_env() -> None:
    if os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true":
        return
    load_dotenv()


def main() -> None:
    load_local_env()
    headlines = collect_headlines()
    if not headlines:
        sys.exit("見出しを1件も取得できませんでした")
    summary = summarize(build_prompt(headlines))
    now = datetime.now()
    summary2 = build_frontmatter(now, summary)
    print(summary2)

    out_dir = Path(os.getenv("OUTPUT_DIR", ".")).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"digest_{now:%Y-%m-%d}.md"
    out.write_text(
        summary2,
        encoding="utf-8",
    )
    print(f"\n保存しました: {out}")
