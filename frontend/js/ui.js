/* =====================================================================
   SimpliFlix — utilidades de interface (namespace global SF)
   Formatação numérica (fração/decimal), criação de elementos, toasts,
   carregamento, modal e textos matemáticos.
   ===================================================================== */
window.SF = window.SF || {};

(function (SF) {
  'use strict';

  const state = SF.state = SF.state || {
    numMode: 'frac',      // 'frac' | 'dec'
    model: null,          // modelo em edição
    saved: null,          // cópia para "Restaurar modelo"
    results: null,        // última resposta de /api/solve/all
  };

  // ------------------------------------------------------------ DOM
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function h(html) {
    const t = document.createElement('template');
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  // ------------------------------------------------------------ números
  /** Converte texto exato ("5", "-3/4") em número JS. */
  function fracToFloat(s) {
    if (typeof s === 'number') return s;
    if (s == null) return NaN;
    const str = String(s);
    if (str.includes('/')) {
      const [a, b] = str.split('/');
      return Number(a) / Number(b);
    }
    return Number(str);
  }
  function decStr(x, places = 4) {
    if (!isFinite(x)) return String(x);
    let t = x.toFixed(places);
    t = t.replace(/\.?0+$/, '');
    if (t === '-0' || t === '') t = '0';
    return t.replace('-', '−');
  }
  function fracStr(s) { return String(s).replace(/^-/, '−').replace(/\/(?=\d)/, '/'); }
  /** Formata um valor da API: string exata, {c, m} (Grande M) ou objeto {exact, decimal}. */
  function fmt(v, mode) {
    mode = mode || state.numMode;
    if (v == null) return '—';
    if (typeof v === 'object' && 'exact' in v) v = v.exact;
    if (typeof v === 'object' && 'm' in v) return fmtM(v, mode);
    if (typeof v === 'number') return decStr(v);
    return mode === 'dec' ? decStr(fracToFloat(v)) : fracStr(v);
  }
  function fmtM(v, mode) {
    const one = x => (mode === 'dec' ? decStr(fracToFloat(x)) : fracStr(x));
    const c = fracToFloat(v.c), m = fracToFloat(v.m);
    let mt;
    const am = Math.abs(m);
    const amTxt = one(String(v.m).replace(/^-/, ''));
    mt = (am === 1 ? '' : amTxt) + 'M';
    if (c === 0) return (m < 0 ? '−' : '') + mt;
    return `${one(v.c)} ${m < 0 ? '−' : '+'} ${mt}`;
  }
  function valueOf(v) {
    if (v == null) return NaN;
    if (typeof v === 'object' && 'm' in v) return fracToFloat(v.m) * 1e12 + fracToFloat(v.c);
    if (typeof v === 'object' && 'exact' in v) return fracToFloat(v.exact);
    return fracToFloat(v);
  }

  /** Expressão linear: [3,-1,0] + nomes → "3X1 − X2" */
  function linear(coefs, names) {
    const parts = [];
    coefs.forEach((c, i) => {
      const x = fracToFloat(c);
      if (!isFinite(x) || x === 0) return;
      const neg = x < 0;
      let abs = String(c).trim().replace(/^[-+]/, '');
      const body = (Math.abs(x) === 1 ? '' : abs) + names[i];
      if (!parts.length) parts.push((neg ? '−' : '') + body);
      else parts.push((neg ? '− ' : '+ ') + body);
    });
    return parts.length ? parts.join(' ') : '0';
  }
  const OP = { '<=': '≤', '>=': '≥', '=': '=' };

  // ------------------------------------------------------------ feedback
  function toast(msg, type = 'info', timeout = 4200) {
    const box = $('#toasts');
    const el = h(`<div class="sf-toast ${type}" role="${type === 'error' ? 'alert' : 'status'}"><div>${msg}</div><button type="button" aria-label="Fechar">×</button></div>`);
    el.querySelector('button').onclick = () => el.remove();
    box.appendChild(el);
    if (timeout) setTimeout(() => el.remove(), timeout);
  }
  function loading(on, text) {
    const o = $('#loading');
    if (text) $('#loadingText').textContent = text;
    o.hidden = !on;
    document.body.setAttribute('aria-busy', on ? 'true' : 'false');
  }

  let modalInstance = null;
  function modal(title, bodyHtml, footerHtml = '') {
    $('#sfModalTitle').textContent = title;
    const body = $('#sfModalBody');
    if (typeof bodyHtml === 'string') body.innerHTML = bodyHtml; else { body.innerHTML = ''; body.appendChild(bodyHtml); }
    const foot = $('#sfModalFooter');
    foot.innerHTML = footerHtml || '<button type="button" class="btn btn-sf-ghost" data-bs-dismiss="modal">Fechar</button>';
    foot.hidden = false;
    modalInstance = modalInstance || new bootstrap.Modal($('#sfModal'));
    modalInstance.show();
    return { body, foot, hide: () => modalInstance.hide() };
  }

  function download(filename, data) {
    const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  function slug(s) {
    return (s || 'problema').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'problema';
  }

  function statusClass(st) {
    return ({ optimal: 'st-ok', infeasible: 'st-bad', unbounded: 'st-bad', iteration_limit: 'st-warn', not_applicable: 'st-warn',
      feasible: 'st-warn', limit_no_solution: 'st-warn', error: 'st-bad' })[st] || 'st-info';
  }

  /** Lê uma cor do tema atual (para Plotly). */
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  // ------------------------------------------------------------ tema
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    document.querySelector('meta[name="theme-color"]').setAttribute('content', t === 'light' ? '#f4f5fb' : '#0b0d17');
    try { localStorage.setItem('sf-theme', t); } catch (e) { /* armazenamento indisponível */ }
    document.dispatchEvent(new CustomEvent('sf:theme', { detail: t }));
  }
  function initTheme() {
    let t = null;
    try { t = localStorage.getItem('sf-theme'); } catch (e) { /* */ }
    if (!t) t = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    applyTheme(t);
    $('#themeToggle').addEventListener('click', () => {
      applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });
  }

  function store(key, val) { try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { /* */ } }
  function load(key) { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; } catch (e) { return null; } }

  SF.ui = { $, $$, esc, h, fmt, fmtM, fracToFloat, decStr, valueOf, linear, OP, toast, loading, modal, download, slug,
    statusClass, cssVar, initTheme, store, load };
})(window.SF);
