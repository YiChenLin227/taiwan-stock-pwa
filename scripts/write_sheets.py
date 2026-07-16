"""
write_sheets.py
將每日分析結果寫入 Google Sheets
支援：初始化 header、append 新列、手動更新後重新計算趨勢欄位
"""

import gspread
import json
import os
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials

NA = "⚠️ 無法取得資料"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── 完整欄位定義（依序對應 A、B、C...欄）──
HEADERS = [
    # 基本
    "日期", "市場方向", "今日最大風險",
    # 大盤
    "加權指數收盤", "加權指數漲跌", "加權指數漲跌%", "成交量兆",
    "大盤MA20", "大盤MA60", "大盤RSI", "大盤布林上軌", "大盤布林下軌",
    "關鍵支撐", "關鍵壓力", "預估開盤低", "預估開盤高",
    # 美股
    "那斯達克收盤", "那斯達克漲跌%",
    "道瓊收盤", "道瓊漲跌%",
    "SOX收盤", "SOX漲跌%",
    "TSM_ADR收盤", "TSM_ADR漲跌%",
    # 全球
    "VIX", "DXY收盤", "DXY漲跌%",
    "10年美債殖利率",
    "日經225收盤", "日經225漲跌%",
    "韓股KOSPI收盤", "韓股KOSPI漲跌%",
    "恆生指數收盤", "恆生指數漲跌%",
    "黃金收盤", "黃金漲跌%",
    "布蘭特原油收盤", "布蘭特原油漲跌%",
    # 台幣
    "台幣匯率",
    # 三大法人（現貨）
    "外資買賣超億", "投信買賣超億", "自營商買賣超億", "三大合計億",
    "外資現貨連續N天",
    "本週外資累計億", "本月外資累計億",
    "外資個股排名1", "外資個股排名2", "外資個股排名3",
    # 期貨
    "夜盤台指期收盤", "夜盤台指期漲跌",
    "台指期未平倉口", "外資期貨淨多單口",
    "外資期貨連續N天",
    # 選擇權
    "PC比", "PC情緒",
    "最大Call未平倉履約價", "最大Put未平倉履約價",
    # 融資融券
    "融資餘額變化", "融券餘額",
    # 固定股：台積電
    "2330收盤", "2330漲跌%", "2330_RSI", "2330_MA20", "2330_MA60",
    "2330_MACD_DIF", "2330方向", "2330買入區間", "2330停損", "2330目標",
    "2330新聞1標題", "2330新聞1URL", "2330新聞2標題", "2330新聞2URL", "2330新聞3標題", "2330新聞3URL",
    # 固定股：聯發科
    "2454收盤", "2454漲跌%", "2454_RSI", "2454_MA20",
    "2454方向", "2454買入區間", "2454停損", "2454目標",
    "2454新聞1標題", "2454新聞1URL", "2454新聞2標題", "2454新聞2URL",
    # 固定股：國巨
    "2327收盤", "2327漲跌%", "2327_RSI", "2327_MA20",
    "2327方向", "2327買入區間", "2327停損", "2327目標",
    "2327新聞1標題", "2327新聞1URL", "2327新聞2標題", "2327新聞2URL",
    # 動態精選股
    "精選股JSON", "精選股選股理由",
    # 新聞
    "台股新聞1標題", "台股新聞1URL",
    "台股新聞2標題", "台股新聞2URL",
    "台股新聞3標題", "台股新聞3URL",
    "產業新聞1標題", "產業新聞1URL",
    "產業新聞2標題", "產業新聞2URL",
    "產業新聞3標題", "產業新聞3URL",
    "總經事件1", "總經事件1日期",
    "總經事件2", "總經事件2日期",
    "總經事件3", "總經事件3日期",
    # AI 全文
    "大盤AI解讀", "法人AI解讀", "融資AI解讀", "匯率AI解讀",
    "期貨AI解讀", "全球AI解讀",
    "操盤策略", "風控提醒", "產業趨勢AI", "總經AI",
    "今日最強族群", "今日最大風險標的",
    # 系統
    "手動更新時間", "重新分析次數",
]


def get_client(credentials_json: str):
    """建立 gspread 客戶端"""
    import tempfile
    raw = credentials_json.strip()
    # Handle BOM
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    # Handle outer quote wrapping (common GitHub Secret encoding issue)
    if raw.startswith('"') and raw.endswith('"'):
        try:
            raw = json.loads(raw)   # unwrap outer string layer
        except Exception:
            raw = raw[1:-1].replace('\\"', '"')
    creds_dict = json.loads(raw)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(creds_dict, f)
        tmp_path = f.name
    creds = Credentials.from_service_account_file(tmp_path, scopes=SCOPES)
    return gspread.authorize(creds)


def init_sheet(sheet):
    """若第一行不是 header，自動建立"""
    try:
        first_row = sheet.row_values(1)
        if first_row and first_row[0] == "日期":
            print("[write_sheets] Header 已存在")
            return
    except:
        pass
    print("[write_sheets] 初始化 header...")
    sheet.insert_row(HEADERS, 1)


def get_history_rows(sheet, n=7) -> list:
    """讀取最近 N 筆資料供 AI 趨勢分析"""
    try:
        all_rows = sheet.get_all_records()
        return all_rows[-n:] if len(all_rows) >= n else all_rows
    except:
        return []


def calc_streak(history_rows: list, field: str) -> int:
    """計算連續買超/賣超天數（正=買超，負=賣超）"""
    if not history_rows:
        return 0
    streak = 0
    direction = None
    for row in reversed(history_rows):
        val_str = str(row.get(field, "0")).replace(",", "").replace(NA, "0")
        try:
            val = float(val_str)
        except:
            break
        if direction is None:
            direction = 1 if val >= 0 else -1
        if (val >= 0 and direction == 1) or (val < 0 and direction == -1):
            streak += direction
        else:
            break
    return streak


def calc_weekly_sum(history_rows: list, field: str) -> float:
    """計算本週累計（最近5個交易日）"""
    total = 0
    for row in history_rows[-5:]:
        val_str = str(row.get(field, "0")).replace(",", "").replace(NA, "0")
        try:
            total += float(val_str)
        except:
            pass
    return round(total, 2)


def build_row(market: dict, futures: dict, stocks: dict,
              ai: dict, news: dict, history_rows: list) -> list:
    """組合一列資料（順序對應 HEADERS）"""

    def g(d, k): return str(d.get(k, NA))

    TW = timezone(timedelta(hours=8))
    today = datetime.now(TW).strftime("%Y/%m/%d")

    # 趨勢計算
    foreign_streak = calc_streak(history_rows, "外資買賣超億")
    futures_streak = calc_streak(history_rows, "外資期貨淨多單口")
    weekly_foreign = calc_weekly_sum(history_rows, "外資買賣超億")
    monthly_foreign = calc_weekly_sum(history_rows[-20:] if len(history_rows) >= 20 else history_rows, "外資買賣超億")

    # 外資個股排名
    top3 = market.get("foreign_top3_names", [NA, NA, NA])
    while len(top3) < 3:
        top3.append(NA)

    # 固定股新聞（最多3則）
    def stock_news(code, idx):
        news_list = stocks.get(f"{code}_news", [])
        if idx < len(news_list):
            return news_list[idx].get("title", NA), news_list[idx].get("url", NA)
        return NA, NA

    s2330_n1t, s2330_n1u = stock_news("2330", 0)
    s2330_n2t, s2330_n2u = stock_news("2330", 1)
    s2330_n3t, s2330_n3u = stock_news("2330", 2)
    s2454_n1t, s2454_n1u = stock_news("2454", 0)
    s2454_n2t, s2454_n2u = stock_news("2454", 1)
    s2327_n1t, s2327_n1u = stock_news("2327", 0)
    s2327_n2t, s2327_n2u = stock_news("2327", 1)

    # 台股/產業新聞
    def news_item(lst, idx, key):
        if idx < len(lst): return lst[idx].get(key, NA)
        return NA

    yn = news.get("yahoo_tw_news", [])
    dn = news.get("industry_news", [])
    fe = news.get("macro_events", [])

    # 固定股 AI
    fs = ai.get("fixed_stocks", {})
    def fsg(code, k): return str(fs.get(code, {}).get(k, NA))

    # 精選股
    top_stocks = ai.get("top_stocks", [])
    top_stocks_json = json.dumps(top_stocks, ensure_ascii=False)

    row = [
        # 基本
        today,
        g(ai, "market_direction"),
        g(ai, "biggest_risk"),
        # 大盤
        g(market, "taiex_close"),
        g(market, "taiex_change"),
        g(market, "taiex_change_pct"),
        g(market, "volume_trillion"),
        g(stocks, "taiex_ma20"),
        g(stocks, "taiex_ma60"),
        g(stocks, "taiex_rsi"),
        g(stocks, "taiex_boll_upper"),
        g(stocks, "taiex_boll_lower"),
        g(ai, "key_support"),
        g(ai, "key_resistance"),
        g(ai, "open_range_low"),
        g(ai, "open_range_high"),
        # 美股
        g(stocks, "nasdaq_close"), g(stocks, "nasdaq_change_pct"),
        g(stocks, "dow_close"), g(stocks, "dow_change_pct"),
        g(stocks, "sox_close"), g(stocks, "sox_change_pct"),
        g(stocks, "tsm_adr_close"), g(stocks, "tsm_adr_change_pct"),
        # 全球
        g(stocks, "vix_close"),
        g(stocks, "dxy_close"), g(stocks, "dxy_change_pct"),
        g(stocks, "tnx_close"),
        g(stocks, "nikkei_close"), g(stocks, "nikkei_change_pct"),
        g(stocks, "kospi_close"), g(stocks, "kospi_change_pct"),
        g(stocks, "hsi_close"), g(stocks, "hsi_change_pct"),
        g(stocks, "gold_close"), g(stocks, "gold_change_pct"),
        g(stocks, "oil_close"), g(stocks, "oil_change_pct"),
        # 台幣
        g(market, "twd_usd"),
        # 三大法人
        g(market, "foreign_net_yi"),
        g(market, "trust_net_yi"),
        g(market, "dealer_net_yi"),
        g(market, "total_net_yi"),
        str(foreign_streak),
        str(weekly_foreign),
        str(monthly_foreign),
        top3[0], top3[1], top3[2],
        # 期貨
        g(futures, "night_futures_last"), g(futures, "night_futures_change"),
        g(futures, "night_futures_oi"), g(futures, "futures_foreign_net_oi"),
        str(futures_streak),
        # 選擇權
        g(futures, "pc_ratio"), g(futures, "pc_sentiment"),
        g(futures, "max_call_oi_strike"), g(futures, "max_put_oi_strike"),
        # 融資融券
        g(market, "margin_change"), g(market, "short_balance"),
        # 台積電
        g(stocks, "2330_close"), g(stocks, "2330_change_pct"), g(stocks, "2330_rsi"),
        g(stocks, "2330_ma20"), g(stocks, "2330_ma60"), g(stocks, "2330_macd_dif"),
        fsg("2330","direction"), fsg("2330","buy_range"), fsg("2330","stop_loss"), fsg("2330","target"),
        s2330_n1t, s2330_n1u, s2330_n2t, s2330_n2u, s2330_n3t, s2330_n3u,
        # 聯發科
        g(stocks, "2454_close"), g(stocks, "2454_change_pct"), g(stocks, "2454_rsi"), g(stocks, "2454_ma20"),
        fsg("2454","direction"), fsg("2454","buy_range"), fsg("2454","stop_loss"), fsg("2454","target"),
        s2454_n1t, s2454_n1u, s2454_n2t, s2454_n2u,
        # 國巨
        g(stocks, "2327_close"), g(stocks, "2327_change_pct"), g(stocks, "2327_rsi"), g(stocks, "2327_ma20"),
        fsg("2327","direction"), fsg("2327","buy_range"), fsg("2327","stop_loss"), fsg("2327","target"),
        s2327_n1t, s2327_n1u, s2327_n2t, s2327_n2u,
        # 動態精選股
        top_stocks_json,
        g(ai, "top_stocks_reason"),
        # 台股新聞
        news_item(yn,0,"title"), news_item(yn,0,"url"),
        news_item(yn,1,"title"), news_item(yn,1,"url"),
        news_item(yn,2,"title"), news_item(yn,2,"url"),
        # 產業新聞
        news_item(dn,0,"title"), news_item(dn,0,"url"),
        news_item(dn,1,"title"), news_item(dn,1,"url"),
        news_item(dn,2,"title"), news_item(dn,2,"url"),
        # 總經事件
        news_item(fe,0,"title"), news_item(fe,0,"date"),
        news_item(fe,1,"title"), news_item(fe,1,"date"),
        news_item(fe,2,"title"), news_item(fe,2,"date"),
        # AI 全文
        g(ai, "taiex_ai"), g(ai, "institutional_ai"), g(ai, "margin_ai"),
        g(ai, "fx_ai"), g(ai, "futures_ai"), g(ai, "global_ai"),
        g(ai, "strategy_ai"), g(ai, "risk_warning"),
        g(ai, "sector_trend_ai"), g(ai, "macro_ai"),
        g(ai, "today_strongest_sector"), g(ai, "today_biggest_risk_stock"),
        # 系統
        "",  # 手動更新時間（空白，手動填）
        str(ai.get("reanalysis_count", 0)),
    ]
    return row


def write(market: dict, futures: dict, stocks: dict,
          ai: dict, news: dict,
          credentials_json: str = "", sheet_id: str = "") -> list:
    """主入口：寫入一列到 Sheets，回傳 history_rows"""
    creds = credentials_json or os.environ.get("GOOGLE_CREDENTIALS", "")
    sid = sheet_id or os.environ.get("SHEET_ID", "")

    if not creds or not sid:
        print("[write_sheets] 未設定 GOOGLE_CREDENTIALS 或 SHEET_ID，跳過")
        return []

    try:
        client = get_client(creds)
        spreadsheet = client.open_by_key(sid)
        sheet = spreadsheet.sheet1

        init_sheet(sheet)
        history_rows = get_history_rows(sheet, n=25)

        row = build_row(market, futures, stocks, ai, news, history_rows)
        today_str = row[0]  # 日期 欄位（已改用台灣時區計算，避免 UTC 造成的日期偏移）

        # 避免同一天重複執行（手動重跑 / 排程重試）造成同日多筆重複列：
        # 若「日期」欄已存在今天的資料列，改為覆蓋該列，而非永遠 append 新列
        all_values = sheet.get_all_values()
        existing_row_num = None
        for i, r in enumerate(all_values[1:], start=2):  # 從第2列開始（第1列是 header）
            if r and len(r) > 0 and r[0] == today_str:
                existing_row_num = i
                break

        if existing_row_num:
            end_col = gspread.utils.rowcol_to_a1(1, len(row)).rstrip("1")
            sheet.update(f"A{existing_row_num}:{end_col}{existing_row_num}", [row], value_input_option="USER_ENTERED")
            print(f"[write_sheets] 完成，{today_str} 已有資料列（第 {existing_row_num} 列），已覆蓋更新，共 {len(row)} 欄")
        else:
            sheet.append_row(row, value_input_option="USER_ENTERED")
            print(f"[write_sheets] 完成，新增 {today_str} 資料列，共 {len(row)} 欄寫入 Sheets")

        return history_rows

    except Exception as e:
        print(f"[write_sheets] 錯誤: {e}")
        return []


def get_history(credentials_json: str = "", sheet_id: str = "", n: int = 7) -> list:
    """供 reanalyze.py 讀取歷史資料"""
    creds = credentials_json or os.environ.get("GOOGLE_CREDENTIALS", "")
    sid = sheet_id or os.environ.get("SHEET_ID", "")
    try:
        client = get_client(creds)
        sheet = client.open_by_key(sid).sheet1
        return get_history_rows(sheet, n)
    except Exception as e:
        print(f"[write_sheets.get_history] 錯誤: {e}")
        return []


if __name__ == "__main__":
    print(f"欄位總數：{len(HEADERS)}")
    for i, h in enumerate(HEADERS):
        print(f"  {i+1:3d}. {h}")
