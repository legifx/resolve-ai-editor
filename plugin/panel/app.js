/* Panel logic — vanilla JS, talks JSON to the local server only. */
"use strict";

const TOKEN = new URLSearchParams(location.search).get("token") || "";
const api = (path, opts = {}) =>
  fetch(path, {
    ...opts,
    headers: { "X-Token": TOKEN, "Content-Type": "application/json",
               ...(opts.headers || {}) },
  }).then(r => r.json());

const $ = sel => document.querySelector(sel);

/* ---- tabs ---- */
document.querySelectorAll("nav button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button, .tab").forEach(el =>
      el.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
  });
});

/* ---- status ---- */
async function refreshStatus() {
  try {
    const s = await api("/api/status");
    $("#version").textContent = "v" + s.version;
    const r = s.resolve;
    $("#st-project").textContent = r.project || "–";
    $("#st-timeline").textContent = r.timeline || "–";
    $("#st-fps").textContent = r.fps != null ? r.fps : "–";
    $("#st-clips").textContent = r.clip_count != null ? r.clip_count : "–";
    $("#st-detector").textContent = s.vad_available
      ? "webrtcvad + ffmpeg" : "ffmpeg silencedetect";
    const conn = $("#conn");
    conn.textContent = r.connected ? "Resolve connected" : "not connected";
    conn.className = "badge " + (r.connected ? "ok" : "bad");
    const err = $("#st-error");
    err.classList.toggle("hidden", !r.error);
    err.textContent = r.error || "";
    $("#btn-rawcut").disabled = !r.connected;
  } catch (e) {
    $("#conn").textContent = "panel server unreachable";
    $("#conn").className = "badge bad";
  }
}

/* ---- raw cut job ---- */
let pollTimer = null;

$("#btn-rawcut").addEventListener("click", async () => {
  $("#btn-rawcut").disabled = true;
  $("#job-log").classList.remove("hidden");
  $("#job-log").textContent = "starting…";
  $("#job-report").classList.add("hidden");
  const profile = $("#profile-select").value;
  const res = await api("/api/rawcut", {
    method: "POST", body: JSON.stringify({ profile }),
  });
  if (res.error) return jobDone({ error: res.error });
  pollTimer = setInterval(pollJob, 700);
});

/* ---- edit profiles ---- */
let profileData = {};
async function loadProfiles() {
  let d;
  try { d = await api("/api/profiles"); } catch (e) { return; }
  const sel = $("#profile-select");
  for (const p of d.profiles) {
    profileData[p.key] = p;
    const opt = document.createElement("option");
    opt.value = p.key;
    opt.textContent = p.label;
    sel.appendChild(opt);
  }
  sel.value = d.default || "";
  showProfileDesc();
}
function showProfileDesc() {
  const p = profileData[$("#profile-select").value];
  $("#profile-desc").textContent = p ? (p.description + " · target " + p.aspect_ratio) : "";
}
$("#profile-select").addEventListener("change", showProfileDesc);

async function pollJob() {
  const j = await api("/api/job");
  $("#job-log").textContent = j.log.join("\n") || "working…";
  if (!j.running) { clearInterval(pollTimer); jobDone(j); }
}

function jobDone(j) {
  $("#btn-rawcut").disabled = false;
  const rep = $("#job-report");
  rep.classList.remove("hidden");
  if (j.error) {
    rep.innerHTML = '<p class="error"></p>';
    rep.querySelector("p").textContent = "✗ " + j.error;
  } else if (j.report) {
    const r = j.report;
    rep.textContent = "";
    const stats = document.createElement("div");
    for (const [v, label] of [[r.segments, "segments"],
        [r.removed_seconds + " s", "removed"], [r.output_seconds + " s", "result"]]) {
      const d = document.createElement("div");
      d.className = "stat";
      const b = document.createElement("b"); b.textContent = v;
      d.appendChild(b); d.appendChild(document.createTextNode(label));
      stats.appendChild(d);
    }
    rep.appendChild(stats);

    const meta = document.createElement("p");
    meta.className = "muted";
    meta.textContent = "New timeline: " + r.timeline +
      (r.profile ? "  ·  profile: " + r.profile : "") +
      (r.skipped_clips.length
        ? "  ·  skipped (no media pool item): " + r.skipped_clips.join(", ") : "");
    rep.appendChild(meta);

    if (r.aspect_warning) {
      const w = document.createElement("p");
      w.className = "error";
      w.textContent = "⚠ " + r.aspect_warning;
      rep.appendChild(w);
    }
    if (r.recommendations && r.recommendations.length) {
      const h = document.createElement("p");
      h.className = "muted";
      h.style.marginBottom = "2px";
      h.textContent = "Recommended manual steps for this profile:";
      rep.appendChild(h);
      const ul = document.createElement("ul");
      ul.className = "muted";
      ul.style.margin = "0 0 0 18px";
      for (const rec of r.recommendations) {
        const li = document.createElement("li");
        li.textContent = rec;
        ul.appendChild(li);
      }
      rep.appendChild(ul);
    }
    refreshStatus();
  }
}

/* ---- settings ---- */
async function loadSettings() {
  const s = await api("/api/settings");
  const form = $("#settings-form");
  for (const [k, v] of Object.entries(s)) {
    const input = form.elements[k];
    if (!input) continue;
    if (input.type === "checkbox") input.checked = !!v;
    else input.value = v;
  }
}

$("#settings-form").addEventListener("submit", async ev => {
  ev.preventDefault();
  const form = ev.target, payload = {};
  for (const input of form.querySelectorAll("input")) {
    payload[input.name] = input.type === "checkbox"
      ? input.checked : parseFloat(input.value);
  }
  await api("/api/settings", { method: "POST", body: JSON.stringify(payload) });
  $("#settings-saved").classList.remove("hidden");
  setTimeout(() => $("#settings-saved").classList.add("hidden"), 1500);
});

/* ---- assets ---- */
let assetFolders = [];
async function loadAssets() {
  let s;
  try { s = await api("/api/assets/status"); } catch (e) { return; }
  assetFolders = s.folders || [];
  const list = $("#folders-list");
  list.textContent = assetFolders.length
    ? "Folders: " + assetFolders.join("  ·  ")
    : "No folders connected yet.";
  const kinds = Object.entries(s.by_kind || {})
    .map(([k, n]) => n + " " + k).join(", ");
  $("#assets-count").textContent = s.indexed
    ? "  " + s.indexed + " assets indexed (" + kinds + ")" : "";
}

$("#folder-add").addEventListener("click", async () => {
  const v = $("#folder-input").value.trim();
  if (!v) return;
  assetFolders.push(v);
  await api("/api/assets/folders", {
    method: "POST", body: JSON.stringify({ folders: assetFolders }),
  });
  $("#folder-input").value = "";
  loadAssets();
});

$("#assets-scan").addEventListener("click", async () => {
  $("#assets-count").textContent = "  scanning…";
  const r = await api("/api/assets/scan", { method: "POST", body: "{}" });
  if (r.error) { $("#assets-count").textContent = "  ✗ " + r.error; return; }
  loadAssets();
});

function renderPlacements(placements, header) {
  const out = $("#assets-result");
  out.textContent = "";
  const h = document.createElement("p");
  h.className = "muted"; h.style.marginBottom = "4px";
  h.textContent = header;
  out.appendChild(h);
  const ul = document.createElement("ul");
  ul.className = "muted"; ul.style.margin = "0 0 0 18px";
  for (const p of placements) {
    const li = document.createElement("li");
    li.textContent = p.timecode + "  " +
      (p.asset_name ? (p.asset_name + " — " + p.reason)
                    : ("(" + p.reason + ")"));
    if (!p.asset_name) li.style.color = "#c98a3a";
    ul.appendChild(li);
  }
  out.appendChild(ul);
}

$("#assets-recommend").addEventListener("click", async () => {
  $("#assets-result").textContent = "thinking…";
  const r = await api("/api/assets/recommend", {
    method: "POST",
    body: JSON.stringify({ use_ai: $("#assets-use-ai").checked }),
  });
  if (r.error) { $("#assets-result").textContent = "✗ " + r.error; return; }
  renderPlacements(r.placements,
    "Recommended SFX" + (r.ai_used ? " (AI-refined):" : " (heuristic):"));
});

$("#assets-place").addEventListener("click", async () => {
  $("#assets-result").textContent = "inserting…";
  const r = await api("/api/assets/place", {
    method: "POST",
    body: JSON.stringify({ use_ai: $("#assets-use-ai").checked }),
  });
  const out = $("#assets-result");
  if (r.error) { out.textContent = "✗ " + r.error; return; }
  const rep = r.report;
  out.textContent = "✓ Inserted " + rep.placed + " SFX on track " + rep.track +
    (rep.missing_asset.length
      ? "  ·  " + rep.missing_asset.length + " cut(s) had no matching asset"
      : "");
  out.style.color = "var(--ok)";
  refreshStatus();
});

/* ---- AI providers ---- */
async function loadAiStatus() {
  let s;
  try {
    s = await api("/api/ai/status");
  } catch (e) { return; }
  $("#ai-backend").textContent = "in " + s.key_backend;
  for (const [prov, has] of Object.entries(s.keys)) {
    const el = document.querySelector('.keystate[data-state="' + prov + '"]');
    if (el) {
      el.textContent = has ? "✓ stored" : "not set";
      el.style.color = has ? "var(--ok)" : "var(--muted)";
    }
  }
  $("#ai-custom-url").value = s.custom_base_url || "";
  for (const tier of ["routine", "complex"]) {
    const route = s.routing[tier] || {};
    const provSel = document.querySelector('.route-provider[data-tier="' + tier + '"]');
    const modelIn = document.querySelector('.route-model[data-tier="' + tier + '"]');
    if (provSel && route.provider) provSel.value = route.provider;
    if (modelIn) modelIn.value = route.model || "";
  }
  // per-tier readiness line
  const status = $("#ai-tier-status");
  status.innerHTML = "";
  for (const [tier, t] of Object.entries(s.tiers)) {
    const div = document.createElement("div");
    div.className = "muted";
    div.innerHTML = (t.ready ? "✓ " : "✗ ") + "<b>" + tier + "</b>: " +
      (t.ready ? (t.provider + " / " + t.model) : t.reason);
    div.style.color = t.ready ? "var(--ok)" : "var(--muted)";
    status.appendChild(div);
  }
}

document.querySelectorAll(".ai-save").forEach(btn =>
  btn.addEventListener("click", async () => {
    const prov = btn.dataset.provider;
    const input = document.querySelector('input[data-provider="' + prov + '"]');
    await api("/api/ai/key", {
      method: "POST", body: JSON.stringify({ provider: prov, key: input.value }),
    });
    input.value = "";
    loadAiStatus();
  }));

document.querySelectorAll(".ai-clear").forEach(btn =>
  btn.addEventListener("click", async () => {
    await api("/api/ai/key", {
      method: "POST",
      body: JSON.stringify({ provider: btn.dataset.provider, key: "" }),
    });
    loadAiStatus();
  }));

$("#ai-save-routing").addEventListener("click", async () => {
  const routing = {};
  for (const tier of ["routine", "complex"]) {
    routing[tier] = {
      provider: document.querySelector('.route-provider[data-tier="' + tier + '"]').value,
      model: document.querySelector('.route-model[data-tier="' + tier + '"]').value,
    };
  }
  await api("/api/settings", {
    method: "POST",
    body: JSON.stringify({
      ai_routing: routing,
      ai_custom_base_url: $("#ai-custom-url").value,
    }),
  });
  $("#ai-routing-saved").classList.remove("hidden");
  setTimeout(() => $("#ai-routing-saved").classList.add("hidden"), 1500);
  loadAiStatus();
});

document.querySelectorAll(".ai-test").forEach(btn =>
  btn.addEventListener("click", async () => {
    const out = $("#ai-test-result");
    out.textContent = "testing " + btn.dataset.tier + "…";
    const r = await api("/api/ai/test", {
      method: "POST", body: JSON.stringify({ tier: btn.dataset.tier }),
    });
    if (r.ok) {
      const cost = r.cost_usd == null ? "cost unknown"
        : "$" + r.cost_usd.toFixed(6);
      out.style.color = "var(--ok)";
      out.textContent = "✓ " + r.provider + "/" + r.model + " → \"" + r.reply +
        "\" (" + r.input_tokens + "+" + r.output_tokens + " tok, " + cost + ")";
    } else {
      out.style.color = "#e05c5c";
      out.textContent = "✗ " + r.error;
    }
  }));

/* ---- boot ---- */
refreshStatus();
loadSettings();
loadProfiles();
loadAssets();
loadAiStatus();
setInterval(refreshStatus, 5000);
