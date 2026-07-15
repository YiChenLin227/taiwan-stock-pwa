"""
fetch_news.py
新聞及經濟行事曆：Yahoo RSS / DigiTimes RSS / FRED API
"""

import requests
import json
import os
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

NA = "⚠️ 無法取得資料"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_yahoo_tw_news(limit=5) -> list:
    """Yahoo 台股新聞 RSS"""
    url = "https://tw.news.yahoo.com/rss/finance"
    source = "https://tw.news.yahoo.com/finance/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        news = []
        for item in items[:limit]:
            title = item.findtext("title", "")
            link  = item.findtext("link", "")
            pub   = item.findtext("pubDate", "")
            if title:
                news.append({"title": title.strip(), "url": link.strip(), "date": pub[:16], "source": "Yahoo Finance"})
        return news
    except Exception as e:
        print(f"[fetch_yahoo_tw_news] 錯誤: {e}")
        return [{"title": NA, "url": source, "date": "", "source": "Yahoo Finance"}]


def fetch_digitimes_news(limit=3) -> list:
    """DigiTimes 科技產業新聞 RSS"""
    # New URL (old /tech/rss.xml returns 404)
    urls = [
        "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_10_0.xml",  # 科技/產業
        "https://www.digitimes.com.tw/tech/rss/xml/xmlrss_10_20.xml", # 半導體
    ]
    source = "https://www.digitimes.com.tw/"
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            print(f"[fetch_digitimes_news] {url} status={r.status_code} len={len(r.content)}")
            # Guard: DigiTimes returns HTML (login page) instead of XML when blocked
            if b"<html" in r.content[:100].lower() or b"<!DOCTYPE" in r.content[:100]:
                print(f"[fetch_digitimes_news] 回傳 HTML 非 XML，可能需登入")
                continue
            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            news = []
            for item in items[:limit]:
                title = item.findtext("title", "")
                link  = item.findtext("link", "")
                pub   = item.findtext("pubDate", "")
                if title:
                    news.append({"title": title.strip(), "url": link.strip(), "date": pub[:16], "source": "DigiTimes"})
            if news:
                return news
        except Exception as e:
            print(f"[fetch_digitimes_news] {url} 錯誤: {e}")
    return [{"title": "DigiTimes 科技產業新聞", "url": source, "date": "", "source": "DigiTimes"}]


def fetch_fred_events(api_key: str, days_ahead=14) -> list:
    """FRED API：未來 N 天的重大美國經濟事件"""
    source = "https://fred.stlouisfed.org/releases"
    if not api_key:
        return [{"title": NA, "date": "", "source": source}]

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        url = (
            f"https://api.stlouisfed.org/fred/releases/dates"
            f"?api_key={api_key}&file_type=json"
            f"&realtime_start={today}&realtime_end={future}"
            f"&sort_order=asc&limit=20"
        )
        r = requests.get(url, timeout=15)
        data = r.json()
        events = []
        for item in data.get("release_dates", []):
            name = item.get("release_name", "")
            date = item.get("date", "")
            # 只取重要的：CPI、Fed、NFP、GDP、PCE
            keywords = ["CPI", "Federal", "Nonfarm", "GDP", "PCE", "Employment", "FOMC", "Interest Rate"]
            if any(kw.lower() in name.lower() for kw in keywords):
                events.append({"title": name, "date": date, "source": source})
        return events[:10] if events else [{"title": "近期無重大事件", "date": "", "source": source}]
    except Exception as e:
        print(f"[fetch_fred_events] 錯誤: {e}")
        return [{"title": NA, "date": "", "source": source}]


def _load_cowork_override():
    """讀取 Cowork 排程寫入的新聞/總經資料（data/news_latest.json），12 小時內有效才採用。"""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "news_latest.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") != "ok":
            return None
        written_at = datetime.strptime(data["written_at"], "%Y-%m-%dT%H:%M:%SZ")
        age_hours = (datetime.utcnow() - written_at).total_seconds() / 3600
        if age_hours > 12:
            return None
        return data
    except Exception:
        return None


def fetch_all(fred_api_key: str = "") -> dict:
    print("[fetch_news] 開始抓取新聞及行事曆...")

    override = _load_cowork_override()
    if override:
        print(f"[fetch_news] 使用 Cowork 提供的資料（written_at={override.get('written_at')}）")
        yahoo_news     = override.get("yahoo_tw_news") or fetch_yahoo_tw_news(limit=5)
        digitimes_news = override.get("industry_news") or fetch_digitimes_news(limit=3)
        fred_events    = override.get("macro_events") or fetch_fred_events(fred_api_key or os.environ.get("FRED_API_KEY", ""))
    else:
        yahoo_news     = fetch_yahoo_tw_news(limit=5)
        digitimes_news = fetch_digitimes_news(limit=3)
        fred_events    = fetch_fred_events(fred_api_key or os.environ.get("FRED_API_KEY", ""))

    result = {
        "yahoo_tw_news": yahoo_news,
        "industry_news": digitimes_news,
        "macro_events": fred_events,
        "news_source": "https://tw.news.yahoo.com/finance/",
        "industry_source": "https://www.digitimes.com.tw/",
        "macro_source": "https://fred.stlouisfed.org/releases",
    }

    print(f"[fetch_news] 完成，Yahoo:{len(yahoo_news)} DigiTimes:{len(digitimes_news)} FRED:{len(fred_events)}")
    return result


if __name__ == "__main__":
    import os
    print(json.dumps(fetch_all(os.environ.get("FRED_API_KEY", "")), ensure_ascii=False, indent=2))
