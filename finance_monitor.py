import os
import re
import json
import time
import asyncio
import hashlib
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from google import genai

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
client = genai.Client(api_key=GEMINI_API_KEY)

SEEN_FILE = "seen_finance.json"
TAIPEI_TZ = timezone(timedelta(hours=8))

# 多模型自動容錯輪詢清单（主模型 503 滿載時自動切換下一顆）
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]

# 三大穩定財經新聞 RSS 來源
RSS_SOURCES = [
    ("Reuters 路透財經", "https://news.google.com/rss/search?q=site:reuters.com+(markets+OR+semiconductor+OR+fed+OR+ai+OR+tariff)&hl=en-US&gl=US&ceid=US:en"),
    ("AP News 美聯社財經", "https://news.google.com/rss/search?q=site:apnews.com+(business+OR+economy+OR+tech+OR+fed+OR+chip)&hl=en-US&gl=US&ceid=US:en"),
    ("新浪財經全球焦點", "https://rss.sina.com.cn/roll/finance/hot_roll.xml"),
]

# 擴充版第一層關鍵字初篩：涵蓋總經、AI 伺服器、CCL、ABF、PCB、散熱、CoWoS 設備、HBM、矽光子與重電
KEYWORDS = [
    # 1. 總經、央行與地緣關稅
    "fed", "powell", "fomc", "cpi", "ppi", "pce", "nonfarm", "payroll", "rate", "treasury", "yield",
    "inflation", "recession", "tariff", "sanction", "export control", "boj", "yen", "yuan", "currency",
    "美聯儲", "聯準會", "鮑爾", "降息", "升息", "通膨", "非農", "美債", "關稅", "制裁", "出口管制", "日銀", "匯率",

    # 2. 雲端大廠與晶片巨頭
    "nvidia", "tsmc", "taiwan", "semiconductor", "chip", "ai", "apple", "microsoft", "google", "alphabet",
    "meta", "amazon", "aws", "tesla", "broadcom", "asml", "amd", "intel", "arm", "qualcomm", "mediatek",
    "輝達", "英偉達", "台積電", "半導體", "芯片", "晶片", "蘋果", "微軟", "谷歌", "特斯拉", "博通", "聯發科", "高通",

    # 3. AI 伺服器、CCL、ABF、PCB、散熱與代工廠
    "server", "data center", "capex", "gb200", "gb300", "blackwell", "rubin", "pcb", "substrate", "abf",
    "ccl", "copper clad", "liquid cooling", "thermal", "power supply", "rack", "supermicro", "smci",
    "vertiv", "foxconn", "quanta", "wiwynn", "delta",
    "伺服器", "服務器", "資料中心", "數據中心", "資本支出", "銅箔基板", "載板", "液冷", "水冷", "散熱",
    "電源", "機櫃", "鴻海", "廣達", "緯穎", "台達電", "光寶",

    # 4. 先進封裝 CoWoS、HBM 記憶體與半導體設備
    "cowos", "packaging", "hbm", "hbm3e", "hbm4", "dram", "nand", "memory", "foundry", "wafer",
    "lithography", "euv", "micron", "sk hynix", "applied materials", "amat", "lam research", "klac",
    "先進封裝", "記憶體", "高頻寬記憶體", "美光", "海力士", "晶圓", "光刻機", "設備",

    # 5. 矽光子 CPO、光通訊與低軌衛星網通
    "optical", "photonics", "cpo", "transceiver", "800g", "1.6t", "coherent", "lumentum", "marvell",
    "starlink", "spacex", "satellite", "5g", "6g",
    "矽光子", "光通訊", "高速傳輸", "低軌衛星", "星鏈", "網通",

    # 6. 重電電網、被動元件與原物料航運
    "grid", "transformer", "power grid", "electricity", "nuclear", "energy storage", "eaton", "ge vernova",
    "mlcc", "capacitor", "murata", "tdk", "ev", "electric vehicle", "byd",
    "oil", "brent", "wti", "copper", "gold", "silver", "shipping", "freight",
    "電網", "變壓器", "重電", "電力", "儲能", "核能", "被動元件", "村田", "電動車", "比亞迪",
    "原油", "銅價", "白銀", "航運", "運價", "美股", "納指", "費半"
]

def load_seen() -> list:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_seen(seen_list: list):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_list[-300:], f, ensure_ascii=False, indent=2)

def fetch_rss_candidates(seen_ids: set) -> list:
    candidates = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FinanceMonitor/1.0)"}

    for source_name, url in RSS_SOURCES:
        try:
            res = requests.get(url, headers=headers, timeout=15)
            res.raise_for_status()
            root = ET.fromstring(res.content)
            items = root.findall(".//item")[:20]

            for item in items:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                if not title or not link:
                    continue

                uid = hashlib.md5(title.lower().encode("utf-8")).hexdigest()[:12]
                if uid in seen_ids:
                    continue

                title_lower = title.lower()
                if any(kw in title_lower for kw in KEYWORDS):
                    candidates.append({
                        "uid": uid,
                        "source": source_name,
                        "title": title,
                        "link": link,
                        "pub_date": pub_date
                    })
        except Exception as e:
            print(f"⚠️ 讀取 {source_name} RSS 異常: {e}", flush=True)

    return candidates[:15]

def analyze_taiwan_impact(candidates: list) -> dict:
    """第二層：台股全供應鏈交易員視角評分（只放行 >= 4 星重大事件）"""
    news_text = "\n".join(
        [f"- [{c['source']}] {c['title']} ({c['pub_date']})" for c in candidates]
    )

    prompt = f"""
    你是一位資深的台股自營部宏觀與科技供應鏈研究員。請從以下最新國際財經快訊中，篩選出對台股具有【4星或5星重大影響】的新聞（1~3星瑣碎消息請直接忽略）。
    重點追蹤以下台股核心板塊：
    1. 權值與晶圓代工/設備/封裝（台積電、聯發科、日月光、CoWoS/先進封裝設備、HBM記憶體）
    2. AI 伺服器全供應鏈（ODM組裝：鴻海/廣達/緯穎；上游零組件：CCL銅箔基板、ABF載板、PCB、水冷散熱、電源供應器）
    3. 矽光子 CPO / 光通訊 / 低軌衛星網通
    4. 重電與電網基建（變壓器、AI資料中心電力設備，如華城）
    5. 被動元件（MLCC報價與日廠動態，如國巨）、金融股與原物料航運

    請嚴格輸出合法 JSON 格式（不要包含 markdown 標記或額外文字）：
    {{
      "has_major_news": true 或 false,
      "max_score": 1到5的整數,
      "sentiment": "強烈利多" 或 "偏多" 或 "中性觀望" 或 "偏空" 或 "重大利空",
      "headline": "20字以內的繁體中文震撼主標題（適合當短影音封面標題）",
      "affected_sectors": "受影響台股細分族群與代表性個股（例如：CCL銅箔基板/台光電、台燿；或AI伺服器/鴻海、廣達）",
      "discord_brief": "條列式繁體中文重點摘要與台股開盤影響推演（250字以內）",
      "voice_script": "60秒內可唸完的繁體中文晨間財經快報口播稿（語氣專業簡潔，約130~180字，不可為空字串）"
    }}

    【最新抓取的候選財經快訊】：
    {news_text}
    """

    last_err = None
    for model_name in FALLBACK_MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                clean_text = re.sub(r"^```json\s*|\s*```$", "", response.text.strip(), flags=re.MULTILINE)
                return json.loads(clean_text)
            except Exception as e:
                last_err = e
                print(f"⚠️ {model_name} 分析暫時失敗 (第 {attempt + 1} 次): {e}", flush=True)
                time.sleep(4)
    raise RuntimeError(f"所有分析模型皆失敗: {last_err}")

async def generate_tts(text: str, output_mp3: str):
    clean_speech = re.sub(r"[^\w\u4e00-\u9fff，。！？、；：（）%0-9a-zA-Z\s]", "", text).strip()
    if not clean_speech:
        clean_speech = "全球財經重大快訊更新，請留意台股開盤權值股與供應鏈波動風險。"
    communicate = edge_tts.Communicate(clean_speech, voice="zh-TW-YunJheNeural", rate="+5%")
    await communicate.save(output_mp3)

def create_video_card(analysis: dict, audio_path: str, output_mp4: str):
    """生成 1080x1920 直式專業財經快報短影音"""
    img_path = "finance_card.png"
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"

    font_tag = ImageFont.truetype(font_path, 42)
    font_title = ImageFont.truetype(font_path, 66)
    font_sub = ImageFont.truetype(font_path, 40)
    font_body = ImageFont.truetype(font_path, 36)

    now_str = datetime.now(TAIPEI_TZ).strftime("%Y/%m/%d %H:%M 台北時間")
    sentiment = analysis.get("sentiment", "中性觀望")
    badge_color = (220, 38, 38) if "利多" in sentiment else ((22, 163, 74) if "利空" in sentiment else (202, 138, 4))

    draw.rectangle([70, 120, 1010, 210], fill=badge_color)
    draw.text((100, 140), f"⚡ 全球財經快報｜台股影響：{sentiment}（{'★' * analysis.get('max_score', 4)}）", fill=(255, 255, 255), font=font_tag)
    draw.text((70, 240), now_str, fill=(148, 163, 184), font=font_body)

    headline = analysis.get("headline", "國際財經重大快訊")
    y_cursor = 340
    for i in range(0, len(headline), 13):
        draw.text((70, y_cursor), headline[i:i+13], fill=(248, 250, 252), font=font_title)
        y_cursor += 88

    y_cursor += 40
    draw.rectangle([70, y_cursor, 1010, y_cursor + 180], fill=(30, 41, 59))
    draw.text((95, y_cursor + 20), "🎯 連動台股族群與焦點：", fill=(56, 189, 248), font=font_sub)
    sectors = analysis.get("affected_sectors", "台股權值與科技供應鏈")
    draw.text((95, y_cursor + 85), sectors[:22], fill=(255, 255, 255), font=font_body)

    y_cursor += 230
    script = analysis.get("voice_script", "")
    for i in range(0, len(script), 23):
        if y_cursor > 1720:
            break
        draw.text((70, y_cursor), script[i:i+23], fill=(203, 213, 225), font=font_body)
        y_cursor += 58

    img.save(img_path)

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path, "-i", audio_path,
        "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-shortest", output_mp4
    ]
    subprocess.run(cmd, check=True)

def main():
    print("🔍 開始巡檢 Reuters / AP News / 新浪財經 最新快訊...", flush=True)
    seen_list = load_seen()
    seen_ids = set(seen_list)

    candidates = fetch_rss_candidates(seen_ids)
    if not candidates:
        print("☕ 目前無符合關鍵字之未讀財經快訊。", flush=True)
        return

    print(f"📥 抓到 {len(candidates)} 則關鍵字候選新聞，送交 AI 評估對台股影響力...", flush=True)
    analysis = analyze_taiwan_impact(candidates)

    for c in candidates:
        seen_list.append(c["uid"])
    save_seen(seen_list)

    if not analysis.get("has_major_news") or analysis.get("max_score", 0) < 4:
        print(f"📉 最高影響評分為 {analysis.get('max_score', 0)} 星（未達 4 星門檻），靜默略過推播。", flush=True)
        return

    print(f"🚨 偵測到 {analysis['max_score']} 星重大財經事件！準備推播 Discord...", flush=True)
    sources_links = "\n".join([f"• [{c['source']}] [{c['title']}]({c['link']})" for c in candidates[:4]])
    msg = (
        f"🚨 **【{analysis['max_score']}★ 全球財經快報】{analysis['headline']}**\n"
        f"**📊 台股方向判讀：** `{analysis['sentiment']}`｜**🎯 焦點族群：** {analysis['affected_sectors']}\n\n"
        f"{analysis['discord_brief']}\n\n"
        f"**🔗 原始新聞來源：**\n{sources_links}"
    )
    requests.post(DISCORD_WEBHOOK, json={"content": msg[:1950]}, timeout=15).raise_for_status()

    try:
        audio_file = "finance_voice.mp3"
        video_file = "finance_brief.mp4"
        asyncio.run(generate_tts(analysis["voice_script"], audio_file))
        create_video_card(analysis, audio_file, video_file)
        with open(video_file, "rb") as vf:
            requests.post(
                DISCORD_WEBHOOK,
                files={"file": ("finance_brief.mp4", vf, "video/mp4")},
                timeout=30
            ).raise_for_status()
        print("✅ 重大財經快報與短影音皆已成功推送至 Discord！", flush=True)
    except Exception as tts_err:
        print(f"⚠️ 語音短影音生成受限（已自動降級為純文字快報送達 Discord）: {tts_err}", flush=True)

if __name__ == "__main__":
    main()
