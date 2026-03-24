const state = {
  summary: {},
  students: [],
  teachers: [],
  fees: [],
  papers: [],
  parents: [],
  studentAttendance: [],
  hifz: [],
  incidents: [],
  announcements: [],
  timetable: [],
  books: [],
  rooms: [],
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
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}

function setStatus(id, text, isError = false) {
  const el = byId(id);
  if (!el) return;
  el.textContent = text || "";
  el.className = `status ${isError ? "err" : "ok"}`;
}

function activateSection(id) {
  document.querySelectorAll(".menu-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.section === id);
  });
  document.querySelectorAll(".section-card").forEach((card) => {
    card.classList.toggle("active", card.id === id);
  });
}

function renderSummary() {
  byId("sum_students").textContent = String(state.summary.students || 0);
  byId("sum_teachers").textContent = String(state.summary.teachers || 0);
  byId("sum_parents").textContent = String(state.summary.parents || 0);
  byId("sum_pending").textContent = String(state.summary.pending_fee_records || 0);
  byId("sum_outstanding").textContent = Number(state.summary.pending_fee_balance || 0).toFixed(2);
  byId("sum_attendance").textContent = `${state.summary.today_attendance_present || 0}/${state.summary.today_attendance_total || 0}`;
  byId("sum_hostel").textContent = String(state.summary.hostel_active_allocations || 0);
  byId("sum_library").textContent = String(state.summary.library_issued_books || 0);
}

function renderStudents() {
  const body = byId("students_table");
  if (!state.students.length) {
    body.innerHTML = '<tr><td colspan="5">No students found.</td></tr>';
    return;
  }
  body.innerHTML = state.students.map((s) => `
    <tr>
      <td>${s.id}</td>
      <td>${esc(s.admission_no)}</td>
      <td>${esc(s.full_name)}</td>
      <td>${esc(s.class_name)}</td>
      <td>${esc(s.guardian_name)}</td>
    </tr>
  `).join("");
}

function renderTeachers() {
  const body = byId("teachers_table");
  if (!state.teachers.length) {
    body.innerHTML = '<tr><td colspan="3">No teachers found.</td></tr>';
    return;
  }
  body.innerHTML = state.teachers.map((t) => `
    <tr>
      <td>${t.id}</td>
      <td>${esc(t.full_name)}</td>
      <td>${esc(t.subject)}</td>
    </tr>
  `).join("");
}

function renderParents() {
  const body = byId("parents_table");
  if (!state.parents.length) {
    body.innerHTML = '<tr><td colspan="3">No parent links found.</td></tr>';
    return;
  }
  body.innerHTML = state.parents.map((p) => `
    <tr>
      <td>${esc(p.username)}</td>
      <td>${esc(p.parent_name)}</td>
      <td>${esc(p.student_name)}</td>
    </tr>
  `).join("");
}

function renderFees() {
  const body = byId("fees_table");
  if (!state.fees.length) {
    body.innerHTML = '<tr><td colspan="5">No fee records found.</td></tr>';
    return;
  }
  body.innerHTML = state.fees.map((f) => `
    <tr>
      <td>${f.id}</td>
      <td>${esc(f.full_name)}</td>
      <td>${esc(f.fee_month)}</td>
      <td>${esc(f.status)}</td>
      <td>${Number(f.balance || 0).toFixed(2)}</td>
    </tr>
  `).join("");
}

function renderAttendance() {
  const body = byId("student_attendance_table");
  if (!state.studentAttendance.length) {
    body.innerHTML = '<tr><td colspan="4">No attendance records found.</td></tr>';
    return;
  }
  body.innerHTML = state.studentAttendance.map((a) => `
    <tr>
      <td>${esc(a.day)}</td>
      <td>${esc(a.full_name)}</td>
      <td>${esc(a.class_name)}</td>
      <td>${a.present ? "Present" : "Absent"}</td>
    </tr>
  `).join("");
}

function renderPapers() {
  const body = byId("papers_table");
  if (!state.papers.length) {
    body.innerHTML = '<tr><td colspan="5">No paper records found.</td></tr>';
    return;
  }
  body.innerHTML = state.papers.map((p) => `
    <tr>
      <td>${p.id}</td>
      <td>${esc(p.title)}</td>
      <td>${esc(p.class_name)}</td>
      <td>${esc(p.exam_date)}</td>
      <td>${Number(p.max_marks).toFixed(2)}</td>
    </tr>
  `).join("");
}

function renderHifz() {
  const body = byId("hifz_table");
  if (!state.hifz.length) {
    body.innerHTML = '<tr><td colspan="5">No hifz logs found.</td></tr>';
    return;
  }
  body.innerHTML = state.hifz.map((h) => `
    <tr>
      <td>${esc(h.student_name)}</td>
      <td>${esc(h.surah_name)}</td>
      <td>${h.para_no}</td>
      <td>${h.ayat_from}-${h.ayat_to}</td>
      <td>${esc(h.revision_grade || "-")}</td>
    </tr>
  `).join("");
}

function renderIncidents() {
  const body = byId("incident_table");
  if (!state.incidents.length) {
    body.innerHTML = '<tr><td colspan="4">No incidents found.</td></tr>';
    return;
  }
  body.innerHTML = state.incidents.map((i) => `
    <tr>
      <td>${i.id}</td>
      <td>${esc(i.student_name)}</td>
      <td>${esc(i.category)}</td>
      <td>${esc(i.action_taken || "-")}</td>
    </tr>
  `).join("");
}

function renderAnnouncements() {
  const body = byId("notice_table");
  if (!state.announcements.length) {
    body.innerHTML = '<tr><td colspan="3">No announcements found.</td></tr>';
    return;
  }
  body.innerHTML = state.announcements.map((n) => `
    <tr>
      <td>${esc(n.title)}</td>
      <td>${esc(n.target_group)}</td>
      <td>${esc(n.created_at)}</td>
    </tr>
  `).join("");
}

function renderTimetable() {
  const body = byId("tt_table");
  if (!state.timetable.length) {
    body.innerHTML = '<tr><td colspan="5">No timetable entries found.</td></tr>';
    return;
  }
  body.innerHTML = state.timetable.map((t) => `
    <tr>
      <td>${esc(t.class_name)}</td>
      <td>${esc(t.day_name)}</td>
      <td>${t.period_no}</td>
      <td>${esc(t.subject)}</td>
      <td>${esc(t.start_time)}-${esc(t.end_time)}</td>
    </tr>
  `).join("");
}

function renderBooks(books) {
  const body = byId("books_table");
  if (!books.length) {
    body.innerHTML = '<tr><td colspan="4">No books found.</td></tr>';
    return;
  }
  body.innerHTML = books.map((b) => `
    <tr>
      <td>${b.id}</td>
      <td>${esc(b.book_code)}</td>
      <td>${esc(b.title)}</td>
      <td>${b.available_copies}/${b.total_copies}</td>
    </tr>
  `).join("");
}

function renderRooms(rooms) {
  const body = byId("rooms_table");
  if (!rooms.length) {
    body.innerHTML = '<tr><td colspan="3">No rooms found.</td></tr>';
    return;
  }
  body.innerHTML = rooms.map((r) => `
    <tr>
      <td>${esc(r.room_code)}</td>
      <td>${r.capacity}</td>
      <td>${r.occupied}</td>
    </tr>
  `).join("");
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

async function loadParents() {
  const data = await requestJson("/api/parents");
  state.parents = data.parents || [];
  renderParents();
}

async function loadFees() {
  const data = await requestJson("/api/fees");
  state.fees = data.fees || [];
  renderFees();
}

async function loadAttendance() {
  const data = await requestJson("/api/attendance/students");
  state.studentAttendance = data.attendance || [];
  renderAttendance();
}

async function loadPapers() {
  const data = await requestJson("/api/papers");
  state.papers = data.papers || [];
  renderPapers();
}

async function loadHifz() {
  const data = await requestJson("/api/hifz");
  state.hifz = data.hifz_logs || [];
  renderHifz();
}

async function loadIncidents() {
  const [incidents, notices] = await Promise.all([
    requestJson("/api/incidents"),
    requestJson("/api/announcements"),
  ]);
  state.incidents = incidents.incidents || [];
  state.announcements = notices.announcements || [];
  renderIncidents();
  renderAnnouncements();
}

async function loadTimetable() {
  const data = await requestJson("/api/timetable");
  state.timetable = data.timetable || [];
  renderTimetable();
}

async function loadLibrary() {
  const books = await requestJson("/api/library/books");
  renderBooks(books.books || []);
}

async function loadHostel() {
  const rooms = await requestJson("/api/hostel/rooms");
  renderRooms(rooms.rooms || []);
}

async function onStudentCreate() {
  try {
    await requestJson("/api/students", {
      method: "POST",
      body: JSON.stringify({
        full_name: byId("student_name").value,
        arabic_name: byId("student_arabic_name").value,
        class_name: byId("student_class").value,
        section_name: byId("student_section").value,
        guardian_name: byId("student_guardian").value,
        guardian_phone: byId("student_guardian_phone").value,
      }),
    });
    setStatus("student_status", "Student admitted successfully.");
    await Promise.all([loadStudents(), loadSummary()]);
  } catch (err) {
    setStatus("student_status", err.message, true);
  }
}

async function onTeacherCreate() {
  try {
    await requestJson("/api/teachers", {
      method: "POST",
      body: JSON.stringify({
        full_name: byId("teacher_name").value,
        subject: byId("teacher_subject").value,
      }),
    });
    setStatus("people_status", "Teacher added.");
    await Promise.all([loadTeachers(), loadSummary()]);
  } catch (err) {
    setStatus("people_status", err.message, true);
  }
}

async function onParentLink() {
  try {
    const res = await requestJson("/api/parents/link", {
      method: "POST",
      body: JSON.stringify({
        student_id: Number(byId("parent_student_id").value),
        parent_name: byId("parent_name").value,
        parent_phone: byId("parent_phone").value,
        password: byId("parent_password").value,
      }),
    });
    const tmp = res.parent_user.temporary_password;
    setStatus("people_status", tmp ? `Parent linked. Temporary password: ${tmp}` : "Parent linked.");
    await Promise.all([loadParents(), loadSummary()]);
  } catch (err) {
    setStatus("people_status", err.message, true);
  }
}

async function onFeeCreate() {
  try {
    await requestJson("/api/fees", {
      method: "POST",
      body: JSON.stringify({
        student_id: Number(byId("fee_student_id").value),
        fee_month: byId("fee_month").value,
        category: byId("fee_category").value,
        amount: Number(byId("fee_amount").value),
        due_date: byId("fee_due_date").value,
      }),
    });
    setStatus("fees_status", "Fee record created.");
    await Promise.all([loadFees(), loadSummary()]);
  } catch (err) {
    setStatus("fees_status", err.message, true);
  }
}

async function onFeePay() {
  try {
    await requestJson(`/api/fees/${Number(byId("pay_fee_id").value)}/pay`, {
      method: "POST",
      body: JSON.stringify({
        amount: Number(byId("pay_amount").value),
        method: byId("pay_method").value,
      }),
    });
    setStatus("fees_status", "Payment recorded.");
    await Promise.all([loadFees(), loadSummary()]);
  } catch (err) {
    setStatus("fees_status", err.message, true);
  }
}

async function onStudentAttendance() {
  try {
    await requestJson("/api/attendance/students", {
      method: "POST",
      body: JSON.stringify({
        day: byId("att_student_day").value,
        entries: [{
          student_id: Number(byId("att_student_id").value),
          present: byId("att_student_present").value === "true",
        }],
      }),
    });
    setStatus("attendance_status", "Student attendance saved.");
    await Promise.all([loadAttendance(), loadSummary()]);
  } catch (err) {
    setStatus("attendance_status", err.message, true);
  }
}

async function onTeacherAttendance() {
  try {
    await requestJson("/api/attendance/teachers", {
      method: "POST",
      body: JSON.stringify({
        day: byId("att_teacher_day").value,
        entries: [{
          teacher_id: Number(byId("att_teacher_id").value),
          present: byId("att_teacher_present").value === "true",
        }],
      }),
    });
    setStatus("attendance_status", "Teacher attendance saved.");
  } catch (err) {
    setStatus("attendance_status", err.message, true);
  }
}

async function onPaperCreate() {
  try {
    await requestJson("/api/papers", {
      method: "POST",
      body: JSON.stringify({
        title: byId("paper_title").value,
        subject: byId("paper_subject").value,
        class_name: byId("paper_class").value,
        term_name: byId("paper_term").value,
        max_marks: Number(byId("paper_max_marks").value),
        exam_date: byId("paper_date").value,
        paper_type: byId("paper_type").value,
      }),
    });
    setStatus("papers_status", "Paper created.");
    await loadPapers();
  } catch (err) {
    setStatus("papers_status", err.message, true);
  }
}

async function onScoreSave() {
  try {
    await requestJson(`/api/papers/${Number(byId("score_paper_id").value)}/scores`, {
      method: "POST",
      body: JSON.stringify({
        entries: [{
          student_id: Number(byId("score_student_id").value),
          marks: Number(byId("score_marks").value),
        }],
      }),
    });
    setStatus("papers_status", "Score saved.");
  } catch (err) {
    setStatus("papers_status", err.message, true);
  }
}

async function onReportView() {
  try {
    const res = await requestJson(`/api/reports/students/${Number(byId("report_student_id").value)}/progress`);
    byId("report_preview").textContent = JSON.stringify(res.report, null, 2);
    setStatus("report_status", "Report generated.");
  } catch (err) {
    setStatus("report_status", err.message, true);
  }
}

async function onReportPublish() {
  try {
    await requestJson(`/api/reports/students/${Number(byId("report_student_id").value)}/publish`, {
      method: "POST",
      body: JSON.stringify({ generated_by: byId("report_generated_by").value }),
    });
    setStatus("report_status", "Report published.");
  } catch (err) {
    setStatus("report_status", err.message, true);
  }
}

async function onPortalLogin() {
  try {
    const res = await requestJson("/api/parent-portal", {
      method: "POST",
      body: JSON.stringify({
        username: byId("portal_username").value,
        password: byId("portal_password").value,
      }),
    });
    byId("portal_preview").textContent = JSON.stringify(res.portal, null, 2);
    setStatus("portal_status", "Parent portal loaded.");
  } catch (err) {
    setStatus("portal_status", err.message, true);
  }
}

async function onHifzSave() {
  try {
    await requestJson("/api/hifz", {
      method: "POST",
      body: JSON.stringify({
        student_id: Number(byId("hifz_student_id").value),
        para_no: Number(byId("hifz_para").value),
        surah_name: byId("hifz_surah").value,
        ayat_from: Number(byId("hifz_ayat_from").value),
        ayat_to: Number(byId("hifz_ayat_to").value),
        revision_grade: byId("hifz_grade").value,
      }),
    });
    setStatus("hifz_status", "Hifz saved.");
    await loadHifz();
  } catch (err) {
    setStatus("hifz_status", err.message, true);
  }
}

async function onIncidentSave() {
  try {
    await requestJson("/api/incidents", {
      method: "POST",
      body: JSON.stringify({
        student_id: Number(byId("incident_student_id").value),
        category: byId("incident_category").value,
        description: byId("incident_desc").value,
        action_taken: byId("incident_action").value,
      }),
    });
    setStatus("notice_status", "Incident saved.");
    await loadIncidents();
  } catch (err) {
    setStatus("notice_status", err.message, true);
  }
}

async function onNoticeSave() {
  try {
    await requestJson("/api/announcements", {
      method: "POST",
      body: JSON.stringify({
        title: byId("notice_title").value,
        target_group: byId("notice_target").value,
        body: byId("notice_body").value,
      }),
    });
    setStatus("notice_status", "Announcement published.");
    await loadIncidents();
  } catch (err) {
    setStatus("notice_status", err.message, true);
  }
}

async function onTimetableSave() {
  try {
    const [start, end] = (byId("tt_time").value || "").split("-");
    await requestJson("/api/timetable", {
      method: "POST",
      body: JSON.stringify({
        class_name: byId("tt_class").value,
        day_name: byId("tt_day").value,
        period_no: Number(byId("tt_period").value),
        subject: byId("tt_subject").value,
        teacher_name: byId("tt_teacher").value,
        start_time: (start || "").trim(),
        end_time: (end || "").trim(),
      }),
    });
    setStatus("tt_status", "Timetable saved.");
    await loadTimetable();
  } catch (err) {
    setStatus("tt_status", err.message, true);
  }
}

async function onBookAdd() {
  try {
    await requestJson("/api/library/books", {
      method: "POST",
      body: JSON.stringify({
        book_code: byId("book_code").value,
        title: byId("book_title").value,
        total_copies: Number(byId("book_copies").value),
      }),
    });
    setStatus("library_status", "Book added.");
    await loadLibrary();
  } catch (err) {
    setStatus("library_status", err.message, true);
  }
}

async function onBookIssue() {
  try {
    await requestJson("/api/library/issues", {
      method: "POST",
      body: JSON.stringify({
        book_id: Number(byId("issue_book_id").value),
        student_id: Number(byId("issue_student_id").value),
        due_on: byId("issue_due").value,
      }),
    });
    setStatus("library_status", "Book issued.");
    await loadLibrary();
  } catch (err) {
    setStatus("library_status", err.message, true);
  }
}

async function onBookReturn() {
  try {
    await requestJson(`/api/library/issues/${Number(byId("return_issue_id").value)}/return`, { method: "POST" });
    setStatus("library_status", "Book returned.");
    await loadLibrary();
  } catch (err) {
    setStatus("library_status", err.message, true);
  }
}

async function onRoomAdd() {
  try {
    await requestJson("/api/hostel/rooms", {
      method: "POST",
      body: JSON.stringify({
        room_code: byId("room_code").value,
        capacity: Number(byId("room_capacity").value),
      }),
    });
    setStatus("hostel_status", "Room added.");
    await loadHostel();
  } catch (err) {
    setStatus("hostel_status", err.message, true);
  }
}

async function onRoomAllocate() {
  try {
    await requestJson("/api/hostel/allocations", {
      method: "POST",
      body: JSON.stringify({
        room_id: Number(byId("alloc_room_id").value),
        student_id: Number(byId("alloc_student_id").value),
        start_on: byId("alloc_start").value,
      }),
    });
    setStatus("hostel_status", "Room allocated.");
    await Promise.all([loadHostel(), loadSummary()]);
  } catch (err) {
    setStatus("hostel_status", err.message, true);
  }
}

function bindEvents() {
  document.querySelectorAll(".menu-item").forEach((btn) => {
    btn.addEventListener("click", () => activateSection(btn.dataset.section));
  });
  byId("add_student_btn").addEventListener("click", onStudentCreate);
  byId("refresh_students_btn").addEventListener("click", loadStudents);
  byId("add_teacher_btn").addEventListener("click", onTeacherCreate);
  byId("link_parent_btn").addEventListener("click", onParentLink);
  byId("refresh_people_btn").addEventListener("click", async () => { await Promise.all([loadTeachers(), loadParents()]); });
  byId("add_fee_btn").addEventListener("click", onFeeCreate);
  byId("pay_fee_btn").addEventListener("click", onFeePay);
  byId("refresh_fees_btn").addEventListener("click", loadFees);
  byId("save_student_att_btn").addEventListener("click", onStudentAttendance);
  byId("save_teacher_att_btn").addEventListener("click", onTeacherAttendance);
  byId("refresh_attendance_btn").addEventListener("click", loadAttendance);
  byId("add_paper_btn").addEventListener("click", onPaperCreate);
  byId("save_score_btn").addEventListener("click", onScoreSave);
  byId("refresh_papers_btn").addEventListener("click", loadPapers);
  byId("view_report_btn").addEventListener("click", onReportView);
  byId("publish_report_btn").addEventListener("click", onReportPublish);
  byId("portal_login_btn").addEventListener("click", onPortalLogin);
  byId("save_hifz_btn").addEventListener("click", onHifzSave);
  byId("refresh_hifz_btn").addEventListener("click", loadHifz);
  byId("save_incident_btn").addEventListener("click", onIncidentSave);
  byId("save_notice_btn").addEventListener("click", onNoticeSave);
  byId("refresh_notice_btn").addEventListener("click", loadIncidents);
  byId("save_tt_btn").addEventListener("click", onTimetableSave);
  byId("refresh_tt_btn").addEventListener("click", loadTimetable);
  byId("add_book_btn").addEventListener("click", onBookAdd);
  byId("issue_book_btn").addEventListener("click", onBookIssue);
  byId("return_book_btn").addEventListener("click", onBookReturn);
  byId("refresh_library_btn").addEventListener("click", loadLibrary);
  byId("add_room_btn").addEventListener("click", onRoomAdd);
  byId("allocate_room_btn").addEventListener("click", onRoomAllocate);
  byId("refresh_hostel_btn").addEventListener("click", loadHostel);
}

async function init() {
  bindEvents();
  activateSection("overview");
  await Promise.all([
    loadSummary(),
    loadStudents(),
    loadTeachers(),
    loadParents(),
    loadFees(),
    loadAttendance(),
    loadPapers(),
    loadHifz(),
    loadIncidents(),
    loadTimetable(),
    loadLibrary(),
    loadHostel(),
  ]);
}

init().catch((err) => {
  setStatus("student_status", err.message, true);
});

