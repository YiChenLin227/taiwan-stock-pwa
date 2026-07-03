"""
fetch_market.py
取得台灣股市大盤相關資料：大盤指數、三大法人、融資融券、外資個股排名
來源：TWSE 官方 API + 台銀匯率
"""

import requests
from datetime import datetime, timedelta
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NA = "⚠️ 無法取得資料"


def get_latest_trading_date():
    """取得最近的交易日（排除週末）"""
    d = datetime.now()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    if datetime.now().hour < 9:
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def fetch_taiex(date):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date={date}&type=MS"
    source = "https://www.twse.com.tw/zh/trading/indices/MI_5MINS_HIST.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        for table in data.get("tables", []):
            for row in table.get("data", []):
                if "加權股價指數" in str(row):
                    return {
                        "taiex_close": row[1].replace(",", "") if len(row) > 1 else NA,
                        "taiex_change": row[2].replace(",", "") if len(row) > 2 else NA,
                        "taiex_change_pct": row[3] if len(row) > 3 else NA,
                        "taiex_source": source
                    }
        print("[fetch_taiex] TWSE 無資料，改用 yfinance ^TWII")
        return _fetch_taiex_yf(source)
    except Exception as e:
        print(f"[fetch_taiex] TWSE 錯誤: {e}，改用 yfinance ^TWII")
        return _fetch_taiex_yf(source)


def _fetch_taiex_yf(source_url):
    """yfinance ^TWII 作為 TWSE 備援"""
    NA = "⚠️ 無法取得資料"
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
        NA = "⚠️ 無法取得資料"
        return {"taiex_close": NA, "taiex_change": NA, "taiex_change_pct": NA, "taiex_source": source_url}


def fetch_volume(date):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date={date}&type=MS"
    source = "https://www.twse.com.tw/zh/trading/indices/MI_5MINS_HIST.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
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
        return {"volume_trillion": NA, "volume_source": source}
    except Exception as e:
        print(f"[fetch_volume] 錯誤: {e}")
        return {"volume_trillion": NA, "volume_source": source}


def fetch_institutional(date):
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date}&selectType=ALLBUT0999"
    source = "https://www.twse.com.tw/zh/trading/foreign/twt38u.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get("stat") != "OK":
            return {"foreign_net": NA, "trust_net": NA, "dealer_net": NA, "total_net": NA, "institutional_source": source}

        foreign_net = trust_net = dealer_net = 0
        rows = data.get("data", [])
        print(f"[fetch_institutional] T86 共 {len(rows)} 行")
        for row in rows:
            name = str(row[0]).strip() if row else ""
            # col 6 = 買賣超金額(千元)；col 9 = 買賣超股數(不含自行買賣)(千股)
            try:
                net = int(str(row[6]).replace(",", "").replace("+", "").strip()) if len(row) > 6 else 0
            except:
                net = 0
            # T86 row names：外資及陸資(不含外資自營商) / 投信 / 自營商(自行買賣)
            if "外資及陸資" in name and "不含外資自營商" in name:
                print(f"[fetch_institutional] 外資: {row[6] if len(row)>6 else 'N/A'}")
                foreign_net = net
            elif name == "投信":
                print(f"[fetch_institutional] 投信: {row[6] if len(row)>6 else 'N/A'}")
                trust_net = net
            elif "自營商" in name and "避險" not in name and "外資" not in name:
                print(f"[fetch_institutional] 自營商: {row[6] if len(row)>6 else 'N/A'}")
                dealer_net = net

        # 換算億元（千元 / 100,000 = 億元）
        def to_yi(amount_thousand_ntd):
            return round(amount_thousand_ntd / 100000, 2)

        return {
            "foreign_net_yi": str(to_yi(foreign_net)),
            "trust_net_yi": str(to_yi(trust_net)),
            "dealer_net_yi": str(to_yi(dealer_net)),
            "total_net_yi": str(to_yi(foreign_net + trust_net + dealer_net)),
            "institutional_source": source
        }
    except Exception as e:
        print(f"[fetch_institutional] 錯誤: {e}")
        return {"foreign_net_yi": NA, "trust_net_yi": NA, "dealer_net_yi": NA, "total_net_yi": NA, "institutional_source": source}


def fetch_foreign_top(date):
    url = f"https://www.twse.com.tw/rwd/zh/fund/TWT38U?response=json&date={date}"
    source = "https://goodinfo.tw/tw/StockBuySaleList.asp?RPT_CAT=BF&CHT_CAT2=DATE"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get("stat") != "OK":
            return {"foreign_top30": [], "foreign_top3_names": [NA, NA, NA], "foreign_top_source": source}

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
    except Exception as e:
        print(f"[fetch_foreign_top] 錯誤: {e}")
        return {"foreign_top30": [], "foreign_top3_names": [NA, NA, NA], "foreign_top_source": source}


def fetch_margin(date):
    url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date={date}&selectType=MS"
    source = "https://www.twse.com.tw/zh/trading/margin/MI_MARGN.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get("stat") != "OK":
            return {"margin_change": NA, "short_balance": NA, "margin_source": source}

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
    except Exception as e:
        print(f"[fetch_margin] 錯誤: {e}")
        return {"margin_change": NA, "short_balance": NA, "margin_source": source}


def fetch_fx():
    url = "https://rate.bot.com.tw/xrt/flcsv/0/day"
    source = "https://rate.bot.com.tw/xrt"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
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
    """yfinance USDTWD=X 作為台銀備援"""
    NA = "⚠️ 無法取得資料"
    try:
        import yfinance as yf
        hist = yf.Ticker("USDTWD=X").history(period="5d")
        if hist.empty:
            return {"twd_usd": NA, "fx_source": "https://finance.yahoo.com/quote/USDTWD%3DX/"}
        rate = round(float(hist["Close"].iloc[-1]), 3)
        return {"twd_usd": str(rate), "fx_source": "https://finance.yahoo.com/quote/USDTWD%3DX/"}
    except Exception as e:
        print(f"[_fetch_fx_yf] 錯誤: {e}")
        NA2 = "⚠️ 無法取得資料"
        return {"twd_usd": NA2, "fx_source": "https://finance.yahoo.com/quote/USDTWD%3DX/"}


def fetch_volume_top20(date):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX20?response=json&date={date}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        return [{"code": row[0], "name": row[1]} for row in data.get("data", [])[:20] if len(row) >= 2]
    except Exception as e:
        print(f"[fetch_volume_top20] 錯誤: {e}")
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
