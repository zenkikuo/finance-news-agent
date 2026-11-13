# 📈 Global Finance & Taiwan Market Monitor (`finance-news-agent`)

24 小時全自動國際財經情報監控與台股開盤預警系統。透過 **Multi-Agent 協作架構**，每小時自動聚合 **Reuters（路透社）、AP News（美聯社）與新浪財經**最新快訊，以台股自營交易員視角過濾出 **4～5 星重大事件**，生成繁體中文摘要、受影響台股細分族群判讀與直式語音短影音，並自動推播至 Discord 專屬頻道。

## ✨ 核心特色

* **三源穩定情報聚合**：結合 Reuters（Google News RSS 聚合）、AP News 與新浪財經全球焦點 RSS，避開反爬蟲封鎖並自動去重（`seen_finance.json`）。
* **雙層漏斗精準過濾（4～5 星門檻）**：
  1. **第一層（全供應鏈關鍵字初篩）**：鎖定 Fed 利率、CPI/通膨、關稅匯率、晶圓代工與先進封裝（CoWoS 設備、HBM 記憶體）、AI 伺服器上下游零組件（CCL 銅箔基板、ABF 載板、PCB、水冷散熱、電源）、矽光子 CPO、重電電網與大宗原物料。
  2. **第二層（AI 交易員影響力評分）**：呼叫 Gemini 模型評估對台股權值股與細分供應鏈的實質衝擊，僅放行 **4 星與 5 星**事件。
* **多媒體雙推播與優雅降級（Fallback）**：優先發送結構化文字戰報，並透過 `edge-tts` + `Pillow` + `FFmpeg` 合成 1080×1920 直式財經短影音；若雲端 TTS 受限則自動降級為純文字快報。
* **多模型容錯與全自動修復（Auto-Heal）**：支援 `gemini-2.5-flash` -> `gemini-2.5-flash-lite` -> `gemini-2.0-flash` 自動輪詢，執行異常時自動喚醒 `debug_agent.py` 修補程式碼推回 `main` 並重跑驗證。

## 📂 專案結構

    finance-news-agent/
    ├── .github/workflows/
    │   └── watch_finance.yml    # GitHub Actions 每小時排程與 Auto-Heal 流程定義
    ├── finance_monitor.py       # 核心爬蟲、台股全供應鏈評分、短影音合成與 Discord 推播
    ├── debug_agent.py           # 異常自動診斷、程式碼修補與多模型容錯代理
    ├── seen_finance.json        # 已處理新聞雜湊紀錄（防止重複推播）
    └── README.md                # 專案說明文件

---

## ⚙️ 環境與 Secrets 設定

本專案完全運行於 **GitHub Actions** 雲端環境，無需本地伺服器。部署時需於 GitHub Repository 設定以下項目：

1. **Repository Secrets**（`Settings` -> `Secrets and variables` -> `Actions`）：
   * `GEMINI_API_KEY`：Google AI Studio API 金鑰。
   * `DISCORD_WEBHOOK_URL`：Discord `#全球財經快報` 頻道的專屬 Webhook 網址。
2. **Workflow 權限**（`Settings` -> `Actions` -> `General`）：
   * 勾選 **Read and write permissions**（允許排程更新 `seen_finance.json` 及由 `Debug Agent` 自動推送修復 Commit）。

---

## 🚀 執行方式

* **自動排程**：每小時整點（`0 * * * *` UTC）自動巡檢一次。
* **手動即時測試**：前往 GitHub 頁面的 **Actions** -> **Global Finance & Taiwan Market Monitor** -> 點擊 **Run workflow** 即可立即觸發執行。
