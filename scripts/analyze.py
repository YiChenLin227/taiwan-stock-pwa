"""
analyze.py
整合所有抓取資料，呼叫 Claude API 進行 AI 分析
輸出：完整 JSON，含市場解讀、個股分析、動態精選股、新聞摘要
"""

import anthropic
import json
import os
import time
from datetime import datetime

NA = "⚠️ 無法取得資料"


def build_prompt(market: dict, futures: dict, stocks: dict,
                 candidates: list, news: dict, history_rows: list) -> str:
    """組合送給 Claude 的完整 prompt"""

    today = datetime.now().strftime("%Y/%m/%d")
    trade_date = market.get("trade_date", today)

    # 歷史趨勢（前5天）
    history_summary = ""
    if history_rows:
        history_summary = "【近期歷史（供趨勢判斷）】\n"
        for row in history_rows[-5:]:
            history_summary += (
                f"  {row.get('日期','')}："
                f"大盤 {row.get('taiex_close','')}（{row.get('taiex_change_pct','')}）"
                f"外資 {row.get('foreign_net_yi','')}億\n"
            )

    # 候選股摘要
    candidate_summary = "【動態候選股池（請從中選出最強 3~5 隻）】\n"
    for c in candidates:
        candidate_summary += (
            f"  {c.get('name','')}({c.get('code','')}) "
            f"收盤:{c.get('close','')} 漲跌:{c.get('change_pct','')} "
            f"RSI:{c.get('rsi','')} MA20:{c.get('ma20','')} "
            f"量能趨勢:{c.get('vol_trend_pct','')} 5日漲跌:{c.get('price_5d_pct','')} "
            f"入選理由:{c.get('selection_reason','')} "
            f"新聞:{[n['title'] for n in c.get('news',[])[:1]]}\n"
        )

    # 新聞摘要
    news_summary = "【台股新聞】\n"
    for n in news.get("yahoo_tw_news", [])[:5]:
        news_summary += f"  - {n.get('title','')} [{n.get('source','')}]\n"
    news_summary += "【產業新聞】\n"
    for n in news.get("industry_news", [])[:3]:
        news_summary += f"  - {n.get('title','')} [{n.get('source','')}]\n"
    news_summary += "【美國經濟行事曆（近14天）】\n"
    for e in news.get("macro_events", [])[:5]:
        news_summary += f"  - {e.get('date','')} {e.get('title','')}\n"

    prompt = f"""你是一位專業的台股盤前分析師。今天是 {today}，以下是 {trade_date} 的完整市場數據。
請根據所有資料做出深度分析，並以 JSON 格式回覆。

=== 大盤數據 ===
加權指數收盤：{market.get('taiex_close',NA)} 漲跌：{market.get('taiex_change',NA)}（{market.get('taiex_change_pct',NA)}）
成交量：{market.get('volume_trillion',NA)} 兆
外資買賣超：{market.get('foreign_net_yi',NA)} 億
投信買賣超：{market.get('trust_net_yi',NA)} 億
自營商買賣超：{market.get('dealer_net_yi',NA)} 億
三大合計：{market.get('total_net_yi',NA)} 億
融資餘額變化：{market.get('margin_change',NA)} 
融券餘額：{market.get('short_balance',NA)}
台幣匯率：{market.get('twd_usd',NA)}
外資個股買超前3：{market.get('foreign_top3_names',[])}

=== 期貨及選擇權 ===
夜盤台指期收盤：{futures.get('night_futures_last',NA)} 漲跌：{futures.get('night_futures_change',NA)}
台指期未平倉：{futures.get('night_futures_oi',NA)} 口
外資期貨淨多單：{futures.get('futures_foreign_net_oi',NA)} 口
Put/Call比：{futures.get('pc_ratio',NA)}%（{futures.get('pc_sentiment',NA)}）
最大未平倉Call履約價（壓力）：{futures.get('max_call_oi_strike',NA)}
最大未平倉Put履約價（支撐）：{futures.get('max_put_oi_strike',NA)}

=== 全球市場 ===
TSM ADR：{stocks.get('tsm_adr_close',NA)}（{stocks.get('tsm_adr_change_pct',NA)}）
那斯達克：{stocks.get('nasdaq_close',NA)}（{stocks.get('nasdaq_change_pct',NA)}）
道瓊：{stocks.get('dow_close',NA)}（{stocks.get('dow_change_pct',NA)}）
費城半導體SOX：{stocks.get('sox_close',NA)}（{stocks.get('sox_change_pct',NA)}）
VIX恐慌指數：{stocks.get('vix_close',NA)}
美元指數DXY：{stocks.get('dxy_close',NA)}（{stocks.get('dxy_change_pct',NA)}）
10年美債殖利率：{stocks.get('tnx_close',NA)}%
日經225：{stocks.get('nikkei_close',NA)}（{stocks.get('nikkei_change_pct',NA)}）
韓股KOSPI：{stocks.get('kospi_close',NA)}（{stocks.get('kospi_change_pct',NA)}）
恆生指數：{stocks.get('hsi_close',NA)}（{stocks.get('hsi_change_pct',NA)}）
黃金：{stocks.get('gold_close',NA)}（{stocks.get('gold_change_pct',NA)}）
布蘭特原油：{stocks.get('oil_close',NA)}（{stocks.get('oil_change_pct',NA)}）

=== 大盤技術指標 ===
大盤MA20：{stocks.get('taiex_ma20',NA)}  MA60：{stocks.get('taiex_ma60',NA)}
大盤RSI：{stocks.get('taiex_rsi',NA)}
布林上軌：{stocks.get('taiex_boll_upper',NA)}  下軌：{stocks.get('taiex_boll_lower',NA)}

=== 固定個股 ===
台積電2330：收盤 {stocks.get('2330_close',NA)} RSI {stocks.get('2330_rsi',NA)} MA20 {stocks.get('2330_ma20',NA)} MACD-DIF {stocks.get('2330_macd_dif',NA)}
聯發科2454：收盤 {stocks.get('2454_close',NA)} RSI {stocks.get('2454_rsi',NA)} MA20 {stocks.get('2454_ma20',NA)} MACD-DIF {stocks.get('2454_macd_dif',NA)}
國巨2327：收盤 {stocks.get('2327_close',NA)} RSI {stocks.get('2327_rsi',NA)} MA20 {stocks.get('2327_ma20',NA)} MACD-DIF {stocks.get('2327_macd_dif',NA)}

{history_summary}
{candidate_summary}
{news_summary}

=== 請以以下 JSON 格式回覆，不要有任何額外文字 ===

{{
  "market_direction": "中性偏多 / 中性偏空 / 強勢多頭 / 強勢空頭 / 盤整 中選一",
  "biggest_risk": "今日最大風險（1~2句）",
  "open_range_low": "預估開盤下限點位（純數字）",
  "open_range_high": "預估開盤上限點位（純數字）",
  "key_support": "關鍵支撐點位",
  "key_resistance": "關鍵壓力點位",

  "taiex_ai": "大盤 AI 解讀（100~150字，含技術面+籌碼面+全球連動分析）",
  "institutional_ai": "三大法人 AI 解讀（80~120字）",
  "margin_ai": "融資融券 AI 解讀（60~80字）",
  "fx_ai": "匯率 AI 解讀（60~80字）",
  "futures_ai": "期貨選擇權 AI 解讀（80~100字，含P/C比、外資期貨部位、最大未平倉）",
  "global_ai": "全球市場 AI 解讀（80~100字，含日韓港、VIX、美債、DXY）",
  "strategy_ai": "今日核心操盤策略（100~150字）",
  "risk_warning": "今日風控提醒（3~4條重點）",
  "sector_trend_ai": "產業趨勢觀察（80~100字，根據新聞判斷）",
  "macro_ai": "總經事件提醒（60~80字，含FRED行事曆重點）",

  "fixed_stocks": {{
    "2330": {{
      "direction": "積極做多 / 偏多觀察 / 觀望等待 / 偏空謹慎 中選一",
      "buy_range": "建議買入區間（例：2400~2430）",
      "stop_loss": "停損線（純數字）",
      "target": "中線目標（純數字）",
      "ai_insight": "台積電 AI 解讀（80~100字）",
      "news_summary": [
        {{"title": "新聞標題（中文）", "url": "原始連結"}}
      ]
    }},
    "2454": {{
      "direction": "",
      "buy_range": "",
      "stop_loss": "",
      "target": "",
      "ai_insight": "",
      "news_summary": []
    }},
    "2327": {{
      "direction": "",
      "buy_range": "",
      "stop_loss": "",
      "target": "",
      "ai_insight": "",
      "news_summary": []
    }}
  }},

  "top_stocks": [
    {{
      "code": "股票代號",
      "name": "股票名稱",
      "direction": "積極做多 / 偏多觀察 / 觀望等待 中選一",
      "buy_range": "建議買入區間",
      "stop_loss": "停損線",
      "target": "中線目標",
      "theme": "核心題材（10字內）",
      "ai_insight": "AI 解讀（80~100字）",
      "news_summary": [
        {{"title": "新聞標題（中文）", "url": "原始連結"}}
      ]
    }}
  ],
  "top_stocks_reason": "這次選出這幾隻的整體說明（50~80字）",

  "today_strongest_sector": "今日最強族群（10字內）",
  "today_biggest_risk_stock": "今日最需警惕標的（股名+原因，30字內）",

  "full_ai_text": "完整 AI 盤前解讀（300~500字，分今日定性/短線/中線/行動清單四段落）",
  "ai_opportunities": "今日三大機會（每條25字內，用\n分隔）",
  "ai_risks_text": "今日三大風險（每條25字內，用\n分隔）",
  "ai_best_strategy": "今日最佳策略一句話（40字內）",
  "risk_ai": "風控建議（含具體停損點位，3條重點，用\n分隔）",

  "sectors": [
    {{
      "num": "①",
      "name": "半導體製造",
      "reps": "台積電(2330)・聯電(2303)・世界先進(5347)",
      "trend": "中性偏空→逢低多",
      "trend_css": "gold",
      "trend_bg": "rgba(245,185,66,0.12)",
      "desc": "當日趨勢動態預估（50~80字）",
      "week_outlook": "一週展望（5字內）",
      "week_css": "gold",
      "week_bg": "rgba(239,68,68,0.08)",
      "month_outlook": "一個月展望（5字內）",
      "month_css": "dn",
      "month_bg": "rgba(16,185,129,0.08)",
      "key_event": "關鍵事件（10字內）",
      "highlight": false
    }},
    {{ "num": "②", "name": "IC 設計", "reps": "聯發科(2454)・瑞昱(2379)・聯詠(3034)", "trend": "", "trend_css": "dn", "trend_bg": "rgba(16,185,129,0.12)", "desc": "", "week_outlook": "", "week_css": "dn", "week_bg": "rgba(16,185,129,0.08)", "month_outlook": "", "month_css": "dn", "month_bg": "rgba(16,185,129,0.08)", "key_event": "", "highlight": false }},
    {{ "num": "③", "name": "AI 伺服器 / ODM", "reps": "廣達(2382)・緯創(3231)・鴻海(2317)", "trend": "", "trend_css": "dn", "trend_bg": "rgba(16,185,129,0.15)", "desc": "", "week_outlook": "", "week_css": "dn", "week_bg": "rgba(16,185,129,0.12)", "month_outlook": "", "month_css": "dn", "month_bg": "rgba(16,185,129,0.12)", "key_event": "", "highlight": false }},
    {{ "num": "④", "name": "先進封裝", "reps": "日月光投控(3711)・京元電(2449)・矽格(6257)", "trend": "", "trend_css": "gold", "trend_bg": "rgba(245,185,66,0.12)", "desc": "", "week_outlook": "", "week_css": "gold", "week_bg": "rgba(245,185,66,0.08)", "month_outlook": "", "month_css": "dn", "month_bg": "rgba(16,185,129,0.08)", "key_event": "", "highlight": false }},
    {{ "num": "⑤", "name": "被動元件", "reps": "國巨(2327)・華新科(2492)・禾伸堂(3026)", "trend": "", "trend_css": "gold", "trend_bg": "rgba(245,185,66,0.12)", "desc": "", "week_outlook": "", "week_css": "dn", "week_bg": "rgba(16,185,129,0.08)", "month_outlook": "", "month_css": "dn", "month_bg": "rgba(16,185,129,0.08)", "key_event": "", "highlight": false }},
    {{ "num": "⑥", "name": "電源 / 散熱", "reps": "台達電(2308)・奇鋐(3017)・建準(2421)", "trend": "", "trend_css": "gold", "trend_bg": "rgba(245,185,66,0.12)", "desc": "", "week_outlook": "", "week_css": "gold", "week_bg": "rgba(245,185,66,0.08)", "month_outlook": "", "month_css": "dn", "month_bg": "rgba(16,185,129,0.08)", "key_event": "", "highlight": false }},
    {{ "num": "⑦", "name": "記憶體", "reps": "南亞科(2408)・群聯(8299)・威剛(3260)", "trend": "", "trend_css": "sub", "trend_bg": "rgba(255,255,255,0.05)", "desc": "", "week_outlook": "", "week_css": "sub", "week_bg": "rgba(255,255,255,0.04)", "month_outlook": "", "month_css": "gold", "month_bg": "rgba(245,185,66,0.06)", "key_event": "", "highlight": false }},
    {{ "num": "⑧", "name": "網通 / 光連接器", "reps": "台光電(2383)・正崴(2392)・上詮(3363)", "trend": "", "trend_css": "gold", "trend_bg": "rgba(245,185,66,0.12)", "desc": "", "week_outlook": "", "week_css": "dn", "week_bg": "rgba(16,185,129,0.08)", "month_outlook": "", "month_css": "dn", "month_bg": "rgba(16,185,129,0.08)", "key_event": "", "highlight": false }}
  ],

  "earnings_calendar": [
    {{"date": "月/日", "name": "公司名稱+代號", "type": "法說會", "importance_stars": "★★★", "css": "hold", "is_important": false}}
  ],
  "earnings_ai": "本月法說會/財報行事曆 AI 解讀（80~120字）",

  "review_market": [
    {{"item": "大盤方向", "forecast": "昨日預測", "actual": "實際結果", "actual_css": "dn", "result": "accurate"}},
    {{"item": "外資方向", "forecast": "", "actual": "", "actual_css": "dn", "result": "accurate"}},
    {{"item": "台積電走勢", "forecast": "", "actual": "", "actual_css": "dn", "result": "accurate"}},
    {{"item": "成交量", "forecast": "", "actual": "", "actual_css": "dn", "result": "accurate"}}
  ],
  "review_stocks": [
    {{"name": "台積電 2330", "forecast": "昨日建議", "actual": "實際漲跌幅", "actual_css": "dn", "result": "accurate"}}
  ],
  "review_ai": "復盤 AI 解讀（100~150字：哪裡判斷正確/哪裡需要改進）",

  "reanalysis_count": 0
}}"""
    return prompt


def _extract_json(raw: str) -> dict:
    """Try to extract valid JSON even from truncated Claude response."""
    # Remove markdown code block
    if "```" in raw:
        for part in raw.split("```"):
            s = part.strip()
            if s.startswith("json"):
                s = s[4:].strip()
            if s.startswith("{"):
                raw = s
                break
    raw = raw.strip()
    # Find first {
    start = raw.find("{")
    if start > 0:
        raw = raw[start:]
    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try finding last balanced } to recover truncated JSON
    depth = 0
    last_balanced = -1
    in_str = False
    escape = False
    for i, ch in enumerate(raw):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_str = not in_str
            continue
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    last_balanced = i
    if last_balanced > 0:
        try:
            return json.loads(raw[:last_balanced + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("Cannot extract valid JSON from response")


def call_claude(prompt: str, api_key: str, max_retries: int = 3) -> dict:
    """呼叫 Claude API，失敗自動重試"""
    client = anthropic.Anthropic(api_key=api_key)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  [Claude API] 第 {attempt} 次呼叫...")
            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = message.content[0].text.strip()
            result = _extract_json(raw)
            print(f"  [Claude API] 成功，選出 {len(result.get('top_stocks',[]))} 隻精選股")
            return result

        except (json.JSONDecodeError, ValueError) as e:
            print(f"  [Claude API] JSON 解析失敗（第{attempt}次）: {e}")
            if attempt == max_retries:
                return _fallback_result()
            time.sleep(5)
        except Exception as e:
            print(f"  [Claude API] 錯誤（第{attempt}次）: {e}")
            if attempt == max_retries:
                return _fallback_result()
            time.sleep(10)

    return _fallback_result()


def _fallback_result() -> dict:
    """Claude API 完全失敗時的備用空結構"""
    print("  [Claude API] 使用備用空結構")
    return {
        "market_direction": NA,
        "biggest_risk": NA,
        "open_range_low": NA, "open_range_high": NA,
        "key_support": NA, "key_resistance": NA,
        "taiex_ai": NA, "institutional_ai": NA, "margin_ai": NA,
        "fx_ai": NA, "futures_ai": NA, "global_ai": NA,
        "strategy_ai": NA, "risk_warning": NA, "risk_ai": NA,
        "sector_trend_ai": NA, "macro_ai": NA,
        "full_ai_text": NA, "ai_opportunities": NA,
        "ai_risks_text": NA, "ai_best_strategy": NA,
        "fixed_stocks": {
            "2330": {"direction": NA, "buy_range": NA, "stop_loss": NA, "target": NA, "ai_insight": NA, "news_summary": []},
            "2454": {"direction": NA, "buy_range": NA, "stop_loss": NA, "target": NA, "ai_insight": NA, "news_summary": []},
            "2327": {"direction": NA, "buy_range": NA, "stop_loss": NA, "target": NA, "ai_insight": NA, "news_summary": []},
        },
        "top_stocks": [],
        "top_stocks_reason": NA,
        "today_strongest_sector": NA,
        "today_biggest_risk_stock": NA,
        "sectors": [],
        "earnings_calendar": [],
        "earnings_ai": NA,
        "review_market": [],
        "review_stocks": [],
        "review_ai": NA,
        "reanalysis_count": 0
    }


def analyze(market: dict, futures: dict, stocks: dict,
            candidates: list, news: dict, history_rows: list,
            api_key: str = "") -> dict:
    """主入口：組 prompt → 呼叫 Claude → 回傳分析結果"""
    key = api_key or os.environ.get("CLAUDE_API_KEY", "")
    if not key:
        print("[analyze] 未設定 CLAUDE_API_KEY")
        return _fallback_result()

    print("[analyze] 組合分析 prompt...")
    prompt = build_prompt(market, futures, stocks, candidates, news, history_rows)

    print("[analyze] 呼叫 Claude API...")
    result = call_claude(prompt, key)

    return result


if __name__ == "__main__":
    # 測試用：印出 prompt 結構（不實際呼叫 API）
    dummy = {}
    prompt = build_prompt(dummy, dummy, dummy, [], {"yahoo_tw_news":[],"industry_news":[],"macro_events":[]}, [])
    print(prompt[:500], "\n...(截斷)")
