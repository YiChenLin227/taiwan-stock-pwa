#!/usr/bin/env python3
"""
update.py — Daily orchestrator for Taiwan stock pre-market PWA
Run by GitHub Actions at 06:30 Taiwan time (22:30 UTC Sun-Thu)
"""

import os, sys, json, traceback
from datetime import datetime

def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def main():
    # ── Environment ──────────────────────────────────────────────────────────
    claude_key  = os.environ.get("CLAUDE_API_KEY","")
    fred_key    = os.environ.get("FRED_API_KEY","")
    sheet_id    = os.environ.get("SHEET_ID","")
    gcp_creds   = os.environ.get("GOOGLE_CREDENTIALS","")  # JSON string

    if not claude_key:
        log("❌ CLAUDE_API_KEY not set"); sys.exit(1)

    # Write GCP credentials to temp file if provided
    creds_path = None
    if gcp_creds:
        creds_path = "/tmp/gcp_creds.json"
        with open(creds_path, "w") as f:
            f.write(gcp_creds)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # ── Step 1: Fetch market data ─────────────────────────────────────────────
    log("📊 Step 1/7: Fetching market data...")
    try:
        from fetch_market import fetch_all as fetch_market
        market_data = fetch_market()
        log(f"  TAIEX: {market_data.get('taiex_close')} | Volume: {market_data.get('volume_trillion')}T")
    except Exception as e:
        log(f"  ⚠️ Market fetch error: {e}"); market_data = {}

    # ── Step 2: Fetch futures data ────────────────────────────────────────────
    log("📈 Step 2/7: Fetching futures data...")
    try:
        from fetch_futures import fetch_all as fetch_futures
        futures_data = fetch_futures()
        log(f"  Night fut: {futures_data.get('night_futures_last')} | P/C: {futures_data.get('pc_ratio')}")
    except Exception as e:
        log(f"  ⚠️ Futures fetch error: {e}"); futures_data = {}

    # ── Step 3: Fetch stock data (fixed 3) ───────────────────────────────────
    log("📋 Step 3/7: Fetching stock data (fixed stocks + global indices)...")
    try:
        from fetch_stocks import fetch_all as fetch_stocks
        stocks_data = fetch_stocks()
        log(f"  2330 close: {stocks_data.get('stock_2330',{}).get('close')} | TSM ADR: {stocks_data.get('tsm_adr_close')}")
    except Exception as e:
        log(f"  ⚠️ Stocks fetch error: {e}"); stocks_data = {}

    # ── Step 4: Fetch candidate pool + select dynamic stocks ─────────────────
    log("🔍 Step 4/7: Fetching candidate stocks...")
    try:
        from fetch_candidates import fetch_all as fetch_candidates
        foreign_top30 = market_data.get("foreign_top30", [])
        volume_top20  = market_data.get("volume_top20", [])
        candidates_data = fetch_candidates(foreign_top30, volume_top20)
        log(f"  Candidate pool: {len(candidates_data)} stocks")
    except Exception as e:
        log(f"  ⚠️ Candidates fetch error: {e}"); candidates_data = []

    # ── Step 5: Fetch news ───────────────────────────────────────────────────
    log("📰 Step 5/7: Fetching news & economic calendar...")
    try:
        from fetch_news import fetch_all as fetch_news
        news_data = fetch_news(fred_api_key=fred_key)
        log(f"  Yahoo: {len(news_data.get('yahoo_tw_news',[]))} | DigiTimes: {len(news_data.get('industry_news',[]))} | FRED: {len(news_data.get('macro_events',[]))}")
    except Exception as e:
        log(f"  ⚠️ News fetch error: {e}"); news_data = {}

    # ── Step 6: Read Sheets history + AI analysis ─────────────────────────────
    log("🤖 Step 6/7: Running AI analysis...")
    history_rows = []
    if sheet_id and gcp_creds:
        try:
            from write_sheets import get_history
            history_rows = get_history(gcp_creds, sheet_id, n=7)
            log(f"  History rows loaded: {len(history_rows)}")
        except Exception as e:
            log(f"  ⚠️ History read error: {e}")

    try:
        from analyze import analyze, _fallback_result
        ai_result = analyze(
            market=market_data,
            futures=futures_data,
            stocks=stocks_data,
            candidates=candidates_data,
            news=news_data,
            history_rows=history_rows,
            api_key=claude_key,
        )
        log(f"  Direction: {ai_result.get('market_direction')} | Top stocks: {len(ai_result.get('top_stocks',[]))}")
    except Exception as e:
        log(f"  ❌ AI analysis error: {e}")
        traceback.print_exc()
        from analyze import _fallback_result
        ai_result = _fallback_result()

    # ── Step 7: Build render data dict ───────────────────────────────────────
    log("🎨 Step 7/7: Rendering HTML...")

    # Merge all data sources into render dict
    render_data = _build_render_data(market_data, futures_data, stocks_data, news_data, ai_result, candidates_data, history_rows)

    try:
        from render_html import render
        render(render_data, output_path="../index.html")
        log("  ✅ index.html written")
    except Exception as e:
        log(f"  ❌ Render error: {e}")
        traceback.print_exc()
        sys.exit(1)

    # ── Write to Sheets ──────────────────────────────────────────────────────
    if sheet_id and gcp_creds:
        try:
            from write_sheets import write
            write(market_data, futures_data, stocks_data, ai_result, news_data, gcp_creds, sheet_id)
            log("  ✅ Google Sheets updated")
        except Exception as e:
            log(f"  ⚠️ Sheets write error: {e}")

    log("🏁 Done! index.html is ready for GitHub Pages deployment.")


def _build_render_data(market, futures, stocks, news, ai, candidates_data=None, history_rows=None):
    """Merge raw fetched data + AI results into the render_html data dict"""
    candidates_data = candidates_data or []
    history_rows = history_rows or []
    from datetime import datetime, timezone, timedelta
    TW = timezone(timedelta(hours=8))
    now_tw = datetime.now(TW)
    today = now_tw.strftime("%Y/%m/%d")
    today_short = now_tw.strftime("%m/%d")

    # Determine trading date label
    raw_date = str(market.get("trade_date", ""))
    if len(raw_date) == 8 and raw_date.isdigit():
        trading_date = f"{raw_date[4:6]}/{raw_date[6:8]}"
    else:
        trading_date = market.get("trading_date", "前日")

    # ── Safe numeric helper ───────────────────────────────────────────────────
    def safe_float(val, default=0.0):
        """Convert to float safely; returns default for warning strings or None."""
        if val is None:
            return default
        s = str(val).replace("%","").replace("+","").replace(",","").replace("億","").strip()
        if not s or "⚠" in s.encode('ascii','ignore').decode() or "無法" in s:
            return default
        # Check for Chinese warning text
        try:
            encoded = s.encode('utf-8')
        except Exception:
            return default
        if b"\xe2\x9a\xa0" in encoded or b"\xe7\x84\xa1\xe6\xb3\x95" in encoded:
            return default
        try:
            return float(s)
        except (ValueError, TypeError):
            return default

    # CSS helpers
    def pct_css(val):
        try:
            f = float(str(val).replace("%","").replace("+","").replace(",",""))
            return "up" if f >= 0 else "dn"
        except: return "sub"

    def sign_css(val):
        """For institutional amounts: positive=dn(green), negative=up(red)"""
        try:
            f = float(str(val).replace("+","").replace(",","").replace("億",""))
            return "up" if f >= 0 else "dn"
        except: return "sub"

    def fmt_yi(val):
        try:
            f = float(str(val).replace(",",""))
            return f"+{f:.2f}" if f>=0 else f"{f:.2f}"
        except: return str(val) if val else "⚠️"

    # ── TAIEX ────────────────────────────────────────────────────────────────
    taiex_close = market.get("taiex_close","")
    taiex_change = market.get("taiex_change","")
    taiex_change_pct = market.get("taiex_change_pct","")
    taiex_css = pct_css(taiex_change_pct)

    # ── FX ───────────────────────────────────────────────────────────────────
    twd_usd = market.get("twd_usd","")
    fx_change_pct = market.get("fx_change_pct","")
    # TWD depreciates = bad for import, shown as "up" (red)
    try:
        fx_f = float(str(fx_change_pct).replace("%","").replace("+",""))
        fx_css = "up" if fx_f >= 0 else "dn"  # positive change = red, consistent with other indicators
        fx_desc = f"{'貶值' if fx_f < 0 else '升值'} {fx_change_pct}"
    except:
        fx_css = "sub"; fx_desc = fx_change_pct or "—"

    # ── ADR ──────────────────────────────────────────────────────────────────
    adr_close = stocks.get("tsm_adr_close","")
    adr_pct = stocks.get("tsm_adr_change_pct","")
    adr_css = pct_css(adr_pct)  # negative=up(red)
    # flip: negative ADR is bad, should show as up(red)
    try:
        adr_f = float(str(adr_pct).replace("%","").replace("+",""))
        adr_css = "dn" if adr_f < 0 else "up"
    except: pass

    # ── Institutional ────────────────────────────────────────────────────────
    foreign_net = market.get("foreign_net_yi",0)
    trust_net   = market.get("trust_net_yi",0)
    dealer_net  = market.get("dealer_net_yi",0)
    total_net   = market.get("total_net_yi",0)

    def inst_desc(val, entity="法人"):
        try:
            f = float(str(val).replace(",",""))
            if f > 200: return "積極加碼"
            if f > 50:  return "買超"
            if f > 0:   return "小幅買超"
            if f > -50: return "小幅賣超"
            return "大幅賣超"
        except: return "—"

    # Foreign top 3 from market data
    foreign_top30 = market.get("foreign_top30", [])
    top3 = []
    medals = ["🥇 第1","🥈 第2","🥉 第3"]
    for i, s in enumerate(foreign_top30[:3]):
        top3.append({"rank": medals[i], "name": f"{s.get('name','')} {s.get('code','')}", "css": "up"})

    # 個股外資買超排名對照表（來自 market.foreign_top30，供固定股/精選股頁面查詢個股外資狀態）
    foreign_rank_map = {}
    for idx, s in enumerate(foreign_top30):
        _code = str(s.get("code", "")).strip()
        if _code:
            foreign_rank_map[_code] = (idx + 1, s.get("net_shares", 0))

    def get_foreign_info(code):
        """依股票代號查詢外資買超排名；查不到代表當日未進外資買超前30名（非資料抓取失敗）"""
        info = foreign_rank_map.get(str(code))
        if info:
            rank, net_shares = info
            try:
                lots = f"{int(net_shares) // 1000:,}張"
            except (TypeError, ValueError):
                lots = str(net_shares)
            return f"買超第{rank}名", f"外資買超 {lots}", "up"
        return "未進前30", "非外資買超前30名個股", "dn"

    # ── PC Ratio ─────────────────────────────────────────────────────────────
    pc_ratio = futures.get("pc_ratio")
    pc_sentiment = futures.get("pc_sentiment","中性")
    if pc_ratio:
        try:
            pc_f = float(pc_ratio)
            pc_css = "acc" if pc_f < 0.8 else ("gold" if pc_f > 1.2 else "sub")
            pc_desc = f"市場偏多" if pc_f < 0.8 else ("市場偏空" if pc_f > 1.2 else "中性觀望")
        except: pc_css="gold"; pc_desc=pc_sentiment
    else:
        pc_css="sub"; pc_desc="即時查詢"

    # ── Global indices ────────────────────────────────────────────────────────
    def idx_css(val):
        try:
            f = float(str(val).replace("%","").replace("+",""))
            return "up" if f >= 0 else "dn"
        except: return "sub"

    def idx_desc(val, name=""):
        try:
            f = float(str(val).replace("%","").replace("+",""))
            arrow = "↑" if f >= 0 else "↓"
            return f"{arrow} {name}{'看多' if f>0 else '承壓'}"
        except: return "—"

    nasdaq_ch = stocks.get("nasdaq_change_pct","")
    dji_ch    = stocks.get("dji_change_pct","")
    sox_ch    = stocks.get("sox_change_pct","")
    vix_val   = stocks.get("vix_close","")
    gold_ch   = stocks.get("gold_change_pct","")
    brent_ch  = stocks.get("brent_change_pct","")
    nikkei_ch = stocks.get("nikkei_change_pct","")
    hsi_ch    = stocks.get("hsi_change_pct","")

    # ── AI results → render fields ────────────────────────────────────────────
    market_direction = ai.get("market_direction","中性")
    biggest_risk     = ai.get("biggest_risk","請確認當日市場狀況")
    open_lo = ai.get("open_range_low","")  or market.get("taiex_close","")
    open_hi = ai.get("open_range_high","") or market.get("taiex_close","")

    # Fixed stock details from AI
    def build_stock_render(code, ai_stock, raw_stock):
        close = raw_stock.get("close","")
        change_pct = raw_stock.get("change_pct","")
        rsi = raw_stock.get("rsi","")
        try: rsi_f = float(str(rsi)); rsi_css = "up" if rsi_f>70 else ("dn" if rsi_f<30 else "gold")
        except: rsi_css = "gold"
        rsi_desc = "短線超買" if str(rsi_css)=="up" else ("超賣反彈" if str(rsi_css)=="dn" else "正常區間")
        news_list = raw_stock.get("news", [])
        f_rank, f_desc, f_css = get_foreign_info(code)
        return {
            "name": raw_stock.get("name",""),
            "desc": raw_stock.get("desc",""),
            "close": close, "change_pct": change_pct,
            "change_css": pct_css(change_pct),
            "adr_close": stocks.get("tsm_adr_close","") if code=="2330" else "",
            "adr_change_pct": adr_pct if code=="2330" else "",
            "adr_css": adr_css if code=="2330" else "sub",
            "trend_text": ai_stock.get("direction","偏多"),
            "trend_css": "up" if "多" in ai_stock.get("direction","") else ("dn" if "空" in ai_stock.get("direction","") else "gold"),
            "foreign_rank": f_rank,
            "foreign_css": f_css,
            "foreign_desc": f_desc,
            "rsi": rsi, "rsi_css": rsi_css, "rsi_desc": rsi_desc,
            "direction": ai_stock.get("direction","觀望"),
            "direction_css": "up" if "多" in ai_stock.get("direction","") else ("dn" if "空" in ai_stock.get("direction","") else "gold"),
            "buy_range": ai_stock.get("buy_range","—"),
            "stop_loss": ai_stock.get("stop_loss","—"),
            "target": ai_stock.get("target","—"),
            "ai_insight": ai_stock.get("ai_insight",""),
            "news": news_list,
            "trading_date": trading_date,
        }

    ai_fixed = ai.get("fixed_stocks",{})

    # fetch_stocks returns FLAT keys like "2330_close", "2330_rsi", etc.
    def get_stock_dict(code):
        prefix = f"{code}_"
        return {k[len(prefix):]: v for k, v in stocks.items() if k.startswith(prefix)}

    s2330_raw = get_stock_dict("2330")
    s2454_raw = get_stock_dict("2454")
    s2327_raw = get_stock_dict("2327")
    s2330_raw.setdefault("name","台積電"); s2330_raw.setdefault("desc","晶圓代工龍頭")
    s2454_raw.setdefault("name","聯發科"); s2454_raw.setdefault("desc","IC 設計龍頭 ‧ AI 晶片 / AI PC 概念")
    s2327_raw.setdefault("name","國巨");  s2327_raw.setdefault("desc","被動元件龍頭")

    stock_2330 = build_stock_render("2330", ai_fixed.get("2330",{}), s2330_raw)
    stock_2454 = build_stock_render("2454", ai_fixed.get("2454",{}), s2454_raw)
    stock_2327 = build_stock_render("2327", ai_fixed.get("2327",{}), s2327_raw)
    stock_2330["extra_label"] = "外資目標價"
    stock_2330["extra_css"] = "acc"
    stock_2330["extra_value"] = s2330_raw.get("target_price", stocks.get("tsm_target_price","—"))
    stock_2330["extra_desc"] = "ADR 分析師共識"
    stock_2330["op4_label"] = "法說會"
    stock_2330["op4_value"] = ai.get("tsmc_earnings_date","待確認")

    # Dynamic top stocks
    ai_top = ai.get("top_stocks",[])
    top_stocks = []
    for s in ai_top:
        code = s.get("code","")
        raw = {k[len(code)+1:]: v for k, v in stocks.items() if k.startswith(f"{code}_")}
        if not raw:
            raw = stocks.get(f"stock_{code}", {})
        # Try candidates pool for additional data
        cand_data = {}
        for c in candidates_data:
            if c.get("code")==code: cand_data=c; break
        close = raw.get("close","") or cand_data.get("close","")
        change_pct = raw.get("change_pct","") or cand_data.get("change_pct","")
        rsi = raw.get("rsi","") or cand_data.get("rsi","")
        try: rsi_f=float(str(rsi)); rsi_css="up" if rsi_f>70 else ("dn" if rsi_f<30 else "gold")
        except: rsi_css="gold"
        f_rank, f_desc, f_css = get_foreign_info(code)
        if f_rank == "未進前30" and cand_data.get("selection_reason"):
            f_desc = cand_data.get("selection_reason", f_desc)
        top_stocks.append({
            "code": code, "name": s.get("name",""),
            "desc": s.get("theme",""),
            "close": close, "change_pct": change_pct,
            "change_css": pct_css(change_pct),
            "direction": s.get("direction","偏多"),
            "direction_css": "up" if "多" in s.get("direction","") else "dn",
            "foreign_rank": f_rank,
            "foreign_css": f_css,
            "foreign_desc": f_desc,
            "rsi": rsi, "rsi_css": rsi_css,
            "rsi_desc": "超買" if rsi_css=="up" else ("超賣" if rsi_css=="dn" else "正常"),
            "theme": s.get("theme",""), "theme_desc": s.get("ai_insight","")[:20] if s.get("ai_insight") else "",
            "buy_range": s.get("buy_range","—"),
            "stop_loss": s.get("stop_loss","—"),
            "target": s.get("target","—"),
            "selection_reason": s.get("ai_insight","")[:30] if s.get("ai_insight") else "",
            "ai_insight": s.get("ai_insight",""),
            "news": s.get("news",[]) or raw.get("news",[]),
            "trading_date": trading_date,
        })

    # ── Chart data from history ───────────────────────────────────────────────
    # 從 Google Sheets 歷史紀錄（「日期」「加權指數收盤」欄位）組出近期走勢圖，並補上今日即時收盤
    chart_labels, chart_data = [], []
    for row in history_rows:
        d_label = str(row.get("日期", "")).strip()
        close_val = row.get("加權指數收盤", "")
        try:
            close_f = float(str(close_val).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if len(d_label) == 10 and "/" in d_label:
            d_label = d_label[5:]  # "2026/07/16" → "07/16"
        chart_labels.append(d_label)
        chart_data.append(close_f)
    # 補上今日（尚未寫入 Sheets 的即時收盤）
    try:
        today_close_f = float(str(taiex_close).replace(",", ""))
        if today_close_f and (not chart_labels or chart_labels[-1] != trading_date):
            chart_labels.append(trading_date)
            chart_data.append(today_close_f)
    except (TypeError, ValueError):
        pass
    if not chart_labels:
        chart_labels = [trading_date]
        chart_data = [taiex_close] if taiex_close else []

    # ── Sectors from AI ───────────────────────────────────────────────────────
    sectors = ai.get("sectors", [])
    if not sectors:
        # Default 8 sectors structure — AI fills in the dynamic parts
        sectors = _default_sectors()

    # ── Build final render dict ───────────────────────────────────────────────
    return {
        "today": today, "today_short": today_short, "trading_date": trading_date,
        "market_direction": market_direction, "biggest_risk": biggest_risk,
        "taiex_close": str(taiex_close), "taiex_change": str(taiex_change),
        "taiex_change_pct": str(taiex_change_pct), "taiex_css": taiex_css,
        "open_range_low": str(open_lo), "open_range_high": str(open_hi),
        "volume_trillion": str(market.get("volume_trillion","")),
        "volume_desc": "量能充沛" if safe_float(market.get("volume_trillion",0)) > 1.0 else "量能普通",
        "twd_usd": str(twd_usd), "fx_change_pct": str(fx_change_pct),
        "fx_change_desc": fx_desc, "fx_css": fx_css,
        "tsm_adr_close": str(adr_close), "tsm_adr_change_pct": str(adr_pct), "tsm_adr_css": adr_css,
        "tsm_target_price": stocks.get("tsm_target_price",""),
        "night_futures_last": str(futures.get("night_futures_last","⚠️ 待即時更新")),
        "key_support": str(ai.get("key_support","")),
        "key_resistance": str(ai.get("key_resistance","")),
        "taiex_ai": ai.get("taiex_ai",""),
        "strategy_ai": ai.get("strategy_ai",""),
        "risk_ai": ai.get("risk_ai",""),
        "macro_ai": ai.get("macro_ai",""),
        "full_ai_text": ai.get("full_ai_text",""),
        "ai_opportunities": ai.get("ai_opportunities",""),
        "ai_risks_text": ai.get("ai_risks_text",""),
        "ai_best_strategy": ai.get("ai_best_strategy",""),
        "institutional_ai": ai.get("institutional_ai",""),
        "margin_ai": ai.get("margin_ai",""),
        "fx_ai": ai.get("fx_ai",""),
        "sector_trend_ai": ai.get("sector_trend_ai",""),
        # Institutional
        "foreign_net_yi": fmt_yi(foreign_net), "foreign_css": sign_css(foreign_net),
        "foreign_top1": foreign_top30[0].get("name","—") if foreign_top30 else "—",
        "trust_net_yi": fmt_yi(trust_net), "trust_css": sign_css(trust_net),
        "trust_desc": inst_desc(trust_net,"投信"),
        "dealer_net_yi": fmt_yi(dealer_net), "dealer_css": sign_css(dealer_net),
        "dealer_desc": inst_desc(dealer_net,"自營商"),
        "total_net_yi": fmt_yi(total_net), "total_css": sign_css(total_net),
        "total_desc": "近期高水位" if safe_float(total_net)>400 else inst_desc(total_net),
        "foreign_top3": top3,
        "foreign_net_raw": safe_float(foreign_net),
        "trust_net_raw": safe_float(trust_net),
        "dealer_net_raw": safe_float(dealer_net),
        # Margin
        "margin_change_yi": str(market.get("margin_change","")),
        "margin_change_css": sign_css(market.get("margin_change",0)),
        "margin_change_desc": "散戶去槓桿（健康）" if safe_float(market.get("margin_change",0))<0 else "融資擴大（留意風險）",
        "short_balance": str(market.get("short_balance","")),
        "short_ratio_pct": str(market.get("short_ratio_pct","")),
        # PC
        "pc_ratio": str(pc_ratio) if pc_ratio else None,
        "pc_sentiment": pc_sentiment, "pc_desc": pc_desc,
        # Global
        "nasdaq_change": nasdaq_ch, "nasdaq_css": idx_css(nasdaq_ch), "nasdaq_desc": idx_desc(nasdaq_ch,"那斯達克"),
        "dji_change": dji_ch, "dji_css": idx_css(dji_ch), "dji_desc": idx_desc(dji_ch,"道瓊"),
        "sox_change": sox_ch, "sox_css": idx_css(sox_ch), "sox_desc": idx_desc(sox_ch,"SOX"),
        "vix": vix_val, "vix_css": "up" if safe_float(vix_val)>25 else "dn",
        "vix_desc": "⚠️ 恐慌升高" if safe_float(vix_val)>25 else "↓ 市場平靜",
        "gold_change": gold_ch, "gold_css": idx_css(gold_ch), "gold_desc": idx_desc(gold_ch,"黃金"),
        "brent_change": brent_ch, "brent_css": idx_css(brent_ch), "brent_desc": idx_desc(brent_ch,"原油"),
        "nikkei_change": nikkei_ch, "nikkei_css": idx_css(nikkei_ch), "nikkei_desc": idx_desc(nikkei_ch,"日股"),
        "hsi_change": hsi_ch, "hsi_css": idx_css(hsi_ch), "hsi_desc": idx_desc(hsi_ch,"恆生"),
        # Stocks
        "stock_2330": stock_2330, "stock_2454": stock_2454, "stock_2327": stock_2327,
        "top_stocks": top_stocks,
        "top_stocks_reason": ai.get("top_stocks_reason","AI 依外資買超強度、技術動能、產業題材綜合判斷選出今日最強勢股"),
        # Operations
        "today_strongest_sector": ai.get("today_strongest_sector",""),
        "today_biggest_risk_stock": ai.get("today_biggest_risk_stock",""),
        "stop_loss_tsmc": ai_fixed.get("2330",{}).get("stop_loss",""),
        "stop_loss_taiex": ai.get("key_support",""),
        "reanalysis_count": ai.get("reanalysis_count",0),
        "update_time": __import__('datetime').datetime.utcnow().strftime("%m/%d %H:%M") + " UTC",
        "generated_at": __import__('datetime').datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        # Sectors
        "sectors": sectors,
        # Review (yesterday's data from Sheets)
        "review_date": market.get("prev_trading_date", trading_date),
        "review_market": ai.get("review_market",[]),
        "review_stocks": ai.get("review_stocks",[]),
        "review_ai": ai.get("review_ai",""),
        # News
        "yahoo_news": news.get("yahoo_tw_news",[]),
        "digitimes_news": news.get("industry_news",[]),
        "fred_events": news.get("macro_events",[]),
        "earnings_calendar": ai.get("earnings_calendar",[]),
        "earnings_ai": ai.get("earnings_ai",""),
        # Charts
        "taiex_chart_labels": chart_labels,
        "taiex_chart_data": chart_data,
    }


def _default_sectors():
    return [
        {"num":"①","name":"半導體製造","reps":"台積電(2330)・聯電(2303)・世界先進(5347)","trend":"—","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"AI 分析暫無資料","week_outlook":"—","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"—","month_css":"sub","month_bg":"rgba(255,255,255,0.04)","key_event":"法說會"},
        {"num":"②","name":"IC 設計","reps":"聯發科(2454)・瑞昱(2379)・聯詠(3034)","trend":"—","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"AI 分析暫無資料","week_outlook":"—","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"—","month_css":"sub","month_bg":"rgba(255,255,255,0.04)","key_event":"法說會"},
        {"num":"③","name":"AI 伺服器 / ODM","reps":"廣達(2382)・緯創(3231)・鴻海(2317)","trend":"—","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"AI 分析暫無資料","week_outlook":"—","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"—","month_css":"sub","month_bg":"rgba(255,255,255,0.04)","key_event":"法說會","highlight":False},
        {"num":"④","name":"先進封裝","reps":"日月光投控(3711)・京元電(2449)・矽格(6257)","trend":"—","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"AI 分析暫無資料","week_outlook":"—","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"—","month_css":"sub","month_bg":"rgba(255,255,255,0.04)","key_event":"法說會"},
        {"num":"⑤","name":"被動元件","reps":"國巨(2327)・華新科(2492)・禾伸堂(3026)","trend":"—","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"AI 分析暫無資料","week_outlook":"—","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"—","month_css":"sub","month_bg":"rgba(255,255,255,0.04)","key_event":"法說會"},
        {"num":"⑥","name":"電源 / 散熱","reps":"台達電(2308)・奇鋐(3017)・建準(2421)","trend":"—","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"AI 分析暫無資料","week_outlook":"—","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"—","month_css":"sub","month_bg":"rgba(255,255,255,0.04)","key_event":"法說會"},
        {"num":"⑦","name":"記憶體","reps":"南亞科(2408)・群聯(8299)・威剛(3260)","trend":"—","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"AI 分析暫無資料","week_outlook":"—","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"—","month_css":"sub","month_bg":"rgba(255,255,255,0.04)","key_event":"—"},
        {"num":"⑧","name":"網通 / 光連接器","reps":"台光電(2383)・正崴(2392)・上詮(3363)","trend":"—","trend_css":"sub","trend_bg":"rgba(255,255,255,0.05)","desc":"AI 分析暫無資料","week_outlook":"—","week_css":"sub","week_bg":"rgba(255,255,255,0.04)","month_outlook":"—","month_css":"sub","month_bg":"rgba(255,255,255,0.04)","key_event":"—"},
    ]


if __name__ == "__main__":
    main()
