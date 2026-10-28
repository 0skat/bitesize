const GROUP_LABELS = {
  ai: "AI",
  feed: "Feed fetching",
  filter: "Article filters",
  epub: "EPUB layout",
  integrations: "Integrations",
  cli: "CLI defaults",
  kindle: "Kindle delivery",
};

const BOOL_KEYS = new Set([
  "kindle_delivery_enabled",
  "integration_gmail",
  "integration_google_calendar",
  "cli_select_all_sources",
]);

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
  if (!r.ok) throw new Error(data?.error || data?.message || r.statusText);
  return data;
}

function setStatus(el, msg, ok) {
  el.textContent = msg || "";
  el.className = "status" + (msg ? (ok ? " ok" : " err") : "");
}

const TEXTAREA_KEYS = new Set(["user_interests"]);

function inputForKey(key, value) {
  if (TEXTAREA_KEYS.has(key)) {
    const ta = document.createElement("textarea");
    ta.rows = 4;
    ta.value = value ?? "";
    ta.placeholder = "What you want to read about, in your own words.";
    ta.dataset.key = key;
    return ta;
  }
  if (BOOL_KEYS.has(key)) {
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

loadSettings().then(refreshSources).catch((e) => {
  setStatus($("#settings-status"), e.message, false);
});

const tokenInput = $("#dashboard-token");
if (tokenInput) {
  const saved = localStorage.getItem(TOKEN_KEY);
  if (saved) tokenInput.value = saved;
  tokenInput.addEventListener("change", () => {
    const v = tokenInput.value.trim();
    if (v) localStorage.setItem(TOKEN_KEY, v);
    else localStorage.removeItem(TOKEN_KEY);
  });
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
