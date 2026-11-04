// The filter form. Writes to the store; render() reflects the store back into the
// controls (so matrix clicks and URL changes show up here too).
(function (T) {
  "use strict";
  const { monthLong } = T.format;

  const SEARCH_DELAY_MS = 250; // wait for typing to pause before filtering
  const FIELDS = ["state", "cat", "sector", "stage", "focus", "from", "to", "q"]; // store keys owned by this form

  function createFilters(form, { store, data, defaults }) {
    // Phones: the fields fold behind a button that counts the filters set.
    const toggle = form.querySelector("#filters-toggle");
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(open));
      form.classList.toggle("is-open", open);
    });
    const fieldValue = (el) => (el.type === "checkbox" ? (el.checked ? el.value : "") : el.value);

    const { meta } = data;
    const fill = (name, options) => {
      for (const [value, label] of options) form.elements[name].add(new Option(label, value));
    };
    fill("state", meta.states.map((s) => [s.name, s.name]));
    fill("cat", meta.categories.map((c) => [c.id, c.label]));
    fill("sector", meta.sectors.map((s) => [s, s]));
    // "Action taken" first: it is the useful cut. Data built before stages existed has no
    // meta.stages, and then the control is hidden.
    const stageLabel = Object.fromEntries((meta.stages || []).map((s) => [s.id, s.label]));
    if (meta.stages?.length) {
      fill("stage", [["action", "Action taken"], ...["decided", "underway", "announced"].map((id) => [id, stageLabel[id]])]);
    } else {
      form.elements.stage.closest("label").hidden = true;
    }
    fill("from", data.months.map((m) => [m, monthLong(m)]));
    fill("to", data.months.map((m) => [m, monthLong(m)]));

    let timer;
    form.addEventListener("input", (e) => {
      const { name } = e.target;
      if (!FIELDS.includes(name)) return;
      const value = fieldValue(e.target);
      clearTimeout(timer);
      if (name === "q") { timer = setTimeout(() => store.set({ q: value }), SEARCH_DELAY_MS); return; }
      const patch = { [name]: value };
      const s = { ...store.get(), ...patch };
      if (s.from > s.to) patch[name === "from" ? "to" : "from"] = value; // keep the range valid
      store.set(patch);
    });
    form.addEventListener("submit", (e) => e.preventDefault());
    form.addEventListener("reset", (e) => {
      e.preventDefault();
      clearTimeout(timer);
      store.set(Object.fromEntries(FIELDS.map((k) => [k, defaults[k]]))); // keeps view options
    });

    return {
      render({ state }) {
        for (const key of FIELDS) {
          const el = form.elements[key];
          if (el.type === "checkbox") el.checked = state[key] === el.value;
          else if (el !== document.activeElement || key !== "q") el.value = state[key];
          el.classList.toggle("is-set", state[key] !== defaults[key]);
        }
        // The date range counts once; search sits outside the folded fields.
        const set = ["state", "cat", "sector", "stage", "focus"].filter((k) => state[k] !== defaults[k]).length +
          (state.from !== defaults.from || state.to !== defaults.to ? 1 : 0);
        toggle.textContent = set ? `Filters (${set} set)` : "Filters";
      },
    };
  }

  T.filters = { createFilters };
})(window.Tracker = window.Tracker || {});
