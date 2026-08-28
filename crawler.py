import json
import datetime
from datetime import timezone, timedelta
import requests
from deep_translator import GoogleTranslator

# horoscope_st 코드 매핑 (01: 양자리 ~ 12: 물고기자리)
HOROSCOPE_ST_MAP = {
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
    "12": "물고기자리"
}

# 색상 판별 키워드
COLOR_KEYWORDS = ["色", "ゴールド", "シルバー", "ピンク", "オレンジ", "赤", "青", "黄", "白", "黒", "緑", "紫"]

def translate_safe(text: str, translator: GoogleTranslator) -> str:
    if not text or text == "-":
        return text
    try:
        translated = translator.translate(text.strip())
        return translated if translated else text.strip()
    except Exception as e:
        print(f"번역 경고 ({text}): {e}")
        return text.strip()

def parse_official_json():
    url = "https://www.asahi.co.jp/data/ohaasa2020/horoscope.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=15)
    response.encoding = "utf-8"
    
    if response.status_code != 200:
        raise RuntimeError(f"공식 JSON 호출 실패: 상태 코드 {response.status_code}")
        
    data = response.json()
    if not data or not isinstance(data, list):
        raise ValueError("유효하지 않은 JSON 데이터 구조입니다.")
        
    # 최신 날짜의 운세 항목 (첫 번째 원소)
    latest_data = data[0]
    raw_date = latest_data.get("onair_date", "")
    
    # YYYYMMDD -> YYYY-MM-DD 포맷 변환
    formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else datetime.datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    
    translator = GoogleTranslator(source="ja", target="ko")
    rankings = []
    
    for item in latest_data.get("detail", []):
        st_code = item.get("horoscope_st", "")
        sign_name = HOROSCOPE_ST_MAP.get(st_code, "알 수 없음")
        rank_no = int(item.get("ranking_no", 0))
        text_raw = item.get("horoscope_text", "")
        
        # 탭(\t) 구분자로 문장 및 행운 정보 분리
        tokens = [t.strip() for t in text_raw.split("\t") if t.strip()]
        
        description_ja = ""
        lucky_target_ja = ""
        
        if len(tokens) >= 2:
            description_ja = " ".join(tokens[:-1])
            lucky_target_ja = tokens[-1]
        elif len(tokens) == 1:
            description_ja = tokens[0]
            
        # 마지막 토큰이 색상인지 아이템인지 판별
        lucky_color_raw = "-"
        lucky_item_raw = "-"
        
        if lucky_target_ja:
            if any(k in lucky_target_ja for k in COLOR_KEYWORDS):
                lucky_color_raw = lucky_target_ja
            else:
                lucky_item_raw = lucky_target_ja
                
        # 한국어로 번역
        description_ko = translate_safe(description_ja, translator)
        lucky_color_ko = translate_safe(lucky_color_raw, translator) if lucky_color_raw != "-" else "-"
        lucky_item_ko = translate_safe(lucky_item_raw, translator) if lucky_item_raw != "-" else "-"
        
        rankings.append({
            "sign": sign_name,
            "rank": rank_no,
            "luckyColor": lucky_color_ko,
            "luckyItem": lucky_item_ko,
            "description": description_ko
        })
        
    rankings.sort(key=lambda x: x["rank"])
    return formatted_date, rankings

def main():
    print("아사히 공식 JSON 데이터를 수집 및 가공합니다...")
    try:
        date_str, rankings = parse_official_json()
    except Exception as e:
        print(f"오류 발생: {e}")
        return

    payload = {
        "date": date_str,
        "rankings": rankings
    }

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[{date_str}] today.json 생성이 완료되었습니다. (총 {len(rankings)} 개 별자리)")

if __name__ == "__main__":
    main()
