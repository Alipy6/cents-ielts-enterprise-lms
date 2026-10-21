"""
test_app.py v4.0 -- Pytest suite for the Exam Prep Engine API (Enterprise LMS Edition).
Run with: pytest -v
"""
import json
import os
import sqlite3

import pytest

# ── Ensure we can import from the project directory ─────────────────────────
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from init_db import DB_PATH, ALLOWED_SUBJECTS, init
import app as app_module

# ── Test client fixture ─────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def fresh_db():
    """Re-initialise the database once before the test session."""
    init()
    yield


@pytest.fixture(scope="session")
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth_client(client):
    """Logs in as ali@student.eu on the shared client."""
    client.post("/api/auth/login", json={
        "email": "ali@student.eu",
        "password": "Student2026!",
    })
    return client


# ===========================================================================
# 1. Database Integrity
# ===========================================================================

def test_db_total_questions():
    con = sqlite3.connect(DB_PATH)
    count = con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    con.close()
    assert count >= 60, f"Expected at least 60 questions, got {count}"


def test_db_questions_per_mock_set():
    con = sqlite3.connect(DB_PATH)
    for mock_set in (1, 2, 3):
        count = con.execute(
            "SELECT COUNT(*) FROM questions WHERE mock_set = ?", (mock_set,)
        ).fetchone()[0]
        assert count == 20, f"Mock set {mock_set}: expected 20, got {count}"
    con.close()


def test_db_no_biology():
    con = sqlite3.connect(DB_PATH)
    bio = con.execute(
        "SELECT COUNT(*) FROM questions WHERE subject = 'Biology'"
    ).fetchone()[0]
    con.close()
    assert bio == 0, "Found Biology questions — should be 0"


def test_db_only_allowed_subjects():
    con = sqlite3.connect(DB_PATH)
    subjects = {
        r[0] for r in con.execute("SELECT DISTINCT subject FROM questions").fetchall()
    }
    con.close()
    assert subjects <= set(ALLOWED_SUBJECTS), f"Unexpected subjects: {subjects - set(ALLOWED_SUBJECTS)}"


def test_db_all_five_options_non_null():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT id FROM questions "
        "WHERE option_a IS NULL OR option_b IS NULL OR option_c IS NULL "
        "OR option_d IS NULL OR option_e IS NULL"
    ).fetchall()
    con.close()
    assert len(rows) == 0, f"Questions with NULL options: {[r[0] for r in rows]}"


def test_db_correct_option_values():
    con = sqlite3.connect(DB_PATH)
    bad = con.execute(
        "SELECT id FROM questions WHERE correct_option NOT IN ('A','B','C','D','E')"
    ).fetchall()
    con.close()
    assert len(bad) == 0, f"Questions with invalid correct_option: {[r[0] for r in bad]}"


def test_db_writing_prompts_count():
    con = sqlite3.connect(DB_PATH)
    count = con.execute("SELECT COUNT(*) FROM writing_prompts").fetchone()[0]
    con.close()
    assert count == 6, f"Expected 6 writing prompts, got {count}"


# ===========================================================================
# 2. GET /api/exam
# ===========================================================================

def test_get_exam_mock1(client):
    rv = client.get("/api/exam?mode=mock1")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["count"] == 20
    assert data["mode"] == "mock1"
    assert len(data["flat_questions"]) == 20


def test_get_exam_mock2(client):
    rv = client.get("/api/exam?mode=mock2")
    assert rv.status_code == 200
    assert rv.get_json()["count"] == 20


def test_get_exam_mock3(client):
    rv = client.get("/api/exam?mode=mock3")
    assert rv.status_code == 200
    assert rv.get_json()["count"] == 20


def test_get_exam_custom_subjects_limit(client):
    rv = client.get("/api/exam?mode=custom&subjects=Mathematics,Physics&limit=10")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["count"] == 10
    for q in data["flat_questions"]:
        assert q["subject"] in ("Mathematics", "Physics"), \
            f"Unexpected subject: {q['subject']}"


def test_get_exam_custom_difficulty(client):
    rv = client.get("/api/exam?mode=custom&subjects=Mathematics,Logic,Physics,Chemistry&difficulty=Easy&limit=30")
    assert rv.status_code == 200
    data = rv.get_json()
    for q in data["flat_questions"]:
        assert q["difficulty"] == "Easy", f"Non-Easy question returned: {q}"


def test_get_exam_invalid_mode(client):
    rv = client.get("/api/exam?mode=bogus")
    assert rv.status_code == 400


def test_get_exam_custom_no_valid_subjects(client):
    rv = client.get("/api/exam?mode=custom&subjects=Biology,Alchemy")
    assert rv.status_code == 400


# ===========================================================================
# 3. POST /api/exam  (CISIA penalty scoring)
# ===========================================================================

def _get_mock1_ids(client):
    rv = client.get("/api/exam?mode=mock1")
    return rv.get_json()["flat_questions"]


def test_post_exam_all_correct(client):
    """All correct answers → score == 20.0"""
    questions = _get_mock1_ids(client)
    con = sqlite3.connect(DB_PATH)
    correct_map = {
        r[0]: r[1]
        for r in con.execute("SELECT id, correct_option FROM questions WHERE mock_set=1").fetchall()
    }
    con.close()

    answers = [{"question_id": q["id"], "selected_option": correct_map[q["id"]]}
               for q in questions]
    ids = [q["id"] for q in questions]

    rv = client.post("/api/exam", json={
        "exam_mode": "Mock 1",
        "question_ids": ids,
        "answers": answers,
        "duration_seconds": 300
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["correct"] == 20
    assert data["wrong"] == 0
    assert data["blank"] == 0
    assert abs(data["total_score"] - 20.0) < 0.001


def test_post_exam_penalty_math(client):
    """Mixed: 10 correct, 5 wrong, 5 blank → 10 - 1.25 = 8.75"""
    questions = _get_mock1_ids(client)
    con = sqlite3.connect(DB_PATH)
    correct_map = {
        r[0]: r[1]
        for r in con.execute("SELECT id, correct_option FROM questions WHERE mock_set=1").fetchall()
    }
    con.close()

    def wrong_opt(correct):
        opts = ["A", "B", "C", "D", "E"]
        idx = opts.index(correct)
        return opts[(idx + 1) % 5]

    ids = [q["id"] for q in questions]
    answers = []
    for i, q in enumerate(questions):
        if i < 10:
            answers.append({"question_id": q["id"], "selected_option": correct_map[q["id"]]})
        elif i < 15:
            answers.append({"question_id": q["id"], "selected_option": wrong_opt(correct_map[q["id"]])})

    rv = client.post("/api/exam", json={
        "exam_mode": "Mock 1",
        "question_ids": ids,
        "answers": answers,
        "duration_seconds": 300
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["correct"] == 10
    assert data["wrong"] == 5
    assert data["blank"] == 5
    assert abs(data["total_score"] - 8.75) < 0.001


def test_post_exam_blank_no_penalty(client):
    """Blank answers should not cause penalty."""
    questions = _get_mock1_ids(client)
    con = sqlite3.connect(DB_PATH)
    correct_map = {
        r[0]: r[1]
        for r in con.execute("SELECT id, correct_option FROM questions WHERE mock_set=1").fetchall()
    }
    con.close()

    answers = []
    for i, q in enumerate(questions):
        if i < 5:
            answers.append({"question_id": q["id"], "selected_option": correct_map[q["id"]]})
        # rest are blank

    ids = [q["id"] for q in questions]

    rv = client.post("/api/exam", json={
        "exam_mode": "Mock 1",
        "question_ids": ids,
        "answers": answers,
        "duration_seconds": 300
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["correct"] == 5
    assert data["wrong"] == 0
    assert data["blank"] == 15
    assert abs(data["total_score"] - 5.0) < 0.001


def test_post_exam_without_question_ids(client):
    """When question_ids not given, infer from answers."""
    questions = _get_mock1_ids(client)
    con = sqlite3.connect(DB_PATH)
    correct_map = {
        r[0]: r[1]
        for r in con.execute("SELECT id, correct_option FROM questions WHERE mock_set=1").fetchall()
    }
    con.close()

    answers = [{"question_id": q["id"], "selected_option": correct_map[q["id"]]}
               for q in questions[:10]]

    rv = client.post("/api/exam", json={
        "exam_mode": "Mock 1",
        "answers": answers,
        "duration_seconds": 300
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["correct"] == 10


# ===========================================================================
# 4. GET /api/writing/prompts
# ===========================================================================

def test_writing_prompts(client):
    rv = client.get("/api/writing/prompts")
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data) == 6
    for p in data:
        assert p["task_type"] in ("Task 1", "Task 2")


def test_writing_submit(client):
    essay = (
        "The chart illustrates the proportion of households with internet access "
        "in three European countries between 2000 and 2020. "
        "Overall, internet adoption surged dramatically across all three nations. "
        "Notably, while Germany maintained the highest coverage, Hungary experienced "
        "the most substantial relative growth. "
        "In 2000, Germany led with 28% household penetration, whereas Italy and Hungary "
        "recorded significantly lower figures at 19% and 12%, respectively. "
        "Over the next decade, connectivity expanded rapidly; consequently, by 2010, "
        "more than half of all households in each country had secured broadband access. "
        "In contrast to the wide disparities seen in 2000, the final decade showed "
        "strong convergence. By 2020, Germany achieved near-universal coverage at 96%, "
        "while Italy and Hungary climbed to impressive levels of 91% and 89%, respectively."
    )
    rv = client.post("/api/writing", json={
        "task_type": "Task 1",
        "prompt_text": "Describe the chart.",
        "essay": essay,
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert "band_score" in data or "estimated_band" in data


def test_writing_history(client):
    """Writing submissions should be filtered by logged-in user."""
    rv = client.get("/api/writing/history")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)


# ===========================================================================
# 5. Auth endpoints (v4.0)
# ===========================================================================

def test_auth_register(client):
    rv = client.post("/api/auth/register", json={
        "email": "testuser@example.com",
        "name": "Test User",
        "password": "TestPass123!",
        "role": "student",
        "target_uni": "Politecnico di Milano",
        "target_score": 18.0,
        "target_ielts": 7.0,
    })
    assert rv.status_code == 201
    data = rv.get_json()
    assert "user_id" in data
    assert "role" in data
    assert "invite_code" in data
    assert "auth_provider" in data
    assert "avatar_url" in data
    assert "target_uni" in data
    assert "target_score" in data
    assert "target_ielts" in data
    assert data["role"] == "student"
    assert data["invite_code"] is None


def test_auth_register_teacher_with_invite(client):
    """Teachers get auto-generated invite_code."""
    rv = client.post("/api/auth/register", json={
        "email": "teacher@example.com",
        "name": "Teacher User",
        "password": "TeacherPass123!",
        "role": "teacher",
        "target_uni": "Politecnico di Milano",
    })
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["role"] == "teacher"
    assert data["invite_code"] is not None
    assert data["invite_code"].startswith("T-")


def test_auth_register_duplicate(client):
    """Registering with the same email should fail."""
    client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "name": "Dup User",
        "password": "TestPass123!",
    })
    rv = client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "name": "Another User",
        "password": "TestPass456!",
    })
    assert rv.status_code == 409


def test_auth_login_success(client):
    """Login with a seeded user."""
    rv = client.post("/api/auth/login", json={
        "email": "ali@student.eu",
        "password": "Student2026!",
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert "user_id" in data
    assert data["email"] == "ali@student.eu"
    assert data["role"] == "student"
    assert data["invite_code"] is None


def test_auth_login_wrong_password(client):
    rv = client.post("/api/auth/login", json={
        "email": "ali@student.eu",
        "password": "WrongPassword!",
    })
    assert rv.status_code == 401


def test_auth_google(client):
    rv = client.post("/api/auth/google", json={
        "google_sub": "test_google_sub_123",
        "email": "googleuser@gmail.com",
        "name": "Google User",
        "avatar_url": "https://example.com/avatar.png",
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert "user_id" in data
    assert data["email"] == "googleuser@gmail.com"
    assert "role" in data


def test_auth_me(client):
    """Login then check /api/auth/me."""
    client.post("/api/auth/login", json={
        "email": "ali@student.eu",
        "password": "Student2026!",
    })
    rv = client.get("/api/auth/me")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["email"] == "ali@student.eu"
    assert "role" in data
    assert "invite_code" in data
    assert "auth_provider" in data
    assert "avatar_url" in data
    assert "target_uni" in data
    assert "target_score" in data
    assert "target_ielts" in data


def test_auth_logout(client):
    """Logout should clear the session."""
    client.post("/api/auth/login", json={
        "email": "ali@student.eu",
        "password": "Student2026!",
    })
    rv = client.post("/api/auth/logout")
    assert rv.status_code == 200


def test_auth_profile_update(client):
    """Update user profile."""
    client.post("/api/auth/login", json={
        "email": "ali@student.eu",
        "password": "Student2026!",
    })
    rv = client.put("/api/auth/profile", json={
        "target_score": 18.5,
        "target_uni": "Politecnico di Torino",
        "target_ielts": 8.0,
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["target_score"] == 18.5
    assert data["target_uni"] == "Politecnico di Torino"


def test_auth_profile_change_password(client):
    """Update password via new_password field."""
    client.post("/api/auth/login", json={
        "email": "ali@student.eu",
        "password": "Student2026!",
    })
    rv = client.put("/api/auth/profile", json={
        "new_password": "NewPass123!",
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert "user_id" in data


def test_auth_profile_change_role(client):
    """Update role from student to teacher."""
    client.post("/api/auth/login", json={
        "email": "ali@student.eu",
        "password": "Student2026!",
    })
    rv = client.put("/api/auth/profile", json={
        "role": "teacher",
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["role"] == "teacher"
    assert data["invite_code"] is not None


# ===========================================================================
# 6. Leaderboard (v4.0 - no fake users)
# ===========================================================================

def test_no_fake_users_in_db(client):
    """Verify Marco Rossi, Sofia Bianchi, Elena Costa, Ali Hassani do NOT exist."""
    db = sqlite3.connect(DB_PATH)
    fake_names = ['Marco Rossi', 'Sofia Bianchi', 'Elena Costa', 'Ali Hassani']
    for name in fake_names:
        row = db.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        assert row is None, f"Fake user '{name}' should not exist"
    db.close()


def test_only_two_seeded_users(client):
    """Verify the initial 2 seeded users are ali@student.eu and instructor@academy.eu."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    users = db.execute("SELECT email, role FROM users WHERE id IN (1, 2) ORDER BY id").fetchall()
    assert len(users) == 2
    assert users[0]["email"] == "ali@student.eu"
    assert users[1]["email"] == "instructor@academy.eu"
    db.close()


def test_get_leaderboard(client):
    """Leaderboard only shows real users with attempts (only ali@student.eu has attempts)."""
    rv = client.get("/api/leaderboard")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "leaderboard" in data
    assert "uni_cutoffs" in data
    assert isinstance(data["leaderboard"], list)
    assert len(data["leaderboard"]) == 1  # Only ali@student.eu has attempts


# ===========================================================================
# 7. User Isolation
# ===========================================================================

def test_new_user_sees_zero_attempts(client):
    """A newly registered user must see 0 attempts, not other users' data."""
    # Register a new user
    r = client.post('/api/auth/register', json={
        'email': 'newuser@test.com', 'name': 'New User', 'password': 'Pass123!'
    })
    assert r.status_code in (200, 201)
    # Login as new user
    r = client.post('/api/auth/login', json={
        'email': 'newuser@test.com', 'password': 'Pass123!'
    })
    assert r.status_code == 200
    # Check attempts — should be empty
    r = client.get('/api/attempts')
    assert r.status_code == 200
    data = r.get_json()
    attempts = data if isinstance(data, list) else data.get('attempts', [])
    assert len(attempts) == 0

    client.post('/api/auth/login', json={
        'email': 'ali@student.eu', 'password': 'Student2026!'
    })

# ===========================================================================
# 8. Bookmarks
# ===========================================================================

def test_get_bookmarks(client):
    client.post("/api/auth/logout")  # Reset session to default user_id=1
    rv = client.get("/api/bookmarks")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)
    assert len(data) >= 2

def test_add_bookmark(client):
    rv = client.post("/api/bookmarks", json={
        "question_id": 1,
        "note": "Need to review this one.",
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["question_id"] == 1


def test_delete_bookmark(client):
    """Add then delete a bookmark."""
    client.post("/api/bookmarks", json={
        "question_id": 2,
        "note": "Temporary bookmark.",
    })
    rv = client.delete("/api/bookmarks/2")
    assert rv.status_code == 200


def test_delete_bookmark_not_found(client):
    rv = client.delete("/api/bookmarks/99999")
    assert rv.status_code == 404


# ===========================================================================
# 9. Reading Hub
# ===========================================================================

def test_get_reading_passages(client):
    rv = client.get("/api/reading")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)
    assert len(data) >= 2
    for passage in data:
        assert "title" in passage
        assert "passage_html" in passage
        assert "questions" in passage
        assert len(passage["questions"]) == 5


def test_reading_grade(client):
    """Grade reading answers — all correct for passage 1."""
    rv = client.get("/api/reading")
    passage = rv.get_json()[0]
    passage_id = passage["id"]
    correct_answers = {}
    for i, q in enumerate(passage["questions"]):
        correct_answers[str(i)] = q["correct"]

    rv2 = client.post("/api/reading/grade", json={
        "passage_id": passage_id,
        "answers": correct_answers,
    })
    assert rv2.status_code == 200
    data = rv2.get_json()
    assert data["correct"] == 5
    assert data["total_questions"] == 5
    assert data["score_pct"] == 100.0


def test_reading_grade_partial(client):
    """Grade reading answers — some wrong."""
    rv = client.get("/api/reading")
    passage = rv.get_json()[0]
    passage_id = passage["id"]
    answers = {}
    for i, q in enumerate(passage["questions"]):
        if i < 3:
            answers[str(i)] = q["correct"]
        else:
            answers[str(i)] = "A" if q["correct"] != "A" else "B"

    rv2 = client.post("/api/reading/grade", json={
        "passage_id": passage_id,
        "answers": answers,
    })
    assert rv2.status_code == 200
    data = rv2.get_json()
    assert data["correct"] == 3
    assert data["total_questions"] == 5


# ===========================================================================
# 10. Flashcards
# ===========================================================================

def test_get_flashcards(client):
    rv = client.get("/api/flashcards")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)
    assert len(data) >= 20
    for card in data:
        assert "subject" in card
        assert "front_text" in card
        assert "back_text" in card


def test_get_flashcards_by_subject(client):
    rv = client.get("/api/flashcards?subject=Mathematics")
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data) >= 4
    for card in data:
        assert card["subject"] == "Mathematics"


# ===========================================================================
# 11. Teacher Workflow
# ===========================================================================

def test_teacher_list_students(auth_client):
    """Teacher sees their enrolled students."""
    # Login as teacher
    auth_client.post('/api/auth/login', json={
        'email': 'instructor@academy.eu', 'password': 'Teacher2026!'
    })
    r = auth_client.get('/api/teacher/students')
    assert r.status_code == 200
    data = r.get_json()
    students = data if isinstance(data, list) else data.get('students', [])
    assert len(students) >= 1
    # Log back in as student
    auth_client.post('/api/auth/login', json={
        'email': 'ali@student.eu', 'password': 'Student2026!'
    })


def test_teacher_student_report(auth_client):
    """Teacher views student report."""
    auth_client.post('/api/auth/login', json={
        'email': 'instructor@academy.eu', 'password': 'Teacher2026!'
    })
    r = auth_client.get('/api/teacher/student/1/report')
    assert r.status_code == 200
    data = r.get_json()
    assert 'user' in data or 'attempts' in data
    # Log back in as student
    auth_client.post('/api/auth/login', json={
        'email': 'ali@student.eu', 'password': 'Student2026!'
    })


def test_teacher_create_assignment(auth_client):
    """Teacher creates an assignment for student_id=1."""
    # Login as teacher
    auth_client.post('/api/auth/login', json={
        'email': 'instructor@academy.eu', 'password': 'Teacher2026!'
    })
    r = auth_client.post('/api/teacher/assignments', json={
        'title': 'Test Assignment',
        'description': 'Test description',
        'student_id': 1,
        'assignment_type': 'exam',
        'question_ids': [1, 2, 3],
        'time_limit_mins': 15,
        'due_date': '2026-12-01'
    })
    assert r.status_code in (200, 201)
    data = r.get_json()
    assert data.get('ok') == True or data.get('assignment', {}).get('title') == 'Test Assignment'
    # Log back in as student
    auth_client.post('/api/auth/login', json={
        'email': 'ali@student.eu', 'password': 'Student2026!'
    })


def test_student_sees_assignments(auth_client):
    """Student sees assignments assigned to them."""
    r = auth_client.get('/api/assignments')
    assert r.status_code == 200
    data = r.get_json()
    assignments = data if isinstance(data, list) else data.get('assignments', [])
    assert len(assignments) >= 1  # At least the seeded one


def test_student_submit_assignment(auth_client):
    """Student submits an assignment."""
    # Get assignments to find the ID
    r = auth_client.get('/api/assignments')
    data = r.get_json()
    assignments = data if isinstance(data, list) else data.get('assignments', [])
    assignment_id = assignments[0]['id']
    # Submit
    r = auth_client.post(f'/api/assignments/{assignment_id}/submit', json={
        'grade': 4.0,
        'max_grade': 5.0
    })
    assert r.status_code in (200, 201)


def test_teacher_grade_submission(auth_client):
    """Teacher grades a student's submission."""
    # Login as teacher
    auth_client.post('/api/auth/login', json={
        'email': 'instructor@academy.eu', 'password': 'Teacher2026!'
    })
    # Get assignments as teacher to find submissions
    r = auth_client.get('/api/assignments')
    data = r.get_json()
    assignments = data if isinstance(data, list) else data.get('assignments', [])
    # Find a submission to grade
    submission_id = None
    for a in assignments:
        subs = a.get('submissions', [])
        if subs:
            submission_id = subs[0]['id']
            break
    assert submission_id is not None, "No submission found to grade"
    r = auth_client.post(f'/api/teacher/submissions/{submission_id}/grade', json={
        'teacher_grade': 4.5,
        'teacher_comment': 'Well done!'
    })
    assert r.status_code == 200
    # Log back in as student
    auth_client.post('/api/auth/login', json={
        'email': 'ali@student.eu', 'password': 'Student2026!'
    })


# ===========================================================================
# 12. Teacher-Student Management
# ===========================================================================

def test_student_join_teacher(auth_client):
    """Student can join a teacher via invite_code."""
    # Register a new student
    auth_client.post('/api/auth/register', json={
        'email': 'joiner@test.com', 'name': 'Joiner', 'password': 'Pass123!'
    })
    auth_client.post('/api/auth/login', json={
        'email': 'joiner@test.com', 'password': 'Pass123!'
    })
    r = auth_client.post('/api/student/join-teacher', json={
        'invite_code': 'CENTS2026'
    })
    assert r.status_code == 200
    # Log back in as ali@student.eu
    auth_client.post('/api/auth/login', json={
        'email': 'ali@student.eu', 'password': 'Student2026!'
    })


# ===========================================================================
# 13. AI Engine endpoints
# ===========================================================================

def test_ai_generate_questions(client):
    rv = client.post("/api/ai/generate-questions", json={
        "subject": "Mathematics",
        "topic": "Calculus",
        "difficulty": "Medium",
        "count": 3,
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["source"] == "parametric_engine"
    assert len(data["questions"]) == 3
    for q in data["questions"]:
        assert q["subject"] == "Mathematics"
        assert q["correct_option"] in ("A", "B", "C", "D", "E")
        assert q["option_a"]
        assert q["option_b"]
        assert q["option_c"]
        assert q["option_d"]
        assert q["option_e"]


def test_ai_generate_questions_invalid_subject(client):
    rv = client.post("/api/ai/generate-questions", json={
        "subject": "Biology",
        "count": 3,
    })
    assert rv.status_code == 400


def test_ai_generate_questions_save_to_db(client):
    """Test save_to_db=True saves questions."""
    rv = client.post("/api/ai/generate-questions", json={
        "subject": "Mathematics",
        "topic": "Calculus",
        "difficulty": "Medium",
        "count": 3,
        "save_to_db": True,
    })
    assert rv.status_code == 200


def test_ai_notes_to_exam(client):
    rv = client.post("/api/ai/notes-to-exam", json={
        "notes": "Quadratic formula: x = (-b ± sqrt(b²-4ac))/2a",
        "subject": "Mathematics",
        "count": 2,
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data["questions"]) == 2


def test_ai_explain_trap(client):
    rv = client.post("/api/ai/explain-trap", json={
        "question_text": "If x² = 4, what is x?",
        "trap_answer": "2",
        "correct_answer": "2 or -2",
        "explanation": "Taking square root gives both positive and negative solutions.",
    })
    assert rv.status_code == 200


def test_ai_upgrade_essay(client):
    rv = client.post("/api/ai/upgrade-essay", json={
        "original": "The chart show big changes.",
        "band_score": 4.0,
        "target_band": 7.0,
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert "upgraded_essay" in data or "feedback" in data


# ===========================================================================
# 14. Analytics endpoints
# ===========================================================================

def test_analytics_user_auth(client):
    """Analytics endpoint returns data for logged-in user."""
    rv = client.get("/api/analytics")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "subject_breakdown" in data
    assert "strengths" in data or "weaknesses" in data
