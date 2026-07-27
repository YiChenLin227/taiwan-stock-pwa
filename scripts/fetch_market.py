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
    "Accept-Encoding": "gzip, deflate",
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
        prev = round(float(hist["Close"].iloc[-2]), 0)
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
    """
    取得大盤成交金額（兆元）。

    修正紀錄（2026-07-27）：TWSE rwd/afterTrading/MI_INDEX 端點在 GitHub Actions
    環境下經常被回傳 HTTP 307（非機器人流量判定所致，非日期或資料本身問題——
    直接以瀏覽器連線同一網址可正常取得資料）。原本這裡沒有任何備援，失敗就直接
    回傳「無法取得資料」。現在依序嘗試：
      1) TWSE rwd 端點（原本邏輯）
      2) TWSE OpenAPI 的 FMTQIK（每日市場成交資訊，同樣是 TWSE 官方資料，單位一致）
      3) yfinance ^TWII 的 Volume 當作最後手段，並加上合理性檢查，避免因單位不同
         （股數 vs 成交金額）而顯示錯誤但看起來正常的數字
    """
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

    print(f"[fetch_volume] TWSE rwd 無資料({err})，改用 OpenAPI FMTQIK")

    # 備援 1：TWSE OpenAPI FMTQIK
    fmtqik_source = "https://www.twse.com.tw/zh/trading/historical/fmtqik.html"
    try:
        open_url = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
        r = requests.get(open_url, headers=FULL_HEADERS, timeout=15)
        print(f"[fetch_volume] OpenAPI FMTQIK status={r.status_code} body_len={len(r.content)}")
        if r.content:
            open_data = r.json()
            # Date 欄位可能是西元年 (20260724) 或民國年 (1150724)，兩種都比對
            try:
                roc_date = f"{int(date[:4]) - 1911}{date[4:]}"
            except Exception:
                roc_date = ""
            for row in open_data:
                row_date = str(row.get("Date", "")).strip()
                if row_date in (date, roc_date):
                    trade_value = str(row.get("TradeValue", "")).replace(",", "")
                    try:
                        trillion = round(float(trade_value) / 1e12, 2)
                        print(f"[fetch_volume] OpenAPI FMTQIK 命中 date={row_date} TradeValue={trade_value}")
                        return {"volume_trillion": str(trillion), "volume_source": fmtqik_source}
                    except Exception as e:
                        print(f"[fetch_volume] OpenAPI FMTQIK TradeValue 解析失敗: {e}")
    except Exception as e:
        print(f"[fetch_volume] OpenAPI FMTQIK 錯誤: {e}")

    print("[fetch_volume] OpenAPI 也無資料，改用 yfinance ^TWII（僅供參考，會做合理性檢查）")

    # 備援 2：yfinance（最後手段，且需通過合理性檢查才採用）
    try:
        import yfinance as yf
        hist = yf.Ticker("^TWII").history(period="10d")
        if not hist.empty and "Volume" in hist.columns:
            vol_series = hist["Volume"].dropna()
            if len(vol_series) >= 1:
                last_vol = float(vol_series.iloc[-1])
                trillion_guess = round(last_vol / 1e12, 2)
                # 台股單日成交金額合理範圍大約 0.05兆~5兆，超出此範圍代表單位
                # 很可能不是成交金額（例如變成股數），寧可留白也不要顯示錯誤數字
                if 0.05 <= trillion_guess <= 5:
                    return {
                        "volume_trillion": str(trillion_guess),
                        "volume_source": "https://finance.yahoo.com/quote/%5ETWII/ （yfinance 估算，單位可能與官方成交金額有誤差，僅供參考）"
                    }
                else:
                    print(f"[fetch_volume] yfinance Volume 換算後不合理（{trillion_guess}兆），捨棄")
    except Exception as e:
        print(f"[fetch_volume] yfinance 備援錯誤: {e}")

    print(f"[fetch_volume] 所有來源皆失敗: {err}")
    return {"volume_trillion": NA, "volume_source": source}

def fetch_institutional(date):
    """
    使用 BFI82U（三大法人買賣超日報）取得法人總計資料。
    BFI82U 直接給出各機構別的買賣超「金額」摘要，col3 = 買賣超金額(千元)。
    （T86 是各股票明細表，ALLBUT0999 不含總計列，不適合此用途。）
    """
    source = "https://www.twse.com.tw/zh/trading/foreign/twt38u.html"
    url = f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&type=day&dayDate={date}"

    data, err = _twse_get(url, retries=3, delay=5)
    if data:
        stat = data.get("stat", "")
        rows = data.get("data", [])
        print(f"[fetch_institutional] BFI82U stat={stat} 共 {len(rows)} 行")

        if stat == "OK" and rows:
            foreign_net = trust_net = dealer_net = 0
            matched = []
            for row in rows:
                name = str(row[0]).strip() if row else ""
                # col3 = 買賣超金額(千元)
                try:
                    net = int(str(row[3]).replace(",", "").replace("+", "").strip()) if len(row) > 3 else 0
                except:
                    net = 0
                print(f"[fetch_institutional] name={repr(name)}, col3={row[3] if len(row)>3 else 'N/A'}, net={net}")
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

            def to_yi(v): return round(v / 100000000, 2)
            return {
                "foreign_net_yi": str(to_yi(foreign_net)),
                "trust_net_yi": str(to_yi(trust_net)),
                "dealer_net_yi": str(to_yi(dealer_net)),
                "total_net_yi": str(to_yi(foreign_net + trust_net + dealer_net)),
                "institutional_source": source
            }
        else:
            print(f"[fetch_institutional] BFI82U stat={stat} 或無資料")

    # 備援：OpenAPI BFI82U
    open_url = f"https://openapi.twse.com.tw/v1/funds/BFI82U?date={date}"
    print(f"[fetch_institutional] 改用 OpenAPI BFI82U: {open_url}")
    try:
        r2 = requests.get(open_url, headers=FULL_HEADERS, timeout=20)
        print(f"[fetch_institutional] OpenAPI status={r2.status_code} body_len={len(r2.content)}")
        if r2.content:
            open_data = r2.json()
            print(f"[fetch_institutional] OpenAPI 回傳前500字: {str(open_data)[:500]}")
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
    """
    MI_MARGN fields: [項目, 買進, 賣出, 現金(券)償還, 前日餘額, 今日餘額]
    Rows: 融資(交易單位), 融券(交易單位), 融資金額(仟元)
    - margin_change_yi: 融資金額 今日餘額 - 前日餘額 (仟元 → 億)
    - short_balance: 融券(交易單位) 今日餘額 (張)
    Falls back to previous trading day if today's data not available yet.
    """
    source = "https://www.twse.com.tw/zh/trading/margin/MI_MARGN.html"

    def _try_date(d):
        url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date={d}&selectType=MS"
        data, err = _twse_get(url)
        if not data or data.get("stat") != "OK":
            return None, err
        margin_yi = NA
        short_bal = NA
        for table in data.get("tables", []):
            for row in table.get("data", []):
                item = str(row[0]).strip() if row else ""
                # col4=前日餘額, col5=今日餘額
                if "融資金額" in item and len(row) >= 6:
                    try:
                        today_val = int(row[5].replace(",", ""))
                        prev_val = int(row[4].replace(",", ""))
                        change_qian = today_val - prev_val  # 仟元
                        margin_yi = round(change_qian / 100000, 2)  # 億 (float for sign_css in update.py)
                        print(f"[fetch_margin] 融資金額 today={today_val} prev={prev_val} change={change_qian}仟元 → {margin_yi}億")
                    except Exception as e:
                        print(f"[fetch_margin] 融資金額 parse error: {e} row={row}")
                elif "融券" in item and "交易單位" in item and len(row) >= 6:
                    try:
                        short_bal = row[5].replace(",", "")  # 張，今日餘額
                        print(f"[fetch_margin] 融券餘額={short_bal}張")
                    except Exception as e:
                        print(f"[fetch_margin] 融券 parse error: {e}")
        return (margin_yi, short_bal), None

    result, err = _try_date(date)
    if result:
        return {"margin_change": result[0], "short_balance": result[1], "margin_source": source}

    # Fallback: try previous trading day (data published ~8-9pm TW time)
    from datetime import datetime, timedelta
    d = datetime.strptime(date, "%Y%m%d") - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    prev_date = d.strftime("%Y%m%d")
    print(f"[fetch_margin] {date} 無資料，試前一交易日 {prev_date}")
    result2, err2 = _try_date(prev_date)
    if result2:
        return {"margin_change": result2[0], "short_balance": result2[1], "margin_source": source}

    print(f"[fetch_margin] 最終失敗: {err}")
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
