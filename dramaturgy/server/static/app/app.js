"use strict";

// UI chrome labels for the app shell. ui_lang picks the column; missing keys
// fall back to the data-i default text.
const I18N = {
  ja: {
    "btn.save_config": "保存",
    "init.run": "Claudeで一括初期化",
    "init.running": "一括初期化を実行中…", "init.done": "一括初期化が完了しました",
    "job.running": "実行中…", "job.done": "完了", "job.error": "エラー", "job.idle": "応答待ち",
    "viewer.title": "意味地図プレビュー", "viewer.refresh": "更新",
    "viewer.pin_hint": "各項目の + をクリックして指摘を追加します。",
    "viewer.hide_queue": "キューを隠す", "viewer.show_queue": "キューを表示",
    "rv.queue": "指摘キュー",
    "rv.kind.reframe": "再整理", "rv.kind.audit": "検査", "rv.kind.proposal": "将来提案",
    "rv.kindhelp.reframe": "指摘を是として、正本の意味地図を修正します。",
    "rv.kindhelp.audit": "正本は変えず、矛盾・説明できないパターンを調査して記録します。",
    "rv.kindhelp.proposal": "現状とは別に「今後こう変えたい」を提案として記録します。",
    "rv.add": "キューに追加", "rv.add_run": "追加して実行",
    "rv.run": "実行", "rv.rerun": "再実行", "rv.delete": "削除",
    "rv.run_all": "キューを実行",
    "rv.continue_session": "Claudeセッションを継続する",
    "rv.no_findings": "まだ指摘はありません。プレビューの + から追加します。",
    "rv.no_map": "先に「Claudeで一括初期化」で意味地図を生成してください。",
    "saved": "保存しました", "save_failed": "保存に失敗",
  },
  en: {
    "btn.save_config": "Save",
    "init.run": "Initialize all with Claude",
    "init.running": "Initializing…", "init.done": "Initialization complete",
    "job.running": "running…", "job.done": "done", "job.error": "error", "job.idle": "awaiting response",
    "viewer.title": "Meaning map preview", "viewer.refresh": "Refresh",
    "viewer.pin_hint": "Click + on any item to add a finding.",
    "viewer.hide_queue": "Hide queue", "viewer.show_queue": "Show queue",
    "rv.queue": "Finding queue",
    "rv.kind.reframe": "reframe", "rv.kind.audit": "audit", "rv.kind.proposal": "proposal",
    "rv.kindhelp.reframe": "Accept the remark and edit the canonical meaning map.",
    "rv.kindhelp.audit": "Leave the map unchanged; investigate contradictions / cases it can't explain.",
    "rv.kindhelp.proposal": "Record a future change separately from the as-is map.",
    "rv.add": "Add to queue", "rv.add_run": "Add & run",
    "rv.run": "Run", "rv.rerun": "Re-run", "rv.delete": "Delete",
    "rv.run_all": "Run queued",
    "rv.continue_session": "continue Claude session",
    "rv.no_findings": "No findings yet. Add one with the + in the preview.",
    "rv.no_map": "Generate the map first with “Initialize all with Claude”.",
    "saved": "Saved", "save_failed": "Save failed",
  },
};

let UI_LANG = "ja";
const t = (key) => (I18N[UI_LANG] && I18N[UI_LANG][key]) || key;

function applyI18n() {
  document.querySelectorAll("[data-i]").forEach((el) => {
    const key = el.getAttribute("data-i");
    if (I18N[UI_LANG] && I18N[UI_LANG][key]) el.textContent = I18N[UI_LANG][key];
  });
}

// ---- tiny fetch helpers (relative paths, proxy-safe) -------------------
const APP_BASE = location.pathname.replace(/[^/]*$/, "");
const ROOT_BASE = APP_BASE.replace(/app\/$/, "");
function apiUrl(path) { return ROOT_BASE + path.replace(/^\//, ""); }

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const resp = await fetch(apiUrl(path), opts);
  const text = await resp.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  return { status: resp.status, data };
}

// ---- state -------------------------------------------------------------
let STATE = null;

async function refreshState() {
  const { data } = await api("GET", "/api/state");
  STATE = data;
  document.getElementById("repo-info").textContent = data.repo_root;
  UI_LANG = data.config.ui_lang || "ja";
  document.getElementById("ui-lang").value = UI_LANG;
  document.getElementById("content-lang").value = data.config.content_lang || "ja";
  applyI18n();
  return data;
}

// ---- one-shot full initialization --------------------------------------
async function runInit() {
  const btn = document.getElementById("run-init");
  btn.disabled = true;
  const { status, data } = await api("POST", "/api/jobs/init", {});
  if (status !== 202) {
    showJob("init-job", { status: "error", error: data.error });
    btn.disabled = false;
    return;
  }
  pollJob(data.job_id, "init-job", async () => {
    await refreshState();
    refreshView();
    loadFindings();
  }, () => { btn.disabled = false; });
}

// ---- job polling -------------------------------------------------------
const SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"];

function fmtDuration(sec) {
  sec = Math.round(sec || 0);
  const m = Math.floor(sec / 60), s = sec % 60;
  return m ? `${m}m${String(s).padStart(2, "0")}s` : `${s}s`;
}

function liveStats(job, frame) {
  const spin = SPINNER[frame % SPINNER.length];
  const bits = [`${spin} ${t("job.running")}`, `${fmtDuration(job.elapsed_sec)}`];
  if (job.pid) bits.push(`pid ${job.pid}`);
  if (job.process) {
    bits.push(`CPU ${job.process.cpu_percent}%`);
    bits.push(`${job.process.rss_mb}MB`);
  }
  if (job.idle_sec >= 8) bits.push(`${t("job.idle")} ${fmtDuration(job.idle_sec)}`);
  return bits.join(" · ");
}

function showJob(elId, job, frame = 0) {
  const el = document.getElementById(elId);
  if (!el) return;
  const lines = (job.progress || []).map((l) => `<div class="line">${escapeHtml(l)}</div>`).join("");
  const head = job.status === "running"
    ? `<div class="spin">${escapeHtml(liveStats(job, frame))}</div>`
    : job.status === "done"
      ? `<div>${t("job.done")} · ${fmtDuration(job.elapsed_sec)}${job.session_id ? " · " + job.session_id : ""}</div>`
      : job.status === "error" || job.status === "aborted"
        ? `<div class="status err">${t("job.error")}: ${escapeHtml(job.error || job.status)}</div>`
        : "";
  el.innerHTML = head + lines;
}

function pollJob(jobId, elId, onDone, onEnd) {
  let since = 0, frame = 0, last = null;
  const acc = { progress: [] };
  const animate = setInterval(() => {
    if (last && last.status === "running") {
      frame += 1;
      showJob(elId, { ...last, progress: acc.progress }, frame);
    }
  }, 300);
  const tick = async () => {
    let data;
    try { ({ data } = await api("GET", `/api/jobs/${jobId}?since=${since}`)); }
    catch { setTimeout(tick, 1500); return; }
    acc.progress.push(...(data.progress || []));
    since = data.progress_total;
    last = data;
    showJob(elId, { ...data, progress: acc.progress }, frame);
    if (["done", "error", "aborted"].includes(data.status)) {
      clearInterval(animate);
      if (data.status === "done" && onDone) onDone();
      if (onEnd) onEnd(data.status);
      return;
    }
    setTimeout(tick, 1200);
  };
  tick();
  return () => clearInterval(animate);
}

// Promise wrapper used by the "run queued" loop (sequential).
function pollJobDone(jobId, elId) {
  return new Promise((resolve) => {
    pollJob(jobId, elId, null, (status) => resolve(status));
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

// ---- inline finding popover --------------------------------------------
let POP_TARGET = null;   // {target_type, target_id, target_name}

function currentKind() {
  const r = document.querySelector('input[name="rvkind"]:checked');
  return r ? r.value : "reframe";
}
function updateKindHelp() {
  document.getElementById("rv-kind-help").textContent = t("rv.kindhelp." + currentKind());
}

function openPopover(target) {
  POP_TARGET = target;
  const base = `${target.target_name || target.target_id} (${target.target_type})`;
  document.getElementById("pop-target").textContent =
    target.field_label ? `${base} › ${target.field_label}` : base;
  document.getElementById("rv-comment").value = "";
  updateKindHelp();
  const pop = document.getElementById("rv-pop");
  pop.hidden = false;
  document.getElementById("rv-comment").focus();
}
function closePopover() {
  document.getElementById("rv-pop").hidden = true;
  POP_TARGET = null;
}

async function submitFinding(thenRun) {
  if (!POP_TARGET) return;
  const comment = document.getElementById("rv-comment").value.trim();
  if (!comment) return;
  const { status, data } = await api("POST", "/api/review/findings", {
    ...POP_TARGET, kind: currentKind(), comment,
  });
  if (status !== 201) { alert(data.error || "error"); return; }
  closePopover();
  setQueueVisible(true);   // make sure the new finding is visible
  await loadFindings();
  if (thenRun) runFinding(data.id);
}

// ---- finding queue -----------------------------------------------------
const KIND_CLASS = { reframe: "k-reframe", audit: "k-audit", proposal: "k-proposal" };

async function loadFindings() {
  const { status, data } = await api("GET", "/api/review/findings");
  const list = document.getElementById("rv-list");
  const empty = document.getElementById("queue-empty");
  const hasMap = STATE && STATE.meaning_map;
  empty.textContent = hasMap ? t("rv.no_findings") : t("rv.no_map");
  if (status !== 200) { list.innerHTML = ""; empty.hidden = false; return; }
  const findings = data.findings || [];
  list.innerHTML = "";
  empty.hidden = findings.length > 0;
  findings.forEach((f) => list.appendChild(findingCard(f)));
}

function findingCard(f) {
  const card = document.createElement("div");
  card.className = "rv-card";
  const ran = f.status === "done" || f.status === "error";
  const scope = f.field_label
    ? ` <span class="muted tiny">› ${escapeHtml(f.field_label)}</span>` : "";
  card.innerHTML =
    `<div class="rv-head">
       <span class="badge ${KIND_CLASS[f.kind] || ""}">${escapeHtml(t("rv.kind." + f.kind))}</span>
       <b>${escapeHtml(f.target_name || f.target_id)}</b>${scope}
       <span class="muted tiny">${escapeHtml(f.status)}</span>
     </div>
     <div class="rv-comment">${escapeHtml(f.comment)}</div>`;
  const job = document.createElement("div");
  job.className = "job"; job.id = "rvjob-" + f.id;
  card.appendChild(job);

  if (f.result) {
    const r = document.createElement("div");
    r.className = "muted tiny"; r.textContent = "→ " + f.result;
    card.appendChild(r);
  }
  if (f.kind === "audit" && f.audit_result) {
    const pre = document.createElement("pre");
    pre.className = "out"; pre.style.maxHeight = "160px";
    pre.textContent = JSON.stringify(f.audit_result, null, 2);
    card.appendChild(pre);
  }
  if (f.kind === "proposal" && f.proposal_ref) {
    const r = document.createElement("div");
    r.className = "muted tiny"; r.textContent = f.proposal_ref;
    card.appendChild(r);
  }

  const row = document.createElement("div");
  row.className = "row";
  const run = document.createElement("button");
  run.className = "claude";
  run.textContent = ran ? t("rv.rerun") : t("rv.run");
  run.onclick = () => runFinding(f.id);
  const del = document.createElement("button");
  del.textContent = t("rv.delete");
  del.onclick = async () => { await api("DELETE", "/api/review/findings/" + f.id); loadFindings(); };
  row.appendChild(run); row.appendChild(del);
  card.appendChild(row);
  return card;
}

function continueSession() {
  return document.getElementById("rv-continue").checked;
}

async function runFinding(fid) {
  const { status, data } = await api(
    "POST", "/api/review/findings/" + fid + "/run", { continue_session: continueSession() });
  if (status !== 202) { showJob("rvjob-" + fid, { status: "error", error: data.error }); return; }
  await pollJobDone(data.job_id, "rvjob-" + fid);
  await loadFindings();
  refreshView();   // reframe may have changed the map
}

async function runAllQueued() {
  const { data } = await api("GET", "/api/review/findings");
  const open = (data.findings || []).filter((f) => f.status === "open");
  const btn = document.getElementById("rv-run-all");
  btn.disabled = true;
  // Sequential so a continued session keeps order and we don't hammer Claude.
  for (const f of open) {
    const { status, data: r } = await api(
      "POST", "/api/review/findings/" + f.id + "/run",
      { continue_session: continueSession() });
    if (status !== 202) { showJob("rvjob-" + f.id, { status: "error", error: r.error }); continue; }
    await pollJobDone(r.job_id, "rvjob-" + f.id);
    await loadFindings();
    refreshView();
  }
  btn.disabled = false;
}

// ---- viewer ------------------------------------------------------------
function refreshView() {
  const frame = document.getElementById("view-frame");
  frame.src = apiUrl("/api/view") + "?_=" + Date.now();
}

function setQueueVisible(visible) {
  document.getElementById("queue").hidden = !visible;
  document.getElementById("toggle-queue").textContent =
    visible ? t("viewer.hide_queue") : t("viewer.show_queue");
}
function toggleQueue() {
  setQueueVisible(document.getElementById("queue").hidden);
}

// ---- config ------------------------------------------------------------
async function saveConfig() {
  const body = {
    ...STATE.config,
    ui_lang: document.getElementById("ui-lang").value,
    content_lang: document.getElementById("content-lang").value,
  };
  await api("PUT", "/api/config", body);
  await refreshState();
  refreshView();
}

// ---- wire up -----------------------------------------------------------
function init() {
  document.getElementById("run-init").onclick = runInit;
  document.getElementById("refresh-view").onclick = refreshView;
  document.getElementById("toggle-queue").onclick = toggleQueue;
  document.getElementById("save-config").onclick = saveConfig;
  document.getElementById("rv-run-all").onclick = runAllQueued;
  document.getElementById("rv-add").onclick = () => submitFinding(false);
  document.getElementById("rv-add-run").onclick = () => submitFinding(true);
  document.getElementById("pop-close").onclick = closePopover;
  document.querySelectorAll('input[name="rvkind"]').forEach(
    (r) => (r.onchange = updateKindHelp));

  // The preview iframe asks us (via postMessage) to open the popover when a
  // + pin is clicked inside it.
  window.addEventListener("message", (ev) => {
    const d = ev.data;
    if (d && d.source === "dramaturgy-review") {
      openPopover({ target_type: d.target_type, target_id: d.target_id,
        target_name: d.target_name, field: d.field || "",
        field_label: d.field_label || "" });
    }
  });

  refreshState().then(() => { refreshView(); loadFindings(); });
}

document.addEventListener("DOMContentLoaded", init);
