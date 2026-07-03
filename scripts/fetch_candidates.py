"""
fetch_candidates.py
動態精選股候選池：外資買超前30 + 成交量前20 → 合併去重 → 抓基本資料
供 AI 從中選出最強 3~5 隻
"""

import json
import yfinance as yf
import pandas as pd

NA = "⚠️ 無法取得資料"

# 固定3股不列入動態候選
FIXED_CODES = {"2330", "2454", "2327"}


def build_candidate_pool(foreign_top30: list, volume_top20: list) -> list:
    """合併外資買超前30 + 成交量前20，去重後排除固定3股"""
    seen = set()
    pool = []

    for item in foreign_top30:
        code = str(item.get("code", "")).strip()
        if code and code not in FIXED_CODES and code not in seen:
            seen.add(code)
            pool.append({"code": code, "name": item.get("name", ""), "reason": "外資買超"})

    for item in volume_top20:
        code = str(item.get("code", "")).strip()
        if code and code not in FIXED_CODES and code not in seen:
            seen.add(code)
            pool.append({"code": code, "name": item.get("name", ""), "reason": "成交量前20"})

    return pool[:50]  # 最多50隻


def fetch_candidate_basic(code: str, name: str) -> dict:
    """抓單一候選股的基本資料（快速，不算複雜技術指標）"""
    ticker = f"{code}.TW"
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="30d")
        if hist.empty:
            raise ValueError("無資料")

        close_series = hist["Close"]
        last = round(float(close_series.iloc[-1]), 2)
        prev = round(float(close_series.iloc[-2]), 2)
        change_pct = round(((last - prev) / prev) * 100, 2)

        # RSI14
        delta = close_series.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = round((100 - 100 / (1 + rs)).iloc[-1], 2)

        # MA20
        ma20 = round(close_series.rolling(20).mean().iloc[-1], 2)

        # 成交量趨勢（近5日vs近20日）
        vol_series = hist["Volume"]
        vol5 = vol_series.iloc[-5:].mean()
        vol20 = vol_series.mean()
        vol_trend = round((vol5 / vol20 - 1) * 100, 1) if vol20 > 0 else 0

        # 近5日漲跌
        price_5d = round(((last - float(close_series.iloc[-6])) / float(close_series.iloc[-6])) * 100, 2) if len(close_series) >= 6 else NA

        # 新聞（最多2則）
        news_list = []
        try:
            raw_news = t.news or []
            for n in raw_news[:2]:
                content = n.get("content", {})
                title = content.get("title", n.get("title", ""))
                url = content.get("canonicalUrl", {}).get("url", "") or n.get("link", "")
                if title:
                    news_list.append({"title": title, "url": url})
        except:
            pass

        return {
            "code": code,
            "name": name,
            "close": str(last),
            "change_pct": f"{change_pct}%",
            "rsi": str(rsi),
            "ma20": str(ma20),
            "vol_trend_pct": f"{vol_trend}%",
            "price_5d_pct": f"{price_5d}%" if price_5d != NA else NA,
            "news": news_list,
            "source": f"https://goodinfo.tw/tw/StockInfo.asp?STOCK_ID={code}",
            "tv_source": f"https://tw.tradingview.com/chart/?symbol=TWSE%3A{code}",
        }
    except Exception as e:
        return {
            "code": code, "name": name,
            "close": NA, "change_pct": NA, "rsi": NA,
            "ma20": NA, "vol_trend_pct": NA, "price_5d_pct": NA,
            "news": [],
            "source": f"https://goodinfo.tw/tw/StockInfo.asp?STOCK_ID={code}",
            "tv_source": f"https://tw.tradingview.com/chart/?symbol=TWSE%3A{code}",
            "error": str(e)
        }


def fetch_all(foreign_top30: list, volume_top20: list) -> list:
    """
    外部呼叫入口
    回傳 candidate_pool：每隻股票含基本資料，供 AI 分析選出最強 3~5 隻
    """
    pool = build_candidate_pool(foreign_top30, volume_top20)
    print(f"[fetch_candidates] 候選池 {len(pool)} 隻，開始抓資料...")

    results = []
    for i, item in enumerate(pool):
        print(f"  [{i+1}/{len(pool)}] {item['name']} ({item['code']})")
        data = fetch_candidate_basic(item["code"], item["name"])
        data["selection_reason"] = item["reason"]
        results.append(data)

    print(f"[fetch_candidates] 完成")
    return results


if __name__ == "__main__":
    # 測試用假資料
    test_foreign = [{"code": "2382", "name": "廣達", "net_shares": 5000000}]
    test_volume  = [{"code": "3711", "name": "日月光"}]
    print(json.dumps(fetch_all(test_foreign, test_volume), ensure_ascii=False, indent=2, default=str))
