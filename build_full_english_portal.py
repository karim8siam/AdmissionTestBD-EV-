import os
import json
import urllib.parse
import requests
import time

EV_DIR = "/Users/karimsiam/.gemini/antigravity/scratch/admission-test-bd-ev"
SRC_PORTAL_SCRIPT = "/Users/karimsiam/.gemini/antigravity/scratch/medical-100-test-series/build_clean_portal.py"
CACHE_FILE = os.path.join(EV_DIR, "data", "translation_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def translate_fast(text, cache):
    if not text or not isinstance(text, str):
        return text
    t = text.strip()
    if not t or t.isascii():
        return t
    if t in cache:
        return cache[t]
    try:
        url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=bn&tl=en&dt=t&q=' + urllib.parse.quote(t)
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = ''.join([part[0] for part in r.json()[0] if part and part[0]]).strip()
            cache[t] = res
            return res
    except Exception:
        pass
    return t

def transform_question_ev(q, cache):
    q_copy = dict(q)
    q_text = (q.get('question_bn') or q.get('question') or '').strip()
    q_copy['question_bn'] = q_text
    q_copy['question_en'] = translate_fast(q_text, cache)
    q_copy['question'] = q_copy['question_en']

    orig_opts = q.get('options', [q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d')])
    trans_opts = [translate_fast(opt, cache) if opt else '' for opt in orig_opts]
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
    trans_ref = translate_fast(orig_ref, cache) if orig_ref else ''
    q_copy['book_reference'] = trans_ref
    q_copy['book_reference_en'] = trans_ref
    q_copy['explanation'] = f"Correct Answer ({q_copy['correct_option']}): {correct_ans_text}. Reference: {trans_ref}."
    q_copy['explanation_en'] = q_copy['explanation']

    if q.get('chapter'):
        q_copy['chapter'] = translate_fast(q['chapter'], cache)
    if q.get('sub_discipline'):
        q_copy['sub_discipline'] = translate_fast(q['sub_discipline'], cache)

    return q_copy

def main():
    cache = load_cache()
    print(f"Loaded {len(cache)} cached translation items.")

    print("Loading source Test 1 for Medical and Versity...")
    with open('/Users/karimsiam/.gemini/antigravity/scratch/medical-100-test-series/data/medical_100_tests.json') as f:
        med_1_src = json.load(f)[0]
    with open('/Users/karimsiam/.gemini/antigravity/scratch/medical-100-test-series/data/versity_100_tests.json') as f:
        var_1_src = json.load(f)[0]

    print("Translating Test 1 items...")
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

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

    med_1_json = json.dumps(med_1_ev, ensure_ascii=False)
    var_1_json = json.dumps(var_1_ev, ensure_ascii=False)

    # Read base portal template
    with open(SRC_PORTAL_SCRIPT, 'r', encoding='utf-8') as f:
        src_content = f.read()

    start_marker = 'portal_code = """'
    end_marker = '"""\n\nportal_code = portal_code.replace'
    start_idx = src_content.find(start_marker) + len(start_marker)
    end_idx = src_content.find(end_marker)
    code = src_content[start_idx:end_idx]

    # Apply English translations
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
        "font-family: 'Hind Siliguri', 'Plus Jakarta Sans', sans-serif;",
        "font-family: 'Plus Jakarta Sans', sans-serif;"
    )

    # Branding & Header
    code = code.replace(
        '<span class="text-[10px] px-1.5 py-0.2 rounded-full bg-ai-900/80 text-ai-300 border border-ai-700 font-bold hidden md:inline-block">AI 2.0</span>',
        '<span class="text-[10px] px-1.5 py-0.2 rounded-full bg-ai-900/80 text-ai-300 border border-ai-700 font-bold hidden md:inline-block">English Version (EV)</span>'
    )
    code = code.replace(
        '<p class="text-[11px] text-slate-400 hidden lg:block">বাংলাদেশ অ্যাডমিশন মডেল টেস্ট ও জাতীয় মেধা র‍্যাংকিং</p>',
        '<p class="text-[11px] text-slate-400 hidden lg:block">National Merit Ranking & Full-Length Admission Mock Tests</p>'
    )
    code = code.replace('<span class="hidden md:inline">সেশন:</span>', '<span class="hidden md:inline">Session:</span>')
    code = code.replace('<option value="2025-26" selected>২০২৫-২৬</option>', '<option value="2025-26" selected>2025-26</option>')
    code = code.replace('<option value="2026-27">২০২৬-২৭</option>', '<option value="2026-27">2026-27</option>')
    code = code.replace('<option value="2024-25">২০২৪-২৫</option>', '<option value="2024-25">2024-25</option>')
    code = code.replace('<option value="2027-28">২০২৭-২৮</option>', '<option value="2027-28">2027-28</option>')
    code = code.replace('🩺 মেডিকেল: টেস্ট ০১ আনলকড', '🩺 Medical: Test 01 Unlocked')
    code = code.replace('🏛️ ভার্সিটি ও গুচ্ছ: টেস্ট ০১ আনলকড', '🏛️ Varsity & GST: Test 01 Unlocked')

    # Nav Tabs
    code = code.replace('মেডিকেল ১০০ মডেল টেস্ট', 'Medical 100 Tests')
    code = code.replace('লাইভ', 'LIVE')
    code = code.replace('ভার্সিটি ও গুচ্ছ বিজ্ঞান ১০০ টেস্ট', 'Varsity & GST Science 100 Tests')
    code = code.replace('বিগত ১৫ বছরের প্রশ্ন (২০১০-২০২৫)', 'Past 15 Years (2010-2025)')
    code = code.replace('আনলক মুক্ত', 'FREE')
    code = code.replace('পাঠ্যবই নলেজ বেস (২,০০০ তথ্য)', 'Textbook Knowledge Base (2,000 Facts)')
    code = code.replace('এনসিটিবি', 'NCTB')
    code = code.replace('ক্যালকুলেটরবিহীন স্পিড ট্রিকস', 'No-Calc Speed Math Engine')
    code = code.replace('ইঞ্জিনিয়ারিং ভর্তি (BUET/CKRUET)', 'Engineering Admission (BUET/CKRUET)')
    code = code.replace('শীঘ্রই আসছে', 'Coming Soon')

    # Hero Banner
    code = code.replace('পরবর্তী পরীক্ষা দিতে পূর্ববর্তী পরীক্ষা সম্পন্ন বাধ্যতামূলক', 'Sequential Lock: Completing previous test is required to unlock next')
    code = code.replace('মেডিকেল ও ভার্সিটি <span class="text-transparent bg-clip-text bg-gradient-to-r from-brand-400 via-emerald-300 to-teal-200">১০০ মডেল টেস্ট সিরিজ</span>', 'Medical & Varsity <span class="text-transparent bg-clip-text bg-gradient-to-r from-brand-400 via-emerald-300 to-teal-200">100 Model Test Series (English Version)</span>')
    code = code.replace('পরপর সিকোয়েন্সিয়াল টেস্ট আনলক সিস্টেম। প্রতিটি টেস্টে রয়েছে ৬০ মিনিটের রিয়েল-টাইম কাউন্টডাউন টাইমার, সেশন মেধা ও সর্বকালের অল-বাংলাদেশ লাইভ র‍্যাংকিং।', 'Sequential test unlock system with 60-minute real-time countdown timer, session percentile rank, and All-Bangladesh live leaderboard.')
    code = code.replace('১০,০০০+ এনসিটিবি প্রশ্নব্যাংক', '10,000+ NCTB Standard MCQs')
    code = code.replace('নেগেটিভ মার্কিং (-০.২৫)', 'Negative Marking (-0.25)')
    code = code.replace('অটোমেটিক সাবমিট ব্যবস্থা', 'Automatic Submission System')
    code = code.replace('নির্ভুল পাঠ্যবই ব্যাখ্যা', 'Textbook Referenced Solutions')

    # Selection Card
    code = code.replace('মেডিকেল পূর্ণাঙ্গ মডেল টেস্ট নির্বাচন', 'Medical Full Model Test Selection')
    code = code.replace('ভার্সিটি ও গুচ্ছ বিজ্ঞান মডেল টেস্ট নির্বাচন', 'Varsity & GST Science Model Test Selection')
    code = code.replace('সিকোয়েন্সিয়াল লক সক্রিয়', 'Sequential Lock Active')
    code = code.replace('টেস্ট ০১ সম্পন্ন করলে টেস্ট ০২ স্বয়ংক্রিয়ভাবে আনলক হবে।', 'Complete Test 01 to automatically unlock Test 02.')
    code = code.replace('টেস্ট নম্বর:', 'Test No:')
    code = code.replace('১০০ টেস্টের গ্রিড তালিকা', '100 Tests Grid List')
    code = code.replace('👑 প্রিমিয়াম আনলক', '👑 Premium Unlock')

    # Start Card
    code = code.replace('মেডিকেল পূর্ণাঙ্গ মডেল টেস্ট ০১', 'Medical Full Model Test 01')
    code = code.replace('পরীক্ষা শুরু বাটনে ক্লিক করার সাথে সাথে প্রশ্ন প্রদর্শিত হবে এবং ব্যাকওয়ার্ড কাউন্টডাউন টাইমার শুরু হবে। সময় শেষ হলে আপনার উত্তরপত্র স্বয়ংক্রিয়ভাবে সাবমিট হবে।', 'The countdown timer will begin immediately when you click Start Exam. Questions will appear, and answers will be automatically submitted when time expires.')
    code = code.replace('মোট প্রশ্ন', 'Total Questions')
    code = code.replace('১০০টি', '100 MCQs')
    code = code.replace('পূর্ণমান', 'Total Marks')
    code = code.replace('১০০', '100.00')
    code = code.replace('নির্ধারিত সময়', 'Duration')
    code = code.replace('৬০ মিনিট', '60 Minutes')
    code = code.replace('নেগেটিভ মার্ক', 'Negative Mark')
    code = code.replace('-০.২৫', '-0.25')
    code = code.replace('📌 পরীক্ষা শুরুর নিয়মাবলী:', '📌 Exam Rules & Instructions:')
    code = code.replace('প্রতিটি সঠিক উত্তরের জন্য পাবেন <strong class="text-emerald-400">+১.০০ নম্বর</strong>।', 'Each correct answer awards <strong class="text-emerald-400">+1.00 Mark</strong>.')
    code = code.replace('প্রতিটি ভুল উত্তরের জন্য কাটা যাবে <strong class="text-rose-400">-০.২৫ নম্বর</strong> (নেগেティブ মার্কিং)।', 'Each incorrect answer deducts <strong class="text-rose-400">-0.25 Marks</strong> (Negative Marking).')
    code = code.replace('টাইমার শূন্য (০০:০০) হওয়ার সাথে সাথে পরীক্ষা <strong class="text-amber-400">স্বয়ংক্রিয়ভাবে সাবমিট</strong> হবে।', 'When the timer hits (00:00), the exam <strong class="text-amber-400">will auto-submit</strong>.')
    code = code.replace('পরীক্ষা সাবমিট করার সাথে সাথেই আপনি <strong class="text-teal-400">চলতি সেশন ও সর্বকালের জাতীয় মেধা তালিকা</strong> দেখতে পাবেন।', 'Upon submission, you will instantly receive your <strong class="text-teal-400">Session Merit Rank & All-Bangladesh Live Rank</strong>.')
    code = code.replace('এই পরীক্ষাটি সফলভাবে সম্পন্ন করার পর পরবর্তী টেস্টটি আনলক হবে।', 'Completing this test unlocks the next test in the series.')
    code = code.replace('এই মডেল টেস্টটি আপনি ইতিমধ্যে সম্পন্ন করেছেন। নিজের প্রস্তুতি আরও শাণিত করতে যতবার খুশি পুনরায় পরীক্ষা দিতে পারেন।', 'You have already completed this test. You can retake it unlimited times to sharpen your preparation.')
    code = code.replace('🚀 পরীক্ষা শুরু করো (Start Exam)', '🚀 Start Full 100 MCQ Exam')

    # Active Exam Controls
    code = code.replace('অবশিষ্ট সময়', 'Time Left')
    code = code.replace('৬০:০০', '60:00')
    code = code.replace('উত্তর: <span id="answered-count-pill" class="text-white text-xs sm:text-sm font-black">০</span>/<span id="total-questions-pill">১০০</span>', 'Answered: <span id="answered-count-pill" class="text-white text-xs sm:text-sm font-black">0</span>/<span id="total-questions-pill">100</span>')
    code = code.replace('বাকি: <span id="unanswered-count-pill" class="text-white text-sm font-black">১০০</span>', 'Remaining: <span id="unanswered-count-pill" class="text-white text-sm font-black">100</span>')
    code = code.replace('<span class="hidden sm:inline">সাবমিট করো</span>', '<span class="hidden sm:inline">Submit Exam</span>')
    code = code.replace('<span class="sm:hidden">সাবমিট</span>', '<span class="sm:hidden">Submit</span>')
    code = code.replace('সব বিষয় (১০০)', 'All Subjects (100)')
    code = code.replace('জীববিজ্ঞান', 'Biology')
    code = code.replace('রসায়ন', 'Chemistry')
    code = code.replace('পদার্থবিজ্ঞান', 'Physics')
    code = code.replace('ইংরেজি ও জিকে', 'English & GK')
    code = code.replace('উচ্চতর গণিত', 'Higher Math')
    code = code.replace('পরীক্ষা শেষ করার আগে সমস্ত উত্তর যাচাই করে নিন', 'Please review all questions before submitting your exam')
    code = code.replace('সাবমিট করার সাথে সাথেই সেশন মেধা ও সর্বকালের অল-বাংলাদেশ ফলাফল প্রকাশ পাবে।', 'Upon submission, your session merit rank and all-time leaderboard placement will be updated.')
    code = code.replace('ফলাফল জমা দিন (Submit Exam)', 'Submit Final Answers')

    # Results & Ranking
    code = code.replace('🏆 ফলাফল চূড়ান্তভাবে প্রকাশিত', '🏆 Official Exam Results Published')
    code = code.replace('তোমার মোট প্রাপ্ত নম্বর', 'Total Marks Obtained')
    code = code.replace('পূর্ণমান: <span id="results-full-marks">১০০</span>', 'Full Marks: <span id="results-full-marks">100</span>')
    code = code.replace('সেশন মেধা স্থান (<span id="results-session-name">২০২৫-২৬</span>)', 'Session Merit Rank (<span id="results-session-name">2025-26</span>)')
    code = code.replace('-- <span class="text-xs text-slate-400 font-normal">/ মোট -- জন</span>', '-- <span class="text-xs text-slate-400 font-normal">/ Total -- candidates</span>')
    code = code.replace('লাইভ সেশন', 'Live Session')
    code = code.replace('সর্বকালের জাতীয় মেধাক্রম (All-Time)', 'All-Time National Rank (All-Bangladesh)')
    code = code.replace('অল-বাংলাদেশ', 'National')
    code = code.replace('সঠিক উত্তর', 'Correct Answers')
    code = code.replace('ভুল উত্তর (-০.২৫)', 'Incorrect (-0.25)')
    code = code.replace('উত্তর করা হয়নি', 'Unanswered')
    code = code.replace('ব্যয়িত সময়', 'Time Taken')
    code = code.replace('ব্যয়িত সময়', 'Time Taken')
    code = code.replace('🔄 আবার পরীক্ষা দিন', '🔄 Retake This Test')
    code = code.replace('পরবর্তী টেস্টে যান (Next Test)', 'Next Test →')
    code = code.replace('অভিনন্দন! আপনি সফলভাবে ফ্রি ৫টি মডেল টেস্ট সম্পন্ন করেছেন', 'Congratulations! You have completed all 5 Free Model Tests')
    code = code.replace('পরবর্তী ৯৫টি এক্সক্লুসিভ মডেল টেস্ট (টেস্ট ৬ থেকে ১০০), লাইভ জাতীয় মেধা তালিকায় স্থায়ী অবস্থান এবং সম্পূর্ণ পাঠ্যবই ব্যাখ্যা পেতে মাত্র ৳৪৯৯ দিয়ে প্রিমিয়াম ব্যাচ আনলক করুন।', 'Unlock the remaining 95 exclusive model tests (Tests 6 to 100), full leaderboard placement, and textbook solutions for only ৳499.')
    code = code.replace('📱 bKash দিয়ে বাকি ৯৫টি টেস্ট আনলক করুন (৳৪৯৯)', '📱 Unlock Remaining 95 Tests via bKash (৳499)')
    code = code.replace('AI এক্সাম অটপসি ও বিষয়ভিত্তিক পারফরম্যান্স', 'AI Exam Autopsy & Subject Performance Analytics')
    code = code.replace('এনসিটিবি পাঠ্যবই ম্যাপিং', 'NCTB Curriculum Mapping')
    code = code.replace('প্রতিটি প্রশ্নের বিস্তারিত উত্তর ও পাঠ্যবই ব্যাখ্যা', 'Question-by-Question Detailed Solutions & Citations')
    code = code.replace('সবুজ রঙ সঠিক উত্তর, লাল রঙ আপনার ভুল উত্তর নির্দেশ করে।', 'Green highlights correct answer; red indicates your incorrect choice.')
    code = code.replace('✓ সঠিক', '✓ Correct')
    code = code.replace('✗ ভুল', '✗ Wrong')

    # Modals & Alerts
    code = code.replace('উত্তরপত্র সাবমিট নিশ্চিতকরণ', 'Confirm Exam Submission')
    code = code.replace('আপনি কি উত্তরপত্র সাবমিট করতে নিশ্চিত?', 'Are you sure you want to submit your exam?')
    code = code.replace('মোট প্রশ্ন: <span class="font-black text-white">১০০ টি</span>', 'Total Questions: <span class="font-black text-white">100 MCQs</span>')
    code = code.replace('উত্তর দিয়েছেন: <span id="modal-submit-answered"', 'Answered: <span id="modal-submit-answered"')
    code = code.replace('অনুত্তরিত: <span id="modal-submit-unanswered"', 'Unanswered: <span id="modal-submit-unanswered"')
    code = code.replace('বাতিল করো', 'Cancel')
    code = code.replace('<span>হ্যাঁ, সাবমিট করো</span>', '<span>Yes, Submit Exam</span>')

    code = code.replace('বিকাশ প্রিমিয়াম টেস্ট আনলক', 'bKash Premium Test Unlock')
    code = code.replace('মেডিকেল (৯৫ টেস্ট)', 'Medical (95 Tests)')
    code = code.replace('ভার্সিটি ও গুচ্ছ (৯৫ টেস্ট)', 'Varsity & GST (95 Tests)')
    code = code.replace('কম্বো (মেডিকেল + ভার্সিটি)', 'Combo (Medical + Varsity)')
    code = code.replace('৳৪৯৯ (এককালীন ফি)', '৳499 (One-time fee)')
    code = code.replace('৳৭৯৯ (এককালীন ফি)', '৳799 (One-time fee)')
    code = code.replace('আপনার বিকাশ অ্যাপে গিয়ে Send Money করুন', 'Open your bKash App and select "Send Money"')
    code = code.replace('বিকাশ পার্সোনাল নাম্বার:', 'bKash Personal Number:')
    code = code.replace('কপি করুন', 'Copy')
    code = code.replace('আপনার বিকাশ নম্বর দিন:', 'Your bKash Mobile Number:')
    code = code.replace('SMS-এ প্রাপ্ত Transaction ID (TrxID) দিন:', 'Transaction ID (TrxID) from bKash SMS:')
    code = code.replace('placeholder="যেমন: BLA499XYZ123"', 'placeholder="e.g. BLA499XYZ123"')
    code = code.replace('ভেরিফাই ও আনলক করুন', 'Verify & Unlock All Tests')

    # Replace Option letters to English
    code = code.replace("const optionLetters = ['ক', 'খ', 'গ', 'ঘ'];", "const optionLetters = ['A', 'B', 'C', 'D'];")
    code = code.replace("const letters = ['ক', 'খ', 'গ', 'ঘ'];", "const letters = ['A', 'B', 'C', 'D'];")

    # toBengaliNum replacement
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

    # Toast and dynamic JS strings
    code = code.replace('e.returnValue = \'আপনার পরীক্ষা বর্তমানে চলমান রয়েছে! এখন বের হলে উত্তরপত্র বাতিল হতে পারে।\';', "e.returnValue = 'Your exam is currently in progress! Exiting now will submit your exam.';")
    code = code.replace('showToast("🎉 অভিনন্দন! আপনার পেমেন্ট অনুমোদিত হয়েছে এবং মডেল টেস্ট আনলক করা হয়েছে!", "success");', 'showToast("🎉 Congratulations! Your payment has been approved and tests are unlocked!", "success");')
    code = code.replace('showToast(`ভর্তি সেশন \'${newSession}\' নির্বাচিত হয়েছে। মেধা তালিকা এতে রেকর্ড হবে।`, "success");', 'showToast(`Admission session \'${newSession}\' selected. Rankings will be recorded for this session.`, "success");')
    code = code.replace("const medTier = appState.isMedicalPaid ? '👑 প্রিমিয়াম' : 'ফ্রি';", "const medTier = appState.isMedicalPaid ? '👑 Premium' : 'Free';")
    code = code.replace("const varTier = appState.isVersityPaid ? '👑 প্রিমিয়াম' : 'ফ্রি';", "const varTier = appState.isVersityPaid ? '👑 Premium' : 'Free';")
    code = code.replace("showToast(\"বিকাশ নাম্বার '01644265766' ক্লিপবোর্ডে কপি করা হয়েছে।\", \"success\");", "showToast(\"bKash number '01644265766' copied to clipboard.\", \"success\");")
    code = code.replace("showToast(\"বিকাশ নাম্বার: 01644265766\", \"info\");", "showToast(\"bKash Number: 01644265766\", \"info\");")
    code = code.replace('⚠️ অনুগ্রহ করে SMS-এ প্রাপ্ত সঠিক ও পূর্ণাঙ্গ TrxID লিখুন (কমপক্ষে ৬-১২ ডিজিট/অক্ষর)।', '⚠️ Please enter the valid TrxID from your bKash SMS (at least 6-12 characters).')
    code = code.replace('ভেরিফিকেশন চলছে...', 'Verifying Payment...')
    code = code.replace('অভিনন্দন! আপনার পেমেন্ট সফলভাবে ভেরিফাই হয়েছে।', 'Congratulations! Your payment has been verified successfully.')
    code = code.replace('🎉 অভিনন্দন! প্রিমিয়াম মডেল টেস্ট আনলক হয়েছে।', '🎉 Congratulations! Premium model tests have been unlocked.')
    code = code.replace('হিসাব করা হচ্ছে...', 'Calculating...')
    code = code.replace('🎁 আপনি সফলভাবে ফ্রি ৫টি মডেল টেস্ট সম্পন্ন করেছেন!', '🎁 You have successfully completed all 5 Free Model Tests!')
    code = code.replace('📱 বাকি ৯৫টি টেস্ট আনলক (৳৪৯৯)', '📱 Unlock Remaining 95 Tests (৳499)')
    code = code.replace('পরবর্তী টেস্টে যান (Next Test)', 'Next Test →')
    code = code.replace('🎉 অভিনন্দন! টেস্ট ০', '🎉 Congratulations! Test ')
    code = code.replace('সফলভাবে আনলক হয়েছে!', 'successfully unlocked!')
    code = code.replace('✓ টেস্ট সম্পন্ন হয়েছে।', '✓ Test Completed.')
    code = code.replace('উত্তর করা হয়নি (০.০০)', 'Unanswered (0.00)')
    code = code.replace('✓ সঠিক উত্তর (+১.০০)', '✓ Correct Answer (+1.00)')
    code = code.replace('✗ ভুল উত্তর (-০.২৫)', '✗ Incorrect Answer (-0.25)')
    code = code.replace('আপনার উত্তর:', 'Your Answer:')
    code = code.replace('সঠিক উত্তর:', 'Correct Answer:')
    code = code.replace('পাঠ্যবই রেফারেন্স ও ব্যাখ্যা:', 'Textbook Reference & Detailed Solution:')
    code = code.replace('পরীক্ষার সময় সমাপ্ত! আপনার উত্তরপত্র সাবমিট করা হয়েছে।', 'Time is up! Your exam has been automatically submitted.')
    code = code.replace('উত্তরপত্র সফলভাবে সাবমিট হয়েছে!', 'Exam submitted successfully!')

    # Insert translated embedded test data
    code = code.replace('__DEFAULT_MED_TEST_1__', med_1_json).replace('__DEFAULT_VAR_TEST_1__', var_1_json)

    # Write files
    root_index = os.path.join(EV_DIR, "index.html")
    web_index = os.path.join(EV_DIR, "web", "index.html")
    os.makedirs(os.path.join(EV_DIR, "web"), exist_ok=True)

    with open(root_index, 'w', encoding='utf-8') as f:
        f.write(code)
    with open(web_index, 'w', encoding='utf-8') as f:
        f.write(code)

    print(f"✓ Generated EV {root_index} and {web_index} ({len(code):,} characters)")

if __name__ == '__main__':
    main()
