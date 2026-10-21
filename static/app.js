// ══════════════════════════════════════════════════════════════
// CEnT-S & IELTS Enterprise LMS v4.0 — Frontend Controller (app.js)
// ══════════════════════════════════════════════════════════════
"use strict";

function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function typesetMath(el) {
  if (window.MathJax && typeof window.MathJax.typesetPromise === "function") {
    window.MathJax.typesetPromise(el ? [el] : undefined).catch(function () {});
  }
}

function apiFetch(url, options) {
  options = options || {};
  var headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
  return fetch(url, Object.assign({ credentials: "same-origin" }, options, { headers: headers }))
    .then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok && data && !data.error) data.error = "Error (" + r.status + ")";
        return data;
      });
    });
}

function apiGet(url) { return apiFetch(url, { method: "GET" }); }
function apiPost(url, body) { return apiFetch(url, { method: "POST", body: JSON.stringify(body || {}) }); }
function apiPut(url, body) { return apiFetch(url, { method: "PUT", body: JSON.stringify(body || {}) }); }
function apiDelete(url) { return apiFetch(url, { method: "DELETE" }); }

function showToast(msg, type) {
  type = type || "info";
  var container = document.getElementById("toast-container");
  if (!container) return;
  var toast = document.createElement("div");
  toast.className = "toast " + type;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(function () {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.35s";
    setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 350);
  }, 3200);
}

function formatTime(seconds) {
  var m = Math.floor(seconds / 60);
  var s = seconds % 60;
  return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
}

function openModal(id) {
  var el = document.getElementById(id);
  if (el) el.classList.add("open");
}

function closeModal(id) {
  var el = document.getElementById(id);
  if (el) el.classList.remove("open");
}

// ── Global State ───────────────────────────────────────────────

var STATE = {
  user: null,
  currentTab: "exam",
  activeAssignmentId: null,
  examMode: "mock1",
  examModeLabel: "Mock Exam #1",
  examQuestions: [],
  selectedAnswers: {},
  flaggedQuestions: {},
  examTimer: null,
  examPaused: false,
  examInitialDuration: 2400,
  examTimeLeft: 2400,
  readingPassages: [],
  currentPassage: null,
  readingTimer: null,
  readingPaused: false,
  readingTimeLeft: 1200,
  writingPrompts: [],
  writingTimer: null,
  writingPaused: false,
  writingTimeLeft: 2400,
  allBankQuestions: [],
  bankOffset: 0,
  bankLimit: 10,
  bankTotal: 0,
  charts: {},
  lastGeneratedQuestions: []
};

// ── Responsive Sidebar & Zen Focus Mode Controls ───────────────

function toggleSidebar() {
  var sb = document.getElementById("sidebar");
  if (sb) sb.classList.toggle("collapsed");
}

function openMobileSidebar() {
  var sb = document.getElementById("sidebar");
  var bd = document.getElementById("sidebar-backdrop");
  if (sb) sb.classList.add("mobile-open");
  if (bd) bd.classList.add("open");
}

function closeMobileSidebar() {
  var sb = document.getElementById("sidebar");
  var bd = document.getElementById("sidebar-backdrop");
  if (sb) sb.classList.remove("mobile-open");
  if (bd) bd.classList.remove("open");
}

function toggleZenMode() {
  document.body.classList.toggle("zen-mode");
  var btn = document.getElementById("btn-zen-mode");
  if (btn) {
    btn.textContent = document.body.classList.contains("zen-mode") ? "✕ Exit Focus" : "⛶ Focus Mode";
  }
}

var VIEW_TITLES = {
  "student-assignments": "My Classroom & Assigned Tasks",
  "teacher-roster": "Instructor Portal — Student Roster & Diagnostics",
  "teacher-assignments": "Instructor Portal — Assignment & Exam Builder",
  "exam": "CEnT-S / CISIA Examination Simulator",
  "bank": "AI Question Factory & Study Hub",
  "reading": "IELTS Academic Reading Simulator",
  "writing": "IELTS Academic Writing Studio",
  "analytics": "Performance Analytics & University Cut-off Radar",
  "account": "Account & Security Settings"
};

function showTab(tabId) {
  closeMobileSidebar();
  if (STATE.user && STATE.user.role === "teacher" && tabId === "student-assignments") {
    tabId = "teacher-assignments";
  }
  document.querySelectorAll(".tab-section").forEach(function (s) { s.classList.remove("active"); });
  document.querySelectorAll(".nav-btn, .mob-nav-btn").forEach(function (b) { b.classList.remove("active"); });

  var sec = document.getElementById("tab-" + tabId);
  if (sec) sec.classList.add("active");

  document.querySelectorAll('[data-tab="' + tabId + '"]').forEach(function (b) { b.classList.add("active"); });
  var titleEl = document.getElementById("current-view-title");
  if (titleEl) titleEl.textContent = VIEW_TITLES[tabId] || "Academic Workspace";
  STATE.currentTab = tabId;

  if (tabId === "student-assignments") loadStudentAssignments();
  else if (tabId === "teacher-roster") loadTeacherRoster();
  else if (tabId === "teacher-assignments") { loadTeacherRoster(); loadTeacherAssignments(); loadManualPickerQuestions(); }
  else if (tabId === "exam") loadLobbyAttempts();
  else if (tabId === "bank") { loadQuestionBank(); loadFlashcards(""); }
  else if (tabId === "reading") loadReadingPassages();
  else if (tabId === "writing") { loadWritingPrompts(); loadWritingHistory(); }
  else if (tabId === "analytics") loadAnalytics();
  else if (tabId === "account") populateAccountForm();
}

// ── Authentication & Role Management ───────────────────────────

function initAuth() {
  apiGet("/api/auth/me").then(function (data) {
    if (data && (data.id || data.user_id)) {
      STATE.user = data;
      renderUserArea();
      if (data.role === "teacher") {
        showTab("teacher-roster");
      } else {
        loadStudentAssignmentsBadge();
      }
    } else {
      STATE.user = null;
      renderUserArea();
    }
  }).catch(function () { renderUserArea(); });
}

function renderUserArea() {
  var nameEl = document.getElementById("user-name-display");
  var roleBadge = document.getElementById("user-role-badge");
  var uniBadge = document.getElementById("user-uni-badge");
  var teacherGroup = document.getElementById("nav-group-teacher");
  var studentTasksBtn = document.getElementById("nav-item-student-tasks");
  var badgePending = document.getElementById("badge-pending-tasks");
  var codeEl = document.getElementById("teacher-invite-code-display");

  if (STATE.user) {
    var isTeacher = STATE.user.role === "teacher";
    if (nameEl) nameEl.textContent = STATE.user.name || STATE.user.email;
    if (roleBadge) {
      roleBadge.textContent = isTeacher ? "INSTRUCTOR" : "STUDENT";
      roleBadge.className = "role-pill " + (isTeacher ? "teacher" : "student");
    }
    if (uniBadge) uniBadge.textContent = STATE.user.target_uni || "Politecnico di Milano";
    if (teacherGroup) teacherGroup.style.display = isTeacher ? "block" : "none";
    if (studentTasksBtn) studentTasksBtn.style.display = isTeacher ? "none" : "flex";
    if (isTeacher && badgePending) badgePending.style.display = "none";
    if (codeEl && STATE.user.invite_code) codeEl.textContent = STATE.user.invite_code;
    populateAccountForm();
  } else {
    if (nameEl) nameEl.textContent = "Guest";
    if (roleBadge) { roleBadge.textContent = "GUEST"; roleBadge.className = "role-pill student"; }
    if (teacherGroup) teacherGroup.style.display = "none";
  }
}

function switchAuthTab(tab) {
  document.getElementById("auth-form-signin").style.display = tab === "signin" ? "block" : "none";
  document.getElementById("auth-form-register").style.display = tab === "register" ? "block" : "none";
  document.getElementById("auth-tab-signin").classList.toggle("active", tab === "signin");
  document.getElementById("auth-tab-register").classList.toggle("active", tab === "register");
  document.getElementById("signin-error").textContent = "";
  document.getElementById("reg-error").textContent = "";
}

function demoLogin(role) {
  var email = role === "teacher" ? "instructor@academy.eu" : "ali@student.eu";
  var password = role === "teacher" ? "Teacher2026!" : "Student2026!";
  apiPost("/api/auth/login", { email: email, password: password }).then(function (data) {
    if (data && (data.user_id || data.id)) {
      STATE.user = data;
      renderUserArea();
      closeModal("auth-modal");
      showToast("Signed in as " + data.name + " (" + data.role.toUpperCase() + ")", "success");
      showTab(data.role === "teacher" ? "teacher-roster" : "student-assignments");
    } else {
      showToast(data.error || "Demo login failed", "error");
    }
  });
}

function doSignIn() {
  var email = document.getElementById("signin-email").value.trim();
  var password = document.getElementById("signin-password").value;
  var errEl = document.getElementById("signin-error");
  errEl.textContent = "";
  if (!email || !password) { errEl.textContent = "Email and password required."; return; }
  apiPost("/api/auth/login", { email: email, password: password }).then(function (data) {
    if (data && (data.user_id || data.id)) {
      STATE.user = data;
      renderUserArea();
      closeModal("auth-modal");
      showToast("Welcome back, " + data.name + "!", "success");
      showTab(data.role === "teacher" ? "teacher-roster" : "exam");
    } else {
      errEl.textContent = data.error || "Invalid credentials.";
    }
  });
}

function doRegister() {
  var name = document.getElementById("reg-name").value.trim();
  var email = document.getElementById("reg-email").value.trim();
  var password = document.getElementById("reg-password").value;
  var role = document.getElementById("reg-role").value;
  var uni = document.getElementById("reg-uni").value;
  var errEl = document.getElementById("reg-error");
  errEl.textContent = "";
  if (!name || !email || !password) { errEl.textContent = "All fields are required."; return; }
  apiPost("/api/auth/register", { name: name, email: email, password: password, role: role, target_uni: uni }).then(function (data) {
    if (data && (data.user_id || data.id)) {
      STATE.user = data;
      renderUserArea();
      closeModal("auth-modal");
      showToast("Account created as " + role.toUpperCase() + "!", "success");
      showTab(role === "teacher" ? "teacher-roster" : "exam");
    } else {
      errEl.textContent = data.error || "Registration failed.";
    }
  });
}

function openGoogleOAuthModal() {
  closeModal("auth-modal");
  var emailIn = document.getElementById("google-email-input");
  var nameIn = document.getElementById("google-name-input");
  if (emailIn && !emailIn.value) emailIn.value = "";
  if (nameIn && !nameIn.value) nameIn.value = "";
  openModal("google-oauth-modal");
}

function quickGoogleSelect(email, name, role) {
  var emailEl = document.getElementById("google-email-input");
  var nameEl = document.getElementById("google-name-input");
  var roleEl = document.getElementById("google-role-input");
  if (emailEl) emailEl.value = email;
  if (nameEl) nameEl.value = name;
  if (roleEl) roleEl.value = role || "student";
  submitGoogleOAuth(email, name, role);
}

function submitGoogleOAuth(directEmail, directName, directRole) {
  var emailEl = document.getElementById("google-email-input");
  var nameEl = document.getElementById("google-name-input");
  var roleEl = document.getElementById("google-role-input");

  var email = (directEmail || (emailEl ? emailEl.value : "")).trim().toLowerCase();
  var name = (directName || (nameEl ? nameEl.value : "")).trim();
  var role = (directRole || (roleEl ? roleEl.value : "student")).trim().toLowerCase();

  if (!email || email.indexOf("@") === -1) {
    showToast("Please enter a valid Google email address (e.g. name@gmail.com).", "warning");
    return;
  }
  if (!name) {
    name = email.split("@")[0].replace(/[._-]/g, " ");
    name = name.charAt(0).toUpperCase() + name.slice(1);
  }

  var safeSub = "google_oauth_" + email.replace(/[^a-z0-9]/gi, "_");

  apiPost("/api/auth/google", {
    google_sub: safeSub,
    email: email,
    name: name,
    role: role
  }).then(function (data) {
    if (data && (data.user_id || data.id)) {
      STATE.user = data;
      renderUserArea();
      closeModal("google-oauth-modal");
      closeModal("auth-modal");
      showToast("Signed in with Google as " + data.name + " (" + data.role.toUpperCase() + ")!", "success");
      showTab(data.role === "teacher" ? "teacher-roster" : "student-assignments");
    } else {
      showToast((data && data.error) ? data.error : "Google authentication failed.", "error");
    }
  }).catch(function () {
    showToast("Network error while connecting to Google Auth.", "error");
  });
}

function quickToggleRole() {
  if (!STATE.user) { openModal("auth-modal"); return; }
  var newRole = STATE.user.role === "teacher" ? "student" : "teacher";
  apiPut("/api/auth/profile", { role: newRole }).then(function (data) {
    if (data && (data.id || data.user_id)) {
      STATE.user = data;
      renderUserArea();
      showToast("Switched active portal to " + newRole.toUpperCase() + "!", "success");
      showTab(newRole === "teacher" ? "teacher-roster" : "student-assignments");
    }
  });
}

function populateAccountForm() {
  if (!STATE.user) return;
  document.getElementById("acc-name").value = STATE.user.name || "";
  document.getElementById("acc-email").value = STATE.user.email || "";
  document.getElementById("acc-role").value = STATE.user.role || "student";
  document.getElementById("acc-uni").value = STATE.user.target_uni || "Politecnico di Milano";
  document.getElementById("acc-target-score").value = STATE.user.target_score != null ? STATE.user.target_score : 16.5;
  document.getElementById("acc-target-ielts").value = STATE.user.target_ielts != null ? STATE.user.target_ielts : 7.5;
}

function saveAccountSettings() {
  var payload = {
    name: document.getElementById("acc-name").value.trim(),
    email: document.getElementById("acc-email").value.trim(),
    role: document.getElementById("acc-role").value,
    target_uni: document.getElementById("acc-uni").value,
    target_score: parseFloat(document.getElementById("acc-target-score").value) || 16.0,
    target_ielts: parseFloat(document.getElementById("acc-target-ielts").value) || 7.0
  };
  var aiKey = document.getElementById("acc-ai-key").value.trim();
  var newPass = document.getElementById("acc-new-password").value;
  if (aiKey) payload.ai_api_key = aiKey;
  if (newPass) payload.new_password = newPass;

  apiPut("/api/auth/profile", payload).then(function (data) {
    if (data && (data.id || data.user_id)) {
      STATE.user = data;
      document.getElementById("acc-new-password").value = "";
      renderUserArea();
      showToast("Account settings saved!", "success");
      if (data.role === "teacher" && STATE.currentTab === "student-assignments") {
        showTab("teacher-roster");
      }
    } else {
      showToast(data.error || "Failed to update account.", "error");
    }
  });
}

function doLogout() {
  apiPost("/api/auth/logout", {}).then(function () {
    STATE.user = null;
    renderUserArea();
    showToast("Signed out.", "info");
    openModal("auth-modal");
  });
}

// ── Student Classroom & Assignments ────────────────────────────

function joinTeacherByCode() {
  var code = document.getElementById("join-invite-code").value.trim();
  if (!code) { showToast("Enter an invite code.", "warning"); return; }
  apiPost("/api/student/join-teacher", { invite_code: code }).then(function (data) {
    if (data && data.ok) {
      showToast("Connected to instructor (" + (data.teacher_name || "Classroom") + ")!", "success");
      loadStudentAssignments();
    } else {
      showToast(data.error || "Invalid invite code.", "error");
    }
  });
}

function loadStudentAssignmentsBadge() {
  if (STATE.user && STATE.user.role === "teacher") return;
  apiGet("/api/assignments").then(function (list) {
    if (!Array.isArray(list)) return;
    var pending = list.filter(function (a) { return a.status === "pending"; }).length;
    var badge = document.getElementById("badge-pending-tasks");
    if (badge) {
      badge.textContent = pending;
      badge.style.display = pending > 0 ? "inline-block" : "none";
    }
  });
}

function loadStudentAssignments() {
  var el = document.getElementById("student-assignments-list");
  if (!el) return;
  apiGet("/api/assignments").then(function (list) {
    if (!Array.isArray(list) || !list.length) {
      el.innerHTML = '<div class="text-muted fs-sm">No assignments yet. Enter code <strong>CENTS2026</strong> above and click Connect to Instructor!</div>';
      return;
    }
    loadStudentAssignmentsBadge();
    el.innerHTML = list.map(function (a) {
      var st = a.status || "pending";
      var badgeCls = st === "graded" ? "badge-graded" : (st === "submitted" ? "badge-submitted" : "badge-pending");
      var qCount = (a.question_ids || []).length;
      return (
        '<div class="review-item">' +
          '<div class="flex-row" style="justify-content:space-between;margin-bottom:6px">' +
            '<div><strong>' + escHtml(a.title) + '</strong> <span class="fs-sm text-muted">by ' + escHtml(a.teacher_name || "Instructor") + '</span></div>' +
            '<span class="badge ' + badgeCls + '">' + escHtml(st.toUpperCase()) + '</span>' +
          '</div>' +
          '<div class="fs-sm text-muted mb8">' + escHtml(a.description || "") + '</div>' +
          '<div class="flex-row fs-sm text-muted mb8">' +
            '<span>Type: <strong>' + escHtml((a.assignment_type || "exam").toUpperCase()) + '</strong></span> · ' +
            (qCount ? '<span>Questions: <strong>' + qCount + '</strong></span> · ' : '') +
            '<span>Time Limit: <strong>' + (a.time_limit_mins || 20) + 'm</strong></span> · ' +
            '<span>Due: <strong>' + escHtml(a.due_date || "Flexible") + '</strong></span>' +
          '</div>' +
          (a.score != null ? '<div class="fs-sm mb8">Your Score: <strong class="text-accent">' + a.score + ' / ' + a.max_score + '</strong></div>' : '') +
          (a.teacher_grade != null || a.teacher_comment ? (
            '<div class="ai-explanation-box mb8">' +
              '<div class="fw700 text-success">👨‍🏫 Instructor Evaluation ' + (a.teacher_grade != null ? '(Grade: ' + a.teacher_grade + ')' : '') + '</div>' +
              '<div>' + escHtml(a.teacher_comment || "Graded by instructor.") + '</div>' +
            '</div>'
          ) : '') +
          '<button class="btn-primary btn-sm" onclick=\'launchAssignedTask(' + JSON.stringify(a).replace(/'/g, "&#39;") + ')\'>' +
            (st === "pending" ? "🚀 Start Assigned Task" : "↻ Retake / View Task") +
          '</button>' +
        '</div>'
      );
    }).join("");
  });
}

function launchAssignedTask(asgn) {
  STATE.activeAssignmentId = asgn.id;
  if (asgn.assignment_type === "writing") {
    showTab("writing");
    showToast("Write your essay and click Evaluate to submit to your instructor.", "info");
    return;
  }
  if (asgn.assignment_type === "reading") {
    showTab("reading");
    showToast("Complete the reading test to submit to your instructor.", "info");
    return;
  }
  var qids = asgn.question_ids || [];
  var url = qids.length ? "/api/questions?ids=" + qids.join(",") : "/api/exam?mode=mock1";
  apiGet(url).then(function (data) {
    var qs = Array.isArray(data) ? data : (data.flat_questions || []);
    if (!qs.length) { showToast("Could not load assignment questions.", "error"); return; }
    showTab("exam");
    STATE.examMode = "custom";
    STATE.examModeLabel = "Assignment: " + asgn.title;
    launchExamWorkspace(qs, (asgn.time_limit_mins || 20) * 60);
  });
}

// ── Instructor Roster, Diagnostics & Assignment Builder ────────

function copyInviteCode() {
  var code = document.getElementById("teacher-invite-code-display").textContent;
  if (navigator.clipboard) navigator.clipboard.writeText(code);
  showToast("Copied invite code: " + code, "success");
}

function loadTeacherRoster() {
  var tbody = document.getElementById("teacher-students-tbody");
  var sel = document.getElementById("asgn-student-select");
  apiGet("/api/teacher/students").then(function (students) {
    if (!Array.isArray(students)) {
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-muted">Switch to Instructor Role to view roster.</td></tr>';
      return;
    }
    if (sel) {
      sel.innerHTML = '<option value="">All Enrolled Students (' + students.length + ')</option>' +
        students.map(function (s) { return '<option value="' + s.id + '">' + escHtml(s.name) + ' (' + escHtml(s.email) + ')</option>'; }).join("");
    }
    if (!tbody) return;
    if (!students.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-muted">No students enrolled in this account yet. Click "+ Add Student" above to enroll ali@student.eu!</td></tr>';
      return;
    }
    tbody.innerHTML = students.map(function (s) {
      var weak = s.weakest_subject || "Mathematics";
      return (
        "<tr>" +
          "<td><strong>" + escHtml(s.name) + "</strong><div class='fs-sm text-muted'>" + escHtml(s.email) + "</div></td>" +
          "<td>" + escHtml(s.target_uni || "Politecnico di Milano") + "</td>" +
          "<td>" + (s.attempts_count || 0) + "</td>" +
          "<td class='text-accent fw700'>" + (s.avg_score || 0) + "%</td>" +
          "<td>" + (s.writing_count || 0) + "</td>" +
          "<td><span class='badge badge-pending'>" + escHtml(weak) + "</span></td>" +
          "<td><div class='flex-row'>" +
            "<button class='btn-sm' onclick='openStudentReport(" + s.id + ")'>📊 Full Report</button>" +
            "<button class='btn-sm' style='border-color:var(--warning);color:var(--warning)' onclick=\"assignWeaknessQuiz(" + s.id + ", '" + escHtml(s.name) + "', '" + escHtml(weak) + "')\">⚡ Assign " + escHtml(weak) + " Drill</button>" +
            "<button class='btn-sm text-danger' onclick='teacherRemoveStudent(" + s.id + ")'>✕</button>" +
          "</div></td>" +
        "</tr>"
      );
    }).join("");
  });
}

function teacherAddStudent() {
  var email = document.getElementById("teacher-add-student-email").value.trim();
  if (!email) { showToast("Enter student email.", "warning"); return; }
  apiPost("/api/teacher/students", { email: email }).then(function (data) {
    if (data && data.ok) {
      showToast("Added " + (data.name || email) + " to your classroom!", "success");
      loadTeacherRoster();
    } else {
      showToast(data.error || "Student not found.", "error");
    }
  });
}

function teacherRemoveStudent(sid) {
  apiDelete("/api/teacher/students/" + sid).then(function () {
    showToast("Removed student from roster.", "info");
    loadTeacherRoster();
  });
}

function assignWeaknessQuiz(studentId, studentName, subject) {
  apiPost("/api/teacher/assignments", {
    title: "Targeted Remediation: " + subject + " Drill",
    description: "Personalized 5-question practice drill targeting your weakest subject (" + subject + ").",
    student_id: studentId,
    assignment_type: "exam",
    subject: subject,
    difficulty: "Medium",
    auto_generate_count: 5,
    time_limit_mins: 15,
    due_date: "2026-11-01"
  }).then(function (data) {
    if (data && data.ok) {
      showToast("Assigned 5-question " + subject + " drill to " + studentName + "!", "success");
      loadTeacherAssignments();
    }
  });
}

function openStudentReport(studentId) {
  var content = document.getElementById("student-report-content");
  content.innerHTML = '<div class="text-muted">Loading student portfolio...</div>';
  openModal("student-report-modal");
  apiGet("/api/teacher/student/" + studentId + "/report").then(function (data) {
    if (!data || !data.user) { content.innerHTML = '<div class="text-danger">Failed to load report.</div>'; return; }
    var u = data.user;
    document.getElementById("student-report-title").textContent = u.name + " — Diagnostic Portfolio (" + u.email + ")";
    var accObj = data.subject_accuracy || {};
    var accHtml = Object.keys(accObj).map(function (k) {
      return '<div class="stat-card"><div class="stat-label">' + escHtml(k) + '</div><div class="stat-value text-accent">' + accObj[k] + '%</div></div>';
    }).join("") || '<div class="text-muted fs-sm">No subject data yet.</div>';

    var attHtml = (data.attempts || []).map(function (a) {
      return "<tr><td>#" + a.id + "</td><td>" + escHtml(a.exam_mode) + "</td><td class='fw700 text-accent'>" + a.total_score + " / " + a.max_possible_score + "</td><td class='text-success'>+" + a.correct_count + "</td><td class='text-danger'>-" + a.wrong_count + "</td><td>" + escHtml((a.timestamp || "").slice(0, 16)) + "</td></tr>";
    }).join("") || '<tr><td colspan="6" class="text-muted">No exam attempts.</td></tr>';

    var wrHtml = (data.writing_submissions || []).map(function (w) {
      return '<div class="review-item"><div class="fw700">' + escHtml(w.task_type) + ' — Band ' + w.estimated_band + ' (' + w.word_count + ' words)</div><div class="fs-sm text-muted mt8">' + escHtml(w.essay_text) + '</div></div>';
    }).join("") || '<div class="text-muted fs-sm">No writing submissions.</div>';

    content.innerHTML =
      '<div class="stats-grid">' + accHtml + '</div>' +
      '<div class="card-title mt16">Exam Attempts History</div>' +
      '<div class="table-responsive mb16"><table class="data-table"><thead><tr><th>#</th><th>Mode</th><th>Score</th><th>Correct</th><th>Wrong</th><th>Date</th></tr></thead><tbody>' + attHtml + '</tbody></table></div>' +
      '<div class="card-title">IELTS Writing Submissions</div>' + wrHtml;
  });
}

function onAsgnTypeChange() {
  var t = document.getElementById("asgn-type").value;
  var isExam = t === "exam";
  document.getElementById("asgn-auto-box").style.display = isExam && document.getElementById("asgn-selection-mode").value === "auto" ? "grid" : "none";
  document.getElementById("asgn-manual-box").style.display = isExam && document.getElementById("asgn-selection-mode").value === "manual" ? "block" : "none";
}

function onAsgnSelectionModeChange() {
  var mode = document.getElementById("asgn-selection-mode").value;
  document.getElementById("asgn-auto-box").style.display = mode === "auto" ? "grid" : "none";
  document.getElementById("asgn-manual-box").style.display = mode === "manual" ? "block" : "none";
  if (mode === "manual") loadManualPickerQuestions();
}

function loadManualPickerQuestions() {
  var box = document.getElementById("asgn-manual-q-list");
  if (!box || box.children.length > 0) return;
  apiGet("/api/questions").then(function (list) {
    if (!Array.isArray(list)) return;
    box.innerHTML = list.map(function (q) {
      return (
        '<label style="display:flex;align-items:flex-start;gap:8px;padding:6px 4px;border-bottom:1px solid var(--border);font-size:0.8rem;cursor:pointer">' +
          '<input type="checkbox" class="manual-q-cb" value="' + q.id + '" onchange="updateManualPickedCount()" style="margin-top:3px" />' +
          '<span><strong>#' + q.id + ' [' + escHtml(q.subject) + ' · ' + escHtml(q.difficulty) + ']</strong> ' + q.question_text + '</span>' +
        '</label>'
      );
    }).join("");
    typesetMath(box);
  });
}

function updateManualPickedCount() {
  var cbs = document.querySelectorAll(".manual-q-cb:checked");
  var el = document.getElementById("asgn-picked-count");
  if (el) el.textContent = cbs.length;
}

function teacherCreateAssignment() {
  var title = document.getElementById("asgn-title").value.trim();
  if (!title) { showToast("Please enter an assignment title.", "warning"); return; }
  var selMode = document.getElementById("asgn-selection-mode").value;
  var manualIds = Array.from(document.querySelectorAll(".manual-q-cb:checked")).map(function (cb) { return parseInt(cb.value, 10); });

  var payload = {
    title: title,
    description: document.getElementById("asgn-desc").value.trim(),
    student_id: document.getElementById("asgn-student-select").value ? parseInt(document.getElementById("asgn-student-select").value, 10) : null,
    assignment_type: document.getElementById("asgn-type").value,
    subject: document.getElementById("asgn-subject").value,
    difficulty: document.getElementById("asgn-difficulty").value,
    time_limit_mins: parseInt(document.getElementById("asgn-time-limit").value, 10) || 20,
    due_date: document.getElementById("asgn-due-date").value
  };

  if (payload.assignment_type === "exam") {
    if (selMode === "manual" && manualIds.length > 0) {
      payload.question_ids = manualIds;
    } else {
      payload.auto_generate_count = parseInt(document.getElementById("asgn-auto-count").value, 10) || 5;
    }
  }

  apiPost("/api/teacher/assignments", payload).then(function (data) {
    if (data && data.ok) {
      document.getElementById("asgn-title").value = "";
      showToast("Assignment published to student(s)!", "success");
      loadTeacherAssignments();
    } else {
      showToast(data.error || "Failed to create assignment.", "error");
    }
  });
}

function loadTeacherAssignments() {
  var el = document.getElementById("teacher-assignments-list");
  if (!el) return;
  apiGet("/api/assignments").then(function (list) {
    if (!Array.isArray(list) || !list.length) {
      el.innerHTML = '<div class="text-muted fs-sm">No assignments created yet.</div>';
      return;
    }
    el.innerHTML = list.map(function (a) {
      var subs = a.submissions || [];
      var subsHtml = subs.map(function (s) {
        return (
          '<div class="ai-explanation-box mt8">' +
            '<div class="flex-row" style="justify-content:space-between">' +
              '<strong>' + escHtml(s.student_name) + ' (' + escHtml(s.student_email) + ')</strong>' +
              '<span class="text-accent fw700">Auto Score: ' + (s.score != null ? s.score + '/' + s.max_score : 'N/A') + '</span>' +
            '</div>' +
            '<div class="flex-row mt8">' +
              '<input class="form-input" id="tgrade-' + s.id + '" type="number" step="0.5" placeholder="Grade" value="' + (s.teacher_grade != null ? s.teacher_grade : (s.score || '')) + '" style="max-width:100px" />' +
              '<input class="form-input" id="tcomm-' + s.id + '" placeholder="Write instructor feedback..." value="' + escHtml(s.teacher_comment || '') + '" style="flex:1" />' +
              '<button class="btn-success btn-sm" onclick="teacherGradeSubmission(' + s.id + ')">Save Grade</button>' +
            '</div>' +
          '</div>'
        );
      }).join("") || '<div class="fs-sm text-muted mt8">No student submissions yet.</div>';

      return (
        '<div class="review-item">' +
          '<div class="fw700">' + escHtml(a.title) + ' <span class="badge badge-submitted">' + escHtml((a.assignment_type || "exam").toUpperCase()) + '</span></div>' +
          '<div class="fs-sm text-muted">Assigned to: <strong>' + escHtml(a.target_student_name || "All Enrolled Students") + '</strong> · Questions: ' + (a.question_ids || []).length + ' · Due: ' + escHtml(a.due_date || "Flexible") + '</div>' +
          subsHtml +
        '</div>'
      );
    }).join("");
  });
}

function teacherGradeSubmission(subId) {
  var grade = parseFloat(document.getElementById("tgrade-" + subId).value);
  var comment = document.getElementById("tcomm-" + subId).value.trim();
  apiPost("/api/teacher/submissions/" + subId + "/grade", {
    teacher_grade: isNaN(grade) ? null : grade,
    teacher_comment: comment
  }).then(function (data) {
    if (data && data.ok) {
      showToast("Saved grade & feedback for student!", "success");
      loadTeacherAssignments();
    }
  });
}

// ── CEnT-S Exam Simulator & 3-Button Timer ─────────────────────

function selectMode(mode) {
  STATE.examMode = mode;
  document.querySelectorAll(".mode-card").forEach(function (c) { c.classList.remove("selected"); });
  var card = document.querySelector('[data-mode="' + mode + '"]');
  if (card) card.classList.add("selected");
  var customRow = document.getElementById("custom-options-row");
  if (customRow) customRow.style.display = mode === "custom" ? "block" : "none";
}

function startExamFromLobby() {
  STATE.activeAssignmentId = null;
  var mode = STATE.examMode || "mock1";
  var url = "/api/exam?mode=" + encodeURIComponent(mode);
  if (mode === "custom") {
    var subj = document.getElementById("custom-exam-subject").value;
    var diff = document.getElementById("custom-exam-diff").value;
    var bm = document.getElementById("bookmarked-only-cb").checked;
    if (subj) url += "&subjects=" + encodeURIComponent(subj);
    if (diff && diff !== "All") url += "&difficulty=" + encodeURIComponent(diff);
    if (bm) url += "&bookmarked_only=1";
  }
  var labels = { mock1: "Mock Exam #1", mock2: "Mock Exam #2", mock3: "Mock Exam #3", marathon: "Official Marathon (40 Qs)", custom: "Custom Practice" };
  STATE.examModeLabel = labels[mode] || "Mock Exam";

  apiGet(url).then(function (data) {
    var qs = data.flat_questions || [];
    if (!qs.length) { showToast(data.error || "No matching questions found.", "warning"); return; }
    launchExamWorkspace(qs, mode === "marathon" ? 4800 : 2400);
  });
}

function launchExamWorkspace(questions, durationSecs) {
  STATE.examQuestions = questions;
  STATE.selectedAnswers = {};
  STATE.flaggedQuestions = {};
  STATE.examInitialDuration = durationSecs || 2400;
  STATE.examTimeLeft = STATE.examInitialDuration;

  document.getElementById("exam-lobby").style.display = "none";
  document.getElementById("exam-results").style.display = "none";
  document.getElementById("exam-workspace").style.display = "block";

  renderQuestionCards();
  renderExamPalette();
  updateExamProgress();
  startExamTimer();
}

function getQuestionOptions(q) {
  var letters = ["A", "B", "C", "D", "E"];
  var out = [];
  letters.forEach(function (L) {
    var val = q["option_" + L.toLowerCase()];
    if (val != null && val !== "") out.push({ letter: L, text: val });
  });
  return out;
}

function renderQuestionCards() {
  var container = document.getElementById("question-cards-container");
  container.innerHTML = STATE.examQuestions.map(function (q, idx) {
    var optsHtml = getQuestionOptions(q).map(function (o) {
      return (
        '<li class="option-item" id="opt-' + q.id + '-' + o.letter + '" onclick="selectAnswer(' + q.id + ", '" + o.letter + '\')">' +
          '<span class="option-letter">' + o.letter + '</span>' +
          '<span>' + o.text + '</span>' +
        '</li>'
      );
    }).join("");

    return (
      '<div class="question-card" id="qcard-' + q.id + '">' +
        '<div class="question-header">' +
          '<div><strong>Question ' + (idx + 1) + ' of ' + STATE.examQuestions.length + '</strong> · <span class="text-accent fs-sm fw700">' + escHtml(q.subject) + ' (' + escHtml(q.topic || "General") + ' · ' + escHtml(q.difficulty || "Medium") + ')</span></div>' +
          '<div class="flex-row">' +
            '<button class="btn-sm" id="flag-btn-' + q.id + '" onclick="toggleFlag(' + q.id + ')">🚩 Flag</button>' +
            '<button class="btn-sm" onclick="toggleBookmark(' + q.id + ', this)">⭐ Bookmark</button>' +
            '<button class="btn-sm" onclick="clearAnswer(' + q.id + ')">✕ Clear</button>' +
          '</div>' +
        '</div>' +
        '<div class="question-text">' + q.question_text + '</div>' +
        '<ul class="options-list">' + optsHtml + '</ul>' +
      '</div>'
    );
  }).join("");
  typesetMath(container);
}

function renderExamPalette() {
  var pal = document.getElementById("exam-nav-palette");
  if (!pal) return;
  pal.innerHTML = STATE.examQuestions.map(function (q, idx) {
    var cls = "pal-btn";
    if (STATE.flaggedQuestions[q.id]) cls += " flagged";
    else if (STATE.selectedAnswers[q.id]) cls += " answered";
    return '<button class="' + cls + '" onclick="document.getElementById(\'qcard-' + q.id + '\').scrollIntoView({behavior:\'smooth\'})">' + (idx + 1) + '</button>';
  }).join("");
}

function selectAnswer(qid, letter) {
  if (STATE.selectedAnswers[qid] === letter) { clearAnswer(qid); return; }
  STATE.selectedAnswers[qid] = letter;
  document.getElementById("qcard-" + qid).classList.add("answered");
  ["A", "B", "C", "D", "E"].forEach(function (L) {
    var el = document.getElementById("opt-" + qid + "-" + L);
    if (el) el.classList.toggle("selected", L === letter);
  });
  updateExamProgress();
  renderExamPalette();
}

function clearAnswer(qid) {
  delete STATE.selectedAnswers[qid];
  document.getElementById("qcard-" + qid).classList.remove("answered");
  ["A", "B", "C", "D", "E"].forEach(function (L) {
    var el = document.getElementById("opt-" + qid + "-" + L);
    if (el) el.classList.remove("selected");
  });
  updateExamProgress();
  renderExamPalette();
}

function toggleFlag(qid) {
  if (STATE.flaggedQuestions[qid]) delete STATE.flaggedQuestions[qid];
  else STATE.flaggedQuestions[qid] = true;
  document.getElementById("qcard-" + qid).classList.toggle("flagged", Boolean(STATE.flaggedQuestions[qid]));
  renderExamPalette();
}

function toggleBookmark(qid, btn) {
  apiPost("/api/bookmarks", { question_id: qid, note: "Bookmarked during exam" }).then(function () {
    if (btn) btn.style.borderColor = "var(--warning)";
    showToast("Saved to Mistake Notebook!", "success");
  });
}

function updateExamProgress() {
  var el = document.getElementById("exam-progress-text");
  if (el) el.textContent = Object.keys(STATE.selectedAnswers).length + " / " + STATE.examQuestions.length + " answered";
}

function startExamTimer() {
  clearExamTimer();
  STATE.examPaused = false;
  var el = document.getElementById("exam-timer");
  if (el) el.textContent = formatTime(STATE.examTimeLeft);
  STATE.examTimer = setInterval(function () {
    if (STATE.examPaused) return;
    STATE.examTimeLeft--;
    if (el) el.textContent = formatTime(STATE.examTimeLeft);
    if (STATE.examTimeLeft <= 0) {
      clearExamTimer();
      submitExam();
    }
  }, 1000);
}

function resumeExamTimer() {
  STATE.examPaused = false;
  var btn = document.getElementById("btn-pause-resume");
  if (btn) btn.textContent = "⏸ Pause";
  if (!STATE.examTimer) startExamTimer();
}

function toggleExamPause() {
  STATE.examPaused = !STATE.examPaused;
  var btn = document.getElementById("btn-pause-resume");
  if (btn) btn.textContent = STATE.examPaused ? "▶ Resume" : "⏸ Pause";
}

function resetExamTimer() {
  clearExamTimer();
  STATE.examTimeLeft = STATE.examInitialDuration;
  STATE.examPaused = true;
  var el = document.getElementById("exam-timer");
  if (el) el.textContent = formatTime(STATE.examTimeLeft);
  var btn = document.getElementById("btn-pause-resume");
  if (btn) btn.textContent = "▶ Resume";
  showToast("Exam timer stopped & reset.", "info");
}

function clearExamTimer() {
  if (STATE.examTimer) { clearInterval(STATE.examTimer); STATE.examTimer = null; }
}

function showExamLobby() {
  clearExamTimer();
  document.body.classList.remove("zen-mode");
  document.getElementById("exam-workspace").style.display = "none";
  document.getElementById("exam-results").style.display = "none";
  document.getElementById("exam-lobby").style.display = "block";
  loadLobbyAttempts();
}

function toggleFormulaDrawer() {
  var d = document.getElementById("formula-drawer");
  if (d) { d.classList.toggle("open"); typesetMath(d); }
}

function submitExam() {
  clearExamTimer();
  document.body.classList.remove("zen-mode");
  var qids = STATE.examQuestions.map(function (q) { return q.id; });
  var answers = qids.map(function (id) { return { question_id: id, selected_option: STATE.selectedAnswers[id] || null }; });
  var elapsed = Math.max(0, STATE.examInitialDuration - STATE.examTimeLeft);

  apiPost("/api/exam", {
    exam_mode: STATE.examModeLabel,
    question_ids: qids,
    answers: answers,
    duration_seconds: elapsed
  }).then(function (data) {
    if (STATE.activeAssignmentId && data && data.attempt_id) {
      apiPost("/api/assignments/" + STATE.activeAssignmentId + "/submit", {
        attempt_id: data.attempt_id,
        score: data.total_score,
        max_score: data.max_possible_score
      }).then(function () {
        showToast("Assignment submitted to your instructor!", "success");
        STATE.activeAssignmentId = null;
      });
    }
    renderResults(data);
  });
}

function renderResults(data) {
  document.getElementById("exam-lobby").style.display = "none";
  document.getElementById("exam-workspace").style.display = "none";
  document.getElementById("exam-results").style.display = "block";

  var net = Number(data.total_score || 0).toFixed(2);
  var maxS = data.max_possible_score || STATE.examQuestions.length || 20;
  var c = data.correct != null ? data.correct : (data.correct_count || 0);
  var w = data.wrong != null ? data.wrong : (data.wrong_count || 0);
  var b = data.blank != null ? data.blank : (data.blank_count || 0);
  var tot = c + w + b;

  document.getElementById("results-net-score").textContent = net + " / " + maxS;
  document.getElementById("res-correct").textContent = c;
  document.getElementById("res-wrong").textContent = w;
  document.getElementById("res-blank").textContent = b;
  document.getElementById("res-pct").textContent = (tot ? Math.round((c / tot) * 100) : 0) + "%";

  var whatIf = data.what_if_no_wrong_score != null ? data.what_if_no_wrong_score : c;
  document.getElementById("penalty-desc").innerHTML =
    "Without your <strong>" + w + " wrong guesses</strong> (−0.25 penalty each), your net score would be <strong class='text-success'>" +
    Number(whatIf).toFixed(2) + " pts</strong>. All wrong questions were saved to your Mistake Notebook.";

  var qMap = {};
  STATE.examQuestions.forEach(function (q) { qMap[q.id] = q; });
  var list = document.getElementById("review-list");
  list.innerHTML = (data.feedback || []).map(function (fb, idx) {
    var q = qMap[fb.question_id] || fb;
    var res = fb.result || "blank";
    var cls = res === "correct" ? "correct-item" : (res === "wrong" ? "wrong-item" : "blank-item");
    return (
      '<div class="review-item ' + cls + '">' +
        '<div class="fw700 mb8">Q' + (idx + 1) + ' [' + escHtml(fb.subject || q.subject) + '] — ' + res.toUpperCase() + ' (' + (fb.points_awarded > 0 ? "+" : "") + fb.points_awarded + ' pts)</div>' +
        '<div class="mb8">' + (q.question_text || "") + '</div>' +
        '<div class="fs-sm text-muted mb8">Your Answer: <strong>' + escHtml(fb.selected_option || "Blank") + '</strong> | Correct Option: <strong class="text-success">' + escHtml(fb.correct_option || q.correct_option) + '</strong></div>' +
        (fb.explanation || q.explanation ? '<div class="fs-sm text-muted mb8">💡 ' + (fb.explanation || q.explanation) + '</div>' : '') +
        '<div id="trap-box-' + fb.question_id + '"></div>' +
        '<button class="btn-sm" onclick="askAiTrapExplain(' + fb.question_id + ", '" + (fb.selected_option || "A") + '\')">🤖 Ask AI Tutor Why Option Is a Trap</button>' +
      '</div>'
    );
  }).join("");
  typesetMath(list);
}

function askAiTrapExplain(qid, opt) {
  var box = document.getElementById("trap-box-" + qid);
  if (!box) return;
  box.innerHTML = '<div class="fs-sm text-muted">Consulting AI Tutor...</div>';
  apiPost("/api/ai/explain-trap", { question_id: qid, selected_option: opt }).then(function (d) {
    box.innerHTML =
      '<div class="ai-explanation-box mb8">' +
        '<div><strong>Trap Analysis:</strong> ' + (d.trap_analysis || "") + '</div>' +
        '<div class="mt8"><strong>Core Rule:</strong> ' + (d.core_rule || "") + '</div>' +
        '<div class="mt8 text-warning"><strong>Penalty Strategy:</strong> ' + escHtml(d.penalty_tip || "") + '</div>' +
      '</div>';
    typesetMath(box);
  });
}

function loadLobbyAttempts() {
  var box = document.getElementById("lobby-attempts-box");
  if (!box) return;
  apiGet("/api/attempts").then(function (list) {
    if (!Array.isArray(list) || !list.length) {
      box.innerHTML = '<div class="card-title">My Recent Exam Attempts</div><div class="fs-sm text-muted">No personal attempts recorded yet.</div>';
      return;
    }
    var rows = list.slice(0, 8).map(function (a) {
      return (
        "<tr>" +
          "<td>#" + a.id + "</td>" +
          "<td><strong>" + escHtml(a.exam_mode) + "</strong></td>" +
          "<td class='text-accent fw700'>" + Number(a.total_score).toFixed(2) + " / " + a.max_possible_score + "</td>" +
          "<td class='text-success'>+" + a.correct_count + "</td>" +
          "<td class='text-danger'>-" + a.wrong_count + "</td>" +
          "<td class='text-warning'>" + a.blank_count + "</td>" +
          "<td class='fs-sm text-muted'>" + escHtml((a.timestamp || "").slice(0, 16)) + "</td>" +
          "<td><button class='btn-sm' onclick='reviewPastAttempt(" + a.id + ")'>Review</button></td>" +
        "</tr>"
      );
    }).join("");
    box.innerHTML =
      '<div class="card-title">My Personal Exam Attempts History</div>' +
      '<div class="table-responsive"><table class="data-table"><thead><tr><th>#</th><th>Mode</th><th>Net Score</th><th>Correct</th><th>Wrong</th><th>Blank</th><th>Date</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>';
  });
}

function reviewPastAttempt(id) {
  apiGet("/api/attempts/" + id).then(function (data) {
    var att = data.attempt || data;
    STATE.examQuestions = (data.answers || []).map(function (a) {
      return { id: a.question_id, subject: a.subject, question_text: a.question_text, correct_option: a.correct_option, explanation: a.explanation };
    });
    renderResults({
      total_score: att.total_score,
      max_possible_score: att.max_possible_score,
      correct: att.correct_count,
      wrong: att.wrong_count,
      blank: att.blank_count,
      what_if_no_wrong_score: att.correct_count,
      feedback: data.answers || []
    });
  });
}

// ── Tab 5: AI Question Factory & Bank ──────────────────────────

function generateQuestions() {
  var subject = document.getElementById("gen-subject").value;
  var difficulty = document.getElementById("gen-difficulty").value;
  var count = parseInt(document.getElementById("gen-count").value, 10) || 5;
  var topic = document.getElementById("gen-topic").value.trim() || "General";
  var resEl = document.getElementById("gen-results");
  resEl.innerHTML = '<div class="fs-sm text-muted">Generating questions...</div>';

  apiPost("/api/ai/generate-questions", { subject: subject, topic: topic, difficulty: difficulty, count: count, save_to_db: true }).then(function (data) {
    var qs = data.questions || [];
    STATE.lastGeneratedQuestions = qs;
    resEl.innerHTML =
      '<div class="mb8 fw700 text-success">Generated ' + qs.length + ' new ' + escHtml(subject) + ' questions!</div>' +
      '<button class="btn-success btn-sm" onclick="practiceGeneratedNow()">🚀 Practice These Questions in Simulator</button>';
    loadQuestionBank();
  });
}

function practiceGeneratedNow() {
  if (!STATE.lastGeneratedQuestions.length) return;
  showTab("exam");
  STATE.examModeLabel = "AI Generated Practice";
  launchExamWorkspace(STATE.lastGeneratedQuestions, STATE.lastGeneratedQuestions.length * 120);
}

function notesToExam() {
  var notes = document.getElementById("notes-text").value.trim();
  var subject = document.getElementById("notes-subject").value;
  var resEl = document.getElementById("notes-results");
  if (!notes) { showToast("Paste your study notes first.", "warning"); return; }
  resEl.innerHTML = '<div class="fs-sm text-muted">Converting notes to exam questions...</div>';
  apiPost("/api/ai/notes-to-exam", { notes_text: notes, subject: subject, count: 5, save_to_db: true }).then(function (data) {
    var qs = data.questions || [];
    STATE.lastGeneratedQuestions = qs;
    resEl.innerHTML =
      '<div class="fs-sm text-muted mb8">Keywords: <strong>' + escHtml((data.keywords || []).join(", ")) + '</strong></div>' +
      '<button class="btn-success btn-sm" onclick="practiceGeneratedNow()">🚀 Launch Notes Quiz (' + qs.length + ' Qs)</button>';
    loadQuestionBank();
  });
}

var _bankTimer = null;
function debounceLoadBank() {
  clearTimeout(_bankTimer);
  _bankTimer = setTimeout(function () { STATE.bankOffset = 0; loadQuestionBank(); }, 300);
}

function loadQuestionBank() {
  var subj = document.getElementById("bank-subject-filter").value;
  var diff = document.getElementById("bank-diff-filter").value;
  var search = document.getElementById("bank-search").value.trim();
  var bm = document.getElementById("bank-bookmarked-only").checked;
  var params = new URLSearchParams();
  if (subj) params.set("subject", subj);
  if (diff) params.set("difficulty", diff);
  if (search) params.set("search", search);
  if (bm) params.set("bookmarked_only", "true");

  apiGet("/api/questions?" + params.toString()).then(function (list) {
    STATE.allBankQuestions = Array.isArray(list) ? list : [];
    STATE.bankTotal = STATE.allBankQuestions.length;
    renderBankPage();
  });
}

function exportQuestionBankJSON() {
  var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(STATE.allBankQuestions, null, 2));
  var dlAnchor = document.createElement("a");
  dlAnchor.setAttribute("href", dataStr);
  dlAnchor.setAttribute("download", "cents_question_bank_v4.json");
  document.body.appendChild(dlAnchor);
  dlAnchor.click();
  dlAnchor.remove();
  showToast("Exported Question Bank JSON!", "success");
}

function renderBankPage() {
  var el = document.getElementById("question-bank-list");
  var slice = STATE.allBankQuestions.slice(STATE.bankOffset, STATE.bankOffset + STATE.bankLimit);
  el.innerHTML = slice.map(function (q) {
    var opts = getQuestionOptions(q).map(function (o) {
      return '<div class="fs-sm ' + (o.letter === q.correct_option ? 'text-success fw700' : 'text-muted') + '">' + o.letter + '. ' + o.text + '</div>';
    }).join("");
    return (
      '<div class="review-item">' +
        '<div class="flex-row" style="justify-content:space-between;margin-bottom:6px">' +
          '<span class="fs-sm fw700 text-accent">#' + q.id + ' · ' + escHtml(q.subject) + ' (' + escHtml(q.topic || "General") + ')</span>' +
          '<span class="badge badge-submitted">' + escHtml(q.difficulty) + '</span>' +
        '</div>' +
        '<div class="mb8">' + q.question_text + '</div>' +
        '<details class="fs-sm"><summary style="cursor:pointer;color:var(--accent);font-weight:600">Show Options &amp; Solution</summary><div class="mt8">' + opts + '<div class="mt8 text-muted">💡 ' + (q.explanation || "") + '</div></div></details>' +
      '</div>'
    );
  }).join("") || '<div class="text-muted fs-sm">No questions match your filter.</div>';
  typesetMath(el);

  var info = document.getElementById("bank-page-info");
  if (info) info.textContent = STATE.bankTotal ? (STATE.bankOffset + 1) + "–" + Math.min(STATE.bankOffset + STATE.bankLimit, STATE.bankTotal) + " of " + STATE.bankTotal : "0 questions";
}

function bankPrevPage() { STATE.bankOffset = Math.max(0, STATE.bankOffset - STATE.bankLimit); renderBankPage(); }
function bankNextPage() { if (STATE.bankOffset + STATE.bankLimit < STATE.bankTotal) { STATE.bankOffset += STATE.bankLimit; renderBankPage(); } }

function loadFlashcards(subject) {
  var grid = document.getElementById("flashcard-grid");
  var url = "/api/flashcards" + (subject ? "?subject=" + encodeURIComponent(subject) : "");
  apiGet(url).then(function (cards) {
    grid.innerHTML = (cards || []).map(function (c) {
      return (
        '<div class="flashcard-scene" onclick="this.classList.toggle(\'flipped\')">' +
          '<div class="flashcard-inner">' +
            '<div class="flashcard-front"><div class="fs-sm text-accent mb8">' + escHtml(c.subject) + '</div><div class="fw700">' + c.front_text + '</div></div>' +
            '<div class="flashcard-back"><div>' + c.back_text + '</div></div>' +
          '</div>' +
        '</div>'
      );
    }).join("");
    typesetMath(grid);
  });
}

// ── Tab 6: IELTS Reading Lab & 3-Button Timer ──────────────────

function loadReadingPassages() {
  apiGet("/api/reading").then(function (list) {
    STATE.readingPassages = list || [];
    var sel = document.getElementById("passage-selector");
    sel.innerHTML = STATE.readingPassages.map(function (p) {
      return '<option value="' + p.id + '">' + escHtml(p.title) + '</option>';
    }).join("");
    if (STATE.readingPassages.length) renderPassage(STATE.readingPassages[0].id);
  });
}

function renderPassage(pid) {
  var p = STATE.readingPassages.find(function (x) { return String(x.id) === String(pid); });
  if (!p) return;
  STATE.currentPassage = p;
  document.getElementById("reading-placeholder").style.display = "none";
  document.getElementById("reading-split").style.display = "grid";
  document.getElementById("reading-passage-pane").innerHTML = p.passage_html;

  var qPane = document.getElementById("reading-questions-pane");
  qPane.innerHTML = '<div class="card-title">Comprehension Questions</div>' +
    (p.questions || []).map(function (q, idx) {
      var opts = (q.options || []).map(function (o, oi) {
        var L = String.fromCharCode(65 + oi);
        return '<label style="display:block;margin:5px 0;font-size:0.85rem;cursor:pointer"><input type="radio" name="rq-' + idx + '" value="' + L + '"> <strong>' + L + '.</strong> ' + escHtml(o) + '</label>';
      }).join("");
      return '<div class="mb16"><div class="fw700 fs-sm mb8">' + (idx + 1) + '. ' + escHtml(q.question) + '</div>' + opts + '</div>';
    }).join("") +
    '<button class="btn-primary" style="width:100%" onclick="submitReadingTest()">Submit Reading Answers</button>' +
    '<div id="reading-results" class="mt16"></div>';
}

function startReadingTimer() {
  if (STATE.readingTimer) clearInterval(STATE.readingTimer);
  STATE.readingPaused = false;
  var el = document.getElementById("reading-timer");
  STATE.readingTimer = setInterval(function () {
    if (STATE.readingPaused) return;
    STATE.readingTimeLeft--;
    if (el) el.textContent = formatTime(STATE.readingTimeLeft);
    if (STATE.readingTimeLeft <= 0) { clearInterval(STATE.readingTimer); submitReadingTest(); }
  }, 1000);
}

function pauseReadingTimer() {
  STATE.readingPaused = !STATE.readingPaused;
  document.getElementById("btn-reading-pause").textContent = STATE.readingPaused ? "▶ Resume" : "⏸ Pause";
}

function resetReadingTimer() {
  if (STATE.readingTimer) { clearInterval(STATE.readingTimer); STATE.readingTimer = null; }
  STATE.readingTimeLeft = 1200;
  STATE.readingPaused = false;
  document.getElementById("reading-timer").textContent = "20:00";
  document.getElementById("btn-reading-pause").textContent = "⏸ Pause";
}

function submitReadingTest() {
  if (!STATE.currentPassage) return;
  var answers = {};
  (STATE.currentPassage.questions || []).forEach(function (_, idx) {
    var r = document.querySelector('input[name="rq-' + idx + '"]:checked');
    if (r) answers[String(idx)] = r.value;
  });
  apiPost("/api/reading/grade", { passage_id: STATE.currentPassage.id, answers: answers }).then(function (d) {
    if (STATE.activeAssignmentId) {
      apiPost("/api/assignments/" + STATE.activeAssignmentId + "/submit", {
        score: d.correct,
        max_score: d.total_questions
      }).then(function () {
        showToast("Reading task submitted to your instructor!", "success");
        STATE.activeAssignmentId = null;
      });
    }
    var detailHtml = (d.detail || []).map(function (item, i) {
      return '<div class="fs-sm mt8">' + (item.is_correct ? '✅' : '❌') + ' Q' + (i + 1) + ': Your choice <strong>' + escHtml(item.selected || "Blank") + '</strong> (Correct: <strong class="text-success">' + escHtml(item.correct) + '</strong>) — ' + escHtml(item.explanation || '') + '</div>';
    }).join("");
    document.getElementById("reading-results").innerHTML =
      '<div class="ai-explanation-box"><div class="fw700 text-success">Score: ' + d.correct + ' / ' + d.total_questions + ' (' + d.score_pct + '%) — Estimated Band: ' + d.estimated_band + '</div>' + detailHtml + '</div>';
  });
}

// ── Tab 7: IELTS Writing Studio, Annotated Highlighter & Timer ──

function loadWritingPrompts() {
  apiGet("/api/writing/prompts").then(function (list) {
    STATE.writingPrompts = list || [];
    var sel = document.getElementById("writing-prompt-selector");
    sel.innerHTML = '<option value="">— Custom Writing Prompt —</option>' +
      STATE.writingPrompts.map(function (p) { return '<option value="' + p.id + '">' + escHtml(p.title) + '</option>'; }).join("");
  });
}

function onWritingPromptChange() {
  var pid = document.getElementById("writing-prompt-selector").value;
  var box = document.getElementById("writing-prompt-display");
  var txt = document.getElementById("writing-prompt-text");
  if (!pid) { box.style.display = "none"; return; }
  var p = STATE.writingPrompts.find(function (x) { return String(x.id) === String(pid); });
  if (!p) return;
  document.getElementById("writing-task-type").value = p.task_type === "Task 1" ? "task1" : "task2";
  onTaskTypeChange();
  txt.innerHTML = '<div>' + escHtml(p.prompt_text) + '</div>' + (p.chart_svg_or_table ? '<div class="mt16">' + p.chart_svg_or_table + '</div>' : '');
  box.style.display = "block";
}

function onTaskTypeChange() {
  var t = document.getElementById("writing-task-type").value;
  document.getElementById("word-count-target").textContent = "Target: " + (t === "task1" ? "150+" : "250+") + " words";
  STATE.writingTimeLeft = t === "task1" ? 1200 : 2400;
  document.getElementById("writing-timer").textContent = formatTime(STATE.writingTimeLeft);
  updateWordCount();
}

function updateWordCount() {
  var text = document.getElementById("main-essay-textarea").value.trim();
  var words = text ? text.split(/\s+/).length : 0;
  var target = document.getElementById("writing-task-type").value === "task1" ? 150 : 250;
  document.getElementById("word-count-label").textContent = words + " words";
  var fill = document.getElementById("word-count-fill");
  fill.style.width = Math.min(100, Math.round((words / target) * 100)) + "%";
  fill.style.background = words >= target ? "var(--success)" : "var(--accent)";
}

function startWritingTimer() {
  if (STATE.writingTimer) clearInterval(STATE.writingTimer);
  STATE.writingPaused = false;
  var el = document.getElementById("writing-timer");
  STATE.writingTimer = setInterval(function () {
    if (STATE.writingPaused) return;
    STATE.writingTimeLeft--;
    if (el) el.textContent = formatTime(STATE.writingTimeLeft);
    if (STATE.writingTimeLeft <= 0) { clearInterval(STATE.writingTimer); submitWriting(); }
  }, 1000);
}

function pauseWritingTimer() {
  STATE.writingPaused = !STATE.writingPaused;
  document.getElementById("btn-writing-pause").textContent = STATE.writingPaused ? "▶ Resume" : "⏸ Pause";
}

function resetWritingTimer() {
  if (STATE.writingTimer) { clearInterval(STATE.writingTimer); STATE.writingTimer = null; }
  var t = document.getElementById("writing-task-type").value;
  STATE.writingTimeLeft = t === "task1" ? 1200 : 2400;
  STATE.writingPaused = false;
  document.getElementById("writing-timer").textContent = formatTime(STATE.writingTimeLeft);
  document.getElementById("btn-writing-pause").textContent = "⏸ Pause";
}

function buildAnnotatedEssayHtml(rawText, transitions, repeatedWords) {
  var sents = rawText.split(/(?<=[.!?])\s+/);
  return sents.map(function (s) {
    var isLong = s.trim().split(/\s+/).length > 35;
    var safe = escHtml(s);
    (transitions || []).forEach(function (tr) {
      var re = new RegExp("\\b(" + tr.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")\\b", "gi");
      safe = safe.replace(re, '<span class="hl-transition" title="Academic Discourse Marker">$1</span>');
    });
    (repeatedWords || []).forEach(function (rw) {
      var re = new RegExp("\\b(" + rw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")\\b", "gi");
      safe = safe.replace(re, '<span class="hl-repeated" title="Overused Word (4+ times)">$1</span>');
    });
    return isLong ? '<span class="hl-long-sent" title="Long Sentence (>35 words)">' + safe + '</span>' : safe;
  }).join(" ");
}

function submitWriting() {
  var text = document.getElementById("main-essay-textarea").value.trim();
  if (!text) { showToast("Write your essay first.", "warning"); return; }
  var t = document.getElementById("writing-task-type").value === "task1" ? "Task 1" : "Task 2";
  var pid = document.getElementById("writing-prompt-selector").value || null;
  var fb = document.getElementById("writing-feedback");
  fb.style.display = "block";
  fb.innerHTML = '<div class="card">Evaluating essay...</div>';

  apiPost("/api/writing", { task_type: t, prompt_id: pid, essay_text: text }).then(function (d) {
    if (STATE.activeAssignmentId) {
      apiPost("/api/assignments/" + STATE.activeAssignmentId + "/submit", {
        score: d.estimated_band,
        max_score: 9.0
      }).then(function () {
        showToast("Writing task submitted to your instructor!", "success");
        STATE.activeAssignmentId = null;
      });
    }
    var sub = d.sub_scores || {};
    var annotatedHtml = buildAnnotatedEssayHtml(text, d.transition_words_used || [], d.repeated_words || []);

    fb.innerHTML =
      '<div class="card">' +
        '<div class="card-title"><span>Estimated IELTS Band: <strong class="text-accent" style="font-size:1.5rem">' + d.estimated_band + ' / 9.0</strong></span><span>Words: ' + d.word_count + ' | Paragraphs: ' + d.paragraph_count + '</span></div>' +
        '<div class="stats-grid">' +
          '<div class="stat-card"><div class="stat-label">Task Achievement</div><div class="stat-value">' + (sub.task_achievement || 1) + '</div></div>' +
          '<div class="stat-card"><div class="stat-label">Coherence</div><div class="stat-value">' + (sub.coherence_cohesion || 1) + '</div></div>' +
          '<div class="stat-card"><div class="stat-label">Lexical Resource</div><div class="stat-value">' + (sub.lexical_resource || 1) + '</div></div>' +
          '<div class="stat-card"><div class="stat-label">Grammar Range</div><div class="stat-value">' + (sub.grammatical_range || 1) + '</div></div>' +
        '</div>' +
        '<div class="fs-sm text-muted mb8"><strong>Interactive Annotated Text:</strong> <span class="hl-transition">Green = Discourse Markers</span> · <span class="hl-repeated">Red = Overused Words</span> · <span class="hl-long-sent">Amber Border = Long Sentences (&gt;35w)</span></div>' +
        '<div class="annotated-essay-box">' + annotatedHtml + '</div>' +
        '<ul style="padding-left:18px" class="fs-sm mb16">' + (d.feedback || []).map(function (x) { return '<li>' + escHtml(x) + '</li>'; }).join("") + '</ul>' +
        (d.model_band8_sample ? '<details class="fs-sm"><summary style="cursor:pointer;color:var(--success);font-weight:700">View Band 8.5 Reference Model Answer</summary><div class="ai-explanation-box mt8">' + escHtml(d.model_band8_sample) + '</div></details>' : '') +
      '</div>';
    loadWritingHistory();
  });
}

function upgradeEssay() {
  var text = document.getElementById("main-essay-textarea").value.trim();
  if (!text) { showToast("Write a paragraph first.", "warning"); return; }
  var fb = document.getElementById("writing-feedback");
  fb.style.display = "block";
  apiPost("/api/ai/upgrade-essay", { text: text }).then(function (d) {
    var vocabHtml = (d.vocabulary_upgrades || []).map(function (v) {
      return '<div class="fs-sm mt8"><span class="text-danger">' + escHtml(v.from) + '</span> → <strong class="text-success">' + escHtml(v.to) + '</strong> <span class="text-muted">(' + escHtml(v.reason || '') + ')</span></div>';
    }).join("");
    fb.innerHTML =
      '<div class="card">' +
        '<div class="card-title">✨ Band 8.5 Academic Prose Upgrade</div>' +
        '<div class="ai-explanation-box mb16">' + escHtml(d.upgraded_text || "") + '</div>' +
        (vocabHtml ? '<div class="mb16"><div class="fw700 fs-sm">Lexical Register Enhancements:</div>' + vocabHtml + '</div>' : '') +
        '<div class="fs-sm">' + (d.grammar_tips || []).map(function (t) { return '<div>• ' + escHtml(t) + '</div>'; }).join("") + '</div>' +
      '</div>';
  });
}

function loadWritingHistory() {
  var box = document.getElementById("writing-history-box");
  if (!box) return;
  apiGet("/api/writing/history").then(function (list) {
    if (!Array.isArray(list) || !list.length) {
      box.innerHTML = '<div class="card-title">My Past Writing Submissions</div><div class="fs-sm text-muted">No submissions yet.</div>';
      return;
    }
    box.innerHTML = '<div class="card-title">My Past Writing Submissions</div>' +
      list.slice(0, 5).map(function (w) {
        return '<div class="review-item"><div class="fw700">' + escHtml(w.task_type) + ' — Band <span class="text-accent">' + w.estimated_band + '</span> (' + w.word_count + ' words)</div><div class="fs-sm text-muted">' + escHtml((w.essay_text || "").slice(0, 180)) + '...</div></div>';
      }).join("");
  });
}

// ── Tab 8: Analytics & Uni Cut-off Radar ───────────────────────

function loadAnalytics() {
  Promise.all([apiGet("/api/analytics"), apiGet("/api/leaderboard")]).then(function (res) {
    var an = res[0] || {};
    var lb = res[1] || {};
    var trend = an.overall_trend || [];
    var scores = trend.map(function (t) { return Number(t.total_score || 0); });
    var total = trend.length;
    var avg = total ? scores.reduce(function (a, b) { return a + b; }, 0) / total : 0;
    var best = total ? Math.max.apply(null, scores) : 0;
    var imp = total >= 2 && scores[0] > 0 ? ((scores[scores.length - 1] - scores[0]) / scores[0]) * 100 : 0;

    document.getElementById("stat-total-exams").textContent = total;
    document.getElementById("stat-avg-score").textContent = avg.toFixed(2) + " / 20";
    document.getElementById("stat-best-score").textContent = best.toFixed(2) + " / 20";
    document.getElementById("stat-improvement").textContent = (imp >= 0 ? "+" : "") + imp.toFixed(1) + "%";

    var cutoffs = lb.uni_cutoffs || { "Politecnico di Milano": 16, "Università di Padova": 15, "Università di Bologna": 15.5, "Politecnico di Torino": 15, "Università di Pavia": 14 };
    var uKeys = Object.keys(cutoffs);

    if (STATE.charts.radar) STATE.charts.radar.destroy();
    STATE.charts.radar = new Chart(document.getElementById("radar-chart"), {
      type: "radar",
      data: {
        labels: uKeys,
        datasets: [
          { label: "My Best Score (/20)", data: uKeys.map(function () { return best; }), borderColor: "#6366f1", backgroundColor: "rgba(99,102,241,0.2)" },
          { label: "Admission Cut-off (/20)", data: uKeys.map(function (k) { return cutoffs[k]; }), borderColor: "#10b981", backgroundColor: "rgba(16,185,129,0.08)", borderDash: [5, 5] }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false, scales: { r: { min: 0, max: 20, ticks: { backdropColor: "transparent", color: "#9ca3af" }, pointLabels: { color: "#f9fafb" }, grid: { color: "rgba(255,255,255,0.08)" } } } }
    });

    if (STATE.charts.history) STATE.charts.history.destroy();
    STATE.charts.history = new Chart(document.getElementById("history-chart"), {
      type: "line",
      data: { labels: trend.map(function (t) { return "#" + t.id + " " + t.exam_mode; }), datasets: [{ label: "Net Score", data: scores, borderColor: "#6366f1", fill: true, backgroundColor: "rgba(99,102,241,0.15)", tension: 0.3 }] },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { min: 0, max: 20 } } }
    });

    var subObj = an.subjects || {};
    var sKeys = Object.keys(subObj);
    if (STATE.charts.subject) STATE.charts.subject.destroy();
    STATE.charts.subject = new Chart(document.getElementById("subject-chart"), {
      type: "bar",
      data: { labels: sKeys, datasets: [{ label: "Accuracy %", data: sKeys.map(function (k) { return subObj[k].accuracy || 0; }), backgroundColor: ["#6366f1", "#10b981", "#f59e0b", "#ef4444"] }] },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { min: 0, max: 100 } } }
    });

    var tbody = document.getElementById("leaderboard-tbody");
    tbody.innerHTML = (lb.leaderboard || []).map(function (e, i) {
      return "<tr><td>#" + (i + 1) + "</td><td><strong>" + escHtml(e.name) + "</strong></td><td class='text-accent fw700'>" + Number(e.total_score).toFixed(2) + " / " + e.max_possible_score + "</td><td>" + escHtml(e.target_uni) + "</td></tr>";
    }).join("");
  });
}

// ── Init ───────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", function () {
  initAuth();
  loadLobbyAttempts();
});

// ══════════════════════════════════════════════════════════════
// v5.0 REAL INSTRUCTOR STUDIO, GRADEBOOK, AUTHORING & PROCTORING
// ══════════════════════════════════════════════════════════════

STATE.strictExamMode = false;
STATE.tabSwitchCount = 0;
STATE.gradebookCache = null;

VIEW_TITLES["teacher-authoring"] = "Instructor Portal — Content Authoring Studio";
VIEW_TITLES["teacher-gradebook"] = "Instructor Portal — Master Gradebook Matrix";

// Track tab switches during strict proctored assignments
document.addEventListener("visibilitychange", function () {
  var ws = document.getElementById("exam-workspace");
  if (document.hidden && ws && ws.style.display === "block" && STATE.strictExamMode) {
    STATE.tabSwitchCount = (STATE.tabSwitchCount || 0) + 1;
    showToast("⚠️ Proctoring Alert: Tab switch detected (" + STATE.tabSwitchCount + " recorded for instructor).", "warning");
  }
});

// Hook showTab to load new v5 tabs
var _origShowTab = showTab;
showTab = function (tabId) {
  _origShowTab(tabId);
  if (tabId === "student-assignments") {
    loadAnnouncements();
  } else if (tabId === "teacher-roster") {
    loadClassrooms();
    loadAnnouncements();
  } else if (tabId === "teacher-assignments") {
    populateAssignmentPromptSelectors();
  } else if (tabId === "teacher-gradebook") {
    loadTeacherGradebook();
  }
};

// ── 1. Multi-Classroom & Announcements Logic ───────────────────

function loadClassrooms() {
  var el = document.getElementById("teacher-classrooms-list");
  if (!el) return;
  apiGet("/api/classrooms").then(function (list) {
    if (!Array.isArray(list) || !list.length) {
      el.innerHTML = '<div class="text-muted">No custom cohorts yet.</div>';
      return;
    }
    el.innerHTML = list.map(function (c) {
      return (
        '<div class="flex-row" style="justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)">' +
          '<div><strong>' + escHtml(c.name) + '</strong> <span class="text-muted">(' + escHtml(c.subject) + ')</span></div>' +
          '<div><span class="badge badge-submitted">Code: ' + escHtml(c.invite_code) + '</span></div>' +
        '</div>'
      );
    }).join("");
  });
}

function createClassroom() {
  var name = document.getElementById("new-cls-name").value.trim();
  var subj = document.getElementById("new-cls-subj").value;
  if (!name) { showToast("Enter a cohort/classroom name.", "warning"); return; }
  apiPost("/api/classrooms", { name: name, subject: subj }).then(function (d) {
    if (d && d.ok) {
      document.getElementById("new-cls-name").value = "";
      showToast("Created classroom cohort (" + d.invite_code + ")!", "success");
      loadClassrooms();
    } else {
      showToast(d.error || "Could not create classroom.", "error");
    }
  });
}

function loadAnnouncements() {
  var stEl = document.getElementById("student-announcements-list");
  apiGet("/api/announcements").then(function (list) {
    if (!Array.isArray(list)) return;
    if (stEl) {
      if (!list.length) {
        stEl.innerHTML = '<div class="text-muted fs-sm">No announcements posted yet.</div>';
      } else {
        stEl.innerHTML = list.map(function (a) {
          return (
            '<div class="ai-explanation-box mb8" style="border-left:4px solid var(--accent)">' +
              '<div class="flex-row" style="justify-content:space-between">' +
                '<strong>📢 ' + escHtml(a.title) + '</strong>' +
                '<span class="fs-sm text-muted">' + escHtml(a.teacher_name || "Instructor") + ' · ' + escHtml((a.created_at || "").slice(0, 16)) + '</span>' +
              '</div>' +
              '<div class="fs-sm mt8">' + escHtml(a.content) + '</div>' +
              (a.attachment_url ? '<div class="mt8"><a href="' + escHtml(a.attachment_url) + '" target="_blank" class="fs-sm text-accent fw700">📎 Open Attached Lecture Material / Link →</a></div>' : '') +
            '</div>'
          );
        }).join("");
      }
    }
  });
}

function postAnnouncement() {
  var title = document.getElementById("ann-title").value.trim();
  var content = document.getElementById("ann-content").value.trim();
  var link = document.getElementById("ann-link").value.trim();
  if (!title || !content) { showToast("Enter announcement title and content.", "warning"); return; }
  apiPost("/api/announcements", { title: title, content: content, attachment_url: link }).then(function (d) {
    if (d && d.ok) {
      document.getElementById("ann-title").value = "";
      document.getElementById("ann-content").value = "";
      document.getElementById("ann-link").value = "";
      showToast("Announcement published to student classroom!", "success");
      loadAnnouncements();
    }
  });
}

// ── 2. Enhanced Assignment Builder (Writing/Reading Pickers & Proctoring) ──

function populateAssignmentPromptSelectors() {
  apiGet("/api/writing/prompts").then(function (wList) {
    var wSel = document.getElementById("asgn-writing-prompt-sel");
    if (wSel && Array.isArray(wList)) {
      wSel.innerHTML = wList.map(function (p) {
        return '<option value="' + p.id + '">' + escHtml(p.title) + ' (' + escHtml(p.task_type) + ')</option>';
      }).join("");
    }
  });
  apiGet("/api/reading").then(function (rList) {
    var rSel = document.getElementById("asgn-reading-passage-sel");
    if (rSel && Array.isArray(rList)) {
      rSel.innerHTML = rList.map(function (p) {
        return '<option value="' + p.id + '">' + escHtml(p.title) + '</option>';
      }).join("");
    }
  });
}

onAsgnTypeChange = function () {
  var t = document.getElementById("asgn-type").value;
  var selMode = document.getElementById("asgn-selection-mode").value;
  document.getElementById("asgn-auto-box").style.display = (t === "exam" && selMode === "auto") ? "grid" : "none";
  document.getElementById("asgn-manual-box").style.display = (t === "exam" && selMode === "manual") ? "block" : "none";
  var wBox = document.getElementById("asgn-writing-box");
  var rBox = document.getElementById("asgn-reading-box");
  if (wBox) wBox.style.display = t === "writing" ? "block" : "none";
  if (rBox) rBox.style.display = t === "reading" ? "block" : "none";
  if (t !== "exam") populateAssignmentPromptSelectors();
};

teacherCreateAssignment = function () {
  var title = document.getElementById("asgn-title").value.trim();
  if (!title) { showToast("Please enter an assignment title.", "warning"); return; }
  var t = document.getElementById("asgn-type").value;
  var selMode = document.getElementById("asgn-selection-mode").value;
  var manualIds = Array.from(document.querySelectorAll(".manual-q-cb:checked")).map(function (cb) { return parseInt(cb.value, 10); });
  var strictCb = document.getElementById("asgn-strict-mode");

  var payload = {
    title: title,
    description: document.getElementById("asgn-desc").value.trim(),
    student_id: document.getElementById("asgn-student-select").value ? parseInt(document.getElementById("asgn-student-select").value, 10) : null,
    assignment_type: t,
    subject: document.getElementById("asgn-subject").value,
    difficulty: document.getElementById("asgn-difficulty").value,
    time_limit_mins: parseInt(document.getElementById("asgn-time-limit").value, 10) || 20,
    due_date: document.getElementById("asgn-due-date").value,
    strict_mode: strictCb ? strictCb.checked : true
  };

  if (t === "exam") {
    if (selMode === "manual" && manualIds.length > 0) {
      payload.question_ids = manualIds;
    } else {
      payload.auto_generate_count = parseInt(document.getElementById("asgn-auto-count").value, 10) || 5;
    }
  } else if (t === "writing") {
    var wSel = document.getElementById("asgn-writing-prompt-sel");
    if (wSel && wSel.value) payload.writing_prompt_id = parseInt(wSel.value, 10);
  } else if (t === "reading") {
    var rSel = document.getElementById("asgn-reading-passage-sel");
    if (rSel && rSel.value) payload.reading_passage_id = parseInt(rSel.value, 10);
  }

  apiPost("/api/teacher/assignments", payload).then(function (data) {
    if (data && data.ok) {
      document.getElementById("asgn-title").value = "";
      showToast("Assignment published!", "success");
      loadTeacherAssignments();
    } else {
      showToast(data.error || "Failed to create assignment.", "error");
    }
  });
};

// Override launchAssignedTask to enforce strict proctoring & specific writing/reading prompts
launchAssignedTask = function (asgn) {
  STATE.activeAssignmentId = asgn.id;
  STATE.strictExamMode = Boolean(asgn.strict_mode);
  STATE.tabSwitchCount = 0;

  if (asgn.assignment_type === "writing") {
    showTab("writing");
    setTimeout(function () {
      if (asgn.writing_prompt_id) {
        var sel = document.getElementById("writing-prompt-selector");
        if (sel) { sel.value = String(asgn.writing_prompt_id); onWritingPromptChange(); }
      }
      startWritingTimer();
      showToast("Assigned Writing Task started! Submit when finished.", "info");
    }, 250);
    return;
  }
  if (asgn.assignment_type === "reading") {
    showTab("reading");
    setTimeout(function () {
      if (asgn.reading_passage_id) {
        var sel = document.getElementById("passage-selector");
        if (sel) { sel.value = String(asgn.reading_passage_id); renderPassage(asgn.reading_passage_id); }
      }
      startReadingTimer();
      showToast("Assigned Reading Task started!", "info");
    }, 250);
    return;
  }

  var qids = asgn.question_ids || [];
  var url = qids.length ? "/api/questions?ids=" + qids.join(",") : "/api/exam?mode=mock1";
  apiGet(url).then(function (data) {
    var qs = Array.isArray(data) ? data : (data.flat_questions || []);
    if (!qs.length) { showToast("Could not load assignment questions.", "error"); return; }
    showTab("exam");
    STATE.examMode = "custom";
    STATE.examModeLabel = (STATE.strictExamMode ? "🔒 Proctored Assignment: " : "Assignment: ") + asgn.title;
    launchExamWorkspace(qs, (asgn.time_limit_mins || 20) * 60);
    var pauseBtn = document.getElementById("btn-pause-resume");
    if (pauseBtn) pauseBtn.style.display = STATE.strictExamMode ? "none" : "inline-block";
  });
};

// Override submitExam & submitWriting to include tab_switches & writing_id
submitExam = function () {
  clearExamTimer();
  document.body.classList.remove("zen-mode");
  var pauseBtn = document.getElementById("btn-pause-resume");
  if (pauseBtn) pauseBtn.style.display = "inline-block";

  var qids = STATE.examQuestions.map(function (q) { return q.id; });
  var answers = qids.map(function (id) { return { question_id: id, selected_option: STATE.selectedAnswers[id] || null }; });
  var elapsed = Math.max(0, STATE.examInitialDuration - STATE.examTimeLeft);

  apiPost("/api/exam", {
    exam_mode: STATE.examModeLabel,
    question_ids: qids,
    answers: answers,
    duration_seconds: elapsed
  }).then(function (data) {
    if (STATE.activeAssignmentId && data && data.attempt_id) {
      apiPost("/api/assignments/" + STATE.activeAssignmentId + "/submit", {
        attempt_id: data.attempt_id,
        score: data.total_score,
        max_score: data.max_possible_score,
        tab_switches: STATE.tabSwitchCount || 0
      }).then(function () {
        showToast("Official assignment submitted to instructor!", "success");
        STATE.activeAssignmentId = null;
        STATE.strictExamMode = false;
      });
    }
    renderResults(data);
  });
};

// ── 3. Interactive 2-Column Grading Workbench & Item Analytics ──

loadTeacherAssignments = function () {
  var el = document.getElementById("teacher-assignments-list");
  if (!el) return;
  apiGet("/api/assignments").then(function (list) {
    if (!Array.isArray(list) || !list.length) {
      el.innerHTML = '<div class="text-muted fs-sm">No assignments created yet.</div>';
      return;
    }
    el.innerHTML = list.map(function (a) {
      var subs = a.submissions || [];
      var subsHtml = subs.map(function (s) {
        var tabWarn = s.tab_switches > 0 ? '<span class="badge badge-pending" style="margin-left:6px">⚠️ ' + s.tab_switches + ' Tab Switches</span>' : '';
        return (
          '<div class="ai-explanation-box mt8">' +
            '<div class="flex-row" style="justify-content:space-between">' +
              '<div><strong>' + escHtml(s.student_name) + '</strong> <span class="fs-sm text-muted">(' + escHtml(s.student_email) + ')</span>' + tabWarn + '</div>' +
              '<div class="flex-row">' +
                '<span class="text-accent fw700 fs-sm">Auto: ' + (s.score != null ? s.score + '/' + s.max_score : 'N/A') + '</span>' +
                '<button class="btn-primary btn-sm" onclick="openGradingWorkbench(' + s.id + ')">🔍 Open Grading Workbench</button>' +
              '</div>' +
            '</div>' +
            '<div class="flex-row mt8">' +
              '<input class="form-input" id="tgrade-' + s.id + '" type="number" step="0.5" placeholder="Grade" value="' + (s.teacher_grade != null ? s.teacher_grade : (s.score != null ? s.score : '')) + '" style="max-width:95px" />' +
              '<input class="form-input" id="tcomm-' + s.id + '" placeholder="Quick feedback comment..." value="' + escHtml(s.teacher_comment || '') + '" style="flex:1" />' +
              '<button class="btn-success btn-sm" onclick="teacherGradeSubmission(' + s.id + ')">Save</button>' +
            '</div>' +
          '</div>'
        );
      }).join("") || '<div class="fs-sm text-muted mt8">No student submissions yet.</div>';

      return (
        '<div class="review-item">' +
          '<div class="flex-row" style="justify-content:space-between">' +
            '<div class="fw700">' + escHtml(a.title) + ' <span class="badge badge-submitted">' + escHtml((a.assignment_type || "exam").toUpperCase()) + '</span></div>' +
            (a.assignment_type === "exam" ? '<button class="btn-sm" onclick="openAssignmentItemAnalytics(' + a.id + ')">📊 Class Item Analysis</button>' : '') +
          '</div>' +
          '<div class="fs-sm text-muted mt8">Assigned to: <strong>' + escHtml(a.target_student_name || "All Enrolled Students") + '</strong> · Due: ' + escHtml(a.due_date || "Flexible") + '</div>' +
          subsHtml +
        '</div>'
      );
    }).join("");
  });
};

function openGradingWorkbench(subId) {
  var body = document.getElementById("workbench-body");
  body.innerHTML = '<div class="text-muted">Loading student submission...</div>';
  openModal("grading-workbench-modal");

  apiGet("/api/teacher/submissions/" + subId + "/detail").then(function (d) {
    if (!d || d.error) { body.innerHTML = '<div class="text-danger">' + escHtml(d.error || "Error") + '</div>'; return; }
    document.getElementById("workbench-title").textContent = "Grading Workbench — " + d.student_name + " (" + d.assignment_title + ")";

    var leftHtml = "";
    if (d.writing_detail) {
      var w = d.writing_detail;
      leftHtml =
        '<div class="card" style="margin:0;max-height:68vh;overflow-y:auto">' +
          '<div class="card-title"><span>Student Submitted Essay (' + w.word_count + ' words)</span><span class="badge badge-submitted">AI Band: ' + w.estimated_band + '</span></div>' +
          '<div class="fs-sm text-muted mb8"><strong>Prompt:</strong> ' + escHtml(w.prompt_text) + '</div>' +
          '<div class="annotated-essay-box" style="white-space:pre-wrap">' + escHtml(w.essay_text) + '</div>' +
        '</div>';
    } else if (d.exam_answers && d.exam_answers.length) {
      leftHtml =
        '<div class="card" style="margin:0;max-height:68vh;overflow-y:auto">' +
          '<div class="card-title"><span>Student Exam Paper (' + d.exam_answers.length + ' Questions)</span><span class="badge badge-pending">Tab Switches: ' + (d.tab_switches || 0) + '</span></div>' +
          d.exam_answers.map(function (a, i) {
            var isOk = a.points_awarded > 0;
            var isBlank = !a.selected_option;
            return (
              '<div class="review-item ' + (isOk ? "correct-item" : (isBlank ? "blank-item" : "wrong-item")) + '">' +
                '<div class="fw700 fs-sm">Q' + (i + 1) + ' [' + escHtml(a.subject) + '] — Student Picked: <strong>' + escHtml(a.selected_option || "Blank") + '</strong> | Correct: <strong class="text-success">' + escHtml(a.correct_option) + '</strong> (' + a.points_awarded + ' pts)</div>' +
                '<div class="fs-sm mt8">' + a.question_text + '</div>' +
              '</div>'
            );
          }).join("") +
        '</div>';
    } else {
      leftHtml = '<div class="card"><div class="text-muted">Auto Score: ' + d.score + ' / ' + d.max_score + '</div></div>';
    }

    var rub = d.rubric || {};
    var rightHtml =
      '<div class="card" style="margin:0">' +
        '<div class="card-title">Instructor Evaluation &amp; Rubric</div>' +
        '<div class="fs-sm text-muted mb16">Student: <strong>' + escHtml(d.student_name) + '</strong> · Auto Score: <strong class="text-accent">' + (d.score != null ? d.score + ' / ' + d.max_score : 'N/A') + '</strong></div>' +
        '<div class="inline-grid-3 mb16">' +
          '<div><label class="form-label">Accuracy / TA</label><input class="form-input" type="number" step="0.5" id="wb-r-ta" value="' + (rub.ta || 7.5) + '" /></div>' +
          '<div><label class="form-label">Method / CC</label><input class="form-input" type="number" step="0.5" id="wb-r-cc" value="' + (rub.cc || 7.5) + '" /></div>' +
          '<div><label class="form-label">Rigor / LR</label><input class="form-input" type="number" step="0.5" id="wb-r-lr" value="' + (rub.lr || 7.5) + '" /></div>' +
        '</div>' +
        '<div class="form-group">' +
          '<label class="form-label">Final Instructor Grade (out of ' + (d.max_score || 20) + ')</label>' +
          '<input class="form-input" type="number" step="0.25" id="wb-final-grade" value="' + (d.teacher_grade != null ? d.teacher_grade : (d.score != null ? d.score : '')) + '" />' +
        '</div>' +
        '<div class="form-group">' +
          '<label class="form-label">Detailed Line-by-Line Instructor Feedback</label>' +
          '<textarea class="form-textarea" id="wb-comment" rows="5" placeholder="Write constructive feedback for the student...">' + escHtml(d.teacher_comment || '') + '</textarea>' +
        '</div>' +
        '<button class="btn-success" style="width:100%" onclick="saveWorkbenchGrade(' + d.id + ')">✓ Publish Official Grade &amp; Feedback to Student</button>' +
      '</div>';

    body.innerHTML = leftHtml + rightHtml;
    typesetMath(body);
  });
}

function saveWorkbenchGrade(subId) {
  var grade = parseFloat(document.getElementById("wb-final-grade").value);
  var comment = document.getElementById("wb-comment").value.trim();
  var rubric = {
    ta: parseFloat(document.getElementById("wb-r-ta").value) || 0,
    cc: parseFloat(document.getElementById("wb-r-cc").value) || 0,
    lr: parseFloat(document.getElementById("wb-r-lr").value) || 0
  };
  apiPost("/api/teacher/submissions/" + subId + "/grade", {
    teacher_grade: isNaN(grade) ? null : grade,
    teacher_comment: comment,
    rubric: rubric
  }).then(function (d) {
    if (d && d.ok) {
      showToast("Official evaluation published!", "success");
      closeModal("grading-workbench-modal");
      loadTeacherAssignments();
      if (STATE.currentTab === "teacher-gradebook") loadTeacherGradebook();
    }
  });
}

function openAssignmentItemAnalytics(asgnId) {
  var body = document.getElementById("item-analytics-body");
  body.innerHTML = '<div class="text-muted">Computing class item matrix...</div>';
  openModal("item-analytics-modal");

  apiGet("/api/teacher/assignments/" + asgnId + "/analytics").then(function (d) {
    document.getElementById("item-analytics-title").textContent = "Item-Level Class Accuracy — " + (d.title || "Assignment");
    var items = d.items || [];
    if (!items.length) {
      body.innerHTML = '<div class="text-muted">No question items in this assignment.</div>';
      return;
    }
    body.innerHTML =
      '<div class="fs-sm text-muted mb16">Total Student Attempts Analyzed: <strong>' + (d.submission_count || 0) + '</strong>. Questions with accuracy below 50% are flagged in red for classroom review.</div>' +
      items.map(function (it, idx) {
        var low = it.accuracy_pct < 50;
        return (
          '<div class="review-item ' + (low ? "wrong-item" : "correct-item") + '">' +
            '<div class="flex-row" style="justify-content:space-between">' +
              '<strong>Q' + (idx + 1) + ' (#' + it.question_id + ' · ' + escHtml(it.subject) + ' — ' + escHtml(it.topic) + ')</strong>' +
              '<span class="badge ' + (low ? "badge-pending" : "badge-graded") + '">Class Accuracy: ' + it.accuracy_pct + '% (' + it.correct_count + '/' + it.total_responses + ')</span>' +
            '</div>' +
            '<div class="fs-sm mt8">' + it.question_text + '</div>' +
            '<div class="fs-sm text-muted mt8">Correct Option: <strong class="text-success">' + it.correct_option + '</strong> · Wrong: ' + it.wrong_count + ' · Blank: ' + it.blank_count + '</div>' +
          '</div>'
        );
      }).join("");
    typesetMath(body);
  });
}

// ── 4. Content Authoring Studio Logic ──────────────────────────

function authorSaveQuestion() {
  var payload = {
    subject: document.getElementById("auth-q-subj").value,
    topic: document.getElementById("auth-q-topic").value.trim(),
    difficulty: document.getElementById("auth-q-diff").value,
    question_text: document.getElementById("auth-q-text").value.trim(),
    option_a: document.getElementById("auth-q-a").value.trim(),
    option_b: document.getElementById("auth-q-b").value.trim(),
    option_c: document.getElementById("auth-q-c").value.trim(),
    option_d: document.getElementById("auth-q-d").value.trim(),
    option_e: document.getElementById("auth-q-e").value.trim(),
    correct_option: document.getElementById("auth-q-correct").value,
    explanation: document.getElementById("auth-q-expl").value.trim()
  };
  apiPost("/api/teacher/author/question", payload).then(function (d) {
    if (d && d.ok) {
      document.getElementById("auth-q-text").value = "";
      showToast("Custom question #" + d.id + " added to question bank!", "success");
    } else {
      showToast(d.error || "Please fill in question and all 5 options.", "error");
    }
  });
}

function authorSaveWritingPrompt() {
  var payload = {
    task_type: document.getElementById("auth-w-type").value,
    title: document.getElementById("auth-w-title").value.trim(),
    prompt_text: document.getElementById("auth-w-text").value.trim(),
    chart_svg_or_table: document.getElementById("auth-w-chart").value.trim()
  };
  apiPost("/api/teacher/author/writing-prompt", payload).then(function (d) {
    if (d && d.ok) {
      document.getElementById("auth-w-title").value = "";
      document.getElementById("auth-w-text").value = "";
      showToast("Custom IELTS Writing Prompt saved!", "success");
    } else {
      showToast(d.error || "Title and prompt required.", "error");
    }
  });
}

function authorSaveReadingPassage() {
  var title = document.getElementById("auth-r-title").value.trim();
  var topic = document.getElementById("auth-r-topic").value.trim();
  var text = document.getElementById("auth-r-text").value.trim();
  var q1 = document.getElementById("auth-r-q1").value.trim() || "What is the main focus of the passage?";
  var a = document.getElementById("auth-r-q1a").value.trim() || "Historical background";
  var b = document.getElementById("auth-r-q1b").value.trim() || "Unrelated theory";
  var c = document.getElementById("auth-r-q1c").value.trim() || "Core scientific mechanism";

  var questions = [
    { question: q1, options: [a, b, c, "None of the above", "All of the above"], correct: "C", explanation: "Option C directly reflects the passage thesis." }
  ];
  apiPost("/api/teacher/author/reading-passage", {
    title: title,
    topic: topic,
    passage_html: text,
    questions: questions
  }).then(function (d) {
    if (d && d.ok) {
      document.getElementById("auth-r-title").value = "";
      document.getElementById("auth-r-text").value = "";
      showToast("Custom Reading Passage saved!", "success");
    } else {
      showToast(d.error || "Fill in passage title and text.", "error");
    }
  });
}

// ── 5. Master Gradebook Matrix & CSV Export ────────────────────

function loadTeacherGradebook() {
  var container = document.getElementById("gradebook-matrix-container");
  if (!container) return;
  apiGet("/api/teacher/gradebook").then(function (d) {
    STATE.gradebookCache = d;
    var asgns = d.assignments || [];
    var students = d.students || [];
    if (!students.length) {
      container.innerHTML = '<div class="text-muted fs-sm">No students enrolled yet.</div>';
      return;
    }
    var ths = asgns.map(function (a) {
      return "<th>" + escHtml(a.title) + "<div class='fs-sm text-muted'>" + escHtml(a.assignment_type.toUpperCase()) + "</div></th>";
    }).join("");

    var rows = students.map(function (st) {
      var cells = asgns.map(function (a) {
        var g = (st.grades || {})[String(a.id)] || { status: "pending", final_display: "—" };
        if (g.submission_id) {
          var cls = g.status === "graded" ? "text-success fw700" : "text-accent fw700";
          return '<td><button class="btn-sm ' + cls + '" onclick="openGradingWorkbench(' + g.submission_id + ')">' + escHtml(g.final_display) + ' 🔍</button></td>';
        }
        return '<td class="text-muted">—</td>';
      }).join("");
      return (
        "<tr>" +
          "<td><strong>" + escHtml(st.name) + "</strong><div class='fs-sm text-muted'>" + escHtml(st.email) + "</div></td>" +
          "<td>" + escHtml(st.target_uni) + "</td>" +
          cells +
          "<td class='fw700 text-accent'>" + st.overall_avg_pct + "%</td>" +
        "</tr>"
      );
    }).join("");

    container.innerHTML =
      '<table class="data-table">' +
        '<thead><tr><th>Student</th><th>Target Uni</th>' + ths + '<th>Overall Avg</th></tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
      '</table>';
  });
}

function exportGradebookCSV() {
  var d = STATE.gradebookCache;
  if (!d || !d.students) { showToast("Load gradebook first.", "warning"); return; }
  var asgns = d.assignments || [];
  var headers = ["Student Name", "Email", "Target University"].concat(asgns.map(function (a) { return a.title; })).concat(["Overall Avg %"]);
  var csvRows = [headers.join(",")];

  d.students.forEach(function (st) {
    var row = [
      '"' + (st.name || "").replace(/"/g, '""') + '"',
      '"' + (st.email || "") + '"',
      '"' + (st.target_uni || "") + '"'
    ];
    asgns.forEach(function (a) {
      var g = (st.grades || {})[String(a.id)] || {};
      row.push('"' + (g.final_display || "Pending") + '"');
    });
    row.push(st.overall_avg_pct + "%");
    csvRows.push(row.join(","));
  });

  var blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a");
  a.href = url;
  a.download = "classroom_gradebook_v5.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast("Exported Master Gradebook to CSV!", "success");
}


// ══════════════════════════════════════════════════════════════
// v6.0 PRODUCTION PATCH: STRICT KEY LOCK, MULTI-READING & BULK IMPORT
// ══════════════════════════════════════════════════════════════

STATE.lastSubmittedWasStrictAssignment = false;

// 1. Lock Answer Key on Strict Proctored Assignments until Instructor Grades It
var _v5SubmitExam = submitExam;
submitExam = function () {
  STATE.lastSubmittedWasStrictAssignment = Boolean(STATE.activeAssignmentId && STATE.strictExamMode);
  _v5SubmitExam();
};

var _v5RenderResults = renderResults;
renderResults = function (data) {
  _v5RenderResults(data);
  if (STATE.lastSubmittedWasStrictAssignment) {
    var list = document.getElementById("review-list");
    if (list) {
      list.innerHTML =
        '<div class="ai-explanation-box" style="border-left:4px solid var(--warning);padding:18px">' +
          '<div class="fw700 text-warning mb8">🔒 Proctored Classroom Assignment — Answer Key Locked</div>' +
          '<div class="fs-sm text-muted">To protect exam integrity while other students are still testing, the step-by-step solutions and answer key are hidden until your instructor reviews and releases your grade in <strong>My Classroom &amp; Tasks</strong>.</div>' +
        '</div>';
    }
    STATE.lastSubmittedWasStrictAssignment = false;
  }
};

// 2. Dynamic Multi-Question Reading Builder for Instructors
var _authorReadingQIndex = 0;

function addAuthorReadingQuestionRow() {
  var container = document.getElementById("auth-r-questions-container");
  if (!container) return;
  _authorReadingQIndex++;
  var idx = _authorReadingQIndex;
  var div = document.createElement("div");
  div.className = "review-item auth-rq-block mb8";
  div.innerHTML =
    '<div class="flex-row mb8" style="justify-content:space-between">' +
      '<strong class="fs-sm text-accent">Reading Question #' + idx + '</strong>' +
      '<button type="button" class="btn-sm text-danger" onclick="this.closest(\'.auth-rq-block\').remove()">✕ Remove</button>' +
    '</div>' +
    '<input class="form-input mb8 rq-stem" placeholder="Question stem..." />' +
    '<div class="inline-grid-3 mb8">' +
      '<input class="form-input rq-opt-a" placeholder="Option A" />' +
      '<input class="form-input rq-opt-b" placeholder="Option B" />' +
      '<input class="form-input rq-opt-c" placeholder="Option C" />' +
      '<input class="form-input rq-opt-d" placeholder="Option D" />' +
      '<input class="form-input rq-opt-e" placeholder="Option E" />' +
      '<select class="form-select rq-correct">' +
        '<option value="A">Correct: A</option>' +
        '<option value="B">Correct: B</option>' +
        '<option value="C" selected>Correct: C</option>' +
        '<option value="D">Correct: D</option>' +
        '<option value="E">Correct: E</option>' +
      '</select>' +
    '</div>' +
    '<input class="form-input rq-expl" placeholder="Explanation / Paragraph evidence reference..." />';
  container.appendChild(div);
}

authorSaveReadingPassage = function () {
  var title = document.getElementById("auth-r-title").value.trim();
  var topic = document.getElementById("auth-r-topic").value.trim() || "Academic";
  var text = document.getElementById("auth-r-text").value.trim();
  var blocks = document.querySelectorAll(".auth-rq-block");
  var questions = [];

  blocks.forEach(function (b) {
    var stem = b.querySelector(".rq-stem").value.trim();
    var oa = b.querySelector(".rq-opt-a").value.trim() || "Option A";
    var ob = b.querySelector(".rq-opt-b").value.trim() || "Option B";
    var oc = b.querySelector(".rq-opt-c").value.trim() || "Option C";
    var od = b.querySelector(".rq-opt-d").value.trim() || "Option D";
    var oe = b.querySelector(".rq-opt-e").value.trim() || "Option E";
    var corr = b.querySelector(".rq-correct").value || "C";
    var expl = b.querySelector(".rq-expl").value.trim() || "Refer to passage evidence.";
    if (stem) {
      questions.push({
        question: stem,
        options: [oa, ob, oc, od, oe],
        correct: corr,
        explanation: expl
      });
    }
  });

  if (!title || !text || !questions.length) {
    showToast("Please provide a passage title, text, and at least 1 question.", "warning");
    return;
  }

  apiPost("/api/teacher/author/reading-passage", {
    title: title,
    topic: topic,
    passage_html: text,
    questions: questions
  }).then(function (d) {
    if (d && d.ok) {
      document.getElementById("auth-r-title").value = "";
      document.getElementById("auth-r-text").value = "";
      document.getElementById("auth-r-questions-container").innerHTML = "";
      _authorReadingQIndex = 0;
      addAuthorReadingQuestionRow();
      showToast("Saved Reading Passage with " + questions.length + " questions!", "success");
    } else {
      showToast(d.error || "Failed to save passage.", "error");
    }
  });
};

// Initialize 2 default question rows in Reading Authoring Studio
document.addEventListener("DOMContentLoaded", function () {
  var c = document.getElementById("auth-r-questions-container");
  if (c && c.children.length === 0) {
    addAuthorReadingQuestionRow();
    addAuthorReadingQuestionRow();
  }
});

// 3. Bulk JSON Question Import Handler
function handleBulkJsonImport(inputEl) {
  var file = inputEl.files && inputEl.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function (e) {
    try {
      var parsed = JSON.parse(e.target.result);
      apiPost("/api/teacher/author/import-json", { questions: parsed }).then(function (d) {
        if (d && d.ok) {
          showToast("Successfully imported " + d.imported_count + " questions into bank!", "success");
          loadQuestionBank();
        } else {
          showToast(d.error || "Import failed.", "error");
        }
      });
    } catch (err) {
      showToast("Invalid JSON file format.", "error");
    }
    inputEl.value = "";
  };
  reader.readAsText(file);
}
