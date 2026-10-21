"""
ai_engine.py - Hybrid AI & Parametric Question Engine (v3.0).

Works 100% offline via a deterministic parametric scientific generator.
Optionally supports live LLM calls via urllib.request if an API key is provided.

Functions:
  generate_questions(subject, topic, difficulty, count, api_key) -> dict
  notes_to_exam(notes_text, subject, count, api_key) -> dict
  explain_trap(question_row, selected_option, api_key) -> dict
  upgrade_essay_paragraph(text, task_type, api_key) -> dict
"""
import json
import math
import random
import re
import urllib.request
import urllib.error

ALLOWED_SUBJECTS = ("Mathematics", "Logic", "Physics", "Chemistry")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _options(correct: str, opt_a: str, opt_b: str, opt_c: str, opt_d: str, opt_e: str):
    """Return the five options keyed A-E with the correct one flagged."""
    return {
        "A": opt_a,
        "B": opt_b,
        "C": opt_c,
        "D": opt_d,
        "E": opt_e,
    }


def _pick_correct(correct_value: str, distractors: list):
    """Place the correct value at a random letter position and fill the rest
    with distractors, returning (correct_letter, option_a, option_b, option_c,
    option_d, option_e)."""
    letters = ["A", "B", "C", "D", "E"]
    correct_idx = random.randint(0, 4)
    pool = list(distractors)
    random.shuffle(pool)
    distractor_iter = iter(pool)
    vals = {}
    for i, letter in enumerate(letters):
        if i == correct_idx:
            vals[letter] = correct_value
        else:
            vals[letter] = next(distractor_iter)
    return (
        letters[correct_idx],
        vals["A"], vals["B"], vals["C"], vals["D"], vals["E"],
    )


def _wrap_latex(expr: str) -> str:
    """Wrap a plain expression in LaTeX inline delimiters if not already wrapped."""
    if expr.startswith("\\("):
        return expr
    return f"\\({expr}\\)"


# ---------------------------------------------------------------------------
# Parametric generators per subject
# ---------------------------------------------------------------------------

def _gen_math(count: int, difficulty: str, topic: str = "General"):
    """Generate randomized Mathematics questions."""
    questions = []
    for _ in range(count):
        q_type = random.choice([
            "derivative", "integral", "logarithm", "quadratic",
            "matrix_det", "geometric_series", "combinatorics",
        ])
        if q_type == "derivative":
            a = random.randint(2, 9)
            n = random.randint(2, 6)
            correct_val = f"{a * n}x^{{{n - 1}}}"
            distractors = [
                f"{a}x^{{{n}}}",
                f"{a * n}x^{{{n}}}",
                f"{a}x^{{{n - 1}}}",
                f"\\frac{{{a}}}{{{n}}}x^{{{n + 1}}}",
            ]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(
                _wrap_latex(correct_val), [_wrap_latex(d) for d in distractors]
            )
            q = {
                "question_text": f"Find the derivative of \\(f(x) = {a}x^{{{n}}}\\).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"Using the power rule, \\(\\frac{{d}}{{dx}}[{a}x^{{{n}}}] = {a}\\cdot{n}\\,x^{{{n-1}}} = {a*n}x^{{{n-1}}}\\).",
                "topic": topic or "Calculus",
            }
        elif q_type == "integral":
            a = random.randint(1, 6)
            n = random.randint(1, 5)
            # integral of a*x^n from 0 to some upper bound
            upper = random.randint(2, 5)
            correct_val = (a / (n + 1)) * (upper ** (n + 1))
            correct_str = str(int(correct_val)) if correct_val == int(correct_val) else f"\\frac{{{int(correct_val * 100)}}}{{{100}}}"
            distractors = [
                str(int((a / n) * (upper ** n))),
                str(int(a * upper ** n)),
                str(int((a / (n + 1)) * upper ** n + 1)),
                str(int(a * upper ** (n + 1))),
            ]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(
                _wrap_latex(correct_str), [_wrap_latex(d) for d in distractors]
            )
            q = {
                "question_text": f"Evaluate \\(\\displaystyle\\int_0^{{{upper}}} {a}x^{{{n}}}\\,dx\\).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\(\\int {a}x^{{{n}}}dx = \\frac{{{a}}}{{{n+1}}}x^{{{n+1}}}\\). Evaluating from 0 to {upper}: \\(\\frac{{{a}}}{{{n+1}}}\\cdot{upper}^{{{n+1}}} = {correct_val}\\).",
                "topic": topic or "Calculus",
            }
        elif q_type == "logarithm":
            base = random.choice([2, 3, 5, 10])
            result = random.randint(2, 6)
            x_val = base ** result
            correct_str = str(result)
            distractors = [
                str(result + 1), str(result - 1),
                str(result * 2), str(result + 2),
            ]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(
                correct_str, distractors
            )
            q = {
                "question_text": f"Find \\(\\log_{{{base}}} {x_val}\\).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\({base}^{result} = {x_val}\\), so \\(\\log_{{{base}}} {x_val} = {result}\\).",
                "topic": topic or "Algebra",
            }
        elif q_type == "quadratic":
            a_coef = random.randint(1, 4)
            roots = random.sample(range(-4, 5), 2)
            b_coef = -(roots[0] + roots[1])
            c_coef = roots[0] * roots[1]
            correct_str = str(max(roots))
            distractors = [
                str(min(roots)), str(roots[0] + 1), str(roots[1] - 1),
                str(roots[0] * roots[1]),
            ]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(
                correct_str, distractors
            )
            q = {
                "question_text": f"Solve \\({a_coef}x^2 + {a_coef * b_coef}x + {a_coef * c_coef} = 0\\) for the larger root.",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"Dividing by {a_coef}: \\(x^2 + {b_coef}x + {c_coef} = 0\\) with roots \\({roots[0]}\\) and \\({roots[1]}\\). The larger root is {max(roots)}.",
                "topic": topic or "Algebra",
            }
        elif q_type == "matrix_det":
            a, b = random.randint(1, 5), random.randint(1, 5)
            c, d = random.randint(1, 5), random.randint(1, 5)
            det = a * d - b * c
            k = random.choice([2, 3])
            correct_str = str(k ** 2 * det)
            distractors = [
                str(k * det), str(k ** 3 * det), str(k ** 2 * det + 1),
                str(det),
            ]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(
                correct_str, distractors
            )
            q = {
                "question_text": f"If \\(A\\) is a \\(2\\times 2\\) matrix with \\(\\det(A) = {det}\\), what is \\(\\det({k}A)\\)?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"For an \\(n\\times n\\) matrix, \\(\\det(kA) = k^n \\det(A) = {k}^2 \\times {det} = {k**2 * det}\\).",
                "topic": topic or "Linear Algebra",
            }
        elif q_type == "geometric_series":
            a = random.randint(1, 5)
            r = random.choice([2, 3])
            correct_val = a / (1 - 1 / r)
            correct_str = str(int(correct_val)) if correct_val == int(correct_val) else f"\\frac{{{int(correct_val * r)}}}{{{r}}}"
            distractors = [
                str(a), str(a * r), str(int(a / (1 - 1 / r) + 1)),
                str(a * r - 1),
            ]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(
                _wrap_latex(correct_str), [_wrap_latex(d) for d in distractors]
            )
            q = {
                "question_text": f"Find the sum of the infinite geometric series \\(\\displaystyle\\sum_{{n=0}}^{{\\infty}} {a}\\left(\\frac{{1}}{{{r}}}\\right)^n\\).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"First term \\(a = {a}\\), ratio \\(r = 1/{r}\\). Sum \\(S = \\frac{{a}}{{1-r}} = \\frac{{{a}}}{{1 - 1/{r}}} = {correct_val}\\).",
                "topic": topic or "Calculus",
            }
        else:  # combinatorics
            n = random.randint(5, 10)
            k = random.randint(2, 4)
            correct_val = math.factorial(n) // math.factorial(n - k)
            correct_str = str(correct_val)
            distractors = [
                str(math.factorial(n) // (math.factorial(k) * math.factorial(n - k))),
                str(correct_val + n),
                str(correct_val - n),
                str(n ** k),
            ]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(
                correct_str, distractors
            )
            q = {
                "question_text": f"How many ways can you arrange {k} items chosen from {n} distinct objects (order matters)?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"Permutations \\(P({n},{k}) = \\frac{{{n}!}}{{({n}-{k})!}} = {correct_val}\\).",
                "topic": topic or "Combinatorics",
            }
        q["subject"] = "Mathematics"
        q["difficulty"] = difficulty
        questions.append(q)
    return questions


def _gen_logic(count: int, difficulty: str, topic: str = "General"):
    """Generate randomized Logic questions."""
    questions = []
    for _ in range(count):
        q_type = random.choice([
            "modus_ponens", "syllogism", "truth_table", "set_union",
            "set_intersection", "fallacy_identify",
        ])
        if q_type == "modus_ponens":
            p, q_label = random.choice([("rain", "wet"), ("study", "pass"), ("heat", "expand")])
            correct_str = f"{q_label}"
            distractors = [f"not {q_label}", f"maybe {q_label}", f"{q_label} only if not {p}", f"neither {p} nor {q_label}"]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"If it is true that '{p}' implies '{q_label}', and we know '{p}' is true, what can we conclude?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"By modus ponens: \\(P \\Rightarrow Q\\) and \\(P\\) true, therefore \\(Q\\) is true. Conclusion: '{q_label}'.",
                "topic": topic or "Propositional Logic",
            }
        elif q_type == "syllogism":
            correct_str = "All A are C"
            distractors = ["No A are C", "Some A are not C", "All C are A", "No conclusion follows"]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": "Given: 'All A are B' and 'All B are C'. Which conclusion is valid?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": "This is a valid Barbara syllogism: All A are B, All B are C, therefore All A are C (transitivity).",
                "topic": topic or "Syllogisms",
            }
        elif q_type == "truth_table":
            correct_str = "True"
            distractors = ["False", "Both", "Neither", "Depends on P"]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": "What is the truth value of \\(P \\lor \\neg P\\) (Law of Excluded Middle)?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": "\\(P \\lor \\neg P\\) is a tautology: it is always True regardless of P's value (Law of Excluded Middle).",
                "topic": topic or "Propositional Logic",
            }
        elif q_type == "set_union":
            a_size = random.randint(10, 30)
            b_size = random.randint(10, 30)
            overlap = random.randint(1, min(a_size, b_size) - 1)
            correct_str = str(a_size + b_size - overlap)
            distractors = [str(a_size + b_size), str(a_size + b_size + overlap), str(max(a_size, b_size)), str(a_size * b_size)]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"If \\(|A| = {a_size}\\), \\(|B| = {b_size}\\), and \\(|A \\cap B| = {overlap}\\), find \\(|A \\cup B|\\).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"By inclusion-exclusion: \\(|A \\cup B| = |A| + |B| - |A \\cap B| = {a_size} + {b_size} - {overlap} = {a_size + b_size - overlap}\\).",
                "topic": topic or "Set Theory",
            }
        elif q_type == "set_intersection":
            universal = random.randint(20, 50)
            a_size = random.randint(10, universal - 5)
            not_b = random.randint(5, universal - 5)
            correct_str = str(a_size - max(0, not_b - (universal - a_size)))
            val = a_size - max(0, not_b - (universal - a_size))
            distractors = [str(a_size + not_b), str(a_size - not_b), str(universal - a_size - not_b), str(max(a_size, not_b))]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(str(val), distractors)
            q = {
                "question_text": f"In a universal set of {universal} elements, \\(|A| = {a_size}\\) and \\(|B^c| = {not_b}\\). Find \\(|A \\cap B|\\).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\(|B| = {universal} - {not_b} = {universal - not_b}\\). Elements in A that are also in B = \\(|A| - |A \\cap B^c|\\). Given the constraints, \\(|A \\cap B| = {val}\\).",
                "topic": topic or "Set Theory",
            }
        else:  # fallacy_identify
            correct_str = "Ad hominem"
            distractors = ["Straw man", "Appeal to authority", "Slippery slope", "Red herring"]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": "'You cannot trust John's argument about climate change because he is not a scientist.' What fallacy is this?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": "This is an ad hominem fallacy: it attacks the person (John's credentials) rather than addressing the substance of his argument.",
                "topic": topic or "Logical Fallacies",
            }
        q["subject"] = "Logic"
        q["difficulty"] = difficulty
        questions.append(q)
    return questions


def _gen_physics(count: int, difficulty: str, topic: str = "General"):
    """Generate randomized Physics questions."""
    questions = []
    for _ in range(count):
        q_type = random.choice([
            "newton2", "ohms_law", "kinematics", "energy", "momentum", "waves",
        ])
        if q_type == "newton2":
            m = random.randint(1, 20)
            a = random.randint(2, 10)
            correct_str = str(m * a)
            distractors = [str(m + a), str(m - a), str(m * a + 1), str(int(m * a / 2))]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"A force accelerates a \\({m}\\,\\text{{kg}}\\) mass at \\({a}\\,\\text{{m/s}}^2\\). What is the force?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"Newton's Second Law: \\(F = ma = {m} \\times {a} = {m*a}\\,\\text{{N}}\\).",
                "topic": topic or "Mechanics",
            }
        elif q_type == "ohms_law":
            v = random.randint(5, 50)
            r = random.randint(2, 20)
            correct_val = v / r if v % r != 0 else v // r
            correct_str = str(correct_val)
            distractors = [str(v * r), str(v + r), str(v - r), str(int(v / r) + 1) if isinstance(correct_val, float) else str(v)]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"A circuit has voltage \\(V = {v}\\,\\text{{V}}\\) and resistance \\(R = {r}\\,\\Omega\\). Find the current.",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"Ohm's Law: \\(I = \\frac{{V}}{{R}} = \\frac{{{v}}}{{{r}}} = {correct_val}\\,\\text{{A}}\\).",
                "topic": topic or "Electromagnetism",
            }
        elif q_type == "kinematics":
            v0 = random.randint(0, 20)
            a = random.randint(2, 10)
            t = random.randint(2, 8)
            correct_val = v0 + a * t
            correct_str = str(correct_val)
            distractors = [str(v0 + a + t), str(v0 * t), str(a * t), str(v0 + a)]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"An object starts at \\(v_0 = {v0}\\,\\text{{m/s}}\\) with acceleration \\(a = {a}\\,\\text{{m/s}}^2\\) for \\(t = {t}\\,\\text{{s}}\\). Find the final velocity.",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\(v = v_0 + at = {v0} + {a} \\times {t} = {correct_val}\\,\\text{{m/s}}\\).",
                "topic": topic or "Mechanics",
            }
        elif q_type == "energy":
            m = random.randint(1, 10)
            h = random.randint(5, 30)
            g = 9.8
            correct_val = round(m * g * h, 1)
            correct_str = str(correct_val)
            distractors = [str(round(m * h, 1)), str(round(m * g + h, 1)), str(round(m * g * h + 1, 1)), str(round(m * h * g / 2, 1))]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"Find the gravitational potential energy of a \\({m}\\,\\text{{kg}}\\) object at height \\({h}\\,\\text{{m}}\\) (\\(g = 9.8\\,\\text{{m/s}}^2\\)).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\(E_p = mgh = {m} \\times 9.8 \\times {h} = {correct_val}\\,\\text{{J}}\\).",
                "topic": topic or "Mechanics",
            }
        elif q_type == "momentum":
            m = random.randint(2, 15)
            v = random.randint(3, 12)
            correct_str = str(m * v)
            distractors = [str(m + v), str(m * v + 1), str(int(m * v / 2)), str(m * v - 1)]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"What is the momentum of a \\({m}\\,\\text{{kg}}\\) object moving at \\({v}\\,\\text{{m/s}}\\)?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\(p = mv = {m} \\times {v} = {m*v}\\,\\text{{kg}}\\cdot\\text{{m/s}}\\).",
                "topic": topic or "Mechanics",
            }
        else:  # waves
            f = random.randint(2, 20)
            lam = random.randint(1, 10)
            correct_val = f * lam
            correct_str = str(correct_val)
            distractors = [str(f + lam), str(f * lam + 1), str(int(f * lam / 2)), str(f - lam) if f > lam else str(f + lam)]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"A wave has frequency \\(f = {f}\\,\\text{{Hz}}\\) and wavelength \\(\\lambda = {lam}\\,\\text{{m}}\\). Find the wave speed.",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\(v = f\\lambda = {f} \\times {lam} = {correct_val}\\,\\text{{m/s}}\\).",
                "topic": topic or "Waves",
            }
        q["subject"] = "Physics"
        q["difficulty"] = difficulty
        questions.append(q)
    return questions


def _gen_chemistry(count: int, difficulty: str, topic: str = "General"):
    """Generate randomized Chemistry questions."""
    questions = []
    for _ in range(count):
        q_type = random.choice([
            "moles", "ph", "balancing", "gas_law", "bonding", "organic",
        ])
        if q_type == "moles":
            mass = random.randint(10, 100)
            mw = random.choice([12, 18, 32, 44, 58])
            correct_val = round(mass / mw, 2)
            correct_str = str(correct_val)
            distractors = [str(round(mass * mw, 2)), str(round(mass / mw + 1, 2)), str(round(mass + mw, 2)), str(round(mass - mw, 2))]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"How many moles are in \\({mass}\\,\\text{{g}}\\) of a substance with molar mass \\({mw}\\,\\text{{g/mol}}\\)?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\(n = \\frac{{m}}{{M}} = \\frac{{{mass}}}{{{mw}}} = {correct_val}\\,\\text{{mol}}\\).",
                "topic": topic or "Stoichiometry",
            }
        elif q_type == "ph":
            h_conc = random.choice([1e-3, 1e-5, 1e-7, 1e-9, 1e-2])
            correct_val = round(-math.log10(h_conc), 1)
            correct_str = str(correct_val)
            distractors = [str(correct_val + 1), str(correct_val - 1), str(correct_val + 2), str(14 - correct_val)]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"Calculate the pH of a solution with \\([H^+] = {h_conc}\\,\\text{{mol/L}}\\).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"\\(\\text{{pH}} = -\\log[H^+] = -\\log({h_conc}) = {correct_val}\\).",
                "topic": topic or "Acids & Bases",
            }
        elif q_type == "balancing":
            correct_str = "2"
            distractors = ["1", "3", "4", "5"]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": "Balance: \\(\\text{{H}}_2 + \\text{{O}}_2 \\rightarrow \\text{{H}}_2\\text{{O}}\\). What coefficient is needed for \\(\\text{{H}}_2\\)?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": "Balanced equation: \\(2\\text{H}_2 + \\text{O}_2 \\rightarrow 2\\text{H}_2\\text{O}\\). The coefficient for \\(\\text{H}_2\\) is 2.",
                "topic": topic or "Stoichiometry",
            }
        elif q_type == "gas_law":
            p = random.randint(1, 5)
            v = random.randint(2, 10)
            n = random.randint(1, 3)
            t = random.randint(200, 400)
            r = 0.0821
            # PV = nRT => check consistency, generate a question about Boyle's law
            p1, v1 = random.randint(1, 5), random.randint(2, 10)
            p2 = random.randint(1, 5)
            correct_val = round(p1 * v1 / p2, 1)
            correct_str = str(correct_val)
            distractors = [str(round(p1 * p2 / v1, 1)), str(round(p2 * v1 / p1, 1)), str(round(p1 + v1 + p2, 1)), str(round(p1 * v1 * p2, 1))]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": f"At constant temperature, a gas has \\(P_1 = {p1}\\,\\text{{atm}}\\) and \\(V_1 = {v1}\\,\\text{{L}}\\). If \\(P_2 = {p2}\\,\\text{{atm}}\\), find \\(V_2\\) (Boyle's Law).",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": f"Boyle's Law: \\(P_1 V_1 = P_2 V_2 \\Rightarrow V_2 = \\frac{{{p1} \\times {v1}}}{{{p2}}} = {correct_val}\\,\\text{{L}}\\).",
                "topic": topic or "Gas Laws",
            }
        elif q_type == "bonding":
            correct_str = "4"
            distractors = ["2", "6", "8", "1"]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": "How many covalent bonds can a carbon atom form?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": "Carbon has 4 valence electrons, so it can form 4 covalent bonds to complete its octet.",
                "topic": topic or "Chemical Bonding",
            }
        else:  # organic
            correct_str = "\\(C_n H_{2n+2}\\)"
            distractors = ["\\(C_n H_{2n}\\)", "\\(C_n H_{2n-2}\\)", "\\(C_n H_n\\)", "\\(C_n H_{2n-6}\\)"]
            correct_letter, oa, ob, oc, od, oe = _pick_correct(correct_str, distractors)
            q = {
                "question_text": "What is the general formula for alkanes (saturated hydrocarbons)?",
                "option_a": oa, "option_b": ob, "option_c": oc,
                "option_d": od, "option_e": oe,
                "correct_option": correct_letter,
                "explanation": "Alkanes are saturated hydrocarbons with the general formula \\(C_n H_{2n+2}\\) (all single bonds).",
                "topic": topic or "Organic Chemistry",
            }
        q["subject"] = "Chemistry"
        q["difficulty"] = difficulty
        questions.append(q)
    return questions


# ---------------------------------------------------------------------------
# Keyword extraction for notes_to_exam
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "can", "this", "that", "these",
    "those", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "up", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "s", "t", "just", "now", "also", "if", "it", "its", "i", "you", "we",
    "they", "he", "she", "them", "his", "her", "their", "our", "your",
    "as", "because", "while", "within", "without", "which", "what", "who",
}


def _extract_keywords(text: str, max_keywords: int = 10) -> list:
    """Extract the most frequent meaningful keywords from text."""
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    freq = {}
    for t in tokens:
        if t in _STOPWORDS:
            continue
        freq[t] = freq.get(t, 0) + 1
    sorted_kw = sorted(freq.items(), key=lambda x: -x[1])
    return [kw for kw, _ in sorted_kw[:max_keywords]]


# ---------------------------------------------------------------------------
# Optional live LLM call via urllib.request
# ---------------------------------------------------------------------------

def _call_llm(api_key: str, prompt: str, system_prompt: str = "") -> str:
    """Make a minimal OpenAI-compatible chat completion call using urllib.
    Returns the assistant message text. Raises on error."""
    if not api_key:
        raise ValueError("No API key provided for live LLM call.")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt or "You are a helpful academic tutor."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_questions(
    subject: str,
    topic: str = "General",
    difficulty: str = "Medium",
    count: int = 5,
    api_key: str = "",
) -> dict:
    """Generate `count` randomized 5-option questions for the given subject.

    If a valid api_key is provided, attempts to use a live LLM; on any error
    falls back to the parametric engine. Returns a dict with 'source' and
    'questions' keys.
    """
    if subject not in ALLOWED_SUBJECTS:
        raise ValueError(
            f"Invalid subject '{subject}'. Must be one of {ALLOWED_SUBJECTS}."
        )

    # Try live LLM if api_key provided
    if api_key:
        try:
            llm_prompt = (
                f"Generate {count} multiple-choice questions on {subject} "
                f"(topic: {topic}, difficulty: {difficulty}). "
                "Return JSON: {\"questions\": [{\"question_text\": \"...\", "
                "\"option_a\": \"...\", \"option_b\": \"...\", \"option_c\": \"...\", "
                "\"option_d\": \"...\", \"option_e\": \"...\", \"correct_option\": \"A\"-\"E\", "
                "\"explanation\": \"...\", \"topic\": \"...\", \"difficulty\": \"...\"}]}"
            )
            raw = _call_llm(api_key, llm_prompt, system_prompt="You are an expert exam question writer.")
            parsed = json.loads(raw)
            if "questions" in parsed and len(parsed["questions"]) == count:
                return {"source": "live_llm", "questions": parsed["questions"]}
        except Exception:
            pass  # fall back to parametric

    # Parametric engine (default, 100% offline)
    if subject == "Mathematics":
        qs = _gen_math(count, difficulty, topic)
    elif subject == "Logic":
        qs = _gen_logic(count, difficulty, topic)
    elif subject == "Physics":
        qs = _gen_physics(count, difficulty, topic)
    elif subject == "Chemistry":
        qs = _gen_chemistry(count, difficulty, topic)
    else:
        raise ValueError(f"Unsupported subject: {subject}")

    return {"source": "parametric_engine", "questions": qs}


def notes_to_exam(
    notes_text: str,
    subject: str = "Physics",
    count: int = 5,
    api_key: str = "",
) -> dict:
    """Generate `count` 5-option questions tailored to keywords extracted
    from `notes_text`."""
    if subject not in ALLOWED_SUBJECTS:
        raise ValueError(
            f"Invalid subject '{subject}'. Must be one of {ALLOWED_SUBJECTS}."
        )

    keywords = _extract_keywords(notes_text)
    tailored_topic = ", ".join(keywords[:3]) if keywords else "General"

    # Try live LLM if api_key provided
    if api_key:
        try:
            llm_prompt = (
                f"Based on these study notes, generate {count} multiple-choice "
                f"{subject} questions (difficulty: Medium):\n\n{notes_text[:2000]}\n\n"
                "Return JSON: {\"questions\": [{\"question_text\": \"...\", "
                "\"option_a\": \"...\", \"option_b\": \"...\", \"option_c\": \"...\", "
                "\"option_d\": \"...\", \"option_e\": \"...\", \"correct_option\": \"A\"-\"E\", "
                "\"explanation\": \"...\", \"topic\": \"...\", \"difficulty\": \"...\"}]}"
            )
            raw = _call_llm(api_key, llm_prompt, system_prompt="You are an expert exam question writer who creates questions from student notes.")
            parsed = json.loads(raw)
            if "questions" in parsed and len(parsed["questions"]) == count:
                return {"source": "live_llm", "questions": parsed["questions"], "keywords": keywords}
        except Exception:
            pass

    result = generate_questions(subject, tailored_topic, "Medium", count, api_key="")
    result["keywords"] = keywords
    return result


def explain_trap(
    question_row: dict,
    selected_option: str,
    api_key: str = "",
) -> dict:
    """Explain why a selected option is wrong and how to avoid the trap."""
    correct_opt = question_row.get("correct_option", "")
    subject = question_row.get("subject", "")
    explanation = question_row.get("explanation", "")
    question_text = question_row.get("question_text", "")

    # Map option letters to their text
    option_texts = {}
    for letter in ("A", "B", "C", "D", "E"):
        key = f"option_{letter.lower()}"
        if key in question_row:
            option_texts[letter] = question_row[key]

    selected_text = option_texts.get(selected_option, "Unknown")
    correct_text = option_texts.get(correct_opt, "Unknown")

    if selected_option.upper() == correct_opt:
        trap_analysis = (
            f"You selected option {selected_option} which is CORRECT. "
            "Well done! No trap was triggered here."
        )
        core_rule = explanation
        penalty_tip = "Keep up the consistent reasoning and verify with the explanation."
    else:
        trap_analysis = (
            f"You selected option {selected_option} ('{selected_text}'), but the correct "
            f"answer is option {correct_opt} ('{correct_text}'). "
            f"The trap likely stems from a common misconception or a miscalculation "
            f"in the {subject} domain. Review the explanation carefully: {explanation}"
        )
        core_rule = (
            f"Core {subject} rule: {explanation} "
            "Always double-check the units, signs, and the applicability of the formula "
            "before committing to an answer."
        )
        penalty_tip = (
            "Under CISIA penalty scoring, a wrong answer costs -0.25 points. "
            "If you are not at least 70% confident, leave the question blank (0 points) "
            "rather than risking a negative score. Practice flagging uncertain questions "
            "and returning to them only if time permits."
        )

    return {
        "question_id": question_row.get("id"),
        "selected_option": selected_option,
        "correct_option": correct_opt,
        "trap_analysis": trap_analysis,
        "core_rule": core_rule,
        "penalty_tip": penalty_tip,
    }


def upgrade_essay_paragraph(
    text: str,
    task_type: str = "Task 2",
    api_key: str = "",
) -> dict:
    """Upgrade a single essay paragraph, providing vocabulary and grammar tips."""
    # Vocabulary upgrade mapping (common → academic)
    vocab_map = {
        "very": "considerably",
        "big": "substantial",
        "small": "negligible",
        "important": "crucial",
        "good": "beneficial",
        "bad": "detrimental",
        "a lot of": "numerous",
        "many people": "a significant proportion of individuals",
        "think": "argue",
        "get": "obtain",
        "show": "demonstrate",
        "use": "utilize",
        "help": "facilitate",
        "make": "constitute",
        "because": "due to the fact that",
        "so": "consequently",
        "also": "furthermore",
        "but": "nevertheless",
        "really": "genuinely",
        "thing": "factor",
        "way": "approach",
    }

    vocabulary_upgrades = []
    upgraded = text
    for informal, formal in vocab_map.items():
        pattern = re.compile(re.escape(informal), re.IGNORECASE)
        if pattern.search(upgraded):
            reason = f"'{informal}' is informal for academic writing; '{formal}' elevates the register."
            vocabulary_upgrades.append({
                "from": informal,
                "to": formal,
                "reason": reason,
            })
            upgraded = pattern.sub(formal, upgraded, count=1)

    # Grammar tips based on text analysis
    grammar_tips = []
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s for s in sentences if s.strip()]

    if sentences and all(len(s.split()) < 12 for s in sentences):
        grammar_tips.append(
            "Your sentences are quite short. Consider combining related ideas with "
            "subordinating conjunctions (e.g., 'although', 'whereas', 'given that') "
            "to demonstrate syntactic range."
        )
    if not re.search(r"\b(however|moreover|furthermore|consequently|nevertheless|in contrast|thus)\b", text, re.IGNORECASE):
        grammar_tips.append(
            "Add transition words (e.g., 'furthermore', 'consequently', 'in contrast') "
            "to improve cohesion between sentences and paragraphs."
        )
    if re.search(r"\b(I|you|we)\b", text):
        grammar_tips.append(
            "Avoid first and second person pronouns (I, you, we) in academic Task 2 essays. "
            "Use passive constructions or third-person phrasing for a more formal tone."
        )
    if len(sentences) > 0:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_len > 30:
            grammar_tips.append(
                f"Your average sentence length is {avg_len:.1f} words, which is quite long. "
                "Break overly complex sentences into two to improve readability."
            )
    if not grammar_tips:
        grammar_tips.append(
            "Your grammar is solid. Focus on varying sentence structures "
            "(simple, compound, complex) for a higher band score."
        )

    # If api_key provided, try live LLM for richer upgrades
    if api_key:
        try:
            llm_prompt = (
                f"Upgrade this IELTS {task_type} paragraph to band 7+ level. "
                f"Return JSON: {{\"upgraded_text\": \"...\", "
                f"\"vocabulary_upgrades\": [{{\"from\": \"...\", \"to\": \"...\", \"reason\": \"...\"}}], "
                f"\"grammar_tips\": [\"...\"]}}\n\nParagraph:\n{text}"
            )
            raw = _call_llm(api_key, llm_prompt, system_prompt="You are an expert IELTS writing tutor.")
            parsed = json.loads(raw)
            return {
                "original_text": text,
                "upgraded_text": parsed.get("upgraded_text", upgraded),
                "vocabulary_upgrades": parsed.get("vocabulary_upgrades", vocabulary_upgrades),
                "grammar_tips": parsed.get("grammar_tips", grammar_tips),
            }
        except Exception:
            pass  # fall back to parametric

    return {
        "original_text": text,
        "upgraded_text": upgraded,
        "vocabulary_upgrades": vocabulary_upgrades,
        "grammar_tips": grammar_tips,
    }
