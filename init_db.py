"""
init_db.py - Production-Grade Database Initializer & Seeder (v3.0+v4.0 Unified Edition).
Generates 60 authentic questions across 3 Mock Sets (Mathematics, Logic, Physics, Chemistry),
6 official-style IELTS Academic Writing prompts, 2 reading passages, and 20 flashcards.
v3.0+v4.0 unified schema with all analytics columns.
"""
import json
import os
import secrets
import sqlite3

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prep.db")
ALLOWED_SUBJECTS = ['Mathematics', 'Logic', 'Physics', 'Chemistry']

SCHEMA = """
DROP TABLE IF EXISTS announcements;
DROP TABLE IF EXISTS classroom_students;
DROP TABLE IF EXISTS classrooms;

CREATE TABLE classrooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    subject     TEXT DEFAULT 'All Subjects',
    invite_code TEXT UNIQUE NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE classroom_students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
    student_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(classroom_id, student_id)
);

CREATE TABLE announcements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    classroom_id INTEGER REFERENCES classrooms(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    content      TEXT NOT NULL,
    attachment_url TEXT DEFAULT '',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
DROP TABLE IF EXISTS assignment_submissions;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS teacher_students;
DROP TABLE IF EXISTS attempt_answers;
DROP TABLE IF EXISTS exam_attempts;
DROP TABLE IF EXISTS bookmarks;
DROP TABLE IF EXISTS flashcards;
DROP TABLE IF EXISTS reading_passages;
DROP TABLE IF EXISTS writing_submissions;
DROP TABLE IF EXISTS writing_prompts;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student','teacher')),
    invite_code     TEXT UNIQUE,
    auth_provider   TEXT NOT NULL DEFAULT 'local',
    google_sub      TEXT,
    avatar_url      TEXT DEFAULT '',
    target_uni      TEXT DEFAULT 'Politecnico di Milano',
    target_score    REAL DEFAULT 16.0,
    target_ielts    REAL DEFAULT 7.0,
    ai_api_key      TEXT DEFAULT '',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mock_set        INTEGER DEFAULT 1,
    subject         TEXT NOT NULL,
    topic           TEXT DEFAULT 'General',
    question_text   TEXT NOT NULL,
    option_a        TEXT NOT NULL,
    option_b        TEXT NOT NULL,
    option_c        TEXT NOT NULL,
    option_d        TEXT NOT NULL,
    option_e        TEXT NOT NULL DEFAULT '',
    correct_option  TEXT NOT NULL CHECK (correct_option IN ('A','B','C','D','E')),
    explanation     TEXT NOT NULL,
    difficulty      TEXT NOT NULL CHECK (difficulty IN ('Easy','Medium','Hard'))
);

CREATE TABLE writing_prompts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type           TEXT NOT NULL,
    title               TEXT NOT NULL,
    prompt_text         TEXT NOT NULL,
    chart_svg_or_table  TEXT DEFAULT ''
);

CREATE TABLE writing_submissions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    prompt_id               INTEGER REFERENCES writing_prompts(id),
    task_type               TEXT NOT NULL,
    prompt_text             TEXT NOT NULL,
    essay_text              TEXT NOT NULL,
    word_count              INTEGER DEFAULT 0,
    paragraph_count         INTEGER DEFAULT 0,
    lexical_diversity       REAL DEFAULT 0.0,
    avg_sentence_length     REAL DEFAULT 0.0,
    transition_words_used   INTEGER DEFAULT 0,
    estimated_band          REAL DEFAULT 0.0,
    feedback_json           TEXT DEFAULT '{}',
    timestamp               DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reading_passages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    topic           TEXT DEFAULT 'Academic',
    passage_html    TEXT NOT NULL,
    questions_json  TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE flashcards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER DEFAULT 1 REFERENCES users(id),
    subject     TEXT NOT NULL,
    topic       TEXT DEFAULT 'Core',
    front_text  TEXT NOT NULL,
    back_text   TEXT NOT NULL
);

CREATE TABLE bookmarks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    question_id     INTEGER NOT NULL REFERENCES questions(id),
    is_auto_mistake INTEGER DEFAULT 0,
    note            TEXT DEFAULT '',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, question_id)
);

CREATE TABLE exam_attempts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    exam_mode           TEXT DEFAULT 'Mock 1',
    total_score         REAL DEFAULT 0.0,
    max_possible_score  REAL DEFAULT 0.0,
    correct_count       INTEGER DEFAULT 0,
    wrong_count         INTEGER DEFAULT 0,
    blank_count         INTEGER DEFAULT 0,
    duration_seconds    INTEGER DEFAULT 0,
    timestamp           DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE attempt_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL REFERENCES exam_attempts(id) ON DELETE CASCADE,
    question_id     INTEGER NOT NULL REFERENCES questions(id),
    selected_option TEXT DEFAULT '',
    points_awarded  REAL DEFAULT 0.0,
    subject         TEXT DEFAULT ''
);

CREATE TABLE teacher_students (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(teacher_id, student_id)
);

CREATE TABLE assignments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_id          INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    description         TEXT DEFAULT '',
    assignment_type     TEXT NOT NULL DEFAULT 'exam' CHECK (assignment_type IN ('exam','writing','reading')),
    question_ids_json   TEXT DEFAULT '[]',
    writing_prompt_id   INTEGER,
    reading_passage_id  INTEGER,
    time_limit_mins     INTEGER DEFAULT 40,
    due_date            TEXT DEFAULT '',
    strict_mode         INTEGER DEFAULT 1,
    classroom_id        INTEGER,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assignment_submissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_id      INTEGER REFERENCES exam_attempts(id) ON DELETE SET NULL,
    writing_id      INTEGER REFERENCES writing_submissions(id) ON DELETE SET NULL,
    score           REAL,
    max_score       REAL,
    status          TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','graded')),
    teacher_comment TEXT DEFAULT '',
    teacher_grade   REAL,
    tab_switches    INTEGER DEFAULT 0,
    rubric_json     TEXT DEFAULT '{}',
    submitted_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(assignment_id, student_id)
);
"""

# ---------------------------------------------------------------------------
# USERS  (email, name, password_hash, role, invite_code, auth_provider,
#          google_sub, avatar_url, target_uni, target_score, target_ielts, ai_api_key)
# ---------------------------------------------------------------------------
USERS_DATA = [
    (
        "ali@student.eu",
        "Ali Farzaneh",
        generate_password_hash("Student2026!", method="pbkdf2:sha256"),
        "student", None, "local", None, "",
        "Politecnico di Milano", 16.5, 7.5, ""
    ),
    (
        "instructor@academy.eu",
        "Dr. Lorenzoetti (Instructor)",
        generate_password_hash("Teacher2026!", method="pbkdf2:sha256"),
        "teacher", "CENTS2026", "local", None, "",
        "Politecnico di Milano", 20.0, 8.5, ""
    ),
]

# ---------------------------------------------------------------------------
# 60 Questions  (mock_set, subject, topic, question_text,
#                opt_a, opt_b, opt_c, opt_d, opt_e, correct, explanation, difficulty)
# ---------------------------------------------------------------------------
QUESTIONS_DATA = [
    # ================= MOCK 1 (20 Questions) =================
    # Math (Mock 1)
    (1, "Mathematics", "Calculus", "Evaluate the definite integral \\(\\displaystyle\\int_0^{2} 3x^{2}\\,dx\\).", "\\(4\\)", "\\(6\\)", "\\(8\\)", "\\(12\\)", "\\(16\\)", "C", "By the power rule, \\(\\int 3x^2 dx = x^3\\). Evaluating from 0 to 2 gives \\(2^3 - 0 = 8\\).", "Easy"),
    (1, "Mathematics", "Algebra", "If \\(\\log_{2} x + \\log_{2}(x - 2) = 3\\), find the real value of \\(x\\).", "\\(4\\)", "\\(3\\)", "\\(2\\)", "\\(6\\)", "\\(8\\)", "A", "\\(\\log_2(x(x-2)) = 3 \\Rightarrow x^2 - 2x - 8 = 0 \\Rightarrow (x-4)(x+2)=0\\). Since \\(x>2\\), \\(x=4\\).", "Medium"),
    (1, "Mathematics", "Calculus", "The sum of the infinite geometric series \\(\\displaystyle\\sum_{n=0}^{\\infty}\\frac{1}{2^{n+1}}\\) equals:", "\\(\\frac{1}{2}\\)", "\\(1\\)", "\\(\\frac{2}{3}\\)", "\\(2\\)", "\\(\\frac{3}{2}\\)", "B", "First term \\(a = 1/2\\), ratio \\(r = 1/2\\). Sum \\(S = \\frac{a}{1-r} = \\frac{1/2}{1/2} = 1\\).", "Easy"),
    (1, "Mathematics", "Calculus", "Given \\(f(x) = x^3 - 3x + 1\\), how many distinct real roots does \\(f(x) = 0\\) have?", "None", "One", "Two", "Three", "Four", "D", "\\(f'(x)=3x^2-3=0 \\Rightarrow x=\\pm 1\\). Since \\(f(-1)=3>0\\) and \\(f(1)=-1<0\\), the cubic crosses the axis 3 times.", "Hard"),
    (1, "Mathematics", "Combinatorics", "How many distinct 4-letter strings can be formed from \\(\\{A,B,C,D,E\\}\\) without repetition?", "\\(24\\)", "\\(60\\)", "\\(120\\)", "\\(240\\)", "\\(625\\)", "C", "Permutations of 5 items taken 4 at a time: \\(P(5,4) = 5 \\times 4 \\times 3 \\times 2 = 120\\).", "Medium"),
    # Logic (Mock 1)
    (1, "Logic", "Syllogism", "All A are B. Some B are C. Which conclusion necessarily follows?", "All A are C", "Some A are C", "No A is C", "Some C are not A", "None of the above necessarily follows", "E", "There is no guaranteed overlap between sets A and C.", "Easy"),
    (1, "Logic", "Propositional", "If the light is red, the car stops. The car stopped. What follows about the light?", "It was definitely red", "It was definitely green", "It was not red", "Cannot be deduced with certainty", "The car broke down", "D", "Affirming the consequent (\\(P\\to Q, Q \\vdash P\\)) is a formal fallacy.", "Easy"),
    (1, "Logic", "Combinatorics", "Six people are seated around a circular table. How many distinct arrangements exist up to rotation?", "\\(720\\)", "\\(360\\)", "\\(120\\)", "\\(60\\)", "\\(24\\)", "C", "Circular permutations of \\(n\\) objects: \\((n-1)! = 5! = 120\\).", "Medium"),
    (1, "Logic", "Counting", "A 4-digit PIN uses digits 0-9 with repetition allowed, but the first digit cannot be 0. How many PINs exist?", "\\(10000\\)", "\\(9000\\)", "\\(5040\\)", "\\(4536\\)", "\\(8100\\)", "B", "9 choices for the first digit and 10 for each of the remaining three: \\(9 \\times 10^3 = 9000\\).", "Easy"),
    (1, "Logic", "Quantifiers", "What is the logical negation of the statement \\(\\forall x\\, P(x)\\)?", "\\(\\forall x\\, \\neg P(x)\\)", "\\(\\exists x\\, \\neg P(x)\\)", "\\(\\exists x\\, P(x)\\)", "\\(\\neg \\exists x\\, P(x)\\)", "\\(P(x) \\to \\neg P(x)\\)", "B", "De Morgan's law for quantifiers: \\(\\neg \\forall x\\, P(x) \\equiv \\exists x\\, \\neg P(x)\\).", "Medium"),
    # Physics (Mock 1)
    (1, "Physics", "Mechanics", "An object is dropped from height \\(h\\) in vacuum. Its impact speed is proportional to:", "\\(h\\)", "\\(\\sqrt{h}\\)", "\\(h^2\\)", "\\(1/h\\)", "\\(1/\\sqrt{h}\\)", "B", "From conservation of energy \\(mgh = \\frac{1}{2}mv^2 \\Rightarrow v = \\sqrt{2gh} \\propto \\sqrt{h}\\).", "Easy"),
    (1, "Physics", "Oscillations", "The period \\(T\\) of a simple pendulum of length \\(L\\) in gravitational field \\(g\\) is:", "\\(2\\pi\\sqrt{L/g}\\)", "\\(\\pi\\sqrt{L/g}\\)", "\\(2\\pi\\sqrt{g/L}\\)", "\\(\\frac{1}{2\\pi}\\sqrt{L/g}\\)", "\\(2\\pi L/g\\)", "A", "For small oscillations, \\(T = 2\\pi\\sqrt{L/g}\\).", "Easy"),
    (1, "Physics", "Mechanics", "A 2 kg block moving at 3 m/s collides elastically with a wall and reverses direction at 3 m/s. The impulse magnitude is:", "\\(0\\,\\text{N}\\cdot\\text{s}\\)", "\\(3\\,\\text{N}\\cdot\\text{s}\\)", "\\(6\\,\\text{N}\\cdot\\text{s}\\)", "\\(9\\,\\text{N}\\cdot\\text{s}\\)", "\\(12\\,\\text{N}\\cdot\\text{s}\\)", "E", "Impulse \\(J = |\\Delta p| = |m(-v) - mv| = |2(-3) - 2(3)| = 12\\,\\text{N}\\cdot\\text{s}\\).", "Medium"),
    (1, "Physics", "Thermodynamics", "For an ideal gas in an isothermal expansion from \\(V_1\\) to \\(V_2\\), the work done by the gas is:", "\\(P_1(V_2-V_1)\\)", "\\(nRT\\ln(V_2/V_1)\\)", "\\(0\\)", "\\(C_v \\Delta T\\)", "\\(P_2 V_2 - P_1 V_1\\)", "B", "In an isothermal process \\(T\\) is constant, so \\(W = \\int P\\,dV = nRT\\ln(V_2/V_1)\\).", "Hard"),
    (1, "Physics", "Electromagnetism", "A charge of \\(6\\,\\text{C}\\) flows through a resistor in \\(3\\,\\text{s}\\). What is the electric current?", "\\(0.5\\,\\text{A}\\)", "\\(1.5\\,\\text{A}\\)", "\\(2.0\\,\\text{A}\\)", "\\(3.0\\,\\text{A}\\)", "\\(18.0\\,\\text{A}\\)", "C", "Electric current \\(I = Q/t = 6/3 = 2.0\\,\\text{A}\\).", "Easy"),
    # Chemistry (Mock 1)
    (1, "Chemistry", "Acid-Base", "The pH of a \\(0.001\\,\\text{M}\\) \\(\\text{HCl}\\) aqueous solution at \\(25^\\circ\\text{C}\\) is:", "\\(1\\)", "\\(2\\)", "\\(3\\)", "\\(7\\)", "\\(11\\)", "C", "HCl completely dissociates: \\([\\text{H}^+] = 10^{-3}\\,\\text{M} \\Rightarrow \\text{pH} = -\\log_{10}(10^{-3}) = 3\\).", "Easy"),
    (1, "Chemistry", "Nomenclature", "Which of the following chemical formulas represents an INVALID neutral species?", "\\(\\text{NaHSO}_4\\)", "\\(\\text{Na}_2\\text{SO}_4\\)", "\\(\\text{H}_2\\text{SO}_4\\)", "\\(\\text{NaSO}_4\\)", "\\(\\text{CaSO}_4\\)", "D", "Since sulfate is \\(\\text{SO}_4^{2-}\\) and sodium is \\(\\text{Na}^+\\), a neutral salt requires two sodium ions: \\(\\text{Na}_2\\text{SO}_4\\).", "Medium"),
    (1, "Chemistry", "Electrochemistry", "Given \\(E^\\circ(\\text{Zn}^{2+}/\\text{Zn}) = -0.76\\,\\text{V}\\) and \\(E^\\circ(\\text{Cu}^{2+}/\\text{Cu}) = +0.34\\,\\text{V}\\), the standard EMF of a Zn-Cu galvanic cell is:", "\\(+0.42\\,\\text{V}\\)", "\\(-0.42\\,\\text{V}\\)", "\\(+1.10\\,\\text{V}\\)", "\\(-1.10\\,\\text{V}\\)", "\\(+0.76\\,\\text{V}\\)", "C", "\\(E^\\circ_{\\text{cell}} = E^\\circ_{\\text{cathode}} - E^\\circ_{\\text{anode}} = 0.34 - (-0.76) = +1.10\\,\\text{V}\\).", "Medium"),
    (1, "Chemistry", "Thermodynamics", "A reaction has \\(\\Delta H = -150\\,\\text{kJ/mol}\\) and \\(\\Delta S = +200\\,\\text{J/(mol}\\cdot\\text{K)}\\). When is it spontaneous?", "Only at high T", "Only at low T", "At all temperatures", "Never spontaneous", "Only at T = 298 K", "C", "\\(\\Delta G = \\Delta H - T\\Delta S\\). Since \\(\\Delta H < 0\\) and \\(\\Delta S > 0\\), \\(\\Delta G < 0\\) for all \\(T > 0\\).", "Hard"),
    (1, "Chemistry", "Stoichiometry", "What is the empirical formula of a compound containing 40% C, 6.7% H, and 53.3% O by mass?", "\\(\\text{CH}_2\\text{O}\\)", "\\(\\text{C}_2\\text{H}_4\\text{O}\\)", "\\(\\text{CH}_4\\text{O}\\)", "\\(\\text{C}_3\\text{H}_6\\text{O}_2\\)", "\\(\\text{CHO}\\)", "A", "Moles per 100g: C = 40/12 = 3.33, H = 6.7/1 = 6.7, O = 53.3/16 = 3.33. Ratio is 1:2:1.", "Medium"),

    # ================= MOCK 2 (20 Questions) =================
    # Math (Mock 2)
    (2, "Mathematics", "Calculus", "Evaluate the limit \\(\\displaystyle\\lim_{x\\to 0}\\frac{\\sin(5x)}{x}\\).", "\\(0\\)", "\\(1\\)", "\\(5\\)", "\\(1/5\\)", "\\(\\infty\\)", "C", "Using the standard limit \\(\\lim_{u\\to 0}\\frac{\\sin u}{u}=1\\), we multiply and divide by 5 to get 5.", "Easy"),
    (2, "Mathematics", "Linear Algebra", "What is the determinant of the matrix \\(A = \\begin{pmatrix} 3 & 2 \\\\ 1 & 4 \\end{pmatrix}\\)?", "\\(10\\)", "\\(12\\)", "\\(14\\)", "\\(8\\)", "\\(-10\\)", "A", "\\(\\det(A) = (3)(4) - (2)(1) = 12 - 2 = 10\\).", "Easy"),
    (2, "Mathematics", "Calculus", "Find the area enclosed between \\(y = x\\) and \\(y = x^2\\) for \\(x \\in [0,1]\\).", "\\(1/2\\)", "\\(1/3\\)", "\\(1/4\\)", "\\(1/6\\)", "\\(1/12\\)", "D", "\\(\\int_0^1 (x - x^2)\\,dx = [x^2/2 - x^3/3]_0^1 = 1/2 - 1/3 = 1/6\\).", "Medium"),
    (2, "Mathematics", "Algebra", "By Vieta's formulas, the sum of the roots of \\(2x^3 - 12x^2 + 7x - 5 = 0\\) is:", "\\(12\\)", "\\(6\\)", "\\(-6\\)", "\\(7/2\\)", "\\(5/2\\)", "B", "Sum of roots for \\(ax^3+bx^2+cx+d=0\\) is \\(-b/a = -(-12)/2 = 6\\).", "Medium"),
    (2, "Mathematics", "Calculus", "At which point is the tangent to \\(y = x^3 - 3x\\) parallel to the x-axis for \\(x > 0\\)?", "\\((1, -2)\\)", "\\((1, 2)\\)", "\\((0, 0)\\)", "\\((3, 18)\\)", "\\((2, 2)\\)", "A", "\\(y' = 3x^2 - 3 = 0 \\Rightarrow x = 1\\) (for \\(x>0\\)). Then \\(y(1) = 1 - 3 = -2\\).", "Hard"),
    # Logic (Mock 2)
    (2, "Logic", "Propositional", "Which statement is the contrapositive of \\(P \\to Q\\)?", "\\(Q \\to P\\)", "\\(\\neg P \\to \\neg Q\\)", "\\(\\neg Q \\to \\neg P\\)", "\\(P \\wedge \\neg Q\\)", "\\(\\neg P \\vee Q\\)", "C", "The contrapositive negates and swaps both terms: \\(\\neg Q \\to \\neg P\\).", "Easy"),
    (2, "Logic", "Boolean", "By De Morgan's laws, \\(\\neg(P \\wedge Q)\\) is logically equivalent to:", "\\(\\neg P \\wedge \\neg Q\\)", "\\(\\neg P \\vee \\neg Q\\)", "\\(P \\vee Q\\)", "\\(P \\to Q\\)", "\\(\\neg P \\to Q\\)", "B", "Negating a conjunction yields the disjunction of the negations: \\(\\neg P \\vee \\neg Q\\).", "Easy"),
    (2, "Logic", "Probability", "Two fair six-sided dice are rolled. What is the probability that the sum is 7?", "\\(1/12\\)", "\\(1/9\\)", "\\(1/6\\)", "\\(5/36\\)", "\\(7/36\\)", "C", "There are 6 favorable pairs out of 36 outcomes: \\(6/36 = 1/6\\).", "Medium"),
    (2, "Logic", "Deduction", "In a tournament, if Team X plays, Team Y sits out. Team Y played today. Therefore:", "Team X played", "Team X did not play", "Both teams played", "The game was canceled", "Cannot be determined", "B", "By Modus Tollens (\\(X \\to \\neg Y\\), and \\(Y\\) is true, so \\(\\neg X\\) must be true).", "Medium"),
    (2, "Logic", "Combinatorics", "How many subsets does a set with 6 distinct elements have (including empty set)?", "\\(12\\)", "\\(32\\)", "\\(36\\)", "\\(64\\)", "\\(720\\)", "D", "The power set of an \\(n\\)-element set has \\(2^n = 2^6 = 64\\) subsets.", "Easy"),
    # Physics (Mock 2)
    (2, "Physics", "Mechanics", "A ball is thrown vertically upward at \\(20\\,\\text{m/s}\\) (\\(g = 10\\,\\text{m/s}^2\\)). What is its maximum height?", "\\(10\\,\\text{m}\\)", "\\(20\\,\\text{m}\\)", "\\(30\\,\\text{m}\\)", "\\(40\\,\\text{m}\\)", "\\(80\\,\\text{m}\\)", "B", "\\(h = v_0^2 / (2g) = 400 / 20 = 20\\,\\text{m}\\).", "Easy"),
    (2, "Physics", "Mechanics", "A block slides down a frictionless \\(30^\\circ\\) incline (\\(g = 10\\,\\text{m/s}^2\\)). Its acceleration is:", "\\(2.5\\,\\text{m/s}^2\\)", "\\(5.0\\,\\text{m/s}^2\\)", "\\(7.5\\,\\text{m/s}^2\\)", "\\(8.66\\,\\text{m/s}^2\\)", "\\(10.0\\,\\text{m/s}^2\\)", "B", "\\(a = g\\sin(30^\\circ) = 10 \\times 0.5 = 5.0\\,\\text{m/s}^2\\).", "Easy"),
    (2, "Physics", "Thermodynamics", "What is the Carnot efficiency of a heat engine operating between \\(600\\,\\text{K}\\) and \\(300\\,\\text{K}\\)?", "\\(25\\%\\)", "\\(33\\%\\)", "\\(50\\%\\)", "\\(67\\%\\)", "\\(100\\%\\)", "C", "\\(\\eta = 1 - T_C/T_H = 1 - 300/600 = 0.50 = 50\\%\\).", "Medium"),
    (2, "Physics", "Electromagnetism", "Two resistors of \\(6\\,\\Omega\\) and \\(3\\,\\Omega\\) are connected in parallel. Their equivalent resistance is:", "\\(1.5\\,\\Omega\\)", "\\(2.0\\,\\Omega\\)", "\\(4.5\\,\\Omega\\)", "\\(9.0\\,\\Omega\\)", "\\(18.0\\,\\Omega\\)", "B", "\\(R_{eq} = \\frac{R_1 R_2}{R_1 + R_2} = \\frac{18}{9} = 2.0\\,\\Omega\\).", "Easy"),
    (2, "Physics", "Rotation", "The moment of inertia of a uniform solid disk of mass \\(M\\) and radius \\(R\\) about its central axis is:", "\\(MR^2\\)", "\\(\\frac{1}{2}MR^2\\)", "\\(\\frac{2}{5}MR^2\\)", "\\(\\frac{2}{3}MR^2\\)", "\\(\\frac{1}{4}MR^2\\)", "B", "Integrating concentric rings from 0 to \\(R\\) yields \\(I = \\frac{1}{2}MR^2\\).", "Hard"),
    # Chemistry (Mock 2)
    (2, "Chemistry", "Stoichiometry", "What mass of \\(\\text{NaOH}\\) (\\(M = 40\\,\\text{g/mol}\\)) is needed to prepare \\(500\\,\\text{mL}\\) of a \\(0.5\\,\\text{M}\\) solution?", "\\(5\\,\\text{g}\\)", "\\(10\\,\\text{g}\\)", "\\(20\\,\\text{g}\\)", "\\(40\\,\\text{g}\\)", "\\(50\\,\\text{g}\\)", "B", "Moles \\(n = M \\times V = 0.5 \\times 0.5 = 0.25\\,\\text{mol}\\). Mass \\(= 0.25 \\times 40 = 10\\,\\text{g}\\).", "Easy"),
    (2, "Chemistry", "Acid-Base", "According to Brønsted-Lowry theory, the conjugate base of \\(\\text{H}_2\\text{SO}_4\\) is:", "\\(\\text{SO}_4^{2-}\\)", "\\(\\text{HSO}_4^-\\)", "\\(\\text{H}_3\\text{SO}_4^+\\)", "\\(\\text{H}_2\\text{SO}_3\\)", "\\(\\text{OH}^-\\)", "B", "Removing a single proton (\\(\\text{H}^+\\)) from \\(\\text{H}_2\\text{SO}_4\\) leaves \\(\\text{HSO}_4^-\\).", "Easy"),
    (2, "Chemistry", "Redox", "What is the oxidation state of Chromium (Cr) in the dichromate ion \\(\\text{Cr}_2\\text{O}_7^{2-}\\)?", "\\(+3\\)", "\\(+4\\)", "\\(+5\\)", "\\(+6\\)", "\\(+7\\)", "D", "\\(2x + 7(-2) = -2 \\Rightarrow 2x = 12 \\Rightarrow x = +6\\).", "Medium"),
    (2, "Chemistry", "Stoichiometry", "In \\(2\\text{Al} + \\text{Fe}_2\\text{O}_3 \\to \\text{Al}_2\\text{O}_3 + 2\\text{Fe}\\), how many grams of Al (\\(27\\,\\text{g/mol}\\)) produce \\(112\\,\\text{g}\\) of Fe (\\(56\\,\\text{g/mol}\\))?", "\\(27\\,\\text{g}\\)", "\\(54\\,\\text{g}\\)", "\\(81\\,\\text{g}\\)", "\\(108\\,\\text{g}\\)", "\\(112\\,\\text{g}\\)", "B", "\\(112\\,\\text{g Fe} = 2\\,\\text{mol Fe}\\), requiring \\(2\\,\\text{mol Al} = 2 \\times 27 = 54\\,\\text{g}\\).", "Medium"),
    (2, "Chemistry", "Gas Laws", "At STP (\\(0^\\circ\\text{C}\\), \\(1\\,\\text{atm}\\)), what volume does \\(2\\,\\text{mol}\\) of an ideal gas occupy?", "\\(11.2\\,\\text{L}\\)", "\\(22.4\\,\\text{L}\\)", "\\(33.6\\,\\text{L}\\)", "\\(44.8\\,\\text{L}\\)", "\\(67.2\\,\\text{L}\\)", "D", "1 mol occupies \\(22.4\\,\\text{L}\\) at STP, so 2 mol occupy \\(44.8\\,\\text{L}\\).", "Easy"),

    # ================= MOCK 3 (20 Questions) =================
    # Math (Mock 3)
    (3, "Mathematics", "Calculus", "Find the derivative \\(\\frac{dy}{dx}\\) of \\(y = e^{2x}\\cos x\\).", "\\(e^{2x}(2\\cos x - \\sin x)\\)", "\\(e^{2x}(\\cos x - 2\\sin x)\\)", "\\(2e^{2x}\\sin x\\)", "\\(-2e^{2x}\\sin x\\)", "\\(e^{2x}(2\\cos x + \\sin x)\\)", "A", "By the product rule: \\((e^{2x})'\\cos x + e^{2x}(\\cos x)' = 2e^{2x}\\cos x - e^{2x}\\sin x\\).", "Medium"),
    (3, "Mathematics", "Series", "Evaluate the telescoping series \\(\\displaystyle\\sum_{n=1}^{\\infty}\\frac{1}{n(n+1)}\\).", "\\(1/2\\)", "\\(1\\)", "\\(2\\)", "\\(\\pi^2/6\\)", "Diverges", "B", "Since \\(\\frac{1}{n(n+1)} = \\frac{1}{n} - \\frac{1}{n+1}\\), partial sums equal \\(1 - \\frac{1}{N+1} \\to 1\\).", "Hard"),
    (3, "Mathematics", "Combinatorics", "In how many ways can a 3-person committee be chosen from 4 men and 3 women with at least 1 woman?", "\\(35\\)", "\\(31\\)", "\\(27\\)", "\\(18\\)", "\\(12\\)", "B", "Total committees \\(\\binom{7}{3}=35\\) minus all-male committees \\(\\binom{4}{3}=4\\) gives \\(35-4=31\\).", "Medium"),
    (3, "Mathematics", "Linear Algebra", "If \\(A\\) is a \\(2\\times 2\\) matrix with \\(\\det(A) = 6\\), what is \\(\\det(2A)\\)?", "\\(6\\)", "\\(12\\)", "\\(18\\)", "\\(24\\)", "\\(36\\)", "D", "For an \\(n\\times n\\) matrix, \\(\\det(kA) = k^n \\det(A) = 2^2 \\times 6 = 24\\).", "Medium"),
    (3, "Mathematics", "Algebra", "What is the sum of the first 20 positive integers (\\(1 + 2 + \\dots + 20\\))?", "\\(190\\)", "\\(200\\)", "\\(210\\)", "\\(220\\)", "\\(400\\)", "C", "Using \\(n(n+1)/2\\): \\(20 \\times 21 / 2 = 210\\).", "Easy"),
    # Logic (Mock 3)
    (3, "Logic", "Propositional", "The conditional statement \\(P \\to Q\\) is logically equivalent to:", "\\(P \\wedge Q\\)", "\\(\\neg P \\vee Q\\)", "\\(P \\vee \\neg Q\\)", "\\(\\neg P \\wedge \\neg Q\\)", "\\(Q \\to P\\)", "B", "Material implication rule: \\(P \\to Q \\equiv \\neg P \\vee Q\\).", "Easy"),
    (3, "Logic", "Induction", "In mathematical induction, after verifying the base case \\(n=1\\), the inductive step proves:", "\\(P(n)\\) is true for all \\(n\\)", "\\(P(k) \\to P(k+1)\\)", "\\(\\neg P(k) \\to \\neg P(1)\\)", "\\(P(1) \\to P(2)\\)", "\\(P(k) \\wedge \\neg P(k+1)\\)", "B", "The inductive step assumes \\(P(k)\\) and deduces \\(P(k+1)\\).", "Easy"),
    (3, "Logic", "Set Theory", "If \\(|A| = 10\\), \\(|B| = 8\\), and \\(|A \\cap B| = 3\\), what is \\(|A \\cup B|\\)?", "\\(12\\)", "\\(15\\)", "\\(18\\)", "\\(21\\)", "\\(24\\)", "B", "Inclusion-Exclusion Principle: \\(|A \\cup B| = 10 + 8 - 3 = 15\\).", "Easy"),
    (3, "Logic", "Propositional", "Which of the following is a tautology (always true)?", "\\(P \\wedge \\neg P\\)", "\\(P \\vee \\neg P\\)", "\\(P \\to \\neg P\\)", "\\(P \\leftrightarrow \\neg P\\)", "\\((P \\vee Q) \\to P\\)", "B", "The Law of Excluded Middle (\\(P \\vee \\neg P\\)) is true for every truth assignment.", "Easy"),
    (3, "Logic", "Number Theory", "If the product of two integers \\(a \\cdot b\\) is odd, which statement must be true?", "Both a and b are even", "Exactly one is odd", "Both a and b are odd", "a + b is odd", "a - b is odd", "C", "A product of integers is odd if and only if every factor is odd.", "Medium"),
    # Physics (Mock 3)
    (3, "Physics", "Oscillations", "A \\(2\\,\\text{kg}\\) mass on a spring of constant \\(k = 50\\,\\text{N/m}\\) oscillates with angular frequency \\(\\omega\\) equal to:", "\\(2.5\\,\\text{rad/s}\\)", "\\(5.0\\,\\text{rad/s}\\)", "\\(10.0\\,\\text{rad/s}\\)", "\\(25.0\\,\\text{rad/s}\\)", "\\(100\\,\\text{rad/s}\\)", "B", "\\(\\omega = \\sqrt{k/m} = \\sqrt{50/2} = \\sqrt{25} = 5.0\\,\\text{rad/s}\\).", "Easy"),
    (3, "Physics", "Thermodynamics", "In an adiabatic process for an ideal gas, which quantity remains constant?", "\\(P V\\)", "\\(P / T\\)", "\\(P V^\\gamma\\)", "\\(V / T\\)", "\\(P + V\\)", "C", "For a reversible adiabatic process, \\(P V^\\gamma = \\text{constant}\\).", "Medium"),
    (3, "Physics", "Electromagnetism", "The magnetic field at distance \\(r\\) from a long straight wire carrying current \\(I\\) is:", "\\(\\frac{\\mu_0 I}{2\\pi r}\\)", "\\(\\frac{\\mu_0 I}{4\\pi r^2}\\)", "\\(\\mu_0 n I\\)", "\\(2\\pi r \\mu_0 I\\)", "\\(\\frac{\\mu_0 I}{2r}\\)", "A", "By Ampère's Law around a circular loop of radius \\(r\\), \\(B = \\frac{\\mu_0 I}{2\\pi r}\\).", "Medium"),
    (3, "Physics", "Optics", "Light travels from air (\\(n_1=1\\)) into glass (\\(n_2=1.5\\)) at incidence angle \\(30^\\circ\\). Then \\(\\sin\\theta_2\\) equals:", "\\(1/2\\)", "\\(1/3\\)", "\\(3/4\\)", "\\(2/3\\)", "\\(1/4\\)", "B", "Snell's Law: \\(n_1\\sin 30^\\circ = n_2\\sin\\theta_2 \\Rightarrow 1(0.5) = 1.5\\sin\\theta_2 \\Rightarrow \\sin\\theta_2 = 1/3\\).", "Medium"),
    (3, "Physics", "Modern Physics", "If the frequency of incident photons is doubled, the energy of each photon:", "Halves", "Stays the same", "Doubles", "Quadruples", "Increases by \\(\\sqrt{2}\\)", "C", "Photon energy \\(E = hf\\) is directly proportional to frequency \\(f\\).", "Easy"),
    # Chemistry (Mock 3)
    (3, "Chemistry", "Acid-Base", "Which of the following \\(0.1\\,\\text{M}\\) aqueous solutions has the HIGHEST pH?", "\\(\\text{HCl}\\)", "\\(\\text{CH}_3\\text{COOH}\\)", "\\(\\text{NaCl}\\)", "\\(\\text{NH}_3\\)", "\\(\\text{NaOH}\\)", "E", "\\(\\text{NaOH}\\) is a strong base (\\(\\text{pH} = 13\\)), giving the highest pH among the choices.", "Easy"),
    (3, "Chemistry", "Kinetics", "For a rate law \\(\\text{Rate} = k[A]^2[B]\\), doubling the concentration of \\(A\\) while keeping \\(B\\) constant multiplies the rate by:", "\\(1\\)", "\\(2\\)", "\\(3\\)", "\\(4\\)", "\\(8\\)", "D", "The reaction is second-order in \\(A\\), so \\(2^2 = 4\\).", "Easy"),
    (3, "Chemistry", "Equilibrium", "For the exothermic reaction \\(\\text{N}_2 + 3\\text{H}_2 \\rightleftharpoons 2\\text{NH}_3 + \\text{heat}\\), increasing pressure shifts equilibrium:", "To the left (reactants)", "To the right (products)", "No shift occurs", "Stops the reaction", "Decreases ammonia yield", "B", "By Le Chatelier's principle, higher pressure favors the side with fewer gas moles (4 moles vs 2 moles).", "Medium"),
    (3, "Chemistry", "Atomic Structure", "What is the ground-state electron configuration of a neutral Sodium atom (\\(Z = 11\\))?", "\\(1s^2 2s^2 2p^6 3s^1\\)", "\\(1s^2 2s^2 2p^5 3s^2\\)", "\\(1s^2 2s^2 2p^6 3p^1\\)", "\\(1s^2 2s^2 2p^6\\)", "\\(1s^2 2s^2 2p^6 3s^2\\)", "A", "11 electrons fill \\(1s(2)\\), \\(2s(2)\\), \\(2p(6)\\), leaving 1 valence electron in \\(3s^1\\).", "Easy"),
    (3, "Chemistry", "Bonding", "What is the molecular geometry of Methane (\\(\\text{CH}_4\\)) according to VSEPR theory?", "Linear", "Trigonal planar", "Bent", "Trigonal pyramidal", "Tetrahedral", "E", "Four bonding pairs and zero lone pairs around carbon result in a tetrahedral geometry (\\(109.5^\\circ\\)).", "Easy"),
]

# ---------------------------------------------------------------------------
# WRITING PROMPTS  (task_type, title, prompt_text, chart_svg_or_table)
# ---------------------------------------------------------------------------
WRITING_PROMPTS_DATA = [
    (
        "Task 1",
        "Task 1: Household Internet Adoption (2000–2020)",
        "The table below shows the percentage of households with high-speed internet access across three European countries between 2000 and 2020. Summarise the information by selecting and reporting the main features, and make comparisons where relevant. Write at least 150 words.",
        """<table class="subject-table" style="margin-top:8px;">
            <thead><tr><th>Country</th><th>2000</th><th>2005</th><th>2010</th><th>2015</th><th>2020</th></tr></thead>
            <tbody>
              <tr><td><strong>Italy</strong></td><td>19%</td><td>34%</td><td>59%</td><td>75%</td><td>91%</td></tr>
              <tr><td><strong>Germany</strong></td><td>28%</td><td>49%</td><td>76%</td><td>88%</td><td>96%</td></tr>
              <tr><td><strong>Hungary</strong></td><td>12%</td><td>27%</td><td>54%</td><td>73%</td><td>89%</td></tr>
            </tbody>
           </table>"""
    ),
    (
        "Task 1",
        "Task 1: University Engineering Enrollment by Field",
        "The bar chart data below illustrates the number of undergraduate applicants to four engineering tracks at a technical university in 2015 and 2025. Summarise the information by selecting and reporting the main features, and make comparisons where relevant. Write at least 150 words.",
        """<table class="subject-table" style="margin-top:8px;">
            <thead><tr><th>Engineering Track</th><th>2015 Applicants</th><th>2025 Applicants</th><th>% Change</th></tr></thead>
            <tbody>
              <tr><td><strong>Computer & AI Engineering</strong></td><td>1,450</td><td>3,820</td><td style="color:#34d399">+163%</td></tr>
              <tr><td><strong>Mechanical Engineering</strong></td><td>2,100</td><td>2,250</td><td style="color:#38bdf8">+7%</td></tr>
              <tr><td><strong>Electrical Engineering</strong></td><td>1,800</td><td>2,490</td><td style="color:#34d399">+38%</td></tr>
              <tr><td><strong>Chemical Engineering</strong></td><td>1,150</td><td>980</td><td style="color:#f87171">-15%</td></tr>
            </tbody>
           </table>"""
    ),
    (
        "Task 1",
        "Task 1: Electricity Generation Sources (%)",
        "The table below compares the share of electricity produced from four different energy sources in a European country in 2005 and 2025. Summarise the information by selecting and reporting the main features. Write at least 150 words.",
        """<table class="subject-table" style="margin-top:8px;">
            <thead><tr><th>Energy Source</th><th>2005 Share</th><th>2025 Share</th></tr></thead>
            <tbody>
              <tr><td><strong>Solar & Wind</strong></td><td>8%</td><td>44%</td></tr>
              <tr><td><strong>Natural Gas</strong></td><td>42%</td><td>31%</td></tr>
              <tr><td><strong>Hydroelectric</strong></td><td>20%</td><td>19%</td></tr>
              <tr><td><strong>Coal</strong></td><td>30%</td><td>6%</td></tr>
            </tbody>
           </table>"""
    ),
    (
        "Task 2",
        "Task 2: AI & Automation in Software Engineering",
        "Some people believe that artificial intelligence and automated coding tools will replace human software engineers, while others argue that they will merely increase human productivity and create higher-level engineering roles. Discuss both views and give your own opinion. Write at least 250 words.",
        ""
    ),
    (
        "Task 2",
        "Task 2: Tuition-Free University Education",
        "Many countries offer merit-based scholarships and free higher education to international students in STEM fields. Do the economic and scientific benefits of this policy outweigh the financial costs to taxpayers? Give reasons for your answer and include relevant examples. Write at least 250 words.",
        ""
    ),
    (
        "Task 2",
        "Task 2: Online Simulations vs. Traditional Laboratories",
        "With the rise of virtual simulators and digital learning platforms, some educators argue that physical university lectures and traditional labs are no longer necessary. To what extent do you agree or disagree? Write at least 250 words.",
        ""
    ),
]

# ---------------------------------------------------------------------------
# ATTEMPT SEEDS  — user_id=1 ONLY
# (mode_label, correct_qids, wrong_qids, blank_qids, duration_secs)
# ---------------------------------------------------------------------------
ATTEMPT_SEEDS = [
    ("Mock 1", [1, 2, 3, 6, 7, 11, 12, 16, 17, 18], [4, 8, 13, 19], [5, 9, 10, 14, 15, 20], 940),
    ("Mock 2", [21, 22, 23, 24, 26, 27, 28, 31, 32, 34, 36, 37, 40], [25, 29, 33], [30, 35, 38, 39], 1120),
]

# ---------------------------------------------------------------------------
# READING PASSAGES  (title, topic, passage_html, questions_json)
# Each question in questions_json has keys: question, options (5 items), correct ('A'..'E'), explanation
# ---------------------------------------------------------------------------
READING_PASSAGES_DATA = [
    (
        "The Rise of Renewable Energy in Europe",
        "Academic",
        "<h3>The Rise of Renewable Energy in Europe</h3>"
        "<p><strong>A.</strong> Over the past two decades, Europe has undergone a remarkable transformation in its energy landscape. "
        "Countries such as Germany, Denmark, and Spain have invested heavily in wind and solar infrastructure, driven by both "
        "environmental concerns and the desire for energy independence. By 2023, renewables accounted for nearly 40% of the "
        "EU's electricity generation, a figure that would have seemed implausible at the turn of the millennium.</p>"
        "<p><strong>B.</strong> The transition has not been without its challenges. The intermittent nature of solar and wind power "
        "requires substantial investment in energy storage and grid modernization. Furthermore, the phase-out of nuclear power "
        "in certain nations has created short-term reliance on natural gas, complicating the path to full decarbonization. "
        "Policymakers continue to debate the optimal mix of baseload and renewable capacity.</p>"
        "<p><strong>C.</strong> Despite these obstacles, the economic case for renewables has strengthened considerably. "
        "The levelized cost of solar electricity fell by more than 85% between 2010 and 2023, making it the cheapest source "
        "of new electricity generation in history according to the International Energy Agency. This cost revolution is "
        "attracting private capital at an unprecedented scale, accelerating the transition beyond what government mandates alone could achieve.</p>",
        json.dumps([
            {"question": "According to paragraph A, what share of EU electricity came from renewables by 2023?", "options": ["20%", "30%", "40%", "50%", "60%"], "correct": "C", "explanation": "The passage states that by 2023, renewables accounted for nearly 40% of the EU's electricity generation."},
            {"question": "Which word in paragraph B is closest in meaning to 'irregular or inconsistent'?", "options": ["substantial", "intermittent", "optimal", "baseload", "modernization"], "correct": "B", "explanation": "Intermittent means occurring at irregular intervals or not continuously."},
            {"question": "What does paragraph C suggest happened to the cost of solar electricity between 2010 and 2023?", "options": ["It doubled", "It stayed the same", "It fell by over 85%", "It was subsidized by governments", "It became more expensive"], "correct": "C", "explanation": "The passage explicitly states that the levelized cost of solar electricity fell by more than 85% between 2010 and 2023."},
            {"question": "The phrase 'levelized cost' in paragraph C most likely refers to:", "options": ["The tax applied to energy production", "The average lifetime cost per unit of electricity", "The cost of leveling ground for solar panels", "A government pricing standard", "The initial installation cost"], "correct": "B", "explanation": "Levelized cost refers to the average cost per unit of electricity generated over the lifetime of a power plant."},
            {"question": "What is the main purpose of this passage?", "options": ["To argue against nuclear power", "To describe challenges in European politics", "To explain Europe's renewable energy transition", "To promote a specific energy company", "To discuss energy policy legislation"], "correct": "C", "explanation": "The passage discusses Europe's transition to renewable energy, including the progress, challenges, and economic factors involved."},
        ])
    ),
    (
        "Cognitive Load Theory and Digital Learning",
        "Academic",
        "<h3>Cognitive Load Theory and Digital Learning</h3>"
        "<p><strong>A.</strong> Cognitive Load Theory (CLT), first proposed by John Sweller in the 1980s, posits that human "
        "working memory has a limited capacity. When instructional design forces learners to process too much information "
        "simultaneously — a state called cognitive overload — learning efficiency drops sharply. CLT distinguishes three "
        "types of load: intrinsic (related to the complexity of the material), extraneous (caused by poor instructional "
        "design), and germane (cognitive effort devoted to schema formation).</p>"
        "<p><strong>B.</strong> Digital learning environments present both opportunities and pitfalls from a CLT perspective. "
        "Multimedia presentations that combine text, audio, and animation can reduce extraneous load by leveraging the "
        "dual-channel processing model — the idea that auditory and visual channels operate independently, effectively "
        "doubling working memory capacity. However, poorly designed interfaces, excessive notifications, and irrelevant "
        "graphics can rapidly erode these gains by imposing unnecessary cognitive demands.</p>"
        "<p><strong>C.</strong> Recent empirical studies suggest that adaptive learning systems — platforms that adjust "
        "content difficulty in real time based on learner performance — are particularly effective at managing intrinsic load. "
        "By scaffolding new concepts onto existing knowledge schemas, these systems keep learners operating in the optimal "
        "challenge zone described by Vygotsky's Zone of Proximal Development. Researchers at Stanford and ETH Zurich have "
        "reported 30–40% improvements in retention rates among students using such adaptive platforms compared to static curricula.</p>",
        json.dumps([
            {"question": "According to paragraph A, what happens when a learner experiences cognitive overload?", "options": ["They retain more information", "Learning efficiency drops sharply", "Working memory expands", "Schema formation accelerates", "No change occurs"], "correct": "B", "explanation": "The passage states that when learners experience cognitive overload, learning efficiency drops sharply."},
            {"question": "Which of the three types of cognitive load is associated with the complexity of the subject matter itself?", "options": ["Extraneous", "Germane", "Intrinsic", "Adaptive", "Excessive"], "correct": "C", "explanation": "Intrinsic load is described as being related to the complexity of the material itself."},
            {"question": "The 'dual-channel processing model' mentioned in paragraph B implies that:", "options": ["Students learn better with one sense at a time", "Auditory and visual channels process information independently", "Digital screens reduce memory capacity", "Animations always improve learning outcomes", "Visual learning is superior to auditory learning"], "correct": "B", "explanation": "The passage explains that the dual-channel processing model refers to auditory and visual channels operating independently, effectively doubling working memory capacity."},
            {"question": "What does the word 'scaffolding' most likely mean in paragraph C?", "options": ["Building physical structures for support", "Providing structured support to build on existing knowledge", "Reducing the number of topics covered", "Testing learners frequently", "Creating step-by-step guides"], "correct": "B", "explanation": "In this context, scaffolding refers to providing structured support to help learners build on their existing knowledge."},
            {"question": "What evidence is provided in paragraph C to support the effectiveness of adaptive learning systems?", "options": ["Anecdotal reports from students", "A 30-40% improvement in retention rates from Stanford and ETH Zurich studies", "Government funding data", "Comparisons with traditional textbooks", "User satisfaction surveys"], "correct": "B", "explanation": "The passage states that researchers at Stanford and ETH Zurich reported 30–40% improvements in retention rates among students using adaptive platforms."},
        ])
    ),
]

# ---------------------------------------------------------------------------
# FLASHCARDS  (subject, topic, front_text, back_text)
# ---------------------------------------------------------------------------
FLASHCARDS_DATA = [
    # Mathematics
    ("Mathematics", "Core", "What is the Fundamental Theorem of Calculus?", "\\(\\int_a^b f(x)\\,dx = F(b) - F(a)\\), where \\(F\\) is an antiderivative of \\(f\\)."),
    ("Mathematics", "Core", "State the Quadratic Formula.", "For \\(ax^2+bx+c=0\\): \\(x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}\\)."),
    ("Mathematics", "Core", "What is Euler's Identity?", "\\(e^{i\\pi} + 1 = 0\\)"),
    ("Mathematics", "Core", "Define a derivative using limits.", "\\(f'(x) = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h}\\)"),
    # Logic
    ("Logic", "Core", "What is Modus Ponens?", "If \\(P \\to Q\\) and \\(P\\) is true, then \\(Q\\) is true."),
    ("Logic", "Core", "What is Modus Tollens?", "If \\(P \\to Q\\) and \\(Q\\) is false, then \\(P\\) is false."),
    ("Logic", "Core", "State De Morgan's Laws.", "\\(\\neg(P \\wedge Q) \\equiv \\neg P \\vee \\neg Q\\) and \\(\\neg(P \\vee Q) \\equiv \\neg P \\wedge \\neg Q\\)"),
    ("Logic", "Core", "What is a tautology?", "A proposition that is true under every possible truth assignment."),
    # Physics
    ("Physics", "Core", "State Newton's Second Law.", "\\(\\vec{F} = m\\vec{a}\\): The net force on an object equals its mass times acceleration."),
    ("Physics", "Core", "What is the formula for kinetic energy?", "\\(KE = \\frac{1}{2}mv^2\\), where \\(m\\) is mass and \\(v\\) is speed."),
    ("Physics", "Core", "State Ohm's Law.", "\\(V = IR\\): Voltage equals current times resistance."),
    ("Physics", "Core", "What is Snell's Law of refraction?", "\\(n_1 \\sin \\theta_1 = n_2 \\sin \\theta_2\\)"),
    # Chemistry
    ("Chemistry", "Core", "What is the mole concept?", "One mole contains \\(6.022 \\times 10^{23}\\) particles (Avogadro's number)."),
    ("Chemistry", "Core", "What is the pH of a neutral solution at 25°C?", "pH = 7 (where \\([H^+] = 10^{-7}\\) mol/L)"),
    ("Chemistry", "Core", "What is the general formula of alkanes?", "\\(C_n H_{2n+2}\\)"),
    ("Chemistry", "Core", "What is a coordinate covalent bond?", "A bond where both shared electrons come from one atom (donor-acceptor bond)."),
    # IELTS Vocabulary
    ("IELTS Vocabulary", "Core", "What does 'inevitable' mean?", "Certain to happen, unavoidable (synonyms: inescapable, predetermined)."),
    ("IELTS Vocabulary", "Core", "What does 'mitigate' mean?", "To make less severe or intense (synonyms: alleviate, reduce, lessen)."),
    ("IELTS Vocabulary", "Core", "What does 'predominantly' mean?", "Mainly, for the most part (synonyms: chiefly, primarily, largely)."),
    ("IELTS Vocabulary", "Core", "What does 'subsequently' mean?", "Afterwards, following in time or order (synonyms: later, then, thereafter)."),
]

# ---------------------------------------------------------------------------
# BOOKMARKS  (user_id, question_id, is_auto_mistake, note)
# ---------------------------------------------------------------------------
BOOKMARKS_DATA = [
    (1, 4, 1, "Got this wrong on first attempt"),
    (1, 8, 0, ""),
]

# ---------------------------------------------------------------------------
# TEACHER → STUDENT links
# ---------------------------------------------------------------------------
TEACHER_STUDENT_SEEDS = [
    (2, 1),  # teacher_id=2, student_id=1
]

# ---------------------------------------------------------------------------
# ASSIGNMENTS
# (teacher_id, student_id, title, description, assignment_type,
#  question_ids_json, writing_prompt_id, reading_passage_id,
#  time_limit_mins, due_date)
# ---------------------------------------------------------------------------
ASSIGNMENT_SEEDS = [
    (
        2, 1,
        "Calculus & Mechanics Diagnostic",
        "Complete these 5 core questions before Friday.",
        "exam",
        json.dumps([1, 2, 11, 12, 16]),
        None, None,
        20, "2026-10-25"
    ),
]


# ---------------------------------------------------------------------------
# init()
# ---------------------------------------------------------------------------
def init(db_path=DB_PATH):
    """Create all tables and seed v3.0+v4.0 unified data."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")

    for stmt in SCHEMA.replace("user_id     INTEGER NOT NULL REFERENCES users(id),\n    subject     TEXT NOT NULL,\n    topic       TEXT DEFAULT 'Core'", "user_id     INTEGER DEFAULT 1 REFERENCES users(id),\n    subject     TEXT NOT NULL,\n    topic       TEXT DEFAULT 'Core'").split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)

    cur.execute("PRAGMA foreign_keys = ON")

    # ── Seed users ────────────────────────────────────────────────────────────
    cur.executemany(
        """INSERT INTO users
           (email, name, password_hash, role, invite_code, auth_provider,
            google_sub, avatar_url, target_uni, target_score, target_ielts, ai_api_key)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        USERS_DATA,
    )

    # ── Seed questions (all 12 fields) ────────────────────────────────────────
    questions_rows = list(QUESTIONS_DATA)
    cur.executemany(
        """INSERT INTO questions
           (mock_set, subject, topic, question_text, option_a, option_b, option_c, option_d, option_e, correct_option, explanation, difficulty)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        questions_rows,
    )

    # ── Seed writing prompts ──────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO writing_prompts (task_type, title, prompt_text, chart_svg_or_table) VALUES (?,?,?,?)",
        WRITING_PROMPTS_DATA,
    )

    # ── Seed reading passages ─────────────────────────────────────────────────
    cur.executemany(
        "INSERT INTO reading_passages (title, topic, passage_html, questions_json) VALUES (?,?,?,?)",
        READING_PASSAGES_DATA,
    )

    # ── Seed flashcards (assign user_id=1) ────────────────────────────────────
    flashcard_rows = [(1, subject, topic, front, back) for subject, topic, front, back in FLASHCARDS_DATA]
    cur.executemany(
        "INSERT INTO flashcards (user_id, subject, topic, front_text, back_text) VALUES (?,?,?,?,?)",
        flashcard_rows,
    )

    # ── Seed bookmarks for user_id=1 ──────────────────────────────────────────
    cur.executemany(
        "INSERT INTO bookmarks (user_id, question_id, is_auto_mistake, note) VALUES (?,?,?,?)",
        BOOKMARKS_DATA,
    )

    # ── Seed teacher → student links ──────────────────────────────────────────
    cur.executemany(
        "INSERT INTO teacher_students (teacher_id, student_id) VALUES (?,?)",
        TEACHER_STUDENT_SEEDS,
    )

    # ── Seed assignments ──────────────────────────────────────────────────────
    cur.executemany(
        """INSERT INTO assignments
           (teacher_id, student_id, title, description, assignment_type,
            question_ids_json, writing_prompt_id, reading_passage_id,
            time_limit_mins, due_date)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ASSIGNMENT_SEEDS,
    )

    # ── Seed exam attempts for user_id=1 ONLY (with exact CISIA -0.25 math) ───
    for mode_label, correct_ids, wrong_ids, blank_ids, duration in ATTEMPT_SEEDS:
        total_q = len(correct_ids) + len(wrong_ids) + len(blank_ids)
        score = round(1.0 * len(correct_ids) - 0.25 * len(wrong_ids), 2)

        cur.execute(
            """INSERT INTO exam_attempts
               (user_id, exam_mode, total_score, max_possible_score, correct_count, wrong_count, blank_count, duration_seconds)
               VALUES (?,?,?,?,?,?,?,?)""",
            (1, mode_label, score, float(total_q), len(correct_ids), len(wrong_ids), len(blank_ids), duration),
        )
        aid = cur.lastrowid

        for qid in correct_ids:
            q = questions_rows[qid - 1]
            cur.execute(
                "INSERT INTO attempt_answers (attempt_id, question_id, selected_option, points_awarded, subject) VALUES (?,?,?,?,?)",
                (aid, qid, q[9], 1.0, q[1]),
            )
        for qid in wrong_ids:
            q = questions_rows[qid - 1]
            wrong_opt = "B" if q[9] != "B" else "A"
            cur.execute(
                "INSERT INTO attempt_answers (attempt_id, question_id, selected_option, points_awarded, subject) VALUES (?,?,?,?,?)",
                (aid, qid, wrong_opt, -0.25, q[1]),
            )
        for qid in blank_ids:
            q = questions_rows[qid - 1]
            cur.execute(
                "INSERT INTO attempt_answers (attempt_id, question_id, selected_option, points_awarded, subject) VALUES (?,?,?,?,?)",
                (aid, qid, None, 0.0, q[1]),
            )

    # ── Seed 1 writing submission for user_id=1 ──────────────────────────────
    sample_essay = (
        "The provided table illustrates the proportion of households with high-speed internet access "
        "in Italy, Germany, and Hungary between 2000 and 2020. Overall, internet adoption surged dramatically."
    )
    cur.execute(
        """INSERT INTO writing_submissions
           (user_id, prompt_id, task_type, prompt_text, essay_text, word_count, paragraph_count,
            lexical_diversity, avg_sentence_length, transition_words_used, estimated_band, feedback_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            1, 1, "Task 1", WRITING_PROMPTS_DATA[0][2], sample_essay,
            155, 4, 0.64, 20.1, "overall | notably", 7.5,
            json.dumps({"feedback": ["Strong academic overview."]}),
        ),
    )

    con.commit()
    con.close()
    print(f"[init_db v4.0] Database initialised successfully at: {db_path}")



def ensure_initialized(db_path=DB_PATH):
    """Initialize database ONLY if it does not exist or has no users (preserves production data)."""
    if os.path.exists(db_path):
        try:
            con = sqlite3.connect(db_path)
            cnt = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            con.close()
            if cnt >= 2:
                return
        except Exception:
            pass
    init(db_path)


if __name__ == "__main__":
    init()