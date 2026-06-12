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
  const res = await api("/api/rawcut", { method: "POST", body: "{}" });
  if (res.error) return jobDone({ error: res.error });
  pollTimer = setInterval(pollJob, 700);
});

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
    rep.innerHTML =
      '<div class="stat"><b>' + r.segments + "</b>segments</div>" +
      '<div class="stat"><b>' + r.removed_seconds + " s</b>removed</div>" +
      '<div class="stat"><b>' + r.output_seconds + " s</b>result</div>" +
      "<p class='muted'>New timeline: <b>" + r.timeline + "</b>" +
      (r.skipped_clips.length
        ? "<br>Skipped (no media pool item): " + r.skipped_clips.join(", ")
        : "") + "</p>";
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

/* ---- boot ---- */
refreshStatus();
loadSettings();
setInterval(refreshStatus, 5000);
