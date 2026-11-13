# 📈 Global Finance & Taiwan Market Monitor (`finance-news-agent`)

24 小時全自動國際財經情報監控與台股開盤預警系統。透過 **Multi-Agent 協作架構**，每小時自動聚合 **Reuters（路透社）、AP News（美聯社）與新浪財經**最新快訊，以台股自營交易員視角過濾出 **4～5 星重大事件**，生成繁體中文摘要、受影響台股族群判讀與直式語音短影音，並自動推播至 Discord 專屬頻道。

內建 **AI Self-Healing（自我修復）閉環機制**：一旦執行期間發生程式異常或外部 API 瞬時滿載，系統會自動喚醒 `Debug Agent` 切換備援模型分析錯誤、直接修補程式碼推送回 `main` 分支並重新驗證執行。

---

## ✨ 核心特色

* **三源穩定情報聚合**：結合 Reuters（Google News RSS 聚合）、AP News 與新浪財經全球焦點 RSS，避開反爬蟲封鎖並自動去重（`seen_finance.json`）。
* **雙層漏斗精準過濾（4～5 星門檻）**：
  1. **第一層（硬性關鍵字初篩）**：鎖定 Fed 利率、CPI/通膨、關稅、台積電/輝達/蘋果供應鏈、AI 伺服器、重電與原物料波動。
  2. **第二層（AI 交易員影響力評分）**：呼叫 Gemini 模型評估對台股權值股、AI 伺服器、重電、被動元件與金融股的實質衝擊，僅放行 **4 星與 5 星**事件。
* **多媒體雙推播與優雅降級（Fallback）**：
  * 優先發送結構化文字戰報（含利多/利空判讀、受影響台股族群與原始新聞連結）。
  * 自動透過 `edge-tts` + `Pillow` + `FFmpeg` 合成 1080×1920 直式財經短影音；若雲端機房遭微軟 TTS 限流，則優雅降級為純文字快報，確保情報零漏接。
* **多模型容錯與全自動修復（Auto-Heal）**：
  * 內建 `gemini-2.5-flash` -> `gemini-2.5-flash-lite` -> `gemini-2.0-flash` 自動輪詢機制，免疫單一節點 `503 UNAVAILABLE` 滿載錯誤。
  * 腳本執行失敗時自動觸發 `debug_agent.py` 修復程式碼、自動 `git push` 回 `main` 並重跑驗證，同步發送診斷報告至 Discord。

---

## 📂 專案結構

    finance-news-agent/
    ├── .github/workflows/
    │   └── watch_finance.yml    # GitHub Actions 每小時排程與 Auto-Heal 流程定義
    ├── finance_monitor.py       # 核心爬蟲、台股影響力評分、短影音合成與 Discord 推播
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
