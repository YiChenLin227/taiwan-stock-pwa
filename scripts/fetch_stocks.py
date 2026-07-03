"""
fetch_stocks.py
個股及全球指數資料：yfinance
固定3股：2330.TW / 2454.TW / 2327.TW
全球：TSM / ^IXIC / ^DJI / ^SOX / ^VIX / DX-Y.NYB / ^TNX / ^N225 / ^KS11 / ^HSI / GC=F / BZ=F
技術指標：RSI14、MA20、MA60、布林通道、MACD
"""

import json
import yfinance as yf
import pandas as pd
import numpy as np

NA = "⚠️ 無法取得資料"

FIXED_STOCKS = {
    "2330": {"ticker": "2330.TW", "name": "台積電", "source": "https://goodinfo.tw/tw/StockInfo.asp?STOCK_ID=2330"},
    "2454": {"ticker": "2454.TW", "name": "聯發科", "source": "https://goodinfo.tw/tw/StockInfo.asp?STOCK_ID=2454"},
    "2327": {"ticker": "2327.TW", "name": "國巨",   "source": "https://goodinfo.tw/tw/StockInfo.asp?STOCK_ID=2327"},
}

GLOBAL_TICKERS = {
    "tsm_adr":    {"ticker": "TSM",       "name": "TSM ADR",    "source": "https://finance.yahoo.com/quote/TSM/"},
    "nasdaq":     {"ticker": "^IXIC",     "name": "那斯達克",   "source": "https://finance.yahoo.com/quote/%5EIXIC/"},
    "dow":        {"ticker": "^DJI",      "name": "道瓊",       "source": "https://finance.yahoo.com/quote/%5EDJI/"},
    "sox":        {"ticker": "^SOX",      "name": "費城半導體", "source": "https://finance.yahoo.com/quote/%5ESOX/"},
    "vix":        {"ticker": "^VIX",      "name": "VIX",        "source": "https://finance.yahoo.com/quote/%5EVIX/"},
    "dxy":        {"ticker": "DX-Y.NYB",  "name": "美元指數",   "source": "https://finance.yahoo.com/quote/DX-Y.NYB/"},
    "tnx":        {"ticker": "^TNX",      "name": "10年美債殖利率","source": "https://finance.yahoo.com/quote/%5ETNX/"},
    "nikkei":     {"ticker": "^N225",     "name": "日經225",    "source": "https://finance.yahoo.com/quote/%5EN225/"},
    "kospi":      {"ticker": "^KS11",     "name": "韓股KOSPI",  "source": "https://finance.yahoo.com/quote/%5EKS11/"},
    "hsi":        {"ticker": "^HSI",      "name": "恆生指數",   "source": "https://finance.yahoo.com/quote/%5EHSI/"},
    "gold":       {"ticker": "GC=F",      "name": "黃金",       "source": "https://finance.yahoo.com/quote/GC=F/"},
    "oil":        {"ticker": "BZ=F",      "name": "布蘭特原油", "source": "https://finance.yahoo.com/quote/BZ=F/"},
}


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return round((100 - 100 / (1 + rs)).iloc[-1], 2)


def calc_ma(series, period):
    return round(series.rolling(period).mean().iloc[-1], 2)


def calc_bollinger(series, period=20):
    ma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = round((ma + 2 * std).iloc[-1], 2)
    lower = round((ma - 2 * std).iloc[-1], 2)
    return upper, lower


def calc_macd(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    macd_line = dif.ewm(span=9, adjust=False).mean()
    histogram = dif - macd_line
    return round(dif.iloc[-1], 2), round(macd_line.iloc[-1], 2), round(histogram.iloc[-1], 2)


def fetch_stock_data(code, ticker, name, source):
    """抓單一個股資料 + 技術指標"""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="90d")
        info = t.info
        fast = t.fast_info

        if hist.empty:
            raise ValueError("無歷史資料")

        close_series = hist["Close"]
        last_close = round(float(close_series.iloc[-1]), 2)
        prev_close = round(float(close_series.iloc[-2]), 2)
        change = round(last_close - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2)

        rsi = calc_rsi(close_series)
        ma20 = calc_ma(close_series, 20)
        ma60 = calc_ma(close_series, 60)
        boll_upper, boll_lower = calc_bollinger(close_series)
        macd_dif, macd_line, macd_hist = calc_macd(close_series)

        # 分析師目標價（TSM ADR 才抓）
        target_price = info.get("targetMeanPrice", NA)
        recommendation = info.get("recommendationKey", NA)

        # 新聞
        news_list = []
        try:
            raw_news = t.news or []
            for n in raw_news[:3]:
                content = n.get("content", {})
                title = content.get("title", n.get("title", ""))
                url = content.get("canonicalUrl", {}).get("url", "") or n.get("link", "")
                if title:
                    news_list.append({"title": title, "url": url})
        except:
            pass

        return {
            f"{code}_close": str(last_close),
            f"{code}_change": str(change),
            f"{code}_change_pct": str(change_pct) + "%",
            f"{code}_rsi": str(rsi),
            f"{code}_ma20": str(ma20),
            f"{code}_ma60": str(ma60),
            f"{code}_boll_upper": str(boll_upper),
            f"{code}_boll_lower": str(boll_lower),
            f"{code}_macd_dif": str(macd_dif),
            f"{code}_macd_line": str(macd_line),
            f"{code}_macd_hist": str(macd_hist),
            f"{code}_target_price": str(target_price),
            f"{code}_recommendation": recommendation,
            f"{code}_news": news_list,
            f"{code}_source": source,
        }
    except Exception as e:
        print(f"[fetch_stock_data] {code} 錯誤: {e}")
        keys = ["close","change","change_pct","rsi","ma20","ma60","boll_upper","boll_lower",
                "macd_dif","macd_line","macd_hist","target_price","recommendation"]
        result = {f"{code}_{k}": NA for k in keys}
        result[f"{code}_news"] = []
        result[f"{code}_source"] = source
        return result


def fetch_global_index(key, ticker, name, source):
    """全球指數（只抓收盤+漲跌，不計算技術指標）"""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist.empty:
            raise ValueError("無資料")
        close_series = hist["Close"]
        last = round(float(close_series.iloc[-1]), 2)
        prev = round(float(close_series.iloc[-2]), 2)
        change = round(last - prev, 2)
        change_pct = round((change / prev) * 100, 2)
        return {
            f"{key}_close": str(last),
            f"{key}_change_pct": f"{change_pct}%",
            f"{key}_source": source
        }
    except Exception as e:
        print(f"[fetch_global_index] {key} 錯誤: {e}")
        return {f"{key}_close": NA, f"{key}_change_pct": NA, f"{key}_source": source}


def fetch_taiex_technicals():
    """大盤加權指數技術指標（用 ^TWII）"""
    source = "https://tw.tradingview.com/chart/?symbol=TWSE%3ATAIEX"
    try:
        t = yf.Ticker("^TWII")
        hist = t.history(period="90d")
        if hist.empty:
            raise ValueError("無資料")
        close = hist["Close"]
        return {
            "taiex_ma20": str(calc_ma(close, 20)),
            "taiex_ma60": str(calc_ma(close, 60)),
            "taiex_boll_upper": str(calc_bollinger(close)[0]),
            "taiex_boll_lower": str(calc_bollinger(close)[1]),
            "taiex_rsi": str(calc_rsi(close)),
            "taiex_tech_source": source
        }
    except Exception as e:
        print(f"[fetch_taiex_technicals] 錯誤: {e}")
        return {k: NA for k in ["taiex_ma20","taiex_ma60","taiex_boll_upper","taiex_boll_lower","taiex_rsi","taiex_tech_source"]}


def fetch_all():
    print("[fetch_stocks] 開始抓取個股及全球指數...")
    result = {}

    # 固定3股
    for code, meta in FIXED_STOCKS.items():
        print(f"  → {meta['name']} ({code})")
        result.update(fetch_stock_data(code, meta["ticker"], meta["name"], meta["source"]))

    # 全球指數
    for key, meta in GLOBAL_TICKERS.items():
        print(f"  → {meta['name']} ({meta['ticker']})")
        result.update(fetch_global_index(key, meta["ticker"], meta["name"], meta["source"]))

    # 大盤技術指標
    print("  → 大盤技術指標 (^TWII)")
    result.update(fetch_taiex_technicals())

    print(f"[fetch_stocks] 完成，台積電: {result.get('2330_close')}  TSM ADR: {result.get('tsm_adr_close')}")
    return result


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2, default=str))
