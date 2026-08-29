import json
import os
import re
import datetime
from datetime import timezone, timedelta
import time
import requests
from bs4 import BeautifulSoup
from deep_translator import DeeplTranslator

# DeepL API 키: 코드에 직접 쓰지 말고 환경 변수로 설정하세요.
#   export DEEPL_API_KEY="your-api-key-here"
# 무료 플랜(Free) 키는 끝에 ":fx"가 붙어있고, 아래 DEEPL_USE_FREE_API=True로 둬야 합니다.
# 유료 플랜(Pro) 키를 쓴다면 False로 바꾸세요.
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")
DEEPL_USE_FREE_API = True

if not DEEPL_API_KEY:
    raise RuntimeError(
        "DEEPL_API_KEY 환경 변수가 설정되어 있지 않습니다. "
        "https://www.deepl.com/ko/pro#developer 에서 발급받은 키를 설정하세요."
    )

URL = "https://www.tv-asahi.co.jp/goodmorning/uranai/"

# 페이지의 id/data-label(로마자 표기) -> 한글 별자리 매핑
ZODIAC_ID_MAP = {
    "ohitsuji": "양자리",
    "ousi": "황소자리",
    "futago": "쌍둥이자리",
    "kani": "게자리",
    "sisi": "사자자리",
    "otome": "처녀자리",
    "tenbin": "천칭자리",
    "sasori": "전갈자리",
    "ite": "사수자리",
    "yagi": "염소자리",
    "mizugame": "물병자리",
    "uo": "물고기자리",
}


def translate_to_korean(text: str, translator: DeeplTranslator, max_retries=3) -> str:
    """호출 지연 및 재시도를 통한 안정적인 한글 번역"""
    if not text:
        return ""
    for attempt in range(max_retries):
        try:
            time.sleep(0.3)  # 속도 제한 방지 딜레이
            translated = translator.translate(text.strip())
            if translated:
                return translated.strip()
        except Exception as e:
            print(f"번역 재시도 ({attempt + 1}/{max_retries}) - {text}: {e}")
            time.sleep(1.0)
    return text.strip()


def fetch_html() -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(URL, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"페이지 요청 실패: {e}") from e

    # 페이지 meta charset이 Shift_JIS로 명시되어 있으므로 명시적으로 지정
    response.encoding = "shift_jis"
    return response.text


def parse_rank_order(soup: BeautifulSoup) -> dict:
    """rank-box 리스트에서 data-label -> 순위(rank-N.png의 N) 매핑 추출"""
    rank_map = {}
    for a in soup.select(".rank-box a[data-label]"):
        label = a.get("data-label")
        img = a.find("img", class_="rank")
        if not img:
            continue
        m = re.search(r"rank-(\d+)", img.get("src", ""))
        if not m:
            continue
        rank_map[label] = int(m.group(1))
    return rank_map


def parse_seiza_box(box) -> tuple:
    """개별 seiza-box에서 (기간, 설명, 럭키컬러, 럭키아이템) 추출"""
    ttl = box.select_one(".seiza-ttl .seiza-txt")
    period = ""
    if ttl:
        period_span = ttl.find("span", class_="period")
        if period_span:
            period = period_span.get_text(strip=True)

    read_area = box.select_one(".read-area")
    description = lucky_color = lucky_key = ""
    if read_area:
        p = read_area.find("p", class_="read")
        if p:
            description = p.get_text(strip=True)

        full_text = read_area.get_text("\n", strip=True)
        m_color = re.search(r"ラッキーカラー\s*[:：]\s*([^\n]+)", full_text)
        if m_color:
            lucky_color = m_color.group(1).strip()
        m_key = re.search(r"幸運のカギ\s*[:：]\s*([^\n]+)", full_text)
        if m_key:
            lucky_key = m_key.group(1).strip()

    return period, description, lucky_color, lucky_key


def scrape_uranai():
    html = fetch_html()
    soup = BeautifulSoup(html, "html.parser")

    rank_map = parse_rank_order(soup)
    if not rank_map:
        raise RuntimeError("순위 목록(.rank-box)을 찾을 수 없습니다. 사이트 구조가 변경되었을 수 있습니다.")

    translator = DeeplTranslator(
        api_key=DEEPL_API_KEY,
        source="ja",
        target="ko",
        use_free_api=DEEPL_USE_FREE_API,
    )

    rankings = []
    for box in soup.select(".seiza-box[id]"):
        label = box.get("id")
        sign = ZODIAC_ID_MAP.get(label)
        if not sign:
            print(f"경고: 알 수 없는 별자리 id '{label}' — 건너뜁니다.")
            continue

        rank_num = rank_map.get(label)
        if rank_num is None:
            print(f"경고: '{label}'의 순위를 찾을 수 없어 건너뜁니다.")
            continue

        period, desc_ja, color_ja, key_ja = parse_seiza_box(box)

        korean_desc = translate_to_korean(desc_ja, translator) or "오늘 하루도 활기차게 보내세요!"
        korean_color = translate_to_korean(color_ja, translator) if color_ja else "-"
        korean_key = translate_to_korean(key_ja, translator) if key_ja else "-"

        rankings.append({
            "sign": sign,
            "rank": rank_num,
            "period": period,
            "luckyColor": korean_color,
            "luckyItem": korean_key,
            "description": korean_desc,
        })

    rankings.sort(key=lambda x: x["rank"])
    return rankings


def main():
    kst = timezone(timedelta(hours=9))
    today_str = datetime.datetime.now(kst).strftime("%Y-%m-%d")

    print(f"[{today_str}] 굿모닝 별자리 운세 수집 및 번역을 시작합니다...")

    try:
        rankings = scrape_uranai()
    except RuntimeError as e:
        print(f"수집 실패: {e}")
        return

    payload = {
        "date": today_str,
        "rankings": rankings,
    }

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[{today_str}] today.json 저장 완료 (총 {len(rankings)} 개 별자리)")


if __name__ == "__main__":
    main()
