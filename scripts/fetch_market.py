"""
fetch_market.py
取得台灣股市大盤相關資料：大盤指數、三大法人、融資融券、外資個股排名
來源：TWSE 官方 API + 台銀匯率
"""

import requests
import time
from datetime import datetime, timedelta
import json

NA = "⚠️ 無法取得資料"

FULL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.twse.com.tw/zh/",
    "Origin": "https://www.twse.com.tw",
    "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Connection": "keep-alive",
}

_twse_session = None


def _get_twse_session():
    """建立並快取 TWSE session（預取 cookies）"""
    global _twse_session
    if _twse_session is not None:
        return _twse_session
    s = requests.Session()
    s.headers.update(FULL_HEADERS)
    try:
        s.get("https://www.twse.com.tw/zh/", timeout=10)
        print("[twse_session] homepage cookies OK")
    except Exception as e:
        print(f"[twse_session] homepage pre-fetch 失敗: {e}")
    _twse_session = s
    return s


def _twse_get(url, retries=3, delay=4):
    """帶重試的 TWSE GET，回傳 (data_dict, error_str)"""
    session = _get_twse_session()
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=20)
            print(f"[twse_get] attempt={attempt} status={r.status_code} body_len={len(r.content)} url={url}")
            if not r.content:
                last_err = f"empty response (HTTP {r.status_code})"
                time.sleep(delay)
                continue
            return r.json(), None
        except Exception as e:
            last_err = str(e)
            print(f"[twse_get] attempt={attempt} error: {e}")
            time.sleep(delay)
    return None, last_err


def get_latest_trading_date():
    """取得最近的交易日（排除週末）— 使用 UTC+8 台灣時間"""
    # GitHub Actions 跑在 UTC，需轉換成台灣時間
    tw_now = datetime.utcnow() + timedelta(hours=8)
    d = tw_now
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    # 若台灣時間尚未到 16:30（T86 發布時間），用前一交易日
    if tw_now.hour < 16 or (tw_now.hour == 16 and tw_now.minute < 30):
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def fetch_taiex(date):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date={date}&type=MS"
    source = "https://www.twse.com.tw/zh/trading/indices/MI_5MINS_HIST.html"
    data, err = _twse_get(url)
    if data:
        for table in data.get("tables", []):
            for row in table.get("data", []):
                if "加權股價指數" in str(row):
                    return {
                        "taiex_close": row[1].replace(",", "") if len(row) > 1 else NA,
                        "taiex_change": row[2].replace(",", "") if len(row) > 2 else NA,
                        "taiex_change_pct": row[3] if len(row) > 3 else NA,
                        "taiex_source": source
                    }
    print(f"[fetch_taiex] TWSE 無資料({err})，改用 yfinance ^TWII")
    return _fetch_taiex_yf(source)


def _fetch_taiex_yf(source_url):
    try:
        import yfinance as yf
        hist = yf.Ticker("^TWII").history(period="10d")
        if len(hist) < 2:
            return {"taiex_close": NA, "taiex_change": NA, "taiex_change_pct": NA, "taiex_source": source_url}
        close = round(float(hist["Close"].iloc[-1]), 0)
        prev  = round(float(hist["Close"].iloc[-2]), 0)
        change = round(close - prev, 0)
        pct = round((change / prev) * 100, 2) if prev else 0
        sign = "+" if change >= 0 else ""
        return {
            "taiex_close": str(int(close)),
            "taiex_change": f"{sign}{int(change)}",
            "taiex_change_pct": f"{sign}{pct}%",
            "taiex_source": "https://finance.yahoo.com/quote/%5ETWII/"
        }
    except Exception as e:
        print(f"[_fetch_taiex_yf] 錯誤: {e}")
        return {"taiex_close": NA, "taiex_change": NA, "taiex_change_pct": NA, "taiex_source": source_url}


def fetch_volume(date):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date={date}&type=MS"
    source = "https://www.twse.com.tw/zh/trading/indices/MI_5MINS_HIST.html"
    data, err = _twse_get(url)
    if data:
        for table in data.get("tables", []):
            if "成交金額" in str(table.get("fields", [])):
                rows = table.get("data", [])
                if rows:
                    amount_str = rows[0][1].replace(",", "") if len(rows[0]) > 1 else "0"
                    try:
                        trillion = round(float(amount_str) / 1e12, 2)
                        return {"volume_trillion": str(trillion), "volume_source": source}
                    except:
                        pass
    print(f"[fetch_volume] 無資料: {err}")
    return {"volume_trillion": NA, "volume_source": source}


def _parse_t86_rows(rows, source):
    """解析 T86 rows，回傳法人資料 dict"""
    foreign_net = trust_net = dealer_net = 0
    matched = []
    print(f"[fetch_institutional] T86 共 {len(rows)} 行")
    for row in rows:
        name = str(row[0]).strip() if row else ""
        print(f"[fetch_institutional]   row[0]={repr(name)}, col6={row[6] if len(row)>6 else 'N/A'}")
        try:
            net = int(str(row[6]).replace(",", "").replace("+", "").strip()) if len(row) > 6 else 0
        except:
            net = 0
        if "外資及陸資" in name and "不含外資自營商" in name:
            foreign_net = net
            matched.append(f"外資={net}")
        elif name == "投信":
            trust_net = net
            matched.append(f"投信={net}")
        elif "自營商" in name and "避險" not in name and "外資" not in name:
            dealer_net = net
            matched.append(f"自營商={net}")
    print(f"[fetch_institutional] 匹配: {matched}")

    def to_yi(v): return round(v / 100000, 2)
    return {
        "foreign_net_yi": str(to_yi(foreign_net)),
        "trust_net_yi": str(to_yi(trust_net)),
        "dealer_net_yi": str(to_yi(dealer_net)),
        "total_net_yi": str(to_yi(foreign_net + trust_net + dealer_net)),
        "institutional_source": source
    }


def fetch_institutional(date):
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date}&selectType=ALLBUT0999"
    source = "https://www.twse.com.tw/zh/trading/foreign/twt38u.html"

    data, err = _twse_get(url, retries=3, delay=5)
    if data:
        if data.get("stat") != "OK":
            print(f"[fetch_institutional] stat={data.get('stat')}")
        else:
            return _parse_t86_rows(data.get("data", []), source)

    # OpenAPI 備援
    open_url = f"https://openapi.twse.com.tw/v1/funds/T86?date={date}"
    print(f"[fetch_institutional] 改用 OpenAPI: {open_url}")
    try:
        r2 = requests.get(open_url, headers=FULL_HEADERS, timeout=20)
        print(f"[fetch_institutional] OpenAPI status={r2.status_code} body_len={len(r2.content)}")
        if r2.content:
            open_data = r2.json()
            # OpenAPI 回傳格式：{"stat":"OK","data":[...]} 或 [{"Code":..., ...}]
            if isinstance(open_data, dict) and open_data.get("stat") == "OK":
                return _parse_t86_rows(open_data.get("data", []), source)
            # OpenAPI 也可能是不同結構，直接印出前3筆便於除錯
            print(f"[fetch_institutional] OpenAPI 回傳: {str(open_data)[:300]}")
    except Exception as e:
        print(f"[fetch_institutional] OpenAPI 錯誤: {e}")

    print(f"[fetch_institutional] 最終失敗: {err}")
    return {"foreign_net_yi": NA, "trust_net_yi": NA, "dealer_net_yi": NA, "total_net_yi": NA, "institutional_source": source}


def fetch_foreign_top(date):
    url = f"https://www.twse.com.tw/rwd/zh/fund/TWT38U?response=json&date={date}"
    source = "https://goodinfo.tw/tw/StockBuySaleList.asp?RPT_CAT=BF&CHT_CAT2=DATE"
    data, err = _twse_get(url)
    if data and data.get("stat") == "OK":
        top = []
        for row in data.get("data", []):
            if len(row) < 5:
                continue
            try:
                net = int(row[4].replace(",", "").replace("+", ""))
                if net > 0:
                    top.append({"code": row[1], "name": row[2], "net_shares": net})
            except:
                continue
        top = sorted(top, key=lambda x: x["net_shares"], reverse=True)[:30]
        return {
            "foreign_top30": top,
            "foreign_top3_names": [f"{t['name']} {t['code']}" for t in top[:3]],
            "foreign_top_source": source
        }
    print(f"[fetch_foreign_top] 無資料: {err}")
    return {"foreign_top30": [], "foreign_top3_names": [NA, NA, NA], "foreign_top_source": source}


def fetch_margin(date):
    url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date={date}&selectType=MS"
    source = "https://www.twse.com.tw/zh/trading/margin/MI_MARGN.html"
    data, err = _twse_get(url)
    if data and data.get("stat") == "OK":
        margin_change = short_balance = NA
        for table in data.get("tables", []):
            for row in table.get("data", []):
                item = str(row[0]) if row else ""
                if "融資" in item and "餘額" in item and len(row) > 2:
                    try:
                        margin_change = row[2].replace(",", "")
                    except:
                        pass
                if "融券" in item and "餘額" in item and len(row) > 2:
                    try:
                        short_balance = row[2].replace(",", "")
                    except:
                        pass
        return {"margin_change": margin_change, "short_balance": short_balance, "margin_source": source}
    print(f"[fetch_margin] 無資料: {err}")
    return {"margin_change": NA, "short_balance": NA, "margin_source": source}


def fetch_fx():
    url = "https://rate.bot.com.tw/xrt/flcsv/0/day"
    source = "https://rate.bot.com.tw/xrt"
    try:
        r = requests.get(url, headers=FULL_HEADERS, timeout=15)
        r.encoding = "utf-8"
        for line in r.text.strip().split("\n"):
            if "USD" in line:
                parts = line.split(",")
                if len(parts) > 2:
                    return {"twd_usd": parts[2].strip(), "fx_source": source}
        print("[fetch_fx] 台銀 CSV 無資料，改用 yfinance")
        return _fetch_fx_yf()
    except Exception as e:
        print(f"[fetch_fx] 台銀錯誤: {e}，改用 yfinance")
        return _fetch_fx_yf()


def _fetch_fx_yf():
    try:
        import yfinance as yf
        hist = yf.Ticker("USDTWD=X").history(period="5d")
        if hist.empty:
            return {"twd_usd": NA, "fx_source": "https://finance.yahoo.com/quote/USDTWD%3DX/"}
        rate = round(float(hist["Close"].iloc[-1]), 3)
        return {"twd_usd": str(rate), "fx_source": "https://finance.yahoo.com/quote/USDTWD%3DX/"}
    except Exception as e:
        print(f"[_fetch_fx_yf] 錯誤: {e}")
        return {"twd_usd": NA, "fx_source": "https://finance.yahoo.com/quote/USDTWD%3DX/"}


def fetch_volume_top20(date):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX20?response=json&date={date}"
    data, err = _twse_get(url)
    if data:
        rows = data.get("data", [])
        result = [{"code": row[0], "name": row[1]} for row in rows[:20] if len(row) >= 2]
        if result:
            return result
    print(f"[fetch_volume_top20] 無資料: {err}")
    return []


def fetch_all():
    date = get_latest_trading_date()
    print(f"[fetch_market] 交易日: {date}")
    result = {"trade_date": date, "trading_date": f"{date[4:6]}/{date[6:8]}"}
    result.update(fetch_taiex(date))
    result.update(fetch_volume(date))
    result.update(fetch_institutional(date))
    result.update(fetch_foreign_top(date))
    result.update(fetch_margin(date))
    result.update(fetch_fx())
    result["volume_top20"] = fetch_volume_top20(date)
    print(f"[fetch_market] 完成，大盤: {result.get('taiex_close')} 外資: {result.get('foreign_net_yi')}億")
    return result


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
