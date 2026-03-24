const state = {
  summary: {},
  students: [],
  teachers: [],
  fees: [],
  papers: [],
  paperScores: [],
  parents: [],
  announcements: [],
  books: [],
  issues: [],
  rooms: [],
  allocations: [],
  hifz: [],
  incidents: [],
  timetable: [],
};

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function byId(id) {
  return document.getElementById(id);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch (_) {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload;
}

function setStatus(elId, text, isError = false) {
  const el = byId(elId);
  if (!el) return;
  el.textContent = text || "";
  el.className = `status ${isError ? "err" : "ok"}`;
}

function renderSummary() {
  byId("sum_students").textContent = String(state.summary.students || 0);
  byId("sum_teachers").textContent = String(state.summary.teachers || 0);
  byId("sum_parents").textContent = String(state.summary.parents || 0);
  byId("sum_fee_balance").textContent = String(state.summary.pending_fee_balance || 0);
  byId("sum_attendance").textContent = `${state.summary.today_attendance_present || 0} / ${state.summary.today_attendance_total || 0}`;
  byId("sum_library").textContent = String(state.summary.library_issued_books || 0);
}

function studentOptions() {
  return state.students
    .map((s) => `<option value="${s.id}">${esc(s.full_name)} (${esc(s.admission_no)})</option>`)
    .join("");
}

function teacherOptions() {
  return state.teachers
    .map((t) => `<option value="${t.id}">${esc(t.full_name)} (${esc(t.employee_no)})</option>`)
    .join("");
}

function feeOptions() {
  return state.fees
    .map((f) => `<option value="${f.id}">${esc(f.full_name)} - ${esc(f.category)} (${Number(f.balance || 0).toFixed(2)})</option>`)
    .join("");
}

function paperOptions() {
  return state.papers
    .map((p) => `<option value="${p.id}">${esc(p.title)} (${esc(p.class_name)})</option>`)
    .join("");
}

function bookOptions() {
  return state.books
    .map((b) => `<option value="${b.id}">${esc(b.title)} (${esc(b.book_code)})</option>`)
    .join("");
}

function roomOptions() {
  return state.rooms
    .map((r) => `<option value="${r.id}">${esc(r.room_code)} (${r.occupied}/${r.capacity})</option>`)
    .join("");
}

function refreshSelectors() {
  const sopts = studentOptions();
  [
    "fee_student_id",
    "attendance_student_id",
    "paper_score_student_id",
    "parent_student_id",
    "report_student_id",
    "book_issue_student_id",
    "hostel_student_id",
    "hifz_student_id",
    "incident_student_id",
  ].forEach((id) => {
    const el = byId(id);
    if (el) el.innerHTML = sopts || '<option value="">No students</option>';
  });

  const topts = teacherOptions();
  const teacherSelect = byId("attendance_teacher_id");
  if (teacherSelect) teacherSelect.innerHTML = topts || '<option value="">No teachers</option>';

  const fopts = feeOptions();
  const feePaySelect = byId("fee_pay_id");
  if (feePaySelect) feePaySelect.innerHTML = fopts || '<option value="">No fee records</option>';

  const popts = paperOptions();
  const paperSelect = byId("paper_score_paper_id");
  if (paperSelect) paperSelect.innerHTML = popts || '<option value="">No papers</option>';

  const bopts = bookOptions();
  const bookSelect = byId("book_issue_book_id");
  if (bookSelect) bookSelect.innerHTML = bopts || '<option value="">No books</option>';

  const ropts = roomOptions();
  const roomSelect = byId("hostel_room_id");
  if (roomSelect) roomSelect.innerHTML = ropts || '<option value="">No rooms</option>';
}

function renderStudents() {
  const body = byId("students_table");
  if (!state.students.length) {
    body.innerHTML = '<tr><td colspan="7" class="small">No students yet.</td></tr>';
    refreshSelectors();
    return;
  }
  body.innerHTML = state.students
    .map(
      (s) => `<tr>
      <td>${esc(s.admission_no)}</td>
      <td>${esc(s.full_name)}</td>
      <td>${esc(s.class_name)}</td>
      <td>${esc(s.section_name)}</td>
      <td>${esc(s.guardian_name)}</td>
      <td>${esc(s.guardian_phone)}</td>
      <td>${esc(s.status)}</td>
    </tr>`
    )
    .join("");
  refreshSelectors();
}

function renderTeachers() {
  const body = byId("teachers_table");
  if (!state.teachers.length) {
    body.innerHTML = '<tr><td colspan="5" class="small">No teachers yet.</td></tr>';
    refreshSelectors();
    return;
  }
  body.innerHTML = state.teachers
    .map(
      (t) => `<tr>
      <td>${esc(t.employee_no)}</td>
      <td>${esc(t.full_name)}</td>
      <td>${esc(t.subject)}</td>
      <td>${esc(t.phone)}</td>
      <td>${esc(t.status)}</td>
    </tr>`
    )
    .join("");
  refreshSelectors();
}

function renderFees() {
  const body = byId("fees_table");
  if (!state.fees.length) {
    body.innerHTML = '<tr><td colspan="8" class="small">No fee records yet.</td></tr>';
    refreshSelectors();
    return;
  }
  body.innerHTML = state.fees
    .map(
      (f) => `<tr>
      <td>${f.id}</td>
      <td>${esc(f.full_name)}</td>
      <td>${esc(f.fee_month)}</td>
      <td>${esc(f.category)}</td>
      <td>${Number(f.amount).toFixed(2)}</td>
      <td>${Number(f.paid_amount).toFixed(2)}</td>
      <td>${Number(f.balance).toFixed(2)}</td>
      <td>${esc(f.status)}</td>
    </tr>`
    )
    .join("");
  refreshSelectors();
}

function renderAttendance() {
  const body = byId("attendance_table");
  if (!state.studentAttendance?.length) {
    body.innerHTML = '<tr><td colspan="5" class="small">No attendance data yet.</td></tr>';
    return;
  }
  body.innerHTML = state.studentAttendance
    .map(
      (a) => `<tr>
      <td>${esc(a.day)}</td>
      <td>${esc(a.admission_no)}</td>
      <td>${esc(a.full_name)}</td>
      <td>${a.present ? "Present" : "Absent"}</td>
      <td>${esc(a.remark || "")}</td>
    </tr>`
    )
    .join("");
}

function renderTeacherAttendance() {
  const body = byId("teacher_attendance_table");
  if (!state.teacherAttendance?.length) {
    body.innerHTML = '<tr><td colspan="5" class="small">No teacher attendance data yet.</td></tr>';
    return;
  }
  body.innerHTML = state.teacherAttendance
    .map(
      (a) => `<tr>
      <td>${esc(a.day)}</td>
      <td>${esc(a.employee_no)}</td>
      <td>${esc(a.full_name)}</td>
      <td>${a.present ? "Present" : "Absent"}</td>
      <td>${esc(a.remark || "")}</td>
    </tr>`
    )
    .join("");
}

function renderPapers() {
  const body = byId("papers_table");
  if (!state.papers.length) {
    body.innerHTML = '<tr><td colspan="6" class="small">No papers created yet.</td></tr>';
    refreshSelectors();
    return;
  }
  body.innerHTML = state.papers
    .map(
      (p) => `<tr>
      <td>${p.id}</td>
      <td>${esc(p.title)}</td>
      <td>${esc(p.subject)}</td>
      <td>${esc(p.class_name)}</td>
      <td>${esc(p.term_name)}</td>
      <td>${p.max_marks}</td>
    </tr>`
    )
    .join("");
  refreshSelectors();
}

function renderPaperScores() {
  const body = byId("paper_scores_table");
  if (!state.paperScores.length) {
    body.innerHTML = '<tr><td colspan="4" class="small">No paper scores yet.</td></tr>';
    return;
  }
  body.innerHTML = state.paperScores
    .map(
      (s) => `<tr>
      <td>${esc(s.admission_no)}</td>
      <td>${esc(s.full_name)}</td>
      <td>${Number(s.marks).toFixed(2)}</td>
      <td>${esc(s.remarks || "")}</td>
    </tr>`
    )
    .join("");
}

function renderParents() {
  const body = byId("parents_table");
  if (!state.parents.length) {
    body.innerHTML = '<tr><td colspan="6" class="small">No parent links yet.</td></tr>';
    return;
  }
  body.innerHTML = state.parents
    .map(
      (p) => `<tr>
      <td>${esc(p.username)}</td>
      <td>${esc(p.parent_name)}</td>
      <td>${esc(p.phone)}</td>
      <td>${esc(p.student_name)}</td>
      <td>${esc(p.admission_no)}</td>
      <td>${esc(p.relation)}</td>
    </tr>`
    )
    .join("");
}

function renderAnnouncements() {
  const body = byId("announcements_table");
  if (!state.announcements.length) {
    body.innerHTML = '<tr><td colspan="4" class="small">No announcements yet.</td></tr>';
    return;
  }
  body.innerHTML = state.announcements
    .map(
      (a) => `<tr>
      <td>${a.id}</td>
      <td>${esc(a.title)}</td>
      <td>${esc(a.target_group)}</td>
      <td>${esc(a.created_at)}</td>
    </tr>`
    )
    .join("");
}

function renderBooks() {
  const body = byId("books_table");
  if (!state.books.length) {
    body.innerHTML = '<tr><td colspan="6" class="small">No books yet.</td></tr>';
    refreshSelectors();
    return;
  }
  body.innerHTML = state.books
    .map(
      (b) => `<tr>
      <td>${esc(b.book_code)}</td>
      <td>${esc(b.title)}</td>
      <td>${esc(b.author)}</td>
      <td>${esc(b.category)}</td>
      <td>${b.total_copies}</td>
      <td>${b.available_copies}</td>
    </tr>`
    )
    .join("");
  refreshSelectors();
}

function renderIssues() {
  const body = byId("issues_table");
  if (!state.issues.length) {
    body.innerHTML = '<tr><td colspan="8" class="small">No issue logs yet.</td></tr>';
    return;
  }
  body.innerHTML = state.issues
    .map(
      (i) => `<tr>
      <td>${i.id}</td>
      <td>${esc(i.book_title)}</td>
      <td>${esc(i.student_name)}</td>
      <td>${esc(i.issued_on)}</td>
      <td>${esc(i.due_on)}</td>
      <td>${esc(i.returned_on || "-")}</td>
      <td>${esc(i.status)}</td>
      <td>${i.status === "issued" ? `<button data-return-issue="${i.id}">Return</button>` : ""}</td>
    </tr>`
    )
    .join("");
  body.querySelectorAll("button[data-return-issue]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await requestJson(`/api/library/issues/${btn.dataset.returnIssue}/return`, { method: "POST" });
        await loadLibrary();
        setStatus("library_status", "Book returned.");
      } catch (err) {
        setStatus("library_status", err.message, true);
      }
    });
  });
}

function renderRooms() {
  const body = byId("rooms_table");
  if (!state.rooms.length) {
    body.innerHTML = '<tr><td colspan="3" class="small">No hostel rooms yet.</td></tr>';
    refreshSelectors();
    return;
  }
  body.innerHTML = state.rooms
    .map(
      (r) => `<tr>
      <td>${esc(r.room_code)}</td>
      <td>${r.capacity}</td>
      <td>${r.occupied}</td>
    </tr>`
    )
    .join("");
  refreshSelectors();
}

function renderAllocations() {
  const body = byId("allocations_table");
  if (!state.allocations.length) {
    body.innerHTML = '<tr><td colspan="5" class="small">No hostel allocations yet.</td></tr>';
    return;
  }
  body.innerHTML = state.allocations
    .map(
      (a) => `<tr>
      <td>${esc(a.room_code)}</td>
      <td>${esc(a.student_name)}</td>
      <td>${esc(a.start_on)}</td>
      <td>${esc(a.end_on || "-")}</td>
      <td>${esc(a.status)}</td>
    </tr>`
    )
    .join("");
}

function renderHifz() {
  const body = byId("hifz_table");
  if (!state.hifz.length) {
    body.innerHTML = '<tr><td colspan="7" class="small">No hifz logs yet.</td></tr>';
    return;
  }
  body.innerHTML = state.hifz
    .map(
      (h) => `<tr>
      <td>${esc(h.student_name)}</td>
      <td>${esc(h.surah_name)}</td>
      <td>${h.para_no}</td>
      <td>${h.ayat_from}</td>
      <td>${h.ayat_to}</td>
      <td>${esc(h.revision_grade || "-")}</td>
      <td>${esc(h.teacher_name || "-")}</td>
    </tr>`
    )
    .join("");
}

function renderIncidents() {
  const body = byId("incidents_table");
  if (!state.incidents.length) {
    body.innerHTML = '<tr><td colspan="6" class="small">No incidents yet.</td></tr>';
    return;
  }
  body.innerHTML = state.incidents
    .map(
      (i) => `<tr>
      <td>${esc(i.student_name)}</td>
      <td>${esc(i.category)}</td>
      <td>${esc(i.description)}</td>
      <td>${esc(i.action_taken || "-")}</td>
      <td>${esc(i.reported_by)}</td>
      <td>${esc(i.incident_on)}</td>
    </tr>`
    )
    .join("");
}

function renderTimetable() {
  const body = byId("timetable_table");
  if (!state.timetable.length) {
    body.innerHTML = '<tr><td colspan="7" class="small">No timetable entries yet.</td></tr>';
    return;
  }
  body.innerHTML = state.timetable
    .map(
      (t) => `<tr>
      <td>${esc(t.class_name)}</td>
      <td>${esc(t.day_name)}</td>
      <td>${t.period_no}</td>
      <td>${esc(t.subject)}</td>
      <td>${esc(t.teacher_name || "-")}</td>
      <td>${esc(t.start_time)}</td>
      <td>${esc(t.end_time)}</td>
    </tr>`
    )
    .join("");
}

function renderParentPortal(payload) {
  const portal = payload?.portal || {};
  const children = portal.children || [];
  const reports = portal.reports || [];
  byId("portal_meta").textContent = `Parent: ${payload.parent?.full_name || "-"} (${payload.parent?.username || "-"})`;

  const childrenBody = byId("portal_children_table");
  if (!children.length) {
    childrenBody.innerHTML = '<tr><td colspan="4" class="small">No linked children.</td></tr>';
  } else {
    childrenBody.innerHTML = children
      .map(
        (c) => `<tr>
        <td>${esc(c.admission_no)}</td>
        <td>${esc(c.full_name)}</td>
        <td>${esc(c.class_name)}</td>
        <td>${esc(c.relation)}</td>
      </tr>`
      )
      .join("");
  }

  const reportsBody = byId("portal_reports_table");
  if (!reports.length) {
    reportsBody.innerHTML = '<tr><td colspan="4" class="small">No reports published yet.</td></tr>';
  } else {
    reportsBody.innerHTML = reports
      .map(
        (r) => `<tr>
        <td>${esc(r.admission_no)}</td>
        <td>${esc(r.student_name)}</td>
        <td>${Number(r.summary?.academics?.average_percentage || 0).toFixed(2)}%</td>
        <td>${Number(r.summary?.fees?.outstanding_balance || 0).toFixed(2)}</td>
      </tr>`
      )
      .join("");
  }
}

async function loadSummary() {
  state.summary = await requestJson("/api/summary");
  renderSummary();
}

async function loadStudents() {
  const data = await requestJson("/api/students");
  state.students = data.students || [];
  renderStudents();
}

async function loadTeachers() {
  const data = await requestJson("/api/teachers");
  state.teachers = data.teachers || [];
  renderTeachers();
}

async function loadFees() {
  const data = await requestJson("/api/fees");
  state.fees = data.fees || [];
  renderFees();
}

async function loadStudentAttendance(day = "") {
  const suffix = day ? `?day=${encodeURIComponent(day)}` : "";
  const data = await requestJson(`/api/attendance/students${suffix}`);
  state.studentAttendance = data.attendance || [];
  renderAttendance();
}

async function loadTeacherAttendance(day = "") {
  const suffix = day ? `?day=${encodeURIComponent(day)}` : "";
  const data = await requestJson(`/api/attendance/teachers${suffix}`);
  state.teacherAttendance = data.attendance || [];
  renderTeacherAttendance();
}

async function loadPapers() {
  const data = await requestJson("/api/papers");
  state.papers = data.papers || [];
  renderPapers();
}

async function loadPaperScores() {
  const paperId = byId("paper_score_paper_id").value;
  if (!paperId) {
    state.paperScores = [];
    renderPaperScores();
    return;
  }
  const data = await requestJson(`/api/papers/${paperId}/scores`);
  state.paperScores = data.scores || [];
  renderPaperScores();
}

async function loadParents() {
  const data = await requestJson("/api/parents");
  state.parents = data.parents || [];
  renderParents();
}

async function loadAnnouncements() {
  const data = await requestJson("/api/announcements");
  state.announcements = data.announcements || [];
  renderAnnouncements();
}

async function loadLibrary() {
  const [books, issues] = await Promise.all([requestJson("/api/library/books"), requestJson("/api/library/issues")]);
  state.books = books.books || [];
  state.issues = issues.issues || [];
  renderBooks();
  renderIssues();
}

async function loadHostel() {
  const [rooms, allocations] = await Promise.all([
    requestJson("/api/hostel/rooms"),
    requestJson("/api/hostel/allocations"),
  ]);
  state.rooms = rooms.rooms || [];
  state.allocations = allocations.allocations || [];
  renderRooms();
  renderAllocations();
}

async function loadHifz() {
  const data = await requestJson("/api/hifz");
  state.hifz = data.hifz_logs || [];
  renderHifz();
}

async function loadIncidents() {
  const data = await requestJson("/api/incidents");
  state.incidents = data.incidents || [];
  renderIncidents();
}

async function loadTimetable() {
  const data = await requestJson("/api/timetable");
  state.timetable = data.timetable || [];
  renderTimetable();
}

async function onStudentCreate() {
  const payload = {
    full_name: byId("student_full_name").value.trim(),
    class_name: byId("student_class_name").value.trim(),
    section_name: byId("student_section_name").value.trim(),
    guardian_name: byId("student_guardian_name").value.trim(),
    guardian_phone: byId("student_guardian_phone").value.trim(),
    address: byId("student_address").value.trim(),
    notes: byId("student_notes").value.trim(),
  };
  try {
    await requestJson("/api/students", { method: "POST", body: JSON.stringify(payload) });
    setStatus("admission_status", "Student admitted.");
    await Promise.all([loadStudents(), loadSummary()]);
  } catch (err) {
    setStatus("admission_status", err.message, true);
  }
}

async function onTeacherCreate() {
  const payload = {
    full_name: byId("teacher_full_name").value.trim(),
    subject: byId("teacher_subject").value.trim(),
    phone: byId("teacher_phone").value.trim(),
  };
  try {
    await requestJson("/api/teachers", { method: "POST", body: JSON.stringify(payload) });
    setStatus("teacher_status", "Teacher added.");
    await Promise.all([loadTeachers(), loadSummary()]);
  } catch (err) {
    setStatus("teacher_status", err.message, true);
  }
}

async function onFeeCreate() {
  const payload = {
    student_id: Number(byId("fee_student_id").value || "0"),
    fee_month: byId("fee_month").value.trim(),
    category: byId("fee_category").value.trim(),
    amount: Number(byId("fee_amount").value || "0"),
    due_date: byId("fee_due_date").value.trim(),
  };
  try {
    await requestJson("/api/fees", { method: "POST", body: JSON.stringify(payload) });
    setStatus("fees_status", "Fee record created.");
    await Promise.all([loadFees(), loadSummary()]);
  } catch (err) {
    setStatus("fees_status", err.message, true);
  }
}

async function onFeePay() {
  const feeId = Number(byId("fee_pay_id").value || "0");
  const payload = {
    amount: Number(byId("fee_pay_amount").value || "0"),
    method: byId("fee_pay_method").value.trim(),
    reference: byId("fee_pay_reference").value.trim(),
    recorded_by: "admin",
  };
  try {
    await requestJson(`/api/fees/${feeId}/pay`, { method: "POST", body: JSON.stringify(payload) });
    setStatus("fees_status", "Fee payment recorded.");
    await Promise.all([loadFees(), loadSummary()]);
  } catch (err) {
    setStatus("fees_status", err.message, true);
  }
}

async function onStudentAttendanceSave() {
  const payload = {
    day: byId("attendance_day").value.trim(),
    recorded_by: "admin",
    entries: [
      {
        student_id: Number(byId("attendance_student_id").value || "0"),
        present: byId("attendance_present").value === "true",
        remark: byId("attendance_remark").value.trim(),
      },
    ],
  };
  try {
    await requestJson("/api/attendance/students", { method: "POST", body: JSON.stringify(payload) });
    setStatus("attendance_status", "Student attendance saved.");
    await Promise.all([loadStudentAttendance(payload.day), loadSummary()]);
  } catch (err) {
    setStatus("attendance_status", err.message, true);
  }
}

async function onTeacherAttendanceSave() {
  const payload = {
    day: byId("teacher_attendance_day").value.trim(),
    recorded_by: "admin",
    entries: [
      {
        teacher_id: Number(byId("attendance_teacher_id").value || "0"),
        present: byId("teacher_attendance_present").value === "true",
        remark: byId("teacher_attendance_remark").value.trim(),
      },
    ],
  };
  try {
    await requestJson("/api/attendance/teachers", { method: "POST", body: JSON.stringify(payload) });
    setStatus("attendance_status", "Teacher attendance saved.");
    await loadTeacherAttendance(payload.day);
  } catch (err) {
    setStatus("attendance_status", err.message, true);
  }
}

async function onPaperCreate() {
  const payload = {
    title: byId("paper_title").value.trim(),
    subject: byId("paper_subject").value.trim(),
    class_name: byId("paper_class_name").value.trim(),
    term_name: byId("paper_term_name").value.trim(),
    max_marks: Number(byId("paper_max_marks").value || "0"),
    exam_date: byId("paper_exam_date").value.trim(),
    paper_type: byId("paper_type").value.trim(),
    created_by: "admin",
  };
  try {
    await requestJson("/api/papers", { method: "POST", body: JSON.stringify(payload) });
    setStatus("papers_status", "Paper created.");
    await loadPapers();
  } catch (err) {
    setStatus("papers_status", err.message, true);
  }
}

async function onPaperScoreSave() {
  const paperId = Number(byId("paper_score_paper_id").value || "0");
  const payload = {
    entries: [
      {
        student_id: Number(byId("paper_score_student_id").value || "0"),
        marks: Number(byId("paper_score_marks").value || "0"),
        remarks: byId("paper_score_remarks").value.trim(),
      },
    ],
  };
  try {
    await requestJson(`/api/papers/${paperId}/scores`, { method: "POST", body: JSON.stringify(payload) });
    setStatus("papers_status", "Paper score saved.");
    await loadPaperScores();
  } catch (err) {
    setStatus("papers_status", err.message, true);
  }
}

async function onPaperSelectionChange() {
  await loadPaperScores();
}

async function onParentLink() {
  const payload = {
    student_id: Number(byId("parent_student_id").value || "0"),
    parent_name: byId("parent_name").value.trim(),
    parent_phone: byId("parent_phone").value.trim(),
    relation: byId("parent_relation").value.trim(),
    preferred_username: byId("parent_username").value.trim(),
    password: byId("parent_password").value.trim(),
  };
  try {
    const data = await requestJson("/api/parents/link", { method: "POST", body: JSON.stringify(payload) });
    const passHint = data.parent_user?.temporary_password ? ` Temporary password: ${data.parent_user.temporary_password}` : "";
    setStatus("parent_status", `Parent linked.${passHint}`);
    await Promise.all([loadParents(), loadSummary()]);
  } catch (err) {
    setStatus("parent_status", err.message, true);
  }
}

async function onProgressGenerate() {
  const studentId = Number(byId("report_student_id").value || "0");
  try {
    const data = await requestJson(`/api/reports/students/${studentId}/progress`);
    const report = data.report || {};
    byId("progress_result").textContent = JSON.stringify(
      {
        student: report.student?.full_name,
        attendance_percentage: report.attendance?.percentage,
        outstanding_balance: report.fees?.outstanding_balance,
        average_percentage: report.academics?.average_percentage,
        grade: report.academics?.grade,
      },
      null,
      2
    );
    setStatus("report_status", "Progress report generated.");
  } catch (err) {
    setStatus("report_status", err.message, true);
  }
}

async function onProgressPublish() {
  const studentId = Number(byId("report_student_id").value || "0");
  try {
    await requestJson(`/api/reports/students/${studentId}/publish`, {
      method: "POST",
      body: JSON.stringify({ generated_by: "admin" }),
    });
    setStatus("report_status", "Report published to parent portal.");
  } catch (err) {
    setStatus("report_status", err.message, true);
  }
}

async function onParentPortalLogin() {
  const payload = {
    username: byId("portal_username").value.trim(),
    password: byId("portal_password").value.trim(),
  };
  try {
    const data = await requestJson("/api/parent-portal", { method: "POST", body: JSON.stringify(payload) });
    renderParentPortal(data);
    setStatus("portal_status", "Parent portal loaded.");
  } catch (err) {
    setStatus("portal_status", err.message, true);
  }
}

async function onAnnouncementCreate() {
  const payload = {
    title: byId("announce_title").value.trim(),
    body: byId("announce_body").value.trim(),
    target_group: byId("announce_target").value.trim(),
  };
  try {
    await requestJson("/api/announcements", { method: "POST", body: JSON.stringify(payload) });
    setStatus("announce_status", "Announcement posted.");
    await loadAnnouncements();
  } catch (err) {
    setStatus("announce_status", err.message, true);
  }
}

async function onBookAdd() {
  const payload = {
    book_code: byId("book_code").value.trim(),
    title: byId("book_title").value.trim(),
    author: byId("book_author").value.trim(),
    category: byId("book_category").value.trim(),
    total_copies: Number(byId("book_copies").value || "1"),
  };
  try {
    await requestJson("/api/library/books", { method: "POST", body: JSON.stringify(payload) });
    setStatus("library_status", "Book added.");
    await loadLibrary();
  } catch (err) {
    setStatus("library_status", err.message, true);
  }
}

async function onBookIssue() {
  const payload = {
    book_id: Number(byId("book_issue_book_id").value || "0"),
    student_id: Number(byId("book_issue_student_id").value || "0"),
    due_on: byId("book_issue_due_on").value.trim(),
  };
  try {
    await requestJson("/api/library/issues", { method: "POST", body: JSON.stringify(payload) });
    setStatus("library_status", "Book issued.");
    await loadLibrary();
  } catch (err) {
    setStatus("library_status", err.message, true);
  }
}

async function onRoomAdd() {
  const payload = {
    room_code: byId("hostel_room_code").value.trim(),
    capacity: Number(byId("hostel_capacity").value || "0"),
  };
  try {
    await requestJson("/api/hostel/rooms", { method: "POST", body: JSON.stringify(payload) });
    setStatus("hostel_status", "Hostel room added.");
    await loadHostel();
  } catch (err) {
    setStatus("hostel_status", err.message, true);
  }
}

async function onHostelAllocate() {
  const payload = {
    room_id: Number(byId("hostel_room_id").value || "0"),
    student_id: Number(byId("hostel_student_id").value || "0"),
    start_on: byId("hostel_start_on").value.trim(),
  };
  try {
    await requestJson("/api/hostel/allocations", { method: "POST", body: JSON.stringify(payload) });
    setStatus("hostel_status", "Student allocated to hostel room.");
    await Promise.all([loadHostel(), loadSummary()]);
  } catch (err) {
    setStatus("hostel_status", err.message, true);
  }
}

async function onHifzSave() {
  const payload = {
    student_id: Number(byId("hifz_student_id").value || "0"),
    surah_name: byId("hifz_surah").value.trim(),
    para_no: Number(byId("hifz_para").value || "1"),
    ayat_from: Number(byId("hifz_from").value || "1"),
    ayat_to: Number(byId("hifz_to").value || "1"),
    revision_grade: byId("hifz_grade").value.trim(),
    teacher_name: byId("hifz_teacher").value.trim(),
  };
  try {
    await requestJson("/api/hifz", { method: "POST", body: JSON.stringify(payload) });
    setStatus("hifz_status", "Hifz progress saved.");
    await loadHifz();
  } catch (err) {
    setStatus("hifz_status", err.message, true);
  }
}

async function onIncidentSave() {
  const payload = {
    student_id: Number(byId("incident_student_id").value || "0"),
    category: byId("incident_category").value.trim(),
    description: byId("incident_description").value.trim(),
    action_taken: byId("incident_action").value.trim(),
    reported_by: byId("incident_reported_by").value.trim(),
  };
  try {
    await requestJson("/api/incidents", { method: "POST", body: JSON.stringify(payload) });
    setStatus("incident_status", "Incident logged.");
    await loadIncidents();
  } catch (err) {
    setStatus("incident_status", err.message, true);
  }
}

async function onTimetableSave() {
  const payload = {
    class_name: byId("tt_class_name").value.trim(),
    day_name: byId("tt_day_name").value.trim(),
    period_no: Number(byId("tt_period_no").value || "1"),
    subject: byId("tt_subject").value.trim(),
    teacher_name: byId("tt_teacher_name").value.trim(),
    start_time: byId("tt_start").value.trim(),
    end_time: byId("tt_end").value.trim(),
  };
  try {
    await requestJson("/api/timetable", { method: "POST", body: JSON.stringify(payload) });
    setStatus("timetable_status", "Timetable entry saved.");
    await loadTimetable();
  } catch (err) {
    setStatus("timetable_status", err.message, true);
  }
}

function bindEvents() {
  byId("refresh_all_btn").addEventListener("click", init);
  byId("student_add_btn").addEventListener("click", onStudentCreate);
  byId("teacher_add_btn").addEventListener("click", onTeacherCreate);
  byId("fee_add_btn").addEventListener("click", onFeeCreate);
  byId("fee_pay_btn").addEventListener("click", onFeePay);
  byId("attendance_save_btn").addEventListener("click", onStudentAttendanceSave);
  byId("teacher_attendance_save_btn").addEventListener("click", onTeacherAttendanceSave);
  byId("paper_add_btn").addEventListener("click", onPaperCreate);
  byId("paper_score_save_btn").addEventListener("click", onPaperScoreSave);
  byId("paper_score_paper_id").addEventListener("change", onPaperSelectionChange);
  byId("parent_link_btn").addEventListener("click", onParentLink);
  byId("progress_generate_btn").addEventListener("click", onProgressGenerate);
  byId("progress_publish_btn").addEventListener("click", onProgressPublish);
  byId("portal_login_btn").addEventListener("click", onParentPortalLogin);
  byId("announce_add_btn").addEventListener("click", onAnnouncementCreate);
  byId("book_add_btn").addEventListener("click", onBookAdd);
  byId("book_issue_btn").addEventListener("click", onBookIssue);
  byId("hostel_room_add_btn").addEventListener("click", onRoomAdd);
  byId("hostel_allocate_btn").addEventListener("click", onHostelAllocate);
  byId("hifz_save_btn").addEventListener("click", onHifzSave);
  byId("incident_save_btn").addEventListener("click", onIncidentSave);
  byId("tt_save_btn").addEventListener("click", onTimetableSave);
}

async function init() {
  try {
    await Promise.all([
      loadSummary(),
      loadStudents(),
      loadTeachers(),
      loadFees(),
      loadPapers(),
      loadParents(),
      loadAnnouncements(),
      loadLibrary(),
      loadHostel(),
      loadHifz(),
      loadIncidents(),
      loadTimetable(),
      loadStudentAttendance(),
      loadTeacherAttendance(),
    ]);
    await loadPaperScores();
  } catch (err) {
    setStatus("admission_status", err.message, true);
  }
}

bindEvents();
init();

