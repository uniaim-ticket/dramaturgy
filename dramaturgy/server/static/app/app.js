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
async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const resp = await fetch(path, opts);
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
function showJob(elId, job) {
  const el = document.getElementById(elId);
  if (!el) return;
  const lines = (job.progress || []).map((l) => `<div class="line">${escapeHtml(l)}</div>`).join("");
  const head = job.status === "running"
    ? `<div class="spin">${t("job.running")}</div>`
    : job.status === "done"
      ? `<div>${t("job.done")}${job.session_id ? " · " + job.session_id : ""}</div>`
      : `<div class="status err">${t("job.error")}: ${escapeHtml(job.error || job.status)}</div>`;
  el.innerHTML = head + lines;
}

async function pollJob(jobId, elId, onDone) {
  let since = 0;
  const acc = { progress: [] };
  const tick = async () => {
    const { data } = await api("GET", `/api/jobs/${jobId}?since=${since}`);
    acc.progress.push(...(data.progress || []));
    since = data.progress_total;
    showJob(elId, { ...data, progress: acc.progress });
    if (["done", "error", "aborted"].includes(data.status)) {
      if (data.status === "done" && onDone) onDone();
      return;
    }
    setTimeout(tick, 1200);
  };
  tick();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

// ---- viewer ------------------------------------------------------------
function refreshView() {
  const frame = document.getElementById("view-frame");
  frame.src = "/api/view?_=" + Date.now();
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
  document.getElementById("run-analyze").onclick = runAnalyze;
  document.getElementById("gen-tree").onclick = genTree;
  document.getElementById("save-tree").onclick = saveTreeJson;
  document.getElementById("run-merge").onclick = runMerge;
  document.getElementById("run-validate").onclick = runValidate;
  document.getElementById("run-render").onclick = runRender;
  document.getElementById("refresh-view").onclick = refreshView;
  document.getElementById("save-config").onclick = saveConfig;
  refreshState().then(() => { showStep("analyze"); refreshView(); });
}

document.addEventListener("DOMContentLoaded", init);
