import json
import datetime
from datetime import timezone, timedelta
import re
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# 일본어 표기(히라가나/한자) 대응 매핑 테이블
ZODIAC_NAME_MAP = {
    "おひつじ": "양자리", "牡羊": "양자리",
    "おうし": "황소자리", "牡牛": "황소자리",
    "ふたご": "쌍둥이자리", "双子": "쌍둥이자리",
    "かに": "게자리", "蟹": "게자리",
    "しし": "사자자리", "獅子": "사자자리",
    "おとめ": "처녀자리", "乙女": "처녀자리",
    "てんびん": "천칭자리", "天秤": "천칭자리",
    "さそり": "전갈자리", "蠍": "전갈자리",
    "いて": "사수자리", "射手": "사수자리",
    "やぎ": "염소자리", "山羊": "염소자리",
    "みずがめ": "물병자리", "水瓶": "물병자리",
    "うお": "물고기자리", "魚": "물고기자리"
}

def translate_to_korean(text: str, translator: GoogleTranslator) -> str:
    if not text:
        return ""
    try:
        translated = translator.translate(text.strip())
        return translated if translated else text.strip()
    except Exception as e:
        print(f"번역 경고: {e}")
        return text.strip()

def scrape_ohaasa_exact():
    url = "https://www.asahi.co.jp/ohaasa/week/horoscope/index.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=20)
    response.encoding = "utf-8"
    
    if response.status_code != 200:
        raise RuntimeError(f"사이트 응답 오류: {response.status_code}")
        
    soup = BeautifulSoup(response.text, "html.parser")
    translator = GoogleTranslator(source="ja", target="ko")
    
    rankings = []
    
    # 1. 별자리 카드별 공통 부모 요소 탐색
    names = soup.select(".horo-name")
    ranks = soup.select(".horo-rank")
    txts = soup.select(".horo-txt")
    
    # 개별 항목 개수 기반 매핑
    total_count = min(len(names), len(ranks), len(txts))
    
    if total_count > 0:
        for i in range(total_count):
            name_text = names[i].get_text().strip()
            rank_text = ranks[i].get_text().strip()
            desc_text = txts[i].get_text().strip()
            
            # 별자리 매칭
            matched_sign = None
            for ja_key, ko_val in ZODIAC_NAME_MAP.items():
                if ja_key in name_text:
                    matched_sign = ko_val
                    break
                    
            if not matched_sign:
                continue
                
            # 순위 숫자 추출
            rank_digits = re.findall(r'\d+', rank_text)
            rank_num = int(rank_digits[0]) if rank_digits else (i + 1)
            
            # 본문 한글 번역
            korean_desc = translate_to_korean(desc_text, translator)
            
            rankings.append({
                "sign": matched_sign,
                "rank": rank_num,
                "luckyColor": "-",
                "luckyItem": "-",
                "description": korean_desc if korean_desc else "오늘 하루도 활기차게 보내세요!"
            })
    else:
        # 부모 블록을 순회하는 fallback 방식
        cards = soup.find_all(lambda tag: tag.find(class_="horo-name") is not None)
        for idx, card in enumerate(cards):
            name_elem = card.find(class_="horo-name")
            rank_elem = card.find(class_="horo-rank")
            txt_elem = card.find(class_="horo-txt")
            
            if not name_elem:
                continue
                
            name_text = name_elem.get_text().strip()
            matched_sign = None
            for ja_key, ko_val in ZODIAC_NAME_MAP.items():
                if ja_key in name_text:
                    matched_sign = ko_val
                    break
                    
            if not matched_sign:
                continue
                
            rank_num = idx + 1
            if rank_elem:
                rank_digits = re.findall(r'\d+', rank_elem.get_text())
                if rank_digits:
                    rank_num = int(rank_digits[0])
                    
            desc_raw = txt_elem.get_text().strip() if txt_elem else ""
            korean_desc = translate_to_korean(desc_raw, translator)
            
            rankings.append({
                "sign": matched_sign,
                "rank": rank_num,
                "luckyColor": "-",
                "luckyItem": "-",
                "description": korean_desc if korean_desc else "긍정적인 마음으로 하루를 보내세요."
            })
            
    # 순위 오름차순 정렬
    rankings.sort(key=lambda x: x["rank"])
    return rankings

def main():
    kst = timezone(timedelta(hours=9))
    today_str = datetime.datetime.now(kst).strftime("%Y-%m-%d")
    
    print(f"[{today_str}] 오하아사 운세 데이터를 수집합니다...")
    rankings = scrape_ohaasa_exact()
    
    payload = {
        "date": today_str,
        "rankings": rankings
    }
    
    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        
    print(f"[{today_str}] today.json 생성이 완료되었습니다. (추출된 별자리: {len(rankings)} 개)")

if __name__ == "__main__":
    main()
