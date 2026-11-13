### 🤖 AI Debug Agent 自動診斷報告

錯誤原因為 `edge_tts` 庫因 AI 生成的 `voice_script` 為空或無效而無法生成音訊，導致程式中斷。修復方式為在嘗試生成語音與短影音前，新增檢查 `voice_script` 是否有效。若無效或生成媒體過程中發生任何錯誤，則跳過媒體生成，改為僅推送文字快報至 Discord，確保核心警報功能不中斷，並增加錯誤處理以提升穩定性。

---
*請檢視 Files changed 確認無誤後，點擊下方 **Merge pull request** 即可套用修復。*