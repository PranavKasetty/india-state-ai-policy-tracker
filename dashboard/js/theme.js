// Light / dark / system theme. "system" follows the OS; the other two pin it by
// setting data-theme on <html>, which css/tokens.css turns into color-scheme.
// The saved choice is a per-viewer convenience: if storage is blocked the page
// still works and simply follows the OS. index.html applies it before first paint.
(function (T) {
  "use strict";
  const KEY = "tracker-theme";
  const CHOICES = ["system", "light", "dark"];

  function saved() {
    try { const v = localStorage.getItem(KEY); return CHOICES.includes(v) ? v : "system"; } catch { return "system"; }
  }

  function apply(choice) {
    const root = document.documentElement;
    if (choice === "system") delete root.dataset.theme; else root.dataset.theme = choice;
    try { choice === "system" ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, choice); } catch { /* ignore */ }
  }

  function initTheme(group) {
    const buttons = [...group.querySelectorAll("[data-theme-choice]")];
    const sync = (choice) => buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeChoice === choice)));
    sync(saved());
    group.addEventListener("click", (e) => {
      const b = e.target.closest("[data-theme-choice]");
      if (!b) return;
      apply(b.dataset.themeChoice);
      sync(b.dataset.themeChoice);
    });
  }

  T.theme = { initTheme };
})(window.Tracker = window.Tracker || {});
