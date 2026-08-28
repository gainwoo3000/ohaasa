import json
import datetime
from datetime import timezone, timedelta
import re
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# 12개 일본어 별자리 키워드 매핑
ZODIAC_MAP = {
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

def translate_safe(text: str, translator: GoogleTranslator) -> str:
    if not text:
        return ""
    try:
        res = translator.translate(text.strip())
        return res if res else text.strip()
    except Exception as e:
        print(f"번역 오류 ({text}): {e}")
        return text.strip()

def parse_ohaasa_stream():
    url = "https://www.asahi.co.jp/ohaasa/week/horoscope/index.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=20)
    response.encoding = "utf-8"
    
    if response.status_code != 200:
        raise RuntimeError(f"웹사이트 접속 실패 (상태 코드: {response.status_code})")
        
    soup = BeautifulSoup(response.text, "html.parser")
    
    # script, style 태그 제거 후 순수 텍스트 추출
    for tag in soup(["script", "style", "header", "footer", "nav"]):
        tag.decompose()
        
    full_text = soup.get_text(separator="\n")
    lines = [re.sub(r'\s+', ' ', line).strip() for line in full_text.split("\n") if line.strip()]
    
    translator = GoogleTranslator(source="ja", target="ko")
    rankings = []
    
    # 텍스트 전체에서 각 별자리가 등장하는 줄 번호(인덱스) 수집
    zodiac_indices = []
    for idx, line in enumerate(lines):
        for ja_name, ko_name in ZODIAC_MAP.items():
            if ja_name in line:
                zodiac_indices.append((idx, ja_name, ko_name))
                break
                
    # 별자리 간 구간을 분할하여 상세 정보 파싱
    for i, (start_idx, ja_sign, ko_sign) in enumerate(zodiac_indices):
        end_idx = zodiac_indices[i + 1][0] if i + 1 < len(zodiac_indices) else min(start_idx + 15, len(lines))
        chunk_lines = lines[start_idx:end_idx]
        chunk_text = " ".join(chunk_lines)
        
        # 1. 순위 파싱 (1~12위)
        rank = i + 1
        rank_match = re.search(r'([1-9]|1[0-2])\s*位', chunk_text)
        if rank_match:
            rank = int(rank_match.group(1))
        else:
            num_match = re.search(r'\b([1-9]|1[0-2])\b', chunk_lines[0])
            if num_match:
                rank = int(num_match.group(1))
                
        # 2. 행운색 / 행운 아이템 파싱
        lucky_color_raw = ""
        lucky_item_raw = ""
        desc_candidates = []
        
        for line in chunk_lines:
            if "ラッキーカラー" in line:
                lucky_color_raw = re.sub(r'.*ラッキーカラー[:：\s]*', '', line).strip()
            elif "ラッキーアイテム" in line:
                lucky_item_raw = re.sub(r'.*ラッキーアイテム[:：\s]*', '', line).strip()
            elif not any(k in line for k in list(ZODIAC_MAP.keys()) + ["位", "占い", "Horoscope", "朝日"]):
                if len(line) >= 8:
                    desc_candidates.append(line)
                    
        # 3. 운세 설명 문구 선정
        description_raw = desc_candidates[0] if desc_candidates else "기분 좋은 하루를 보내세요."
        
        # 한국어 번역
        lucky_color = translate_safe(lucky_color_raw, translator) if lucky_color_raw else "행운색"
        lucky_item = translate_safe(lucky_item_raw, translator) if lucky_item_raw else "행운 아이템"
        description = translate_safe(description_raw, translator)
        
        rankings.append({
            "sign": ko_sign,
            "rank": rank,
            "luckyColor": lucky_color,
            "luckyItem": lucky_item,
            "description": description
        })
        
    rankings.sort(key=lambda x: x["rank"])
    return rankings

def main():
    kst = timezone(timedelta(hours=9))
    today_str = datetime.datetime.now(kst).strftime("%Y-%m-%d")
    
    print("아사히 방송 오하아사 운세 데이터를 수집합니다...")
    try:
        rankings = parse_ohaasa_stream()
    except Exception as e:
        print(f"파싱 실패: {e}")
        return

    payload = {
        "date": today_str,
        "rankings": rankings
    }

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[{today_str}] 크롤링 성공 (총 {len(rankings)} 개 별자리 저장 완료)")

if __name__ == "__main__":
    main()
