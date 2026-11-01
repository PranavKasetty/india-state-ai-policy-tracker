// The page's single source of state: filters plus view options. Views read it in
// render() and change it with store.set(); every change re-renders all views and
// is mirrored to the URL hash so a filtered view can be bookmarked or shared.
(function (T) {
  "use strict";
  function createStore(initial) {
    let state = { ...initial };
    const listeners = new Set();
    return {
      get: () => state,
      set(patch) {
        const next = { ...state, ...patch };
        if (Object.keys(next).every((k) => next[k] === state[k])) return;
        state = next;
        listeners.forEach((fn) => fn(state));
      },
      subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    };
  }

  /** Read known keys from the hash; ignore anything not in `defaults` or not in `allowed`. */
  function readHash(defaults, allowed = {}) {
    const params = new URLSearchParams(location.hash.slice(1));
    const out = {};
    for (const key of Object.keys(defaults)) {
      if (!params.has(key)) continue;
      const value = params.get(key);
      if (!allowed[key] || allowed[key].includes(value)) out[key] = value;
    }
    return out;
  }

  /** Write only the keys that differ from their defaults. */
  function writeHash(state, defaults) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(state)) if (value !== defaults[key]) params.set(key, value);
    const hash = params.toString();
    history.replaceState(null, "", hash ? `#${hash}` : location.pathname + location.search);
  }

  T.store = { createStore, readHash, writeHash };
})(window.Tracker = window.Tracker || {});
