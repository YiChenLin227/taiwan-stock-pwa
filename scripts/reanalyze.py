"""
reanalyze.py
手動觸發：讀取今日 Sheets 資料（含手動更新欄位）→ 重新 AI 分析 → 渲染 HTML
用法：在 GitHub Actions 手動執行 reanalyze.yml workflow
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

import fetch_stocks
import fetch_news
import analyze
import write_sheets
import render_html


def main():
    print(f"\n{'='*60}")
    print(f"重新 AI 分析  {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 讀取 Sheets 今日資料（含手動更新的欄位）
    print("【1】讀取 Sheets 歷史及今日資料...")
    history_rows = write_sheets.get_history(n=8)

    if not history_rows:
        print("❌ 無法讀取 Sheets 資料，請確認 Secrets 設定正確")
        return

    today_row = history_rows[-1]  # 最新一筆（今日）
    prev_rows = history_rows[:-1]  # 歷史

    # 從 Sheets 重建 market / futures / stocks dict
    def row_to_market(row):
        return {
            "trade_date": row.get("日期", ""),
            "taiex_close": row.get("加權指數收盤", ""),
            "taiex_change": row.get("加權指數漲跌", ""),
            "taiex_change_pct": row.get("加權指數漲跌%", ""),
            "volume_trillion": row.get("成交量兆", ""),
            "foreign_net_yi": row.get("外資買賣超億", ""),
            "trust_net_yi": row.get("投信買賣超億", ""),
            "dealer_net_yi": row.get("自營商買賣超億", ""),
            "total_net_yi": row.get("三大合計億", ""),
            "margin_change": row.get("融資餘額變化", ""),
            "short_balance": row.get("融券餘額", ""),
            "twd_usd": row.get("台幣匯率", ""),
            "foreign_top3_names": [
                row.get("外資個股排名1", ""),
                row.get("外資個股排名2", ""),
                row.get("外資個股排名3", ""),
            ],
        }

    def row_to_futures(row):
        return {
            "night_futures_last": row.get("夜盤台指期收盤", ""),
            "night_futures_change": row.get("夜盤台指期漲跌", ""),
            "night_futures_oi": row.get("台指期未平倉口", ""),
            "futures_foreign_net_oi": row.get("外資期貨淨多單口", ""),
            "pc_ratio": row.get("PC比", ""),
            "pc_sentiment": row.get("PC情緒", ""),
            "max_call_oi_strike": row.get("最大Call未平倉履約價", ""),
            "max_put_oi_strike": row.get("最大Put未平倉履約價", ""),
        }

    market  = row_to_market(today_row)
    futures = row_to_futures(today_row)

    # 重新抓個股（以取得最新技術指標）
    print("【2】重新抓取個股即時資料...")
    stocks = fetch_stocks.fetch_all()

    # 重新抓新聞
    print("【3】重新抓取新聞...")
    news = fetch_news.fetch_all(os.environ.get("FRED_API_KEY", ""))

    # 重新 AI 分析
    print("【4】Claude AI 重新分析...")
    ai_result = analyze.analyze(market, futures, stocks, [], news, prev_rows)

    # 更新重新分析次數
    try:
        prev_count = int(today_row.get("重新分析次數", "0"))
    except:
        prev_count = 0
    ai_result["reanalysis_count"] = prev_count + 1

    # 重新渲染 HTML
    print("【5】重新渲染 index.html...")
    render_html.render(market, futures, stocks, ai_result, news)

    print(f"\n✅ 重新分析完成（第 {ai_result['reanalysis_count']} 次）")


if __name__ == "__main__":
    main()
