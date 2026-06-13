document.documentElement.classList.add("js");

document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav-links]");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const isOpen = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(isOpen));
    });
  }

  document.querySelectorAll("[data-confirm]").forEach((el) => {
    el.addEventListener("submit", (event) => {
      const message = el.getAttribute("data-confirm");
      if (message && !window.confirm(message)) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll(".table-wrap").forEach((wrap) => {
    const table = wrap.querySelector("table");
    if (table && table.scrollWidth > wrap.clientWidth) {
      wrap.dataset.overflow = "true";
    }
  });

  // Live unread badge for the Support nav link.
  const supportBadges = document.querySelectorAll("[data-support-badge]");
  if (supportBadges.length) {
    const refreshBadges = () => {
      fetch("/api/notifications.json", { credentials: "same-origin" })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (!d) return;
          supportBadges.forEach((el) => {
            if (d.support > 0) { el.textContent = d.support; el.hidden = false; }
            else { el.hidden = true; }
          });
        })
        .catch(() => {});
    };
    refreshBadges();
    setInterval(refreshBadges, 20000);
  }

  // Dark-mode toggle: flip <html data-theme>, persist choice, sync address-bar colour.
  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
      const meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute("content", next === "dark" ? "#0e1217" : "#0f766e");
    });
  });
});
