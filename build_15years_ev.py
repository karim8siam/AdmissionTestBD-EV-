import os
import json

SOURCE_DIR = "/Users/karimsiam/.gemini/antigravity/scratch/medical-100-test-series/data"
TARGET_DIR = "/Users/karimsiam/.gemini/antigravity/scratch/admission-test-bd-ev/data"
CACHE_FILE = os.path.join(TARGET_DIR, "translation_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def translate_str(text, cache):
    if not text or not isinstance(text, str):
        return text
    t = text.strip()
    if not t or t.isascii():
        return t
    return cache.get(t, t)

def main():
    cache = load_cache()
    print(f"Loaded {len(cache)} cached items.")
    opt_map = {'ক': 'A', 'খ': 'B', 'গ': 'C', 'ঘ': 'D', 'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D'}

    combined = {}
    for fn, stream_name, title_prefix in [
        ('past_15years_medical.json', 'medical', 'Medical Admission Test: Past 15 Years Session'),
        ('past_15years_versity.json', 'versity', 'Varsity & GST Science: Past 15 Years Session')
    ]:
        src_path = os.path.join(SOURCE_DIR, fn)
        if not os.path.exists(src_path):
            continue
        with open(src_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        data_ev = []
        for test in data:
            sess = test.get('session', '')
            t_copy = dict(test)
            t_copy['title'] = f"{title_prefix} {sess}"
            
            qs_ev = []
            for q in test.get('questions', []):
                q_copy = dict(q)
                qt = (q.get('question_bn') or q.get('question') or '').strip()
                q_copy['question_bn'] = qt
                q_copy['question_en'] = translate_str(qt, cache)
                q_copy['question'] = q_copy['question_en']
                
                orig_opts = q.get('options', [q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d')])
                trans_opts = [translate_str(o, cache) if o else '' for o in orig_opts]
                q_copy['options'] = trans_opts
                q_copy['option_a'] = trans_opts[0] if len(trans_opts) > 0 else ''
                q_copy['option_b'] = trans_opts[1] if len(trans_opts) > 1 else ''
                q_copy['option_c'] = trans_opts[2] if len(trans_opts) > 2 else ''
                q_copy['option_d'] = trans_opts[3] if len(trans_opts) > 3 else ''
                
                c_idx = q.get('correct_index', 0)
                q_copy['correct_index'] = c_idx
                orig_opt = q.get('correct_option', 'A')
                q_copy['correct_option'] = opt_map.get(orig_opt, ['A', 'B', 'C', 'D'][c_idx if 0 <= c_idx < 4 else 0])
                
                orig_exp = q.get('explanation', '')
                if orig_exp:
                    exp_trans = translate_str(orig_exp, cache)
                    exp_trans = exp_trans.replace('সঠিক উত্তর', 'Correct Answer').replace('রেফারেন্স:', 'Reference:')
                    q_copy['explanation'] = exp_trans
                    q_copy['explanation_en'] = exp_trans
                
                if q.get('chapter'):
                    q_copy['chapter'] = translate_str(q['chapter'], cache)
                if q.get('subject'):
                    sub = q['subject']
                    if 'জীব' in sub or 'প্রাণি' in sub or 'উদ্ভিদ' in sub: q_copy['subject'] = 'Biology'
                    elif 'রসায়ন' in sub: q_copy['subject'] = 'Chemistry'
                    elif 'পদার্থ' in sub: q_copy['subject'] = 'Physics'
                    elif 'ইংরেজি' in sub: q_copy['subject'] = 'English'
                    elif 'গণিত' in sub: q_copy['subject'] = 'HigherMath'
                    elif 'সাধারণ জ্ঞান' in sub or 'জ্ঞান' in sub: q_copy['subject'] = 'General Knowledge'
                    
                qs_ev.append(q_copy)
                
            t_copy['questions'] = qs_ev
            data_ev.append(t_copy)
            
        target_path = os.path.join(TARGET_DIR, fn)
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(data_ev, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved {len(data_ev)} tests to {target_path}")
        combined[stream_name] = data_ev

    combined_path = os.path.join(TARGET_DIR, 'past_15years_tests.json')
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved combined past 15 years tests to {combined_path}")

if __name__ == '__main__':
    main()
