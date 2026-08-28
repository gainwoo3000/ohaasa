import json
import datetime
from datetime import timezone, timedelta
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

ZODIAC_NAME_MAP = {
    "おひつじ座": "양자리",
    "おうし座": "황소자리",
    "ふたご座": "쌍둥이자리",
    "かに座": "게자리",
    "しし座": "사자자리",
    "おとめ座": "처녀자리",
    "てんびん座": "천칭자리",
    "さ소리座": "전갈자리",
    "いて座": "사수자리",
    "やぎ座": "염소자리",
    "みずがめ座": "물병자리",
    "うお座": "물고기자리"
}

def translate_to_korean(text: str, translator: GoogleTranslator) -> str:
    if not text:
        return ""
    try:
        return translator.translate(text.strip())
    except Exception:
        return text.strip()

def scrape_ohaasa():
    url = "https://www.asahi.co.jp/ohaasa/week/horoscope/index.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=15)
    response.encoding = "utf-8"
    
    if response.status_code != 200:
        raise RuntimeError(f"사이트 접근 실패: {response.status_code}")
        
    soup = BeautifulSoup(response.text, "html.parser")
    translator = GoogleTranslator(source="ja", target="ko")
    
    rankings = []
    fortune_boxes = soup.select(".horoscope_list li, .rank_box, .horoscope_box")
    if not fortune_boxes:
        fortune_boxes = soup.find_all("div", class_=lambda x: x and "horoscope" in x)
        
    rank_counter = 1
    for box in fortune_boxes:
        text_content = box.get_text()
        
        matched_sign = None
        for ja_name, ko_name in ZODIAC_NAME_MAP.items():
            if ja_name in text_content:
                matched_sign = ko_name
                break
                
        if not matched_sign:
            continue
            
        rank = rank_counter
        rank_elem = box.select_one(".rank, .num")
        if rank_elem and rank_elem.text.strip().isdigit():
            rank = int(rank_elem.text.strip())
            
        lucky_color_raw = ""
        lucky_item_raw = ""
        description_raw = ""
        
        lines = [line.strip() for line in text_content.split("\n") if line.strip()]
        for line in lines:
            if "ラッキーカラー" in line:
                lucky_color_raw = line.replace("ラッキーカラー", "").replace(":", "").replace("：", "").strip()
            elif "ラッキーアイテム" in line:
                lucky_item_raw = line.replace("ラッキーアイテム", "").replace(":", "").replace("：", "").strip()
            elif len(line) > 15 and not any(k in line for k in ["おひつじ", "おうし", "ふたご", "かに", "しし", "おとめ", "てんびん", "さそり", "いて", "やぎ", "みずがめ", "うお"]):
                description_raw = line
                
        lucky_color = translate_to_korean(lucky_color_raw, translator) if lucky_color_raw else "골드"
        lucky_item = translate_to_korean(lucky_item_raw, translator) if lucky_item_raw else "손수건"
        description = translate_to_korean(description_raw, translator) if description_raw else "오늘 하루도 기분 좋고 활기차게 보내세요!"
        
        rankings.append({
            "sign": matched_sign,
            "rank": rank,
            "luckyColor": lucky_color,
            "luckyItem": lucky_item,
            "description": description
        })
        rank_counter += 1

    existing_signs = {item["sign"] for item in rankings}
    for sign in ZODIAC_NAME_MAP.values():
        if sign not in existing_signs:
            rankings.append({
                "sign": sign,
                "rank": len(rankings) + 1,
                "luckyColor": "골드",
                "luckyItem": "손수건",
                "description": f"오늘 {sign} 의 운세입니다. 긍정적인 마음으로 하루를 시작해보세요."
            })
            
    rankings.sort(key=lambda x: x["rank"])
    return rankings

def main():
    kst = timezone(timedelta(hours=9))
    today_str = datetime.datetime.now(kst).strftime("%Y-%m-%d")
    
    try:
        rankings = scrape_ohaasa()
    except Exception as e:
        print(f"오류: {e}")
        return

    payload = {
        "date": today_str,
        "rankings": rankings
    }

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[{today_str}] today.json 생성 완료")

if __name__ == "__main__":
    main()
