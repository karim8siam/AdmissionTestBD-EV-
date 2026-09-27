import json
import os
import urllib.parse
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = "/Users/karimsiam/.gemini/antigravity/scratch/admission-test-bd-ev"
UI_FILE = os.path.join(BASE_DIR, "ui_bn_phrases.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "ui_translations.json")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': '*/*',
}

def translate_single(text, max_retries=3):
    if not text or not isinstance(text, str):
        return None
    t = text.strip()
    if not t or t.isascii():
        return t

    for _ in range(max_retries):
        try:
            url = 'https://translate.googleapis.com/translate_a/single?client=dict-chrome-ex&sl=bn&tl=en&dt=t&q=' + urllib.parse.quote(t)
            r = requests.get(url, headers=HEADERS, timeout=6)
            if r.status_code == 200:
                res = ''.join([part[0] for part in r.json()[0] if part and part[0]]).strip()
                if res and res != t:
                    return res
        except Exception:
            time.sleep(0.3)

    try:
        url = f'https://api.mymemory.translated.net/get?q={urllib.parse.quote(t)}&langpair=bn|en'
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            res = r.json().get('responseData', {}).get('translatedText', '').strip()
            if res and res != t:
                return res
    except Exception:
        pass

    return None

def main():
    if not os.path.exists(UI_FILE):
        print("No UI file found.")
        return

    with open(UI_FILE, 'r', encoding='utf-8') as f:
        phrases = [line.strip() for line in f if line.strip()]

    translations = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                translations = json.load(f)
        except Exception:
            pass

    needed = [p for p in phrases if p not in translations or translations[p] == p]
    print(f"Total UI phrases: {len(phrases)}, Already translated: {len(translations)}, Needed: {len(needed)}")

    if not needed:
        print("All UI phrases already translated.")
        return

    completed = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(translate_single, text): text for text in needed}
        for future in as_completed(futures):
            text = futures[future]
            try:
                res = future.result()
                if res and res != text:
                    translations[text] = res
            except Exception:
                pass
            completed += 1
            if completed % 50 == 0 or completed == len(needed):
                print(f"UI Translation Progress: {completed}/{len(needed)} ({completed*100//len(needed)}%)")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)

    print(f"✓ Saved {len(translations)} UI translations to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
