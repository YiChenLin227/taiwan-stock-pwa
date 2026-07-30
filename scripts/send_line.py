#!/usr/bin/env python3
"""
send_line.py — 透過 LINE Messaging API 廣播每日盤前摘要給官方帳號好友
需要環境變數 LINE_CHANNEL_ACCESS_TOKEN（GitHub Actions Secret）
"""

import os
import requests

BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"
PAGE_URL = "https://yichenlin227.github.io/taiwan-stock-pwa/"


def build_message(render_data: dict) -> str:
    """從渲染資料組出簡短文字推播內容"""
    trading_date = render_data.get("trading_date", "")
    direction    = render_data.get("market_direction", "")
    taiex_close  = render_data.get("taiex_close", "")
    taiex_change_pct = render_data.get("taiex_change_pct", "")

    lines = [f"📊 台股盤前 {trading_date}"]
    if direction:
        lines.append(f"大盤方向：{direction}")
    if taiex_close:
        chg = f"（{taiex_change_pct}）" if taiex_change_pct else ""
        lines.append(f"加權指數：{taiex_close} {chg}".rstrip())
    lines.append(f"👉 完整分析：{PAGE_URL}")
    return "\n".join(lines)


def send_broadcast(text: str, channel_access_token: str) -> None:
    """呼叫 LINE Messaging API 的 broadcast 端點，推給所有加官方帳號好友"""
    headers = {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json",
    }
    body = {"messages": [{"type": "text", "text": text}]}
    r = requests.post(BROADCAST_URL, headers=headers, json=body, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"LINE broadcast failed: {r.status_code} {r.text}")


def send_daily_broadcast(render_data: dict, channel_access_token: str) -> None:
    """主入口：組訊息 + 廣播"""
    text = build_message(render_data)
    send_broadcast(text, channel_access_token)


if __name__ == "__main__":
    # 手動測試用：export LINE_CHANNEL_ACCESS_TOKEN=xxx && python send_line.py
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        print("請設定 LINE_CHANNEL_ACCESS_TOKEN 環境變數")
    else:
        send_broadcast("這是一則測試訊息 🚀（台股盤前 PWA 已連接 LINE 官方帳號）", token)
        print("已送出測試訊息，請確認 LINE 官方帳號好友是否收到")
