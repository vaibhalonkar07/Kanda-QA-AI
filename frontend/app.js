/* Kanda QA - single-page client. Vanilla JS, no build step. */
const $app = document.getElementById("app");
const state = { token: sessionStorage.getItem("token"), user: JSON.parse(sessionStorage.getItem("user") || "null") };

const DECISION = { GRADE_A: "Grade A lot", URS: "URS lot", REJECTED: "Not eligible" };
const GRADE = { GRADE_A: "Grade A", URS: "URS", REJECT: "Rejected" };
const SEGMENTS = [
  ["grade_a", "Grade A", "#2e7d4f"], ["urs", "URS", "#d18a1c"], ["rotten", "Rotten", "#5e1a1a"],
  ["damaged", "Damaged", "#b3261e"], ["sprouted", "Sprouted", "#e0754a"],
  ["undersized", "Undersized", "#8b7d9c"], ["oversized", "Oversized", "#5f5470"],
];

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (iso) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
const fmtMoney = (amount) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(amount);
const isStaff = () => state.user && ["admin", "operator"].includes(state.user.role);

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2800);
}

async function api(path, { method = "GET", json, form, raw } = {}) {
  const headers = {};
  if (state.token) headers.Authorization = "Bearer " + state.token;
  let body;
  if (json) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) body = form;
  const res = await fetch("/api" + path, { method, headers, body });
  if (res.status === 401 && state.token) { signOut(); throw new Error("Session expired. Sign in again"); }
  if (!res.ok) {
    let msg = res.statusText;
    try { const d = await res.json(); msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail); } catch {}
    throw new Error(msg);
  }
  return raw ? res : res.json();
}

function setSession(data) {
  state.token = data.access_token; state.user = data.user;
  sessionStorage.setItem("token", state.token); sessionStorage.setItem("user", JSON.stringify(state.user));
}
function signOut() {
  state.token = null; state.user = null; sessionStorage.clear(); location.hash = "#/"; render();
}

/* ---------- layout ---------- */
function shell(active, inner) {
  const staff = isStaff();
  const nav = [
    ["dashboard", "Dashboard"], ...(staff ? [["inspect", "New inspection"]] : []),
    ["batches", staff ? "Batches" : "My batches"], ["reports", staff ? "Reports" : "My reports"],
    ...(staff ? [["farmers", "Farmers"]] : []), ...(state.user.role === "admin" ? [["standards", "Standards"]] : []),
  ];
  return `<div class="shell"><nav class="rail" aria-label="Main">
    <div class="brand"><i></i>Kanda QA</div>
    ${nav.map(([r, l]) => `<a href="#/${r}" ${active === r ? 'aria-current="page"' : ""}>${l}</a>`).join("")}
    <div class="who">${esc(state.user.full_name)}<br><span class="small">${esc(state.user.role)}${state.user.centre ? " - " + esc(state.user.centre) : ""}</span><br>
    <button id="signout">Sign out</button></div></nav><main>${inner}</main></div>`;
}

/* ---------- auth ---------- */
function viewAuth(mode = "login") {
  const reg = mode === "register";
  $app.innerHTML = `<div class="auth"><div class="brand"><i></i>Kanda QA</div>
  <div class="panel"><h1>${reg ? "Create farmer account" : "Sign in"}</h1>
  <p class="muted">${reg ? "See the quality reports for your onion lots." : "AI-assisted onion quality inspection for procurement centres."}</p>
  <form id="f">
    ${reg ? `<label for="full_name">Full name</label><input id="full_name" required minlength="2" autocomplete="name">
    <div class="row"><div><label for="phone">Phone</label><input id="phone" inputmode="tel"></div><div><label for="village">Village</label><input id="village"></div></div>` : ""}
    <label for="username">Username</label><input id="username" required minlength="3" autocomplete="username">
    <label for="password">Password${reg ? " (8+ characters)" : ""}</label><input id="password" type="password" required ${reg ? 'minlength="8"' : ""} autocomplete="${reg ? "new-password" : "current-password"}">
    <div class="err" id="err"></div>
    <button class="primary" style="width:100%;margin-top:8px">${reg ? "Create account" : "Sign in"}</button>
  </form>
  <p class="small muted" style="margin-top:14px">${reg ? 'Have an account? <a href="#/login">Sign in</a>' : 'Farmer without an account? <a href="#/register">Create one</a>'}</p></div>
  <p class="small muted">Check a report: <a href="#/verify">verify a report ID</a></p></div>`;
  document.getElementById("f").onsubmit = async (e) => {
    e.preventDefault();
    const v = (id) => document.getElementById(id)?.value.trim();
    try {
      const data = reg
        ? await api("/auth/register-farmer", { method: "POST", json: { username: v("username"), password: document.getElementById("password").value, full_name: v("full_name"), phone: v("phone") || "", village: v("village") || "" } })
        : await api("/auth/login", { method: "POST", json: { username: v("username"), password: document.getElementById("password").value } });
      setSession(data); location.hash = "#/dashboard"; render();
    } catch (err) { document.getElementById("err").textContent = err.message; }
  };
}

/* ---------- shared pieces ---------- */
function band(counts, pct) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  const segs = SEGMENTS.filter(([k]) => counts[k] > 0);
  return `<div class="band" role="img" aria-label="Lot composition">${segs.map(([k, l, c]) => `<div style="flex:${counts[k] / total};background:${c}" title="${l} ${pct[k]}%"></div>`).join("")}</div>
  <div class="legend">${SEGMENTS.map(([k, l, c]) => `<span style="--c:${c}">${l} <b>${counts[k] || 0}</b> (${pct[k] ?? 0}%)</span>`).join("")}</div>`;
}
function inspectionTable(rows) {
  if (!rows.length) return `<p class="muted">No inspections yet.</p>`;
  return `<div class="scroll"><table><thead><tr><th>Report</th><th>Batch</th><th>Farmer</th><th>Result</th><th class="num">Grade A</th><th class="num">Onions</th><th>Date</th></tr></thead><tbody>
  ${rows.map((r) => `<tr class="click" data-go="#/report/${r.id}"><td>${esc(r.report_id)}</td><td>${esc(r.batch_code)}</td><td>${esc(r.farmer)}</td>
  <td><span class="pill ${r.decision}">${DECISION[r.decision]}</span></td><td class="num">${r.grade_a_pct}%</td><td class="num">${r.total_onions}</td><td>${fmtDate(r.created_at)}</td></tr>`).join("")}</tbody></table></div>`;
}
function wireRows() { document.querySelectorAll("[data-go]").forEach((tr) => (tr.onclick = () => (location.hash = tr.dataset.go))); }

/* ---------- views ---------- */
async function viewDashboard() {
  const s = await api("/dashboard/summary");
  $app.innerHTML = shell("dashboard", `<div class="head"><div><h1>Dashboard</h1><p class="muted">${isStaff() ? "Inspection activity at your centre" : "Your onion lots and their quality reports"}</p></div>
    ${isStaff() ? '<button class="primary" data-go="#/inspect">Start new inspection</button>' : ""}</div>
    <div class="kpis"><div class="kpi"><b>${s.batches}</b><span>Batches</span></div><div class="kpi"><b>${s.inspections}</b><span>Inspections</span></div>
    <div class="kpi"><b>${s.onions_analysed}</b><span>Onions analysed</span></div><div class="kpi"><b>${s.grade_a_pct}%</b><span>Grade A</span></div>
    <div class="kpi"><b>${s.urs_pct}%</b><span>URS</span></div><div class="kpi"><b>${s.defective_pct}%</b><span>Rejected onions</span></div></div>
    <div class="panel" style="margin-top:16px"><h2>Recent inspections</h2><div style="margin-top:10px">${inspectionTable(s.recent)}</div></div>`);
  wireRows();
}

let farmersCache = [];
let cameraStream = null;
function stopCamera() {
  cameraStream?.getTracks().forEach((track) => track.stop());
  cameraStream = null;
}

async function viewInspect() {
  if (!isStaff()) return (location.hash = "#/dashboard");
  farmersCache = await api("/farmers");
  $app.innerHTML = shell("inspect", `<div class="head"><div><h1>New inspection</h1><p class="muted">Register the batch, add photos of the onions on a plain tray, then run the AI check.</p></div></div>
  <form id="f" class="grid g2">
    <div class="panel"><h2>1. Batch</h2>
      <label for="farmer">Farmer</label>
      <select id="farmer">${farmersCache.map((f) => `<option value="${f.id}">${esc(f.name)} (${esc(f.farmer_code)})</option>`).join("")}<option value="new">New farmer...</option></select>
      <div id="newf" hidden><label for="fname">Farmer name</label><input id="fname"><div class="row"><div><label for="fvillage">Village</label><input id="fvillage"></div><div><label for="fphone">Phone</label><input id="fphone" inputmode="tel"></div></div></div>
      <div class="row"><div><label for="variety">Variety</label><select id="variety"><option>Red Onion</option><option>Light Red Onion</option><option>White Onion</option><option>Other</option></select></div>
      <div><label for="qty">Quantity (kg)</label><input id="qty" type="number" min="1" step="any" required value="500"></div></div>
      <label for="bagRate">Agreed rate per 50 kg bag (INR)</label><input id="bagRate" type="number" min="0.01" step="0.01" required value="1500">
      <p class="small muted" id="lotValue" aria-live="polite" style="margin:8px 0 0"></p>
      <label for="notes">Notes (optional)</label><input id="notes" maxlength="200"></div>
    <div class="panel"><h2>2. Photos</h2>
      <div class="camera-actions"><button type="button" id="startCamera">Open camera</button>
      <button type="button" id="capturePhoto" disabled>Capture photo</button>
      <button type="button" id="stopCamera" hidden>Close camera</button></div>
      <video id="cameraPreview" class="camera-preview" autoplay muted playsinline hidden></video>
      <p class="small err" id="cameraError" role="status"></p>
      <div class="drop" id="drop"><p style="margin:0 0 8px">Choose photos from this device or drop them here</p>
      <input id="files" type="file" accept="image/*" multiple>
      <p class="small muted" id="fileinfo" style="margin:8px 0 0">Capture photos or choose local files; up to 10 total. Keep every onion fully inside the frame.</p></div>
      <button type="button" id="demo" style="margin-top:10px">Use demo tray image</button>
      <h2 style="margin-top:18px">3. Scale</h2>
      <label for="cal">How is size measured?</label>
      <select id="cal"><option value="marker">Reference marker (ArUco 4x4, in the photo)</option><option value="scene">Fixed camera: width of the tray</option><option value="mmpp">Known millimetres per pixel</option><option value="none">No scale (skip size rules)</option></select>
      <label for="calv" id="callabel">Marker side (mm)</label><input id="calv" type="number" min="0.01" step="any" value="40"></div>
    <div style="grid-column:1/-1"><div class="err" id="err"></div><button class="primary" id="run">Run inspection</button></div>
  </form>`);
  const $ = (id) => document.getElementById(id);
  const updateLotValue = () => {
    const quantity = Number($("qty").value), rate = Number($("bagRate").value);
    $("lotValue").textContent = quantity > 0 && rate > 0
      ? `Estimated value (${(quantity / 50).toLocaleString(undefined, { maximumFractionDigits: 2 })} bags): ${fmtMoney(quantity / 50 * rate)}`
      : "Enter the lot weight and bag rate to estimate its value.";
  };
  $("qty").addEventListener("input", updateLotValue);
  $("bagRate").addEventListener("input", updateLotValue);
  updateLotValue();
  const cameraFiles = [];
  let demoFile = null;
  const selectedCount = () => cameraFiles.length + $("files").files.length + (demoFile ? 1 : 0);
  const updateFileInfo = () => {
    const total = selectedCount();
    const parts = [];
    if ($("files").files.length) parts.push(`${$("files").files.length} local`);
    if (cameraFiles.length) parts.push(`${cameraFiles.length} camera`);
    if (demoFile) parts.push("demo image");
    $("fileinfo").textContent = parts.length ? `${parts.join(" + ")} photo(s) selected (${total}/10)`
      : "Capture photos or choose local files; up to 10 total. Keep every onion fully inside the frame.";
    $("capturePhoto").disabled = !cameraStream || selectedCount() >= 10;
  };
  const calMeta = { marker: ["Marker side (mm)", 40], scene: ["Tray width in the image (mm)", 400], mmpp: ["Millimetres per pixel", 0.33], none: ["", ""] };
  $("cal").onchange = () => { const [l, v] = calMeta[$("cal").value]; $("callabel").textContent = l; $("calv").value = v; $("calv").hidden = $("callabel").hidden = !l; };
  $("farmer").onchange = () => ($("newf").hidden = $("farmer").value !== "new");
  $("files").onchange = () => { demoFile = null; updateFileInfo(); };
  $("drop").ondragover = (e) => { e.preventDefault(); $("drop").classList.add("on"); };
  $("drop").ondragleave = () => $("drop").classList.remove("on");
  $("drop").ondrop = (e) => { e.preventDefault(); $("drop").classList.remove("on"); $("files").files = e.dataTransfer.files; $("files").onchange(); };
  $("startCamera").onclick = async () => {
    $("cameraError").textContent = "";
    if (!navigator.mediaDevices?.getUserMedia) {
      $("cameraError").textContent = "Live camera access is unavailable. Open this site on HTTPS or localhost, or choose local photos.";
      return;
    }
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      demoFile = null;
      $("cameraPreview").srcObject = cameraStream;
      $("cameraPreview").hidden = false;
      $("startCamera").hidden = true;
      $("stopCamera").hidden = false;
      await $("cameraPreview").play();
      updateFileInfo();
    } catch (err) {
      stopCamera();
      $("cameraPreview").srcObject = null;
      $("cameraPreview").hidden = true;
      $("startCamera").hidden = false;
      $("stopCamera").hidden = true;
      $("cameraError").textContent = err.name === "NotAllowedError"
        ? "Camera permission was denied. Allow camera access in your browser or choose local photos."
        : "Could not open the camera. Check that it is connected and not in use by another app.";
    }
  };
  $("stopCamera").onclick = () => {
    stopCamera();
    $("cameraPreview").srcObject = null;
    $("cameraPreview").hidden = true;
    $("startCamera").hidden = false;
    $("stopCamera").hidden = true;
    updateFileInfo();
  };
  $("capturePhoto").onclick = async () => {
    const video = $("cameraPreview");
    if (!video.videoWidth || selectedCount() >= 10) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (blob) cameraFiles.push(new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" }));
    updateFileInfo();
  };
  $("demo").onclick = async () => {
    const blob = await (await fetch("/api/demo/sample-image.jpg")).blob();
    demoFile = new File([blob], "demo-tray.jpg", { type: "image/jpeg" });
    stopCamera();
    $("cameraPreview").srcObject = null;
    $("cameraPreview").hidden = true;
    $("startCamera").hidden = false;
    $("stopCamera").hidden = true;
    cameraFiles.length = 0;
    $("files").value = ""; $("cal").value = "marker"; $("cal").onchange(); updateFileInfo();
  };
  $("f").onsubmit = async (e) => {
    e.preventDefault(); $("err").textContent = "";
    const list = demoFile ? [demoFile] : [...$("files").files, ...cameraFiles];
    if (!list.length) return ($("err").textContent = "Add at least one photo.");
    if (list.length > 10) return ($("err").textContent = "Choose no more than 10 photos in total.");
    const btn = $("run"); btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>Analysing...';
    try {
      let farmerId = $("farmer").value;
      if (farmerId === "new") {
        if (!$("fname").value.trim()) throw new Error("Enter the farmer's name.");
        farmerId = (await api("/farmers", { method: "POST", json: { name: $("fname").value.trim(), village: $("fvillage").value.trim(), phone: $("fphone").value.trim() } })).id;
      }
      const batch = await api("/batches", { method: "POST", json: { farmer_id: Number(farmerId), variety: $("variety").value, quantity_kg: Number($("qty").value) } });
      const fd = new FormData();
      list.forEach((f) => fd.append("files", f));
      fd.append("bag_rate_50kg", $("bagRate").value);
      const v = $("calv").value, k = $("cal").value;
      if (v && k !== "none") fd.append({ marker: "marker_size_mm", scene: "scene_width_mm", mmpp: "mm_per_pixel" }[k], v);
      fd.append("notes", $("notes").value);
      const insp = await api(`/batches/${batch.id}/inspections`, { method: "POST", form: fd });
      toast("Report " + insp.report_id + " created");
      location.hash = "#/report/" + insp.id;
    } catch (err) { $("err").textContent = err.message; btn.disabled = false; btn.textContent = "Run inspection"; }
  };
}

async function viewReport(id) {
  const r = await api("/inspections/" + id);
  const b = r.batch;
  $app.innerHTML = shell("reports", `<div class="head"><div><h1>${esc(r.report_id)}</h1><p class="muted">${esc(b.batch_code)} - ${esc(b.farmer.name)} (${esc(b.farmer.farmer_code)}) - ${esc(b.quantity_kg)} kg ${esc(b.variety)} - ${fmtDate(r.created_at)}</p></div>
    <button class="primary" id="pdf">Download PDF report</button></div>
    <div class="panel"><div class="decision"><span class="big ${r.decision}">${DECISION[r.decision]}</span><span class="muted">${r.total_onions} onions analysed, mean confidence ${r.avg_confidence}</span></div>
    ${r.bag_rate_50kg != null ? `<p style="margin:8px 0 0"><b>Agreed rate:</b> ${fmtMoney(r.bag_rate_50kg)} per 50 kg bag <span class="muted">|</span> <b>Estimated lot value:</b> ${fmtMoney(r.estimated_lot_value)}</p>` : ""}
    ${band(r.counts, r.percentages)}${(r.warnings || []).map((w) => `<div class="note">${esc(w)}</div>`).join("")}</div>
    <div class="grid g2" style="margin-top:16px"><div class="panel"><h2>Why this result</h2><ul class="why" style="margin-top:8px">${r.explanation.map((e) => `<li class="${e.status}">${esc(e.text)}</li>`).join("")}</ul>
      <p class="small muted" style="margin-top:12px">Standard applied: ${esc(r.standard)}. Inspected by ${esc(r.operator || "-")}.</p></div>
    <div class="panel"><h2>Record integrity</h2><p class="small muted">Anyone with the report ID can confirm this record is unchanged.</p>
      <div class="hash">${esc(r.integrity_hash)}</div><p style="margin-top:10px"><a href="#/verify/${esc(r.report_id)}">Open public verification</a></p></div></div>
    <div class="panel" style="margin-top:16px"><h2>Annotated images</h2><p class="small muted">Green outline = Grade A, amber = URS, red = rejected, grey = excluded at the image edge.</p><div class="gallery" id="gal" style="margin-top:10px"></div></div>
    <div class="panel" style="margin-top:16px"><h2>Onion-by-onion</h2><div class="scroll" style="margin-top:8px"><table><thead><tr><th class="num">#</th><th class="num">Diameter</th><th>Grade</th><th>Category</th><th class="num">Damage</th><th class="num">Conf.</th><th>Reasons</th></tr></thead><tbody>
    ${r.onions.map((o) => `<tr><td class="num">${o.number}</td><td class="num">${o.diameter_mm ? o.diameter_mm + " mm" : "-"}</td><td><span class="pill ${o.grade}">${GRADE[o.grade]}</span></td><td>${esc(o.category)}</td><td class="num">${o.damage_pct}%</td><td class="num">${o.confidence}</td><td>${esc(o.reasons.join("; ")) || "-"}</td></tr>`).join("")}</tbody></table></div></div>`);
  document.getElementById("pdf").onclick = async () => {
    const res = await api(`/inspections/${id}/report.pdf`, { raw: true });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(await res.blob()), download: r.report_id + ".pdf" });
    a.click();
  };
  const gal = document.getElementById("gal");
  for (const im of r.images) {
    const res = await api(`/inspections/${id}/images/${im.id}/annotated`, { raw: true });
    const fig = document.createElement("figure"); fig.style.margin = 0;
    fig.innerHTML = `<img alt="Annotated tray photo" src="${URL.createObjectURL(await res.blob())}"><figcaption class="small muted">${im.onion_count} onions, scale: ${esc(im.calibration_method.replace(/_/g, " "))}${im.mm_per_pixel ? ", " + im.mm_per_pixel.toFixed(3) + " mm/px" : ""}</figcaption>`;
    gal.appendChild(fig);
  }
}

async function viewReports() {
  const rows = await api("/inspections");
  $app.innerHTML = shell("reports", `<div class="head"><h1>${isStaff() ? "Reports" : "My reports"}</h1></div><div class="panel">${inspectionTable(rows)}</div>`);
  wireRows();
}
async function viewBatches() {
  const rows = await api("/batches");
  $app.innerHTML = shell("batches", `<div class="head"><h1>${isStaff() ? "Batches" : "My batches"}</h1></div><div class="panel"><div class="scroll"><table><thead><tr><th>Batch</th><th>Farmer</th><th>Variety</th><th class="num">Kg</th><th>Latest result</th><th>Date</th></tr></thead><tbody>
  ${rows.map((b) => { const l = b.latest_inspection; return `<tr ${l ? `class="click" data-go="#/report/${l.id}"` : ""}><td>${esc(b.batch_code)}</td><td>${esc(b.farmer.name)}</td><td>${esc(b.variety)}</td><td class="num">${b.quantity_kg}</td><td>${l ? `<span class="pill ${l.decision}">${DECISION[l.decision]}</span> ${l.grade_a_pct}% Grade A` : '<span class="muted">Not inspected</span>'}</td><td>${fmtDate(b.created_at)}</td></tr>`; }).join("") || '<tr><td colspan="6" class="muted">No batches yet.</td></tr>'}</tbody></table></div></div>`);
  wireRows();
}
async function viewFarmers() {
  const rows = await api("/farmers");
  $app.innerHTML = shell("farmers", `<div class="head"><h1>Farmers</h1></div><div class="panel"><div class="scroll"><table><thead><tr><th>ID</th><th>Name</th><th>Village</th><th>Phone</th></tr></thead><tbody>
  ${rows.map((f) => `<tr><td>${esc(f.farmer_code)}</td><td>${esc(f.name)}</td><td>${esc(f.village)}</td><td>${esc(f.phone)}</td></tr>`).join("")}</tbody></table></div></div>`);
}

async function viewStandards() {
  const list = await api("/standards");
  const active = list.find((s) => s.is_active) || list[0];
  $app.innerHTML = shell("standards", `<div class="head"><div><h1>Quality standards</h1><p class="muted">The AI measures. These rules decide the grade. Publish a new version whenever the procurement specification changes; old reports keep the version they used.</p></div></div>
  <div class="grid g2"><div class="panel"><h2>Publish new version</h2><label for="sname">Name</label><input id="sname" value="${esc(active.name)}">
  <label for="scfg">Rules (JSON)</label><textarea id="scfg" class="json" spellcheck="false">${esc(JSON.stringify(active.config, null, 2))}</textarea>
  <div class="err" id="err"></div><button class="primary" id="pub">Publish and activate</button></div>
  <div class="panel"><h2>Versions</h2><table><thead><tr><th>Version</th><th>Name</th><th>Status</th><th></th></tr></thead><tbody>
  ${list.map((s) => `<tr><td>v${s.version}</td><td>${esc(s.name)}<br><span class="small muted">${fmtDate(s.created_at)}</span></td><td>${s.is_active ? '<span class="pill GRADE_A">Active</span>' : ""}</td><td>${s.is_active ? "" : `<button data-act="${s.id}">Activate</button>`}</td></tr>`).join("")}</tbody></table></div></div>`);
  document.getElementById("pub").onclick = async () => {
    try {
      const config = JSON.parse(document.getElementById("scfg").value);
      await api("/standards", { method: "POST", json: { name: document.getElementById("sname").value, config } });
      toast("New standard version is active"); viewStandards();
    } catch (e) { document.getElementById("err").textContent = e.message; }
  };
  document.querySelectorAll("[data-act]").forEach((b) => (b.onclick = async () => { await api(`/standards/${b.dataset.act}/activate`, { method: "POST" }); toast("Standard activated"); viewStandards(); }));
}

async function viewVerify(reportId) {
  const body = (inner) => ($app.innerHTML = `<div class="auth" style="max-width:560px"><div class="brand"><i></i>Kanda QA</div><div class="panel"><h1>Verify a report</h1>
    <form id="f" class="row" style="margin-top:10px"><input id="rid" placeholder="RPT-2609-A1B2C3" value="${esc(reportId || "")}" aria-label="Report ID"><button class="primary" style="flex:0 0 auto">Check</button></form>${inner}</div>
    <p class="small"><a href="#/">Back to sign in</a></p></div>`);
  let out = "";
  if (reportId) {
    try {
      const v = await api("/reports/verify/" + encodeURIComponent(reportId));
      out = `<div style="margin-top:16px"><span class="pill ${v.integrity_ok ? "GRADE_A" : "REJECTED"}">${v.integrity_ok ? "Record is unchanged" : "Record does not match its seal"}</span>
      <p><b>${esc(v.batch_code)}</b> - <span class="pill ${v.decision}">${DECISION[v.decision]}</span></p>
      <p class="muted small">Grade A ${v.grade_a_pct}%, URS ${v.urs_pct}% of ${v.total_onions} onions. ${esc(v.standard)}. Issued ${fmtDate(v.created_at)}.</p><div class="hash">${esc(v.integrity_hash)}</div></div>`;
    } catch (e) { out = `<div class="err">${esc(e.message)}</div>`; }
  }
  body(out);
  document.getElementById("f").onsubmit = (e) => { e.preventDefault(); location.hash = "#/verify/" + document.getElementById("rid").value.trim(); };
}

/* ---------- router ---------- */
async function render() {
  const [, route = "", arg] = location.hash.split("/");
  try {
    if (route === "verify") return await viewVerify(arg);
    if (route === "register") return viewAuth("register");
    if (!state.token) return viewAuth("login");
    const routes = { dashboard: viewDashboard, inspect: viewInspect, reports: viewReports, batches: viewBatches, farmers: viewFarmers, standards: viewStandards, report: () => viewReport(arg) };
    await (routes[route] || viewDashboard)();
    document.querySelectorAll("button[data-go]").forEach((b) => (b.onclick = () => (location.hash = b.dataset.go)));
  } catch (e) { toast(e.message); }
}
document.addEventListener("click", (e) => { if (e.target.id === "signout") signOut(); });
window.addEventListener("hashchange", () => { stopCamera(); render(); });
render();
