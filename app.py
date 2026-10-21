import os
"""
app.py v4.0 -- Flask API for Academic Prep, Analytics, Auth, Bookmarks,
Reading Hub, Flashcards, Leaderboard, AI Engine, and LMS (Teacher/Student).
"""
import json
import random
import secrets
import sqlite3
from functools import wraps

from flask import Flask, abort, jsonify, request, send_from_directory, session

from analyzer import analyze_essay
from ai_engine import (
    generate_questions as ai_generate_questions,
    notes_to_exam as ai_notes_to_exam,
    explain_trap as ai_explain_trap,
    upgrade_essay_paragraph as ai_upgrade_essay,
)
from init_db import ALLOWED_SUBJECTS, DB_PATH, init, ensure_initialized

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "dev-exam-prep-secret-v6")
ensure_initialized()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _row(r):
    return dict(r)


def _uid() -> int:
    return int(session.get("user_id", 1))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            session["user_id"] = 1
        return f(*args, **kwargs)
    return decorated


def _user_dict(u):
    return {
        "id":            u["id"],
        "user_id":       u["id"],
        "email":         u["email"],
        "name":          u["name"],
        "role":          u["role"],
        "invite_code":   u["invite_code"],
        "auth_provider": u["auth_provider"],
        "avatar_url":    u["avatar_url"] or "",
        "target_uni":    u["target_uni"] or "Politecnico di Milano",
        "target_score":  u["target_score"] if u["target_score"] is not None else 16.0,
        "target_ielts":  u["target_ielts"] if u["target_ielts"] is not None else 7.0,
    }


def _require_role(role):
    con = _db()
    u = con.execute("SELECT role FROM users WHERE id=?", (_uid(),)).fetchone()
    con.close()
    if not u or u["role"] != role:
        abort(403, description=f"Requires {role} role")


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------------------------------------------------------
# Exam endpoints
# ---------------------------------------------------------------------------

@app.route("/api/exam", methods=["GET"])
def get_exam():
    mode = request.args.get("mode", "mock1").lower()
    subjects = request.args.get("subjects")
    difficulty = request.args.get("difficulty")
    bookmarked_only = request.args.get("bookmarked_only", "").lower() in ("1", "true")
    limit = request.args.get("limit", 20, type=int)

    con = _db()
    base_query = (
        "SELECT q.id, q.mock_set, q.subject, q.topic, q.question_text, "
        "q.option_a, q.option_b, q.option_c, q.option_d, q.option_e, "
        "q.correct_option, q.explanation, q.difficulty FROM questions q"
    )
    params = []

    if mode in ("mock1", "mock2", "mock3"):
        mock_num = {"mock1": 1, "mock2": 2, "mock3": 3}[mode]
        base_query += " WHERE q.mock_set = ? ORDER BY q.subject, q.id"
        params.append(mock_num)
        rows = con.execute(base_query, params).fetchall()
        con.close()
        flat = [_row(r) for r in rows]
        grouped = {}
        for q in flat:
            grouped.setdefault(q["subject"], []).append(q)
        return jsonify({
            "mode": mode,
            "subjects": list(grouped.keys()),
            "questions": grouped,
            "flat_questions": flat,
            "count": len(flat),
        })

    elif mode == "marathon":
        base_query += " WHERE q.mock_set IN (1, 2, 3) ORDER BY q.mock_set, q.subject, q.id LIMIT 40"
        rows = con.execute(base_query).fetchall()
        con.close()
        flat = [_row(r) for r in rows]
        grouped = {}
        for q in flat:
            grouped.setdefault(q["subject"], []).append(q)
        return jsonify({
            "mode": mode,
            "subjects": list(grouped.keys()),
            "questions": grouped,
            "flat_questions": flat,
            "count": len(flat),
        })

    elif mode == "custom":
        conditions = []
        if bookmarked_only:
            base_query += " JOIN bookmarks b ON q.id = b.question_id AND b.user_id = ?"
            params.append(_uid())
        if subjects:
            subj_list = [s.strip() for s in subjects.split(",") if s.strip() in ALLOWED_SUBJECTS]
            if not subj_list:
                con.close()
                return jsonify({"error": "No valid subjects provided"}), 400
            placeholders = ",".join("?" * len(subj_list))
            conditions.append(f"q.subject IN ({placeholders})")
            params.extend(subj_list)
        if difficulty and difficulty != "All":
            conditions.append("UPPER(q.difficulty) = UPPER(?)")
            params.append(difficulty)
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
    else:
        con.close()
        return jsonify({"error": f"Invalid mode '{mode}'"}), 400

    rows = con.execute(base_query, params).fetchall()
    con.close()

    if not rows:
        return jsonify({"error": "No questions match the filter"}), 404

    shuffled = list(rows)
    random.shuffle(shuffled)
    if limit and limit < len(shuffled):
        shuffled = shuffled[:limit]

    flat = [_row(r) for r in shuffled]
    grouped = {}
    for q in flat:
        grouped.setdefault(q["subject"], []).append(q)

    return jsonify({
        "mode": mode,
        "subjects": list(grouped.keys()),
        "questions": grouped,
        "count": len(flat),
        "flat_questions": flat,
    })


@app.route("/api/exam", methods=["POST"])
def submit_exam():
    data = request.get_json(force=True) or {}
    question_ids = data.get("question_ids", [])
    answers = data.get("answers", {})
    exam_mode = data.get("exam_mode", "Custom")
    duration_seconds = int(data.get("duration_seconds", 0))

    if isinstance(answers, list):
        answer_map = {}
        for a in answers:
            if "question_id" in a:
                qid = int(a["question_id"])
                opt = a.get("selected_option")
                answer_map[qid] = opt if opt else None
    else:
        answer_map = {int(k): (v if v else None) for k, v in answers.items()}

    grading_ids = [int(q) for q in question_ids] if question_ids else list(answer_map.keys())
    if not grading_ids:
        return jsonify({"error": "question_ids required"}), 400

    con = _db()
    placeholders = ",".join("?" * len(grading_ids))
    q_rows = con.execute(
        f"SELECT id, subject, correct_option, explanation FROM questions WHERE id IN ({placeholders})",
        grading_ids,
    ).fetchall()
    correct_map = {r["id"]: (r["correct_option"], r["subject"], r["explanation"]) for r in q_rows}

    total_score = 0.0
    correct_count = wrong_count = blank_count = 0
    subject_stats = {}
    answer_records = []
    wrong_question_ids = []

    for qid in grading_ids:
        if qid not in correct_map:
            continue
        correct_opt, subject, explanation = correct_map[qid]
        selected = answer_map.get(qid)

        if subject not in subject_stats:
            subject_stats[subject] = {"correct": 0, "wrong": 0, "blank": 0, "score": 0.0}

        if selected is None:
            points = 0.0
            blank_count += 1
            subject_stats[subject]["blank"] += 1
        elif str(selected).upper() == correct_opt:
            points = 1.0
            correct_count += 1
            subject_stats[subject]["correct"] += 1
        else:
            points = -0.25
            wrong_count += 1
            subject_stats[subject]["wrong"] += 1
            wrong_question_ids.append(qid)

        total_score += points
        subject_stats[subject]["score"] = round(subject_stats[subject]["score"] + points, 4)
        answer_records.append((qid, selected, round(points, 4), subject))

    max_possible_score = float(len(grading_ids))
    total_score = round(total_score, 4)
    what_if_no_wrong_score = float(correct_count * 1.0)

    uid = _uid()
    cur = con.execute(
        "INSERT INTO exam_attempts "
        "(user_id, exam_mode, total_score, max_possible_score, correct_count, wrong_count, blank_count, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (uid, exam_mode, total_score, max_possible_score,
         correct_count, wrong_count, blank_count, duration_seconds),
    )
    attempt_id = cur.lastrowid

    con.executemany(
        "INSERT INTO attempt_answers (attempt_id, question_id, selected_option, points_awarded, subject) "
        "VALUES (?, ?, ?, ?, ?)",
        [(attempt_id, rec[0], rec[1], rec[2], rec[3]) for rec in answer_records],
    )

    for qid in wrong_question_ids:
        try:
            con.execute(
                "INSERT INTO bookmarks (user_id, question_id, is_auto_mistake, note) "
                "VALUES (?, ?, 1, 'Auto-saved from wrong exam answer') "
                "ON CONFLICT(user_id, question_id) DO UPDATE SET is_auto_mistake = 1",
                (uid, qid),
            )
        except Exception:
            pass

    con.commit()
    con.close()

    feedback = []
    for qid, selected, points, subject in answer_records:
        c_opt, _, expl = correct_map[qid]
        feedback.append({
            "question_id": qid,
            "selected_option": selected,
            "correct_option": c_opt,
            "explanation": expl,
            "points_awarded": points,
            "subject": subject,
            "result": "correct" if points == 1.0 else ("blank" if points == 0.0 else "wrong"),
        })

    return jsonify({
        "attempt_id": attempt_id,
        "exam_mode": exam_mode,
        "total_score": total_score,
        "max_possible_score": max_possible_score,
        "correct": correct_count,
        "wrong": wrong_count,
        "blank": blank_count,
        "what_if_no_wrong_score": what_if_no_wrong_score,
        "subject_stats": subject_stats,
        "feedback": feedback,
    })


# ---------------------------------------------------------------------------
# Attempts & Analytics
# ---------------------------------------------------------------------------

@app.route("/api/attempts")
def list_attempts():
    con = _db()
    rows = con.execute(
        "SELECT id, user_id, exam_mode, total_score, max_possible_score, "
        "correct_count, wrong_count, blank_count, duration_seconds, timestamp "
        "FROM exam_attempts WHERE user_id = ? ORDER BY id DESC",
        (_uid(),)
    ).fetchall()
    con.close()
    return jsonify([_row(r) for r in rows])


@app.route("/api/attempts/<int:attempt_id>")
def get_attempt(attempt_id):
    con = _db()
    att = con.execute(
        "SELECT * FROM exam_attempts WHERE id = ?", (attempt_id,)
    ).fetchone()
    if not att:
        con.close()
        return jsonify({"error": "Attempt not found"}), 404
    answers = con.execute(
        """SELECT aa.question_id, aa.selected_option, aa.points_awarded, aa.subject,
                  q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.option_e,
                  q.correct_option, q.explanation, q.difficulty, q.topic
           FROM attempt_answers aa
           JOIN questions q ON aa.question_id = q.id
           WHERE aa.attempt_id = ?
           ORDER BY aa.id""",
        (attempt_id,),
    ).fetchall()
    con.close()

    answer_list = []
    for a in answers:
        item = _row(a)
        item["result"] = (
            "correct" if item["points_awarded"] == 1.0
            else ("blank" if item["points_awarded"] == 0.0 else "wrong")
        )
        answer_list.append(item)

    att_dict = _row(att)
    att_dict["attempt"] = _row(att)
    att_dict["answers"] = answer_list
    return jsonify(att_dict)


@app.route("/api/analytics")
def analytics():
    con = _db()
    uid = _uid()
    subj_rows = con.execute(
        "SELECT aa.subject, aa.points_awarded, aa.question_id "
        "FROM attempt_answers aa "
        "JOIN exam_attempts ea ON ea.id = aa.attempt_id "
        "WHERE ea.user_id = ?",
        (uid,)
    ).fetchall()

    per_subject = {}
    for r in subj_rows:
        s = r["subject"]
        if not s:
            continue
        if s not in per_subject:
            per_subject[s] = {"correct": 0, "wrong": 0, "blank": 0, "score": 0.0, "accuracy": 0.0}
        pts = r["points_awarded"]
        if pts == 1.0:
            per_subject[s]["correct"] += 1
        elif pts < 0:
            per_subject[s]["wrong"] += 1
        else:
            per_subject[s]["blank"] += 1
        per_subject[s]["score"] = round(per_subject[s]["score"] + pts, 4)

    subject_breakdown = {}
    strengths = []
    weaknesses = []
    for s, stats in per_subject.items():
        tot = stats["correct"] + stats["wrong"] + stats["blank"]
        acc = round((stats["correct"] / tot) * 100, 1) if tot > 0 else 0.0
        stats["accuracy"] = acc
        subject_breakdown[s] = acc
        if acc >= 60.0:
            strengths.append(s)
        else:
            weaknesses.append(s)

    trend = con.execute(
        "SELECT id, exam_mode, total_score, max_possible_score, timestamp "
        "FROM exam_attempts WHERE user_id = ? ORDER BY id",
        (uid,)
    ).fetchall()
    con.close()

    trend_list = [_row(t) for t in trend]
    return jsonify({
        "per_subject": per_subject,
        "subjects": per_subject,
        "subject_breakdown": subject_breakdown,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "trend": trend_list,
        "overall_trend": trend_list,
    })


# ---------------------------------------------------------------------------
# Writing endpoints
# ---------------------------------------------------------------------------

@app.route("/api/writing/prompts")
def writing_prompts():
    con = _db()
    rows = con.execute(
        "SELECT id, task_type, title, prompt_text, chart_svg_or_table FROM writing_prompts ORDER BY id"
    ).fetchall()
    con.close()
    return jsonify([_row(r) for r in rows])


@app.route("/api/writing", methods=["POST"])
def submit_writing():
    data = request.get_json(force=True) or {}
    task_type = data.get("task_type", "Task 2")
    prompt_id = data.get("prompt_id")
    prompt_text = data.get("prompt_text", "")
    essay_text = data.get("essay_text") or data.get("essay") or ""

    if not essay_text.strip():
        return jsonify({"error": "essay_text required"}), 400

    result = analyze_essay(essay_text, task_type=task_type)
    result["band_score"] = result["estimated_band"]

    con = _db()
    cur_w = con.execute(
        """INSERT INTO writing_submissions
           (user_id, prompt_id, task_type, prompt_text, essay_text, word_count, paragraph_count,
            lexical_diversity, avg_sentence_length, transition_words_used,
            estimated_band, feedback_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _uid(),
            prompt_id,
            task_type,
            prompt_text,
            essay_text,
            result["word_count"],
            result["paragraph_count"],
            result["lexical_diversity"],
            result["avg_sentence_length"],
            " | ".join(result.get("transition_words_used", [])),
            result["estimated_band"],
            json.dumps(result),
        ),
    )
    result["writing_id"] = cur_w.lastrowid
    con.commit()
    con.close()

    return jsonify(result)


@app.route("/api/writing/history")
def writing_history():
    con = _db()
    rows = con.execute(
        "SELECT ws.*, wp.title as prompt_title FROM writing_submissions ws "
        "LEFT JOIN writing_prompts wp ON wp.id = ws.prompt_id "
        "WHERE ws.user_id = ? ORDER BY ws.timestamp DESC, ws.id DESC",
        (_uid(),)
    ).fetchall()
    con.close()
    return jsonify([_row(r) for r in rows])


# ---------------------------------------------------------------------------
# Auth endpoints (v4.0)
# ---------------------------------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    from werkzeug.security import generate_password_hash

    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""
    target_uni = (data.get("target_uni") or "Politecnico di Milano").strip()
    target_score = float(data.get("target_score", 16.0))
    target_ielts = float(data.get("target_ielts", 7.0))
    role = (data.get("role") or "student").strip().lower()

    if role not in ("student", "teacher"):
        return jsonify({"error": "role must be 'student' or 'teacher'"}), 400

    if not email or not name or not password:
        return jsonify({"error": "email, name, and password are required"}), 400

    invite_code = ("T-" + secrets.token_hex(3).upper()) if role == "teacher" else None

    con = _db()
    existing = con.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        con.close()
        return jsonify({"error": "Email already registered"}), 409

    pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
    cur = con.execute(
        "INSERT INTO users (email, name, password_hash, auth_provider, target_uni, target_score, target_ielts, role, invite_code) "
        "VALUES (?, ?, ?, 'local', ?, ?, ?, ?, ?)",
        (email, name, pw_hash, target_uni, target_score, target_ielts, role, invite_code),
    )
    con.commit()
    user_id = cur.lastrowid
    row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    con.close()

    session["user_id"] = user_id
    return jsonify(_user_dict(row)), 201


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    from werkzeug.security import check_password_hash

    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    con = _db()
    row = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    con.close()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = row["id"]
    return jsonify(_user_dict(row))


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    from werkzeug.security import generate_password_hash

    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "Google User").strip()
    avatar_url = data.get("avatar_url") or ""
    role = (data.get("role") or "student").strip().lower()

    if role not in ("student", "teacher"):
        role = "student"

    if not email:
        return jsonify({"error": "Google email is required"}), 400

    google_sub = data.get("google_sub") or f"google_{email}"

    con = _db()
    try:
        # 1. Check by email first (most reliable across seeded & OAuth users)
        existing = con.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
        if not existing:
            existing = con.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,)).fetchone()

        if existing:
            user_id = existing["id"]
            invite_code = existing["invite_code"]
            if role == "teacher" and not invite_code:
                invite_code = "T-" + secrets.token_hex(3).upper()

            con.execute(
                """UPDATE users
                   SET google_sub = ?, auth_provider = 'google', name = ?, role = ?, invite_code = ?, avatar_url = ?
                   WHERE id = ?""",
                (google_sub, name or existing["name"], role, invite_code, avatar_url, user_id),
            )
            con.commit()
        else:
            pw_hash = generate_password_hash(google_sub, method="pbkdf2:sha256")
            invite_code = ("T-" + secrets.token_hex(3).upper()) if role == "teacher" else None
            cur = con.execute(
                """INSERT INTO users (email, name, password_hash, auth_provider, google_sub, avatar_url, role, invite_code)
                   VALUES (?, ?, ?, 'google', ?, ?, ?, ?)""",
                (email, name, pw_hash, google_sub, avatar_url, role, invite_code),
            )
            con.commit()
            user_id = cur.lastrowid

        row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        user_payload = _user_dict(row)
    finally:
        con.close()

    session.permanent = True
    session["user_id"] = user_id
    return jsonify(user_payload), 200


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@app.route("/api/auth/me")
def auth_me():
    uid = _uid()
    con = _db()
    row = con.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    con.close()
    if not row:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_user_dict(row))


@app.route("/api/auth/profile", methods=["PUT"])
def auth_profile():
    uid = _uid()
    data = request.get_json(force=True) or {}

    allowed_fields = ["name", "email", "role", "target_uni", "target_score", "target_ielts", "ai_api_key", "avatar_url"]
    updates = {f: data[f] for f in allowed_fields if f in data}

    if data.get("new_password"):
        from werkzeug.security import generate_password_hash
        updates["password_hash"] = generate_password_hash(data["new_password"], method="pbkdf2:sha256")

    con = _db()
    if updates.get("role") == "teacher":
        cur_u = con.execute("SELECT invite_code FROM users WHERE id = ?", (uid,)).fetchone()
        if cur_u and not cur_u["invite_code"]:
            updates["invite_code"] = "T-" + secrets.token_hex(3).upper()

    if not updates:
        con.close()
        return jsonify({"error": "No updatable fields provided"}), 400

    set_clause = ", ".join([f"{f} = ?" for f in updates])
    values = list(updates.values()) + [uid]

    con.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    con.commit()
    row = con.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    con.close()
    return jsonify(_user_dict(row))


# ---------------------------------------------------------------------------
# LMS: Teacher & Student endpoints (v4.0)
# ---------------------------------------------------------------------------

@app.route("/api/teacher/students", methods=["GET"])
@login_required
def teacher_students_list():
    _require_role("teacher")
    con = _db()
    rows = con.execute(
        "SELECT u.id, u.name, u.email, u.avatar_url, u.target_uni, u.created_at "
        "FROM teacher_students ts JOIN users u ON u.id = ts.student_id "
        "WHERE ts.teacher_id = ?", (_uid(),)
    ).fetchall()
    result = []
    for s in rows:
        sid = s["id"]
        attempts_count = con.execute(
            "SELECT COUNT(*) as c FROM exam_attempts WHERE user_id=?", (sid,)
        ).fetchone()["c"]
        avg_row = con.execute(
            "SELECT AVG(total_score * 100.0 / max_possible_score) as avg FROM exam_attempts WHERE user_id=? AND max_possible_score > 0", (sid,)
        ).fetchone()
        avg_score = round(avg_row["avg"] or 0, 1)
        last_row = con.execute(
            "SELECT timestamp FROM exam_attempts WHERE user_id=? ORDER BY timestamp DESC LIMIT 1", (sid,)
        ).fetchone()
        last_active = last_row["timestamp"] if last_row else None
        subj_row = con.execute(
            "SELECT aa.subject, AVG(CASE WHEN aa.points_awarded > 0 THEN 1.0 ELSE 0.0 END)*100 as acc "
            "FROM attempt_answers aa "
            "JOIN exam_attempts ea ON ea.id = aa.attempt_id "
            "WHERE ea.user_id=? AND aa.subject != '' GROUP BY aa.subject ORDER BY acc ASC LIMIT 1", (sid,)
        ).fetchone()
        weakest_subject = subj_row["subject"] if subj_row else "Mathematics"
        writing_count = con.execute(
            "SELECT COUNT(*) as c FROM writing_submissions WHERE user_id=?", (sid,)
        ).fetchone()["c"]
        result.append({
            "id": sid,
            "name": s["name"],
            "email": s["email"],
            "target_uni": s["target_uni"] or "Politecnico di Milano",
            "avatar_url": s["avatar_url"] or "",
            "created_at": s["created_at"],
            "attempts_count": attempts_count,
            "avg_score": avg_score,
            "last_active": last_active,
            "weakest_subject": weakest_subject,
            "writing_count": writing_count,
        })
    con.close()
    return jsonify(result)


@app.route("/api/teacher/students", methods=["POST"])
@login_required
def teacher_add_student():
    _require_role("teacher")
    con = _db()
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        con.close()
        return jsonify({"error": "email required"}), 400
    student = con.execute("SELECT id, name, email FROM users WHERE email=? AND role='student'", (email,)).fetchone()
    if not student:
        con.close()
        return jsonify({"error": "Student not found"}), 404
    con.execute(
        "INSERT OR IGNORE INTO teacher_students (teacher_id, student_id) VALUES (?,?)",
        (_uid(), student["id"])
    )
    con.commit()
    con.close()
    return jsonify({"ok": True, "student_id": student["id"], "name": student["name"]})


@app.route("/api/teacher/students/<int:student_id>", methods=["DELETE"])
@login_required
def teacher_remove_student(student_id):
    _require_role("teacher")
    con = _db()
    con.execute(
        "DELETE FROM teacher_students WHERE teacher_id=? AND student_id=?",
        (_uid(), student_id)
    )
    con.commit()
    con.close()
    return jsonify({"ok": True})


@app.route("/api/teacher/student/<int:student_id>/report", methods=["GET"])
@login_required
def teacher_student_report(student_id):
    _require_role("teacher")
    con = _db()
    link = con.execute(
        "SELECT id FROM teacher_students WHERE teacher_id=? AND student_id=?",
        (_uid(), student_id)
    ).fetchone()
    if not link:
        con.close()
        return jsonify({"error": "Student not in your roster"}), 403
    user = con.execute(
        "SELECT id, name, email, target_uni, target_score, target_ielts, avatar_url, created_at FROM users WHERE id=?", (student_id,)
    ).fetchone()
    attempts = con.execute(
        "SELECT * FROM exam_attempts WHERE user_id=? ORDER BY timestamp DESC", (student_id,)
    ).fetchall()
    writings = con.execute(
        "SELECT ws.*, wp.title as prompt_title FROM writing_submissions ws "
        "LEFT JOIN writing_prompts wp ON wp.id=ws.prompt_id "
        "WHERE ws.user_id=? ORDER BY ws.timestamp DESC", (student_id,)
    ).fetchall()
    subject_rows = con.execute(
        "SELECT aa.subject, COUNT(*) as total, SUM(CASE WHEN aa.points_awarded > 0 THEN 1 ELSE 0 END) as correct "
        "FROM attempt_answers aa "
        "JOIN exam_attempts ea ON ea.id = aa.attempt_id "
        "WHERE ea.user_id=? AND aa.subject != '' GROUP BY aa.subject", (student_id,)
    ).fetchall()
    subject_accuracy = {r["subject"]: round((r["correct"] or 0) * 100.0 / r["total"], 1) for r in subject_rows if r["total"] > 0}
    bookmarks = con.execute(
        "SELECT q.*, b.note, b.is_auto_mistake FROM bookmarks b JOIN questions q ON q.id=b.question_id WHERE b.user_id=?", (student_id,)
    ).fetchall()
    con.close()
    return jsonify({
        "user": dict(user) if user else {},
        "attempts": [dict(a) for a in attempts],
        "writing_submissions": [dict(w) for w in writings],
        "subject_accuracy": subject_accuracy,
        "bookmarks": [dict(b) for b in bookmarks],
    })


@app.route("/api/student/join-teacher", methods=["POST"])
@login_required
def student_join_teacher():
    con = _db()
    data = request.get_json(force=True) or {}
    invite_code = (data.get("invite_code") or "").strip().upper()
    if not invite_code:
        con.close()
        return jsonify({"error": "invite_code required"}), 400
    teacher = con.execute(
        "SELECT id, name FROM users WHERE UPPER(invite_code)=? AND role='teacher'", (invite_code,)
    ).fetchone()
    if not teacher:
        con.close()
        return jsonify({"error": "Invalid invite code"}), 404
    con.execute(
        "INSERT OR IGNORE INTO teacher_students (teacher_id, student_id) VALUES (?,?)",
        (teacher["id"], _uid())
    )
    con.commit()
    con.close()
    return jsonify({"ok": True, "teacher_id": teacher["id"], "teacher_name": teacher["name"]})


@app.route("/api/teacher/assignments", methods=["POST"])
@login_required
def teacher_create_assignment():
    _require_role("teacher")
    con = _db()
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        con.close()
        return jsonify({"error": "title required"}), 400
    description        = data.get("description", "")
    student_id         = data.get("student_id") or None
    assignment_type    = data.get("assignment_type", "exam")
    question_ids       = data.get("question_ids", [])
    writing_prompt_id  = data.get("writing_prompt_id")
    reading_passage_id = data.get("reading_passage_id")
    time_limit_mins    = int(data.get("time_limit_mins", 40))
    due_date           = data.get("due_date", "")

    auto_count = data.get("auto_generate_count")
    if auto_count:
        subject    = data.get("subject", "Mathematics")
        difficulty = data.get("difficulty", "Medium")
        q_rows = con.execute(
            "SELECT id FROM questions WHERE subject=? AND UPPER(difficulty)=UPPER(?) ORDER BY RANDOM() LIMIT ?",
            (subject, difficulty, int(auto_count))
        ).fetchall()
        if not q_rows:
            q_rows = con.execute(
                "SELECT id FROM questions WHERE subject=? ORDER BY RANDOM() LIMIT ?",
                (subject, int(auto_count))
            ).fetchall()
        question_ids = [r["id"] for r in q_rows]

    strict_mode = 1 if data.get("strict_mode", True) else 0
    classroom_id = data.get("classroom_id") or None
    cur = con.execute(
        "INSERT INTO assignments (teacher_id, student_id, classroom_id, title, description, assignment_type, "
        "question_ids_json, writing_prompt_id, reading_passage_id, time_limit_mins, due_date, strict_mode) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (_uid(), student_id, classroom_id, title, description, assignment_type,
         json.dumps(question_ids), writing_prompt_id, reading_passage_id,
         time_limit_mins, due_date, strict_mode)
    )
    con.commit()
    aid = cur.lastrowid
    con.close()
    return jsonify({"ok": True, "assignment_id": aid}), 201


@app.route("/api/assignments", methods=["GET"])
@login_required
def list_assignments():
    con = _db()
    user = con.execute("SELECT role FROM users WHERE id=?", (_uid(),)).fetchone()
    if not user:
        con.close()
        return jsonify({"error": "Unauthorized"}), 401
    if user["role"] == "teacher":
        rows = con.execute(
            "SELECT a.*, u.name as target_student_name, "
            "(SELECT COUNT(*) FROM assignment_submissions sub WHERE sub.assignment_id=a.id) as submission_count "
            "FROM assignments a LEFT JOIN users u ON u.id = a.student_id "
            "WHERE a.teacher_id=? ORDER BY a.created_at DESC",
            (_uid(),)
        ).fetchall()
        result = []
        for a in rows:
            subs = con.execute(
                "SELECT asub.*, u.name as student_name, u.email as student_email "
                "FROM assignment_submissions asub JOIN users u ON u.id=asub.student_id "
                "WHERE asub.assignment_id=?", (a["id"],)
            ).fetchall()
            d = dict(a)
            d["question_ids"] = json.loads(d.get("question_ids_json") or "[]")
            d["submissions"] = [dict(s) for s in subs]
            result.append(d)
        con.close()
        return jsonify(result)
    else:
        teacher_rows = con.execute(
            "SELECT teacher_id FROM teacher_students WHERE student_id=?", (_uid(),)
        ).fetchall()
        teacher_ids = [r["teacher_id"] for r in teacher_rows]
        if teacher_ids:
            ph = ",".join("?" * len(teacher_ids))
            rows = con.execute(
                f"SELECT a.*, u.name as teacher_name FROM assignments a "
                f"JOIN users u ON u.id = a.teacher_id "
                f"WHERE (a.teacher_id IN ({ph}) AND (a.student_id=? OR a.student_id IS NULL)) "
                f"OR a.student_id=? "
                f"ORDER BY a.created_at DESC",
                (*teacher_ids, _uid(), _uid())
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT a.*, u.name as teacher_name FROM assignments a "
                "JOIN users u ON u.id = a.teacher_id "
                "WHERE a.student_id=? ORDER BY a.created_at DESC",
                (_uid(),)
            ).fetchall()
        result = []
        for a in rows:
            sub = con.execute(
                "SELECT * FROM assignment_submissions WHERE assignment_id=? AND student_id=?",
                (a["id"], _uid())
            ).fetchone()
            d = dict(a)
            d["question_ids"] = json.loads(d.get("question_ids_json") or "[]")
            if sub:
                d["status"]          = sub["status"]
                d["score"]           = sub["score"]
                d["max_score"]       = sub["max_score"]
                d["teacher_comment"] = sub["teacher_comment"]
                d["teacher_grade"]   = sub["teacher_grade"]
            else:
                d["status"]          = "pending"
                d["score"]           = None
                d["max_score"]       = None
                d["teacher_comment"] = ""
                d["teacher_grade"]   = None
            result.append(d)
        con.close()
        return jsonify(result)


@app.route("/api/assignments/<int:assignment_id>/submit", methods=["POST"])
@login_required
def submit_assignment(assignment_id):
    con = _db()
    data = request.get_json(force=True) or {}
    attempt_id = data.get("attempt_id")
    writing_id = data.get("writing_id")
    score      = data.get("score")
    max_score  = data.get("max_score")
    con.execute(
        "INSERT INTO assignment_submissions "
        "(assignment_id, student_id, attempt_id, writing_id, score, max_score, tab_switches, status) "
        "VALUES (?,?,?,?,?,?,?,'submitted') "
        "ON CONFLICT(assignment_id, student_id) DO UPDATE SET "
        "attempt_id=excluded.attempt_id, writing_id=excluded.writing_id, "
        "score=excluded.score, max_score=excluded.max_score, tab_switches=excluded.tab_switches, status='submitted', "
        "submitted_at=CURRENT_TIMESTAMP",
        (assignment_id, _uid(), attempt_id, writing_id, score, max_score, int(data.get("tab_switches", 0)))
    )
    con.commit()
    con.close()
    return jsonify({"ok": True})


@app.route("/api/teacher/submissions/<int:submission_id>/grade", methods=["POST"])
@login_required
def grade_submission(submission_id):
    _require_role("teacher")
    con = _db()
    data = request.get_json(force=True) or {}
    teacher_grade   = data.get("teacher_grade")
    teacher_comment = data.get("teacher_comment", "")
    rubric_json     = json.dumps(data.get("rubric") or {})
    con.execute(
        "UPDATE assignment_submissions SET teacher_grade=?, teacher_comment=?, rubric_json=?, status='graded' WHERE id=?",
        (teacher_grade, teacher_comment, rubric_json, submission_id)
    )
    con.commit()
    con.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Question Bank & Bookmarks
# ---------------------------------------------------------------------------

@app.route("/api/questions")
def question_bank():
    subject = request.args.get("subject")
    difficulty = request.args.get("difficulty")
    ids_param = request.args.get("ids")
    search = request.args.get("search")
    bookmarked_only = request.args.get("bookmarked_only", type=bool) or request.args.get("bookmarked_only") in ("true", "1")

    uid = _uid()
    con = _db()
    bm_ids = {
        r["question_id"]
        for r in con.execute("SELECT question_id FROM bookmarks WHERE user_id = ?", (uid,)).fetchall()
    }

    query = "SELECT q.* FROM questions q"
    params = []
    conditions = []

    if bookmarked_only:
        query += " JOIN bookmarks b ON q.id = b.question_id AND b.user_id = ?"
        params.append(uid)

    if ids_param:
        id_list = [int(x) for x in ids_param.split(",") if x.strip().isdigit()]
        if id_list:
            ph = ",".join("?" * len(id_list))
            conditions.append(f"q.id IN ({ph})")
            params.extend(id_list)
    if subject and subject != "All":
        conditions.append("q.subject = ?")
        params.append(subject)
    if difficulty and difficulty != "All":
        conditions.append("UPPER(q.difficulty) = UPPER(?)")
        params.append(difficulty)
    if search:
        conditions.append("(q.question_text LIKE ? OR q.topic LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    rows = con.execute(query + " ORDER BY q.id", params).fetchall()
    con.close()

    out = []
    for r in rows:
        d = _row(r)
        d["is_bookmarked"] = d["id"] in bm_ids
        out.append(d)
    return jsonify(out)


@app.route("/api/bookmarks")
def list_bookmarks():
    uid = _uid()
    con = _db()
    rows = con.execute(
        """SELECT b.id, b.user_id, b.question_id, b.is_auto_mistake, b.note, b.created_at,
                  q.subject, q.topic, q.question_text, q.correct_option, q.explanation, q.difficulty
           FROM bookmarks b
           JOIN questions q ON b.question_id = q.id
           WHERE b.user_id = ?
           ORDER BY b.created_at DESC""",
        (uid,),
    ).fetchall()
    con.close()
    return jsonify([_row(r) for r in rows])


@app.route("/api/bookmarks", methods=["POST"])
def add_bookmark():
    uid = _uid()
    data = request.get_json(force=True) or {}
    question_id = data.get("question_id")
    note = data.get("note", "")
    is_auto = data.get("is_auto_mistake", 0)

    if not question_id:
        return jsonify({"error": "question_id required"}), 400

    con = _db()
    try:
        con.execute(
            "INSERT INTO bookmarks (user_id, question_id, is_auto_mistake, note) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, question_id) DO UPDATE SET note = excluded.note",
            (uid, question_id, is_auto, note),
        )
        con.commit()
    except Exception as e:
        con.close()
        return jsonify({"error": str(e)}), 400
    con.close()
    return jsonify({"message": "Bookmark added", "question_id": question_id})


@app.route("/api/bookmarks/<int:qid>", methods=["DELETE"])
def delete_bookmark(qid):
    uid = _uid()
    con = _db()
    cur = con.execute(
        "DELETE FROM bookmarks WHERE user_id = ? AND question_id = ?",
        (uid, qid),
    )
    con.commit()
    con.close()
    if cur.rowcount == 0:
        return jsonify({"error": "Bookmark not found"}), 404
    return jsonify({"message": "Bookmark removed", "question_id": qid})


# ---------------------------------------------------------------------------
# Study Hub & Leaderboard
# ---------------------------------------------------------------------------

@app.route("/api/reading")
def reading_passages():
    con = _db()
    rows = con.execute(
        "SELECT id, title, topic, passage_html, questions_json FROM reading_passages ORDER BY id"
    ).fetchall()
    con.close()
    result = []
    for r in rows:
        item = _row(r)
        item["questions"] = json.loads(item["questions_json"])
        result.append(item)
    return jsonify(result)


@app.route("/api/reading/grade", methods=["POST"])
def reading_grade():
    data = request.get_json(force=True) or {}
    passage_id = data.get("passage_id")
    answers = data.get("answers", {})

    if not passage_id:
        return jsonify({"error": "passage_id required"}), 400

    con = _db()
    row = con.execute(
        "SELECT questions_json FROM reading_passages WHERE id = ?", (passage_id,)
    ).fetchone()
    con.close()

    if not row:
        return jsonify({"error": "Passage not found"}), 404

    questions = json.loads(row["questions_json"])
    correct_count = 0
    total = len(questions)
    detail = []

    for i, q in enumerate(questions):
        selected = answers.get(str(i)) or answers.get(i)
        correct_opt = q.get("correct") or q.get("answer")
        is_correct = selected is not None and str(selected).strip().upper() == str(correct_opt).strip().upper()
        if is_correct:
            correct_count += 1
        detail.append({
            "question_index": i,
            "selected": selected,
            "correct": correct_opt,
            "is_correct": is_correct,
            "explanation": q.get("explanation") or q.get("evidence_paragraph", ""),
        })

    pct = round(correct_count / total * 100, 1) if total else 0.0
    estimated_band = round((4.0 + (pct / 100.0) * 5.0) * 2) / 2.0

    return jsonify({
        "passage_id": passage_id,
        "total_questions": total,
        "correct": correct_count,
        "score_pct": pct,
        "estimated_band": estimated_band,
        "detail": detail,
    })


@app.route("/api/flashcards")
def flashcards():
    subject = request.args.get("subject")
    con = _db()
    if subject and subject != "All":
        rows = con.execute(
            "SELECT id, subject, topic, front_text, back_text FROM flashcards WHERE subject = ? ORDER BY id",
            (subject,),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id, subject, topic, front_text, back_text FROM flashcards ORDER BY id"
        ).fetchall()
    con.close()
    return jsonify([_row(r) for r in rows])


@app.route("/api/leaderboard")
def leaderboard():
    con = _db()
    rows = con.execute(
        """SELECT ea.id, ea.user_id, u.name, u.target_uni,
                  ea.exam_mode, MAX(ea.total_score) as total_score, ea.max_possible_score,
                  ea.correct_count, ea.wrong_count, ea.blank_count,
                  ea.duration_seconds, ea.timestamp
           FROM exam_attempts ea
           JOIN users u ON ea.user_id = u.id
           GROUP BY ea.user_id
           ORDER BY total_score DESC
           LIMIT 50"""
    ).fetchall()
    con.close()

    uni_cutoffs = {
        "Politecnico di Milano": 16.0,
        "Università di Padova": 15.0,
        "Università di Bologna": 15.5,
        "Politecnico di Torino": 15.0,
        "Università di Pavia": 14.0,
        "Università di Messina": 11.5,
    }

    return jsonify({
        "leaderboard": [_row(r) for r in rows],
        "uni_cutoffs": uni_cutoffs,
    })


# ---------------------------------------------------------------------------
# AI Engine endpoints (Supporting both v3.0 and v4.0 payloads)
# ---------------------------------------------------------------------------

@app.route("/api/ai/generate-questions", methods=["POST"])
def ai_gen_questions_route():
    data = request.get_json(force=True) or {}
    subject = data.get("subject", "Mathematics")
    topic = data.get("topic", "General")
    difficulty = data.get("difficulty", "Medium")
    count = int(data.get("count", 5))
    save_to_db = bool(data.get("save_to_db", False))

    api_key = data.get("api_key", "")
    if not api_key:
        con = _db()
        user_row = con.execute("SELECT ai_api_key FROM users WHERE id = ?", (_uid(),)).fetchone()
        con.close()
        if user_row and user_row["ai_api_key"]:
            api_key = user_row["ai_api_key"]

    try:
        result = ai_generate_questions(subject, topic, difficulty, count, api_key)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if save_to_db:
        con = _db()
        for q in result["questions"]:
            cur = con.execute(
                """INSERT INTO questions
                   (mock_set, subject, topic, question_text, option_a, option_b, option_c,
                    option_d, option_e, correct_option, explanation, difficulty)
                   VALUES (4, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    subject,
                    q.get("topic", topic),
                    q["question_text"],
                    q["option_a"], q["option_b"], q["option_c"],
                    q["option_d"], q["option_e"],
                    q["correct_option"],
                    q.get("explanation", ""),
                    q.get("difficulty", difficulty),
                ),
            )
            q["id"] = cur.lastrowid
        con.commit()
        con.close()

    return jsonify(result)


@app.route("/api/ai/notes-to-exam", methods=["POST"])
def ai_notes_to_exam_route():
    data = request.get_json(force=True) or {}
    notes_text = data.get("notes_text") or data.get("notes") or ""
    subject = data.get("subject", "Physics")
    count = int(data.get("count", 5))
    save_to_db = bool(data.get("save_to_db", True))

    if not notes_text.strip():
        return jsonify({"error": "notes_text required"}), 400

    api_key = data.get("api_key", "")
    if not api_key:
        con = _db()
        user_row = con.execute("SELECT ai_api_key FROM users WHERE id = ?", (_uid(),)).fetchone()
        con.close()
        if user_row and user_row["ai_api_key"]:
            api_key = user_row["ai_api_key"]

    try:
        result = ai_notes_to_exam(notes_text, subject, count, api_key)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if save_to_db and "questions" in result:
        con = _db()
        for q in result["questions"]:
            cur = con.execute(
                """INSERT INTO questions
                   (mock_set, subject, topic, question_text, option_a, option_b, option_c,
                    option_d, option_e, correct_option, explanation, difficulty)
                   VALUES (4, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    subject,
                    q.get("topic", "Study Notes"),
                    q["question_text"],
                    q["option_a"], q["option_b"], q["option_c"],
                    q["option_d"], q["option_e"],
                    q["correct_option"],
                    q.get("explanation", ""),
                    q.get("difficulty", "Medium"),
                ),
            )
            q["id"] = cur.lastrowid
        con.commit()
        con.close()

    return jsonify(result)


@app.route("/api/ai/explain-trap", methods=["POST"])
def ai_explain_trap_route():
    data = request.get_json(force=True) or {}
    question_id = data.get("question_id")
    selected_option = data.get("selected_option") or data.get("chosen_option") or data.get("trap_answer") or "B"

    if question_id:
        con = _db()
        row = con.execute(
            "SELECT id, subject, topic, question_text, option_a, option_b, option_c, option_d, option_e, correct_option, explanation, difficulty FROM questions WHERE id = ?",
            (question_id,),
        ).fetchone()
        con.close()
        if not row:
            return jsonify({"error": "Question not found"}), 404
        q_dict = _row(row)
    elif data.get("question_text"):
        q_dict = {
            "id": 0,
            "subject": data.get("subject", "Mathematics"),
            "question_text": data.get("question_text"),
            "option_a": data.get("trap_answer", ""),
            "option_b": data.get("correct_answer", ""),
            "correct_option": "B",
            "explanation": data.get("explanation", ""),
        }
    else:
        return jsonify({"error": "question_id or question_text required"}), 400

    api_key = data.get("api_key", "")
    result = ai_explain_trap(q_dict, str(selected_option), api_key)
    return jsonify(result)


@app.route("/api/ai/upgrade-essay", methods=["POST"])
def ai_upgrade_essay_route():
    data = request.get_json(force=True) or {}
    text = data.get("text") or data.get("essay_text") or data.get("original") or ""
    task_type = data.get("task_type", "Task 2")

    if not text.strip():
        return jsonify({"error": "text required"}), 400

    api_key = data.get("api_key", "")
    if not api_key:
        con = _db()
        user_row = con.execute("SELECT ai_api_key FROM users WHERE id = ?", (_uid(),)).fetchone()
        con.close()
        if user_row and user_row["ai_api_key"]:
            api_key = user_row["ai_api_key"]

    result = ai_upgrade_essay(text, task_type, api_key)
    result["upgraded_essay"] = result.get("upgraded_text", "")
    result["feedback"] = result.get("grammar_tips", [])
    return jsonify(result)




# ===========================================================================
# v5.0 ENTERPRISE INSTRUCTOR STUDIO, AUTHORING, GRADEBOOK & PROCTORING APIs
# ===========================================================================

def _ensure_v5_tables():
    con = _db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS classrooms (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name        TEXT NOT NULL,
        subject     TEXT DEFAULT 'All Subjects',
        invite_code TEXT UNIQUE NOT NULL,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS classroom_students (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
        student_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        joined_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(classroom_id, student_id)
    );
    CREATE TABLE IF NOT EXISTS announcements (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        classroom_id INTEGER REFERENCES classrooms(id) ON DELETE CASCADE,
        title        TEXT NOT NULL,
        content      TEXT NOT NULL,
        attachment_url TEXT DEFAULT '',
        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # Safely add v5 columns if missing
    for alter_sql in [
        "ALTER TABLE assignments ADD COLUMN strict_mode INTEGER DEFAULT 1",
        "ALTER TABLE assignments ADD COLUMN classroom_id INTEGER",
        "ALTER TABLE assignment_submissions ADD COLUMN tab_switches INTEGER DEFAULT 0",
        "ALTER TABLE assignment_submissions ADD COLUMN rubric_json TEXT DEFAULT '{}'",
    ]:
        try:
            con.execute(alter_sql)
        except Exception:
            pass

    # Seed default classroom & announcement if empty
    c_count = con.execute("SELECT COUNT(*) FROM classrooms").fetchone()[0]
    if c_count == 0:
        con.execute(
            "INSERT OR IGNORE INTO classrooms (id, teacher_id, name, subject, invite_code) VALUES (1, 2, 'CEnT-S Engineering Cohort 2027', 'All Subjects', 'CENTS2026')"
        )
        con.execute(
            "INSERT OR IGNORE INTO classroom_students (classroom_id, student_id) VALUES (1, 1)"
        )
        con.execute(
            "INSERT INTO announcements (teacher_id, classroom_id, title, content, attachment_url) VALUES (2, 1, 'Welcome to CEnT-S & IELTS Cohort 2027!', 'Please complete the Calculus & Mechanics Diagnostic quiz before Friday under strict CISIA penalty rules (-0.25 for wrong guesses). Review the attached formula sheet.', 'https://www.cisiaonline.it')"
        )
    con.commit()
    con.close()

_ensure_v5_tables()


# ── 1. Multi-Classroom & Announcements Endpoints ──────────────────────────

@app.route("/api/classrooms", methods=["GET", "POST"])
def api_classrooms():
    _ensure_v5_tables()
    con = _db()
    uid = _uid()
    user = con.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    role = user["role"] if user else "student"

    if request.method == "POST":
        if role != "teacher":
            con.close()
            return jsonify({"error": "Only instructors can create classrooms"}), 403
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        subject = (data.get("subject") or "All Subjects").strip()
        if not name:
            con.close()
            return jsonify({"error": "Classroom name is required"}), 400
        code = (data.get("invite_code") or ("CLS-" + secrets.token_hex(2).upper())).strip().upper()
        cur = con.execute(
            "INSERT INTO classrooms (teacher_id, name, subject, invite_code) VALUES (?,?,?,?)",
            (uid, name, subject, code)
        )
        con.commit()
        cid = cur.lastrowid
        con.close()
        return jsonify({"ok": True, "id": cid, "name": name, "subject": subject, "invite_code": code}), 201

    if role == "teacher":
        rows = con.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM classroom_students cs WHERE cs.classroom_id=c.id) as student_count "
            "FROM classrooms c WHERE c.teacher_id=? ORDER BY c.id DESC", (uid,)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT c.*, u.name as teacher_name FROM classrooms c "
            "JOIN classroom_students cs ON cs.classroom_id=c.id "
            "JOIN users u ON u.id=c.teacher_id "
            "WHERE cs.student_id=? ORDER BY c.id DESC", (uid,)
        ).fetchall()
    con.close()
    return jsonify([_row(r) for r in rows])


@app.route("/api/announcements", methods=["GET", "POST"])
def api_announcements():
    _ensure_v5_tables()
    con = _db()
    uid = _uid()
    user = con.execute("SELECT role, name FROM users WHERE id=?", (uid,)).fetchone()
    role = user["role"] if user else "student"

    if request.method == "POST":
        if role != "teacher":
            con.close()
            return jsonify({"error": "Only instructors can post announcements"}), 403
        data = request.get_json(force=True) or {}
        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        classroom_id = data.get("classroom_id") or None
        attachment_url = (data.get("attachment_url") or "").strip()
        if not title or not content:
            con.close()
            return jsonify({"error": "Title and content are required"}), 400
        cur = con.execute(
            "INSERT INTO announcements (teacher_id, classroom_id, title, content, attachment_url) VALUES (?,?,?,?,?)",
            (uid, classroom_id, title, content, attachment_url)
        )
        con.commit()
        aid = cur.lastrowid
        con.close()
        return jsonify({"ok": True, "id": aid}), 201

    if role == "teacher":
        rows = con.execute(
            "SELECT a.*, u.name as teacher_name, c.name as classroom_name "
            "FROM announcements a "
            "JOIN users u ON u.id=a.teacher_id "
            "LEFT JOIN classrooms c ON c.id=a.classroom_id "
            "WHERE a.teacher_id=? ORDER BY a.id DESC", (uid,)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT a.*, u.name as teacher_name, c.name as classroom_name "
            "FROM announcements a "
            "JOIN users u ON u.id=a.teacher_id "
            "LEFT JOIN classrooms c ON c.id=a.classroom_id "
            "WHERE a.teacher_id IN (SELECT teacher_id FROM teacher_students WHERE student_id=?) "
            "OR a.classroom_id IN (SELECT classroom_id FROM classroom_students WHERE student_id=?) "
            "ORDER BY a.id DESC", (uid, uid)
        ).fetchall()
    con.close()
    return jsonify([_row(r) for r in rows])


@app.route("/api/announcements/<int:aid>", methods=["DELETE"])
def api_delete_announcement(aid):
    con = _db()
    con.execute("DELETE FROM announcements WHERE id=? AND teacher_id=?", (aid, _uid()))
    con.commit()
    con.close()
    return jsonify({"ok": True})


# ── 2. Teacher Content Authoring Studio (Custom Questions, Writing, Reading) ──

@app.route("/api/teacher/author/question", methods=["POST"])
def teacher_author_question():
    data = request.get_json(force=True) or {}
    subject = data.get("subject", "Mathematics")
    if subject not in ALLOWED_SUBJECTS:
        return jsonify({"error": f"Subject must be one of {ALLOWED_SUBJECTS}"}), 400
    topic = (data.get("topic") or "Custom Instructor").strip()
    difficulty = data.get("difficulty", "Medium")
    if difficulty not in ("Easy", "Medium", "Hard"):
        difficulty = "Medium"
    q_text = (data.get("question_text") or "").strip()
    oa = (data.get("option_a") or "").strip()
    ob = (data.get("option_b") or "").strip()
    oc = (data.get("option_c") or "").strip()
    od = (data.get("option_d") or "").strip()
    oe = (data.get("option_e") or "").strip()
    correct_opt = (data.get("correct_option") or "A").strip().upper()
    explanation = (data.get("explanation") or "Instructor authored solution.").strip()

    if not q_text or not oa or not ob or not oc or not od or not oe:
        return jsonify({"error": "Question text and all 5 options (A-E) are required."}), 400

    con = _db()
    cur = con.execute(
        """INSERT INTO questions
           (mock_set, subject, topic, question_text, option_a, option_b, option_c, option_d, option_e, correct_option, explanation, difficulty)
           VALUES (4, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (subject, topic, q_text, oa, ob, oc, od, oe, correct_opt, explanation, difficulty)
    )
    con.commit()
    qid = cur.lastrowid
    con.close()
    return jsonify({"ok": True, "id": qid}), 201


@app.route("/api/teacher/author/question/<int:qid>", methods=["DELETE"])
def teacher_delete_question(qid):
    if qid <= 60:
        return jsonify({"error": "Core 60 official mock questions are protected; you can delete custom/AI questions (#61+)."}), 400
    con = _db()
    con.execute("DELETE FROM questions WHERE id=?", (qid,))
    con.commit()
    con.close()
    return jsonify({"ok": True})


@app.route("/api/teacher/author/writing-prompt", methods=["POST"])
def teacher_author_writing_prompt():
    data = request.get_json(force=True) or {}
    task_type = data.get("task_type", "Task 2")
    title = (data.get("title") or "").strip()
    prompt_text = (data.get("prompt_text") or "").strip()
    chart_html = (data.get("chart_svg_or_table") or "").strip()
    if not title or not prompt_text:
        return jsonify({"error": "Title and prompt text are required"}), 400
    con = _db()
    cur = con.execute(
        "INSERT INTO writing_prompts (task_type, title, prompt_text, chart_svg_or_table) VALUES (?,?,?,?)",
        (task_type, title, prompt_text, chart_html)
    )
    con.commit()
    pid = cur.lastrowid
    con.close()
    return jsonify({"ok": True, "id": pid}), 201


@app.route("/api/teacher/author/reading-passage", methods=["POST"])
def teacher_author_reading_passage():
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    topic = (data.get("topic") or "Academic").strip()
    passage_html = (data.get("passage_html") or "").strip()
    questions = data.get("questions") or []
    if not title or not passage_html or not questions:
        return jsonify({"error": "Title, passage HTML/text, and questions are required"}), 400
    if not passage_html.startswith("<"):
        paras = [f"<p>{p.strip()}</p>" for p in passage_html.split("\n") if p.strip()]
        passage_html = f"<h3>{title}</h3>" + "".join(paras)
    con = _db()
    cur = con.execute(
        "INSERT INTO reading_passages (title, topic, passage_html, questions_json) VALUES (?,?,?,?)",
        (title, topic, passage_html, json.dumps(questions))
    )
    con.commit()
    rid = cur.lastrowid
    con.close()
    return jsonify({"ok": True, "id": rid}), 201


# ── 3. Interactive Grading Workbench & Item-Level Class Matrix ─────────────

@app.route("/api/teacher/submissions/<int:sub_id>/detail", methods=["GET"])
def teacher_submission_detail(sub_id):
    _ensure_v5_tables()
    con = _db()
    sub = con.execute(
        """SELECT asub.*, u.name as student_name, u.email as student_email,
                  a.title as assignment_title, a.assignment_type, a.question_ids_json,
                  a.writing_prompt_id, a.reading_passage_id
           FROM assignment_submissions asub
           JOIN users u ON u.id = asub.student_id
           JOIN assignments a ON a.id = asub.assignment_id
           WHERE asub.id = ?""",
        (sub_id,)
    ).fetchone()
    if not sub:
        con.close()
        return jsonify({"error": "Submission not found"}), 404

    sub_dict = _row(sub)
    try:
        sub_dict["rubric"] = json.loads(sub_dict.get("rubric_json") or "{}")
    except Exception:
        sub_dict["rubric"] = {}

    # Attach full exam answers or full writing essay for 2-column grading workbench
    exam_answers = []
    if sub_dict.get("attempt_id"):
        ans_rows = con.execute(
            """SELECT aa.*, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.option_e,
                      q.correct_option, q.explanation, q.topic, q.difficulty
               FROM attempt_answers aa
               JOIN questions q ON q.id = aa.question_id
               WHERE aa.attempt_id = ? ORDER BY aa.id""",
            (sub_dict["attempt_id"],)
        ).fetchall()
        exam_answers = [_row(r) for r in ans_rows]

    writing_detail = None
    if sub_dict.get("writing_id"):
        w_row = con.execute("SELECT * FROM writing_submissions WHERE id=?", (sub_dict["writing_id"],)).fetchone()
        if w_row:
            writing_detail = _row(w_row)
    elif sub_dict.get("assignment_type") == "writing":
        # Fallback to latest writing submission by this student
        w_row = con.execute(
            "SELECT * FROM writing_submissions WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (sub_dict["student_id"],)
        ).fetchone()
        if w_row:
            writing_detail = _row(w_row)

    con.close()
    sub_dict["exam_answers"] = exam_answers
    sub_dict["writing_detail"] = writing_detail
    return jsonify(sub_dict)


@app.route("/api/teacher/assignments/<int:asgn_id>/analytics", methods=["GET"])
def teacher_assignment_item_analytics(asgn_id):
    """Return per-question accuracy across all students who submitted this assignment."""
    con = _db()
    asgn = con.execute("SELECT * FROM assignments WHERE id=?", (asgn_id,)).fetchone()
    if not asgn:
        con.close()
        return jsonify({"error": "Assignment not found"}), 404

    subs = con.execute(
        "SELECT attempt_id FROM assignment_submissions WHERE assignment_id=? AND attempt_id IS NOT NULL",
        (asgn_id,)
    ).fetchall()
    attempt_ids = [r["attempt_id"] for r in subs if r["attempt_id"]]
    qids = json.loads(asgn["question_ids_json"] or "[]")

    items = []
    if qids:
        ph_q = ",".join("?" * len(qids))
        q_rows = con.execute(f"SELECT * FROM questions WHERE id IN ({ph_q})", qids).fetchall()
        q_map = {r["id"]: _row(r) for r in q_rows}
        for qid in qids:
            q_info = q_map.get(qid)
            if not q_info:
                continue
            total_ans = correct_ans = wrong_ans = blank_ans = 0
            dist = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "Blank": 0}
            if attempt_ids:
                ph_a = ",".join("?" * len(attempt_ids))
                a_rows = con.execute(
                    f"SELECT selected_option, points_awarded FROM attempt_answers WHERE question_id=? AND attempt_id IN ({ph_a})",
                    (qid, *attempt_ids)
                ).fetchall()
                for ar in a_rows:
                    total_ans += 1
                    sel = (ar["selected_option"] or "").upper()
                    if sel in dist:
                        dist[sel] += 1
                    else:
                        dist["Blank"] += 1
                    if ar["points_awarded"] > 0:
                        correct_ans += 1
                    elif ar["points_awarded"] < 0:
                        wrong_ans += 1
                    else:
                        blank_ans += 1
            acc = round((correct_ans / total_ans) * 100, 1) if total_ans > 0 else 0.0
            items.append({
                "question_id": qid,
                "subject": q_info["subject"],
                "topic": q_info["topic"],
                "question_text": q_info["question_text"],
                "correct_option": q_info["correct_option"],
                "total_responses": total_ans,
                "correct_count": correct_ans,
                "wrong_count": wrong_ans,
                "blank_count": blank_ans,
                "accuracy_pct": acc,
                "option_distribution": dist,
            })
    con.close()
    return jsonify({
        "assignment_id": asgn_id,
        "title": asgn["title"],
        "submission_count": len(attempt_ids),
        "items": items
    })


# ── 4. Master Gradebook Matrix Endpoint ───────────────────────────────────

@app.route("/api/teacher/gradebook", methods=["GET"])
def teacher_gradebook():
    _ensure_v5_tables()
    con = _db()
    uid = _uid()
    students = con.execute(
        "SELECT u.id, u.name, u.email, u.target_uni "
        "FROM teacher_students ts JOIN users u ON u.id=ts.student_id "
        "WHERE ts.teacher_id=? ORDER BY u.name", (uid,)
    ).fetchall()
    assignments = con.execute(
        "SELECT id, title, assignment_type, due_date FROM assignments WHERE teacher_id=? ORDER BY id ASC",
        (uid,)
    ).fetchall()
    subs = con.execute(
        "SELECT asub.* FROM assignment_submissions asub "
        "JOIN assignments a ON a.id=asub.assignment_id "
        "WHERE a.teacher_id=?", (uid,)
    ).fetchall()
    con.close()

    sub_map = {}
    for s in subs:
        sub_map[f"{s['student_id']}_{s['assignment_id']}"] = _row(s)

    student_rows = []
    for st in students:
        sid = st["id"]
        grades = {}
        total_pct = 0.0
        graded_count = 0
        for a in assignments:
            aid = a["id"]
            sub = sub_map.get(f"{sid}_{aid}")
            if sub:
                final_val = sub["teacher_grade"] if sub["teacher_grade"] is not None else sub["score"]
                max_val = sub["max_score"] or 20.0
                grades[str(aid)] = {
                    "submission_id": sub["id"],
                    "status": sub["status"],
                    "score": sub["score"],
                    "max_score": max_val,
                    "teacher_grade": sub["teacher_grade"],
                    "final_display": f"{final_val} / {max_val}" if final_val is not None else "Submitted",
                    "tab_switches": sub.get("tab_switches", 0)
                }
                if final_val is not None and max_val > 0:
                    total_pct += (float(final_val) / float(max_val)) * 100.0
                    graded_count += 1
            else:
                grades[str(aid)] = {
                    "submission_id": None,
                    "status": "pending",
                    "final_display": "—"
                }
        avg_pct = round(total_pct / graded_count, 1) if graded_count > 0 else 0.0
        student_rows.append({
            "student_id": sid,
            "name": st["name"],
            "email": st["email"],
            "target_uni": st["target_uni"],
            "grades": grades,
            "overall_avg_pct": avg_pct
        })

    return jsonify({
        "assignments": [_row(a) for a in assignments],
        "students": student_rows
    })



@app.route("/api/teacher/author/import-json", methods=["POST"])
def teacher_bulk_import_questions():
    data = request.get_json(force=True) or {}
    questions = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(questions, list) or not questions:
        return jsonify({"error": "Provide a JSON array of question objects."}), 400

    con = _db()
    imported = 0
    for q in questions:
        subj = q.get("subject", "Mathematics")
        if subj not in ALLOWED_SUBJECTS:
            continue
        q_text = (q.get("question_text") or "").strip()
        oa = (q.get("option_a") or "").strip()
        ob = (q.get("option_b") or "").strip()
        oc = (q.get("option_c") or "").strip()
        od = (q.get("option_d") or "").strip()
        oe = (q.get("option_e") or "").strip()
        c_opt = (q.get("correct_option") or "A").strip().upper()
        if not q_text or not oa or not ob or not oc or not od or not oe or c_opt not in ("A","B","C","D","E"):
            continue
        con.execute(
            """INSERT INTO questions
               (mock_set, subject, topic, question_text, option_a, option_b, option_c, option_d, option_e, correct_option, explanation, difficulty)
               VALUES (4, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                subj,
                q.get("topic", "Imported"),
                q_text, oa, ob, oc, od, oe, c_opt,
                q.get("explanation", ""),
                q.get("difficulty", "Medium") if q.get("difficulty") in ("Easy","Medium","Hard") else "Medium"
            )
        )
        imported += 1
    con.commit()
    con.close()
    return jsonify({"ok": True, "imported_count": imported}), 201


if __name__ == "__main__":
    app.run(debug=True, port=5000)
