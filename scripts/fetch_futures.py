"""
fetch_futures.py
期交所資料：夜盤台指期、Put/Call比、期貨三大法人、選擇權最大未平倉
來源：openapi.taifex.com.tw/v1
"""

import requests
import json

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
NA = "⚠️ 無法取得資料"
BASE = "https://openapi.taifex.com.tw/v1"


def fetch_night_futures():
    """夜盤台指期收盤（TradingSession=盤後 的 TX 近月）"""
    url = f"{BASE}/DailyMarketReportFut"
    source = "https://www.taifex.com.tw/cht/5/afterHoursFutures"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        # 找 TX 盤後近月
        tx_night = [d for d in data if d.get("Contract") == "TX" and d.get("TradingSession") == "盤後"]
        if tx_night:
            row = tx_night[0]
            return {
                "night_futures_last": row.get("Last", NA),
                "night_futures_change": row.get("Change", NA),
                "night_futures_open": row.get("Open", NA),
                "night_futures_high": row.get("High", NA),
                "night_futures_low": row.get("Low", NA),
                "night_futures_oi": row.get("OpenInterest", NA),
                "night_futures_source": source
            }
        # 備用：日盤 TX
        tx_day = [d for d in data if d.get("Contract") == "TX" and d.get("TradingSession") == "一般"]
        if tx_day:
            row = tx_day[0]
            return {
                "night_futures_last": row.get("Last", NA) + "（日盤）",
                "night_futures_change": row.get("Change", NA),
                "night_futures_open": row.get("Open", NA),
                "night_futures_high": row.get("High", NA),
                "night_futures_low": row.get("Low", NA),
                "night_futures_oi": row.get("OpenInterest", NA),
                "night_futures_source": source
            }
        return {k: NA for k in ["night_futures_last","night_futures_change","night_futures_open","night_futures_high","night_futures_low","night_futures_oi"]} | {"night_futures_source": source}
    except Exception as e:
        print(f"[fetch_night_futures] 錯誤: {e}")
        return {k: NA for k in ["night_futures_last","night_futures_change","night_futures_open","night_futures_high","night_futures_low","night_futures_oi"]} | {"night_futures_source": source}


def fetch_put_call_ratio():
    """Put/Call 比率"""
    url = f"{BASE}/PutCallRatio"
    source = "https://www.taifex.com.tw/cht/3/callAndputVolume"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if data and isinstance(data, list):
            latest = data[0]
            pc_ratio = latest.get("PutCallVolumeRatio%", NA)
            put_vol = latest.get("PutVolume", NA)
            call_vol = latest.get("CallVolume", NA)
            put_oi = latest.get("PutOI", NA) if "PutOI" in latest else NA
            call_oi = latest.get("CallOI", NA) if "CallOI" in latest else NA

            # 判斷偏多/偏空
            try:
                ratio = float(pc_ratio)
                sentiment = "偏多（Call居多）" if ratio < 80 else "偏空（Put居多）" if ratio > 120 else "中性"
            except:
                sentiment = NA

            return {
                "pc_ratio": pc_ratio,
                "put_volume": put_vol,
                "call_volume": call_vol,
                "put_oi": put_oi,
                "call_oi": call_oi,
                "pc_sentiment": sentiment,
                "pc_source": source
            }
        return {k: NA for k in ["pc_ratio","put_volume","call_volume","put_oi","call_oi","pc_sentiment"]} | {"pc_source": source}
    except Exception as e:
        print(f"[fetch_put_call_ratio] 錯誤: {e}")
        return {k: NA for k in ["pc_ratio","put_volume","call_volume","put_oi","call_oi","pc_sentiment"]} | {"pc_source": source}


def fetch_futures_institutional():
    """期貨三大法人（外資期貨淨多單口數）"""
    url = f"{BASE}/MarketDataOfMajorInstitutionalTradersGeneralBytheDate"
    source = "https://www.taifex.com.tw/cht/3/futContractsDate"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()

        foreign_net = trust_net = dealer_net = NA
        for row in data:
            item = row.get("Item", "")
            try:
                net = int(str(row.get("NetOI", "0")).replace(",", "").replace("+", ""))
            except:
                net = 0
            if "外資" in item:
                foreign_net = str(net)
            elif "投信" in item:
                trust_net = str(net)
            elif "自營商" in item:
                dealer_net = str(net)

        return {
            "futures_foreign_net_oi": foreign_net,
            "futures_trust_net_oi": trust_net,
            "futures_dealer_net_oi": dealer_net,
            "futures_inst_source": source
        }
    except Exception as e:
        print(f"[fetch_futures_institutional] 錯誤: {e}")
        return {
            "futures_foreign_net_oi": NA,
            "futures_trust_net_oi": NA,
            "futures_dealer_net_oi": NA,
            "futures_inst_source": source
        }


def fetch_max_oi_strike():
    """選擇權最大未平倉履約價（Call/Put）→ 壓力/支撐參考"""
    url = f"{BASE}/DailyMarketReportOpt"
    source = "https://www.taifex.com.tw/cht/3/callsAndPutsDate"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()

        # 篩選 TXO 本月近月合約
        txo = [d for d in data if d.get("Contract") == "TXO"]
        calls = [d for d in txo if d.get("CallPut") == "買權" or "C" in str(d.get("ContractMonth(Week)", ""))]
        puts  = [d for d in txo if d.get("CallPut") == "賣權" or "P" in str(d.get("ContractMonth(Week)", ""))]

        def max_oi_strike(rows):
            best = None
            best_oi = -1
            for row in rows:
                try:
                    oi = int(str(row.get("OpenInterest", "0")).replace(",", ""))
                    if oi > best_oi:
                        best_oi = oi
                        best = row.get("StrikePrice", NA)
                except:
                    pass
            return best or NA

        return {
            "max_call_oi_strike": max_oi_strike(calls),
            "max_put_oi_strike": max_oi_strike(puts),
            "option_oi_source": source
        }
    except Exception as e:
        print(f"[fetch_max_oi_strike] 錯誤: {e}")
        return {"max_call_oi_strike": NA, "max_put_oi_strike": NA, "option_oi_source": source}


def fetch_all():
    print("[fetch_futures] 開始抓取期交所資料...")
    result = {}
    result.update(fetch_night_futures())
    result.update(fetch_put_call_ratio())
    result.update(fetch_futures_institutional())
    result.update(fetch_max_oi_strike())
    print(f"[fetch_futures] 完成，夜盤台指期: {result.get('night_futures_last')}  P/C比: {result.get('pc_ratio')}")
    return result


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
