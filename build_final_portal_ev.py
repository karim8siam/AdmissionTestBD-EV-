import os
import json
import re

EV_DIR = "/Users/karimsiam/.gemini/antigravity/scratch/admission-test-bd-ev"
SRC_INDEX = "/Users/karimsiam/.gemini/antigravity/scratch/medical-100-test-series/index.html"
CACHE_FILE = os.path.join(EV_DIR, "data", "translation_cache.json")
UI_TRANS_FILE = os.path.join(EV_DIR, "ui_translations.json")

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
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

def transform_question_ev(q, cache):
    q_copy = dict(q)
    q_text = (q.get('question_bn') or q.get('question') or '').strip()
    q_copy['question_bn'] = q_text
    q_copy['question_en'] = translate_str(q_text, cache)
    q_copy['question'] = q_copy['question_en']

    orig_opts = q.get('options', [q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d')])
    trans_opts = [translate_str(opt, cache) if opt else '' for opt in orig_opts]
    q_copy['options'] = trans_opts
    q_copy['option_a'] = trans_opts[0] if len(trans_opts) > 0 else ''
    q_copy['option_b'] = trans_opts[1] if len(trans_opts) > 1 else ''
    q_copy['option_c'] = trans_opts[2] if len(trans_opts) > 2 else ''
    q_copy['option_d'] = trans_opts[3] if len(trans_opts) > 3 else ''

    opt_letter_map = {'ক': 'A', 'খ': 'B', 'গ': 'C', 'ঘ': 'D', 'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D'}
    correct_idx = q.get('correct_index', 0)
    q_copy['correct_index'] = correct_idx
    orig_opt_letter = q.get('correct_option', 'A')
    q_copy['correct_option'] = opt_letter_map.get(orig_opt_letter, ['A', 'B', 'C', 'D'][correct_idx if 0 <= correct_idx < 4 else 0])

    correct_ans_text = trans_opts[correct_idx] if 0 <= correct_idx < len(trans_opts) else ''
    orig_ref = q.get('book_reference', '')
    trans_ref = translate_str(orig_ref, cache) if orig_ref else ''
    q_copy['book_reference'] = trans_ref
    q_copy['book_reference_en'] = trans_ref
    q_copy['explanation'] = f"Correct Answer ({q_copy['correct_option']}): {correct_ans_text}. Reference: {trans_ref}."
    q_copy['explanation_en'] = q_copy['explanation']

    if q.get('chapter'):
        q_copy['chapter'] = translate_str(q['chapter'], cache)
    if q.get('sub_discipline'):
        q_copy['sub_discipline'] = translate_str(q['sub_discipline'], cache)

    return q_copy

def main():
    print("Loading translation caches...")
    cache = load_json(CACHE_FILE)
    ui_cache = load_json(UI_TRANS_FILE)
    print(f"Loaded {len(cache)} question translations, {len(ui_cache)} UI translations.")

    # 1. Prepare English Test 1 objects
    med_ev_path = os.path.join(EV_DIR, "data", "medical_100_tests.json")
    var_ev_path = os.path.join(EV_DIR, "data", "versity_100_tests.json")

    if os.path.exists(med_ev_path) and os.path.exists(var_ev_path):
        with open(med_ev_path, 'r', encoding='utf-8') as f:
            med_1_ev = json.load(f)[0]
        with open(var_ev_path, 'r', encoding='utf-8') as f:
            var_1_ev = json.load(f)[0]
    else:
        with open('/Users/karimsiam/.gemini/antigravity/scratch/medical-100-test-series/data/medical_100_tests.json') as f:
            med_1_src = json.load(f)[0]
        with open('/Users/karimsiam/.gemini/antigravity/scratch/medical-100-test-series/data/versity_100_tests.json') as f:
            var_1_src = json.load(f)[0]

        med_1_ev = {
            'test_id': 1,
            'test_code': "MED-001",
            'test_name': "Medical Full Model Test 01",
            'test_name_bn': "Medical Full Model Test 01",
            'stream': 'medical',
            'total_questions': len(med_1_src['questions']),
            'duration_minutes': 60,
            'questions': [transform_question_ev(q, cache) for q in med_1_src['questions']]
        }

        var_1_ev = {
            'test_id': 1,
            'test_code': "VAR-001",
            'test_name': "Varsity & GST Model Test 01",
            'test_name_bn': "Varsity & GST Model Test 01",
            'stream': 'versity',
            'total_questions': len(var_1_src['questions']),
            'duration_minutes': 60,
            'questions': [transform_question_ev(q, cache) for q in var_1_src['questions']]
        }

    med_1_json = json.dumps(med_1_ev, ensure_ascii=False)
    var_1_json = json.dumps(var_1_ev, ensure_ascii=False)

    # 2. Read latest master index.html
    with open(SRC_INDEX, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Replace line 1492 & 1493 (DEFAULT_MED_TEST_1 and DEFAULT_VAR_TEST_1)
    new_lines = []
    for line in lines:
        if line.strip().startswith('const DEFAULT_MED_TEST_1 = '):
            new_lines.append(f"    const DEFAULT_MED_TEST_1 = {med_1_json};\n")
        elif line.strip().startswith('const DEFAULT_VAR_TEST_1 = '):
            new_lines.append(f"    const DEFAULT_VAR_TEST_1 = {var_1_json};\n")
        else:
            new_lines.append(line)

    code = "".join(new_lines)

    # 3. Core Document & Meta Settings
    code = code.replace('<html lang="bn"', '<html lang="en"')
    code = code.replace(
        '<title>Admission Test BD | AI-Powered Exam Preparation & National Merit Ranking</title>',
        '<title>Admission Test BD (English Version) | Medical & Varsity 100 Model Test Series</title>'
    )
    code = code.replace(
        'বাংলাদেশ শীর্ষস্থানীয় এডমিশন টেস্ট পোর্টাল: মেডিকেল ও ভার্সিটি ১০০ মডেল টেস্ট, বিগত ১৫ বছরের প্রশ্ন, ২০০০ পাঠ্যবই তথ্য এবং রিয়েল-টাইম জাতীয় ও সেশন মেধা তালিকা।',
        'Bangladesh Leading Admission Test Portal (English Version): Medical & Varsity 100 Model Tests, Past 15 Years Questions, 2,000 Textbook Facts, Real-Time National Merit Ranking.'
    )
    code = code.replace(
        "fontFamily: {\n            sans: ['Hind Siliguri', 'Plus Jakarta Sans', 'sans-serif'],",
        "fontFamily: {\n            sans: ['Plus Jakarta Sans', 'sans-serif'],"
    )
    code = code.replace(
        "body {\n      font-family: 'Hind Siliguri', 'Plus Jakarta Sans', sans-serif;\n    }",
        "body {\n      font-family: 'Plus Jakarta Sans', sans-serif;\n    }"
    )

    # 4. English Option Letters & Digits
    code = code.replace("const optionLetters = ['ক', 'খ', 'গ', 'ঘ'];", "const optionLetters = ['A', 'B', 'C', 'D'];")
    code = code.replace("const letters = ['ক', 'খ', 'গ', 'ঘ'];", "const letters = ['A', 'B', 'C', 'D'];")

    to_num_old = """    function toBengaliNum(num) {
      if (num === null || num === undefined) return '';
      const bnDigits = ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯'];
      return String(num).replace(/[0-9]/g, d => bnDigits[Number(d)]);
    }"""
    to_num_new = """    function toBengaliNum(num) {
      if (num === null || num === undefined) return '';
      return String(num);
    }"""
    code = code.replace(to_num_old, to_num_new)

    # Fix leading zero formatting
    code = code.replace("'০' + toBengaliNum", "'0' + toBengaliNum")
    code = code.replace('"০" + toBengaliNum', '"0" + toBengaliNum')

    # 5. Curated High-Yield Portal UI Dictionary
    curated_replacements = [
        # Header & Badges
        ('<span class="text-[10px] px-1.5 py-0.2 rounded-full bg-ai-900/80 text-ai-300 border border-ai-700 font-bold hidden md:inline-block">AI 2.0</span>',
         '<span class="text-[10px] px-1.5 py-0.2 rounded-full bg-ai-900/80 text-ai-300 border border-ai-700 font-bold hidden md:inline-block">English Version (EV)</span>'),
        ('<p class="text-[11px] text-slate-400 hidden lg:block">বাংলাদেশ অ্যাডমিশন মডেল টেস্ট ও জাতীয় মেধা র‍্যাংকিং</p>',
         '<p class="text-[11px] text-slate-400 hidden lg:block">National Merit Ranking & Full-Length Admission Mock Tests</p>'),
        ('<span class="hidden md:inline">সেশন:</span>', '<span class="hidden md:inline">Session:</span>'),
        ('<option value="2025-26" selected>২০২৫-২৬</option>', '<option value="2025-26" selected>2025-26</option>'),
        ('<option value="2026-27">২০২৬-২৭</option>', '<option value="2026-27">2026-27</option>'),
        ('<option value="2024-25">২০২৪-২৫</option>', '<option value="2024-25">2024-25</option>'),
        ('<option value="2027-28">২০২৭-২৮</option>', '<option value="2027-28">2027-28</option>'),
        ('🩺 মেডিকেল: টেস্ট ০১ আনলকড', '🩺 Medical: Test 01 Unlocked'),
        ('🏛️ ভার্সিটি ও গুচ্ছ: টেস্ট ০১ আনলকড', '🏛️ Varsity & GST: Test 01 Unlocked'),

        # Nav Tabs
        ('>মেডিকেল ১০০ মডেল টেস্ট</span>', '>Medical 100 Tests</span>'),
        ('>লাইভ</span>', '>LIVE</span>'),
        ('>ভার্সিটি ও গুচ্ছ বিজ্ঞান ১০০ টেস্ট</span>', '>Varsity & GST Science 100 Tests</span>'),
        ('>বিগত ১৫ বছরের প্রশ্ন (২০১০-২০২৫)</span>', '>Past 15 Years (2010-2025)</span>'),
        ('>আনলক মুক্ত</span>', '>FREE</span>'),
        ('>পাঠ্যবই নলেজ বেস (২,০০০ তথ্য)</span>', '>Textbook Knowledge Base (2,000 Facts)</span>'),
        ('>এনসিটিবি</span>', '>NCTB</span>'),
        ('>ক্যালকুলেটরবিহীন স্পিড ট্রিকস</span>', '>No-Calc Speed Math Engine</span>'),
        ('>ইঞ্জিনিয়ারিং ভর্তি (BUET/CKRUET)</span>', '>Engineering Admission (BUET/CKRUET)</span>'),
        ('>শীঘ্রই আসছে</span>', '>Coming Soon</span>'),

        # Hero Banner
        ('পরবর্তী পরীক্ষা দিতে পূর্ববর্তী পরীক্ষা সম্পন্ন বাধ্যতামূলক', 'Sequential Lock: Completing previous test is required to unlock next'),
        ('মেডিকেল ও ভার্সিটি <span class="text-transparent bg-clip-text bg-gradient-to-r from-brand-400 via-emerald-300 to-teal-200">১০০ মডেল টেস্ট সিরিজ</span>',
         'Medical & Varsity <span class="text-transparent bg-clip-text bg-gradient-to-r from-brand-400 via-emerald-300 to-teal-200">100 Model Test Series (English Version)</span>'),
        ('পরপর সিকোয়েন্সিয়াল টেস্ট আনলক সিস্টেম। প্রতিটি টেস্টে রয়েছে ৬০ মিনিটের রিয়েল-টাইম কাউন্টডাউন টাইমার, সেশন মেধা ও সর্বকালের অল-বাংলাদেশ লাইভ র‍্যাংকিং।',
         'Sequential test unlock system with 60-minute real-time countdown timer, session percentile rank, and All-Bangladesh live leaderboard.'),
        ('১০,০০০+ এনসিটিবি প্রশ্নব্যাংক', '10,000+ NCTB Standard MCQs'),
        ('নেগেটিভ মার্কিং (-০.২৫)', 'Negative Marking (-0.25)'),
        ('অটোমেটিক সাবমিট ব্যবস্থা', 'Automatic Submission System'),
        ('নির্ভুল পাঠ্যবই ব্যাখ্যা', 'Textbook Referenced Solutions'),

        # Selection Card
        ('মেডিকেল পূর্ণাঙ্গ মডেল টেস্ট নির্বাচন', 'Medical Full Model Test Selection'),
        ('ভার্সিটি ও গুচ্ছ বিজ্ঞান মডেল টেস্ট নির্বাচন', 'Varsity & GST Science Model Test Selection'),
        ('সিকোয়েন্সিয়াল লক সক্রিয়', 'Sequential Lock Active'),
        ('টেস্ট ০১ সম্পন্ন করলে টেস্ট ০২ স্বয়ংক্রিয়ভাবে আনলক হবে।', 'Complete Test 01 to automatically unlock Test 02.'),
        ('টেস্ট নম্বর:', 'Test No:'),
        ('১০০ টেস্টের গ্রিড তালিকা', '100 Tests Grid List'),
        ('👑 প্রিমিয়াম আনলক', '👑 Premium Unlock'),

        # Start Card
        ('মেডিকেল পূর্ণাঙ্গ মডেল টেস্ট ০১', 'Medical Full Model Test 01'),
        ('পরীক্ষা শুরু বাটনে ক্লিক করার সাথে সাথে প্রশ্ন প্রদর্শিত হবে এবং ব্যাকওয়ার্ড কাউন্টডাউন টাইমার শুরু হবে। সময় শেষ হলে আপনার উত্তরপত্র স্বয়ংক্রিয়ভাবে সাবমিট হবে।',
         'The countdown timer will begin immediately when you click Start Exam. Questions will appear, and answers will be automatically submitted when time expires.'),
        ('মোট প্রশ্ন', 'Total Questions'),
        ('১০০টি', '100 MCQs'),
        ('পূর্ণমান', 'Total Marks'),
        ('নির্ধারিত সময়', 'Duration'),
        ('৬০ মিনিট', '60 Minutes'),
        ('নেগেটিভ মার্ক', 'Negative Mark'),
        ('📌 পরীক্ষা শুরুর নিয়মাবলী:', '📌 Exam Rules & Instructions:'),
        ('প্রতিটি সঠিক উত্তরের জন্য পাবেন <strong class="text-emerald-400">+১.০০ নম্বর</strong>।', 'Each correct answer awards <strong class="text-emerald-400">+1.00 Mark</strong>.'),
        ('প্রতিটি ভুল উত্তরের জন্য কাটা যাবে <strong class="text-rose-400">-০.২৫ নম্বর</strong> (নেগেটিভ মার্কিং)।', 'Each incorrect answer deducts <strong class="text-rose-400">-0.25 Marks</strong> (Negative Marking).'),
        ('টাইমার শূন্য (০০:০০) হওয়ার সাথে সাথে পরীক্ষা <strong class="text-amber-400">স্বয়ংক্রিয়ভাবে সাবমিট</strong> হবে।', 'When the timer hits (00:00), the exam <strong class="text-amber-400">will auto-submit</strong>.'),
        ('পরীক্ষা সাবমিট করার সাথে সাথেই আপনি <strong class="text-teal-400">চলতি সেশন ও সর্বকালের জাতীয় মেধা তালিকা</strong> দেখতে পাবেন।', 'Upon submission, you will instantly receive your <strong class="text-teal-400">Session Merit Rank & All-Bangladesh Live Rank</strong>.'),
        ('এই পরীক্ষাটি সফলভাবে সম্পন্ন করার পর পরবর্তী টেস্টটি আনলক হবে।', 'Completing this test unlocks the next test in the series.'),
        ('এই মডেল টেস্টটি আপনি ইতিমধ্যে সম্পন্ন করেছেন। নিজের প্রস্তুতি আরও শাণিত করতে যতবার খুশি পুনরায় পরীক্ষা দিতে পারেন।', 'You have already completed this test. You can retake it unlimited times to sharpen your preparation.'),
        ('🚀 পরীক্ষা শুরু করো (Start Exam)', '🚀 Start Full 100 MCQ Exam'),
        ('🔄 আবার পরীক্ষা দিন', '🔄 Retake This Test'),
        ('পরবর্তী টেস্টে যান (Next Test)', 'Next Test →'),

        # Active Exam Controls
        ('অবশিষ্ট সময়', 'Time Left'),
        ('উত্তর: <span id="answered-count-pill" class="text-white text-xs sm:text-sm font-black">০</span>/<span id="total-questions-pill">১০০</span>',
         'Answered: <span id="answered-count-pill" class="text-white text-xs sm:text-sm font-black">0</span>/<span id="total-questions-pill">100</span>'),
        ('বাকি: <span id="unanswered-count-pill" class="text-white text-sm font-black">১০০</span>',
         'Remaining: <span id="unanswered-count-pill" class="text-white text-sm font-black">100</span>'),
        ('<span class="hidden sm:inline">সাবমিট করো</span>', '<span class="hidden sm:inline">Submit Exam</span>'),
        ('<span class="sm:hidden">সাবমিট</span>', '<span class="sm:hidden">Submit</span>'),
        ('সব বিষয় (১০০)', 'All Subjects (100)'),
        ('জীববিজ্ঞান', 'Biology'),
        ('রসায়ন', 'Chemistry'),
        ('পদার্থবিজ্ঞান', 'Physics'),
        ('ইংরেজি ও জিকে', 'English & GK'),
        ('উচ্চতর গণিত', 'Higher Math'),
        ('পরীক্ষা শেষ করার আগে সমস্ত উত্তর যাচাই করে নিন', 'Please review all questions before submitting your exam'),
        ('সাবমিট করার সাথে সাথেই সেশন মেধা ও সর্বকালের অল-বাংলাদেশ ফলাফল প্রকাশ পাবে।', 'Upon submission, your session merit rank and all-time leaderboard placement will be updated.'),
        ('ফলাফল জমা দিন (Submit Exam)', 'Submit Final Answers'),

        # Results & Ranking
        ('🏆 ফলাফল চূড়ান্তভাবে প্রকাশিত', '🏆 Official Exam Results Published'),
        ('তোমার মোট প্রাপ্ত নম্বর', 'Total Marks Obtained'),
        ('পূর্ণমান: <span id="results-full-marks">১০০</span>', 'Full Marks: <span id="results-full-marks">100</span>'),
        ('সেশন মেধা স্থান (<span id="results-session-name">২০২৫-২৬</span>)', 'Session Merit Rank (<span id="results-session-name">2025-26</span>)'),
        ('সর্বকালের জাতীয় মেধাক্রম (All-Time)', 'All-Time National Rank (All-Bangladesh)'),
        ('লাইভ সেশন', 'Live Session'),
        ('অল-বাংলাদেশ', 'National'),
        ('সঠিক উত্তর', 'Correct Answers'),
        ('ভুল উত্তর (-০.২৫)', 'Incorrect (-0.25)'),
        ('উত্তর করা হয়নি', 'Unanswered'),
        ('ব্যয়িত সময়', 'Time Taken'),
        ('ব্যয়িত সময়', 'Time Taken'),
        ('অভিনন্দন! আপনি সফলভাবে ফ্রি ৫টি মডেল টেস্ট সম্পন্ন করেছেন', 'Congratulations! You have completed all 5 Free Model Tests'),
        ('পরবর্তী ৯৫টি এক্সক্লুসিভ মডেল টেস্ট (টেস্ট ৬ থেকে ১০০), লাইভ জাতীয় মেধা তালিকায় স্থায়ী অবস্থান এবং সম্পূর্ণ পাঠ্যবই ব্যাখ্যা পেতে মাত্র ৳৪৯৯ দিয়ে প্রিমিয়াম ব্যাচ আনলক করুন।',
         'Unlock the remaining 95 exclusive model tests (Tests 6 to 100), full leaderboard placement, and textbook solutions for only ৳499.'),
        ('📱 bKash দিয়ে বাকি ৯৫টি টেস্ট আনলক করুন (৳৪৯৯)', '📱 Unlock Remaining 95 Tests via bKash (৳499)'),
        ('AI এক্সাম অটপসি ও বিষয়ভিত্তিক পারফরম্যান্স', 'AI Exam Autopsy & Subject Performance Analytics'),
        ('এনসিটিবি পাঠ্যবই ম্যাপিং', 'NCTB Curriculum Mapping'),
        ('প্রতিটি প্রশ্নের বিস্তারিত উত্তর ও পাঠ্যবই ব্যাখ্যা', 'Question-by-Question Detailed Solutions & Citations'),
        ('সবুজ রঙ সঠিক উত্তর, লাল রঙ আপনার ভুল উত্তর নির্দেশ করে।', 'Green highlights correct answer; red indicates your incorrect choice.'),
        ('✓ সঠিক', '✓ Correct'),
        ('✗ ভুল', '✗ Wrong'),

        # Modals & Alerts
        ('উত্তরপত্র সাবমিট নিশ্চিতকরণ', 'Confirm Exam Submission'),
        ('আপনি কি উত্তরপত্র সাবমিট করতে নিশ্চিত?', 'Are you sure you want to submit your exam?'),
        ('মোট প্রশ্ন: <span class="font-black text-white">১০০ টি</span>', 'Total Questions: <span class="font-black text-white">100 MCQs</span>'),
        ('উত্তর দিয়েছেন: <span id="modal-submit-answered"', 'Answered: <span id="modal-submit-answered"'),
        ('অনুত্তরিত: <span id="modal-submit-unanswered"', 'Unanswered: <span id="modal-submit-unanswered"'),
        ('বাতিল করো', 'Cancel'),
        ('<span>হ্যাঁ, সাবমিট করো</span>', '<span>Yes, Submit Exam</span>'),

        # Paywall Modal
        ('বিকাশ প্রিমিয়াম টেস্ট আনলক', 'bKash Premium Test Unlock'),
        ('মেডিকেল (৯৫ টেস্ট)', 'Medical (95 Tests)'),
        ('ভার্সিটি ও গুচ্ছ (৯৫ টেস্ট)', 'Varsity & GST (95 Tests)'),
        ('কম্বো (মেডিকেল + ভার্সিটি)', 'Combo (Medical + Varsity)'),
        ('৳৪৯৯ (এককালীন ফি)', '৳499 (One-time fee)'),
        ('৳৭৯৯ (এককালীন ফি)', '৳799 (One-time fee)'),
        ('আপনার বিকাশ অ্যাপে গিয়ে Send Money করুন', 'Open your bKash App and select "Send Money"'),
        ('বিকাশ পার্সোনাল নাম্বার:', 'bKash Personal Number:'),
        ('কপি করুন', 'Copy'),
        ('আপনার বিকাশ নম্বর দিন:', 'Your bKash Mobile Number:'),
        ('SMS-এ প্রাপ্ত Transaction ID (TrxID) দিন:', 'Transaction ID (TrxID) from bKash SMS:'),
        ('placeholder="যেমন: BLA499XYZ123"', 'placeholder="e.g. BLA499XYZ123"'),
        ('ভেরিফাই ও আনলক করুন', 'Verify & Unlock All Tests'),
        ('বিকাশ নম্বর:', 'bKash Mobile Number:'),

        # Dynamic JS & Toasts
        ("e.returnValue = 'আপনার পরীক্ষা বর্তমানে চলমান রয়েছে! এখন বের হলে উত্তরপত্র বাতিল হতে পারে।';",
         "e.returnValue = 'Your exam is currently in progress! Exiting now will submit your exam.';"),
        ('showToast("🎉 অভিনন্দন! আপনার পেমেন্ট অনুমোদিত হয়েছে এবং মডেল টেস্ট আনলক করা হয়েছে!", "success");',
         'showToast("🎉 Congratulations! Your payment has been approved and tests are unlocked!", "success");'),
        ('showToast(`ভর্তি সেশন \'${newSession}\' নির্বাচিত হয়েছে। মেধা তালিকা এতে রেকর্ড হবে।`, "success");',
         'showToast(`Admission session \'${newSession}\' selected. Rankings will be recorded for this session.`, "success");'),
        ("const medTier = appState.isMedicalPaid ? '👑 প্রিমিয়াম' : 'ফ্রি';",
         "const medTier = appState.isMedicalPaid ? '👑 Premium' : 'Free';"),
        ("const varTier = appState.isVersityPaid ? '👑 প্রিমিয়াম' : 'ফ্রি';",
         "const varTier = appState.isVersityPaid ? '👑 Premium' : 'Free';"),
        ('showToast("বিকাশ নাম্বার \'01644265766\' ক্লিপবোর্ডে কপি করা হয়েছে।", "success");',
         'showToast("bKash number \'01644265766\' copied to clipboard.", "success");'),
        ('showToast("বিকাশ নাম্বার: 01644265766", "info");',
         'showToast("bKash Number: 01644265766", "info");'),
        ('⚠️ অনুগ্রহ করে SMS-এ প্রাপ্ত সঠিক ও পূর্ণাঙ্গ TrxID লিখুন (কমপক্ষে ৬-১২ ডিজিট/অক্ষর)।',
         '⚠️ Please enter the valid TrxID from your bKash SMS (at least 6-12 characters).'),
        ('ভেরিফিকেশন চলছে...', 'Verifying Payment...'),
        ('অভিনন্দন! আপনার পেমেন্ট সফলভাবে ভেরিফাই হয়েছে।', 'Congratulations! Your payment has been verified successfully.'),
        ('🎉 অভিনন্দন! প্রিমিয়াম মডেল টেস্ট আনলক হয়েছে।', '🎉 Congratulations! Premium model tests have been unlocked.'),
        ('হিসাব করা হচ্ছে...', 'Calculating...'),
        ('🎁 আপনি সফলভাবে ফ্রি ৫টি মডেল টেস্ট সম্পন্ন করেছেন!', '🎁 You have successfully completed all 5 Free Model Tests!'),
        ('📱 বাকি ৯৫টি টেস্ট আনলক (৳৪৯৯)', '📱 Unlock Remaining 95 Tests (৳499)'),
        ('🎉 অভিনন্দন! টেস্ট ০', '🎉 Congratulations! Test '),
        ('সফলভাবে আনলক হয়েছে!', 'successfully unlocked!'),
        ('✓ টেস্ট সম্পন্ন হয়েছে।', '✓ Test Completed.'),
        ('উত্তর করা হয়নি (০.০০)', 'Unanswered (0.00)'),
        ('✓ সঠিক উত্তর (+১.০০)', '✓ Correct Answer (+1.00)'),
        ('✗ ভুল উত্তর (-০.২৫)', '✗ Incorrect Answer (-0.25)'),
        ('আপনার উত্তর:', 'Your Answer:'),
        ('সঠিক উত্তর:', 'Correct Answer:'),
        ('পাঠ্যবই রেফারেন্স ও ব্যাখ্যা:', 'Textbook Reference & Detailed Solution:'),
        ('পরীক্ষার সময় সমাপ্ত! আপনার উত্তরপত্র সাবমিট করা হয়েছে।', 'Time is up! Your exam has been automatically submitted.'),
        ('উত্তরপত্র সফলভাবে সাবমিট হয়েছে!', 'Exam submitted successfully!'),
        ('প্রশ্ন নং ', 'Question '),
        ('মডেল টেস্ট ', 'Model Test '),
        ('অনুশীলন মোড', 'Practice Mode'),
        ('পরীক্ষা মোড', 'Exam Mode'),
        ('মেধা তালিকা', 'Merit Leaderboard'),
        ('জাতীয় মেধা তালিকা', 'National Merit Leaderboard'),
        ('সেশন মেধা তালিকা', 'Session Merit Leaderboard'),
        ('র‍্যাংক', 'Rank'),
        ('শিক্ষার্থীর নাম', 'Student Name'),
        ('কলেজ / প্রতিষ্ঠান', 'Target College / Institution'),
        ('প্রাপ্ত নম্বর', 'Marks'),
        ('তারিখ ও সময়', 'Date & Time'),

        # Stream syllabus badges
        ('startBadge.innerText = "মেডিকেল পূর্ণাঙ্গ মডেল টেস্ট (বায়োলজি ৩০ • কেমিস্ট্রি ২৫ • ফিজিক্স ২০ • ইংলিশ ১৫ • জিকে ১০)";',
         'startBadge.innerText = "Medical Full Model Test (Biology 30 • Chemistry 25 • Physics 20 • English 15 • GK 10)";'),
        ('startBadge.innerText = "ভার্সিটি ও গুচ্ছ বিজ্ঞান মডেল টেস্ট (ফিজিক্স ২৫ • কেমিস্ট্রি ২৫ • উচ্চতর গণিত ২৫ • বায়োলজি ২৫)";',
         'startBadge.innerText = "Varsity & GST Science Model Test (Physics 25 • Chemistry 25 • Higher Math 25 • Biology 25)";'),
        ('badge.innerText = "মেডিকেল সিলেবাস: বায়োলজি ৩০ • রসায়ন ২৫ • পদার্থ ২০ • ইংরেজি ১৫ • সাধারণ জ্ঞান ১০";',
         'badge.innerText = "Medical Syllabus: Biology 30 • Chemistry 25 • Physics 20 • English 15 • General Knowledge 10";'),
        ('badge.innerText = "ভার্সিটি ও গুচ্ছ সিলেবাস: পদার্থ ২৫ • রসায়ন ২৫ • উচ্চতর গণিত ২৫ • জীববিজ্ঞান ২৫";',
         'badge.innerText = "Varsity & GST Syllabus: Physics 25 • Chemistry 25 • Higher Math 25 • Biology 25";'),

        # Dynamic template literals
        ('medBadge.innerHTML = `🩺 মেডিকেল: ${medTier} (${toBengaliNum(medComp)}/${toBengaliNum(medMax)} সম্পন্ন • টেস্ট ${medNextBn} উন্মুক্ত)`;',
         'medBadge.innerHTML = `🩺 Medical: ${medTier} (${toBengaliNum(medComp)}/${toBengaliNum(medMax)} Done • Test ${medNextBn} Unlocked)`;'),
        ('varBadge.innerHTML = `🏛️ ভার্সিটি: ${varTier} (${toBengaliNum(varComp)}/${toBengaliNum(varMax)} সম্পন্ন • টেস্ট ${varNextBn} উন্মুক্ত)`;',
         'varBadge.innerHTML = `🏛️ Varsity: ${varTier} (${toBengaliNum(varComp)}/${toBengaliNum(varMax)} Done • Test ${varNextBn} Unlocked)`;'),

        # Admin panel
        ('অ্যাডমিন প্যানেল', 'Admin Panel'),
        ('অ্যাডমিন ড্যাশবোর্ড', 'Admin Dashboard'),
        ('৪-লেয়ার অ্যাডমিন সিকিউরিটি অথেনটিকেশন', '4-Layer Admin Security Authentication'),
        ('মাস্টার পাসওয়ার্ড ১', 'Master Password 1'),
        ('মাস্টার পাসওয়ার্ড ২', 'Master Password 2'),
        ('সিকিউরিটি পিন', 'Security PIN'),
        ('সিকিউরিটি ওয়ার্ড', 'Security Word'),
        ('লগইন ভেরিফাই করুন', 'Verify & Access Admin'),
        ('এসএমএস লগ ভেরিফিকেশন', 'bKash SMS Verification Log'),
        ('ম্যানুয়াল স্টুডেন্ট আনলক', 'Manual Student Unlock'),
        ('লাইভ সাবমিশন মনিটর', 'Live Submissions Monitor'),
        ('মোট শিক্ষার্থী', 'Total Students'),
        ('মোট সাবমিশন', 'Total Submissions'),
        ('মোট রেভিনিউ', 'Total Revenue'),
        ('লগআউট', 'Logout')
    ]

    for orig, repl in curated_replacements:
        code = code.replace(orig, repl)

    # 6. Apply remaining UI translations from ui_cache
    for bn_text, en_text in sorted(ui_cache.items(), key=lambda x: -len(x[0])):
        if len(bn_text) > 3 and bn_text in code and not bn_text.isascii() and en_text and en_text != bn_text:
            # Avoid replacing inside json keys or script tags if risky
            code = code.replace(bn_text, en_text)

    # 7. Write root index.html and web/index.html
    root_index = os.path.join(EV_DIR, "index.html")
    web_index = os.path.join(EV_DIR, "web", "index.html")
    os.makedirs(os.path.join(EV_DIR, "web"), exist_ok=True)

    with open(root_index, 'w', encoding='utf-8') as f:
        f.write(code)
    with open(web_index, 'w', encoding='utf-8') as f:
        f.write(code)

    print(f"✓ Generated EV portal: {root_index} and {web_index} ({len(code):,} characters)")

if __name__ == '__main__':
    main()
