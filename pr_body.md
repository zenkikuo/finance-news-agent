### 🤖 AI Debug Agent 自動診斷報告

錯誤原因：`edge_tts.exceptions.NoAudioReceived` 錯誤表示 `edge_tts` 庫在嘗試合成語音時未能接收到任何音頻。這通常發生在傳入的語音腳本（`analysis["voice_script"]`）為空字串或內容不足以合成音頻時。修復方式：在呼叫 `generate_tts` 函數之前，檢查 `analysis["voice_script"]` 是否為空或僅包含空白字元。若為空，則使用一個預設的繁體中文提示訊息作為替代腳本，以確保 `edge_tts` 總能收到可供合成的文本，從而避免錯誤並保證語音與短影音能正常生成。

---
*請檢視 Files changed 確認無誤後，點擊下方 **Merge pull request** 即可套用修復。*