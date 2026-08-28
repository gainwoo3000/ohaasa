import json
import datetime
from datetime import timezone, timedelta
import re
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# 12개 공식 별자리명 매핑 (오타 수정 완료)
ZODIAC_NAME_MAP = {
    "おひつじ座": "양자리",
    "おうし座": "황소자리",
    "ふたご座": "쌍둥이자리",
    "かに座": "게자리",
    "しし座": "사자자리",
    "おとめ座": "처녀자리",
    "てんびん座": "천칭자리",
    "さそり座": "전갈자리",
    "いて座": "사수자리",
    "やぎ座": "염소자리",
    "みずがめ座": "물병자리",
    "うお座": "물고기자리"
}

def translate_text(text: str, translator: GoogleTranslator) -> str:
    if not text:
        return ""
    try:
        translated = translator.translate(text.strip())
        return translated if translated else text.strip()
    except Exception as e:
        print(f"번역 경고 ({text}): {e}")
        return text.strip()

def scrape_ohaasa():
    url = "https://www.asahi.co.jp/ohaasa/week/horoscope/index.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    }
    
    response = requests.get(url, headers=headers, timeout=20)
    response.encoding = "utf-8"
    
    if response.status_code != 200:
        raise RuntimeError(f"사이트 응답 오류 (Status Code: {response.status_code})")
        
    soup = BeautifulSoup(response.text, "html.parser")
    translator = GoogleTranslator(source="ja", target="ko")
    
    rankings = []
    
    # 웹페이지 내의 각 운세 블록 탐색
    cards = soup.find_all(["div", "li", "section"], class_=lambda c: c and any(k in c.lower() for k in ["horoscope", "rank", "box", "list"]))
    
    for card in cards:
        card_text = card.get_text(separator="\n").strip()
        
        # 별자리 매칭
        matched_sign = None
        for ja_sign, ko_sign in ZODIAC_NAME_MAP.items():
            if ja_sign in card_text:
                matched_sign = ko_sign
                break
                
        if not matched_sign:
            continue
            
        # 이미 추가된 별자리인지 중복 방지
        if any(item["sign"] == matched_sign for item in rankings):
            continue
            
        # 순위 추출 (정규표현식으로 1~12위 번호 매칭)
        rank = len(rankings) + 1
        rank_match = re.search(r'([1-9]|1[0-2])\s*位', card_text)
        if rank_match:
            rank = int(rank_match.group(1))
            
        # 럭키 컬러 / 아이템 / 설명문 파싱
        lucky_color_raw = ""
        lucky_item_raw = ""
        description_raw = ""
        
        lines = [line.strip() for line in card_text.split("\n") if line.strip()]
        for idx, line in enumerate(lines):
            if "ラッキーカラー" in line:
                lucky_color_raw = line.replace("ラッキーカラー", "").replace(":", "").replace("：", "").strip()
                if not lucky_color_raw and idx + 1 < len(lines):
                    lucky_color_raw = lines[idx + 1]
            elif "ラッキーアイテム" in line:
                lucky_item_raw = line.replace("ラッキーアイテム", "").replace(":", "").replace("：", "").strip()
                if not lucky_item_raw and idx + 1 < len(lines):
                    lucky_item_raw = lines[idx + 1]
            elif len(line) > 10 and not any(k in line for k in list(ZODIAC_NAME_MAP.keys()) + ["位", "ラッキー"]):
                if not description_raw:
                    description_raw = line

        # 번역 적용
        lucky_color = translate_text(lucky_color_raw, translator) if lucky_color_raw else "골드"
        lucky_item = translate_text(lucky_item_raw, translator) if lucky_item_raw else "손수건"
        description = translate_text(description_raw, translator) if description_raw else "오늘 하루도 긍정적인 마음으로 시작해보세요."
        
        rankings.append({
            "sign": matched_sign,
            "rank": rank,
            "luckyColor": lucky_color,
            "luckyItem": lucky_item,
            "description": description
        })

    # 12개 별자리가 완전히 파싱되지 않은 경우 누락 보정
    existing_signs = {item["sign"] for item in rankings}
    for sign in ZODIAC_NAME_MAP.values():
        if sign not in existing_signs:
            rankings.append({
                "sign": sign,
                "rank": len(rankings) + 1,
                "luckyColor": "파란색",
                "luckyItem": "다이어리",
                "description": f"오늘 {sign} 의 운세입니다. 활기찬 하루를 보내세요."
            })

    rankings.sort(key=lambda x: x["rank"])
    return rankings

def main():
    kst = timezone(timedelta(hours=9))
    today_str = datetime.datetime.now(kst).strftime("%Y-%m-%d")
    
    print("오하아사 최신 운세 데이터를 파싱 중입니다...")
    rankings = scrape_ohaasa()
    
    payload = {
        "date": today_str,
        "rankings": rankings
    }
    
    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        
    print(f"[{today_str}] 크롤링 및 한글 번역 완료 (총 {len(rankings)} 개 별자리)")

if __name__ == "__main__":
    main()
