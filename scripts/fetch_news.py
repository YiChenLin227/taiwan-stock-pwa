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
    url = "https://www.digitimes.com.tw/tech/rss.xml"
    source = "https://www.digitimes.com.tw/"
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
                news.append({"title": title.strip(), "url": link.strip(), "date": pub[:16], "source": "DigiTimes"})
        return news
    except Exception as e:
        print(f"[fetch_digitimes_news] 錯誤: {e}")
        return [{"title": NA, "url": source, "date": "", "source": "DigiTimes"}]


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


def fetch_all(fred_api_key: str = "") -> dict:
    print("[fetch_news] 開始抓取新聞及行事曆...")

    yahoo_news    = fetch_yahoo_tw_news(limit=5)
    digitimes_news = fetch_digitimes_news(limit=3)
    fred_events   = fetch_fred_events(fred_api_key or os.environ.get("FRED_API_KEY", ""))

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
