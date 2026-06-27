"use strict";

// UI chrome labels for the app shell. Kept here (not in the Python HTML
// catalogs) because these are specific to this editing UI. ui_lang picks
// the column; missing keys fall back to the data-i default text.
const I18N = {
  ja: {
    "btn.save_config": "保存", "step.analyze": "1. 解析", "step.tree": "2. 領域ツリー",
    "step.cards": "3. 領域カード", "step.map": "4. 統合・表示",
    "analyze.help": "対象リポジトリを索引します（機械処理、Claude不要）。",
    "analyze.run": "解析を実行", "tree.help": "解析結果から Claude Code に area-tree.json を生成させます（ファイルへ直接書き込み）。",
    "tree.generate": "Claudeで生成", "tree.editor": "area-tree.json",
    "btn.save_json": "JSONを保存", "cards.help": "ツリーの各領域について、Claude に意味地図カードを書かせます。",
    "map.merge": "カードを統合", "map.validate": "検査", "map.render": "HTML生成",
    "map.edit_area": "領域を編集（meaning-map.json に書き戻し）",
    "viewer.title": "意味地図プレビュー", "viewer.refresh": "更新",
    "job.running": "実行中…", "job.done": "完了", "job.error": "エラー",
    "card.generate": "Claudeで生成", "card.regenerate": "再生成", "card.done": "生成済み",
    "saved": "保存しました", "save_failed": "保存に失敗", "area.save": "この領域を保存",
    "init.run": "Claudeで一括初期化", "init.help": "全工程を一度に実行します: 解析 → 領域ツリー → 領域カード → 統合 → 検査 → HTML生成。完了後、下の各ステップで個別に調整できます。",
    "init.running": "一括初期化を実行中…", "init.done": "一括初期化が完了しました",
    "job.idle": "応答待ち",
    "step.review": "5. レビュー",
    "review.help": "登場人物・概念データ・業務領域を指して指摘を追加します。reframe=地図を修正 / audit=矛盾や説明できないパターンを調査（地図は変えない）/ proposal=今後の変更を記録。",
    "rv.type.actor": "登場人物", "rv.type.concept": "概念データ", "rv.type.area": "業務領域",
    "rv.kind.reframe": "再整理", "rv.kind.audit": "検査", "rv.kind.proposal": "将来提案",
    "rv.kindhelp.reframe": "指摘を是として、正本の意味地図を修正します。",
    "rv.kindhelp.audit": "正本は変えず、矛盾・説明できないパターンを調査して記録します。",
    "rv.kindhelp.proposal": "現状とは別に「今後こう変えたい」を提案として記録します。",
    "rv.add": "指摘を追加", "rv.queue": "指摘一覧",
    "rv.continue_session": "Claudeセッションを継続する",
    "rv.run": "実行", "rv.rerun": "再実行", "rv.delete": "削除",
    "rv.view_result": "結果を表示",
    "rv.no_findings": "まだ指摘はありません。",
    "rv.no_map": "先に意味地図を生成してください（4. 統合・表示）。",
  },
  en: {
    "btn.save_config": "Save", "step.analyze": "1. Analyze", "step.tree": "2. Area tree",
    "step.cards": "3. Area cards", "step.map": "4. Merge & view",
    "analyze.help": "Index the target repository (mechanical, no Claude).",
    "analyze.run": "Run analyze", "tree.help": "Have Claude Code generate area-tree.json from the analysis (writes the file directly).",
    "tree.generate": "Generate with Claude", "tree.editor": "area-tree.json",
    "btn.save_json": "Save JSON", "cards.help": "For each area in the tree, have Claude write its meaning-map card.",
    "map.merge": "Merge cards", "map.validate": "Validate", "map.render": "Render HTML",
    "map.edit_area": "Edit area (writes back to meaning-map.json)",
    "viewer.title": "Meaning map preview", "viewer.refresh": "Refresh",
    "job.running": "running…", "job.done": "done", "job.error": "error",
    "card.generate": "Generate with Claude", "card.regenerate": "Regenerate", "card.done": "generated",
    "saved": "Saved", "save_failed": "Save failed", "area.save": "Save this area",
    "init.run": "Initialize all with Claude", "init.help": "Run the full pipeline once: analyze → area tree → area cards → merge → validate → render. Adjust individual steps below afterwards.",
    "init.running": "Initializing…", "init.done": "Initialization complete",
    "job.idle": "awaiting response",
    "step.review": "5. Review",
    "review.help": "Point at an actor, concept, or area and add a remark. reframe edits the map; audit only investigates (no map change); proposal records a future change.",
    "rv.type.actor": "Actor", "rv.type.concept": "Concept data", "rv.type.area": "Area",
    "rv.kind.reframe": "reframe", "rv.kind.audit": "audit", "rv.kind.proposal": "proposal",
    "rv.kindhelp.reframe": "Accept the remark and edit the canonical meaning map.",
    "rv.kindhelp.audit": "Leave the map unchanged; investigate contradictions / cases it can't explain.",
    "rv.kindhelp.proposal": "Record a future change separately from the as-is map.",
    "rv.add": "Add finding", "rv.queue": "Findings",
    "rv.continue_session": "continue Claude session",
    "rv.run": "Run", "rv.rerun": "Re-run", "rv.delete": "Delete",
    "rv.view_result": "View result",
    "rv.no_findings": "No findings yet.",
    "rv.no_map": "Generate the meaning map first (4. Map & view).",
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

// ---- tiny fetch helpers ------------------------------------------------
// The client is served under ".../app/" (the URL ends with a slash). The API
// lives one level up at ".../api/...". Derive both from the current location
// so everything works behind a reverse proxy on an arbitrary sub-path — no
// absolute "/app" / "/api" paths anywhere.
const APP_BASE = location.pathname.replace(/[^/]*$/, "");   // ".../app/"
const ROOT_BASE = APP_BASE.replace(/app\/$/, "");           // ".../"

// Resolve an API path like "/api/state" relative to the server root.
function apiUrl(path) {
  return ROOT_BASE + path.replace(/^\//, "");
}

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

// ---- step navigation ---------------------------------------------------
function showStep(step) {
  document.querySelectorAll("nav#steps button").forEach((b) =>
    b.classList.toggle("active", b.dataset.step === step));
  document.querySelectorAll(".view").forEach((v) => (v.hidden = true));
  document.getElementById("view-" + step).hidden = false;
  if (step === "tree") loadTreeJson();
  if (step === "cards") loadAreaList();
  if (step === "map") loadAreaEditor();
  if (step === "review") loadReview();
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
    // Reflect the freshly generated artifacts in whatever step is open.
    const active = document.querySelector("nav#steps button.active");
    showStep(active ? active.dataset.step : "map");
    refreshView();
    btn.disabled = false;
  }, () => { btn.disabled = false; });
}

// ---- step 1: analyze ---------------------------------------------------
async function runAnalyze() {
  const btn = document.getElementById("run-analyze");
  btn.disabled = true;
  const { data } = await api("POST", "/api/analyze", {});
  document.getElementById("analyze-out").textContent = JSON.stringify(data, null, 2);
  btn.disabled = false;
  await refreshState();
}

// ---- step 2: area tree -------------------------------------------------
async function loadTreeJson() {
  const { status, data } = await api("GET", "/api/artifact/area-tree.json");
  document.getElementById("tree-json").value =
    status === 200 ? JSON.stringify(data, null, 2) : "";
}

async function saveTreeJson() {
  const el = document.getElementById("tree-json");
  const status = document.getElementById("tree-status");
  let parsed;
  try { parsed = JSON.parse(el.value); }
  catch (e) { status.textContent = "JSON: " + e.message; status.className = "status err"; return; }
  const { status: code, data } = await api("PUT", "/api/artifact/area-tree.json", parsed);
  status.textContent = code === 200 ? t("saved") : (data.error || t("save_failed"));
  status.className = code === 200 ? "status" : "status err";
}

async function genTree() {
  const { status, data } = await api("POST", "/api/jobs/area-tree", {});
  if (status !== 202) { showJob("tree-job", { status: "error", error: data.error }); return; }
  pollJob(data.job_id, "tree-job", () => loadTreeJson());
}

// ---- step 3: area cards ------------------------------------------------
async function loadAreaList() {
  const ul = document.getElementById("area-list");
  ul.innerHTML = "";
  const { status, data } = await api("GET", "/api/artifact/area-tree.json");
  if (status !== 200) { ul.innerHTML = `<li class="muted">area-tree.json: none</li>`; return; }
  const existing = new Set(STATE.area_maps.map((n) => n.replace(/\.json$/, "")));
  (data.areas || []).forEach((area) => {
    const li = document.createElement("li");
    const done = existing.has(area.id);
    li.innerHTML = `<span><b>${area.name || area.id}</b>
      <span class="meta">${area.id}</span></span>`;
    const right = document.createElement("span");
    if (done) {
      const b = document.createElement("span");
      b.className = "badge done"; b.textContent = t("card.done");
      right.appendChild(b);
    }
    const btn = document.createElement("button");
    btn.className = "claude";
    btn.textContent = done ? t("card.regenerate") : t("card.generate");
    btn.onclick = () => genCard(area.id, li);
    right.appendChild(btn);
    li.appendChild(right);
    ul.appendChild(li);
  });
}

async function genCard(areaId, li) {
  const job = document.createElement("div");
  job.className = "job"; job.id = "job-" + areaId;
  li.appendChild(job);
  const { status, data } = await api("POST", "/api/jobs/area-card", { area_id: areaId });
  if (status !== 202) { showJob(job.id, { status: "error", error: data.error }); return; }
  pollJob(data.job_id, job.id, async () => { await refreshState(); loadAreaList(); });
}

// ---- step 4: merge / validate / render / edit --------------------------
async function runMerge() { out(await api("POST", "/api/merge", {})); refreshView(); }
async function runValidate() { out(await api("GET", "/api/validate")); }
async function runRender() { out(await api("POST", "/api/render", {})); refreshView(); }
function out(res) { document.getElementById("map-out").textContent = JSON.stringify(res.data, null, 2); }

async function loadAreaEditor() {
  const box = document.getElementById("area-editor");
  box.innerHTML = "";
  const { status, data } = await api("GET", "/api/artifact/meaning-map.json");
  if (status !== 200) { box.innerHTML = `<p class="muted">meaning-map.json: none</p>`; return; }
  const select = document.createElement("select");
  (data.areas || []).forEach((a) => {
    const o = document.createElement("option"); o.value = a.id; o.textContent = a.name || a.id;
    select.appendChild(o);
  });
  box.appendChild(select);
  const form = document.createElement("div");
  box.appendChild(form);
  const render = () => {
    const area = data.areas.find((a) => a.id === select.value);
    form.innerHTML = "";
    ["name", "one_liner", "purpose"].forEach((f) => {
      form.appendChild(field(f, area[f] || "", false));
    });
    form.appendChild(field("risk_points", (area.risk_points || []).join("\n"), true));
    const save = document.createElement("button");
    save.className = "primary"; save.textContent = t("area.save");
    save.onclick = async () => {
      const patch = {
        name: form.querySelector("[name=name]").value,
        one_liner: form.querySelector("[name=one_liner]").value,
        purpose: form.querySelector("[name=purpose]").value,
        risk_points: form.querySelector("[name=risk_points]").value
          .split("\n").map((s) => s.trim()).filter(Boolean),
      };
      const r = await api("PATCH", "/api/area/" + encodeURIComponent(area.id), patch);
      save.textContent = r.status === 200 ? t("saved") : t("save_failed");
      setTimeout(() => (save.textContent = t("area.save")), 1500);
      refreshView();
    };
    form.appendChild(save);
  };
  select.onchange = render;
  render();
}

function field(name, value, multiline) {
  const wrap = document.createElement("div"); wrap.className = "field";
  const label = document.createElement("label"); label.textContent = name;
  const input = document.createElement(multiline ? "textarea" : "input");
  input.setAttribute("name", name); input.value = value;
  wrap.appendChild(label); wrap.appendChild(input);
  return wrap;
}

// ---- job polling -------------------------------------------------------
const SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"];

function fmtDuration(sec) {
  sec = Math.round(sec || 0);
  const m = Math.floor(sec / 60), s = sec % 60;
  return m ? `${m}m${String(s).padStart(2, "0")}s` : `${s}s`;
}

function liveStats(job, frame) {
  // Proves the Claude session is alive: spinner + elapsed + pid + CPU/mem.
  const spin = SPINNER[frame % SPINNER.length];
  const bits = [`${spin} ${t("job.running")}`, `${fmtDuration(job.elapsed_sec)}`];
  if (job.pid) bits.push(`pid ${job.pid}`);
  if (job.process) {
    bits.push(`CPU ${job.process.cpu_percent}%`);
    bits.push(`${job.process.rss_mb}MB`);
  }
  // If we haven't seen output in a while, say so (still alive, just thinking).
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
      : `<div class="status err">${t("job.error")}: ${escapeHtml(job.error || job.status)}</div>`;
  el.innerHTML = head + lines;
}

async function pollJob(jobId, elId, onDone, onEnd) {
  let since = 0;
  let frame = 0;
  let last = null;
  const acc = { progress: [] };

  // Animate the spinner ~3x/sec so the user always sees movement, even
  // between the (slower) server polls — this is the "it's alive" signal.
  const animate = setInterval(() => {
    if (last && last.status === "running") {
      frame += 1;
      showJob(elId, { ...last, progress: acc.progress }, frame);
    }
  }, 300);

  const tick = async () => {
    let data;
    try {
      ({ data } = await api("GET", `/api/jobs/${jobId}?since=${since}`));
    } catch {
      setTimeout(tick, 1500);   // transient network hiccup; keep polling
      return;
    }
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
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

// ---- step 5: interactive review ----------------------------------------
let RV_TARGETS = null;

async function loadReview() {
  const { status, data } = await api("GET", "/api/review/targets");
  const list = document.getElementById("rv-list");
  if (status !== 200) {
    RV_TARGETS = null;
    document.getElementById("rv-target").innerHTML = "";
    list.innerHTML = `<p class="muted">${t("rv.no_map")}</p>`;
    return;
  }
  RV_TARGETS = data;
  fillTargetOptions();
  updateKindHelp();
  loadFindings();
}

function fillTargetOptions() {
  const type = document.getElementById("rv-type").value;
  const sel = document.getElementById("rv-target");
  sel.innerHTML = "";
  (RV_TARGETS[type + "s"] || []).forEach((it) => {
    const o = document.createElement("option");
    o.value = it.id; o.textContent = `${it.name} (${it.id})`;
    sel.appendChild(o);
  });
}

function currentKind() {
  const r = document.querySelector('input[name="rvkind"]:checked');
  return r ? r.value : "reframe";
}

function updateKindHelp() {
  document.getElementById("rv-kind-help").textContent =
    t("rv.kindhelp." + currentKind());
}

async function addFinding() {
  const type = document.getElementById("rv-type").value;
  const sel = document.getElementById("rv-target");
  const comment = document.getElementById("rv-comment").value.trim();
  if (!sel.value || !comment) return;
  const target_name = sel.options[sel.selectedIndex].textContent;
  const { status, data } = await api("POST", "/api/review/findings", {
    target_type: type, target_id: sel.value, target_name,
    kind: currentKind(), comment,
  });
  if (status === 201) {
    document.getElementById("rv-comment").value = "";
    loadFindings();
  } else {
    alert(data.error || "error");
  }
}

const KIND_CLASS = { reframe: "k-reframe", audit: "k-audit", proposal: "k-proposal" };

async function loadFindings() {
  const { status, data } = await api("GET", "/api/review/findings");
  const list = document.getElementById("rv-list");
  if (status !== 200) { list.innerHTML = ""; return; }
  const findings = data.findings || [];
  if (!findings.length) {
    list.innerHTML = `<p class="muted">${t("rv.no_findings")}</p>`;
    return;
  }
  list.innerHTML = "";
  findings.forEach((f) => list.appendChild(findingCard(f)));
}

function findingCard(f) {
  const card = document.createElement("div");
  card.className = "rv-card";
  const ran = f.status === "done" || f.status === "error";
  const kindLabel = t("rv.kind." + f.kind);
  card.innerHTML =
    `<div class="rv-head">
       <span class="badge ${KIND_CLASS[f.kind] || ""}">${escapeHtml(kindLabel)}</span>
       <b>${escapeHtml(f.target_name || f.target_id)}</b>
       <span class="muted tiny">${escapeHtml(f.target_type)} · ${escapeHtml(f.status)}</span>
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

async function runFinding(fid) {
  const cont = document.getElementById("rv-continue").checked;
  const { status, data } = await api(
    "POST", "/api/review/findings/" + fid + "/run", { continue_session: cont });
  if (status !== 202) { showJob("rvjob-" + fid, { status: "error", error: data.error }); return; }
  pollJob(data.job_id, "rvjob-" + fid, async () => {
    await loadFindings();
    refreshView();   // reframe may have changed the map
  });
}

// ---- viewer ------------------------------------------------------------
function refreshView() {
  const frame = document.getElementById("view-frame");
  frame.src = apiUrl("/api/view") + "?_=" + Date.now();
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
}

// ---- wire up -----------------------------------------------------------
function init() {
  document.querySelectorAll("nav#steps button").forEach((b) =>
    (b.onclick = () => showStep(b.dataset.step)));
  document.getElementById("run-init").onclick = runInit;
  document.getElementById("run-analyze").onclick = runAnalyze;
  document.getElementById("gen-tree").onclick = genTree;
  document.getElementById("save-tree").onclick = saveTreeJson;
  document.getElementById("run-merge").onclick = runMerge;
  document.getElementById("run-validate").onclick = runValidate;
  document.getElementById("run-render").onclick = runRender;
  document.getElementById("refresh-view").onclick = refreshView;
  document.getElementById("save-config").onclick = saveConfig;
  document.getElementById("rv-type").onchange = fillTargetOptions;
  document.getElementById("rv-add").onclick = addFinding;
  document.querySelectorAll('input[name="rvkind"]').forEach(
    (r) => (r.onchange = updateKindHelp));
  refreshState().then(() => { showStep("analyze"); refreshView(); });
}

document.addEventListener("DOMContentLoaded", init);
