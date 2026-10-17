"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const PLATFORMS = ["youtube", "instagram", "tiktok"];
const LABELS = { youtube: "YouTube", instagram: "Instagram", tiktok: "TikTok" };
const LOGOS = { youtube: ["yt", "▶"], instagram: ["ig", "◎"], tiktok: ["tt", "♪"] };
const PRIVACY_LABELS = {
  PUBLIC_TO_EVERYONE: "Everyone",
  MUTUAL_FOLLOW_FRIENDS: "Friends",
  FOLLOWER_OF_CREATOR: "Followers",
  SELF_ONLY: "Only me",
};

const state = {
  status: null,
  video: null,
  coverT: 0,
  jobId: null,
  creatorInfo: null,
};

// ------------------------------------------------------------------ helpers

const storage = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
  },
};

async function api(path, options = {}) {
  const opts = { ...options };
  if (opts.json !== undefined) {
    opts.method = opts.method || "POST";
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(opts.json);
    delete opts.json;
  }
  const res = await fetch(path, opts);
  let data;
  try { data = await res.json(); } catch { throw new Error(`Server error (${res.status})`); }
  if (!data.ok) throw new Error(data.error || "Unknown error");
  return data;
}

let toastTimer;
function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), isError ? 7000 : 3500);
}

function fmtTime(t) {
  const m = Math.floor(t / 60);
  const s = (t - m * 60).toFixed(2).padStart(5, "0");
  return `${m}:${s}`;
}

function fmtSize(bytes) {
  if (bytes > 1e9) return (bytes / 1e9).toFixed(2) + " GB";
  return (bytes / 1e6).toFixed(1) + " MB";
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ------------------------------------------------------------------ tabs

function showTab(name) {
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab-panel").forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${name}`));
  if (location.hash !== `#${name}`) history.replaceState(null, "", `${location.pathname}${location.search}#${name}`);
}
$$(".tab").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
window.addEventListener("hashchange", () => showTab(location.hash === "#accounts" ? "accounts" : "publish"));
document.addEventListener("click", (e) => {
  const link = e.target.closest("[data-goto]");
  if (link) { e.preventDefault(); showTab(link.dataset.goto); }
});

// ------------------------------------------------------------------ account status

let statusPoll;
async function loadStatus() {
  const data = await api("/api/status");
  state.status = data;
  renderAccounts();
  renderPlatforms();
  clearTimeout(statusPoll);
  if (data.youtube.auth_running) statusPoll = setTimeout(loadStatus, 2000);
}

function renderAccounts() {
  const s = state.status;
  const setStatus = (id, text, cls) => {
    const el = $(`#acc-${id} .acc-status`);
    el.textContent = text;
    el.className = "acc-status " + (cls || "");
  };

  // YouTube
  const yt = s.youtube;
  setStatus("youtube", yt.connected ? `Connected · ${yt.account}` : "Not connected", yt.connected ? "on" : "");
  $(".yt-client-state").textContent = yt.configured ? "✓ client_secret.json imported" : "";
  $("#yt-connect").disabled = !yt.configured || yt.auth_running;
  $("#yt-connect").textContent = yt.connected ? "Reconnect" : "Connect my channel";
  $(".yt-wait").classList.toggle("hidden", !yt.auth_running);
  if (yt.auth_error && !yt.auth_running && state.lastYtError !== yt.auth_error) {
    state.lastYtError = yt.auth_error;
    toast(`YouTube: ${yt.auth_error}`, true);
  }
  $('#acc-youtube .disconnect').classList.toggle("hidden", !yt.connected);

  // Instagram
  const ig = s.instagram;
  let igText = "Not connected", igCls = "";
  if (ig.connected) {
    igText = `Connected · @${ig.account}`;
    igCls = "on";
  } else if (ig.expired) {
    igText = "Login expired";
    igCls = "bad";
  }
  setStatus("instagram", igText, igCls);
  $("#ig-redirect").textContent = s.redirects.instagram;
  if (ig.app_id && !$("#ig-app-id").value) $("#ig-app-id").value = ig.app_id;
  if (ig.config_id && !$("#ig-config-id").value) $("#ig-config-id").value = ig.config_id;
  if (ig.configured && !$("#ig-app-secret").value) $("#ig-app-secret").placeholder = "App Secret (saved)";
  $("#ig-connect").classList.toggle("disabled", !ig.configured);
  $("#ig-connect").textContent = ig.connected ? "Reconnect" : "Connect with Facebook";
  $('#acc-instagram .disconnect').classList.toggle("hidden", !(ig.connected || ig.expired));
  const sel = $("#ig-account-select");
  $(".ig-accounts").classList.toggle("hidden", !(ig.accounts && ig.accounts.length > 1));
  sel.innerHTML = (ig.accounts || [])
    .map((a) => `<option value="${escapeHtml(a.id)}" ${a.id === ig.account_id ? "selected" : ""}>@${escapeHtml(a.username)} (${escapeHtml(a.page)})</option>`)
    .join("");
  if (ig.connected && ig.expires_at) {
    const days = Math.round((ig.expires_at * 1000 - Date.now()) / 86400000);
    if (days < 10) setStatus("instagram", `@${ig.account} · expires in ${days} d`, "bad");
  }

  // TikTok
  const tt = s.tiktok;
  setStatus("tiktok", tt.connected ? `Connected · ${tt.account}` : "Not connected", tt.connected ? "on" : "");
  $("#tt-redirect").textContent = s.redirects.tiktok;
  if (tt.client_key && !$("#tt-client-key").value) $("#tt-client-key").value = tt.client_key;
  if (tt.configured && !$("#tt-client-secret").value) $("#tt-client-secret").placeholder = "Client secret (saved)";
  $("#tt-connect").classList.toggle("disabled", !tt.configured);
  $("#tt-connect").textContent = tt.connected ? "Reconnect" : "Connect TikTok";
  $('#acc-tiktok .disconnect').classList.toggle("hidden", !tt.connected);

  const missing = PLATFORMS.filter((p) => !s[p].connected).length;
  const badge = $("#accounts-badge");
  badge.textContent = missing;
  badge.classList.toggle("hidden", missing === 0);
}

function renderPlatforms() {
  const s = state.status;
  const saved = storage.get("platforms", PLATFORMS);
  let anyOff = false;
  for (const p of PLATFORMS) {
    const box = $(`.platform[data-platform="${p}"]`);
    const cb = $(".pf-check", box);
    const connected = s[p].connected;
    cb.disabled = !connected;
    if (!connected) cb.checked = false;
    else if (!cb.dataset.init) cb.checked = saved.includes(p);
    cb.dataset.init = "1";
    box.classList.toggle("off", !connected);
    box.classList.toggle("checked", cb.checked);
    $(".pf-account", box).textContent = connected ? (p === "instagram" ? `@${s[p].account}` : s[p].account) : "not connected";
    if (!connected) anyOff = true;
  }
  $("#no-account-hint").classList.toggle("hidden", !anyOff);
  if ($('.pf-check[value="tiktok"]').checked) loadCreatorInfo();
  updatePublishButton();
}

function selectedPlatforms() {
  return $$(".pf-check").filter((c) => c.checked).map((c) => c.value);
}

function updatePublishButton() {
  const n = selectedPlatforms().length;
  const btn = $("#publish-btn");
  const problem = n ? tiktokProblem() : null;
  btn.disabled = !state.video || n === 0 || !!problem;
  btn.textContent = !n ? "Select at least one platform"
    : problem || `Publish to ${selectedPlatforms().map((p) => LABELS[p]).join(", ")}`;
}

$$(".pf-check").forEach((cb) =>
  cb.addEventListener("change", () => {
    cb.closest(".platform").classList.toggle("checked", cb.checked);
    storage.set("platforms", selectedPlatforms());
    if (cb.value === "tiktok" && cb.checked) loadCreatorInfo();
    updatePublishButton();
    updateWarnings();
  })
);

// TikTok requires fresh creator info every time the posting form is shown (Direct Post guidelines).
async function loadCreatorInfo(force = false) {
  if (state.creatorInfoLoading || (state.creatorInfo && !force)) return;
  state.creatorInfoLoading = true;
  try {
    const { info } = await api("/api/tiktok/creator_info");
    state.creatorInfo = info;
    const sel = $("#tt-privacy");
    const current = sel.value;
    const options = info.privacy_level_options || [];
    // No default value: the user has to pick the visibility themselves.
    sel.innerHTML = `<option value="" disabled ${options.includes(current) ? "" : "selected"}>Select…</option>` +
      options.map((o) => `<option value="${o}" ${o === current ? "selected" : ""}>${PRIVACY_LABELS[o] || o}</option>`).join("");
    for (const [key, id] of [["comment_disabled", "#tt-allow-comment"], ["duet_disabled", "#tt-allow-duet"], ["stitch_disabled", "#tt-allow-stitch"]]) {
      const cb = $(id);
      cb.disabled = !!info[key];
      if (info[key]) cb.checked = false;
      cb.closest("label").title = info[key] ? "Turned off in your TikTok privacy settings" : "";
    }
    if (info.creator_nickname) $('.platform[data-platform="tiktok"] .pf-account').textContent = `Posting as ${info.creator_nickname}`;
    updateTikTokForm();
    updateWarnings();
  } catch (e) {
    toast(`TikTok: ${e.message}`, true);
  } finally {
    state.creatorInfoLoading = false;
  }
}

const MUSIC_POLICY = '<a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noopener">Music Usage Confirmation</a>';
const BRANDED_POLICY = '<a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" rel="noopener">Branded Content Policy</a>';

function updateTikTokForm() {
  const commercial = $("#tt-commercial").checked;
  const yourBrand = commercial && $("#tt-your-brand").checked;
  const branded = commercial && $("#tt-branded").checked;
  $("#tt-commercial-opts").classList.toggle("hidden", !commercial);

  let label = "";
  if (branded) label = 'Your video will be labeled as "Paid partnership".';
  else if (yourBrand) label = 'Your video will be labeled as "Promotional content".';
  else if (commercial) label = "You need to indicate if your content promotes yourself, a third party, or both.";
  $("#tt-commercial-label").textContent = label;

  // Branded content can't be private.
  const selfOnly = $('#tt-privacy option[value="SELF_ONLY"]');
  if (selfOnly) {
    selfOnly.disabled = branded;
    selfOnly.title = branded ? "Branded content visibility cannot be set to private." : "";
    if (branded && $("#tt-privacy").value === "SELF_ONLY") {
      $("#tt-privacy").value = "";
      toast("Branded content can't be private: choose another visibility.", true);
    }
  }

  $("#tt-consent").innerHTML = branded
    ? `By posting, you agree to TikTok's ${BRANDED_POLICY} and ${MUSIC_POLICY}.`
    : `By posting, you agree to TikTok's ${MUSIC_POLICY}.`;
  updatePublishButton();
}

function tiktokProblem() {
  if (!selectedPlatforms().includes("tiktok") || $("#tt-mode").value === "draft") return null;
  if (!$("#tt-privacy").value) return "Choose who can view the TikTok video";
  if ($("#tt-commercial").checked && !$("#tt-your-brand").checked && !$("#tt-branded").checked)
    return "Choose your commercial content type";
  const max = state.creatorInfo?.max_video_post_duration_sec;
  if (state.video && max && state.video.duration > max) return `TikTok allows ${max} s max for this account`;
  return null;
}

["#tt-commercial", "#tt-your-brand", "#tt-branded"].forEach((s) => $(s).addEventListener("change", updateTikTokForm));
$("#tt-privacy").addEventListener("change", updatePublishButton);
$("#tt-mode").addEventListener("change", (e) => {
  const draft = e.target.value === "draft";
  $$(".tt-direct").forEach((el) => el.classList.toggle("hidden", draft));
  $(".tt-draft").classList.toggle("hidden", !draft);
  storage.set("tt-mode", e.target.value);
  updatePublishButton();
});
updateTikTokForm();
$("#yt-privacy").value = storage.get("yt-privacy", "public");
$("#yt-privacy").addEventListener("change", (e) => storage.set("yt-privacy", e.target.value));
$("#tt-mode").value = storage.get("tt-mode", "direct");
$("#tt-mode").dispatchEvent(new Event("change"));

// ------------------------------------------------------------------ video import

const dropzone = $("#dropzone");
const fileInput = $("#file-input");
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("over"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("over");
  if (e.dataTransfer.files[0]) uploadVideo(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => { if (fileInput.files[0]) uploadVideo(fileInput.files[0]); });

function uploadVideo(file) {
  const bar = $("#upload-progress");
  bar.classList.remove("hidden");
  bar.firstElementChild.style.width = "0";
  const form = new FormData();
  form.append("file", file);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/videos");
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) bar.firstElementChild.style.width = `${(e.loaded / e.total) * 100}%`;
  };
  xhr.onload = () => {
    bar.classList.add("hidden");
    fileInput.value = "";
    let data;
    try { data = JSON.parse(xhr.responseText); } catch { data = { ok: false, error: `Server error (${xhr.status})` }; }
    if (!data.ok) return toast(data.error, true);
    loadVideo(data.video);
  };
  xhr.onerror = () => { bar.classList.add("hidden"); toast("Upload failed: is the server running?", true); };
  xhr.send(form);
}

function loadVideo(v) {
  state.video = v;
  $("#dropzone").classList.add("hidden");
  $("#job").classList.add("hidden");
  $("#editor").classList.remove("hidden");
  $("#video-name").textContent = v.filename;
  const orient = { horizontal: "Horizontal", vertical: "Vertical", square: "Square" }[v.orientation];
  $("#video-meta").innerHTML = [orient, `${v.width}×${v.height}`, fmtTime(v.duration).replace(/\.\d+$/, ""), fmtSize(v.size)]
    .map((c) => `<span class="chip">${c}</span>`).join("");

  const slider = $("#cover-slider");
  slider.max = Math.max(v.duration - 0.05, 0);
  slider.step = 1 / (v.fps || 30);
  buildFilmstrip();
  setCover(0);

  $("#horizontal-block").classList.toggle("hidden", v.orientation !== "horizontal");
  if ($('.pf-check[value="tiktok"]').checked) loadCreatorInfo(true);
  updateWarnings();
  updatePublishButton();
}

$("#change-video").addEventListener("click", resetToUpload);

function resetToUpload() {
  state.video = null;
  $("#editor").classList.add("hidden");
  $("#job").classList.add("hidden");
  $("#dropzone").classList.remove("hidden");
  updatePublishButton();
}

// ------------------------------------------------------------------ cover picker

const frameUrl = (t, w, mode) =>
  `/api/videos/${state.video.id}/frame?t=${t.toFixed(3)}&w=${w}${mode ? `&mode=${mode}` : ""}`;

// Loads one image at a time and jumps straight to the latest one requested.
function lazyImage(img, spinner) {
  let loading = false, next = null;
  const load = (url) => {
    if (loading) { next = url; return; }
    loading = true;
    spinner?.classList.remove("hidden");
    const pre = new Image();
    pre.onload = pre.onerror = () => {
      if (pre.complete && pre.naturalWidth) img.src = url;
      loading = false;
      if (next) { const n = next; next = null; load(n); } else spinner?.classList.add("hidden");
    };
    pre.src = url;
  };
  return load;
}
const loadCover = lazyImage($("#cover-preview"), $("#cover-loading"));
const loadShort = lazyImage($("#short-preview"));

function setCover(t) {
  const v = state.video;
  t = Math.min(Math.max(t, 0), Math.max(v.duration - 0.05, 0));
  state.coverT = t;
  $("#cover-slider").value = t;
  $("#cover-time").textContent = fmtTime(t);
  loadCover(frameUrl(t, 720));
  if (v.orientation === "horizontal") loadShort(frameUrl(t, 360, verticalMode()));
  $$("#filmstrip img").forEach((img) => img.classList.toggle("active", Math.abs(+img.dataset.t - t) < 0.001));
}

function buildFilmstrip() {
  const v = state.video;
  const n = 10;
  $("#filmstrip").innerHTML = "";
  for (let i = 0; i < n; i++) {
    const t = i === 0 ? 0 : (v.duration * i) / n;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.dataset.t = t;
    img.title = fmtTime(t);
    img.src = frameUrl(t, 180);
    img.addEventListener("click", () => setCover(t));
    $("#filmstrip").appendChild(img);
  }
}

$("#cover-slider").addEventListener("input", (e) => setCover(+e.target.value));
$("#frame-prev").addEventListener("click", () => setCover(state.coverT - 1 / (state.video.fps || 30)));
$("#frame-next").addEventListener("click", () => setCover(state.coverT + 1 / (state.video.fps || 30)));
document.addEventListener("keydown", (e) => {
  if (!state.video || $("#editor").classList.contains("hidden")) return;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) && document.activeElement.type !== "range") return;
  if (e.key === "ArrowLeft") { e.preventDefault(); $("#frame-prev").click(); }
  if (e.key === "ArrowRight") { e.preventDefault(); $("#frame-next").click(); }
});

const verticalMode = () => $('input[name="vmode"]:checked').value;
$$('input[name="vmode"]').forEach((r) =>
  r.addEventListener("change", () => {
    storage.set("vmode", verticalMode());
    loadShort(frameUrl(state.coverT, 360, verticalMode()));
  })
);
{
  const saved = storage.get("vmode", "blur");
  const radio = $(`input[name="vmode"][value="${saved}"]`);
  if (radio) radio.checked = true;
}
$("#vertical-all").checked = storage.get("vertical-all", false);
$("#vertical-all").addEventListener("change", (e) => storage.set("vertical-all", e.target.checked));

function updateWarnings() {
  const v = state.video;
  if (!v) return;
  const warns = [];
  const sel = selectedPlatforms();
  if (sel.includes("youtube") && v.duration > 180)
    warns.push("Video longer than 3 minutes: YouTube will publish it as a regular video, not a Short.");
  if (sel.includes("instagram") && v.duration > 15 * 60)
    warns.push("Instagram doesn't accept Reels longer than 15 minutes through the API.");
  if (sel.includes("instagram") && v.duration < 3)
    warns.push("Instagram requires Reels to be at least 3 seconds long.");
  const max = state.creatorInfo?.max_video_post_duration_sec;
  if (sel.includes("tiktok") && max && v.duration > max)
    warns.push(`Your TikTok account accepts videos up to ${max} s.`);
  const el = $("#duration-warning");
  el.innerHTML = warns.map(escapeHtml).join("<br>");
  el.classList.toggle("hidden", warns.length === 0);
}

// ------------------------------------------------------------------ text

function parseHashtags(raw) {
  const seen = new Set(), out = [];
  for (const m of raw.matchAll(/#?([^\s#,;]+)/g)) {
    const tag = "#" + m[1];
    if (!seen.has(tag.toLowerCase())) { seen.add(tag.toLowerCase()); out.push(tag); }
  }
  return out;
}

function buildCaption() {
  const desc = $("#description").value.trim();
  const tags = parseHashtags($("#hashtags").value).join(" ");
  return [desc, tags].filter(Boolean).join("\n\n");
}

function updateTexts() {
  const caption = buildCaption();
  const dc = $("#desc-count");
  dc.textContent = `${caption.length}/2200`;
  dc.classList.toggle("over", caption.length > 2200);
  dc.title = "Instagram and TikTok limit the caption (description + hashtags) to 2200 characters";
  const tags = parseHashtags($("#hashtags").value);
  const tc = $("#tags-count");
  tc.textContent = tags.length ? `${tags.length}/30` : "";
  tc.classList.toggle("over", tags.length > 30);
  tc.title = "Instagram accepts at most 30 hashtags";
  $("#tags-preview").innerHTML = tags.map((t) => `<span>${escapeHtml(t)}</span>`).join("");
  $("#caption-preview").textContent = caption || "(empty)";
  storage.set("draft", { description: $("#description").value, hashtags: $("#hashtags").value });
}

{
  const draft = storage.get("draft", {});
  $("#description").value = draft.description || "";
  $("#hashtags").value = draft.hashtags || "";
}
["#description", "#hashtags"].forEach((s) => $(s).addEventListener("input", updateTexts));
updateTexts();

// ------------------------------------------------------------------ publishing

$("#publish-btn").addEventListener("click", async () => {
  const platforms = selectedPlatforms();
  const caption = buildCaption();
  if (!caption && platforms.includes("youtube"))
    return toast("Add a description or hashtags (YouTube needs some text).", true);
  if (caption.length > 2200 && platforms.some((p) => p !== "youtube"))
    return toast("The caption is over 2200 characters (Instagram/TikTok limit).", true);
  if (parseHashtags($("#hashtags").value).length > 30 && platforms.includes("instagram"))
    return toast("Instagram accepts at most 30 hashtags.", true);

  const body = {
    video_id: state.video.id,
    platforms,
    description: $("#description").value,
    hashtags: $("#hashtags").value,
    cover_t: state.coverT,
    vertical_mode: verticalMode(),
    vertical_all: $("#vertical-all").checked,
    youtube: { privacy: $("#yt-privacy").value },
    tiktok: {
      mode: $("#tt-mode").value,
      privacy: $("#tt-privacy").value,
      disable_comment: !$("#tt-allow-comment").checked,
      disable_duet: !$("#tt-allow-duet").checked,
      disable_stitch: !$("#tt-allow-stitch").checked,
      brand_organic: $("#tt-commercial").checked && $("#tt-your-brand").checked,
      brand_content: $("#tt-commercial").checked && $("#tt-branded").checked,
    },
  };
  $("#publish-btn").disabled = true;
  try {
    const { job_id } = await api("/api/publish", { json: body });
    state.jobId = job_id;
    $("#editor").classList.add("hidden");
    $("#job").classList.remove("hidden");
    $("#job-actions").classList.add("hidden");
    $("#job h2").textContent = "Publishing…";
    pollJob();
  } catch (e) {
    toast(e.message, true);
  } finally {
    updatePublishButton();
  }
});

function jobRow(label, logo, s) {
  const pct = Math.round((s.progress || 0) * 100);
  const logoHtml = logo ? `<span class="pf-logo ${logo[0]}">${logo[1]}</span>` : "⚙️";
  let msg = escapeHtml(s.message);
  if (s.state === "done" && s.url) msg += ` — <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">view</a>`;
  if (s.state === "error") msg = "✗ " + msg;
  if (s.state === "done") msg = "✓ " + msg;
  return `<div class="job-row ${s.state}">
    <div class="job-label">${logoHtml} ${label}</div>
    <div>
      <div class="job-msg">${msg}</div>
      ${s.state === "running" || s.state === "waiting" ? `<div class="progress"><div style="width:${pct}%"></div></div>` : ""}
      ${s.warning ? `<div class="job-warn">⚠ ${escapeHtml(s.warning)}</div>` : ""}
    </div>
  </div>`;
}

async function pollJob() {
  let job;
  try {
    ({ job } = await api(`/api/jobs/${state.jobId}`));
  } catch (e) {
    toast(e.message, true);
    return;
  }
  $("#job-prep").outerHTML = `<div id="job-prep">${jobRow("Preparation", null, job.prep)}</div>`;
  $("#job-rows").innerHTML = Object.entries(job.platforms).map(([p, s]) => jobRow(LABELS[p], LOGOS[p], s)).join("");
  if (job.done) {
    const failed = Object.values(job.platforms).filter((s) => s.state === "error").length;
    $("#job h2").textContent = failed ? `Finished with ${failed} error${failed > 1 ? "s" : ""}` : "All published 🎉";
    $("#job-actions").classList.remove("hidden");
    return;
  }
  setTimeout(pollJob, 1200);
}

$("#new-post").addEventListener("click", () => {
  $("#description").value = "";
  $("#hashtags").value = "";
  updateTexts();
  resetToUpload();
});
$("#back-edit").addEventListener("click", () => {
  $("#job").classList.add("hidden");
  $("#editor").classList.remove("hidden");
});

// ------------------------------------------------------------------ account actions

$("#yt-client").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const form = new FormData();
  form.append("file", f);
  try {
    await api("/api/accounts/youtube/client", { method: "POST", body: form });
    toast("Google client file imported ✓");
    loadStatus();
  } catch (err) {
    toast(err.message, true);
  }
  e.target.value = "";
});

$("#yt-connect").addEventListener("click", async () => {
  try {
    await api("/api/accounts/youtube/connect", { method: "POST" });
    loadStatus();
  } catch (e) {
    toast(e.message, true);
  }
});

$("#ig-save").addEventListener("click", async () => {
  try {
    await api("/api/accounts/instagram/config", {
      json: { app_id: $("#ig-app-id").value, app_secret: $("#ig-app-secret").value, config_id: $("#ig-config-id").value },
    });
    $("#ig-app-secret").value = "";
    toast("Meta credentials saved ✓");
    loadStatus();
  } catch (e) {
    toast(e.message, true);
  }
});

$("#ig-token-save").addEventListener("click", async () => {
  const btn = $("#ig-token-save");
  btn.disabled = true;
  try {
    await api("/api/accounts/instagram/token", { json: { token: $("#ig-token").value } });
    $("#ig-token").value = "";
    toast("Instagram connected ✓");
    loadStatus();
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
  }
});

$("#ig-account-select").addEventListener("change", async (e) => {
  try {
    await api("/api/accounts/instagram/select", { json: { id: e.target.value } });
    loadStatus();
  } catch (err) {
    toast(err.message, true);
  }
});

$("#tt-save").addEventListener("click", async () => {
  try {
    await api("/api/accounts/tiktok/config", {
      json: { client_key: $("#tt-client-key").value, client_secret: $("#tt-client-secret").value },
    });
    $("#tt-client-secret").value = "";
    toast("TikTok credentials saved ✓");
    loadStatus();
  } catch (e) {
    toast(e.message, true);
  }
});

$$(".disconnect").forEach((b) =>
  b.addEventListener("click", async () => {
    const p = b.dataset.platform;
    if (!confirm(`Disconnect ${LABELS[p]}?`)) return;
    try {
      await api(`/api/accounts/${p}/disconnect`, { method: "POST" });
      if (p === "tiktok") state.creatorInfo = null;
      loadStatus();
    } catch (e) {
      toast(e.message, true);
    }
  })
);

$$(".copy").forEach((el) =>
  el.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(el.textContent);
      toast("Copied ✓");
    } catch { /* clipboard unavailable */ }
  })
);

// ------------------------------------------------------------------ startup

(async function init() {
  const params = new URLSearchParams(location.search);
  if (params.get("connected")) toast(`${LABELS[params.get("connected")] || "Account"} connected ✓`);
  if (params.get("error")) toast(`${LABELS[params.get("platform")] || "Login"}: ${params.get("error")}`, true);
  if (params.toString()) history.replaceState(null, "", location.pathname + location.hash);

  showTab(location.hash === "#accounts" ? "accounts" : "publish");
  try {
    await loadStatus();
  } catch (e) {
    toast(e.message, true);
  }
})();
