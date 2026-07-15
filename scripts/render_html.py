#!/usr/bin/env python3
"""render_html.py — Render dynamic index.html from data dict"""

import json, os, re
from datetime import datetime

# ── CSS (exact copy, static) ─────────────────────────────────────────────────
CSS = """
:root {
  --bg: #0f1419; --card: #1a2129; --card2: #202a35; --line: #2c3947;
  --txt: #e6edf3; --sub: #9fb0c0; --up: #ef4444; --dn: #22c55e;
  --gold: #f5b942; --ai: #7c93ff; --aibg: #1c2340; --acc: #38bdf8;
  --nav-h: 64px; --safe-b: env(safe-area-inset-bottom, 0px);
}
* { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
html, body { height: 100%; overflow: hidden; background: var(--bg); color: var(--txt);
  font-family: -apple-system, "PingFang TC", "Noto Sans TC", system-ui, sans-serif;
  font-size: 15px; line-height: 1.6; }
.hdr {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  background: rgba(15,20,25,0.92); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
  padding: env(safe-area-inset-top, 0) 16px 0;
}
.hdr-inner { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; }
.hdr-title { font-size: 17px; font-weight: 700; letter-spacing: .3px; }
.hdr-sub { font-size: 11px; color: var(--sub); margin-top: 1px; }
.dir-badge { font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 20px;
  background: #2a2310; border: 1px solid #5a4a1a; color: var(--gold); }
.pages-wrap { position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  padding-top: calc(60px + env(safe-area-inset-top, 0px));
  padding-bottom: calc(var(--nav-h) + var(--safe-b)); }
.pages { display: block; height: 100%; overflow: hidden; }
.page { width: 100%; height: 100%; overflow-y: auto; padding: 14px 14px 20px;
  scroll-behavior: smooth; -webkit-overflow-scrolling: touch; }
.page.hidden { display: none; }
.bnav {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 100;
  background: rgba(15,20,25,0.95); backdrop-filter: blur(12px);
  border-top: 1px solid var(--line); display: flex; align-items: stretch;
  padding-bottom: var(--safe-b); height: calc(var(--nav-h) + var(--safe-b));
}
.bnav-btn { flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 3px; padding: 8px 0; cursor: pointer;
  border: none; background: none; color: var(--sub); transition: color 0.15s; -webkit-appearance: none; }
.bnav-btn.active { color: var(--acc); }
.bnav-icon { font-size: 22px; line-height: 1; }
.bnav-label { font-size: 10px; font-weight: 600; letter-spacing: .3px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 14px 16px; margin-bottom: 10px; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
.stat { background: var(--card2); border: 1px solid var(--line); border-radius: 10px; padding: 11px 12px; }
.stat .k { font-size: 11px; color: var(--sub); margin-bottom: 3px; }
.stat .v { font-size: 18px; font-weight: 700; line-height: 1.2; }
.stat .d { font-size: 12px; color: var(--sub); margin-top: 2px; }
.up { color: var(--up); } .dn { color: var(--dn); }
.gold { color: var(--gold); } .acc { color: var(--acc); } .sub { color: var(--sub); }
.ai { background: var(--aibg); border: 1px solid #34407a; border-radius: 12px;
  padding: 12px 14px; margin-bottom: 10px; font-size: 13.5px; }
.ai-tag { color: var(--ai); font-weight: 700; font-size: 12px; margin-bottom: 6px; }
.sec-hdr { font-size: 15px; font-weight: 700; color: var(--acc);
  border-left: 3px solid var(--acc); padding-left: 10px; margin: 16px 0 10px; }
.alert { background: #2a1a1a; border: 1px solid #5a2a2a; border-radius: 12px;
  padding: 12px 14px; margin-bottom: 10px; font-size: 13px; }
.alert .alert-title { color: var(--up); font-weight: 700; margin-bottom: 4px; }
.collapse-btn { width: 100%; background: var(--card); border: 1px solid var(--line);
  border-radius: 12px; padding: 13px 16px; cursor: pointer; text-align: left;
  color: var(--txt); font-size: 14px; font-weight: 600; margin-bottom: 8px;
  display: flex; justify-content: space-between; align-items: center; -webkit-appearance: none; }
.collapse-btn .arrow { color: var(--sub); transition: transform 0.25s; font-size: 12px; }
.collapse-btn.open .arrow { transform: rotate(180deg); }
.collapse-content { display: none; padding: 0 0 8px; }
.collapse-content.show { display: block; }
.stock-card { background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  overflow: hidden; margin-bottom: 10px; }
.stock-hdr { padding: 12px 14px; background: var(--card2); border-bottom: 1px solid var(--line);
  display: flex; justify-content: space-between; align-items: center; }
.stock-name { font-size: 16px; font-weight: 700; }
.stock-code { font-size: 12px; color: var(--sub); margin-top: 1px; }
.stock-price { text-align: right; }
.stock-body { padding: 12px 14px; }
.opbox { background: #161e28; border-left: 3px solid var(--gold); border-radius: 0 10px 10px 0;
  padding: 10px 14px; margin: 8px 0; }
.opbox .op-dir { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
.op-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.op-item .lbl { font-size: 11px; color: var(--sub); }
.op-item .val { font-size: 13px; font-weight: 600; }
.check-list { list-style: none; }
.check-list li { padding: 8px 0; border-bottom: 1px solid var(--line); font-size: 13.5px;
  display: flex; gap: 10px; align-items: flex-start; }
.check-list li:last-child { border-bottom: none; }
.check-list .icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }
.news-item { padding: 9px 0; border-bottom: 1px solid var(--line); font-size: 13px; }
.news-item:last-child { border-bottom: none; }
.news-item a { color: var(--acc); text-decoration: none; }
.news-meta { font-size: 11px; color: var(--sub); margin-top: 2px; }
.chart-wrap { background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 12px; margin-bottom: 10px; }
.chart-wrap canvas { max-height: 200px; }
.chart-cap { font-size: 11px; color: var(--sub); margin-top: 6px; text-align: center; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th { background: var(--card2); color: var(--sub); padding: 7px 8px; font-size: 11px; font-weight: 600; text-align: left; }
.tbl td { padding: 8px 8px; border-bottom: 1px solid var(--line); vertical-align: middle; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 600; }
.tag.buy { color: var(--up); background: #2a1818; border: 1px solid #5a2a2a; }
.tag.sell { color: var(--dn); background: #13241a; border: 1px solid #1f3a28; }
.tag.hold { color: var(--gold); background: #2a2210; border: 1px solid #5a4a1a; }
"""

# ── Helpers ──────────────────────────────────────────────────────────────────
def v(val, default="⚠️ N/A"):
    return val if val not in (None, "", "NA", "N/A", "nan") else default

def g(data, key, default="⚠️"):
    return v(data.get(key), default)

def na_link(url, label="查詢"):
    return f'<a href="{url}" target="_blank" style="color:var(--acc)">{label}</a>'

def news_items(news_list):
    if not news_list:
        return '<div class="news-item"><span class="sub">⚠️ 暫無新聞資料</span></div>'
    html = ""
    for n in news_list[:3]:
        title = n.get("title", "")
        url = n.get("url", "#")
        source = n.get("source", "")
        date = n.get("date", "")
        html += f'''<div class="news-item">
          <a href="{url}" target="_blank">{title}</a>
          <div class="news-meta">{date} ‧ {source}</div>
        </div>'''
    return html

def stock_card_fixed(s, code, title_note=""):
    """Render a fixed stock card (2330/2454/2327)"""
    css_change = s.get("change_css", "sub")
    css_adr = s.get("adr_css", "sub")
    css_foreign = s.get("foreign_css", "up")
    css_rsi = s.get("rsi_css", "gold")
    css_dir = s.get("direction_css", "gold")
    has_adr = code == "2330"
    
    # Header right panel
    if has_adr:
        price_panel = f'''<div style="font-size:12px;color:var(--sub)">ADR</div>
        <div class="{css_adr}" style="font-size:17px;font-weight:700">{v(s.get("adr_close"),"⚠️ 待查")}</div>
        <div class="{css_adr}" style="font-size:12px">{v(s.get("adr_change_pct"),"⚠️")}</div>'''
    else:
        trend_text = s.get("trend_text", "偏多")
        trend_css = s.get("trend_css", "dn")
        price_panel = f'''<div style="font-size:12px;color:var(--sub)">近期趨勢</div>
        <div class="{trend_css}" style="font-size:17px;font-weight:700">{trend_text}</div>'''

    extra_label = s.get("extra_label", "催化劑")
    extra_value = s.get("extra_value", "—")
    extra_css = s.get("extra_css", "gold")

    notes = news_items(s.get("news", []))
    trading_date = s.get("trading_date", "前日")

    return f'''  <div class="stock-card">
    <div class="stock-hdr">
      <div>
        <div class="stock-name">{s.get("name","?")} <span style="color:var(--sub);font-size:13px">{code}</span></div>
        <div class="stock-code">{s.get("desc","")}{(" ‧ " + title_note) if title_note else ""}</div>
      </div>
      <div class="stock-price">{price_panel}</div>
    </div>
    <div class="stock-body">
      <div class="stats">
        <div class="stat">
          <div class="k">{trading_date} 收盤</div><div class="v {css_change}">{v(s.get("close"),"⚠️ 待查")}</div><div class="d {css_change}">{v(s.get("change_pct"),"")}</div>
          <div class="d sub" style="margin-top:4px"><a href="https://goodinfo.tw/tw/StockInfo.asp?STOCK_ID={code}" target="_blank" style="color:var(--acc);font-size:10px">📎 Goodinfo</a></div>
        </div>
        <div class="stat">
          <div class="k">外資 {trading_date}</div><div class="v {css_foreign}">{v(s.get("foreign_rank"),"⚠️ 待查")}</div><div class="d sub">{v(s.get("foreign_desc"),"")}</div>
          <div class="d sub" style="margin-top:4px"><a href="https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID={code}&CHT_CAT=DATE" target="_blank" style="color:var(--acc);font-size:10px">📎 外資明細</a></div>
        </div>
        <div class="stat">
          <div class="k">RSI</div><div class="v {css_rsi}">{v(s.get("rsi"),"⚠️ 待查")}</div><div class="d sub">{v(s.get("rsi_desc"),"")}</div>
          <div class="d sub" style="margin-top:4px"><a href="https://tw.tradingview.com/chart/?symbol=TWSE%3A{code}" target="_blank" style="color:var(--acc);font-size:10px">📎 TradingView</a></div>
        </div>
        <div class="stat">
          <div class="k">{extra_label}</div><div class="v {extra_css}">{extra_value}</div><div class="d sub">{v(s.get("extra_desc"),"")}</div>
        </div>
      </div>
      <div class="opbox">
        <div class="op-dir">📌 操作建議：<span class="{css_dir}">{v(s.get("direction"),"觀望")}</span></div>
        <div class="op-grid">
          <div class="op-item"><div class="lbl">建議買入</div><div class="val acc">{v(s.get("buy_range"),"⚠️ 待查")}</div></div>
          <div class="op-item"><div class="lbl">停損線</div><div class="val up">{v(s.get("stop_loss"),"⚠️ 待查")}</div></div>
          <div class="op-item"><div class="lbl">中線目標</div><div class="val dn">{v(s.get("target"),"⚠️ 待查")}</div></div>
          <div class="op-item"><div class="lbl">{s.get("op4_label","技術面")}</div><div class="val gold">{v(s.get("op4_value"),"—")}</div></div>
        </div>
      </div>
      <div class="ai" style="margin-top:8px">
        <div class="ai-tag">✦ AI 解讀</div>
        {v(s.get("ai_insight"),"AI 解讀暫無資料")}
      </div>
      <button class="collapse-btn" onclick="toggleCollapse(this)">近期新聞 <span class="arrow">▼</span></button>
      <div class="collapse-content">{notes}</div>
    </div>
  </div>'''

def stock_card_dynamic(s):
    """Render a dynamic AI-selected stock card"""
    code = s.get("code", "")
    css_change = s.get("change_css", "sub")
    css_dir = s.get("direction_css", "dn")
    css_rsi = s.get("rsi_css", "gold")
    trading_date = s.get("trading_date", "前日")
    notes = news_items(s.get("news", []))
    return f'''  <div class="stock-card">
    <div class="stock-hdr">
      <div>
        <div class="stock-name">{s.get("name","?")} <span style="color:var(--sub);font-size:13px">{code}</span></div>
        <div class="stock-code">{v(s.get("desc"),"")}</div>
      </div>
      <div class="stock-price">
        <div style="font-size:12px;color:var(--sub)">操盤方向</div>
        <div class="{css_dir}" style="font-size:17px;font-weight:700">{v(s.get("direction"),"偏多")}</div>
      </div>
    </div>
    <div class="stock-body">
      <div class="stats">
        <div class="stat">
          <div class="k">{trading_date} 收盤</div><div class="v {css_change}">{v(s.get("close"),"⚠️ 待查")}</div><div class="d {css_change}">{v(s.get("change_pct"),"")}</div>
          <div class="d sub" style="margin-top:4px"><a href="https://goodinfo.tw/tw/StockInfo.asp?STOCK_ID={code}" target="_blank" style="color:var(--acc);font-size:10px">📎 Goodinfo</a></div>
        </div>
        <div class="stat">
          <div class="k">外資 {trading_date}</div><div class="v {s.get("foreign_css","sub")}">{v(s.get("foreign_rank"),"⚠️ 待查")}</div><div class="d sub">{v(s.get("foreign_desc"),"")}</div>
          <div class="d sub" style="margin-top:4px"><a href="https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID={code}&CHT_CAT=DATE" target="_blank" style="color:var(--acc);font-size:10px">📎 外資明細</a></div>
        </div>
        <div class="stat">
          <div class="k">RSI</div><div class="v {css_rsi}">{v(s.get("rsi"),"⚠️ 待查")}</div><div class="d sub">{v(s.get("rsi_desc"),"")}</div>
          <div class="d sub" style="margin-top:4px"><a href="https://tw.tradingview.com/chart/?symbol=TWSE%3A{code}" target="_blank" style="color:var(--acc);font-size:10px">📎 TradingView</a></div>
        </div>
        <div class="stat">
          <div class="k">核心題材</div><div class="v dn">{v(s.get("theme"),"AI 概念")}</div><div class="d sub">{v(s.get("theme_desc"),"")}</div>
        </div>
      </div>
      <div class="opbox">
        <div class="op-dir">📌 操作建議：<span class="{css_dir}">{v(s.get("direction"),"偏多")}</span></div>
        <div class="op-grid">
          <div class="op-item"><div class="lbl">建議買入</div><div class="val acc">{v(s.get("buy_range"),"⚠️ 待查")}</div></div>
          <div class="op-item"><div class="lbl">停損線</div><div class="val up">{v(s.get("stop_loss"),"⚠️ 待查")}</div></div>
          <div class="op-item"><div class="lbl">中線目標</div><div class="val dn">{v(s.get("target"),"⚠️ 待查")}</div></div>
          <div class="op-item"><div class="lbl">AI 選股理由</div><div class="val gold" style="font-size:11px">{v(s.get("selection_reason","")[:20],"強勢")}</div></div>
        </div>
      </div>
      <div class="ai" style="margin-top:8px">
        <div class="ai-tag">✦ AI 解讀</div>
        {v(s.get("ai_insight"),"AI 解讀暫無資料")}
      </div>
      <button class="collapse-btn" onclick="toggleCollapse(this)">近期新聞 <span class="arrow">▼</span></button>
      <div class="collapse-content">{notes}</div>
    </div>
  </div>'''


def render(data: dict, output_path: str = "./index.html"):
    d = data
    trading_date = g(d, "trading_date", "前日")
    today = g(d, "today", datetime.now().strftime("%Y/%m/%d"))
    today_short = g(d, "today_short", today[-5:])
    market_direction = g(d, "market_direction", "中性")
    biggest_risk = g(d, "biggest_risk", "請確認當日市場狀況")
    
    # determine badge style
    dir_map = {
        "強勢做多": ("dn","💹"), "偏多": ("dn","📈"), "中性偏多": ("gold","📊"),
        "中性": ("sub","⚖️"), "中性偏空": ("gold","⚠️"), "偏空": ("up","⚠️"), "強勢做空": ("up","🔻")
    }
    dir_css, dir_icon = dir_map.get(market_direction, ("gold","⚠️"))

    # ── page-0 大盤 ──────────────────────────────────────────────────────────
    taiex_close = g(d,"taiex_close","—")
    taiex_change = g(d,"taiex_change","—")
    taiex_change_pct = g(d,"taiex_change_pct","—")
    taiex_css = d.get("taiex_css","dn")
    open_lo = g(d,"open_range_low","—")
    open_hi = g(d,"open_range_high","—")
    volume = g(d,"volume_trillion","—")
    volume_desc = g(d,"volume_desc","—")
    twd = g(d,"twd_usd","—")
    fx_change = g(d,"fx_change_pct","—")
    fx_desc = g(d,"fx_change_desc","—")
    fx_css = d.get("fx_css","sub")
    adr_close = g(d,"tsm_adr_close","—")
    adr_pct = g(d,"tsm_adr_change_pct","—")
    adr_css = d.get("tsm_adr_css","sub")
    night_fut = g(d,"night_futures_last","⚠️ 待即時更新")
    support = g(d,"key_support","—")
    resist = g(d,"key_resistance","—")
    taiex_ai = g(d,"taiex_ai","AI 解讀暫無資料")
    
    # AI summary card
    ai_opportunities = g(d,"ai_opportunities","請確認當日機會")
    ai_risks_text = g(d,"ai_risks_text","請確認當日風險")
    ai_best_strategy = g(d,"ai_best_strategy","開盤觀望後依外資方向操作")

    # Global indices
    def idx_row(name, change, css_cls, desc, url):
        avail = change not in (None,"","NA","N/A","⚠️ N/A","nan")
        val = change if avail else "⚠️ 無法獲取"
        c = css_cls if avail else "sub"
        return f'<tr><td>{name}</td><td class="{c}">{val}</td><td>{desc}</td><td><a href="{url}" target="_blank" style="color:var(--acc);font-size:10px">📎</a></td></tr>'

    global_rows = (
        idx_row("那斯達克", d.get("nasdaq_change"), d.get("nasdaq_css","dn"), d.get("nasdaq_desc","—"), "https://finance.yahoo.com/quote/%5EIXIC/") +
        idx_row("道瓊", d.get("dji_change"), d.get("dji_css","dn"), d.get("dji_desc","—"), "https://finance.yahoo.com/quote/%5EDJI/") +
        idx_row("費城半導體 SOX", d.get("sox_change"), d.get("sox_css","dn"), d.get("sox_desc","—"), "https://finance.yahoo.com/quote/%5ESOX/") +
        idx_row("VIX 恐慌指數", d.get("vix"), d.get("vix_css","sub"), d.get("vix_desc","—"), "https://finance.yahoo.com/quote/%5EVIX/") +
        idx_row("日圓 USD/JPY", d.get("nikkei_change"), d.get("nikkei_css","sub"), d.get("nikkei_desc","—"), "https://finance.yahoo.com/quote/%5EN225/") +
        idx_row("恆生指數", d.get("hsi_change"), d.get("hsi_css","sub"), d.get("hsi_desc","—"), "https://finance.yahoo.com/quote/%5EHSI/") +
        idx_row("黃金 GC", d.get("gold_change"), d.get("gold_css","sub"), d.get("gold_desc","—"), "https://finance.yahoo.com/quote/GC=F/") +
        idx_row("布蘭特原油", d.get("brent_change"), d.get("brent_css","sub"), d.get("brent_desc","—"), "https://finance.yahoo.com/quote/BZ=F/") +
        idx_row("TSM ADR", adr_pct, adr_css, "⚠️ 壓台積電" if adr_css=="dn" else "↑ 助台積電", "https://finance.yahoo.com/quote/TSM/")
    )

    # ── page-1 法人 ──────────────────────────────────────────────────────────
    foreign_net = g(d,"foreign_net_yi","—")
    foreign_css = d.get("foreign_css","sub")
    trust_net = g(d,"trust_net_yi","—")
    trust_css = d.get("trust_css","sub")
    dealer_net = g(d,"dealer_net_yi","—")
    dealer_css = d.get("dealer_css","sub")
    total_net = g(d,"total_net_yi","—")
    total_css = d.get("total_css","sub")
    foreign_top1 = g(d,"foreign_top1","—")
    trust_desc_txt = g(d,"trust_desc","—")
    dealer_desc_txt = g(d,"dealer_desc","—")
    total_desc_txt = g(d,"total_desc","—")
    institutional_ai = g(d,"institutional_ai","AI 解讀暫無資料")
    margin_ai = g(d,"margin_ai","AI 解讀暫無資料")
    fx_ai = g(d,"fx_ai","AI 解讀暫無資料")

    # Foreign top-3
    ftop3 = d.get("foreign_top3", [])
    medals = ["🥇 第1","🥈 第2","🥉 第3"]
    top3_rows = ""
    for i, s in enumerate(ftop3[:3]):
        medal = medals[i] if i < 3 else f"第{i+1}"
        name = s.get("name","—")
        css_td = s.get("css","up")
        top3_rows += f'<tr><td>{medal}</td><td><strong>{name}</strong></td><td class="{css_td}">外資買超</td></tr>'
    if not top3_rows:
        top3_rows = '<tr><td colspan="3" class="sub">⚠️ 外資排名待更新 — <a href="https://www.twse.com.tw/zh/trading/foreign/twt38u.html" target="_blank" style="color:var(--acc)">TWSE查詢</a></td></tr>'

    # Margin
    margin_change = g(d,"margin_change_yi","—")
    margin_css = d.get("margin_change_css","sub")
    margin_desc_txt = g(d,"margin_change_desc","—")
    short_bal = g(d,"short_balance","—")
    short_ratio = g(d,"short_ratio_pct","—")

    # PC ratio
    pc_ratio = d.get("pc_ratio")
    pc_sentiment = g(d,"pc_sentiment","中性")
    if pc_ratio not in (None,"","NA","N/A"):
        pc_val = f"{pc_ratio}"
        pc_desc = g(d,"pc_desc", f"市場情緒：{pc_sentiment}")
        pc_css_val = "dn" if pc_sentiment in ("偏多","強勢多") else ("up" if pc_sentiment in ("偏空","強勢空") else "gold")
    else:
        pc_val = "⚠️ 待即時查證"
        pc_desc = "即時查詢"
        pc_css_val = "sub"

    # Earnings calendar
    cal_rows = ""
    for ev in d.get("earnings_calendar", []):
        date = ev.get("date","—")
        name = ev.get("name","—")
        etype = ev.get("type","法說會")
        stars = ev.get("importance_stars","★★☆")
        tag_css = ev.get("css","hold")
        is_important = ev.get("is_important", False)
        row_style = ' style="background:rgba(245,185,66,0.08)"' if is_important else ""
        date_cell = f'<strong class="gold">{date} ⭐</strong>' if is_important else f'<strong>{date}</strong>'
        name_cell = f'<strong>{name}</strong>' if is_important else name
        cal_rows += f'<tr{row_style}><td>{date_cell}</td><td>{name_cell}</td><td><span class="tag {tag_css}" style="font-size:10px">{etype}</span></td><td><span class="gold">{stars}</span></td></tr>'
    if not cal_rows:
        cal_rows = '<tr><td colspan="4" class="sub">⚠️ 暫無行事曆資料 — <a href="https://mops.twse.com.tw/mops/web/t05st29_1" target="_blank" style="color:var(--acc)">公開資訊觀測站</a></td></tr>'
    earnings_ai = g(d,"earnings_ai","AI 行事曆解讀暫無資料")

    # ── page-2 個股 ──────────────────────────────────────────────────────────
    s2330 = d.get("stock_2330", {})
    s2330.setdefault("name","台積電"); s2330.setdefault("trading_date", trading_date)
    s2330.setdefault("desc","晶圓代工龍頭")
    s2330.setdefault("extra_label","外資目標價"); s2330.setdefault("extra_css","acc")
    s2330.setdefault("extra_value",g(d,"tsm_target_price","$487"))
    s2330.setdefault("extra_desc","ADR 分析師共識")
    s2330.setdefault("op4_label","法說會"); s2330.setdefault("op4_value","待確認")

    s2454 = d.get("stock_2454", {})
    s2454.setdefault("name","聯發科"); s2454.setdefault("trading_date", trading_date)
    s2454.setdefault("desc","IC 設計龍頭 ‧ AI 晶片 / AI PC 概念")
    s2454.setdefault("trend_text","↑ 強勢"); s2454.setdefault("trend_css","dn")
    s2454.setdefault("extra_label","關注催化劑"); s2454.setdefault("extra_css","gold")
    s2454.setdefault("extra_value","AI PC 旺季"); s2454.setdefault("extra_desc","H2 出貨放量")
    s2454.setdefault("op4_label","H2 旺季"); s2454.setdefault("op4_value","AI 晶片出貨")

    s2327 = d.get("stock_2327", {})
    s2327.setdefault("name","國巨"); s2327.setdefault("trading_date", trading_date)
    s2327.setdefault("desc","被動元件龍頭")
    s2327.setdefault("trend_text","偏多"); s2327.setdefault("trend_css","dn")
    s2327.setdefault("extra_label","受益題材"); s2327.setdefault("extra_css","dn")
    s2327.setdefault("extra_value","AI 伺服器"); s2327.setdefault("extra_desc","MLCC/電阻需求↑")
    s2327.setdefault("op4_label","外資連動"); s2327.setdefault("op4_value","ADR 風險留意")

    card_2330 = stock_card_fixed(s2330, "2330", "⚠️ ADR 衝擊" if adr_css=="dn" else "ADR 助漲")
    card_2454 = stock_card_fixed(s2454, "2454")
    card_2327 = stock_card_fixed(s2327, "2327")

    # Dynamic top stocks
    top_stocks = d.get("top_stocks", [])
    top_stocks_html = ""
    for s in top_stocks:
        s.setdefault("trading_date", trading_date)
        top_stocks_html += stock_card_dynamic(s) + "\n"
    if not top_stocks_html:
        top_stocks_html = '<div class="card"><div class="sub">⚠️ AI 尚未選出精選股，請稍後重新分析</div></div>'

    top_stocks_reason = g(d,"top_stocks_reason","AI 精選依據：外資買超強度、技術面動能、產業題材綜合判斷")

    # ── page-3 操盤 ──────────────────────────────────────────────────────────
    strategy_ai = g(d,"strategy_ai","AI 策略解讀暫無資料")
    risk_ai = g(d,"risk_ai","請確認當日風險")
    macro_ai = g(d,"macro_ai","AI 總結暫無資料")
    full_ai = g(d,"full_ai_text","")
    today_strongest = g(d,"today_strongest_sector","AI 伺服器")
    today_biggest_risk = g(d,"today_biggest_risk_stock","請注意盤中變化")
    reanalysis_count = d.get("reanalysis_count",0)
    update_time = g(d,"update_time","--:--")
    generated_at = g(d,"generated_at","--")
    stop_loss_tsmc = g(d,"stop_loss_tsmc", s2330.get("stop_loss","—"))
    stop_loss_taiex = g(d,"stop_loss_taiex", support)

    # FRED events
    fred_rows = ""
    for ev in d.get("fred_events", []):
        ev_date = ev.get("date","—")
        ev_name = ev.get("name","—")
        ev_imp = ev.get("importance","medium")
        imp_color = "#ef4444" if ev_imp=="high" else ("#f5b942" if ev_imp=="medium" else "#9fb0c0")
        fred_rows += f'<tr><td><strong>{ev_date}</strong></td><td>{ev_name}</td><td style="color:{imp_color};font-weight:700">{"★★★" if ev_imp=="high" else "★★☆"}</td></tr>'
    if not fred_rows:
        fred_rows = '<tr><td colspan="3" class="sub">⚠️ 暫無 FRED 事件 — <a href="https://fred.stlouisfed.org/releases" target="_blank" style="color:var(--acc)">FRED查詢</a></td></tr>'

    # ── page-4 産業 ──────────────────────────────────────────────────────────
    sectors = d.get("sectors", [])
    sector_html = ""
    for sec in sectors:
        highlight = sec.get("highlight", False)
        border_style = ';border:1px solid rgba(16,185,129,0.25)' if highlight else ""
        trend_label = sec.get("trend","中性")
        trend_css = sec.get("trend_css","sub")
        trend_bg = sec.get("trend_bg","rgba(255,255,255,0.05)")
        week_outlook = sec.get("week_outlook","觀望")
        week_css = sec.get("week_css","sub")
        week_bg = sec.get("week_bg","rgba(255,255,255,0.04)")
        month_outlook = sec.get("month_outlook","中性")
        month_css = sec.get("month_css","gold")
        month_bg = sec.get("month_bg","rgba(245,185,66,0.08)")
        key_event = sec.get("key_event","—")
        desc_text = sec.get("desc","")
        sector_html += f'''  <div class="card" style="margin-bottom:8px{border_style}">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <div>
        <div style="font-size:14px;font-weight:700;color:var(--txt)">{sec.get("num","·")} {sec.get("name","")}</div>
        <div style="font-size:11px;color:var(--sub);margin-top:2px">代表股：{sec.get("reps","")}</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:11px;color:var(--sub)">趨勢判斷</div>
        <div class="{trend_css}" style="font-size:13px;font-weight:700;background:{trend_bg};padding:2px 8px;border-radius:6px">{trend_label}</div>
      </div>
    </div>
    <div style="font-size:12px;color:var(--txt);line-height:1.7;margin-bottom:6px"><strong>當日趨勢動態：</strong>{desc_text}</div>
    <div style="display:flex;gap:8px">
      <div style="flex:1;background:{week_bg};border-radius:6px;padding:6px;text-align:center">
        <div style="font-size:10px;color:var(--sub)">一週展望</div>
        <div style="font-size:12px" class="{week_css}">{week_outlook}</div>
      </div>
      <div style="flex:1;background:{month_bg};border-radius:6px;padding:6px;text-align:center">
        <div style="font-size:10px;color:var(--sub)">一個月展望</div>
        <div style="font-size:12px" class="{month_css}">{month_outlook}</div>
      </div>
      <div style="flex:1;background:rgba(99,102,241,0.08);border-radius:6px;padding:6px;text-align:center">
        <div style="font-size:10px;color:var(--sub)">關鍵事件</div>
        <div style="font-size:12px;color:var(--acc)">{key_event}</div>
      </div>
    </div>
  </div>
'''

    if not sector_html:
        sector_html = '<div class="card"><div class="sub">⚠️ 產業趨勢資料暫無</div></div>'

    sector_trend_ai = g(d,"sector_trend_ai","")

    # ── page-5 復盤 ──────────────────────────────────────────────────────────
    review_date = g(d,"review_date", trading_date)
    review_ai = g(d,"review_ai","AI 復盤解讀暫無資料")

    def review_tag(result):
        if result in ("accurate","correct","準確"): return '<span class="tag buy" style="font-size:10px">✅ 準確</span>'
        if result in ("partial","部分"): return '<span class="tag hold" style="font-size:10px">⚠️ 部分</span>'
        return '<span class="tag hold" style="font-size:10px">待確認</span>'

    market_rows = ""
    for item in d.get("review_market", []):
        actual_css = item.get("actual_css","dn")
        market_rows += f'<tr><td>{item.get("item","—")}</td><td>{item.get("forecast","—")}</td><td class="{actual_css}">{item.get("actual","—")}</td><td>{review_tag(item.get("result",""))}</td></tr>'
    if not market_rows:
        market_rows = '<tr><td colspan="4" class="sub">⚠️ 復盤資料尚未建立</td></tr>'

    stock_review_rows = ""
    for item in d.get("review_stocks", []):
        actual_css = item.get("actual_css","sub")
        stock_review_rows += f'<tr><td>{item.get("name","—")}</td><td>{item.get("forecast","—")}</td><td class="{actual_css}">{item.get("actual","⚠️ 待補充")}</td><td>{review_tag(item.get("result",""))}</td></tr>'
    if not stock_review_rows:
        stock_review_rows = '<tr><td colspan="4" class="sub">⚠️ 個股復盤待補充</td></tr>'

    # ── Charts JS data ────────────────────────────────────────────────────────
    chart_labels = d.get("taiex_chart_labels", [])
    chart_data = d.get("taiex_chart_data", [])
    chart_labels_js = json.dumps(chart_labels, ensure_ascii=False)
    chart_data_js = json.dumps(chart_data)

    inst_data = [
        d.get("foreign_net_raw", 0),
        d.get("trust_net_raw", 0),
        d.get("dealer_net_raw", 0)
    ]
    inst_data_js = json.dumps(inst_data)

    # ── Yahoo News (for 操盤 page) ────────────────────────────────────────────
    yahoo_news_html = ""
    for n in d.get("yahoo_news", [])[:5]:
        yahoo_news_html += f'''<div class="news-item">
          <a href="{n.get("url","#")}" target="_blank">{n.get("title","")}</a>
          <div class="news-meta">{n.get("date","")} ‧ {n.get("source","Yahoo 財經")}</div>
        </div>'''
    if not yahoo_news_html:
        yahoo_news_html = '<div class="news-item"><span class="sub">⚠️ 暫無新聞 — <a href="https://tw.news.yahoo.com/rss/finance" style="color:var(--acc)">Yahoo 財經</a></span></div>'

    digitimes_html = ""
    for n in d.get("digitimes_news", [])[:3]:
        digitimes_html += f'''<div class="news-item">
          <a href="{n.get("url","#")}" target="_blank">{n.get("title","")}</a>
          <div class="news-meta">{n.get("date","")} ‧ DigiTimes</div>
        </div>'''
    if not digitimes_html:
        digitimes_html = '<div class="news-item"><span class="sub">⚠️ 暫無新聞 — <a href="https://www.digitimes.com.tw/tech/rss.xml" style="color:var(--acc)">DigiTimes</a></span></div>'

    # ── Assemble full HTML ────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="台股盤前">
<meta name="theme-color" content="#0f1419">
<title>台股盤前 {today}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>{CSS}</style>
</head>
<body>

<!-- Header -->
<div class="hdr">
  <div class="hdr-inner">
    <div>
      <div class="hdr-title">📊 台股盤前 {today_short}</div>
      <div class="hdr-sub">基準：{trading_date} 收盤 ‧ AI 自動彙整</div>
      <div style="font-size:10px;color:var(--sub);margin-top:2px">🕐 更新：{generated_at}</div>
    </div>
    <div class="dir-badge">{dir_icon} {market_direction}</div>
  </div>
</div>

<!-- Pages -->
<div class="pages-wrap">
<div class="pages" id="pages">

<!-- ① 大盤 -->
<div class="page" id="page-0">

  <div class="alert">
    <div class="alert-title">⚠️ 今日最大風險</div>
    {biggest_risk}
  </div>

  <div class="card" style="background:linear-gradient(135deg,rgba(99,102,241,0.12),rgba(16,185,129,0.07));border:1px solid rgba(99,102,241,0.35);margin-bottom:12px">
    <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">
      <div class="ai-tag" style="font-size:12px">✦ AI 重點整理</div>
      <div style="font-size:11px;color:var(--sub)">{today_short} 盤前自動彙整</div>
    </div>
    <div style="font-size:13px;line-height:1.8;color:var(--text);margin-bottom:10px">
      {strategy_ai[:300] if len(strategy_ai)>300 else strategy_ai}
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
      <div style="background:rgba(16,185,129,0.1);border-radius:8px;padding:8px;border:1px solid rgba(16,185,129,0.2)">
        <div style="font-size:11px;color:var(--sub);margin-bottom:5px">🎯 今日機會</div>
        <div style="font-size:12px;line-height:1.7;color:var(--text)">{ai_opportunities}</div>
      </div>
      <div style="background:rgba(239,68,68,0.08);border-radius:8px;padding:8px;border:1px solid rgba(239,68,68,0.2)">
        <div style="font-size:11px;color:var(--sub);margin-bottom:5px">⚠️ 今日風險</div>
        <div style="font-size:12px;line-height:1.7;color:var(--text)">{ai_risks_text}</div>
      </div>
    </div>
    <div style="margin-top:8px;padding:6px 8px;background:rgba(245,185,66,0.08);border-radius:6px;border-left:3px solid var(--gold)">
      <div style="font-size:11px;color:var(--gold)">⚡ 今日最佳策略</div>
      <div style="font-size:12px;color:var(--text);margin-top:3px">{ai_best_strategy}</div>
    </div>
  </div>

  <div class="sec-hdr">大盤指標</div>
  <div class="stats">
    <div class="stat">
      <div class="k">加權指數 {trading_date}</div>
      <div class="v {taiex_css}">{taiex_close}</div>
      <div class="d {taiex_css}">{taiex_change}（{taiex_change_pct}）</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.twse.com.tw/zh/trading/indices/MI_5MINS_HIST.html" target="_blank" style="color:var(--acc);font-size:10px">📎 TWSE 官網</a></div>
    </div>
    <div class="stat">
      <div class="k">今日預估開盤</div>
      <div class="v gold">{open_lo}</div>
      <div class="d gold">~{open_hi} 區間</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.taifex.com.tw/cht/5/afterHoursFutures" target="_blank" style="color:var(--acc);font-size:10px">📎 期交所夜盤</a></div>
    </div>
    <div class="stat">
      <div class="k">成交量</div>
      <div class="v acc">{volume} 兆</div>
      <div class="d sub">{volume_desc}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.twse.com.tw/zh/trading/indices/MI_5MINS_HIST.html" target="_blank" style="color:var(--acc);font-size:10px">📎 TWSE 官網</a></div>
    </div>
    <div class="stat">
      <div class="k">台幣匯率</div>
      <div class="v {fx_css}">{twd}</div>
      <div class="d {fx_css}">{fx_desc}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://rate.bot.com.tw/xrt" target="_blank" style="color:var(--acc);font-size:10px">📎 台銀匯率</a></div>
    </div>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="k">台積電 ADR</div>
      <div class="v {adr_css}">{adr_close}</div>
      <div class="d {adr_css}">{adr_pct} {"⚠️" if adr_css=="dn" else "✅"}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://finance.yahoo.com/quote/TSM/" target="_blank" style="color:var(--acc);font-size:10px">📎 Yahoo Finance</a></div>
    </div>
    <div class="stat">
      <div class="k">台指期夜盤</div>
      <div class="v">{night_fut}</div>
      <div class="d sub">⚠️ 請以即時盤確認</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.taifex.com.tw/cht/5/afterHoursFutures" target="_blank" style="color:var(--acc);font-size:10px">📎 期交所查詢</a></div>
    </div>
    <div class="stat">
      <div class="k">關鍵支撐</div>
      <div class="v dn">{support}</div>
      <div class="d sub">跌破轉空</div>
      <div class="d sub" style="margin-top:4px"><a href="https://tw.tradingview.com/chart/?symbol=TWSE%3ATAIEX" target="_blank" style="color:var(--acc);font-size:10px">📎 TradingView</a></div>
    </div>
    <div class="stat">
      <div class="k">前高壓力</div>
      <div class="v">{resist}</div>
      <div class="d sub">突破目標</div>
      <div class="d sub" style="margin-top:4px"><a href="https://tw.tradingview.com/chart/?symbol=TWSE%3ATAIEX" target="_blank" style="color:var(--acc);font-size:10px">📎 TradingView</a></div>
    </div>
  </div>

  <div class="chart-wrap">
    <canvas id="taixChart"></canvas>
    <div class="chart-cap">近期加權指數收盤走勢 ‧ <a href="https://www.twse.com.tw/zh/trading/indices/MI_5MINS_HIST.html" target="_blank" style="color:var(--acc)">📎 TWSE</a></div>
  </div>

  <div class="sec-hdr">美股連動</div>
  <div class="card">
    <table class="tbl">
      <tr><th>指數</th><th>{trading_date}</th><th>方向</th><th style="font-size:10px">來源</th></tr>
      {global_rows}
    </table>
  </div>

  <div class="ai">
    <div class="ai-tag">✦ AI 解讀</div>
    {taiex_ai}
  </div>

</div>

<!-- ② 法人 -->
<div class="page hidden" id="page-1">

  <div class="sec-hdr">三大法人（{trading_date}）</div>
  <div class="stats">
    <div class="stat">
      <div class="k">外資</div>
      <div class="v {foreign_css}">{foreign_net}億</div>
      <div class="d sub">個股排名第1：{foreign_top1}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.twse.com.tw/zh/trading/foreign/twt38u.html" target="_blank" style="color:var(--acc);font-size:10px">📎 TWSE 外資買賣超</a></div>
    </div>
    <div class="stat">
      <div class="k">投信</div>
      <div class="v {trust_css}">{trust_net}億</div>
      <div class="d sub">{trust_desc_txt}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.twse.com.tw/zh/trading/trust/twt43u.html" target="_blank" style="color:var(--acc);font-size:10px">📎 TWSE 投信買賣超</a></div>
    </div>
    <div class="stat">
      <div class="k">自營商</div>
      <div class="v {dealer_css}">{dealer_net}億</div>
      <div class="d sub">{dealer_desc_txt}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.twse.com.tw/zh/trading/dealers/twt44u.html" target="_blank" style="color:var(--acc);font-size:10px">📎 TWSE 自營商買賣超</a></div>
    </div>
    <div class="stat">
      <div class="k">三大合計</div>
      <div class="v {total_css}">{total_net}億</div>
      <div class="d sub">{total_desc_txt}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://goodinfo.tw/tw/StockBuySaleList.asp?RPT_CAT=BF&CHT_CAT2=DATE" target="_blank" style="color:var(--acc);font-size:10px">📎 Goodinfo 法人</a></div>
    </div>
  </div>

  <div class="chart-wrap">
    <canvas id="instChart"></canvas>
    <div class="chart-cap">{trading_date} 三大法人買超金額（億）</div>
  </div>

  <div class="sec-hdr">外資個股排名（{trading_date}）</div>
  <div class="card">
    <table class="tbl">
      <tr><th>排名</th><th>股票</th><th>方向</th></tr>
      {top3_rows}
    </table>
    <p style="font-size:11px;color:var(--sub);margin-top:8px">精確張數→ <a href="https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID=2330&CHT_CAT=DATE" target="_blank" style="color:var(--acc)">Goodinfo.tw</a></p>
  </div>

  <div class="sec-hdr">融資融券</div>
  <div class="stats">
    <div class="stat">
      <div class="k">融資餘額變化</div>
      <div class="v {margin_css}">{margin_change} 億</div>
      <div class="d sub">{margin_desc_txt}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.twse.com.tw/zh/trading/margin/MI_MARGN.html" target="_blank" style="color:var(--acc);font-size:10px">📎 TWSE 融資融券</a></div>
    </div>
    <div class="stat">
      <div class="k">融券餘額</div>
      <div class="v">{short_bal}張</div>
      <div class="d sub">券資比 {short_ratio}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://www.twse.com.tw/zh/trading/margin/MI_MARGN.html" target="_blank" style="color:var(--acc);font-size:10px">📎 TWSE 融資融券</a></div>
    </div>
  </div>

  <div class="ai">
    <div class="ai-tag">✦ 融資融券 AI 解讀</div>
    {margin_ai}
  </div>

  <div class="sec-hdr">匯率 & 期選</div>
  <div class="stats">
    <div class="stat">
      <div class="k">新台幣 {trading_date}</div>
      <div class="v {fx_css}">{twd}</div>
      <div class="d {fx_css}">{fx_desc}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://rate.bot.com.tw/xrt" target="_blank" style="color:var(--acc);font-size:10px">📎 台銀牌告匯率</a></div>
    </div>
    <div class="stat">
      <div class="k">台指 Put/Call 比</div>
      <div class="v {pc_css_val}">{pc_val}</div>
      <div class="d sub">{pc_desc}</div>
      <div class="d sub" style="margin-top:4px"><a href="https://openapi.taifex.com.tw/v1/PutCallRatio" target="_blank" style="color:var(--acc);font-size:10px">📎 期交所 P/C 比</a></div>
    </div>
  </div>

  <div class="ai">
    <div class="ai-tag">✦ 匯率 AI 解讀</div>
    {fx_ai}
  </div>

  <div class="sec-hdr">📅 重要財報 & 法說會行事曆</div>
  <div class="card">
    <table class="tbl">
      <tr><th style="width:60px">日期</th><th>公司</th><th style="width:70px">類型</th><th style="width:70px">重要度</th></tr>
      {cal_rows}
    </table>
    <div class="ai" style="margin-top:8px">
      <div class="ai-tag">✦ AI 行事曆解讀</div>
      {earnings_ai}
    </div>
    <p style="font-size:11px;color:var(--sub);margin-top:6px">⚠️ 行事曆以 AI 預估為基準，正式日期請至 <a href="https://mops.twse.com.tw/mops/web/t05st29_1" target="_blank" style="color:var(--acc)">公開資訊觀測站</a> 確認</p>
  </div>

  <div class="sec-hdr">📰 今日國際財經新聞</div>
  <div class="card">
    {yahoo_news_html}
    <p style="font-size:11px;color:var(--sub);margin-top:6px">來源：<a href="https://tw.news.yahoo.com/rss/finance" target="_blank" style="color:var(--acc)">Yahoo 財經 RSS</a></p>
  </div>

  <div class="sec-hdr">🔧 科技產業新聞</div>
  <div class="card">
    {digitimes_html}
    <p style="font-size:11px;color:var(--sub);margin-top:6px">來源：<a href="https://www.digitimes.com.tw/tech/rss.xml" target="_blank" style="color:var(--acc)">DigiTimes RSS</a></p>
  </div>

  <div class="sec-hdr">🗓️ 美國總經事件（未來14天）</div>
  <div class="card">
    <table class="tbl">
      <tr><th>日期</th><th>事件</th><th>重要度</th></tr>
      {fred_rows}
    </table>
    <p style="font-size:11px;color:var(--sub);margin-top:6px">來源：<a href="https://fred.stlouisfed.org/releases" target="_blank" style="color:var(--acc)">FRED API（美聯準官方）</a></p>
  </div>

</div>

<!-- ③ 個股 -->
<div class="page hidden" id="page-2">

{card_2330}

{card_2454}

{card_2327}

  <div class="sec-hdr">今日精選強勢股</div>
  <div class="card" style="padding:8px 12px;margin-bottom:10px;background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.2)">
    <div style="font-size:12px;color:var(--ai)">🤖 AI 選股理由</div>
    <div style="font-size:12px;color:var(--txt);margin-top:4px;line-height:1.7">{top_stocks_reason}</div>
  </div>

{top_stocks_html}

</div>

<!-- ④ 操盤 -->
<div class="page hidden" id="page-3">

  <div class="sec-hdr">今日操盤方向</div>
  <div class="card">
    <div class="stats">
      <div class="stat">
        <div class="k">今日方向</div>
        <div class="v gold">{market_direction}</div>
        <div class="d sub">{dir_icon} AI 判斷</div>
      </div>
      <div class="stat">
        <div class="k">開盤區間</div>
        <div class="v acc">{open_lo}</div>
        <div class="d sub">~{open_hi}</div>
      </div>
    </div>
  </div>

  <div class="sec-hdr">核心操盤策略</div>
  <div class="opbox">
    <div class="op-dir">今日策略：<span class="gold">{ai_best_strategy[:30] if len(ai_best_strategy)>30 else ai_best_strategy}</span></div>
    <div style="font-size:13.5px;margin-top:8px;line-height:1.8">
      {strategy_ai}
    </div>
  </div>

  <div class="sec-hdr">開盤前確認清單</div>
  <div class="card">
    <ul class="check-list">
      <li><span class="icon">📱</span><div><strong>TSM ADR 最新價</strong><div class="sub" style="font-size:12px">確認 {adr_pct} 是否有後市調整 → <a href="https://finance.yahoo.com/quote/TSM/" target="_blank" style="color:var(--acc)">Yahoo Finance</a></div></div></li>
      <li><span class="icon">📊</span><div><strong>台指期夜盤最新點位</strong><div class="sub" style="font-size:12px">券商 APP 查詢最新夜盤 → 參考點位 {night_fut}</div></div></li>
      <li><span class="icon">💱</span><div><strong>台幣開盤匯率</strong><div class="sub" style="font-size:12px">是否異常貶值？→ <a href="https://tw.stock.yahoo.com/exchange-rate" target="_blank" style="color:var(--acc)">Yahoo 匯率</a></div></div></li>
      <li><span class="icon">🏛️</span><div><strong>Put/Call 比率</strong><div class="sub" style="font-size:12px">低於 0.8 偏多，高於 1.2 偏空 → <a href="https://openapi.taifex.com.tw/v1/PutCallRatio" target="_blank" style="color:var(--acc)">期交所查詢</a>（當前：{pc_val}）</div></div></li>
      <li><span class="icon">💹</span><div><strong>外資現貨買超金額</strong><div class="sub" style="font-size:12px">今日是否繼續買超 100 億以上？→ <a href="https://www.twse.com.tw/zh/trading/foreign/twt38u.html" target="_blank" style="color:var(--acc)">TWSE</a></div></div></li>
      <li><span class="icon">🌐</span><div><strong>費城半導體 SOX</strong><div class="sub" style="font-size:12px">昨晚 SOX 走勢（當前：{d.get("sox_change","⚠️ 待查")}）→ <a href="https://finance.yahoo.com/quote/%5ESOX/" target="_blank" style="color:var(--acc)">Yahoo SOX</a></div></div></li>
    </ul>
  </div>

  <div class="sec-hdr">📖 新手術語速查</div>
  <button class="collapse-btn" onclick="toggleCollapse(this)" style="margin-bottom:0">
    點此展開術語說明 <span class="arrow">▼</span>
  </button>
  <div class="collapse-content">
    <div class="card" style="margin-top:8px;font-size:13px;line-height:1.9">
      <div style="margin-bottom:10px"><strong class="acc">ADR（美國存託憑證）</strong><br><span class="sub">台積電在美國掛牌的憑證（代號 TSM），美股收盤後可看出台股次日開盤方向。ADR -3% ≈ 台積電次日開盤約 -80~100 元。</span></div>
      <div style="margin-bottom:10px"><strong class="acc">三大法人</strong><br><span class="sub">外資（外國機構）＋投信（基金公司）＋自營商（券商自有資金）。三大合買越多，代表法人對後市越樂觀。</span></div>
      <div style="margin-bottom:10px"><strong class="acc">融資 / 融券</strong><br><span class="sub">融資 = 借錢買股（看多）；融券 = 借股票賣出（放空）。融資增加表示散戶追高，過多時是警訊；融資減少反而健康。</span></div>
      <div style="margin-bottom:10px"><strong class="acc">Put/Call 比率（P/C 比）</strong><br><span class="sub">期貨選擇權買賣比例。P/C &lt; 0.8 表示市場偏多（買Call居多）；P/C &gt; 1.2 表示市場偏空（買Put居多）。</span></div>
      <div style="margin-bottom:10px"><strong class="acc">RSI（相對強弱指標）</strong><br><span class="sub">0–100，通常 &gt; 70 為超買（短線可能回調），&lt; 30 為超賣（短線可能反彈）。</span></div>
      <div style="margin-bottom:10px"><strong class="acc">夜盤（台指期夜盤）</strong><br><span class="sub">台灣期貨交易所在一般交易時段結束後（15:00–05:00）提供的台指期交易。夜盤與美股同步，可預測次日開盤。</span></div>
      <div><strong class="acc">法說會（法人說明會）</strong><br><span class="sub">公司對機構法人說明財務業績的會議。法說後若業績超預期，股價易大漲。</span></div>
    </div>
  </div>

  <div class="sec-hdr">📚 進階術語速查</div>
  <button class="collapse-btn" onclick="toggleCollapse(this)" style="width:100%;margin-bottom:0;border-radius:10px 10px 0 0">
    點此展開進階術語 <span class="arrow">▼</span>
  </button>
  <div class="collapse-content" style="background:var(--card);border-radius:0 0 10px 10px;padding:0 12px;margin-bottom:12px">
    <div style="padding:10px 0">
      <div style="margin-bottom:10px"><div style="font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px">🔷 台指期未平倉量（OI）</div><div style="font-size:12px;color:var(--text);line-height:1.6">OI 放大＋價格上漲 = 多方進場積極；OI 縮小 = 主力平倉觀望。<a href="https://www.taifex.com.tw/cht/3/futQryTxnoOpenInterest" target="_blank" style="color:var(--acc)">📎 期交所 OI</a></div></div>
      <div style="margin-bottom:10px"><div style="font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px">🔷 大額交易人淨部位</div><div style="font-size:12px;color:var(--text);line-height:1.6">期交所每日公佈前5大、前10大交易人多空淨部位。外資期貨多單 &gt; 空單 = 主力看多。</div></div>
      <div style="margin-bottom:10px"><div style="font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px">🔷 均線多空排列（MA5/MA20/MA60）</div><div style="font-size:12px;color:var(--text);line-height:1.6">MA5 &gt; MA20 &gt; MA60 = 多頭排列。MA5 跌穿 MA20 為「死亡交叉」，是轉弱訊號。</div></div>
      <div style="margin-bottom:10px"><div style="font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px">🔷 量縮/量增的判讀</div><div style="font-size:12px;color:var(--text);line-height:1.6">量增價漲 = 最健康；量縮價漲 = 漲勢缺動能；量增價跌 = 賣壓沉重；量縮價跌 = 跌勢尾聲。</div></div>
      <div style="margin-bottom:10px"><div style="font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px">🔷 VIX 恐慌指數</div><div style="font-size:12px;color:var(--text);line-height:1.6">VIX &gt; 30 = 市場極度恐慌（反而是買點）；VIX &lt; 15 = 過度樂觀（要小心反轉）。當前 VIX：{d.get("vix","⚠️")}</div></div>
      <div style="margin-bottom:10px"><div style="font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px">🔷 斷頭賣壓（Margin Call）</div><div style="font-size:12px;color:var(--text);line-height:1.6">融資戶股票下跌觸及維持率下限（通常 130%），券商強制賣出，造成集中賣壓。</div></div>
      <div style="margin-bottom:10px"><div style="font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px">🔷 NDF（無本金遠期外匯）</div><div style="font-size:12px;color:var(--text);line-height:1.6">外資押注台幣走勢的工具。NDF 顯示外資對台幣走貶預期越強，代表未來外資流出壓力越大。</div></div>
      <div style="margin-bottom:4px"><div style="font-size:12px;font-weight:700;color:var(--acc);margin-bottom:2px">🔷 費城半導體指數（SOX）</div><div style="font-size:12px;color:var(--text);line-height:1.6">30支主要半導體股組成，與台積電/聯發科相關性 &gt;0.85。盤前必查。<a href="https://finance.yahoo.com/quote/%5ESOX/" target="_blank" style="color:var(--acc)">📎 Yahoo SOX</a></div></div>
    </div>
  </div>

  <div class="sec-hdr">📊 市場狀態說明</div>
  <button class="collapse-btn" onclick="toggleCollapse(this)" style="width:100%;margin-bottom:0;border-radius:10px 10px 0 0">
    點此展開市場狀態圖解 <span class="arrow">▼</span>
  </button>
  <div class="collapse-content" style="background:var(--card);border-radius:0 0 10px 10px;padding:0 12px;margin-bottom:12px">
    <div style="padding:10px 0">
      <div style="margin-bottom:12px;padding:8px;background:rgba(16,185,129,0.1);border-radius:8px;border-left:3px solid var(--dn)">
        <div style="font-size:13px;font-weight:700;color:var(--dn)">💹 強勢做多</div>
        <div style="font-size:12px;color:var(--text);line-height:1.6;margin-top:3px">三大法人大買超 + 外資連續買超 + 大盤突破前高 + ADR 強勁上漲。可積極佈局，追高有理由。</div>
      </div>
      <div style="margin-bottom:12px;padding:8px;background:rgba(16,185,129,0.07);border-radius:8px;border-left:3px solid var(--dn)">
        <div style="font-size:13px;font-weight:700;color:var(--dn)">📈 偏多</div>
        <div style="font-size:12px;color:var(--text);line-height:1.6;margin-top:3px">外資買超為主 + 大盤在均線之上 + ADR 微漲或持平。適合持有多單，逢回不追空。</div>
      </div>
      <div style="margin-bottom:12px;padding:8px;background:rgba(245,185,66,0.08);border-radius:8px;border-left:3px solid var(--gold)">
        <div style="font-size:13px;font-weight:700;color:var(--gold)">📊 中性偏多</div>
        <div style="font-size:12px;color:var(--text);line-height:1.6;margin-top:3px">多空信號混雜，但偏向看多。可持有，降低倉位，等待確認信號後再加碼。</div>
      </div>
      <div style="margin-bottom:12px;padding:8px;background:rgba(255,255,255,0.04);border-radius:8px;border-left:3px solid var(--sub)">
        <div style="font-size:13px;font-weight:700;color:var(--sub)">⚖️ 中性</div>
        <div style="font-size:12px;color:var(--text);line-height:1.6;margin-top:3px">多空力道相當，無明確方向。建議觀望或輕倉，等待盤面給出明確訊號。</div>
      </div>
      <div style="margin-bottom:12px;padding:8px;background:rgba(245,185,66,0.08);border-radius:8px;border-left:3px solid var(--gold)">
        <div style="font-size:13px;font-weight:700;color:var(--gold)">⚠️ 中性偏空</div>
        <div style="font-size:12px;color:var(--text);line-height:1.6;margin-top:3px">有利空因素（如 ADR 下跌、外資賣超），但護盤力道尚存。降低倉位，設好停損，不追多。</div>
      </div>
      <div style="margin-bottom:12px;padding:8px;background:rgba(239,68,68,0.07);border-radius:8px;border-left:3px solid var(--up)">
        <div style="font-size:13px;font-weight:700;color:var(--up)">⚠️ 偏空</div>
        <div style="font-size:12px;color:var(--text);line-height:1.6;margin-top:3px">外資轉賣超 + 大盤跌破重要支撐 + ADR 明顯下跌。宜減碼或觀望，避免逆勢操作。</div>
      </div>
      <div style="padding:8px;background:rgba(239,68,68,0.12);border-radius:8px;border-left:3px solid var(--up)">
        <div style="font-size:13px;font-weight:700;color:var(--up)">🔻 強勢做空</div>
        <div style="font-size:12px;color:var(--text);line-height:1.6;margin-top:3px">三大法人大賣超 + 外資連續大賣 + 大盤跌破月線 + 恐慌氣氛濃厚。嚴格執行停損，保留現金。</div>
      </div>
    </div>
  </div>

  <div class="sec-hdr">🤖 AI 全文總結與提醒</div>
  <div class="card" style="border:1px solid rgba(99,102,241,0.3)">
    <div class="ai-tag" style="margin-bottom:10px">✦ {today_short} 盤前完整解讀（更新次數：{reanalysis_count}）</div>
    <div style="font-size:12px;line-height:1.8;color:var(--text)">
      {full_ai if full_ai else macro_ai}
    </div>
    <div style="margin-top:8px;padding:6px 8px;background:rgba(239,68,68,0.07);border-radius:6px;border-left:3px solid #ef4444">
      <div style="font-size:11px;color:#ef4444;font-weight:700">🔔 今日最強產業：{today_strongest} ‧ 最大風險標的：{today_biggest_risk}</div>
      <div style="font-size:12px;color:var(--text);margin-top:3px">⚠️ 本報告每日 {update_time}（台灣時間）自動更新。所有數字標示來源，「⚠️」欄位請自行以官方來源覆核後再操作。</div>
    </div>
  </div>

  <div class="sec-hdr">⚠️ 今日風控</div>
  <div class="alert">
    <div class="alert-title">設好停損，不賭單一方向</div>
    <div style="font-size:13.5px;line-height:1.8">
      {risk_ai}
      <br>• 台積電跌破 <strong>{stop_loss_tsmc}</strong> 停損出場<br>
      • TAIEX 跌破 <strong>{stop_loss_taiex}</strong> 減碼觀望<br>
      • 避免在開盤前 15 分鐘追價
    </div>
  </div>

  <div class="sec-hdr">免責聲明</div>
  <div class="card" style="font-size:12px;color:var(--sub)">
    本報告為 AI 自動彙整（更新時間：{update_time} 台灣時間），僅供參考，<strong>非投資建議</strong>。
    所有數字均標示來源，「⚠️ 待即時查證」欄位請自行以官方來源覆核後再進行操作決策。投資有風險，請審慎評估。
  </div>

</div>
<!-- ⑤ 產業趨勢 -->
<div class="page hidden" id="page-4">

  <div class="sec-hdr">🏭 產業趨勢追蹤 — {today_short}</div>

  <div class="card" style="padding:8px 10px;margin-bottom:6px">
    <div style="font-size:11px;color:var(--sub);line-height:1.6">
      趨勢判斷：
      <span class="dn" style="background:rgba(16,185,129,0.15);padding:1px 6px;border-radius:4px;font-size:11px">強勢</span>
      <span class="gold" style="background:rgba(245,185,66,0.12);padding:1px 6px;border-radius:4px;font-size:11px;margin-left:4px">偏多</span>
      <span style="color:var(--sub);background:rgba(255,255,255,0.05);padding:1px 6px;border-radius:4px;font-size:11px;margin-left:4px">中性</span>
      <span class="up" style="background:rgba(239,68,68,0.1);padding:1px 6px;border-radius:4px;font-size:11px;margin-left:4px">偏空</span>
    </div>
  </div>

  {sector_html}

  <div class="ai">
    <div class="ai-tag">✦ 產業 AI 總結</div>
    今日最強產業：<strong class="dn">{today_strongest}</strong><br>
    {sector_trend_ai}
  </div>

</div>

<!-- ⑥ 復盤 -->
<div class="page hidden" id="page-5">

  <div class="sec-hdr">📝 前一份預報復盤報告</div>

  <div class="card" style="background:rgba(245,185,66,0.06);border:1px solid rgba(245,185,66,0.2);margin-bottom:12px">
    <div style="font-size:13px;font-weight:700;color:var(--gold);margin-bottom:6px">📋 復盤對象：{review_date} 盤前報告</div>
    <div style="font-size:12px;color:var(--text);line-height:1.7">
      本欄位記錄每日收盤後，對照「盤前預測 vs. 盤後實際結果」的復盤分析。通過逐項比對，持續校正 AI 判斷準確度。
    </div>
  </div>

  <div class="sec-hdr" style="font-size:13px">一、大盤預測 vs. 實際</div>
  <div class="card">
    <table class="tbl">
      <tr><th>項目</th><th>{review_date} 盤前預測</th><th>實際結果</th><th>準確度</th></tr>
      {market_rows}
    </table>
  </div>

  <div class="sec-hdr" style="font-size:13px">二、個股建議 vs. 實際</div>
  <div class="card">
    <table class="tbl">
      <tr><th>股票</th><th>盤前建議</th><th>{review_date} 實際</th><th>評估</th></tr>
      {stock_review_rows}
    </table>
    <p style="font-size:11px;color:var(--sub);margin-top:8px">📌 「⚠️ 待補充」欄位請收盤後手動填入 Google Sheets，即可在此看到復盤</p>
  </div>

  <div class="sec-hdr" style="font-size:13px">三、AI 自我校正</div>
  <div class="card">
    <div class="ai" style="margin-bottom:0">
      <div class="ai-tag">✦ {review_date} 復盤 AI 解讀</div>
      {review_ai}
    </div>
  </div>

  <div class="sec-hdr" style="font-size:13px">四、今日操作記錄（請手動填寫）</div>
  <div class="card" style="background:rgba(255,255,255,0.03)">
    <div style="font-size:12px;color:var(--sub);line-height:2">
      📝 今日買入：___________________________<br>
      📝 今日賣出：___________________________<br>
      📝 今日盈虧：___________________________<br>
      📝 外資現貨買超：________________________億<br>
      📝 大盤收盤：____________________________<br>
      📝 今日心得：___________________________
    </div>
    <div style="margin-top:10px;font-size:11px;color:var(--sub)">* 建議截圖或複製至 Google Sheets 每日更新，系統將自動納入明日 AI 分析</div>
  </div>

</div>
</div><!-- /pages -->
</div><!-- /pages-wrap -->

<!-- Bottom Nav -->
<nav class="bnav">
  <button class="bnav-btn active" id="nav-0" onclick="switchPage(0)"><span class="bnav-icon">📈</span><span class="bnav-label">大盤</span></button>
  <button class="bnav-btn" id="nav-1" onclick="switchPage(1)"><span class="bnav-icon">🏛️</span><span class="bnav-label">法人</span></button>
  <button class="bnav-btn" id="nav-2" onclick="switchPage(2)"><span class="bnav-icon">📋</span><span class="bnav-label">個股</span></button>
  <button class="bnav-btn" id="nav-3" onclick="switchPage(3)"><span class="bnav-icon">⚡</span><span class="bnav-label">操盤</span></button>
  <button class="bnav-btn" id="nav-4" onclick="switchPage(4)"><span class="bnav-icon">🏭</span><span class="bnav-label">產業</span></button>
  <button class="bnav-btn" id="nav-5" onclick="switchPage(5)"><span class="bnav-icon">📝</span><span class="bnav-label">復盤</span></button>
</nav>

<script>
let currentPage = 0;
function switchPage(idx) {{
  document.getElementById('page-' + currentPage).classList.add('hidden');
  document.getElementById('nav-' + currentPage).classList.remove('active');
  currentPage = idx;
  document.getElementById('page-' + idx).classList.remove('hidden');
  document.getElementById('nav-' + idx).classList.add('active');
  document.getElementById('page-' + idx).scrollTop = 0;
}}
function toggleCollapse(btn) {{
  btn.classList.toggle('open');
  btn.nextElementSibling.classList.toggle('show');
}}
const chartDefaults = {{
  plugins: {{ legend: {{ display: false }}, tooltip: {{ backgroundColor: '#1a2129', titleColor: '#9fb0c0', bodyColor: '#e6edf3', borderColor: '#2c3947', borderWidth: 1 }} }},
  scales: {{ x: {{ grid: {{ color: '#2c3947' }}, ticks: {{ color: '#9fb0c0', font: {{ size: 10 }}, maxRotation: 45 }} }},
            y: {{ grid: {{ color: '#2c3947' }}, ticks: {{ color: '#9fb0c0', font: {{ size: 10 }} }} }} }}
}};
const taixLabels = {chart_labels_js};
const taixData   = {chart_data_js};
new Chart(document.getElementById('taixChart'), {{
  type: 'line',
  data: {{ labels: taixLabels, datasets: [{{ data: taixData, borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.08)', borderWidth: 2, pointRadius: 2.5, pointBackgroundColor: '#38bdf8', tension: 0.3, fill: true }}] }},
  options: {{ ...chartDefaults, responsive: true, maintainAspectRatio: true }}
}});
new Chart(document.getElementById('instChart'), {{
  type: 'bar',
  data: {{ labels: ['外資', '投信', '自營商'], datasets: [{{ data: {inst_data_js}, backgroundColor: ['rgba(239,68,68,0.7)','rgba(56,189,248,0.7)','rgba(245,185,66,0.7)'], borderColor: ['#ef4444','#38bdf8','#f5b942'], borderWidth: 1.5, borderRadius: 6 }}] }},
  options: {{ ...chartDefaults, responsive: true, maintainAspectRatio: true, indexAxis: 'y',
    scales: {{ x: {{ grid: {{ color: '#2c3947' }}, ticks: {{ color: '#9fb0c0', font: {{ size: 10 }} }} }}, y: {{ grid: {{ display: false }}, ticks: {{ color: '#e6edf3', font: {{ size: 13, weight: '600' }} }} }} }} }}
}});
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True) if os.path.dirname(output_path) else None
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ render_html: wrote {len(html):,} bytes → {output_path}")
    return output_path


if __name__ == "__main__":
    # Test with minimal sample data
    sample = {
        "today": "2026/07/03", "today_short": "07/03", "trading_date": "07/02",
        "market_direction": "中性偏空", "biggest_risk": "TSM ADR -3.51% 壓制開盤",
        "taiex_close": "47,018", "taiex_change": "+893", "taiex_change_pct": "+1.94%", "taiex_css": "dn",
        "open_range_low": "46,500", "open_range_high": "46,900",
        "volume_trillion": "1.32", "volume_desc": "量能充沛",
        "twd_usd": "31.909", "fx_change_pct": "-0.36%", "fx_change_desc": "貶值 -0.36%", "fx_css": "up",
        "tsm_adr_close": "$446.68", "tsm_adr_change_pct": "-3.51%", "tsm_adr_css": "up",
        "night_futures_last": "47,234", "key_support": "46,500", "key_resistance": "47,742",
        "taiex_ai": "外資護盤力道強，46,500 為多空關鍵，守住則格局不破。",
        "strategy_ai": "等待落底，外資今日若繼續買超 100 億，可逢低分批。",
        "ai_best_strategy": "開盤觀望 15 分鐘→確認台積電低點→外資買超才進場",
        "ai_opportunities": "① 台積電 2,400 分批\n② 國巨抗跌\n③ AI 硬體跌深反彈",
        "ai_risks_text": "① 台積電跌破 2,350\n② 大盤跌破 46,500\n③ 外資翻賣超",
        "foreign_net_yi": "+323.76", "foreign_css": "dn", "foreign_top1": "台積電",
        "trust_net_yi": "+156.03", "trust_css": "dn", "trust_desc": "積極加碼",
        "dealer_net_yi": "+59.38", "dealer_css": "dn", "dealer_desc": "同步買超",
        "total_net_yi": "+539.17", "total_css": "dn", "total_desc": "近期高水位",
        "foreign_top3": [{"rank":"🥇 第1","name":"台積電 2330","css":"up"},{"rank":"🥈 第2","name":"國巨 2327","css":"up"},{"rank":"🥉 第3","name":"聯電 2303","css":"up"}],
        "margin_change_yi": "-21.5", "margin_change_css": "dn", "margin_change_desc": "散戶去槓桿（健康）",
        "short_balance": "196,392", "short_ratio_pct": "2.09%",
        "margin_ai": "融資減少為健康現象，散戶未過度槓桿。",
        "fx_ai": "台幣貶值對出口股有利，關注外資是否持續買超。",
        "nasdaq_change": "+1.52%", "nasdaq_css": "dn", "nasdaq_desc": "↑ 表面樂觀",
        "dji_change": "+0.12%", "dji_css": "dn", "dji_desc": "↑ 溫和",
        "sox_change": "-0.5%", "sox_css": "up", "sox_desc": "⚠️ 半導體承壓",
        "vix": "15.2", "vix_css": "dn", "vix_desc": "↓ 市場平靜",
        "gold_change": "+0.3%", "gold_css": "dn", "gold_desc": "↑ 避險需求",
        "brent_change": "-1.1%", "brent_css": "up", "brent_desc": "↓ 油價走弱",
        "stock_2330": {"name":"台積電","close":"2,520","change_pct":"+1.00%","change_css":"dn","adr_close":"$446.68","adr_change_pct":"-3.51%","adr_css":"up","foreign_rank":"🥇 金額第1","foreign_css":"up","foreign_desc":"買超","rsi":"75.57","rsi_css":"gold","rsi_desc":"短線超買","extra_label":"外資目標價","extra_css":"acc","extra_value":"$487","extra_desc":"ADR共識","direction":"觀望/逢低佈局","direction_css":"gold","buy_range":"2,400~2,430","stop_loss":"2,350","target":"2,700+","op4_label":"法說會","op4_value":"7/16","ai_insight":"ADR -3.51% 若完全反映，單日約 -80~100 元。RSI 75 超買，7/16 法說會前維持觀察。","news":[{"title":"TSM ADR 重挫","url":"https://finance.yahoo.com/quote/TSM/","source":"Yahoo","date":"07/02"}]},
        "stock_2454": {"name":"聯發科","close":"1,250","change_pct":"+0.5%","change_css":"dn","trend_text":"↑ 強勢","trend_css":"dn","foreign_rank":"持續買超","foreign_css":"dn","foreign_desc":"AI PC 旺季","rsi":"62","rsi_css":"gold","rsi_desc":"偏強","direction":"積極偏多","direction_css":"dn","buy_range":"1,220~1,240","stop_loss":"1,180","target":"1,400","op4_label":"H2旺季","op4_value":"AI晶片出貨","ai_insight":"聯發科受惠 AI PC 雙引擎，H2 旺季出貨。","news":[]},
        "stock_2327": {"name":"國巨","close":"880","change_pct":"+0.8%","change_css":"dn","trend_text":"偏多","trend_css":"dn","foreign_rank":"🥈 金額第2","foreign_css":"dn","foreign_desc":"連續買超","rsi":"58","rsi_css":"gold","rsi_desc":"強勢","direction":"偏多關注","direction_css":"dn","buy_range":"860~870","stop_loss":"840","target":"960","op4_label":"外資連動","op4_value":"ADR留意","ai_insight":"外資連續買超，被動元件 AI 需求長線明確。","news":[]},
        "top_stocks": [{"code":"2382","name":"廣達","desc":"AI 伺服器組裝龍頭","close":"280","change_pct":"+1.5%","change_css":"dn","direction":"積極做多","direction_css":"dn","foreign_rank":"買超","foreign_css":"dn","foreign_desc":"外資持續","rsi":"68","rsi_css":"gold","rsi_desc":"偏強","theme":"GB200 出貨","theme_desc":"NVIDIA 超算","buy_range":"270~275","stop_loss":"260","target":"310","selection_reason":"外資買超+AI旺季","ai_insight":"廣達是 NVIDIA GB200 最大組裝廠，跌深反而是中線介入機會。","news":[]}],
        "top_stocks_reason": "AI 依據外資買超強度、RSI 動能、產業題材，選出今日最強勢股。",
        "full_ai_text": "今日台股面臨台積電 ADR -3.51% 施壓，但三大法人昨日合買 539 億奠定護盤底氣。預估開盤後 46,500 是多空分水嶺，外資若持續買超則下跌有限，午後有機會回穩。",
        "macro_ai": "全球總經面相對平靜，VIX 15.2 處低位，市場無系統性風險。美聯準政策不確定性是中期隱憂。",
        "risk_ai": "最大風險：台積電 ADR 若後市再跌，開盤跌幅恐擴大。外資若翻賣超，大盤轉為偏空格局。",
        "today_strongest_sector": "AI 伺服器 / ODM",
        "today_biggest_risk_stock": "台積電（ADR 壓力）",
        "reanalysis_count": 0, "update_time": "06:30",
        "stop_loss_tsmc": "2,350", "stop_loss_taiex": "46,500",
        "sectors": [
            {"num":"①","name":"半導體製造","reps":"台積電(2330)・聯電(2303)・世界先進(5347)","trend":"中性偏空→逢低多","trend_css":"gold","trend_bg":"rgba(245,185,66,0.12)","desc":"台積電 ADR -3.51% 直接施壓，預估開盤 -2~3%。外資護盤意願強，跌幅有限。","week_outlook":"法說前保守","week_css":"gold","week_bg":"rgba(239,68,68,0.08)","month_outlook":"法說後看強","month_css":"dn","month_bg":"rgba(16,185,129,0.08)","key_event":"7/16 法說會"},
            {"num":"②","name":"IC 設計","reps":"聯發科(2454)・瑞昱(2379)・聯詠(3034)","trend":"偏多","trend_css":"dn","trend_bg":"rgba(16,185,129,0.12)","desc":"AI PC / AI 手機 H2 旺季支撐，相對抗跌。","week_outlook":"AI PC 旺季","week_css":"dn","week_bg":"rgba(16,185,129,0.08)","month_outlook":"H2 出貨強勁","month_css":"dn","month_bg":"rgba(16,185,129,0.08)","key_event":"7/17 聯發科法說"},
            {"num":"③","name":"AI 伺服器 / ODM","reps":"廣達(2382)・緯創(3231)・鴻海(2317)","trend":"★ 強勢","trend_css":"dn","trend_bg":"rgba(16,185,129,0.15)","desc":"GB200 出貨持續放大，廣達最大受惠者。跌深是中線最佳介入時機。","week_outlook":"逢跌介入","week_css":"dn","week_bg":"rgba(16,185,129,0.12)","month_outlook":"GB200 旺季","month_css":"dn","month_bg":"rgba(16,185,129,0.12)","key_event":"7/11 廣達法說","highlight":True},
            {"num":"④","name":"先進封裝","reps":"日月光投控(3711)・京元電(2449)・矽格(6257)","trend":"偏多","trend_css":"gold","trend_bg":"rgba(245,185,66,0.12)","desc":"CoWoS 先進封裝持續擴產，日月光最大外包受益者。","week_outlook":"等待落底","week_css":"gold","week_bg":"rgba(245,185,66,0.08)","month_outlook":"CoWoS 擴產","month_css":"dn","month_bg":"rgba(16,185,129,0.08)","key_event":"7/18 日月光法說"},
            {"num":"⑤","name":"被動元件","reps":"國巨(2327)・華新科(2492)・禾伸堂(3026)","trend":"偏多","trend_css":"gold","trend_bg":"rgba(245,185,66,0.12)","desc":"外資連續買超國巨，AI 伺服器 MLCC 需求長線明確，相對抗跌。","week_outlook":"外資護盤","week_css":"dn","week_bg":"rgba(16,185,129,0.08)","month_outlook":"MLCC 旺季","month_css":"dn","month_bg":"rgba(16,185,129,0.08)","key_event":"7/23 國巨法說"},
            {"num":"⑥","name":"電源 / 散熱","reps":"台達電(2308)・奇鋐(3017)・建準(2421)","trend":"中性偏多","trend_css":"gold","trend_bg":"rgba(245,185,66,0.12)","desc":"AI 機櫃電力需求倍增，液冷解決方案需求持續強勁，台達電走勢相對獨立。","week_outlook":"相對抗跌","week_css":"gold","week_bg":"rgba(245,185,66,0.08)","month_outlook":"液冷商機","month_css":"dn","month_bg":"rgba(16,185,129,0.08)","key_event":"7/25 台達電法說"},
            {"num":"⑦","name":"記憶體","reps":"南亞科(2408)・群聯(8299)・威剛(3260)","trend":"中性","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"HBM 供需緊張利好 SK Hynix，台股記憶體受益較間接，缺乏外資積極買超支撐。","week_outlook":"觀望","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"HBM 概念","month_css":"gold","month_bg":"rgba(245,185,66,0.06)","key_event":"DRAM 價格週報"},
            {"num":"⑧","name":"網通 / 光連接器","reps":"台光電(2383)・正崴(2392)・上詮(3363)","trend":"偏多","trend_css":"gold","trend_bg":"rgba(245,185,66,0.12)","desc":"AI 資料中心對 400G/800G 光收發器需求爆炸性成長，走勢相對獨立。","week_outlook":"相對強勢","week_css":"dn","week_bg":"rgba(16,185,129,0.08)","month_outlook":"800G 旺季","month_css":"dn","month_bg":"rgba(16,185,129,0.08)","key_event":"北美 AI 訂單"},
        ],
        "sector_trend_ai": "AI 伺服器族群基本面最確定，建議作為核心持倉。被動元件外資連續買超是強訊號。半導體法說前保守，法說後看強。",
        "review_date": "07/01",
        "review_market": [
            {"item":"大盤方向","forecast":"偏多（法人護盤）","actual":"+1.94%（47,018）","actual_css":"dn","result":"accurate"},
            {"item":"外資方向","forecast":"持續買超","actual":"+323.76 億","actual_css":"dn","result":"accurate"},
            {"item":"台積電走勢","forecast":"偏多/逢低買","actual":"+1.00%（2,520）","actual_css":"dn","result":"accurate"},
            {"item":"成交量","forecast":"量能充沛","actual":"1.32 兆","actual_css":"dn","result":"accurate"},
        ],
        "review_stocks": [
            {"name":"台積電 2330","forecast":"觀望/逢低佈局","actual":"+1.00%","actual_css":"dn","result":"accurate"},
        ],
        "review_ai": "昨日判斷正確：三大法人合買 539 億護盤力道強過 ADR 壓力，大盤最終大漲 1.94%。今日考驗是 ADR -3.51% 能否被法人護盤所吸收。",
        "taiex_chart_labels": ["06/16","06/17","06/18","06/19","06/20","06/23","06/24","06/25","06/26","06/27","06/30","07/01"],
        "taiex_chart_data": [46100,46820,47120,47380,47600,47742,44220,45360,46125,47018,46125,47018],
        "foreign_net_raw": 323.76, "trust_net_raw": 156.03, "dealer_net_raw": 59.38,
        "earnings_calendar": [
            {"date":"7/16","name":"台積電 2330","type":"法說會","importance_stars":"★★★","css":"buy","is_important":True},
            {"date":"7/17","name":"聯發科 2454","type":"法說會","importance_stars":"★★★","css":"hold"},
        ],
        "earnings_ai": "7/16 台積電法說會是本月最大催化劑。Q2 EPS 若超 13 元且 Q3 展望積極，台積電單日漲幅可達 3~5%。",
    }
    render(sample, "/tmp/test_output.html")
    print("Test HTML size:", os.path.getsize("/tmp/test_output.html"), "bytes")
