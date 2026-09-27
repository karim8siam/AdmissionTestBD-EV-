import json
import os
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
SOURCE_DATA_DIR = '/Users/karimsiam/.gemini/antigravity/scratch/medical-100-test-series/data'
CACHE_FILE = os.path.join(DATA_DIR, 'translation_cache.json')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': '*/*',
}

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                c = json.load(f)
                return {k: v for k, v in c.items() if k != v and v and not v.strip() == k.strip()}
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

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
                if res and res != t:
                    return res
        except Exception:
            time.sleep(0.3)
            
    # 2. Fallback MyMemory
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

def batch_translate(texts_to_translate, cache, max_workers=8):
    unique_texts = list(set([t.strip() for t in texts_to_translate if t and isinstance(t, str) and not t.strip().isascii()]))
    needed = [t for t in unique_texts if t not in cache]
    print(f"Total non-ASCII texts: {len(unique_texts)}, Already Cached: {len(unique_texts) - len(needed)}, Needed: {len(needed)}")
    
    if not needed:
        return cache
    
    completed = 0
    total = len(needed)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_text = {executor.submit(translate_single, text): text for text in needed}
        for future in as_completed(future_to_text):
            text = future_to_text[future]
            try:
                res = future.result()
                if res and res != text:
                    cache[text] = res
            except Exception:
                pass
            completed += 1
            if completed % 100 == 0 or completed == total:
                print(f"  Progress: {completed}/{total} ({completed*100//total}%) - Valid cache: {len(cache)}")
                save_cache(cache)
    
    save_cache(cache)
    return cache

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    cache = load_cache()
    print(f"Starting with {len(cache)} pre-verified cached items.")
    
    print("Loading source Medical & Versity 100 test datasets...")
    with open(os.path.join(SOURCE_DATA_DIR, 'medical_100_tests.json'), 'r', encoding='utf-8') as f:
        med_tests = json.load(f)
    with open(os.path.join(SOURCE_DATA_DIR, 'versity_100_tests.json'), 'r', encoding='utf-8') as f:
        var_tests = json.load(f)
        
    all_texts = []
    
    # Collect all question texts, options, chapters, and book references
    for dataset in [med_tests, var_tests]:
        for t in dataset:
            for q in t.get('questions', []):
                q_text = q.get('question_bn') or q.get('question')
                if q_text:
                    all_texts.append(q_text)
                for opt in q.get('options', []):
                    if opt:
                        all_texts.append(opt)
                if q.get('chapter'):
                    all_texts.append(q.get('chapter'))
                if q.get('sub_discipline'):
                    all_texts.append(q.get('sub_discipline'))
                if q.get('book_reference'):
                    all_texts.append(q.get('book_reference'))
    
    cache = batch_translate(all_texts, cache, max_workers=8)
    
    # Helper to map option letter
    opt_letter_map = {'ক': 'A', 'খ': 'B', 'গ': 'C', 'ঘ': 'D', 'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D'}
    
    # Function to translate a test question
    def transform_question(q):
        q_copy = dict(q)
        q_text = (q.get('question_bn') or q.get('question') or '').strip()
        q_copy['question_bn'] = q_text
        q_copy['question_en'] = cache.get(q_text, q_text)
        q_copy['question'] = q_copy['question_en']
        
        orig_opts = q.get('options', [q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d')])
        trans_opts = [cache.get(opt.strip(), opt.strip()) if opt else '' for opt in orig_opts]
        q_copy['options'] = trans_opts
        q_copy['option_a'] = trans_opts[0] if len(trans_opts) > 0 else ''
        q_copy['option_b'] = trans_opts[1] if len(trans_opts) > 1 else ''
        q_copy['option_c'] = trans_opts[2] if len(trans_opts) > 2 else ''
        q_copy['option_d'] = trans_opts[3] if len(trans_opts) > 3 else ''
        
        correct_idx = q.get('correct_index', 0)
        q_copy['correct_index'] = correct_idx
        orig_opt_letter = q.get('correct_option', 'A')
        q_copy['correct_option'] = opt_letter_map.get(orig_opt_letter, ['A', 'B', 'C', 'D'][correct_idx if 0 <= correct_idx < 4 else 0])
        
        # Build clean academic English explanation
        correct_ans_text = trans_opts[correct_idx] if 0 <= correct_idx < len(trans_opts) else ''
        orig_ref = q.get('book_reference', '')
        trans_ref = cache.get(orig_ref.strip(), orig_ref.strip()) if orig_ref else ''
        q_copy['book_reference'] = trans_ref
        q_copy['book_reference_en'] = trans_ref
        q_copy['explanation'] = f"Correct Answer ({q_copy['correct_option']}): {correct_ans_text}. Reference: {trans_ref}."
        q_copy['explanation_en'] = q_copy['explanation']
            
        if q.get('chapter'):
            q_copy['chapter'] = cache.get(q['chapter'].strip(), q['chapter'].strip())
        if q.get('sub_discipline'):
            q_copy['sub_discipline'] = cache.get(q['sub_discipline'].strip(), q['sub_discipline'].strip())
            
        return q_copy

    print("Transforming Medical 100 Tests to English Version...")
    med_ev = []
    for t in med_tests:
        t_id = t.get('test_id', 1)
        med_ev.append({
            'test_id': t_id,
            'test_code': f"MED-{t_id:03d}",
            'test_name': f"Medical Full Model Test {t_id:02d}",
            'test_name_bn': f"Medical Full Model Test {t_id:02d}",
            'stream': 'medical',
            'total_questions': len(t.get('questions', [])),
            'duration_minutes': 60,
            'questions': [transform_question(q) for q in t.get('questions', [])]
        })
    with open(os.path.join(DATA_DIR, 'medical_100_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(med_ev, f, ensure_ascii=False, indent=2)
    print("✓ medical_100_tests.json created successfully!")

    print("Transforming Versity 100 Tests to English Version...")
    var_ev = []
    for t in var_tests:
        t_id = t.get('test_id', 1)
        var_ev.append({
            'test_id': t_id,
            'test_code': f"VAR-{t_id:03d}",
            'test_name': f"Varsity & GST Model Test {t_id:02d}",
            'test_name_bn': f"Varsity & GST Model Test {t_id:02d}",
            'stream': 'versity',
            'total_questions': len(t.get('questions', [])),
            'duration_minutes': 60,
            'questions': [transform_question(q) for q in t.get('questions', [])]
        })
    with open(os.path.join(DATA_DIR, 'versity_100_tests.json'), 'w', encoding='utf-8') as f:
        json.dump(var_ev, f, ensure_ascii=False, indent=2)
    print("✓ versity_100_tests.json created successfully!")

if __name__ == '__main__':
    main()
