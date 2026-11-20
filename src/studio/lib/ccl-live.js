/* Chronic Care Loop · live mode for the Studio.
   When the page is served by backend/server.py (http), the cohort builder, the cohort and campaign library and the
   care-intelligence list read and write the relational backend. Opened as a file, everything stays on the built-in
   synthetic model. */
(function () {
  const origins = [];
  try { origins.push(location.origin); } catch (e) {}
  try { origins.push(parent.location.origin); } catch (e) {}
  const base = origins.find(o => /^https?:/.test(o || ''));
  if (!base) return;
  function api(method, path, body) {
    const x = new XMLHttpRequest();
    x.open(method, base + path, false);   // synchronous on purpose: the screens render estimates inline
    if (body) x.setRequestHeader('Content-Type', 'application/json');
    x.send(body ? JSON.stringify(body) : null);
    if (x.status !== 200) throw new Error(path + ' → ' + x.status + ' ' + x.responseText);
    return JSON.parse(x.responseText);
  }
  let health;
  try { health = api('GET', '/api/health'); } catch (e) { return; }
  if (!health || !health.ok || !health.members) return;   // no extract loaded: stay on the demo data

  const strip = r => ({ id: r.id, f: r.f, op: r.op, v: r.v, v2: r.v2, vs: r.vs || [], l: r.l });
  const toRule = (Eng, r) => { const n = Eng.newRule(r.f); return Object.assign(n, { op: r.op || n.op, v: r.v != null ? r.v : n.v, v2: r.v2 != null ? r.v2 : n.v2, vs: r.vs && r.vs.length ? r.vs : (n.vs || []), l: r.l || n.l }); };
  const L = window.CCL_API = { live: true, base, api, health, log: [] };

  /* exact counts from SQL (cached per rule set; the builder re-renders on every keystroke) */
  function liveEstimate(Eng, fallback) {
    const cache = {};
    return function (cb) {
      const inc = cb.inc.filter(Eng.ruleOn), exc = cb.exc.filter(Eng.ruleOn);
      const key = JSON.stringify([cb.base, cb.logic, inc.map(strip), exc.map(strip)]);
      if (!cache[key]) {
        try {
          const r = api('POST', '/api/cohorts/estimate', { base: cb.base, logic: cb.logic, inc: inc.map(strip), exc: exc.map(strip) });
          const all = inc.concat(exc);
          r.steps.forEach(s => { if (s.id === 'any') return; const rule = all.find(x => String(x.id) === String(s.id)); s.t = (s.ex ? 'Not: ' : '') + (rule ? Eng.ruleText(rule) : s.id); });
          inc.forEach(x => { if (r.alone[x.id] == null) r.alone[x.id] = r.B; });
          r.live = true; r.src = health.members + ' members in extract ' + health.as_of;
          cache[key] = r;
        } catch (e) { console.warn('[ccl] estimate fell back to the model', e); return fallback(cb); }
      }
      return cache[key];
    };
  }

  function cohortsFrom(Eng) {
    return api('GET', '/api/cohorts').cohorts.map(c => Object.assign(c, {
      rules: { logic: c.rules.logic, inc: c.rules.inc.map(r => toRule(Eng, r)), exc: c.rules.exc.map(r => toRule(Eng, r)) },
      def: c.rules.inc.map(r => Eng.ruleText(toRule(Eng, r))).join(' · '),
      trend: Eng.trend ? Eng.trend(Math.max(1, c.n), Eng.hash ? Eng.hash(c.id) : 7).map((v, i, a) => i === a.length - 1 ? c.n : Math.max(0, Math.round(v))) : [c.n],
      owner: c.owner === 'U-0201' ? 'Population health' : c.owner }));
  }
  const campaignsFrom = () => api('GET', '/api/campaigns').campaigns;

  L.saveCohort = coh => { try {
    const r = api('POST', '/api/cohorts', { id: coh.id, name: coh.name, base: coh.base, logic: coh.rules ? coh.rules.logic : 'all', refresh: coh.refresh, src: coh.src,
      inc: (coh.rules ? coh.rules.inc : []).map(strip), exc: (coh.rules ? coh.rules.exc : []).map(strip) });
    L.log.unshift('WRITE cohort ' + coh.id); return r; } catch (e) { console.warn('[ccl] cohort not saved', e); return null; } };
  L.saveCampaign = c => { try { const r = api('POST', '/api/campaigns', c); L.log.unshift('WRITE campaign ' + c.id); return r.campaign; } catch (e) { console.warn('[ccl] campaign not saved', e); return null; } };
  L.nightly = () => api('POST', '/api/runs/nightly', { actor: 'U-0310' });
  L.members = () => api('GET', '/api/intel').members;

  function patchE(E) {
    if (!E || E.__ccl) return; E.__ccl = 1;
    E.MIN_N = 1;   // the demo extract is small; the production threshold is 50
    E.estimate = liveEstimate(E, E.estimate);
    const pf = E.profile, sm = E.sample;
    E.profile = cb => { const e = E.estimate(cb); return e.live && e.profile ? e.profile : pf(cb); };
    E.sample = (cb, k) => { const e = E.estimate(cb); return e.live && e.sample ? e.sample.slice(0, k) : sm(cb, k); };
    E.BASES.forEach(b => { b.n = b.id === 'daman' ? health.members : b.id === 'seha' ? E.estimate({ base: 'seha', logic: 'all', inc: [], exc: [] }).B : 0; });
    const sc = E.seedCohorts, sk = E.seedCampaigns;
    E.seedCohorts = () => { try { return cohortsFrom(E); } catch (e) { return sc(); } };
    E.seedCampaigns = () => { try { return campaignsFrom(); } catch (e) { return sk(); } };
  }
  function patchC(C) {
    if (!C || C.__ccl) return; C.__ccl = 1;
    C.CLS.goal = ['Goal', '#E8F1EE', '#3F7A66'];
    C.estimate = liveEstimate(C, C.estimate);
    const mem = C.members;
    C.members = () => { try { const M = L.members(); return M.length ? M : mem(); } catch (e) { return mem(); } };
    try {
      const k = cohortsFrom(C); C.COHORTS.length = 0; k.forEach(x => C.COHORTS.push(x));
      const g = campaignsFrom(); C.CAMPAIGNS.length = 0; g.forEach(x => C.CAMPAIGNS.push(x));
    } catch (e) { console.warn('[ccl] library stays on the model', e); }
  }
  /* the runtime may load the engines before or after this file: patch now, or the moment they are assigned */
  [['CohortEngine', patchE], ['CCC', patchC]].forEach(([name, fn]) => {
    if (window[name]) { fn(window[name]); return; }
    let v; Object.defineProperty(window, name, { configurable: true, get: () => v, set: x => { v = x; fn(x); } });
  });
  document.documentElement.setAttribute('data-ccl-live', '1');
  console.info('[ccl] live mode · ' + health.members + ' members · run ' + health.run_id);
})();
