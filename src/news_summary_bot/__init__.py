import sys
from datetime import datetime
from pathlib import Path

from news_summary_bot.main import build_prompt, collect_headlines, summarize, upload_md


def main() -> None:
    headlines = collect_headlines()
    if not headlines:
        sys.exit("見出しを1件も取得できませんでした")
    summary = summarize(build_prompt(headlines))
    now = datetime.now()
    out = Path(f"digest_{now:%Y-%m-%d}.md")
    out.write_text(
        f"# マーケット見出しダイジェスト {now:%Y-%m-%d %H:%M}\n\n{summary}\n",
        encoding="utf-8",
    )
    web_view_link = upload_md(out)
    print(f"\n保存しました: {web_view_link}")
