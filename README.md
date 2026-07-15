# 台股盤前 PWA (taiwan-stock-pwa)

自動化台股盤前資訊網頁。每個台灣交易日開盤前，透過 GitHub Actions 自動抓取大盤、期貨、個股、新聞與總經資料，交給 Claude AI 進行整合分析，產出一份可直接在手機瀏覽的靜態網頁（PWA），並部署到 GitHub Pages。

線上網址：`https://<你的 GitHub 帳號>.github.io/taiwan-stock-pwa/`（依 repo 的 GitHub Pages 設定為準）

## 功能特色

- **大盤總覽**：加權指數、成交量、匯率、三大法人買賣超、融資融券
- **期貨與選擇權**：夜盤台指期、Put/Call 比、期貨三大法人、最大未平倉
- **固定追蹤三檔個股**：台積電(2330)、聯發科(2454)、國巨(2327)，含技術指標（RSI、均線、布林通道、MACD）
- **動態精選股**：由外資買超前 30 + 成交量前 20 組成候選池，交由 AI 選出當日最強 3～5 檔
- **全球指數連動**：那斯達克、道瓊、SOX、VIX、黃金、原油、日經、恆生
- **AI 整合分析**：由 Claude API 產出市場方向、風險提示、操作策略等文字解讀
- **新聞與總經行事曆**：Yahoo 股市新聞、DigiTimes 產業新聞、FRED 總經事件
- **PWA 介面**：深色主題、行動裝置優化，可加入手機主畫面

## 專案結構

```
taiwan-stock-pwa/
├── index.html              # 產出的靜態網頁（由 render_html.py 自動產生，勿手動編輯）
├── data/
│   └── news_latest.json    # 新聞資料快取（供 Cowork/手動流程覆寫使用）
├── debug_ai.json           # 最近一次 AI 分析的除錯輸出
├── .nojekyll                # 停用 GitHub Pages 的 Jekyll 處理
├── .github/workflows/
│   ├── daily_update.yml    # 每日排程：抓資料 → AI 分析 → 產出 index.html → 部署
│   ├── reanalyze.yml       # 手動觸發：重新 AI 分析（不重新抓外部資料）
│   ├── deploy.yml          # push 到 main 分支時部署到 GitHub Pages
│   └── static.yml          # 簡易靜態內容部署 workflow
└── scripts/
    ├── update.py           # 每日流程主控（orchestrator），依序執行 7 個步驟
    ├── fetch_market.py     # 大盤指數、三大法人、融資融券、外資排名（TWSE 官方 API）
    ├── fetch_futures.py    # 夜盤台指期、P/C 比、期貨法人（期交所 openapi）
    ├── fetch_stocks.py     # 固定 3 檔個股 + 全球指數（yfinance）＋技術指標
    ├── fetch_candidates.py # 動態候選股池（外資買超前 30、成交量前 20）
    ├── fetch_news.py       # 新聞與經濟行事曆（Yahoo RSS / DigiTimes RSS / FRED API）
    ├── analyze.py          # 彙整所有資料，呼叫 Claude API 產出 AI 分析 JSON
    ├── render_html.py      # 依資料字典渲染出最終的 index.html
    ├── write_sheets.py     # 將每日結果寫入 Google Sheets，並讀取歷史資料
    ├── reanalyze.py        # 手動重新分析用（讀當日 Sheets 資料 → 重新分析 → 重新渲染）
    └── requirements.txt    # Python 相依套件
```

## 運作流程（update.py）

`scripts/update.py` 是整個每日流程的主控腳本，依序執行：

1. 抓取大盤資料（`fetch_market.py`）
2. 抓取期貨資料（`fetch_futures.py`）
3. 抓取固定 3 檔個股 + 全球指數（`fetch_stocks.py`）
4. 抓取動態候選股池（`fetch_candidates.py`）
5. 抓取新聞與總經行事曆（`fetch_news.py`）
6.（選用）從 Google Sheets 讀取近期歷史 → 呼叫 Claude API 進行 AI 分析（`analyze.py`）
7. 將所有資料整合後，渲染輸出 `index.html`（`render_html.py`），並（選用）寫回 Google Sheets（`write_sheets.py`）

每個步驟都有獨立的例外處理：任一資料來源失敗時會記錄警告並使用預設值繼續執行，不會中斷整體流程；只有 AI 分析或 HTML 渲染失敗才會讓流程中止。

## 自動化排程（GitHub Actions）

| Workflow | 觸發時機 | 說明 |
|---|---|---|
| `daily_update.yml` | 每日 22:30 UTC（台灣時間 06:30，週一至週五） | 完整流程：抓資料 → AI 分析 → 產出並 commit `index.html` → 部署到 GitHub Pages |
| `reanalyze.yml` | 手動觸發（workflow_dispatch） | 讀取當日 Sheets 資料重新 AI 分析並重新渲染，不重新抓外部資料 |
| `deploy.yml` | push 到 `main` | 將整個 repo 部署到 GitHub Pages |
| `static.yml` | push 到 `main` | 簡易靜態內容部署（備用） |

## 環境變數 / Secrets

在 GitHub repo 的 **Settings → Secrets and variables → Actions** 設定以下 Secrets：

| Secret | 必要性 | 用途 |
|---|---|---|
| `CLAUDE_API_KEY` | 必要 | 呼叫 Claude API 進行 AI 分析（缺少會直接中止流程） |
| `FRED_API_KEY` | 選用 | 抓取 FRED 總經事件；缺少則跳過該部分 |
| `SHEET_ID` | 選用 | 寫入/讀取 Google Sheets 歷史資料 |
| `GOOGLE_CREDENTIALS` | 選用 | Google Service Account 憑證（JSON 字串），搭配 `SHEET_ID` 使用 |

## 本機執行

```bash
# 安裝相依套件
pip install -r scripts/requirements.txt

# 設定必要環境變數
export CLAUDE_API_KEY="your-api-key"
# 選用
export FRED_API_KEY="..."
export SHEET_ID="..."
export GOOGLE_CREDENTIALS='{"...service account json..."}'

# 執行每日流程（會在上一層目錄產出 index.html）
cd scripts
python update.py
```

手動重新分析（不重新抓外部資料，僅重新跑 AI 分析與渲染）：

```bash
cd scripts
python reanalyze.py
```

## 技術棧

- **資料來源**：TWSE 官方 API、期交所 openapi.taifex.com.tw、yfinance、Yahoo/DigiTimes RSS、FRED API
- **AI 分析**：Anthropic Claude API（`anthropic` SDK）
- **資料處理**：pandas、numpy
- **試算表整合**：gspread + Google OAuth（選用）
- **前端**：純 HTML/CSS/JS 靜態頁面 + Chart.js，無框架、無建置流程
- **部署**：GitHub Actions + GitHub Pages

## 注意事項

- `index.html` 為自動產生檔案，任何手動修改都會在下次排程執行後被覆蓋，若要調整版面請修改 `scripts/render_html.py`。
- 各資料來源皆有例外處理，取得失敗時會顯示「⚠️ 無法取得資料」而非讓整個流程中斷。
- AI 分析結果與除錯資訊會寫入 `debug_ai.json`，方便排查 Claude API 回應異常的狀況。

## 已知問題修正紀錄

- **2026-07-15**：`update.py` 呼叫 `write_sheets.get_history()` / `write()` 時參數順序與函式簽章對不上，導致 Google Sheets 讀寫永遠失敗（例外被吞掉，log 卻顯示「✅ Google Sheets updated」）。已修正參數順序，並改為傳入正確的 `GOOGLE_CREDENTIALS` JSON 字串內容（原本誤傳檔案路徑）。
- **2026-07-15**：`_build_render_data()` 從未接收 `candidates_data`，導致動態精選股清單中的候選池資料（外資排名、選股理由）永遠是空的。已修正為正確傳入。
- **2026-07-15**：`reanalyze.py` 呼叫 `render_html.render()` 時傳入 5 個位置參數，但該函式只接受 `(data, output_path)`，會導致「Manual Re-Analysis」workflow 每次執行必定 TypeError 中止。已修正為先組出正確的 render 字典再呼叫。
