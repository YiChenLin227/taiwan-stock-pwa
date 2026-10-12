#!/usr/bin/env python3
"""
prepare_news.py
用 Anthropic API 的 web search 工具整理盤前新聞，寫入 data/news_latest.json。

fetch_news.py 的 _load_cowork_override() 會讀這個檔：
status == "ok" 且 written_at 在 12 小時內，就優先採用，否則回退到 RSS / FRED。

失敗時不覆寫既有檔案、以 exit code 0 結束，不擋住後續的 update.py。

環境變數：
  CLAUDE_API_KEY   必填
  NEWS_MODEL       選填，預設與 analyze.py 相同
  NEWS_MAX_SEARCH  選填，單次請求的搜尋次數上限（預設 8）
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import anthropic

MODEL = os.environ.get("NEWS_MODEL", "claude-sonnet-5")
MAX_SEARCHES = int(os.environ.get("NEWS_MAX_SEARCH", "8"))
MAX_CONTINUATIONS = 5  # pause_turn 最多續跑幾次
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "news_latest.json")

TW = timezone(timedelta(hours=8))


def log(msg):
    print(f"[prepare_news] {msg}", flush=True)


def build_prompt(now_tw: datetime) -> str:
    today = now_tw.strftime("%Y-%m-%d")
    end = (now_tw + timedelta(days=14)).strftime("%Y-%m-%d")
    return f"""現在是台灣時間 {now_tw.strftime('%Y-%m-%d %H:%M')}，台股開盤前。請用 web search 蒐集盤前需要的資訊：

1. yahoo_tw_news：最近 24 小時內影響台股的重要新聞 5 則（大盤、台積電/權值股、美股與台指期夜盤、外資動向、Fed）。優先 Yahoo奇摩股市、鉅亨網、經濟日報、工商時報。
2. industry_news：最近 24～48 小時的台灣科技產業/半導體/AI 供應鏈新聞 3 則。優先 DIGITIMES、科技新報、MoneyDJ。
3. macro_events：{today} 到 {end} 之間的重要美國經濟事件（CPI、PPI、非農、FOMC 會議/紀錄、GDP、PCE、Fed 主席談話），最多 8 則，依日期排序。

規則：
- 每則新聞的 url 必須是你在搜尋結果中實際看到的文章網址，不可自行編造或拼湊。找不到就少列幾則。
- title 使用繁體中文，簡潔描述（可沿用原標題）。
- 新聞 date 格式為 MM-DD（台灣時間）；macro_events 的 date 格式為 YYYY-MM-DD。
- macro_events 的 source 填資料來源網址。

最後只輸出一個 JSON 物件，用 ```json 包起來，格式如下，不要有其他說明：
```json
{{
  "yahoo_tw_news": [{{"title": "", "url": "", "date": "MM-DD", "source": "媒體名稱"}}],
  "industry_news": [{{"title": "", "url": "", "date": "MM-DD", "source": "媒體名稱"}}],
  "macro_events": [{{"title": "", "date": "YYYY-MM-DD", "source": "https://..."}}]
}}
```"""


def run_search(client: anthropic.Anthropic, prompt: str):
    """呼叫 Claude + web search，處理 pause_turn。回傳 (最終文字, 搜尋結果中出現過的 URL 集合)。"""
    tools = [{
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": MAX_SEARCHES,
        "user_location": {"type": "approximate", "country": "TW", "city": "Taipei", "timezone": "Asia/Taipei"},
    }]
    messages = [{"role": "user", "content": prompt}]
    seen_urls = set()
    texts = []

    for i in range(MAX_CONTINUATIONS + 1):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=messages,
            tools=tools,
        )
        for block in resp.content:
            btype = getattr(block, "type", "")
            if btype == "web_search_tool_result":
                content = getattr(block, "content", None)
                if isinstance(content, list):
                    for r in content:
                        url = getattr(r, "url", None)
                        if url:
                            seen_urls.add(url)
                else:
                    log(f"  搜尋錯誤: {getattr(content, 'error_code', content)}")
            elif btype == "text":
                texts.append(block.text)
                for c in getattr(block, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url:
                        seen_urls.add(url)

        log(f"  第 {i + 1} 輪 stop_reason={resp.stop_reason}，累計搜尋結果網址 {len(seen_urls)} 個")
        if resp.stop_reason != "pause_turn":
            break
        # 原封不動送回 assistant 內容以繼續
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": resp.content},
        ]

    return "\n".join(texts), seen_urls


def extract_json(text: str) -> dict:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    candidate = blocks[-1] if blocks else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(candidate)


def _norm(url: str) -> str:
    return url.strip().rstrip("/").split("#")[0]


def clean_news(items, seen_norm: set, limit: int) -> list:
    """只保留有標題、且 URL 出現在搜尋結果中的新聞，避免編造的連結。"""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title", "")).strip()
        url = str(it.get("url", "")).strip()
        if not title or not url.startswith("http"):
            continue
        if _norm(url) not in seen_norm:
            log(f"  略過（URL 不在搜尋結果中）: {title[:30]}")
            continue
        out.append({
            "title": title,
            "url": url,
            "date": str(it.get("date", "")).strip(),
            "source": str(it.get("source", "")).strip(),
        })
    return out[:limit]


def clean_events(items, limit: int = 8) -> list:
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title", "")).strip()
        date = str(it.get("date", "")).strip()
        if not title or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            continue
        out.append({"title": title, "date": date, "source": str(it.get("source", "")).strip()})
    out.sort(key=lambda e: e["date"])
    return out[:limit]


def main() -> int:
    api_key = os.environ.get("CLAUDE_API_KEY", "")
    if not api_key:
        log("未設定 CLAUDE_API_KEY，略過")
        return 0

    now_utc = datetime.now(timezone.utc)
    prompt = build_prompt(now_utc.astimezone(TW))
    client = anthropic.Anthropic(api_key=api_key)

    data = None
    for attempt in range(1, 3):
        try:
            log(f"呼叫 {MODEL} + web search（第 {attempt} 次）...")
            text, seen = run_search(client, prompt)
            raw = extract_json(text)
            seen_norm = {_norm(u) for u in seen}
            data = {
                "yahoo_tw_news": clean_news(raw.get("yahoo_tw_news"), seen_norm, 5),
                "industry_news": clean_news(raw.get("industry_news"), seen_norm, 3),
                "macro_events": clean_events(raw.get("macro_events")),
            }
            if data["yahoo_tw_news"] or data["industry_news"]:
                break
            log("沒有可用的新聞")
            data = None
        except Exception as e:
            log(f"錯誤: {type(e).__name__}: {e}")
        time.sleep(5)

    if not data:
        log("失敗，保留既有 news_latest.json；update.py 會依 12 小時規則決定是否回退到 RSS")
        return 0

    result = {
        "written_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "source": "anthropic_web_search",
        **data,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log(f"完成：台股 {len(data['yahoo_tw_news'])}、產業 {len(data['industry_news'])}、"
        f"總經 {len(data['macro_events'])} → data/news_latest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
