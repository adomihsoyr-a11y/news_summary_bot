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
    summary = summarize(build_prompt({"Bloomberg": headlines["Bloomberg"]}))
    summary = build_frontmatter(datetime.now(), summary)

    now = datetime.now()
    out_dir = Path(os.getenv("OUTPUT_DIR", ".")).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"digest_{now:%Y-%m-%d}.md"
    out.write_text(
        f"# マーケット見出しダイジェスト {now:%Y-%m-%d %H:%M}\n\n{summary}\n",
        encoding="utf-8",
    )
    print(f"\n保存しました: {out}")
