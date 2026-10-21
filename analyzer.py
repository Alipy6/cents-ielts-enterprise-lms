"""
analyzer.py - Deterministic IELTS Academic Writing NLP Analyzer (v3.0).

Pure-Python, zero-external-dependency essay evaluator.
Produces sub-scores, an overall band (rounded to the nearest 0.5),
and actionable bullet-point feedback for both Task 1 and Task 2.
"""
import re
import math
from typing import Dict, List

TRANSITION_WORDS = [
    "furthermore", "consequently", "nevertheless", "in contrast",
    "overall", "notably", "whereas", "in addition", "thus",
    "moreover", "however", "similarly", "for example", "in conclusion",
    "as a result", "on the other hand", "despite", "in spite of",
    "likewise", "by comparison", "in terms of", "accordingly",
    "nonetheless", "undoubtedly", "in essence", "to sum up",
    "in summary", "specifically", "arguably", "notwithstanding",
]

STOPWORDS_5 = {
    "which", "their", "there", "would", "about", "these", "other",
    "where", "could", "should", "those", "being", "been", "having",
    "first", "after", "before", "while", "under", "above"
}


def _count_words(text: str) -> int:
    """Return total whitespace-separated word count."""
    return len(text.split())


def _tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokens for TTR / vocabulary analysis."""
    return re.findall(r"[a-z']+", text.lower())


def _sentences(text: str) -> List[str]:
    """Split text into sentences using terminal punctuation."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in parts if s.strip()]


def _detect_transitions(text: str) -> List[str]:
    """Return sorted list of transition words present in the text."""
    lower = text.lower()
    return sorted({w for w in TRANSITION_WORDS if w in lower})


def _lexical_diversity(text: str) -> float:
    """Type-Token Ratio: unique tokens / total tokens."""
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    return round(len(set(tokens)) / len(tokens), 4)


def _avg_sentence_length(text: str) -> float:
    """Mean number of words per sentence."""
    sents = _sentences(text)
    if not sents:
        return 0.0
    total = sum(len(s.split()) for s in sents)
    return round(total / len(sents), 2)


def _sentence_length_var(text: str) -> float:
    """Standard deviation of sentence lengths (words)."""
    sents = _sentences(text)
    if len(sents) < 2:
        return 0.0
    lengths = [len(s.split()) for s in sents]
    mean = sum(lengths) / len(lengths)
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return round(math.sqrt(variance), 2)


def _paragraph_count(text: str) -> int:
    """Count non-empty paragraphs."""
    return len([p for p in text.split("\n") if p.strip()])


def _valid_word_ratio(text: str) -> float:
    """Compute ratio of valid English-like words to total tokens."""
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    valid_count = 0
    for tok in tokens:
        if len(tok) > 22:
            continue
        if not re.search(r"[aeiouy]", tok):
            continue
        if re.search(r"[bcdfghjklmnpqrstvwxz]{6,}", tok):
            continue
        if re.search(r"(.)\1\1", tok):
            continue
        valid_count += 1
    return valid_count / len(tokens)


# --- Sub-score calculators (each returns 0-9) ------------------------------

def _task_achievement(word_count: int, task_type: str) -> float:
    """Score task achievement based on word-count compliance."""
    min_words = 150 if task_type == "Task 1" else 250
    ratio = word_count / min_words if min_words else 1.0
    score = 9.0 * min(1.0, ratio)
    if word_count > min_words * 1.1:
        score = min(9.0, score + 0.5)
    return round(max(0.0, min(9.0, score)), 1)


def _coherence_cohesion(text: str, task_type: str) -> float:
    """Score coherence & cohesion: paragraph structure + transition words."""
    wc = _count_words(text)
    para = _paragraph_count(text)
    transitions = _detect_transitions(text)
    if task_type == "Task 1":
        para_bonus = 2.0 if 3 <= para <= 4 else 0.0
    else:
        para_bonus = 2.0 if 4 <= para <= 5 else 0.0
    t_bonus = min(3.0, len(transitions) * 0.5)
    score = para_bonus + t_bonus + 3.0
    if wc < 40:
        score = min(2.0, score)
    return round(max(0.0, min(9.0, score)), 1)


def _lexical_resource(text: str) -> float:
    """Score lexical resource: type-token ratio + average word length with length maturity factor."""
    wc = _count_words(text)
    ttr = _lexical_diversity(text)
    tokens = _tokenize(text)
    avg_word_len = (sum(len(t) for t in tokens) / len(tokens)) if tokens else 0.0
    ttr_score = min(4.0, max(0.0, (ttr - 0.3) * 10.0))
    wl_score = min(3.0, max(0.0, (avg_word_len - 3.0) * 0.5))
    raw_score = ttr_score + wl_score + 2.0
    maturity = min(1.0, wc / 100.0)
    score = raw_score * maturity
    return round(max(0.0, min(9.0, score)), 1)


def _grammatical_range(text: str) -> float:
    """Score grammatical range: sentence-length variance + punctuation variety."""
    sents = _sentences(text)
    if not sents:
        return 0.0
    var = _sentence_length_var(text)
    avg_len = _avg_sentence_length(text)
    var_score = min(4.0, var * 0.5)
    clause_marks = len(re.findall(r"[;:]", text))
    comma_count = len(re.findall(r",", text))
    punct_score = min(3.0, clause_marks * 0.5 + min(1.5, comma_count * 0.1))
    len_bonus = 2.0 if 12 <= avg_len <= 28 else 0.5
    return round(max(0.0, min(9.0, var_score + punct_score + len_bonus)), 1)


# --- Public API --------------------------------------------------------------

MODEL_BAND8_SAMPLES = {
    "Task 1": (
        "The provided line graph illustrates significant shifts in global renewable energy adoption between 2000 and 2025. "
        "Overall, solar and wind power experienced exponential growth, whereas reliance on fossil fuels demonstrated a steady "
        "decline over the twenty-five-year period. In 2000, coal and natural gas dominated the market, accounting for nearly 80% "
        "of total electricity production. However, technological advancements and international environmental policies catalyzed "
        "a dramatic transition toward sustainable alternatives. By 2015, solar energy generation had quadrupled, surpassing "
        "hydroelectric capacity for the first time. Simultaneously, wind energy capacity grew at an average annual rate of 12%, "
        "driven by major offshore installations in Europe and Asia. In contrast, oil-based power generation registered a sharp "
        "decrease, falling to under 5% of global output by 2025. In summary, the quarter-century trend underscores an "
        "irreversible momentum toward decarbonization across major industrialized nations."
    ),
    "Task 2": (
        "The rapid expansion of artificial intelligence in higher education presents both profound opportunities and significant "
        "ethical challenges. Proponents argue that intelligent tutoring systems personalize learning by adapting to individual "
        "student paces, thereby fostering higher academic achievement and democratizing access to knowledge. Furthermore, "
        "automated administrative tools enable educators to dedicate more time to research and interactive mentoring. Conversely, "
        "critics express legitimate concerns regarding academic integrity, algorithmic bias, and the potential erosion of critical "
        "thinking skills when students over-rely on automated text generation. To mitigate these risks, educational institutions "
        "must implement robust guidelines that promote ethical AI usage while preserving intellectual rigor. Ultimately, artificial "
        "intelligence should serve as a powerful complement to human pedagogy rather than a replacement, ensuring that students "
        "develop essential problem-solving abilities alongside technological literacy."
    )
}


def analyze_essay(essay_text: str, task_type: str = "Task 1") -> Dict:
    """
    Analyze an IELTS Academic Writing essay deterministically.
    """
    if not essay_text or not essay_text.strip():
        return {
            "word_count": 0, "paragraph_count": 0,
            "lexical_diversity": 0.0, "avg_sentence_length": 0.0,
            "sentence_length_var": 0.0, "transition_words_used": [],
            "sub_scores": {
                "task_achievement": 1.0, "coherence_cohesion": 1.0,
                "lexical_resource": 1.0, "grammatical_range": 1.0
            },
            "estimated_band": 1.0,
            "feedback": ["No text submitted."],
            "repeated_words": [],
            "long_sentences_count": 0,
            "model_band8_sample": MODEL_BAND8_SAMPLES.get(task_type, MODEL_BAND8_SAMPLES["Task 1"])
        }

    wc = _count_words(essay_text)
    paras = _paragraph_count(essay_text)
    ttr = _lexical_diversity(essay_text)
    avg_sl = _avg_sentence_length(essay_text)
    sl_var = _sentence_length_var(essay_text)
    transitions = _detect_transitions(essay_text)
    valid_ratio = _valid_word_ratio(essay_text)

    tokens = _tokenize(essay_text)
    sents = _sentences(essay_text)

    # Repeated words >= 5 chars, not stopwords, >= 4 occurrences
    freq = {}
    for tok in tokens:
        if len(tok) >= 5 and tok not in STOPWORDS_5:
            freq[tok] = freq.get(tok, 0) + 1
    repeated_words = sorted([w for w, count in freq.items() if count >= 4])

    long_sentences_count = sum(1 for s in sents if len(s.split()) > 35)
    model_sample = MODEL_BAND8_SAMPLES.get(task_type, MODEL_BAND8_SAMPLES["Task 1"])

    # Strict Short-Text & Gibberish Guardrail
    if wc < 25 or valid_ratio < 0.65:
        sub_scores = {
            "task_achievement": 1.0,
            "coherence_cohesion": 1.0,
            "lexical_resource": 1.0,
            "grammatical_range": 1.0,
        }
        return {
            "word_count": wc,
            "paragraph_count": paras,
            "lexical_diversity": ttr,
            "avg_sentence_length": avg_sl,
            "sentence_length_var": sl_var,
            "transition_words_used": transitions,
            "sub_scores": sub_scores,
            "estimated_band": 1.0,
            "feedback": [
                "Submission is too short or contains unrecognized/gibberish tokens. "
                "Please write a complete academic response of at least 150 words (Task 1) or 250 words (Task 2)."
            ],
            "repeated_words": repeated_words,
            "long_sentences_count": long_sentences_count,
            "model_band8_sample": model_sample,
        }

    ta = _task_achievement(wc, task_type)
    cc = _coherence_cohesion(essay_text, task_type)
    lr = _lexical_resource(essay_text)
    gr = _grammatical_range(essay_text)

    sub_scores = {
        "task_achievement": ta,
        "coherence_cohesion": cc,
        "lexical_resource": lr,
        "grammatical_range": gr,
    }

    # Weighted overall score, snapped to the nearest 0.5 band
    weights = [0.30, 0.25, 0.25, 0.20]
    overall = ta * weights[0] + cc * weights[1] + lr * weights[2] + gr * weights[3]
    band = round(overall * 2) / 2.0
    band = max(1.0, min(9.0, band))

    feedback = _build_feedback(wc, task_type, paras, transitions, ttr, avg_sl)

    return {
        "word_count": wc,
        "paragraph_count": paras,
        "lexical_diversity": ttr,
        "avg_sentence_length": avg_sl,
        "sentence_length_var": sl_var,
        "transition_words_used": transitions,
        "sub_scores": sub_scores,
        "estimated_band": band,
        "feedback": feedback,
        "repeated_words": repeated_words,
        "long_sentences_count": long_sentences_count,
        "model_band8_sample": model_sample,
    }


def _build_feedback(wc: int, task_type: str, paras: int,
                    transitions: List[str], ttr: float,
                    avg_sl: float) -> List[str]:
    """Generate targeted, actionable bullet-point feedback."""
    min_words = 150 if task_type == "Task 1" else 250
    fb: List[str] = []

    if wc < min_words:
        fb.append(
            f"Word count is {wc} - below the required minimum of {min_words}. "
            "Expand each point with supporting examples or data."
        )
    elif wc > min_words * 2:
        fb.append(
            f"Word count ({wc}) is well above the minimum - consider "
            "tightening your prose for greater precision."
        )

    if paras < 2:
        if task_type == "Task 1":
            fb.append("Use at least 3-4 paragraphs: intro, overview, and two detail sections.")
        else:
            fb.append("Use at least 4 paragraphs: intro, two body paragraphs, and conclusion.")
    elif paras > 6:
        fb.append("Too many short paragraphs - merge related ideas for better flow.")

    if len(transitions) < 3:
        fb.append(
            "Few discourse markers detected. Incorporate: 'furthermore', "
            "'nevertheless', 'in contrast', 'consequently', 'overall', 'notably'."
        )

    if ttr < 0.45:
        fb.append(
            f"Lexical diversity is low (TTR = {ttr:.2f}). Use precise synonyms: "
            "'rose' -> 'surged / climbed / shot up'."
        )

    if 10 <= avg_sl <= 30:
        fb.append(
            "Good sentence-length range. Keep mixing simple, compound, and "
            "complex constructions to show grammatical flexibility."
        )
    elif avg_sl > 30:
        fb.append(
            f"Average sentence length is long ({avg_sl:.0f} words). Break up "
            "run-on sentences for readability."
        )
    else:
        fb.append(
            f"Average sentence length is short ({avg_sl:.0f} words). Combine "
            "sentences with subordinate clauses and punctuation "
            "(semicolons, colons, commas)."
        )

    fb.append(
        "Proofread for subject-verb agreement, article usage, and "
        "consistent verb tenses before submitting."
    )
    return fb
