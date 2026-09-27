import os
import re

EV_DIR = "/Users/karimsiam/.gemini/antigravity/scratch/admission-test-bd-ev"
INDEX_PATH = os.path.join(EV_DIR, "index.html")
WEB_INDEX_PATH = os.path.join(EV_DIR, "web", "index.html")

def polish_index():
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    replacements = [
        # Stream badges
        ('completed • test ${medNextBn} open', 'Completed • Test ${medNextBn} Unlocked'),
        ('completed • test ${varNextBn} open', 'Completed • Test ${varNextBn} Unlocked'),
        ('`🩺 Medical: ${medTier} (${toBengaliNum(medComp)}/${toBengaliNum(medMax)} completed • test ${medNextBn} open)`',
         '`🩺 Medical: ${medTier} (${toBengaliNum(medComp)}/${toBengaliNum(medMax)} Completed • Test ${medNextBn} Unlocked)`'),
        ('`🏛️ Varsity: ${varTier} (${toBengaliNum(varComp)}/${toBengaliNum(varMax)} completed • test ${varNextBn} open)`',
         '`🏛️ Varsity: ${varTier} (${toBengaliNum(varComp)}/${toBengaliNum(varMax)} Completed • Test ${varNextBn} Unlocked)`'),

        # Dropdown options
        ("let label = `test ${bnNum} `;", "let label = `Test ${bnNum} `;"),
        ("label += '✓ [completed • give again]';", "label += '✓ [Completed • Retake]';"),
        ("label += isFree ? '✓ [free]' : '✓ [open]';", "label += isFree ? '✓ [Free]' : '✓ [Unlocked]';"),
        ("label += '🔒 [premium - 499]';", "label += '🔒 [Premium • Tk 499]';"),
        ("label += '🔒 [Serial locked]';", "label += '🔒 [Sequential Lock]';"),

        # Start button labels
        ('<span>👑 Test with development ${testBn} Unlock (499)</span>', '<span>👑 Unlock Test ${testBn} with bKash (Tk 499)</span>'),
        ('<span>👑 Test with development ${testBn} unlock (499)</span>', '<span>👑 Unlock Test ${testBn} with bKash (Tk 499)</span>'),
        ('<span>🔒 test ${testBn} Locked (complete previous test)</span>', '<span>🔒 Test ${testBn} Locked (Complete Previous Test First)</span>'),
        ('<span>🔄 Retest (Retake Test #${testBn})</span>', '<span>🔄 Retake Test #${testBn}</span>'),

        # Return / Grid navigation
        ('`🔙 test #${bn}-It has been returned`', '`🔙 Returned to Test #${bn}`'),
        ('test #${bnI}', 'Test #${bnI}'),
        ('✓ completed', '✓ Completed'),
        ('🔄 give again', '🔄 Retake Test'),
        ('open (start →)', 'Start Exam →'),
        ('👑 499', '👑 Tk 499'),
        ('🔒 unlock', '🔒 Unlock'),
        ('🔒 locked', '🔒 Locked'),
        ('📋 Progress of Varsity and Integrated Group 100 Model Tests', '📋 Varsity & GST Science 100 Model Tests'),
        ('Varsity and integrated groups', 'Varsity & GST Science'),
        ('Varsity and integrated group', 'Varsity & GST Science'),

        # Counter pills & stats
        ('the answer: <span id="answered-count-pill"', 'Answered: <span id="answered-count-pill"'),
        ('the rest 95T test', 'remaining 95 tests'),
        ('the rest 95 tests', 'remaining 95 tests'),
        ('your Bikash', 'Your bKash'),
        ('Bikash', 'bKash'),
        ('the combo', 'Combo'),
        ('all test', 'All Tests'),
        ('is displayed: <span id="kb-showing-count"', 'Showing: <span id="kb-showing-count"'),
        ('total <span id="kb-total-count"', 'Total <span id="kb-total-count"'),
        ('100 MCQs আসল question', '100 MCQs Original Questions'),
        ('original question', 'Original Questions'),
        ('question 100', 'Question 100'),
        ('question ${', 'Question ${'),
        ('question${', 'Question ${'),
        ('question ', 'Question '),
        ('Question 100 MCQs', '100 MCQs'),

        # Paywall text
        ('Recipient number <strong class="text-white font-mono select-all">01644265766</strong> days and s',
         'bKash Personal Number: <strong class="text-white font-mono select-all">01644265766</strong> (Send Money)'),
        ('Recipient number <strong class="text-white font-mono select-all">01644265766</strong>',
         'bKash Personal Number: <strong class="text-white font-mono select-all">01644265766</strong>'),

        # Admin panel table headers
        ('<th class="pb-3 pr-2">সময়</th>', '<th class="pb-3 pr-2">Time</th>'),
        ('<th class="pb-3 pl-2">মূল SMS the message</th>', '<th class="pb-3 pl-2">Raw SMS Message</th>'),
        ('the message', 'Message')
    ]

    for orig, repl in replacements:
        html = html.replace(orig, repl)

    # Clean double spaces
    html = re.sub(r' +', ' ', html)

    # Automated check: Zero Bengali
    bn = re.findall(r'[\u0980-\u09FF]', html)
    if bn:
        raise AssertionError(f"Found {len(bn)} Bengali chars in polished index.html")

    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    with open(WEB_INDEX_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Successfully polished {INDEX_PATH} and {WEB_INDEX_PATH} (0 Bengali characters).")

if __name__ == '__main__':
    polish_index()
