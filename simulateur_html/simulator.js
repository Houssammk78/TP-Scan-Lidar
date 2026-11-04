"use strict";

// All distances inside the application are metres. Imported LD06 coordinates
// stay local to their scan; the pose is applied only when drawing or exporting.
const $ = id => document.getElementById(id);
const canvas = $("map");
const ctx = canvas.getContext("2d");
const colors = ["#54d9e7", "#ffad66", "#a997ff", "#82db9a", "#ff779d", "#f3d271", "#7aa7ff", "#e5a8e4"];
const state = { scans: [], selected: null, nextId: 1, centerX: 0, centerY: 0,
  scale: 55, width: 0, height: 0, panning: false, lastX: 0, lastY: 0 };
const rad = deg => deg * Math.PI / 180;
const deg = angle => angle * 180 / Math.PI;
const round = (n, digits = 3) => Number(n.toFixed(digits));

function parseNumber(value) {
  if (value === undefined || value === null) return NaN;
  return Number(String(value).trim().replace(/\s/g, "").replace(",", "."));
}

function detectSeparator(line) {
  const counts = { ";": (line.match(/;/g) || []).length,
    ",": (line.match(/,/g) || []).length, "\t": (line.match(/\t/g) || []).length };
  return Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
}

function normalizeHeader(value) {
  return value.trim().toLowerCase().normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function column(headers, names) {
  for (const name of names) {
    const index = headers.indexOf(name);
    if (index >= 0) return index;
  }
  return -1;
}

function parseCSV(text, filename = "scan.csv") {
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter(line => line.trim());
  if (lines.length < 2) throw new Error("Le fichier est vide ou ne contient pas de points.");
  const separator = detectSeparator(lines[0]);
  const headers = lines[0].split(separator).map(normalizeHeader);
  let xi = column(headers, ["x_lib_mm", "x_local_mm", "x_mm", "x_lib_m", "x_local_m", "x_m", "x"]);
  let yi = column(headers, ["y_lib_mm", "y_local_mm", "y_mm", "y_lib_m", "y_local_m", "y_m", "y"]);
  const ai = column(headers, ["angle_deg", "angle", "theta_deg"]);
  const di = column(headers, ["dist_mm", "distance_mm", "dist_m", "distance_m", "distance"]);
  const ii = column(headers, ["intensity", "intensite", "quality"]);
  const pi = column(headers, ["point_index", "index", "id"]);
  const hasXY = xi >= 0 && yi >= 0;
  if (!hasXY && (ai < 0 || di < 0)) {
    // Also accept a plain six-column LD06 export without a header row.
    const first = lines[0].split(separator);
    if (first.length >= 6 && Number.isFinite(parseNumber(first[0])) &&
        Number.isFinite(parseNumber(first[4])) && Number.isFinite(parseNumber(first[5]))) {
      return parseCSV("point_index" + separator + "angle_deg" + separator + "dist_mm" +
        separator + "intensity" + separator + "x_lib_mm" + separator + "y_lib_mm\n" + text, filename);
    }
    throw new Error("Colonnes X/Y ou angle_deg + dist_mm introuvables.");
  }
  const mmXY = hasXY && !headers[xi].endsWith("_m") && headers[xi] !== "x";
  const mmD = di >= 0 && !headers[di].endsWith("_m") && headers[di] !== "distance";
  const points = [];
  let skipped = 0;
  for (let lineNo = 1; lineNo < lines.length; lineNo++) {
    const cells = lines[lineNo].split(separator);
    let x, y;
    if (hasXY) {
      x = parseNumber(cells[xi]) / (mmXY ? 1000 : 1);
      y = parseNumber(cells[yi]) / (mmXY ? 1000 : 1);
    } else {
      const distance = parseNumber(cells[di]) / (mmD ? 1000 : 1);
      const angle = rad(parseNumber(cells[ai]));
      x = distance * Math.cos(angle);
      y = distance * Math.sin(angle);
    }
    if (!Number.isFinite(x) || !Number.isFinite(y) ||
        Math.hypot(x, y) < 0.03 || Math.hypot(x, y) > 30) { skipped++; continue; }
    const index = pi >= 0 ? parseNumber(cells[pi]) : lineNo - 1;
    const intensity = ii >= 0 ? parseNumber(cells[ii]) : NaN;
    points.push({ x, y, index: Number.isFinite(index) ? index : lineNo - 1,
      intensity: Number.isFinite(intensity) ? intensity : null });
    if (points.length > 50000) throw new Error("Plus de 50 000 points : fichier trop grand pour cette page.");
  }
  if (points.length < 3) throw new Error("Moins de trois points valides.");
  points.sort((a, b) => a.index - b.index);
  return { name: filename, points, skipped, source: hasXY ? headers[xi] + " / " + headers[yi] : "polaire" };
}

function transform(p, pose) {
  const a = rad(pose.theta), c = Math.cos(a), s = Math.sin(a);
  return { x: pose.x + c * p.x - s * p.y, y: pose.y + s * p.x + c * p.y };
}

function sample(points, maxCount) {
  if (points.length <= maxCount) return points;
  const step = points.length / maxCount;
  return Array.from({ length: maxCount }, (_, i) => points[Math.floor(i * step)]);
}

function centroid(points) {
  let x = 0, y = 0;
  for (const p of points) { x += p.x; y += p.y; }
  return { x: x / points.length, y: y / points.length };
}

// A small spatial index keeps alignment responsive with ordinary LD06 files.
function spatialIndex(points, cell = 0.4) {
  const bins = new Map();
  for (const p of points) {
    const key = Math.floor(p.x / cell) + "," + Math.floor(p.y / cell);
    if (!bins.has(key)) bins.set(key, []);
    bins.get(key).push(p);
  }
  return { bins, cell };
}

function nearest(index, p, limit = 0.9) {
  const { bins, cell } = index;
  const cx = Math.floor(p.x / cell), cy = Math.floor(p.y / cell);
  const radius = Math.ceil(limit / cell);
  let best = limit * limit, target = null;
  for (let ix = cx - radius; ix <= cx + radius; ix++) {
    for (let iy = cy - radius; iy <= cy + radius; iy++) {
      const bucket = bins.get(ix + "," + iy);
      if (!bucket) continue;
      for (const q of bucket) {
        const dx = p.x - q.x, dy = p.y - q.y, d2 = dx * dx + dy * dy;
        if (d2 < best) { best = d2; target = q; }
      }
    }
  }
  return { target, d2: best };
}

function evaluate(source, index, pose) {
  let sum = 0, inliers = 0;
  for (const p of source) {
    const match = nearest(index, transform(p, pose), 0.9);
    sum += match.d2;
    if (match.d2 < 0.3 * 0.3) inliers++;
  }
  return { score: sum / source.length, overlap: inliers / source.length };
}

function fitRigid(pairs) {
  let sx = 0, sy = 0, tx = 0, ty = 0;
  for (const pair of pairs) {
    sx += pair.p.x; sy += pair.p.y;
    tx += pair.q.x; ty += pair.q.y;
  }
  const n = pairs.length;
  sx /= n; sy /= n; tx /= n; ty /= n;
  let dot = 0, cross = 0;
  for (const pair of pairs) {
    const px = pair.p.x - sx, py = pair.p.y - sy;
    const qx = pair.q.x - tx, qy = pair.q.y - ty;
    dot += px * qx + py * qy;
    cross += px * qy - py * qx;
  }
  const theta = Math.atan2(cross, dot);
  const c = Math.cos(theta), s = Math.sin(theta);
  return { x: tx - c * sx + s * sy, y: ty - s * sx - c * sy, theta: deg(theta) };
}

function refine(source, index, initial) {
  let pose = { ...initial };
  for (let iteration = 0; iteration < 24; iteration++) {
    const pairs = [];
    for (const p of source) {
      const match = nearest(index, transform(p, pose), iteration < 4 ? 1.0 : 0.6);
      if (match.target) pairs.push({ p, q: match.target, d2: match.d2 });
    }
    if (pairs.length < Math.max(8, source.length * 0.08)) break;
    pairs.sort((a, b) => a.d2 - b.d2);
    const kept = pairs.slice(0, Math.max(8, Math.floor(pairs.length * 0.75)));
    const next = fitRigid(kept);
    const delta = Math.hypot(next.x - pose.x, next.y - pose.y) +
      Math.abs(Math.atan2(Math.sin(rad(next.theta - pose.theta)),
                         Math.cos(rad(next.theta - pose.theta)))) * 0.1;
    pose = next;
    if (delta < 0.0005) break;
  }
  return pose;
}

function referencePoints(excluded) {
  return state.scans.filter(s => s !== excluded && s.visible)
    .flatMap(s => sample(s.points, 1200).map(p => transform(p, s.pose)));
}

function rebaseToFirst() {
  if (!state.scans.length) return;
  const origin = { ...state.scans[0].pose };
  const angle = rad(-origin.theta), c = Math.cos(angle), s = Math.sin(angle);
  for (const scan of state.scans) {
    const dx = scan.pose.x - origin.x, dy = scan.pose.y - origin.y;
    scan.pose = { x: c * dx - s * dy, y: s * dx + c * dy,
      theta: scan.pose.theta - origin.theta };
  }
}

function alignScan(scan) {
  const target = sample(referencePoints(scan), 4500);
  if (target.length < 12) return { pose: { x: 0, y: 0, theta: 0 }, overlap: 0 };
  const source = sample(scan.points, 320);
  const refCenter = centroid(target), srcCenter = centroid(source);
  const index = spatialIndex(target);
  const candidates = [];
  // Search the full angle range; the centroid offsets allow partial overlap.
  for (let angle = -180; angle < 180; angle += 15) {
    const c = Math.cos(rad(angle)), s = Math.sin(rad(angle));
    const baseX = refCenter.x - (c * srcCenter.x - s * srcCenter.y);
    const baseY = refCenter.y - (s * srcCenter.x + c * srcCenter.y);
    for (const dx of [-1.5, 0, 1.5]) {
      for (const dy of [-1.5, 0, 1.5]) {
        const pose = { x: baseX + dx, y: baseY + dy, theta: angle };
        const result = evaluate(source, index, pose);
        candidates.push({ pose, score: result.score });
      }
    }
  }
  candidates.sort((a, b) => a.score - b.score);
  let best = null;
  for (const item of candidates.slice(0, 6)) {
    const pose = refine(source, index, item.pose);
    const result = evaluate(source, index, pose);
    if (!best || result.score < best.score) best = { pose, ...result };
  }
  return best;
}

function worldBounds() {
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity, count = 0;
  for (const scan of state.scans) {
    if (!scan.visible) continue;
    for (const p of scan.points) {
      const q = transform(p, scan.pose);
      xmin = Math.min(xmin, q.x); xmax = Math.max(xmax, q.x);
      ymin = Math.min(ymin, q.y); ymax = Math.max(ymax, q.y); count++;
    }
  }
  return count ? { xmin, xmax, ymin, ymax, count } : null;
}

function fitView() {
  const b = worldBounds();
  if (!b || !state.width || !state.height) return;
  state.centerX = (b.xmin + b.xmax) / 2;
  state.centerY = (b.ymin + b.ymax) / 2;
  state.scale = Math.max(8, Math.min(160,
    Math.min((state.width - 90) / Math.max(2, b.xmax - b.xmin),
             (state.height - 90) / Math.max(2, b.ymax - b.ymin))));
  draw();
}

function screen(p) {
  return { x: state.width / 2 + (p.x - state.centerX) * state.scale,
    y: state.height / 2 - (p.y - state.centerY) * state.scale };
}

function draw() {
  if (!state.width || !state.height) return;
  ctx.clearRect(0, 0, state.width, state.height);
  ctx.fillStyle = "#0b1929"; ctx.fillRect(0, 0, state.width, state.height);
  const left = state.centerX - state.width / (2 * state.scale);
  const right = state.centerX + state.width / (2 * state.scale);
  const bottom = state.centerY - state.height / (2 * state.scale);
  const top = state.centerY + state.height / (2 * state.scale);
  const step = state.scale > 55 ? 1 : state.scale > 25 ? 2 : 5;
  ctx.font = "11px Segoe UI, sans-serif";
  ctx.lineWidth = 1;
  ctx.textAlign = "left";
  for (let x = Math.ceil(left / step) * step; x <= right; x += step) {
    const a = screen({ x, y: 0 });
    ctx.strokeStyle = x === 0 ? "#496780" : "#20364b";
    ctx.beginPath(); ctx.moveTo(a.x, 0); ctx.lineTo(a.x, state.height); ctx.stroke();
    ctx.fillStyle = "#7895ad"; ctx.fillText(String(x), a.x + 4, state.height - 12);
  }
  for (let y = Math.ceil(bottom / step) * step; y <= top; y += step) {
    const a = screen({ x: 0, y });
    ctx.strokeStyle = y === 0 ? "#496780" : "#20364b";
    ctx.beginPath(); ctx.moveTo(0, a.y); ctx.lineTo(state.width, a.y); ctx.stroke();
    ctx.fillStyle = "#7895ad"; ctx.fillText(String(y), 9, a.y - 4);
  }
  for (const scan of state.scans) {
    if (!scan.visible) continue;
    const selected = state.selected === scan.id;
    if ($("contours").checked) {
      ctx.strokeStyle = scan.color; ctx.lineWidth = selected ? 2.6 : 1.8;
      ctx.globalAlpha = selected ? .88 : .65;
      for (let i = 1; i < scan.points.length; i++) {
        const p = scan.points[i - 1], q = scan.points[i];
        if (q.index - p.index > 2 || Math.hypot(q.x - p.x, q.y - p.y) > .35) continue;
        const a = screen(transform(p, scan.pose)), b = screen(transform(q, scan.pose));
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
    ctx.fillStyle = scan.color;
    for (const p of scan.points) {
      const q = screen(transform(p, scan.pose));
      if (q.x < -5 || q.x > state.width + 5 || q.y < -5 || q.y > state.height + 5) continue;
      ctx.beginPath(); ctx.arc(q.x, q.y, selected ? 2.9 : 2.3, 0, Math.PI * 2); ctx.fill();
    }
    const origin = screen(scan.pose);
    ctx.strokeStyle = scan.color; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(origin.x, origin.y, selected ? 8 : 6, 0, Math.PI * 2); ctx.stroke();
    const heading = rad(scan.pose.theta);
    ctx.beginPath(); ctx.moveTo(origin.x, origin.y);
    ctx.lineTo(origin.x + Math.cos(heading) * 17, origin.y - Math.sin(heading) * 17); ctx.stroke();
    ctx.fillStyle = "#eaf5ff"; ctx.fillText(String(scan.id), origin.x + 10, origin.y - 9);
  }
}

function resize() {
  const rect = canvas.getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
  state.width = rect.width; state.height = rect.height;
  canvas.width = Math.round(rect.width * ratio); canvas.height = Math.round(rect.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  draw();
}

function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}

function select(id) {
  state.selected = id;
  const scan = state.scans.find(s => s.id === id);
  $("selectionLabel").textContent = scan ? scan.name +
    (scan === state.scans[0] ? " · repère fixe" : "") : "Sélectionne un scan dans la liste.";
  for (const key of ["poseX", "poseY", "poseTheta"])
    $(key).disabled = !scan || scan === state.scans[0];
  $("resetPose").disabled = !scan || scan === state.scans[0];
  if (scan) {
    $("poseX").value = round(scan.pose.x, 3);
    $("poseY").value = round(scan.pose.y, 3);
    $("poseTheta").value = round(scan.pose.theta, 2);
  }
  $("quality").textContent = scan && scan !== state.scans[0] && scan.overlap !== null
    ? "Recouvrement estimé : " + Math.round(scan.overlap * 100) + "%" : "";
  renderList(); draw();
}

function renderList() {
  const list = $("scanList"); list.replaceChildren();
  if (!state.scans.length) {
    const empty = document.createElement("p"); empty.className = "empty-list";
    empty.textContent = "Aucun scan chargé."; list.append(empty); return;
  }
  for (const scan of state.scans) {
    const row = document.createElement("div");
    row.className = "scan-row" + (scan.id === state.selected ? " selected" : "");
    const title = document.createElement("div"); title.className = "scan-title";
    const dot = document.createElement("span"); dot.className = "swatch"; dot.style.background = scan.color;
    const name = document.createElement("strong"); name.textContent = scan.name;
    name.title = "Sélectionner ce scan"; name.addEventListener("click", () => select(scan.id));
    title.append(dot, name);
    const meta = document.createElement("div"); meta.className = "scan-meta";
    meta.textContent = scan.points.length + " points · " + scan.source +
      (scan === state.scans[0] ? " · référence" :
        " · recouvrement " + (scan.overlap === null ? "—" : Math.round(scan.overlap * 100) + "%"));
    const controls = document.createElement("div"); controls.className = "scan-controls";
    const visible = document.createElement("input"); visible.type = "checkbox";
    visible.className = "visibility"; visible.checked = scan.visible;
    visible.title = "Afficher ou masquer"; visible.setAttribute("aria-label", "Afficher " + scan.name);
    visible.addEventListener("change", () => { scan.visible = visible.checked; update(); });
    const choose = document.createElement("button"); choose.className = "icon-button";
    choose.textContent = scan === state.scans[0] ? "Voir" : "Corriger";
    choose.addEventListener("click", () => select(scan.id));
    const remove = document.createElement("button"); remove.className = "icon-button remove";
    remove.textContent = "Retirer"; remove.addEventListener("click", () => {
      const wasReference = scan === state.scans[0];
      state.scans = state.scans.filter(s => s !== scan);
      if (wasReference) rebaseToFirst();
      if (state.selected === scan.id) state.selected = state.scans[0]?.id ?? null;
      select(state.selected); fitView(); update();
    });
    controls.append(visible, choose, remove); row.append(title, meta, controls); list.append(row);
  }
}

function update() {
  const bounds = worldBounds();
  $("scanCount").textContent = String(state.scans.length);
  $("pointCount").textContent = bounds ? bounds.count.toLocaleString("fr-FR") : "0";
  $("visibleCount").textContent = String(state.scans.filter(s => s.visible).length);
  $("bounds").textContent = bounds ?
    (bounds.xmax - bounds.xmin).toFixed(1) + " × " + (bounds.ymax - bounds.ymin).toFixed(1) + " m" : "—";
  $("emptyMap").hidden = Boolean(state.scans.length);
  $("alignAll").disabled = state.scans.length < 2;
  for (const id of ["clear", "fit", "exportCsv", "exportPoses", "exportPng"])
    $(id).disabled = !state.scans.length;
  renderList(); draw();
}

async function importFiles(files) {
  const candidates = Array.from(files).filter(f => f.name.toLowerCase().endsWith(".csv"));
  if (!candidates.length) { status("Choisis au moins un fichier .csv.", true); return; }
  const errors = [];
  for (const file of candidates) {
    try {
      const parsed = parseCSV(await file.text(), file.name);
      const scan = { id: state.nextId++, ...parsed, visible: true,
        pose: { x: 0, y: 0, theta: 0 }, overlap: null,
        color: colors[(state.nextId - 2) % colors.length] };
      if (state.scans.length) {
        const result = alignScan(scan);
        scan.pose = result.pose; scan.overlap = result.overlap;
      }
      state.scans.push(scan);
      select(scan.id); update(); fitView();
      await new Promise(resolve => setTimeout(resolve, 0));
    } catch (error) { errors.push(file.name + " : " + error.message); }
  }
  status(errors.length ? errors.join(" · ") :
    candidates.length + " fichier(s) chargé(s). Vérifie l'alignement sur les murs communs.",
    errors.length > 0);
}

function reAlignAll() {
  if (state.scans.length < 2) return;
  const scans = state.scans.slice();
  state.scans = [scans[0]];
  for (const scan of scans.slice(1)) {
    const result = alignScan(scan); scan.pose = result.pose; scan.overlap = result.overlap;
    state.scans.push(scan);
  }
  select(state.selected); update(); fitView();
  status("Alignement recalculé. Vérifie les murs superposés avant d'exporter.");
}

function csvCell(value) { return String(value).replace(".", ","); }
function download(name, body, type = "text/csv;charset=utf-8") {
  const data = type.startsWith("text/") ? "\uFEFF" + body : body;
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement("a"); a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  status(name + " téléchargé.");
}

function exportMerged() {
  const rows = ["scan;point_index;x_m;y_m;x_local_m;y_local_m;intensity"];
  for (const scan of state.scans) {
    if (!scan.visible) continue;
    for (const p of scan.points) {
      const q = transform(p, scan.pose);
      rows.push([scan.name, p.index, csvCell(q.x.toFixed(4)), csvCell(q.y.toFixed(4)),
        csvCell(p.x.toFixed(4)), csvCell(p.y.toFixed(4)), p.intensity ?? ""].join(";"));
    }
  }
  download("piece_fusionnee.csv", rows.join("\r\n"));
}

function exportPoses() {
  const rows = ["scan;x_estime_m;y_estime_m;rotation_estimee_deg;points;recouvrement_estime_pct;reference"];
  for (const scan of state.scans) {
    rows.push([scan.name, csvCell(scan.pose.x.toFixed(4)), csvCell(scan.pose.y.toFixed(4)),
      csvCell(scan.pose.theta.toFixed(2)), scan.points.length,
      scan.overlap === null ? "" : csvCell((scan.overlap * 100).toFixed(1)),
      scan === state.scans[0] ? "oui" : "non"].join(";"));
  }
  download("poses_estimees.csv", rows.join("\r\n"));
}

function exportImage() {
  canvas.toBlob(blob => {
    if (!blob) { status("Impossible de créer l'image.", true); return; }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "plan_piece_lidar.png";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status("plan_piece_lidar.png téléchargé.");
  }, "image/png");
}

$("files").addEventListener("change", event => {
  importFiles(event.target.files); event.target.value = "";
});
for (const eventName of ["dragenter", "dragover"]) {
  $("dropzone").addEventListener(eventName, event => {
    event.preventDefault(); $("dropzone").classList.add("dragover");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  $("dropzone").addEventListener(eventName, event => {
    event.preventDefault(); $("dropzone").classList.remove("dragover");
    if (eventName === "drop") importFiles(event.dataTransfer.files);
  });
}
window.addEventListener("dragover", event => event.preventDefault());
window.addEventListener("drop", event => event.preventDefault());
$("alignAll").addEventListener("click", reAlignAll);
$("clear").addEventListener("click", () => {
  state.scans = []; state.selected = null; state.nextId = 1;
  select(null); update(); status("Tous les scans ont été effacés.");
});
$("fit").addEventListener("click", fitView);
$("contours").addEventListener("change", draw);
for (const [id, key] of [["poseX", "x"], ["poseY", "y"], ["poseTheta", "theta"]]) {
  $(id).addEventListener("input", event => {
    const scan = state.scans.find(s => s.id === state.selected);
    const value = Number(event.target.value);
    if (!scan || !Number.isFinite(value) || scan === state.scans[0]) return;
    scan.pose[key] = value; scan.overlap = null; $("quality").textContent = "Pose corrigée manuellement"; update();
  });
}
$("resetPose").addEventListener("click", () => {
  const scan = state.scans.find(s => s.id === state.selected);
  if (!scan || scan === state.scans[0]) return;
  scan.pose = { x: 0, y: 0, theta: 0 }; scan.overlap = null;
  select(scan.id); update(); fitView();
});
$("exportCsv").addEventListener("click", exportMerged);
$("exportPoses").addEventListener("click", exportPoses);
$("exportPng").addEventListener("click", exportImage);
canvas.addEventListener("pointerdown", event => {
  state.panning = true; state.lastX = event.clientX; state.lastY = event.clientY;
  canvas.setPointerCapture(event.pointerId);
});
canvas.addEventListener("pointermove", event => {
  if (!state.panning) return;
  state.centerX -= (event.clientX - state.lastX) / state.scale;
  state.centerY += (event.clientY - state.lastY) / state.scale;
  state.lastX = event.clientX; state.lastY = event.clientY; draw();
});
canvas.addEventListener("pointerup", () => { state.panning = false; });
canvas.addEventListener("pointercancel", () => { state.panning = false; });
canvas.addEventListener("wheel", event => {
  event.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const px = event.clientX - rect.left, py = event.clientY - rect.top;
  const worldX = state.centerX + (px - state.width / 2) / state.scale;
  const worldY = state.centerY - (py - state.height / 2) / state.scale;
  state.scale = Math.max(5, Math.min(500, state.scale * (event.deltaY < 0 ? 1.12 : 1 / 1.12)));
  state.centerX = worldX - (px - state.width / 2) / state.scale;
  state.centerY = worldY + (py - state.height / 2) / state.scale;
  draw();
}, { passive: false });
window.addEventListener("resize", resize);
window.LidarRoom = { parseCSV, alignScan, importFiles, state, exportMerged, exportPoses };
requestAnimationFrame(resize);
