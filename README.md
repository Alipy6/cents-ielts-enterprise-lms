# 🎓 CEnT-S & IELTS Enterprise LMS (v6.0 Production SaaS)

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Backend-Flask_3.0-000000?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/Database-SQLite_3_(Persistent)-003B57?logo=sqlite&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-59_Passed_(100%25)-10b981?logo=pytest&logoColor=white)
![Deploy](https://img.shields.io/badge/Cloud_Ready-Render_%7C_Gunicorn-46E3B7)
![License](https://img.shields.io/badge/License-MIT-6366f1)

A production-grade, multi-tenant **Learning Management System (LMS), Instructor Authoring Studio, and Diagnostic Assessment Engine** purpose-built for the **CISIA CEnT-S** university entrance examination (*Mathematics, Logic, Physics, Chemistry*) and **IELTS Academic** (*Reading & Writing*).

---

## 🌟 Core Platform Capabilities

### 👨‍🏫 1. Complete Instructor Studio & Classroom Management
* **Multi-Cohort & Classroom Manager**: Create multiple independent cohorts/classrooms, each with its own auto-generated invite code (e.g., `CENTS2026`), or enroll students directly via email.
* **Classroom Announcements & Study Materials Board**: Publish lecture notes, homework instructions, and external resource links directly to student dashboards.
* **Teacher Content Authoring Studio**:
  * **Custom CEnT-S Question Builder**: Author 5-option (`A`–`E`) questions with inline $\LaTeX$ math rendering and step-by-step explanations.
  * **Bulk JSON Question Importer & Exporter**: Upload or export entire question banks in 1 click using standardized JSON files.
  * **Custom IELTS Writing & Multi-Question Reading Builder**: Create custom Task 1 (with HTML tables/SVG charts) & Task 2 writing prompts, and build full reading passages with dynamic multi-question comprehension sets.
* **Interactive 2-Column Grading Workbench**:
  * Side-by-side inspection of student submissions: view the student's full essay (with NLP annotations) or per-question exam paper on the left while scoring rubrics (`TA`, `CC`, `LR`) and writing line-by-line feedback on the right.
* **Class Item-Level Accuracy Matrix**: Automatically aggregates class-wide performance per question on every assigned exam, flagging questions with $<50\%$ accuracy in red for in-class review.
* **Master Gradebook Matrix & Excel/CSV Export**: Spreadsheet-style matrix (`Students × Assignments`) displaying real-time status, scores, overall averages, and 1-click `.CSV` export.
* **Automated Weakness Diagnostics**: Real-time SQL aggregation detects each student's lowest-performing subject and enables **1-Click Targeted Remediation Quizzes**.

---

### 🎓 2. Student Portal & Proctored Exam Integrity
* **Strict Proctored Assignment Mode (`Anti-Cheat`)**:
  * Disables timer pause/reset controls on official instructor assignments.
  * Tracks browser tab switches (`visibilitychange` proctoring log) and reports violations directly to the instructor's Grading Workbench.
  * **Answer-Key Lock**: Prevents answer leakage by locking step-by-step solutions and answer keys on proctored assignments until the instructor reviews and releases the grade.
* **Strict Multi-Tenant Data Isolation**: Every student's exam history, analytics, writing archive, and mistake notebook are strictly isolated to their own account.

---

### 🏛️ 3. CISIA CEnT-S Exam Simulator & Risk Optimizer
* **5 Examination Modes**: Full Mock Exams #1, #2, #3, Official 40-Question Marathon, and Custom / Mistake Notebook Drills across the 4 official subjects (*Mathematics, Logic, Physics, Chemistry*).
* **Authentic CISIA Penalty Scoring**: $+1.00$ Correct, $-0.25$ Wrong, $0.00$ Blank.
* **What-If Penalty Risk Optimizer**: Computes the exact hypothetical score had the student left wrong guesses blank, training optimal risk management.
* **In-Exam Scientific Toolkit**: Collapsible $\LaTeX$ formula & constants reference sheet, interactive question navigator palette, **Zen Full-Screen Focus Mode**, and 3-state timer controls (*Start / Pause / Reset*).

---

### 🤖 4. Hybrid AI Question Factory & Trap Tutor (`ai_engine.py`)
* **Zero-Config Dual Engine**:
  * **Offline Parametric Scientific Engine**: Works **100% offline out-of-the-box** without any API key, procedurally generating fresh calculus, algebra, logic, kinematics, circuits, and stoichiometry problems with exact mathematical solutions and 5 $\LaTeX$ options.
  * **Live LLM Integration**: Seamlessly switches to live **OpenAI / Gemini API** generation when an API key is configured in Account Settings.
* **Study Notes $\to$ Exam Converter**: Extracts key domain concepts from pasted lecture notes to generate tailored practice quizzes.
* **AI Distractor & Trap Tutor**: Explains the exact mathematical or conceptual trap behind any wrong option selected by the student.

---

### ✍️ 5. IELTS Academic Studio (Reading & Writing)
* **Split-Screen CD-IELTS Reading Lab**: Side-by-side scrollable academic passages and comprehension questions with instant band estimation and paragraph evidence mapping.
* **Deterministic NLP Writing Evaluator (`analyzer.py`)**:
  * Built-in gibberish & short-text guardrails.
  * **Interactive Annotated Essay Highlighter**: Highlights academic discourse markers in **green**, overused words ($\ge 4\times$) in **red**, and run-on sentences ($>35$ words) in **amber**.
  * **Band 8.5 Academic Prose Upgrader**: Rewrites student paragraphs into Band 8.5 academic register with vocabulary replacement tables and grammar tips.

---

### 📱 6. Adaptive 3-Tier Responsive UI/UX
* **Desktop (`> 1024px`)**: Collapsible left vertical navigation sidebar + top utility header.
* **Small Windows / Split-Screen (`640px – 1024px`)**: Auto-collapses into a compact `70px` icon rail for side-by-side study with lecture PDFs or videos.
* **Mobile (`< 640px`)**: Slide-over touch drawer + fixed **Bottom Navigation Bar** for effortless thumb navigation on phones.

---

## 🚀 Quick Start (Local Installation)

```bash
# 1. Clone the repository
git clone [https://github.com/YOUR_USERNAME/exam-prep-engine.git](https://github.com/YOUR_USERNAME/exam-prep-engine.git)
cd exam-prep-engine

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize the database (or let app.py auto-initialize on first run)
python init_db.py

# 4. Run the automated 59-test Pytest suite
python -m pytest -v

# 5. Launch the production-ready server
python app.py
Open http://127.0.0.1:5000 in your browser.(Note: The SQLite database is non-destructive on server restarts—all custom questions, classrooms, and student submissions persist automatically).🔐 Built-In Demo Accounts (1-Click Access)Use the 1-Click Demo Access buttons in the Sign-In modal or click ⇄ Switch Role in the top header to test both portals immediately:Portal RoleEmailPasswordDefault Cohort Code👨‍🏫 Instructorinstructor@academy.euTeacher2026!CENTS2026🎓 Studentali@student.euStudent2026!Joins CENTS2026☁️ 1-Click Cloud Deployment (Render.com)This repository includes render.yaml, Procfile, and gunicorn configuration for instant cloud hosting:Push this repository to your GitHub account.Go to Render.com $\to$ New + $\to$ Blueprint (or Web Service).Connect your GitHub repository. Render will automatically detect render.yaml / Procfile and deploy your live HTTPS platform.🗂️ Repository ArchitecturePlaintextexam-prep-engine/
├── app.py                   # Flask v6.0 REST API (Auth, LMS, Authoring, Gradebook, AI)
├── init_db.py               # Persistent SQLite Schema & Seed Data Initializer
├── analyzer.py              # Deterministic IELTS Academic Writing NLP Analyzer
├── ai_engine.py             # Hybrid LLM + Parametric Scientific Question Generator
├── test_app.py              # Automated 59-Test Pytest Verification Suite
├── requirements.txt         # Production Dependencies (Flask, Gunicorn, Werkzeug, Pytest)
├── Procfile                 # Cloud WSGI Startup Command
├── render.yaml              # Render Cloud Blueprint Configuration
├── .github/workflows/ci.yml # Automated GitHub Actions CI Pipeline
└── static/
    ├── index.html           # 3-Tier Responsive Sidebar SPA & Modals
    └── app.js               # Frontend State Controller, Proctoring, Chart.js & MathJax
📄 LicenseReleased under the MIT License. Free for educational, academic, and portfolio use.