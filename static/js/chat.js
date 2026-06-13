/* Shared live-chat engine for the group chat and support threads.
 * Drives any element marked:
 *   <div data-chat data-endpoint="…/messages.json" data-last="<id>">
 *     <div data-chat-log>…server-rendered messages…</div>
 *     <form data-chat-form action="…/send" method="post"> <… name="body"> </form>
 *   </div>
 * Polls for new messages and posts without a full page reload. */
(function () {
  "use strict";

  const root = document.querySelector("[data-chat]");
  if (!root) return;

  const log = root.querySelector("[data-chat-log]");
  const form = root.querySelector("[data-chat-form]");
  const field = form ? form.querySelector('[name="body"]') : null;
  const endpoint = root.getAttribute("data-endpoint");
  const deleteTmpl = root.getAttribute("data-delete-url"); // e.g. "/chat/__ID__/delete" (admin only)
  let last = parseInt(root.getAttribute("data-last") || "0", 10) || 0;
  let polling = false;

  function attachDelete(row, id) {
    if (!deleteTmpl || !id) return;
    const meta = row.querySelector(".chat-meta");
    if (!meta || meta.querySelector(".chat-del")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chat-del";
    btn.title = "Delete announcement";
    btn.setAttribute("aria-label", "Delete announcement");
    btn.textContent = "Delete";
    btn.addEventListener("click", async () => {
      if (!window.confirm("Delete this announcement? This cannot be undone.")) return;
      btn.disabled = true;
      try {
        const res = await fetch(deleteTmpl.replace("__ID__", id), {
          method: "POST",
          headers: { "X-Requested-With": "fetch", "Content-Type": "application/x-www-form-urlencoded" },
          credentials: "same-origin",
          body: "_=1", // a non-empty body is required (the proxy rejects empty POSTs)
        });
        if (res.ok) { row.remove(); } else { btn.disabled = false; }
      } catch (e) { btn.disabled = false; }
    });
    meta.appendChild(btn);
  }

  // Wire delete onto any server-rendered cards present on load.
  if (deleteTmpl) {
    Array.from(log.querySelectorAll(".chat-msg[data-id]")).forEach((row) => {
      attachDelete(row, row.getAttribute("data-id"));
    });
  }

  function nearBottom() {
    return log.scrollHeight - log.scrollTop - log.clientHeight < 120;
  }
  function toBottom() { log.scrollTop = log.scrollHeight; }

  function fmtTime(iso) {
    try {
      const d = new Date(iso);
      if (isNaN(d)) return "";
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch (e) { return ""; }
  }

  function addMessage(m) {
    const empty = log.querySelector(".chat-empty");
    if (empty) empty.remove();
    const row = document.createElement("div");
    row.className = "chat-msg" + (m.mine ? " is-mine" : "") + (m.role === "admin" ? " is-admin" : "");
    if (m.id) row.dataset.id = m.id;

    const meta = document.createElement("div");
    meta.className = "chat-meta";
    const who = document.createElement("span");
    who.className = "chat-who";
    who.textContent = m.mine ? "You" : m.name;
    meta.appendChild(who);
    if (m.role === "admin") {
      const tag = document.createElement("span");
      tag.className = "chat-tag";
      tag.textContent = "Admin";
      meta.appendChild(tag);
    }
    const time = document.createElement("span");
    time.className = "chat-time";
    time.textContent = fmtTime(m.at);
    meta.appendChild(time);

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    bubble.textContent = m.body; // textContent → safe from HTML injection

    row.appendChild(meta);
    row.appendChild(bubble);
    log.appendChild(row);
    attachDelete(row, m.id);
  }

  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const res = await fetch(endpoint + (endpoint.indexOf("?") >= 0 ? "&" : "?") + "after=" + last, {
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin",
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.messages && data.messages.length) {
        const stick = nearBottom();
        data.messages.forEach((m) => { addMessage(m); if (m.id > last) last = m.id; });
        if (stick) toBottom();
      }
    } catch (e) { /* offline / transient — try again next tick */ }
    finally { polling = false; }
  }

  if (form && field) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = field.value.trim();
      if (!text) return;
      const btn = form.querySelector('[type="submit"]');
      if (btn) btn.disabled = true;
      try {
        await fetch(form.getAttribute("action"), {
          method: "POST",
          headers: { "X-Requested-With": "fetch", "Content-Type": "application/x-www-form-urlencoded" },
          credentials: "same-origin",
          body: "body=" + encodeURIComponent(text),
        });
        field.value = "";
        field.style.height = "";
        await poll();
        toBottom();
      } catch (e) { /* keep text so the user can retry */ }
      finally { if (btn) btn.disabled = false; field.focus(); }
    });

    // Enter to send, Shift+Enter for newline (when the field is a textarea)
    field.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
    // auto-grow textarea
    field.addEventListener("input", () => {
      if (field.tagName === "TEXTAREA") {
        field.style.height = "auto";
        field.style.height = Math.min(field.scrollHeight, 160) + "px";
      }
    });
  }

  toBottom();
  setInterval(poll, 4000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
})();
