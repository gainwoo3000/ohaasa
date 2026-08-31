import json
import os
import re
import sys
import datetime
from datetime import timezone, timedelta
import time
import requests
from bs4 import BeautifulSoup

# DeepL API 키: 코드에 직접 쓰지 말고 환경 변수로 설정하세요.
#   export DEEPL_API_KEY="your-api-key-here"
# 무료 플랜(Free) 키는 끝에 ":fx"가 붙어있고, 아래 DEEPL_USE_FREE_API=True로 둬야 합니다.
# 유료 플랜(Pro) 키를 쓴다면 False로 바꾸세요.
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")
DEEPL_USE_FREE_API = True
DEEPL_API_URL = (
    "https://api-free.deepl.com/v2/translate"
    if DEEPL_USE_FREE_API
    else "https://api.deepl.com/v2/translate"
)

if not DEEPL_API_KEY:
    raise RuntimeError(
        "DEEPL_API_KEY 환경 변수가 설정되어 있지 않습니다. "
        "https://www.deepl.com/ko/pro#developer 에서 발급받은 키를 설정하세요."
    )

KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# 평일(월~금) 소스: 오하아사 JSON API
# ---------------------------------------------------------------------------
WEEKDAY_API_URL = "https://www.asahi.co.jp/data/ohaasa2020/horoscope.json"

# horoscope_st 코드 -> 별자리 매핑
# 주의: API 응답 자체에는 코드-별자리 매핑 정보가 없습니다.
# 서양 12궁 순서(おひつじ=01 ... うお=12)를 가정한 것이므로,
# 실제 페이지에서 오늘자 1위 별자리가 어떤 코드로 나오는지 한 번 대조 확인하는 걸 권장합니다.
ZODIAC_ST_MAP = {
    "01": "양자리",
    "02": "황소자리",
    "03": "쌍둥이자리",
    "04": "게자리",
    "05": "사자자리",
    "06": "처녀자리",
    "07": "천칭자리",
    "08": "전갈자리",
    "09": "사수자리",
    "10": "염소자리",
    "11": "물병자리",
    "12": "물고기자리",
}

# ---------------------------------------------------------------------------
# 주말(토~일) 소스: 굿모닝(グッド！モーニング) 페이지
# ---------------------------------------------------------------------------
WEEKEND_URL = "https://www.tv-asahi.co.jp/goodmorning/uranai/"

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


def translate_to_korean(text: str, max_retries=3) -> str:
    """DeepL API를 직접 호출해 일본어 -> 한국어 번역
    (deep_translator 패키지의 DeeplTranslator는 내부 언어 목록이 오래돼
    한국어(ko)를 지원 언어로 인식하지 못하는 버그가 있어 우회함)

    주의: DeepL은 2025년 3월부터 body의 auth_key 파라미터 인증을 지원 중단했고
    2025년 11월에 완전히 제거했습니다. 반드시 Authorization 헤더로 인증해야 합니다.
    https://developers.deepl.com/docs/resources/breaking-changes-change-notices/march-2025-deprecating-get-requests-to-translate-and-authenticating-with-auth_key
    """
    if not text:
        return ""
    headers = {"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"}
    for attempt in range(max_retries):
        try:
            time.sleep(0.3)  # 속도 제한 방지 딜레이
            resp = requests.post(
                DEEPL_API_URL,
                headers=headers,
                data={
                    "text": text.strip(),
                    "source_lang": "JA",
                    "target_lang": "KO",
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            translated = data["translations"][0]["text"]
            if translated:
                return translated.strip()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:200] if e.response is not None else ""
            status = e.response.status_code if e.response is not None else "?"
            print(f"번역 재시도 ({attempt + 1}/{max_retries}) - HTTP {status}: {body}")
            time.sleep(1.0)
        except Exception as e:
            print(f"번역 재시도 ({attempt + 1}/{max_retries}) - {text}: {e}")
            time.sleep(1.0)
    return text.strip()


def is_weekday_kst() -> bool:
    """한국 시간 기준 월(0)~금(4)이면 True, 토(5)/일(6)이면 False"""
    return datetime.datetime.now(KST).weekday() < 5


# ---------------------------------------------------------------------------
# 평일: JSON API 파싱
# ---------------------------------------------------------------------------
def fetch_weekday_json():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(WEEKDAY_API_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"오하아사 API 요청 실패: {e}") from e

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"오하아사 API 응답이 JSON이 아닙니다: {e}") from e

    if not data:
        raise RuntimeError("오하아사 API 응답이 비어 있습니다.")

    return data[0].get("detail", [])


def parse_horoscope_text(raw_text: str):
    """tab(\t)으로 구분된 텍스트를 (설명, 럭키항목) 튜플로 분리"""
    parts = [p.strip() for p in raw_text.split("\t") if p.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    description_parts, lucky = parts[:-1], parts[-1]
    return " ".join(description_parts), lucky


def scrape_weekday():
    details = fetch_weekday_json()

    rankings = []
    for item in details:
        st_code = item.get("horoscope_st", "")
        sign = ZODIAC_ST_MAP.get(st_code)
        if not sign:
            print(f"경고: 알 수 없는 horoscope_st 코드 '{st_code}' — 건너뜁니다.")
            continue

        rank_raw = item.get("ranking_no", "")
        try:
            rank_num = int(rank_raw)
        except (TypeError, ValueError):
            print(f"경고: ranking_no '{rank_raw}'를 숫자로 변환할 수 없어 건너뜁니다.")
            continue

        raw_text = item.get("horoscope_text", "")
        desc_ja, lucky_ja = parse_horoscope_text(raw_text)

        korean_desc = translate_to_korean(desc_ja) or "오늘 하루도 활기차게 보내세요!"
        # 이 소스는 럭키컬러/아이템이 분리되어 있지 않고 한 필드에 섞여 있어
        # luckyItem에만 채우고 luckyColor는 "-"로 둔다.
        korean_lucky = translate_to_korean(lucky_ja) if lucky_ja else "-"

        rankings.append({
            "sign": sign,
            "rank": rank_num,
            "period": "",
            "luckyColor": "-",
            "luckyItem": korean_lucky,
            "description": korean_desc,
        })

    rankings.sort(key=lambda x: x["rank"])
    return rankings


# ---------------------------------------------------------------------------
# 주말: HTML 파싱
# ---------------------------------------------------------------------------
def fetch_weekend_html() -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(WEEKEND_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"페이지 요청 실패: {e}") from e

    # 인코딩을 임의로 단정하지 않고 원본 바이트를 그대로 반환.
    # BeautifulSoup(UnicodeDammit)이 바이트에서 직접 감지하도록 둔다.
    return response.content


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


def scrape_weekend():
    html = fetch_weekend_html()
    soup = BeautifulSoup(html, "html.parser")

    rank_map = parse_rank_order(soup)
    if not rank_map:
        raise RuntimeError("순위 목록(.rank-box)을 찾을 수 없습니다. 사이트 구조가 변경되었을 수 있습니다.")

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

        korean_desc = translate_to_korean(desc_ja) or "오늘 하루도 활기차게 보내세요!"
        korean_color = translate_to_korean(color_ja) if color_ja else "-"
        korean_key = translate_to_korean(key_ja) if key_ja else "-"

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


# ---------------------------------------------------------------------------
# 공통 진입점
# ---------------------------------------------------------------------------
def scrape_uranai():
    if is_weekday_kst():
        print("평일(월~금) — 오하아사 JSON API에서 수집합니다.")
        return scrape_weekday()
    else:
        print("주말(토~일) — 굿모닝 페이지에서 수집합니다.")
        return scrape_weekend()


def main():
    today_str = datetime.datetime.now(KST).strftime("%Y-%m-%d")

    print(f"[{today_str}] 별자리 운세 수집 및 번역을 시작합니다...")

    try:
        rankings = scrape_uranai()
    except RuntimeError as e:
        print(f"수집 실패: {e}")
        sys.exit(1)  # CI에서 이 실행을 실패로 표시하기 위함

    payload = {
        "date": today_str,
        "rankings": rankings,
    }

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[{today_str}] today.json 저장 완료 (총 {len(rankings)} 개 별자리)")


if __name__ == "__main__":
    main()
