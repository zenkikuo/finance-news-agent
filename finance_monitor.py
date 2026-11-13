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

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]

RSS_SOURCES = [
    ("Reuters 路透財經", "https://news.google.com/rss/search?q=site:reuters.com+(markets+OR+semiconductor+OR+fed+OR+ai+OR+tariff)&hl=en-US&gl=US&ceid=US:en"),
    ("AP News 美聯社財經", "https://news.google.com/rss/search?q=site:apnews.com+(business+OR+economy+OR+tech+OR+fed+OR+chip)&hl=en-US&gl=US&ceid=US:en"),
    ("新浪財經全球焦點", "https://rss.sina.com.cn/roll/finance/hot_roll.xml"),
]

KEYWORDS = [
    "fed", "powell", "cpi", "ppi", "rate", "treasury", "yield", "inflation", "tariff", "boj", "yen",
    "nvidia", "tsmc", "taiwan", "semiconductor", "chip", "ai", "apple", "microsoft", "google", "meta",
    "amazon", "tesla", "broadcom", "asml", "amd", "intel", "server", "oil", "copper", "gold",
    "美聯儲", "降息", "升息", "通膨", "關稅", "輝達", "英偉達", "台積電", "半導體", "芯片", "晶片",
    "蘋果", "特斯拉", "微軟", "谷歌", "服務器", "伺服器", "原油", "匯率", "美股", "納指", "費半"
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
    news_text = "\n".join(
        [f"- [{c['source']}] {c['title']} ({c['pub_date']})" for c in candidates]
    )

    prompt = f"""
    你是一位資深的台股自營部宏觀與供應鏈研究員。請從以下最新國際財經快訊中，篩選出對「台股開盤走勢、權值股、AI伺服器(鴻海/廣達/緯穎/光寶科)、重電(華城)、被動元件(國巨)或金融股」具有【4星或5星重大影響】的新聞（1~3星瑣碎消息請直接忽略）。

    請嚴格輸出合法 JSON 格式（不要包含 markdown 標記或額外文字）：
    {{
      "has_major_news": true 或 false,
      "max_score": 1到5的整數,
      "sentiment": "強烈利多" 或 "偏多" 或 "中性觀望" 或 "偏空" 或 "重大利空",
      "headline": "20字以內的繁體中文震撼主標題（適合當短影音封面標題）",
      "affected_sectors": "受影響台股族群與代表性個股（例如：AI伺服器/鴻海、廣達；或半導體設備）",
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
