import json
import datetime
from datetime import timezone, timedelta
import requests
from deep_translator import GoogleTranslator

# horoscope_st 코드 -> 별자리 매핑
# 주의: API 응답 자체에는 코드-별자리 매핑 정보가 없습니다.
# 서양 12궁 순서(おひつじ=01 ... うお=12)를 가정한 것이므로,
# 실제 페이지(https://www.asahi.co.jp/ohaasa/week/horoscope/index.html)에서
# 오늘자 1위 별자리가 어떤 코드로 나오는지 반드시 한 번 대조 확인하세요.
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

API_URL = "https://www.asahi.co.jp/data/ohaasa2020/horoscope.json"


def translate_to_korean(text: str, translator: GoogleTranslator) -> str:
    if not text:
        return ""
    try:
        translated = translator.translate(text.strip())
        return translated if translated else text.strip()
    except Exception as e:
        print(f"번역 경고: {e}")
        return text.strip()


def fetch_ohaasa_json():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(API_URL, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"오하아사 API 요청 실패: {e}") from e

    # 서버가 명시한 인코딩을 강제로 덮어쓰지 않고 requests가 감지한 값을 사용
    try:
        data = response.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"오하아사 API 응답이 JSON이 아닙니다: {e}") from e

    if not data:
        raise RuntimeError("오하아사 API 응답이 비어 있습니다.")

    return data[0].get("detail", [])


def parse_horoscope_text(raw_text: str):
    """tab으로 구분된 텍스트를 (설명, 럭키아이템) 튜플로 분리"""
    parts = [p.strip() for p in raw_text.split("\t") if p.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    description_parts, lucky = parts[:-1], parts[-1]
    return " ".join(description_parts), lucky


def scrape_ohaasa_exact():
    translator = GoogleTranslator(source="ja", target="ko")
    details = fetch_ohaasa_json()

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

        korean_desc = translate_to_korean(desc_ja, translator) or "오늘 하루도 활기차게 보내세요!"
        korean_lucky = translate_to_korean(lucky_ja, translator) if lucky_ja else "-"

        rankings.append({
            "sign": sign,
            "rank": rank_num,
            # 원본 데이터에 컬러/아이템 구분이 없어 하나의 필드로 통합
            "lucky": korean_lucky,
            "description": korean_desc,
        })

    rankings.sort(key=lambda x: x["rank"])
    return rankings


def main():
    kst = timezone(timedelta(hours=9))
    today_str = datetime.datetime.now(kst).strftime("%Y-%m-%d")

    print(f"[{today_str}] 오하아사 운세 데이터를 수집합니다...")

    try:
        rankings = scrape_ohaasa_exact()
    except RuntimeError as e:
        print(f"수집 실패: {e}")
        return

    payload = {
        "date": today_str,
        "rankings": rankings,
    }

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[{today_str}] today.json 생성이 완료되었습니다. (추출된 별자리: {len(rankings)} 개)")


if __name__ == "__main__":
    main()
