import json
import re

EV_DIR = "/Users/karimsiam/.gemini/antigravity/scratch/admission-test-bd-ev"

def clean_dataset(filename):
    filepath = f"{EV_DIR}/data/{filename}"
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    burette_en = "What is the minimum volume that can be measured with a burette? [D.V.P. 17-18]"
    burette_ref_en = "Hazari & Nag, Higher Secondary Chemistry 1st Paper"

    cleaned_tests = []
    for test in data:
        t_copy = dict(test)
        # Ensure test name and name_bn are pure English
        t_copy['test_name'] = t_copy.get('test_name', '').replace('মডেল টেস্ট', 'Model Test')
        t_copy['test_name_bn'] = t_copy['test_name']

        cleaned_qs = []
        for q in test.get('questions', []):
            q_copy = dict(q)
            q_text = q_copy.get('question_en') or q_copy.get('question') or ''
            if 'ব্যুরেটের সাহায্যে' in q_text:
                q_text = burette_en
                q_copy['explanation'] = "Correct Answer (B): 0.1 mL. Reference: Hazari & Nag, Higher Secondary Chemistry 1st Paper."
                q_copy['book_reference'] = burette_ref_en

            # Remove any lingering Bengali digits in question text
            bn_digits = {'০':'0', '১':'1', '২':'2', '৩':'3', '৪':'4', '৫':'5', '৬':'6', '৭':'7', '৮':'8', '৯':'9'}
            for bd, ed in bn_digits.items():
                q_text = q_text.replace(bd, ed)

            q_copy['question'] = q_text
            q_copy['question_en'] = q_text
            # Crucial: set question_bn to English so no template can ever accidentally render Bengali!
            q_copy['question_bn'] = q_text

            # Clean options
            opts = []
            for opt in q_copy.get('options', []):
                opt_str = str(opt)
                for bd, ed in bn_digits.items():
                    opt_str = opt_str.replace(bd, ed)
                opts.append(opt_str)
            q_copy['options'] = opts
            if len(opts) > 0: q_copy['option_a'] = opts[0]
            if len(opts) > 1: q_copy['option_b'] = opts[1]
            if len(opts) > 2: q_copy['option_c'] = opts[2]
            if len(opts) > 3: q_copy['option_d'] = opts[3]

            cleaned_qs.append(q_copy)

        t_copy['questions'] = cleaned_qs
        cleaned_tests.append(t_copy)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cleaned_tests, f, ensure_ascii=False, indent=2)

    # Verify zero Bengali characters in question and options
    bn_found = 0
    for t in cleaned_tests:
        for q in t['questions']:
            for val in [q['question'], q['question_en'], q['question_bn']] + q['options']:
                if re.search(r'[\u0980-\u09FF]', val):
                    bn_found += 1
    print(f"✓ {filename}: 100 tests processed. Bengali characters in questions/options: {bn_found}")

if __name__ == '__main__':
    clean_dataset('medical_100_tests.json')
    clean_dataset('versity_100_tests.json')
