"use strict";

// UI chrome labels for the app shell. ui_lang picks the column; missing keys
// fall back to the data-i default text.
const I18N = {
  ja: {
    "btn.save_config": "設定保存",
    "dev.toggle": "開発者モード",
    "init.run": "全体解析",
    "init.instr_toggle": "解析指示設定",
    "init.instr_label": "Claudeへの追加指示（リポジトリごとに保存し、毎回の全体解析で再利用されます）:",
    "init.instr_save": "指示を保存",
    "init.effort_label": "Claudeの思考量",
    "init.running": "全体解析を実行中…", "init.done": "全体解析が完了しました",
    "job.running": "実行中…", "job.done": "完了", "job.error": "エラー", "job.idle": "応答待ち",
    "viewer.title": "意味地図プレビュー", "viewer.refresh": "資料更新",
    "viewer.export": "HTMLエクスポート", "export.failed": "書き出しに失敗しました",
    "viewer.pin_hint": "各項目の + をクリックして指摘を追加します。",
    "viewer.hide_queue": "指摘を隠す", "viewer.show_queue": "指摘を表示",
    "rv.queue": "指摘キュー",
    "rv.kind.reframe": "再整理", "rv.kind.audit": "検査", "rv.kind.proposal": "将来提案",
    "rv.kindhelp.reframe": "指摘を是として、正本の意味地図を修正します。",
    "rv.kindhelp.audit": "正本は変えず、矛盾・説明できないパターンを調査して記録します。",
    "rv.kindhelp.proposal": "現状とは別に「今後こう変えたい」を提案として記録します。",
    "rv.add": "キューに追加",
    "rv.rerun": "再実行", "rv.delete": "削除",
    "rv.autorun_hint": "指摘は順番に自動実行されます。",
    "rv.status.open": "待機中", "rv.status.running": "実行中",
    "rv.status.done": "完了", "rv.status.error": "エラー",
    "rv.continue_session": "Claudeセッションを継続する",
    "rv.no_findings": "まだ指摘はありません。プレビューの + から追加します。",
    "rv.no_map": "先に「Claudeで一括初期化」で意味地図を生成してください。",
    "saved": "保存しました", "save_failed": "保存に失敗",
    "tag.help": "この概念データのタグを編集します。語彙タグをクリックで切替、または自由入力（カンマ/空白区切り）。",
    "tag.save": "タグを保存", "tag.manage": "語彙を管理",
    "tag.manage_prompt": "タグ語彙を編集（1行1タグ。「名前 | グループ | 説明」、グループ・説明は省略可）:",
  },
  en: {
    "btn.save_config": "Save settings",
    "dev.toggle": "Developer mode",
    "init.run": "Analyze all",
    "init.instr_toggle": "Analysis instructions",
    "init.instr_label": "Additional instructions for Claude (saved per repository, reused on every analysis):",
    "init.instr_save": "Save instructions",
    "init.effort_label": "Claude effort",
    "init.running": "Analyzing…", "init.done": "Analysis complete",
    "job.running": "running…", "job.done": "done", "job.error": "error", "job.idle": "awaiting response",
    "viewer.title": "Meaning map preview", "viewer.refresh": "Refresh map",
    "viewer.export": "Export HTML", "export.failed": "Export failed",
    "viewer.pin_hint": "Click + on any item to add a finding.",
    "viewer.hide_queue": "Hide findings", "viewer.show_queue": "Show findings",
    "rv.queue": "Finding queue",
    "rv.kind.reframe": "reframe", "rv.kind.audit": "audit", "rv.kind.proposal": "proposal",
    "rv.kindhelp.reframe": "Accept the remark and edit the canonical meaning map.",
    "rv.kindhelp.audit": "Leave the map unchanged; investigate contradictions / cases it can't explain.",
    "rv.kindhelp.proposal": "Record a future change separately from the as-is map.",
    "rv.add": "Add to queue",
    "rv.rerun": "Re-run", "rv.delete": "Delete",
    "rv.autorun_hint": "Findings run automatically, in order.",
    "rv.status.open": "queued", "rv.status.running": "running",
    "rv.status.done": "done", "rv.status.error": "error",
    "rv.continue_session": "continue Claude session",
    "rv.no_findings": "No findings yet. Add one with the + in the preview.",
    "rv.no_map": "Generate the map first with “Initialize all with Claude”.",
    "saved": "Saved", "save_failed": "Save failed",
    "tag.help": "Edit this concept's tags. Click a vocabulary tag to toggle it, or type your own (comma/space separated).",
    "tag.save": "Save tags", "tag.manage": "manage vocabulary",
    "tag.manage_prompt": "Edit the tag vocabulary, one per line: \"name | group | description\" (group/description optional):",
  },
};

let UI_LANG = "ja";
const t = (key) => (I18N[UI_LANG] && I18N[UI_LANG][key]) || key;

// ---- developer mode ----------------------------------------------------
// Hides developer-facing items (code refs / APIs / screens / validation, and
// the generation controls) for non-developers. Persisted locally so it
// sticks across reloads. The preview iframe mirrors it via ?dev= and a
// postMessage toggle. The finding queue stays usable in either mode.
let DEV_MODE = localStorage.getItem("dramaturgy.dev") === "1";

function applyDevMode() {
  document.body.classList.toggle("dev", DEV_MODE);
  const btn = document.getElementById("toggle-dev");
  if (btn) btn.setAttribute("aria-pressed", DEV_MODE ? "true" : "false");
  // Tell the preview iframe to show/hide its developer items live.
  const frame = document.getElementById("view-frame");
  if (frame && frame.contentWindow) {
    frame.contentWindow.postMessage(
      { source: "dramaturgy-shell", type: "dev-mode", on: DEV_MODE }, "*");
  }
}

function toggleDevMode() {
  DEV_MODE = !DEV_MODE;
  localStorage.setItem("dramaturgy.dev", DEV_MODE ? "1" : "0");
  applyDevMode();
}

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

// ---- init instructions + effort (repo-specific, reused across runs) ----
async function loadInitInstructions() {
  const { status, data } = await api("GET", "/api/init-instructions");
  if (status !== 200) return;
  document.getElementById("init-instr").value = data.instructions || "";
  const sel = document.getElementById("init-effort");
  if (sel && !sel.options.length) {
    (data.effort_levels || ["low", "medium", "high", "xhigh", "max"])
      .forEach((lv) => sel.add(new Option(lv, lv)));
  }
  if (sel && data.effort) sel.value = data.effort;
}

async function saveInitInstructions() {
  const text = document.getElementById("init-instr").value;
  const effort = document.getElementById("init-effort").value;
  const { status } = await api("PUT", "/api/init-instructions",
                               { instructions: text, effort });
  const el = document.getElementById("init-instr-status");
  el.textContent = status === 200 ? t("saved") : t("save_failed");
  el.className = status === 200 ? "status" : "status err";
  setTimeout(() => (el.textContent = ""), 1500);
}

function toggleInitInstructions() {
  const bar = document.getElementById("init-instr-bar");
  bar.hidden = !bar.hidden;
}

// ---- one-shot full initialization --------------------------------------
async function runInit() {
  const btn = document.getElementById("run-init");
  btn.disabled = true;
  // Send the current textarea + effort so an edit takes effect even if not yet
  // saved; the server also persists them for reuse.
  const instructions = document.getElementById("init-instr").value;
  const effort = document.getElementById("init-effort").value;
  const { status, data } = await api("POST", "/api/jobs/init",
                                     { instructions, effort });
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

async function submitFinding() {
  if (!POP_TARGET) return;
  const comment = document.getElementById("rv-comment").value.trim();
  if (!comment) return;
  const { status, data } = await api("POST", "/api/review/findings", {
    ...POP_TARGET, kind: currentKind(), comment,
  });
  if (status !== 201) { alert(data.error || "error"); return; }
  closePopover();
  setQueueVisible(true);   // make sure the new finding is visible
  // The server auto-runs queued findings; loadFindings starts the poll loop.
  await loadFindings();
}

// ---- finding queue -----------------------------------------------------
const KIND_CLASS = { reframe: "k-reframe", audit: "k-audit", proposal: "k-proposal" };
let RV_REFRESH = null;   // periodic refresh timer while the queue is active
let RV_SIG = null;       // signature of the rendered list, to avoid redraws

// Card content that, when unchanged, means we must NOT rebuild the list —
// otherwise the periodic refresh would wipe the live progress element that
// pollJob writes into (causing the flicker). Live progress text is handled
// by pollJob separately, so it is deliberately excluded here.
function findingsSignature(findings) {
  return JSON.stringify(findings.map((f) => [
    f.id, f.status, f.result || "", f.job_id || "",
    f.audit_result ? 1 : 0, f.proposal_ref || "",
  ]));
}

async function loadFindings() {
  const { status, data } = await api("GET", "/api/review/findings");
  const list = document.getElementById("rv-list");
  const empty = document.getElementById("queue-empty");
  const hasMap = STATE && STATE.meaning_map;
  empty.textContent = hasMap ? t("rv.no_findings") : t("rv.no_map");
  if (status !== 200) { list.innerHTML = ""; RV_SIG = null; empty.hidden = false; return; }
  const findings = data.findings || [];
  empty.hidden = findings.length > 0;

  // Only rebuild when something actually changed; otherwise leave the DOM
  // (and pollJob's in-flight progress writes) untouched.
  const sig = findingsSignature(findings);
  if (sig !== RV_SIG) {
    RV_SIG = sig;
    list.innerHTML = "";
    findings.forEach((f) => list.appendChild(findingCard(f)));
  }

  // Runs happen automatically on the server. While anything is still
  // open/running, re-poll the list so the UI tracks the worker's progress.
  const active = findings.some((f) => f.status === "open" || f.status === "running");
  if (active && !RV_REFRESH) {
    RV_REFRESH = setInterval(loadFindings, 2000);
  } else if (!active && RV_REFRESH) {
    clearInterval(RV_REFRESH);
    RV_REFRESH = null;
  }
}

// Track which running job we're already polling, so we don't double-poll.
const RV_POLLED = new Set();

function findingCard(f) {
  const card = document.createElement("div");
  card.className = "rv-card";
  const scope = f.field_label
    ? ` <span class="muted tiny">› ${escapeHtml(f.field_label)}</span>` : "";
  const statusLabel = t("rv.status." + f.status) || f.status;
  card.innerHTML =
    `<div class="rv-head">
       <span class="badge ${KIND_CLASS[f.kind] || ""}">${escapeHtml(t("rv.kind." + f.kind))}</span>
       <b>${escapeHtml(f.target_name || f.target_id)}</b>${scope}
       <span class="muted tiny rv-status rv-status-${escapeHtml(f.status)}">${escapeHtml(statusLabel)}</span>
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

  // Runs are automatic. Done/error findings can be re-queued; any finding
  // can be removed.
  const row = document.createElement("div");
  row.className = "row";
  if (f.status === "done" || f.status === "error") {
    const rerun = document.createElement("button");
    rerun.className = "claude";
    rerun.textContent = t("rv.rerun");
    rerun.onclick = async () => {
      await api("POST", "/api/review/findings/" + f.id + "/rerun");
      loadFindings();
    };
    row.appendChild(rerun);
  }
  const del = document.createElement("button");
  del.textContent = t("rv.delete");
  del.onclick = async () => { await api("DELETE", "/api/review/findings/" + f.id); loadFindings(); };
  row.appendChild(del);
  card.appendChild(row);

  // Live progress for a finding the server worker is currently running.
  if (f.status === "running" && f.job_id && !RV_POLLED.has(f.job_id)) {
    RV_POLLED.add(f.job_id);
    pollJob(f.job_id, "rvjob-" + f.id, () => refreshView(),
            () => { RV_POLLED.delete(f.job_id); });
  }
  return card;
}

// ---- concept tag editor (direct edit, no Claude) -----------------------
let TAG_TARGET = null;     // concept id being edited
let TAG_SELECTED = [];     // current tag strings

async function openTagEditor(conceptId, conceptName) {
  TAG_TARGET = conceptId;
  document.getElementById("tag-target").textContent = `${conceptName} (concept)`;
  // Load the concept's current tags + the system vocabulary.
  const [{ data: mm }, { data: vocab }] = await Promise.all([
    api("GET", "/api/artifact/meaning-map.json"),
    api("GET", "/api/tags"),
  ]);
  const concept = (mm.concepts || []).find((c) => c.id === conceptId) || {};
  TAG_SELECTED = (concept.tags || []).slice();
  const vocabNames = (vocab.tags || []).map((t) => t.name);
  // Vocabulary chips (toggle); show selected ones not in vocab too.
  const names = Array.from(new Set([...vocabNames, ...TAG_SELECTED]));
  const bar = document.getElementById("tag-vocab");
  bar.innerHTML = "";
  names.forEach((name) => {
    const chip = document.createElement("span");
    chip.className = "tag tagchip filter" + (TAG_SELECTED.includes(name) ? " active" : "");
    chip.textContent = name;
    chip.onclick = () => {
      const i = TAG_SELECTED.indexOf(name);
      if (i >= 0) TAG_SELECTED.splice(i, 1); else TAG_SELECTED.push(name);
      chip.classList.toggle("active");
      syncTagInput();
    };
    bar.appendChild(chip);
  });
  syncTagInput();
  document.getElementById("tag-pop").hidden = false;
}

function syncTagInput() {
  document.getElementById("tag-input").value = TAG_SELECTED.join(", ");
}

function closeTagEditor() {
  document.getElementById("tag-pop").hidden = true;
  TAG_TARGET = null;
}

async function saveTags() {
  if (!TAG_TARGET) return;
  const tags = document.getElementById("tag-input").value
    .split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  const { status } = await api(
    "PATCH", "/api/concept/" + encodeURIComponent(TAG_TARGET), { tags });
  if (status === 200) { closeTagEditor(); refreshView(); }
  else alert(t("save_failed"));
}

async function manageVocab() {
  const { data } = await api("GET", "/api/tags");
  // One tag per line: "name | group | description" (group/description optional).
  const text = (data.tags || [])
    .map((t) => [t.name, t.group || "", t.description || ""].join(" | ").replace(/( \| )+$/, ""))
    .join("\n");
  const edited = prompt(t("tag.manage_prompt"), text);
  if (edited === null) return;
  const groupSet = {};
  const tags = edited.split("\n").map((line) => {
    const [name, group, ...rest] = line.split("|").map((s) => s.trim());
    if (!name) return null;
    if (group) groupSet[group] = true;
    return { name, group: group || "", description: rest.join("|").trim() };
  }).filter(Boolean);
  // Preserve existing group descriptions; add any newly-referenced groups.
  const existingGroups = {};
  (data.groups || []).forEach((g) => (existingGroups[g.name] = g.description || ""));
  const groups = Object.keys(groupSet).map(
    (name) => ({ name, description: existingGroups[name] || "" }));
  await api("PUT", "/api/tags", { groups, tags });
  if (TAG_TARGET) openTagEditor(TAG_TARGET, document.getElementById("tag-target").textContent);
}

// ---- viewer ------------------------------------------------------------
function refreshView() {
  const frame = document.getElementById("view-frame");
  // Carry dev mode in the query so the freshly-loaded iframe starts correct.
  frame.src = apiUrl("/api/view") + "?_=" + Date.now() + (DEV_MODE ? "&dev=1" : "");
}

// Download a standalone, shareable HTML document (no review pins / app
// coupling) — a single self-contained file. Fetched then saved client-side so
// the browser downloads it rather than navigating to it.
async function exportDocument() {
  const btn = document.getElementById("export-doc");
  btn.disabled = true;
  try {
    const resp = await fetch(apiUrl("/api/export"));
    if (!resp.ok) throw new Error("export " + resp.status);
    const html = await resp.text();
    const name = (STATE && STATE.config && STATE.config.project
      && STATE.config.project.name) || "meaning-map";
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name.replace(/[^\w.-]+/g, "_") + ".html";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(t("export.failed"));
  } finally {
    btn.disabled = false;
  }
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
  // Reflect the persisted dev-mode state immediately (before the first view
  // load) so non-developer chrome is correct from the start.
  applyDevMode();
  document.getElementById("toggle-dev").onclick = toggleDevMode;
  document.getElementById("run-init").onclick = runInit;
  document.getElementById("toggle-init-instr").onclick = toggleInitInstructions;
  document.getElementById("save-init-instr").onclick = saveInitInstructions;
  document.getElementById("refresh-view").onclick = refreshView;
  document.getElementById("export-doc").onclick = exportDocument;
  document.getElementById("toggle-queue").onclick = toggleQueue;
  document.getElementById("save-config").onclick = saveConfig;
  document.getElementById("rv-add").onclick = () => submitFinding();
  document.getElementById("pop-close").onclick = closePopover;
  // Continue-session is a server-side setting (the worker reads it).
  document.getElementById("rv-continue").onchange = (e) =>
    api("PUT", "/api/review/settings", { continue_session: e.target.checked });
  document.querySelectorAll('input[name="rvkind"]').forEach(
    (r) => (r.onchange = updateKindHelp));

  // The preview iframe asks us (via postMessage) to open the popover when a
  // + pin is clicked inside it.
  document.getElementById("tag-close").onclick = closeTagEditor;
  document.getElementById("tag-save").onclick = saveTags;
  document.getElementById("tag-manage").onclick = (e) => { e.preventDefault(); manageVocab(); };

  window.addEventListener("message", (ev) => {
    const d = ev.data;
    if (d && d.source === "dramaturgy-review") {
      // Editing a concept's tags is a direct, Claude-free edit.
      if (d.target_type === "concept" && d.field === "tags") {
        openTagEditor(d.target_id, d.target_name);
      } else {
        openPopover({ target_type: d.target_type, target_id: d.target_id,
          target_name: d.target_name, field: d.field || "",
          field_label: d.field_label || "" });
      }
    }
  });

  refreshState().then(async () => {
    // With no meaning map yet, the non-developer view has nothing to show and
    // the only useful controls (Analyze all, etc.) are developer-only — so
    // start in developer mode. Not persisted: once a map exists, a reload
    // returns to the default (off) / persisted preference. Done before
    // refreshView so the iframe loads with the right ?dev state.
    if (STATE && !STATE.meaning_map && !DEV_MODE) {
      DEV_MODE = true;
      applyDevMode();
    }
    refreshView();
    const { status, data } = await api("GET", "/api/review/settings");
    if (status === 200) {
      document.getElementById("rv-continue").checked = !!data.continue_session;
    }
    loadFindings();
    loadInitInstructions();
  });
}

document.addEventListener("DOMContentLoaded", init);
