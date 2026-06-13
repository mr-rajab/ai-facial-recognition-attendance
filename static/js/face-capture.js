/* Shared guided face-capture flow for the student registration and admin
 * "new student" pages. Both templates expose the same element IDs, so this
 * one script drives both. Safely no-ops if the capture markup is absent. */
(function () {
  "use strict";

  const POSES = [
    { key: "upper", label: "Look up",    short: "Upper", arrow: "↑", hint: "Tilt your head slightly up" },
    { key: "left",  label: "Turn left",  short: "Left",  arrow: "←", hint: "Turn your face to your left" },
    { key: "right", label: "Turn right", short: "Right", arrow: "→", hint: "Turn your face to your right" },
    { key: "lower", label: "Look down",  short: "Lower", arrow: "↓", hint: "Tilt your head slightly down" },
  ];
  const MAX_EDGE = 720; // downscale captured images so uploads stay small + fast

  const $ = (id) => document.getElementById(id);
  const video = $("vid"), stage = $("stage"), statusEl = $("status");
  if (!video || !stage) return; // not a capture page

  const shootBtn = $("shootBtn"), shootLabel = $("shootLabel"), flipBtn = $("flipBtn");
  const uploadBtn = $("uploadBtn"), fileInput = $("fileInput"), flash = $("flash");
  const faceBadge = $("faceBadge"), poseArrow = $("poseArrow");
  const thumbsEl = $("thumbs"), progressFill = $("progressFill"), progressText = $("progressText");
  const submitBtn = $("submitBtn"), submitLabel = $("submitLabel"), form = $("f");
  const clientError = $("clientError");

  const data = {};          // pose key -> dataURL
  let active = 0;           // index into POSES of the pose we're capturing next
  let facing = "user";      // "user" | "environment"
  let stream = null;
  let detector = null;      // optional FaceDetector
  let faceSeen = false;

  // ── Thumbnails ─────────────────────────────────────────────────
  POSES.forEach((p, i) => {
    const li = document.createElement("li");
    li.className = "reg-thumb";
    li.dataset.idx = i;
    li.innerHTML =
      '<span class="reg-thumb-img"><span class="reg-thumb-ph">' + p.arrow + '</span></span>' +
      '<span class="reg-thumb-label">' + p.short + '</span>';
    li.addEventListener("click", () => selectPose(i));
    thumbsEl.appendChild(li);
  });
  const thumbEls = Array.from(thumbsEl.children);

  function selectPose(i) { active = i; renderActive(); }

  function firstEmpty() {
    for (let i = 0; i < POSES.length; i++) if (!data[POSES[i].key]) return i;
    return -1;
  }

  function renderActive() {
    const p = POSES[active];
    shootLabel.textContent = (data[p.key] ? "Retake " : "Capture ") + p.short.toLowerCase();
    poseArrow.textContent = p.arrow;
    statusEl.textContent = p.label + " — " + p.hint + ".";
    thumbEls.forEach((el, i) => el.classList.toggle("is-active", i === active));
  }

  function refresh() {
    let done = 0;
    POSES.forEach((p, i) => {
      const has = !!data[p.key];
      if (has) done++;
      const t = thumbEls[i];
      t.classList.toggle("is-done", has);
      const img = t.querySelector(".reg-thumb-img");
      img.style.backgroundImage = has ? "url(" + data[p.key] + ")" : "";
    });
    progressFill.style.width = (done / POSES.length * 100) + "%";
    progressText.textContent = done + " of " + POSES.length + " angles captured";
    submitBtn.disabled = done < POSES.length;
    if (done === POSES.length) statusEl.textContent = "All angles captured. Fill in the details below.";
  }

  // ── Camera ─────────────────────────────────────────────────────
  async function startCamera() {
    stopCamera();
    stage.dataset.state = "loading";
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing }, audio: false });
      video.srcObject = stream;
      video.style.transform = facing === "user" ? "scaleX(-1)" : "none";
      stage.dataset.state = "live";
      shootBtn.disabled = false;
      renderActive();
      maybeStartDetection();
    } catch (e) {
      stage.dataset.state = "error";
      shootBtn.disabled = true;
      statusEl.textContent = "Camera unavailable — use “Upload a photo” to add each angle.";
      uploadBtn.classList.add("is-pulse");
    }
  }
  function stopCamera() {
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
  }

  if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
    navigator.mediaDevices.enumerateDevices().then(list => {
      if (list.filter(d => d.kind === "videoinput").length > 1) flipBtn.hidden = false;
    }).catch(() => {});
  }
  flipBtn.addEventListener("click", () => {
    facing = facing === "user" ? "environment" : "user";
    startCamera();
  });

  // ── Optional smart face detection (progressive enhancement) ────
  function maybeStartDetection() {
    if (detector || !("FaceDetector" in window)) return;
    try { detector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 }); }
    catch (_) { detector = null; return; }
    const tick = async () => {
      if (!stream || stage.dataset.state !== "live") return;
      try {
        const faces = await detector.detect(video);
        faceSeen = faces && faces.length > 0;
        stage.classList.toggle("has-face", faceSeen);
        faceBadge.hidden = !faceSeen;
      } catch (_) {}
      setTimeout(() => requestAnimationFrame(tick), 400);
    };
    tick();
  }

  // ── Capture ────────────────────────────────────────────────────
  function downscale(srcW, srcH) {
    const edge = Math.max(srcW, srcH);
    const s = edge > MAX_EDGE ? MAX_EDGE / edge : 1;
    return [Math.round(srcW * s), Math.round(srcH * s)];
  }

  function capture() {
    const vw = video.videoWidth || 640, vh = video.videoHeight || 480;
    const [w, h] = downscale(vw, vh);
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const ctx = c.getContext("2d");
    if (facing === "user") { ctx.translate(w, 0); ctx.scale(-1, 1); } // un-mirror to natural orientation
    ctx.drawImage(video, 0, 0, w, h);
    store(POSES[active].key, c.toDataURL("image/jpeg", 0.9));
    flash.classList.remove("is-on"); void flash.offsetWidth; flash.classList.add("is-on");
  }

  function store(key, url) {
    data[key] = url;
    $("img_" + key).value = url;
    refresh();
    const next = firstEmpty();
    if (next !== -1) selectPose(next); else renderActive();
  }

  shootBtn.addEventListener("click", capture);

  // ── Upload fallback ────────────────────────────────────────────
  uploadBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const [w, h] = downscale(img.width, img.height);
        const c = document.createElement("canvas");
        c.width = w; c.height = h;
        c.getContext("2d").drawImage(img, 0, 0, w, h);
        store(POSES[active].key, c.toDataURL("image/jpeg", 0.9));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
    fileInput.value = "";
  });

  // ── Password UX (optional on the page) ─────────────────────────
  const pw = $("password"), pwToggle = $("pwToggle"), pwStrength = $("pwStrength"),
        pwBar = $("pwBar"), pwLabel = $("pwLabel");
  if (pw && pwToggle) {
    pwToggle.addEventListener("click", () => {
      const show = pw.type === "password";
      pw.type = show ? "text" : "password";
      pwToggle.textContent = show ? "Hide" : "Show";
      pwToggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  }
  if (pw && pwStrength) {
    pw.addEventListener("input", () => {
      const v = pw.value;
      pwStrength.hidden = v.length === 0;
      let score = 0;
      if (v.length >= 6) score++;
      if (v.length >= 10) score++;
      if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
      if (/\d/.test(v)) score++;
      if (/[^A-Za-z0-9]/.test(v)) score++;
      const pct = Math.min(100, score * 22 + (v.length ? 12 : 0));
      const tiers = ["Very weak", "Weak", "Fair", "Good", "Strong", "Strong"];
      pwBar.style.width = pct + "%";
      pwBar.dataset.level = Math.min(4, score);
      pwLabel.textContent = tiers[Math.min(5, score)];
    });
  }

  // ── Email inline validation (optional) ─────────────────────────
  const email = $("email"), emailNote = $("emailNote");
  if (email && emailNote) {
    email.addEventListener("blur", () => {
      const v = email.value.trim();
      const ok = !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
      emailNote.hidden = ok;
      emailNote.textContent = ok ? "" : "Enter a valid email address.";
      email.classList.toggle("is-invalid", !ok);
    });
  }

  // ── Submit guard ───────────────────────────────────────────────
  form.addEventListener("submit", (e) => {
    if (clientError) clientError.hidden = true;
    if (firstEmpty() !== -1) {
      e.preventDefault();
      showError("Please capture all four face angles first.");
      return;
    }
    if (!form.checkValidity()) {
      e.preventDefault();
      showError("Please fill in all fields correctly.");
      form.reportValidity();
      return;
    }
    stopCamera();
    submitBtn.disabled = true;
    submitBtn.classList.add("is-loading");
    if (submitLabel) submitLabel.textContent = "Saving…";
  });

  function showError(msg) {
    if (!clientError) { alert(msg); return; }
    clientError.querySelector("p").textContent = msg;
    clientError.hidden = false;
    clientError.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // ── Go ─────────────────────────────────────────────────────────
  refresh();
  startCamera();
  window.addEventListener("pagehide", stopCamera);
})();
