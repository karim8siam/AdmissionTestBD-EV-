import json
import os
import re
import urllib.parse
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

EV_DIR = "/Users/karimsiam/.gemini/antigravity/scratch/admission-test-bd-ev"
CACHE_FILE = os.path.join(EV_DIR, "data", "translation_cache.json")
MISSING_FILE = os.path.join(EV_DIR, "data", "missing_translations.json")

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

    # 1. Google Translate dict-chrome-ex
    for attempt in range(max_retries):
        try:
            url = 'https://translate.googleapis.com/translate_a/single?client=dict-chrome-ex&sl=bn&tl=en&dt=t&q=' + urllib.parse.quote(t)
            r = requests.get(url, headers=HEADERS, timeout=6)
            if r.status_code == 200:
                res = ''.join([part[0] for part in r.json()[0] if part and part[0]]).strip()
                if res and res != t and not re.search(r'[\u0980-\u09FF]', res):
                    return res
        except Exception:
            time.sleep(0.3)

    # 2. Fallback MyMemory
    try:
        url = f'https://api.mymemory.translated.net/get?q={urllib.parse.quote(t)}&langpair=bn|en'
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            res = r.json().get('responseData', {}).get('translatedText', '').strip()
            if res and res != t and not re.search(r'[\u0980-\u09FF]', res):
                return res
    except Exception:
        pass

    return None

def translate_all_missing():
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    with open(MISSING_FILE, 'r', encoding='utf-8') as f:
        missing = json.load(f)

    to_fetch = [s for s in missing if s not in cache or cache[s] == s or re.search(r'[\u0980-\u09FF]', cache[s])]
    print(f"Translating {len(to_fetch)} missing strings...")

    completed = 0
    total = len(to_fetch)
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_text = {executor.submit(translate_single, text): text for text in to_fetch}
        for future in as_completed(future_to_text):
            text = future_to_text[future]
            try:
                res = future.result()
                if res and not re.search(r'[\u0980-\u09FF]', res):
                    cache[text] = res
            except Exception:
                pass
            completed += 1
            if completed % 100 == 0 or completed == total:
                print(f"  Progress: {completed}/{total} ({completed*100//total}%) - Total Cache: {len(cache)}")
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print("✓ Cache updated successfully.")
    return cache

def translate_str(text, cache):
    if not text or not isinstance(text, str):
        return text
    t = text.strip()
    if not t or t.isascii():
        return t
    res = cache.get(t)
    if res and not re.search(r'[\u0980-\u09FF]', res):
        return res
    # Fallback dictionary for common phrases
    fallback_map = {
        'জীববিজ্ঞান': 'Biology',
        'রসায়ন': 'Chemistry',
        'পদার্থবিজ্ঞান': 'Physics',
        'উচ্চতর গণিত': 'Higher Mathematics',
        'গণিত': 'Higher Mathematics',
        'ইংরেজি': 'English',
        'সাধারণ জ্ঞান': 'General Knowledge',
        'সঠিক উত্তর': 'Correct Answer',
        'রেফারেন্স:': 'Reference:',
        'অধ্যায়:': 'Chapter:',
        'ড. মোহাম্মদ আবুল হাসান': 'Dr. Mohammad Abul Hasan',
        'গাজী আজমল ও গাজী আসমত': 'Prof. Gazi Azmal & Gazi Asmat',
        'প্রফেসর হাজারী ও নাগ': 'Prof. Hazari & Nag',
        'হাজারী ও নাগ': 'Hazari & Nag',
        'ড. শাহজাহান তপন': 'Dr. Shahjahan Tapan',
        'অসীম কুমার সাহা': 'Asim Kumar Saha',
        'কেতাব উদ্দিন': 'Ketab Uddin',
        'মেডিকেল ভর্তি পরীক্ষা': 'Medical Admission Test',
        'ভার্সিটি ও গুচ্ছ বিজ্ঞান': 'Varsity & GST Science',
        'সংজ্ঞা': 'Definition',
        'গুরুত্বপূর্ণ': 'High-Yield Note',
        'গাণিতিক': 'Formula / Numerical Note',
        'ব্যতিক্রম': 'Exception / Core Principle',
        'সতর্কতা': 'Common Trap'
    }
    for k, v in fallback_map.items():
        t = t.replace(k, v)
    # Remove remaining Bengali characters if any
    t = re.sub(r'[\u0980-\u09FF]+', '', t).strip()
    return t or "NCTB Curriculum Reference"

def clean_past_15years(cache):
    print("Cleaning and applying English to past 15-year datasets...")
    opt_map = {'ক': 'A', 'খ': 'B', 'গ': 'C', 'ঘ': 'D', 'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D'}
    bn_digits = {'০':'0', '১':'1', '২':'2', '৩':'3', '৪':'4', '৫':'5', '৬':'6', '৭':'7', '৮':'8', '৯':'9'}

    combined = {}
    for fn, stream in [('past_15years_medical.json', 'medical'), ('past_15years_versity.json', 'versity')]:
        path = os.path.join(EV_DIR, "data", fn)
        with open(path, 'r', encoding='utf-8') as f:
            tests = json.load(f)

        cleaned_tests = []
        for t in tests:
            t_copy = dict(t)
            sess = t_copy.get('session', '')
            t_copy['title'] = f"{'Medical Admission Test' if stream == 'medical' else 'Varsity & GST Science'}: Past 15 Years Session {sess}"

            cleaned_qs = []
            for q in t.get('questions', []):
                q_copy = dict(q)
                raw_q = (q.get('question_en') or q.get('question') or q.get('question_bn') or '').strip()
                q_en = translate_str(raw_q, cache)
                for bd, ed in bn_digits.items():
                    q_en = q_en.replace(bd, ed)

                q_copy['question'] = q_en
                q_copy['question_en'] = q_en
                q_copy['question_bn'] = q_en # Pure English

                # Options
                opts = []
                for opt in q.get('options', [q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d')]):
                    opt_en = translate_str(str(opt or ''), cache)
                    for bd, ed in bn_digits.items():
                        opt_en = opt_en.replace(bd, ed)
                    opts.append(opt_en)
                q_copy['options'] = opts
                if len(opts) > 0: q_copy['option_a'] = opts[0]
                if len(opts) > 1: q_copy['option_b'] = opts[1]
                if len(opts) > 2: q_copy['option_c'] = opts[2]
                if len(opts) > 3: q_copy['option_d'] = opts[3]

                c_idx = q.get('correct_index', 0)
                q_copy['correct_index'] = c_idx
                q_copy['correct_option'] = opt_map.get(q.get('correct_option', 'A'), ['A', 'B', 'C', 'D'][c_idx if 0 <= c_idx < 4 else 0])

                # Book reference & Explanation
                ref_en = translate_str(q.get('book_reference', ''), cache)
                q_copy['book_reference'] = ref_en
                q_copy['book_reference_en'] = ref_en

                exp_en = translate_str(q.get('explanation', ''), cache)
                correct_ans_text = opts[c_idx] if 0 <= c_idx < len(opts) else ''
                if not exp_en or re.search(r'[\u0980-\u09FF]', exp_en):
                    exp_en = f"Correct Answer ({q_copy['correct_option']}): {correct_ans_text}. Reference: {ref_en}."
                q_copy['explanation'] = exp_en
                q_copy['explanation_en'] = exp_en

                if q.get('chapter'):
                    q_copy['chapter'] = translate_str(q['chapter'], cache)
                if q.get('subject'):
                    sub = q['subject']
                    if 'জীব' in sub or 'প্রাণি' in sub or 'উদ্ভিদ' in sub: q_copy['subject'] = 'Biology'
                    elif 'রসায়ন' in sub: q_copy['subject'] = 'Chemistry'
                    elif 'পদার্থ' in sub: q_copy['subject'] = 'Physics'
                    elif 'ইংরেজি' in sub: q_copy['subject'] = 'English'
                    elif 'গণিত' in sub: q_copy['subject'] = 'Higher Mathematics'
                    elif 'জ্ঞান' in sub: q_copy['subject'] = 'General Knowledge'

                cleaned_qs.append(q_copy)

            t_copy['questions'] = cleaned_qs
            cleaned_tests.append(t_copy)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_tests, f, ensure_ascii=False, indent=2)
        combined[stream] = cleaned_tests
        print(f"✓ Saved cleaned {fn}")

    combined_path = os.path.join(EV_DIR, "data", "past_15years_tests.json")
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print("✓ Saved cleaned past_15years_tests.json")

def clean_textbook_kb(cache):
    print("Cleaning and applying English to medical_textbooks_kb.json...")
    path = os.path.join(EV_DIR, "data", "medical_textbooks_kb.json")
    with open(path, 'r', encoding='utf-8') as f:
        kb = json.load(f)

    cleaned_kb = []
    for fact in kb:
        f_copy = dict(fact)
        for k in ['chapter', 'topic', 'fact_type', 'keywords', 'citation', 'common_mcq_trap', 'author', 'book_name', 'exact_text_bn']:
            v = fact.get(k)
            if v and isinstance(v, str) and re.search(r'[\u0980-\u09FF]', v):
                f_copy[k] = translate_str(v, cache)

        # Ensure exact_text_en is set
        if not f_copy.get('exact_text_en') or re.search(r'[\u0980-\u09FF]', f_copy.get('exact_text_en', '')):
            f_copy['exact_text_en'] = f_copy.get('exact_text_bn', '')
        if not f_copy.get('context_en') or re.search(r'[\u0980-\u09FF]', f_copy.get('context_en', '')):
            f_copy['context_en'] = f_copy.get('exact_text_en', '')

        cleaned_kb.append(f_copy)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_kb, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved cleaned medical_textbooks_kb.json ({len(cleaned_kb)} facts)")

def main():
    cache = translate_all_missing()
    clean_past_15years(cache)
    clean_textbook_kb(cache)

if __name__ == '__main__':
    main()
