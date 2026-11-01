"""経済・市場メディアの無料見出しを集め、Gemini無料APIで日本語要約するスクリプト。"""

import datetime
import os
import sys

from google import genai
from pydantic import BaseModel, Field

from .sources import SOURCES

SYSTEM_INSTRUCTION = """あなたは金融市場に詳しいアナリストです。
ユーザーが渡す各メディアの見出し一覧を、見出しから分かる範囲だけで日本語に要約してください。
見出しにない事実は推測で補わないこと。見出しの発行日が古いもの・[日付不明]のものを、今日の出来事として断定しないこと。出力は指定のJSONスキーマに従います。
 
title / description / body の3項目を持つJSONで返すこと(各項目の意味はスキーマの説明に従う)。
body は次の形式のMarkdown本文とし、前置きやタイトルは書かず 1. から始めること。
 
1. 今日の全体像(3〜5行)
2. 主要テーマ別の整理(株式 / 金利・中央銀行 / 為替・商品 / 地政学・政策 / その他)
   - 複数媒体で共通して扱われている話題には【複数媒体】と付ける
3. 媒体ごとの特徴・注目見出し(各1〜2行。英語見出しは日本語訳を添える)
4. 今日注目すべきポイント(箇条書き3つ)"""


class DigestOutput(BaseModel):
    """Geminiに返させる構造。説明文はそのままモデルへの指示になる。"""

    title: str = Field(
        description="その日の最も重要な内容を表す28字以内のタイトル。日付は含めない。「衝撃」「大暴落」などの煽り表現は避ける"
    )
    description: str = Field(
        description="その日の内容を伝える80〜120字の説明文。1〜2文で、改行を含めない"
    )
    body: str = Field(
        description="Markdown形式の本文。1. から始め、前置き・タイトル・コードブロックは含めない"
    )


def build_prompt(headlines: dict[str, list[str]]) -> str:
    paywall = {s["name"]: s["paywall"] for s in SOURCES}
    blocks = []
    for name, titles in headlines.items():
        lines = "\n".join(f"- {t}" for t in titles)
        blocks.append(f"## {name}(本文: {paywall[name]})\n{lines}")
    body = "\n\n".join(blocks)
    # データを先、依頼を最後に置く
    return f"""本日は{datetime.datetime.now():%Y-%m-%d}です。各見出しの先頭の[ ]は発行日時です。\n\n{body}\n\n---\n上記の見出しを、指示された形式で日本語で要約してください。"""


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


def summarize(prompt: str) -> DigestOutput:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY が未設定です (.env を確認してください)")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    client = genai.Client(api_key=api_key)
    interaction = with_retry(
        lambda: client.interactions.create(
            model=model,
            input=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": DigestOutput.model_json_schema(),
            },
        )
    )

    return DigestOutput.model_validate_json(interaction.output_text)
