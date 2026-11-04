"""経済・市場メディアの無料見出しを集め、Gemini無料APIで日本語要約するスクリプト。"""

import datetime
import os
import sys

import tiktoken
from google import genai
from google.genai._gaos.types.interactions import Interaction
from pydantic import BaseModel, Field

from .sources import Source

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


class LLMOutput(BaseModel):
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


class DigestOutput(LLMOutput):
    """Digest用の出力。"""

    model: str


def build_prompt(
    headlines: dict[str, list[str]], now: datetime.datetime, sources: list[Source]
) -> str:
    paywall = {s["name"]: s["paywall"] for s in sources}
    blocks = []
    for name, titles in headlines.items():
        lines = "\n".join(f"- {t}" for t in titles)
        blocks.append(f"## {name}(本文: {paywall[name]})\n{lines}")
    body = "\n\n".join(blocks)
    enc = tiktoken.get_encoding("o200k_base")

    prompt = f"""本日は{now:%Y-%m-%d}です。各見出しの先頭の[ ]は発行日時です。\n\n{body}\n\n---\n上記の見出しを、指示された形式で日本語で要約してください。"""
    print(
        f"[INFO] プロンプト概算: {len(enc.encode(prompt)):,} tokens / {len(prompt):,} 文字"
    )
    return prompt


import re
import time

NON_RETRYABLE = {400, 401, 403, 404}  # 再試行しても直らないエラー

import threading
from contextlib import contextmanager


@contextmanager
def heartbeat(label: str, interval: float = 10.0):
    """ブロックの実行中、interval秒ごとに経過時間を表示する。"""
    stop = threading.Event()
    start = time.monotonic()

    def _run():
        while not stop.wait(interval):
            print(
                f"[INFO] {label} 待機中... {time.monotonic() - start:.0f}秒経過",
                flush=True,
            )

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    try:
        yield
    except BaseException:
        print(f"[INFO] {label} 失敗 ({time.monotonic() - start:.1f}秒)", flush=True)
        raise
    else:
        print(f"[INFO] {label} 完了 ({time.monotonic() - start:.1f}秒)", flush=True)
    finally:
        stop.set()
        t.join()


class AttemptTimeout(Exception):
    """1回の試行が switch_after 秒を超えた。"""


def run_with_timeout(fn, timeout: float):
    """fn を別スレッドで実行し、timeout 秒で待つのをやめる。"""
    box: dict = {}
    done = threading.Event()

    def _target():
        try:
            box["value"] = fn()
        except Exception as e:
            box["error"] = e
        finally:
            done.set()

    threading.Thread(target=_target, daemon=True).start()
    if not done.wait(timeout):
        raise AttemptTimeout(f"{timeout:.0f}秒以内に応答がありませんでした")
    if "error" in box:
        raise box["error"]
    return box["value"]


def with_retry(
    call, models: list[str], max_attempts: int = 6, switch_after: float = 120.0
) -> Interaction:
    """
    call(model) を実行する。
    - switch_after 秒応答がなければ次のモデルに切り替えて即再試行
    - 503/429/通信エラーも待ちを伸ばしながら同じモデルで再試行
    """
    model_idx = 0
    for attempt in range(max_attempts):
        model = models[model_idx % len(models)]
        label = f"API呼び出し [{model}] (試行 {attempt + 1}/{max_attempts})"
        print(f"[INFO] {label} 開始", flush=True)
        try:
            with heartbeat(label):
                return run_with_timeout(lambda m=model: call(m), switch_after)
        except AttemptTimeout:
            if attempt == max_attempts - 1:
                raise
            model_idx += 1
            nxt = models[model_idx % len(models)]
            print(
                f"[WARN] {model} が{switch_after:.0f}秒応答なし。{nxt} に切り替えます",
                flush=True,
            )
            continue  # 待たずに即再試行
        except Exception as e:
            m = re.search(r"Error code: (\d{3})", str(e))
            code = getattr(e, "status_code", None) or (int(m.group(1)) if m else None)
            if code in NON_RETRYABLE or attempt == max_attempts - 1:
                raise
            model_idx += 1
            nxt = models[model_idx % len(models)]
            print(
                f"[WARN] {model} が{switch_after:.0f}秒応答なし。{nxt} に切り替えます",
                flush=True,
            )
            continue  # 待たずに即再試行


def version_key(model):
    match = re.match(r"gemini-(\d+(?:\.\d+)?)(?:-|$)", model)
    if match:
        return (1, tuple(map(int, match.group(1).split("."))))
    return (0, ())  # non-versioned Gemini models go last


def list_models() -> list[str]:
    """モデルをリストする。"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    EXCLUDE = (
        "image",
        "tts",
        "lyria",
        "nano-banana",
        "transcribe",
        "omni",
        "robotics",
        "computer-use",
        "customtools",
        "antigravity",
        "argon",
        "gemini-3.7-flash",
    )

    text_models: list[str] = []
    for m in client.models.list():
        name = m.name.removeprefix("models/")
        if "generateContent" not in (m.supported_actions or []):
            continue
        if any(x in name.lower() for x in EXCLUDE):
            continue
        text_models.append(name)

    text_models = sorted(text_models, key=version_key, reverse=True)

    return text_models


def summarize(prompt: str) -> DigestOutput:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY が未設定です (.env を確認してください)")
    client = genai.Client(api_key=api_key)

    def call(model: str) -> Interaction:
        return client.interactions.create(
            model=model,
            input=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": LLMOutput.model_json_schema(),
            },
        )

    interaction = with_retry(call, list_models(), switch_after=100.0)
    llm_output = LLMOutput.model_validate_json(interaction.output_text)
    output = DigestOutput(**llm_output.model_dump(), model=interaction.model)

    return output
