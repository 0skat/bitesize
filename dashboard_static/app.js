const GROUP_LABELS = {
  ai: "AI",
  feed: "Feed fetching",
  filter: "Article filters",
  epub: "EPUB layout",
  integrations: "Integrations",
  cli: "CLI defaults",
  kindle: "Kindle delivery",
  books: "iCloud Books delivery",
  dashboard: "Dashboard access",
  brave: "Brave Search source",
};

// Booleans are detected from the value's type below. This list only covers
// keys that may arrive absent or null, where the type tells us nothing.
const BOOL_KEYS = new Set([
  "kindle_delivery_enabled",
  "integration_gmail",
  "integration_google_calendar",
  "cli_select_all_sources",
  "books_delivery_enabled",
  "ai_covers_enabled",
  "balance_sections",
  "dashboard_cookie_secure",
  "brave_enabled",
]);

function isBoolSetting(key, value) {
  return typeof value === "boolean" || BOOL_KEYS.has(key);
}

const KINDLE_KEYS = [
  "kindle_email",
  "smtp_user",
  "smtp_password",
  "smtp_host",
  "smtp_port",
  "kindle_delivery_enabled",
];

let settingsData = {};

const TOKEN_KEY = "bitesize_dashboard_token";

function dashboardToken() {
  const el = $("#dashboard-token");
  const v = (el?.value || localStorage.getItem(TOKEN_KEY) || "").trim();
  if (el && v && !el.value) el.value = v;
  return v;
}

function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = dashboardToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return [...document.querySelectorAll(sel)]; }

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: authHeaders(),
    ...opts,
  });
  const data = r.headers.get("content-type")?.includes("json")
    ? await r.json()
    : null;
  if (r.status === 401) {
    throw new Error(
      dashboardToken()
        ? "Token rejected — check it against data/dashboard.token."
        : "This change needs the write token. Paste it in the field at the top of the page (it is in data/dashboard.token).",
    );
  }
  if (!r.ok) throw new Error(data?.error || data?.message || r.statusText);
  return data;
}

function setStatus(el, msg, ok) {
  el.textContent = msg || "";
  el.className = "status" + (msg ? (ok ? " ok" : " err") : "");
}

// Multi-line prose. A text input cannot hold a newline at all, so a
// line-per-section setting is unusable without this.
const TEXTAREA_KEYS = new Set(["user_interests", "brave_queries"]);

function inputForKey(key, value) {
  if (TEXTAREA_KEYS.has(key)) {
    const ta = document.createElement("textarea");
    ta.rows = 4;
    ta.value = value ?? "";
    ta.placeholder = "What you want to read about, in your own words.";
    ta.dataset.key = key;
    return ta;
  }
  if (isBoolSetting(key, value)) {
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !!value;
    cb.dataset.key = key;
    return cb;
  }
  const input = document.createElement("input");
  input.type = key.includes("password") ? "password"
    : key.includes("email") ? "email"
    : typeof value === "number" ? "number"
    : "text";
  input.value = value ?? "";
  input.dataset.key = key;
  return input;
}

function renderSettingsGroups() {
  const root = $("#settings-groups");
  root.innerHTML = "";
  for (const [group, fields] of Object.entries(settingsData)) {
    if (group === "kindle") continue;
    const card = document.createElement("div");
    card.className = "group";
    const title = document.createElement("h2");
    title.textContent = GROUP_LABELS[group] || group;
    card.appendChild(title);
    for (const [key, value] of Object.entries(fields)) {
      const row = document.createElement("div");
      row.className = "field";
      const label = document.createElement("label");
      label.textContent = key.replace(/_/g, " ");
      label.htmlFor = key;
      const input = inputForKey(key, value);
      input.id = key;
      row.append(label, input);
      card.appendChild(row);
    }
    root.appendChild(card);
  }
}

function renderKindleFields() {
  const root = $("#kindle-fields");
  root.innerHTML = "";
  const fields = settingsData.kindle || {};
  for (const key of KINDLE_KEYS) {
    if (key === "smtp_password_set") continue;
    const row = document.createElement("div");
    row.className = "field";
    const label = document.createElement("label");
    label.textContent = key.replace(/_/g, " ");
    const input = inputForKey(key, fields[key]);
    if (key === "smtp_password" && fields.smtp_password_set && !fields[key]) {
      input.placeholder = "•••••••• (unchanged)";
    }
    input.dataset.kindle = "1";
    row.append(label, input);
    root.appendChild(row);
  }
}

function collectInputs(container) {
  const out = {};
  container.querySelectorAll("[data-key]").forEach((el) => {
    const key = el.dataset.key;
    if (key === "smtp_password" && !el.value.trim()) {
      return;
    }
    out[key] = el.type === "checkbox" ? el.checked : el.value;
  });
  return out;
}

async function loadSettings() {
  settingsData = await api("/api/settings");
  renderSettingsGroups();
  renderKindleFields();
}

async function saveSettings(container, statusEl) {
  try {
    const updates = collectInputs(container);
    settingsData = await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify(updates),
    });
    setStatus(statusEl, "Saved.", true);
    renderKindleFields();
  } catch (e) {
    setStatus(statusEl, e.message, false);
  }
}

function renderSources(data) {
  const root = $("#sources-list");
  root.innerHTML = "";
  for (const cat of data.categories) {
    const card = document.createElement("div");
    card.className = "card";
    const header = document.createElement("div");
    header.className = "category-header";
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = cat.name;
    const saveCat = document.createElement("button");
    saveCat.textContent = "Rename";
    saveCat.onclick = async () => {
      await api(`/api/categories/${cat.id}`, {
        method: "PUT",
        body: JSON.stringify({ name: nameInput.value.trim() }),
      });
      await refreshSources();
    };
    const delCat = document.createElement("button");
    delCat.textContent = "Delete";
    delCat.className = "danger";
    delCat.onclick = async () => {
      if (!confirm(`Delete category "${cat.name}" and all feeds?`)) return;
      await api(`/api/categories/${cat.id}`, { method: "DELETE" });
      await refreshSources();
    };
    header.append(nameInput, saveCat, delCat);
    card.appendChild(header);

    for (const feed of cat.feeds) {
      const row = document.createElement("div");
      row.className = "feed-row";
      const name = document.createElement("input");
      name.type = "text";
      name.value = feed.name;
      const url = document.createElement("input");
      url.type = "text";
      url.value = feed.url;
      const enabled = document.createElement("input");
      enabled.type = "checkbox";
      enabled.checked = feed.enabled;
      enabled.title = "Enabled";
      const save = document.createElement("button");
      save.textContent = "Save";
      save.onclick = async () => {
        await api(`/api/feeds/${feed.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name: name.value.trim(),
            url: url.value.trim(),
            enabled: enabled.checked,
          }),
        });
        setStatus($("#sources-status"), "Feed saved.", true);
      };
      const del = document.createElement("button");
      del.textContent = "Delete";
      del.className = "danger";
      del.onclick = async () => {
        await api(`/api/feeds/${feed.id}`, { method: "DELETE" });
        await refreshSources();
      };
      row.append(name, url, enabled, save, del);
      card.appendChild(row);
    }

    const addRow = document.createElement("div");
    addRow.className = "feed-add";
    const newName = document.createElement("input");
    newName.placeholder = "Feed name";
    const newUrl = document.createElement("input");
    newUrl.placeholder = "RSS URL";
    const addBtn = document.createElement("button");
    addBtn.textContent = "Add feed";
    addBtn.onclick = async () => {
      await api("/api/feeds", {
        method: "POST",
        body: JSON.stringify({
          category_id: cat.id,
          name: newName.value.trim(),
          url: newUrl.value.trim(),
        }),
      });
      newName.value = "";
      newUrl.value = "";
      await refreshSources();
    };
    addRow.append(newName, newUrl, addBtn);
    card.appendChild(addRow);
    root.appendChild(card);
  }
}

async function refreshSources() {
  const data = await api("/api/sources");
  renderSources(data);
}

let previewLoaded = false;
let issuesLoaded = false;
let currentIssue = null;

// ── Issue review ────────────────────────────────────────────────────────────

function issueLabel(it) {
  const when = (it.created_at || "").replace("T", " ");
  const gone = it.epub_exists ? "" : " — file pruned";
  return `#${it.id}  ${when}  (${it.kept}/${it.stored} kept)${gone}`;
}

async function loadIssueList(selectId) {
  const picker = $("#issue-picker");
  const data = await api("/api/issues?limit=30");
  const list = data.issues || [];
  picker.innerHTML = "";
  if (!list.length) {
    const o = document.createElement("option");
    o.textContent = "No issues recorded yet — run the digest first";
    o.value = "";
    picker.appendChild(o);
    $("#issue-list").innerHTML = "";
    $("#issue-meta").textContent = "";
    return;
  }
  for (const it of list) {
    const o = document.createElement("option");
    o.value = it.id;
    o.textContent = issueLabel(it);
    picker.appendChild(o);
  }
  picker.value = String(selectId ?? list[0].id);
  await loadIssue(picker.value);
}

function articleRow(art) {
  const row = document.createElement("div");
  row.className = "art-row" + (art.excluded ? " excluded" : "");

  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = !art.excluded;
  cb.dataset.articleId = art.id;
  cb.title = "Untick to drop this story from the rebuilt EPUB";
  cb.onchange = () => toggleArticles([art.id], !cb.checked);

  const score = document.createElement("span");
  score.className = "art-score";
  score.textContent = (art.relevance / 10).toFixed(1);
  if (art.relevance_source && art.relevance_source !== "ai") {
    score.classList.add("fallback");
    score.title = `score source: ${art.relevance_source}`;
  }

  const main = document.createElement("div");
  main.className = "art-main";
  const h = document.createElement("div");
  h.className = "art-title";
  if (art.url) {
    const a = document.createElement("a");
    a.href = art.url;
    a.target = "_blank";
    a.rel = "noreferrer noopener";
    a.textContent = art.title || "(untitled)";
    h.appendChild(a);
  } else {
    h.textContent = art.title || "(untitled)";
  }
  const meta = document.createElement("div");
  meta.className = "art-meta";
  const bits = [art.source, art.published, art.tipo, (art.temas || []).join(", ")];
  meta.textContent = bits.filter(Boolean).join(" · ");
  const sum = document.createElement("div");
  sum.className = "art-summary";
  sum.textContent = art.summary || "(no summary)";
  main.append(h, meta, sum);

  row.append(cb, score, main);
  return row;
}

function renderIssue(issue) {
  currentIssue = issue;
  const root = $("#issue-list");
  root.innerHTML = "";

  let kept = 0;
  let total = 0;
  for (const sec of issue.sections) {
    const card = document.createElement("div");
    card.className = "group";
    const head = document.createElement("div");
    head.className = "sec-head";

    const title = document.createElement("h2");
    const live = sec.articles.filter((a) => !a.excluded).length;
    title.textContent = `${sec.name} (${live}/${sec.articles.length})`;
    if (sec.kind === "overflow") {
      const tag = document.createElement("span");
      tag.className = "sec-tag";
      tag.textContent = "overflow";
      title.appendChild(tag);
    }

    const drop = document.createElement("button");
    drop.textContent = live ? "Drop section" : "Restore section";
    drop.onclick = () =>
      toggleArticles(sec.articles.map((a) => a.id), live > 0);

    head.append(title, drop);
    card.appendChild(head);
    for (const art of sec.articles) card.appendChild(articleRow(art));
    root.appendChild(card);

    kept += live;
    total += sec.articles.length;
  }

  $("#issue-meta").textContent =
    `${issue.epub_name} — ${kept} of ${total} kept` +
    (issue.epub_exists ? "" : " (EPUB no longer on disk; rebuild recreates it)");

  // On the Pi there is no iCloud Books copy: the phone downloads the file
  // and Safari offers to open it in Books.
  const dl = $("#download-issue");
  dl.href = `/api/issues/${issue.id}/epub`;
  dl.hidden = !issue.epub_exists;
}

async function loadIssue(id) {
  if (!id) return;
  const status = $("#issue-status");
  try {
    setStatus(status, "Loading…", true);
    renderIssue(await api(`/api/issues/${id}`));
    setStatus(status, "", true);
  } catch (e) {
    setStatus(status, e.message, false);
  }
}

async function toggleArticles(ids, excluded) {
  if (!currentIssue) return;
  const status = $("#issue-status");
  try {
    const res = await api(`/api/issues/${currentIssue.id}/articles`, {
      method: "PUT",
      body: JSON.stringify({ ids, excluded }),
    });
    renderIssue(res.issue);
    setStatus(
      status,
      `${excluded ? "Dropped" : "Restored"} ${res.changed} — rebuild to apply.`,
      true,
    );
  } catch (e) {
    setStatus(status, e.message, false);
  }
}



$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.remove("active"));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#panel-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "preview" && !previewLoaded) {
      previewLoaded = true;
      loadPreview();
    }
    if (btn.dataset.tab === "pool" && !poolsLoaded) {
      poolsLoaded = true;
      loadPoolList().catch((e) => setStatus($("#pool-status"), e.message, false));
    }
    if (btn.dataset.tab === "issue" && !issuesLoaded) {
      issuesLoaded = true;
      loadIssueList().catch((e) => setStatus($("#issue-status"), e.message, false));
    }
  });
});

$("#save-settings").onclick = () =>
  saveSettings($("#panel-settings"), $("#settings-status"));

$("#save-kindle").onclick = () =>
  saveSettings($("#kindle-fields"), $("#kindle-status"));

$("#test-kindle").onclick = async () => {
  const status = $("#kindle-status");
  try {
    await saveSettings($("#kindle-fields"), status);
    const res = await api("/api/kindle/test", { method: "POST" });
    setStatus(status, res.message, res.ok);
  } catch (e) {
    setStatus(status, e.message, false);
  }
};

$("#add-category").onclick = async () => {
  const name = $("#new-category-name").value.trim();
  if (!name) return;
  await api("/api/categories", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  $("#new-category-name").value = "";
  await refreshSources();
};

async function loadPreview() {
  const status = $("#preview-status");
  const root = $("#preview-list");
  setStatus(status, "Fetching headlines…", true);
  root.innerHTML = "";
  try {
    const data = await api("/api/preview?max=5");
    renderPreview(data);
    setStatus(status, "Headlines loaded. Use Include to keep or drop a source.", true);
  } catch (e) {
    setStatus(status, e.message, false);
  }
}

function renderPreview(data) {
  const root = $("#preview-list");
  root.innerHTML = "";
  for (const cat of data.categories || []) {
    const card = document.createElement("div");
    card.className = "card";
    const h = document.createElement("h2");
    h.textContent = cat.name;
    card.appendChild(h);
    for (const feed of cat.feeds || []) {
      const block = document.createElement("div");
      block.className = "preview-feed";
      const header = document.createElement("div");
      header.className = "preview-feed-header";
      const title = document.createElement("strong");
      title.textContent = feed.name;
      const toggle = document.createElement("label");
      toggle.className = "preview-toggle";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!feed.enabled;
      cb.onchange = async () => {
        try {
          await api(`/api/feeds/${feed.id}`, {
            method: "PUT",
            body: JSON.stringify({ enabled: cb.checked }),
          });
          setStatus(
            $("#preview-status"),
            cb.checked ? `${feed.name} included.` : `${feed.name} removed from the digest.`,
            true,
          );
        } catch (e) {
          cb.checked = !cb.checked;
          setStatus($("#preview-status"), e.message, false);
        }
      };
      toggle.append(cb, document.createTextNode(" Include in digest"));
      header.append(title, toggle);
      block.appendChild(header);
      if (feed.error) {
        const err = document.createElement("p");
        err.className = "preview-error";
        err.textContent = feed.error;
        block.appendChild(err);
      }
      const list = document.createElement("ol");
      list.className = "preview-headlines";
      for (const item of feed.headlines || []) {
        const li = document.createElement("li");
        if (item.url) {
          const a = document.createElement("a");
          a.href = item.url;
          a.target = "_blank";
          a.rel = "noopener";
          a.textContent = item.title;
          li.appendChild(a);
        } else {
          li.textContent = item.title;
        }
        if (item.published) {
          const t = document.createElement("span");
          t.className = "preview-time";
          t.textContent = item.published;
          li.append(" ", t);
        }
        list.appendChild(li);
      }
      if (!feed.headlines?.length && !feed.error) {
        const empty = document.createElement("p");
        empty.className = "preview-empty";
        empty.textContent = "No headlines returned.";
        block.appendChild(empty);
      } else {
        block.appendChild(list);
      }
      card.appendChild(block);
    }
    root.appendChild(card);
  }
}

$("#refresh-preview").onclick = loadPreview;

// Initial load is startDashboard()'s job at the bottom of this file: behind a
// login gate these calls would 401 and splash errors across a hidden page.

// A stale token in localStorage, or one a password manager autofilled over,
// used to fail only at the moment of a write — and a DELETE that 401s looks
// like a broken API rather than a bad token. Check it up front instead.
async function verifyToken() {
  const status = $("#token-status");
  if (!status) return;
  if (!dashboardToken()) {
    setStatus(status, "No write token — reads work, changes will be refused.", false);
    return;
  }
  try {
    const r = await fetch("/api/auth/check", { headers: authHeaders() });
    if (r.ok) {
      setStatus(status, "Write token accepted.", true);
    } else {
      setStatus(
        status,
        "Token rejected. Paste the current value from data/dashboard.token.",
        false,
      );
    }
  } catch (e) {
    setStatus(status, `Could not reach the dashboard API: ${e.message}`, false);
  }
}

const tokenInput = $("#dashboard-token");
if (tokenInput) {
  const saved = localStorage.getItem(TOKEN_KEY);
  if (saved) tokenInput.value = saved;
  tokenInput.addEventListener("change", () => {
    const v = tokenInput.value.trim();
    if (v) localStorage.setItem(TOKEN_KEY, v);
    else localStorage.removeItem(TOKEN_KEY);
    verifyToken();
  });
  tokenInput.addEventListener("input", () => {
    const v = tokenInput.value.trim();
    if (v) localStorage.setItem(TOKEN_KEY, v);
  });
  // Only meaningful in the no-password model; startDashboard calls it then.
}

$("#issue-picker").onchange = (e) => loadIssue(e.target.value);

$("#reload-issue").onclick = () =>
  loadIssueList($("#issue-picker").value).catch((e) =>
    setStatus($("#issue-status"), e.message, false),
  );

$("#rebuild-issue").onclick = async () => {
  if (!currentIssue) return;
  const status = $("#issue-status");
  const btn = $("#rebuild-issue");
  btn.disabled = true;
  try {
    setStatus(status, "Rebuilding EPUB…", true);
    const res = await api(`/api/issues/${currentIssue.id}/rebuild`, {
      method: "POST",
      body: JSON.stringify({ deliver: true }),
    });
    setStatus(
      status,
      `Rebuilt ${res.epub_name} — ${res.articles} articles in ${res.sections} sections` +
        (res.delivered ? ", copied to Books." : ", not copied to Books."),
      true,
    );
    await loadIssueList(currentIssue.id);
  } catch (e) {
    setStatus(status, e.message, false);
  } finally {
    btn.disabled = false;
  }
};

// ── Pool: swipe through screened headlines ──────────────────────────────────
// Only kept articles get fetched and summarised, so this is where picking
// fewer actually saves AI calls. Nothing is published until Build.

let currentPool = null;
let poolQueue = [];       // ids still undecided, in rank order
let poolHistory = [];     // {id, pick} for Undo
let poolsLoaded = false;

function poolLabel(p) {
  const when = (p.created_at || "").replace("T", " ");
  const built = p.built_issue_id ? ` → issue #${p.built_issue_id}` : "";
  return `#${p.id}  ${when}  (${p.kept} kept, ${p.undecided} left)${built}`;
}

async function loadPoolList(selectId) {
  const picker = $("#pool-picker");
  const data = await api("/api/pools?limit=30");
  const list = data.pools || [];
  picker.innerHTML = "";
  if (!list.length) {
    const o = document.createElement("option");
    o.value = "";
    o.textContent = "No pool yet — press New pool";
    picker.appendChild(o);
    currentPool = null;
    $("#pool-card").innerHTML = "<p class='stack-empty'>No pool yet.</p>";
    $("#pool-tally").textContent = "";
    return;
  }
  for (const p of list) {
    const o = document.createElement("option");
    o.value = p.id;
    o.textContent = poolLabel(p);
    picker.appendChild(o);
  }
  picker.value = String(selectId ?? list[0].id);
  await loadPool(picker.value);
}

async function loadPool(id) {
  if (!id) return;
  try {
    currentPool = await api(`/api/pools/${id}`);
    poolHistory = [];
    poolQueue = currentPool.articles
      .filter((a) => a.pick === "undecided")
      .map((a) => a.id);
    renderPool();
  } catch (e) {
    setStatus($("#pool-status"), e.message, false);
  }
}

function poolCardById(id) {
  return currentPool?.articles.find((a) => a.id === id) || null;
}

function renderTally() {
  if (!currentPool) return;
  const p = currentPool;
  $("#pool-tally").textContent =
    `${p.kept} kept · ${p.skipped} skipped · ${p.undecided} undecided ` +
    `of ${p.stored}` + (p.built_issue_id ? ` — built as issue #${p.built_issue_id}` : "");
}

function renderPool() {
  renderTally();
  renderPoolCard();
  renderPoolList();
}

function renderPoolCard() {
  const el = $("#pool-card");
  el.style.transform = "";
  el.style.opacity = "";
  const id = poolQueue[0];
  const card = id ? poolCardById(id) : null;

  if (!card) {
    el.innerHTML =
      "<p class='stack-empty'>Nothing left undecided. " +
      "Press <strong>Build issue</strong> when you are happy.</p>";
    return;
  }

  el.innerHTML = "";
  const top = document.createElement("div");
  top.className = "card-top";
  top.textContent = `${card.section} · ${card.source}` +
    (card.published ? ` · ${card.published}` : "");

  const score = document.createElement("span");
  score.className = "card-score";
  score.textContent = card.prefilter_score;
  score.title = "screen score out of 100";
  top.appendChild(score);

  const h = document.createElement("h3");
  h.className = "card-title";
  if (card.url) {
    const a = document.createElement("a");
    a.href = card.url;
    a.target = "_blank";
    a.rel = "noreferrer noopener";
    a.textContent = card.title;
    h.appendChild(a);
  } else {
    h.textContent = card.title;
  }

  const sn = document.createElement("p");
  sn.className = "card-snippet";
  sn.textContent = card.snippet || "(no preview text in the feed)";

  const left = document.createElement("p");
  left.className = "card-left";
  left.textContent = `${poolQueue.length} left to decide`;

  el.append(top, h, sn, left);
}

function renderPoolList() {
  const root = $("#pool-list");
  if (!root || !currentPool) return;
  root.innerHTML = "";
  const bySection = {};
  for (const a of currentPool.articles) {
    (bySection[a.section || "—"] ||= []).push(a);
  }
  for (const section of Object.keys(bySection).sort()) {
    const card = document.createElement("div");
    card.className = "group";
    const h = document.createElement("h2");
    const kept = bySection[section].filter((a) => a.pick === "keep").length;
    h.textContent = `${section} (${kept}/${bySection[section].length} kept)`;
    card.appendChild(h);
    for (const a of bySection[section]) {
      const row = document.createElement("div");
      row.className = "art-row pool-row pick-" + a.pick;

      const btn = document.createElement("button");
      btn.className = "pick-toggle";
      btn.textContent = a.pick === "keep" ? "✓" : a.pick === "skip" ? "✕" : "·";
      btn.title = "click to keep / skip / undecide";
      btn.onclick = () => {
        const next = a.pick === "keep" ? "skip" : a.pick === "skip" ? "undecided" : "keep";
        pickArticles([a.id], next);
      };

      const score = document.createElement("span");
      score.className = "art-score";
      score.textContent = a.prefilter_score;

      const main = document.createElement("div");
      main.className = "art-main";
      const t = document.createElement("div");
      t.className = "art-title";
      t.textContent = a.title;
      const m = document.createElement("div");
      m.className = "art-meta";
      m.textContent = a.source;
      main.append(t, m);

      row.append(btn, score, main);
      card.appendChild(row);
    }
    root.appendChild(card);
  }
}

async function pickArticles(ids, pick, { fromStack = false } = {}) {
  if (!currentPool) return;
  try {
    const res = await api(`/api/pools/${currentPool.id}/picks`, {
      method: "PUT",
      body: JSON.stringify({ ids, pick }),
    });
    currentPool = res.pool;
    if (!fromStack) {
      // A list edit can change what is undecided, so rebuild the queue but
      // keep the card currently on top if it is still undecided.
      const head = poolQueue[0];
      poolQueue = currentPool.articles
        .filter((a) => a.pick === "undecided")
        .map((a) => a.id);
      if (head && poolQueue.includes(head)) {
        poolQueue = [head, ...poolQueue.filter((i) => i !== head)];
      }
    }
    renderPool();
    setStatus($("#pool-status"), "", true);
  } catch (e) {
    setStatus($("#pool-status"), e.message, false);
  }
}

function commitTop(pick) {
  const id = poolQueue[0];
  if (!id) return;
  poolHistory.push({ id, pick });
  poolQueue = poolQueue.slice(1);
  pickArticles([id], pick, { fromStack: true });
}

function undoPick() {
  const last = poolHistory.pop();
  if (!last) {
    setStatus($("#pool-status"), "Nothing to undo.", false);
    return;
  }
  poolQueue = [last.id, ...poolQueue];
  pickArticles([last.id], "undecided", { fromStack: true });
}

// Drag and swipe. Pointer events cover mouse, trackpad and touch in one path.
function wireSwipe() {
  const el = $("#pool-card");
  if (!el) return;
  let startX = null;
  let dx = 0;
  const THRESHOLD = 90;

  el.addEventListener("pointerdown", (e) => {
    if (e.target.tagName === "A") return;   // let links be links
    startX = e.clientX;
    dx = 0;
    el.setPointerCapture?.(e.pointerId);
    el.classList.add("dragging");
  });
  el.addEventListener("pointermove", (e) => {
    if (startX === null) return;
    dx = e.clientX - startX;
    el.style.transform = `translateX(${dx}px) rotate(${dx / 40}deg)`;
    el.style.opacity = String(Math.max(0.35, 1 - Math.abs(dx) / 420));
  });
  const release = () => {
    if (startX === null) return;
    el.classList.remove("dragging");
    const moved = dx;
    startX = null;
    dx = 0;
    if (Math.abs(moved) >= THRESHOLD) {
      commitTop(moved > 0 ? "keep" : "skip");
    } else {
      el.style.transform = "";
      el.style.opacity = "";
    }
  };
  el.addEventListener("pointerup", release);
  el.addEventListener("pointercancel", release);
  el.addEventListener("pointerleave", release);
}

document.addEventListener("keydown", (e) => {
  if (!$("#panel-pool")?.classList.contains("active")) return;
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  if (e.key === "ArrowRight") { e.preventDefault(); commitTop("keep"); }
  if (e.key === "ArrowLeft") { e.preventDefault(); commitTop("skip"); }
  if (e.key.toLowerCase() === "z") { e.preventDefault(); undoPick(); }
});

$("#pool-keep").onclick = () => commitTop("keep");
$("#pool-skip").onclick = () => commitTop("skip");
$("#pool-undo").onclick = () => undoPick();
$("#pool-picker").onchange = (e) => loadPool(e.target.value);

$("#pool-refresh").onclick = async () => {
  const status = $("#pool-status");
  const btn = $("#pool-refresh");
  btn.disabled = true;
  try {
    setStatus(status, "Fetching and screening… this takes about a minute.", true);
    const res = await api("/api/pools/refresh", { method: "POST" });
    await loadPoolList(res.pool.id);
    setStatus(status, `New pool #${res.pool.id} — ${res.pool.stored} candidates.`, true);
  } catch (e) {
    setStatus(status, e.message, false);
  } finally {
    btn.disabled = false;
  }
};

$("#pool-build").onclick = async () => {
  if (!currentPool) return;
  const status = $("#pool-status");
  if (!currentPool.kept) {
    setStatus(status, "Keep at least one article first.", false);
    return;
  }
  const btn = $("#pool-build");
  btn.disabled = true;
  try {
    setStatus(status, `Summarising ${currentPool.kept} picks…`, true);
    const res = await api(`/api/pools/${currentPool.id}/build`, {
      method: "POST",
      body: JSON.stringify({ deliver: true }),
    });
    setStatus(status, `Built ${res.epub_name} as issue #${res.issue_id}.`, true);
    await loadPoolList(currentPool.id);
  } catch (e) {
    setStatus(status, e.message, false);
  } finally {
    btn.disabled = false;
  }
};

wireSwipe();

// ── Login gate ──────────────────────────────────────────────────────────────
// With a password set, every API route needs credentials — reads included —
// because a tunnel makes a remote request look like a local one.

async function authState() {
  try {
    const r = await fetch("/api/auth/state");
    return r.ok ? await r.json() : { password_set: false, authenticated: true };
  } catch {
    return { password_set: false, authenticated: true };
  }
}

function showGate(show) {
  const gate = $("#login-gate");
  const shell = $("#app-shell");
  if (gate) gate.hidden = !show;
  if (shell) shell.hidden = show;
}

async function startDashboard() {
  const state = await authState();

  // The token field only matters in the no-password model.
  const tokenField = $("#dashboard-token")?.closest(".token-field");
  if (tokenField) tokenField.hidden = state.password_set;
  const logout = $("#logout");
  if (logout) logout.hidden = !state.password_set;

  if (state.password_set && !state.authenticated) {
    showGate(true);
    return;
  }
  showGate(false);
  await loadSettings();
  await refreshSources();
  if (!state.password_set) verifyToken();
}

$("#login-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = $("#login-status");
  const pw = $("#login-password");
  try {
    setStatus(status, "Checking…", true);
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw.value }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || "Login failed.");
    pw.value = "";
    setStatus(status, "", true);
    await startDashboard();
  } catch (err) {
    setStatus(status, err.message, false);
  }
});

$("#logout")?.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" }).catch(() => {});
  location.reload();
});

startDashboard();
