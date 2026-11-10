/* =====================================================================
   SimpliFlix — tela de modelagem
   Estado do modelo, formulário dinâmico, validação, importação/exportação.
   ===================================================================== */
(function (SF) {
  'use strict';
  const { $, $$, esc, h, linear, OP, toast } = SF.ui;
  const MAX_VARS = 12, MAX_CONS = 30;
  const NUM_RE = /^[-+]?(\d+([.,]\d*)?|[.,]\d+)$/;
  const FRAC_RE = /^[-+]?\d+\s*\/\s*\d+$/;

  // ------------------------------------------------------------ estado
  function blankModel(n = 2, m = 2) {
    return {
      name: 'Novo problema', sense: 'max', c: Array(n).fill('0'),
      vars: Array.from({ length: n }, () => ({ domain: 'continuous', sign: 'nonneg' })),
      cons: Array.from({ length: m }, () => ({ a: Array(n).fill('0'), op: '<=', b: '0' })),
      methods: { graphical: n === 2, algebraic: false, two_phase: false, big_m: false, dual_simplex: false },
      options: { rule: 'dantzig', maxIter: 200, maxNodes: 500, integer: true, dual: true },
    };
  }
  function normalize(m) {
    const base = blankModel(m.c.length, 0);
    const out = Object.assign(base, JSON.parse(JSON.stringify(m)));
    out.methods = Object.assign(base.methods, m.methods || {});
    out.options = Object.assign(blankModel().options, m.options || {});
    out.vars = out.c.map((_, j) => Object.assign({ domain: 'continuous', sign: 'nonneg' }, (m.vars || [])[j] || {}));
    if (out.c.length !== 2) out.methods.graphical = false;
    return out;
  }
  const clone = o => JSON.parse(JSON.stringify(o));
  const varName = j => `X${j + 1}`;
  const names = m => m.c.map((_, j) => varName(j));

  function current() { return SF.state.model; }
  let saveTimer = null;
  function changed(opts = {}) {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => SF.ui.store('sf-model', SF.state.model), 300);
    renderPreview();
    if (opts.full) render();
  }

  // ------------------------------------------------------------ validação (cliente)
  function isNum(s) {
    s = String(s ?? '').trim();
    if (NUM_RE.test(s)) return true;
    if (FRAC_RE.test(s)) return Number(s.split('/')[1]) !== 0;
    return false;
  }
  function numVal(s) { return SF.ui.fracToFloat(String(s).trim().replace(',', '.').replace(/\s/g, '')); }

  function validate(m) {
    const errs = [];
    const add = (field, msg) => errs.push({ field, msg });
    const chk = (v, field, label) => {
      if (String(v ?? '').trim() === '') add(field, `${label}: campo vazio (use 0 se não houver valor).`);
      else if (!isNum(v)) add(field, `${label}: "${v}" não é um número válido (ex.: 2, -1.5, 3/4).`);
    };
    m.c.forEach((v, j) => chk(v, `objective.coefficients.${j}`, `Coeficiente de ${varName(j)} em Z`));
    if (m.c.every(v => isNum(v) && numVal(v) === 0)) add('objective.coefficients.0', 'A função objetivo precisa de ao menos um coeficiente diferente de zero.');
    if (!m.cons.length) add('constraints', 'Adicione ao menos uma restrição.');
    m.cons.forEach((c, i) => {
      c.a.forEach((v, j) => chk(v, `constraints.${i}.coefficients.${j}`, `R${i + 1}, coeficiente de ${varName(j)}`));
      if (!OP[c.op]) add(`constraints.${i}.operator`, `R${i + 1}: escolha o operador (≤, ≥ ou =).`);
      chk(c.b, `constraints.${i}.rhs`, `R${i + 1}, lado direito`);
      if (c.a.every(v => isNum(v) && numVal(v) === 0)) add(`constraints.${i}.coefficients.0`, `R${i + 1}: todos os coeficientes são zero. Preencha ou remova a restrição.`);
    });
    return errs;
  }

  function markErrors(errs) {
    $$('#view-model .is-invalid').forEach(e => e.classList.remove('is-invalid'));
    errs.forEach(e => {
      const el = document.querySelector(`[data-field="${e.field}"]`);
      if (el) { el.classList.add('is-invalid'); el.setAttribute('aria-invalid', 'true'); }
    });
  }
  function showErrorBox(title, list) {
    const box = $('#modelErrors');
    if (!list || !list.length) { box.hidden = true; return; }
    box.innerHTML = `<strong>${esc(title)}</strong><ul>${list.map(e => `<li>${esc(e.msg || e.message)}</li>`).join('')}</ul>`;
    box.hidden = false;
  }

  // ------------------------------------------------------------ payload da API
  function toPayload(m) {
    const clean = v => String(v).trim().replace(/\s/g, '');
    const methods = ['simplex'];
    Object.entries(m.methods).forEach(([k, on]) => { if (on && !(k === 'graphical' && m.c.length !== 2)) methods.push(k); });
    return {
      name: m.name || 'Problema',
      objective: { type: m.sense, coefficients: m.c.map(clean) },
      variables: m.vars.map((v, j) => ({ name: varName(j), domain: v.domain, sign: v.sign })),
      constraints: m.cons.map((c, i) => ({ name: `R${i + 1}`, coefficients: c.a.map(clean), operator: c.op, rhs: clean(c.b) })),
      options: {
        methods, pivot_rule: m.options.rule, max_iterations: Number(m.options.maxIter) || 200,
        max_nodes: Number(m.options.maxNodes) || 500, include_integer: !!m.options.integer, include_dual: !!m.options.dual,
      },
    };
  }

  /** Aceita o formato da API, o arquivo salvo pelo SimpliFlix ou um resultado exportado. */
  function fromJson(json) {
    let p = json;
    if (p && p.format === 'simpliflix-model' && p.model) p = p.model;
    if (p && p.model_json) p = p.model_json;
    if (p && p.data && p.data.model_json) p = p.data.model_json;
    if (!p || !p.objective || !Array.isArray(p.objective.coefficients)) throw new Error('Arquivo não contém um modelo do SimpliFlix (campo "objective" ausente).');
    const n = p.objective.coefficients.length;
    if (!n || n > MAX_VARS) throw new Error(`O modelo deve ter entre 1 e ${MAX_VARS} variáveis.`);
    const s = v => (v === null || v === undefined ? '' : String(v));
    const vars = (p.variables || []).slice(0, n).map(v => {
      let sign = v.sign;
      if (!sign) sign = (v.lower_bound === null && (v.upper_bound === 0)) ? 'nonpos' : (v.lower_bound === null ? 'free' : 'nonneg');
      return { domain: v.domain === 'integer' ? 'integer' : 'continuous', sign };
    });
    const opt = p.options || {};
    const methods = {};
    (opt.methods || []).forEach(k => { methods[k] = true; });
    return normalize({
      name: p.name || 'Problema importado',
      sense: String(p.objective.type).toLowerCase().startsWith('min') ? 'min' : 'max',
      c: p.objective.coefficients.map(s), vars,
      cons: (p.constraints || []).slice(0, MAX_CONS).map(c => ({ a: (c.coefficients || []).map(s), op: c.operator === '≤' ? '<=' : c.operator === '≥' ? '>=' : c.operator, b: s(c.rhs) })),
      methods: Object.keys(methods).length ? methods : undefined,
      options: { rule: opt.pivot_rule || 'dantzig', maxIter: opt.max_iterations || 200, maxNodes: opt.max_nodes || 500,
        integer: opt.include_integer !== false, dual: opt.include_dual !== false },
    });
  }

  function fromExample(ex) {
    return normalize(Object.assign(clone(ex.model), { methods: { graphical: ex.model.c.length === 2 } }));
  }

  // ------------------------------------------------------------ renderização
  function render() {
    const m = current();
    $('#probName').value = m.name;
    $$('#senseGroup button').forEach(b => b.setAttribute('aria-checked', String(b.dataset.sense === m.sense)));
    $('#nvarValue').textContent = m.c.length;
    $('#nvarMinus').disabled = m.c.length <= 1;
    $('#nvarPlus').disabled = m.c.length >= MAX_VARS;
    renderVars();
    renderCons();
    renderMethods();
    renderOptions();
    renderPreview();
  }

  function renderVars() {
    const m = current();
    const grid = $('#varGrid');
    grid.innerHTML = m.c.map((v, j) => `
      <div class="var-card">
        <label class="d-flex align-items-center justify-content-between mb-1" for="c_${j}">
          <span class="vname">${varName(j)}</span><span class="text-muted small">coef. em Z</span></label>
        <input id="c_${j}" class="form-control sf-input num-input" inputmode="decimal" autocomplete="off"
          data-field="objective.coefficients.${j}" data-kind="c" data-j="${j}" value="${esc(v)}" aria-label="Coeficiente de ${varName(j)} na função objetivo">
        <div class="vrow">
          <div class="flex-fill"><label class="mini" for="d_${j}">Domínio</label>
            <select id="d_${j}" class="form-select sf-input" data-kind="domain" data-j="${j}">
              <option value="continuous"${m.vars[j].domain === 'continuous' ? ' selected' : ''}>Contínua</option>
              <option value="integer"${m.vars[j].domain === 'integer' ? ' selected' : ''}>Inteira</option>
            </select></div>
          <div class="flex-fill"><label class="mini" for="s_${j}">Sinal</label>
            <select id="s_${j}" class="form-select sf-input" data-kind="sign" data-j="${j}">
              <option value="nonneg"${m.vars[j].sign === 'nonneg' ? ' selected' : ''}>≥ 0</option>
              <option value="nonpos"${m.vars[j].sign === 'nonpos' ? ' selected' : ''}>≤ 0</option>
              <option value="free"${m.vars[j].sign === 'free' ? ' selected' : ''}>Livre</option>
            </select></div>
        </div>
      </div>`).join('');
  }

  function renderCons() {
    const m = current();
    const list = $('#consList');
    if (!m.cons.length) {
      list.innerHTML = '<div class="empty-state py-3">Nenhuma restrição. Clique em <b>Adicionar restrição</b>.</div>';
      return;
    }
    list.innerHTML = m.cons.map((c, i) => `
      <div class="cons-row" data-i="${i}">
        <span class="cons-id">R${i + 1}</span>
        <div class="cons-terms">
          ${c.a.map((v, j) => `<span class="term">${j ? '<span class="plus">+</span>' : ''}
            <input class="form-control sf-input num-input" inputmode="decimal" autocomplete="off" value="${esc(v)}"
              data-field="constraints.${i}.coefficients.${j}" data-kind="a" data-i="${i}" data-j="${j}"
              aria-label="R${i + 1}: coeficiente de ${varName(j)}"><span class="tv">${varName(j)}</span></span>`).join('')}
        </div>
        <div class="cons-tail d-flex gap-2">
          <select class="form-select sf-input cons-op" data-field="constraints.${i}.operator" data-kind="op" data-i="${i}" aria-label="R${i + 1}: operador">
            <option value="<="${c.op === '<=' ? ' selected' : ''}>≤</option>
            <option value=">="${c.op === '>=' ? ' selected' : ''}>≥</option>
            <option value="="${c.op === '=' ? ' selected' : ''}>=</option>
          </select>
          <input class="form-control sf-input num-input cons-rhs" inputmode="decimal" autocomplete="off" value="${esc(c.b)}"
            data-field="constraints.${i}.rhs" data-kind="b" data-i="${i}" aria-label="R${i + 1}: lado direito">
        </div>
        <button type="button" class="cons-del" data-del="${i}" aria-label="Remover restrição R${i + 1}" title="Remover restrição">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M9 3v1H4v2h1v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6h1V4h-5V3zm-2 3h10v13H7zm2 2v9h2V8zm4 0v9h2V8z"/></svg>
        </button>
      </div>`).join('');
  }

  function renderMethods() {
    const m = current();
    const n = m.c.length;
    $('#methodCards').innerHTML = SF.methodsInfo.map(info => {
      const locked = info.key === 'simplex';
      const disabled = info.key === 'graphical' && n !== 2;
      const on = locked || (!disabled && !!m.methods[info.key]);
      const badge = locked ? '<span class="mc-badge">Obrigatório</span>' :
        disabled ? '<span class="mc-badge">Requer 2 variáveis</span>' : '';
      return `<button type="button" class="method-card" data-method="${info.key}" aria-pressed="${on}"
        ${disabled ? 'disabled' : ''} ${locked ? 'aria-disabled="true"' : ''}>
        <span class="mc-check" aria-hidden="true">✓</span>
        <span class="mc-title">${info.title}</span>
        <span class="mc-desc">${info.desc}</span>${badge}</button>`;
    }).join('');
  }

  function renderOptions() {
    const o = current().options;
    $('#optRule').value = o.rule;
    $('#optIter').value = o.maxIter;
    $('#optNodes').value = o.maxNodes;
    $('#optInteger').checked = !!o.integer;
    $('#optDualCalc').checked = !!o.dual;
  }

  function signsText(m) {
    const groups = { nonneg: [], nonpos: [], free: [] };
    m.vars.forEach((v, j) => groups[v.sign].push(varName(j)));
    const out = [];
    if (groups.nonneg.length) out.push(`${groups.nonneg.join(', ')} ≥ 0`);
    if (groups.nonpos.length) out.push(`${groups.nonpos.join(', ')} ≤ 0`);
    if (groups.free.length) out.push(`${groups.free.join(', ')} livre${groups.free.length > 1 ? 's' : ''}`);
    return out;
  }

  function renderPreview() {
    const m = current();
    const nm = names(m);
    const safe = arr => arr.map(v => (isNum(v) ? String(v).trim().replace(',', '.') : '0'));
    const obj = `${m.sense.toUpperCase()} Z = ${linear(safe(m.c), nm)}`;
    $('#objPreview').innerHTML = `<b>${m.sense.toUpperCase()}</b> Z = ${esc(linear(safe(m.c), nm))}`;
    const cons = m.cons.map((c, i) => `<div class="cl"><span class="rn">R${i + 1}</span>${esc(linear(safe(c.a), nm))} ${OP[c.op] || '?'} ${esc(isNum(c.b) ? String(c.b).trim() : '?')}</div>`).join('');
    const signs = signsText(m);
    const ints = m.vars.map((v, j) => (v.domain === 'integer' ? varName(j) : null)).filter(Boolean);
    $('#signsLine').textContent = signs.join(';  ') + (ints.length ? `;  ${ints.join(', ')} inteira${ints.length > 1 ? 's' : ''}` : '');
    $('#livePreview').innerHTML = `<div class="obj">${esc(obj)}</div><div class="st">sujeito a</div>${cons || '<div class="text-muted">sem restrições</div>'}
      <div class="cl mt-1">${esc(signs.join('; '))}</div>${ints.length ? `<div class="cl">${esc(ints.join(', '))} ∈ ℤ</div>` : ''}`;
    const nArt = m.cons.filter(c => c.op !== '<=' || (isNum(c.b) && numVal(c.b) < 0)).length;
    $('#previewMeta').innerHTML = `
      <span class="tag ${m.sense === 'max' ? 't-max' : 't-min'}">${m.sense === 'max' ? 'Maximização' : 'Minimização'}</span>
      <span class="tag">${m.c.length} variáve${m.c.length > 1 ? 'is' : 'l'}</span>
      <span class="tag">${m.cons.length} restriç${m.cons.length === 1 ? 'ão' : 'ões'}</span>
      ${ints.length ? '<span class="tag t-int">Inteira</span>' : ''}
      ${nArt ? '<span class="tag t-warn">Exige artificiais</span>' : ''}`;
    const errs = validate(m);
    $('#liveIssues').innerHTML = errs.length
      ? `<ul>${errs.slice(0, 4).map(e => `<li>${esc(e.msg)}</li>`).join('')}${errs.length > 4 ? `<li>+${errs.length - 4} pendência(s)</li>` : ''}</ul>`
      : '<span class="ok">✓ Modelo pronto para resolver</span>';
  }

  // ------------------------------------------------------------ ações
  function setN(n) {
    const m = current();
    n = Math.max(1, Math.min(MAX_VARS, n));
    while (m.c.length < n) { m.c.push('0'); m.vars.push({ domain: 'continuous', sign: 'nonneg' }); m.cons.forEach(c => c.a.push('0')); }
    while (m.c.length > n) { m.c.pop(); m.vars.pop(); m.cons.forEach(c => c.a.pop()); }
    if (n !== 2) m.methods.graphical = false;
    changed({ full: true });
  }
  function addCons() {
    const m = current();
    if (m.cons.length >= MAX_CONS) { toast(`Limite de ${MAX_CONS} restrições.`, 'warning'); return; }
    m.cons.push({ a: Array(m.c.length).fill('0'), op: '<=', b: '0' });
    changed({ full: true });
    const last = $$('#consList .cons-row').pop();
    if (last) last.querySelector('input').focus();
  }
  function removeCons(i) {
    const m = current();
    m.cons.splice(i, 1);
    changed({ full: true });
    toast(`Restrição R${i + 1} removida. As demais foram renumeradas.`, 'info', 2500);
  }
  function clearModel() {
    SF.state.saved = clone(current());
    const keep = current().c.length;
    SF.state.model = blankModel(keep, 1);
    showErrorBox(null);
    changed({ full: true });
    toast('Modelo limpo. Use <b>Restaurar modelo</b> para desfazer.', 'info');
  }
  function restoreModel() {
    if (!SF.state.saved) { toast('Não há versão anterior para restaurar.', 'warning'); return; }
    SF.state.model = normalize(clone(SF.state.saved));
    showErrorBox(null);
    changed({ full: true });
    toast('Modelo restaurado.', 'success', 2500);
  }

  function load(model, { snapshot = true } = {}) {
    SF.state.model = normalize(model);
    if (snapshot) SF.state.saved = clone(SF.state.model);
    showErrorBox(null);
    changed({ full: true });
  }

  function saveJson() {
    const m = current();
    SF.ui.download(`${SF.ui.slug(m.name)}.json`, { format: 'simpliflix-model', version: 1, model: toPayload(m) });
    toast('Modelo salvo em JSON.', 'success', 2500);
  }

  function openFile(file, after) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const json = JSON.parse(reader.result);
        load(fromJson(json));
        toast(`Modelo “${esc(current().name)}” carregado.`, 'success');
        if (after) after();
      } catch (e) {
        toast(`Não foi possível abrir o arquivo: ${esc(e.message)}`, 'error', 7000);
      }
    };
    reader.onerror = () => toast('Falha ao ler o arquivo.', 'error');
    reader.readAsText(file);
  }

  // ------------------------------------------------------------ formulação / dual
  async function showFormulation() {
    const m = current();
    const errs = validate(m);
    if (errs.length) { markErrors(errs); showErrorBox('Corrija o modelo para visualizar a formulação:', errs); return; }
    const box = SF.ui.modal('Formulação matemática', '<div class="text-muted">Carregando forma padrão…</div>');
    try {
      const d = await SF.api.validate(toPayload(m));
      const f = d.model.formulation;
      const sf = d.standard_form;
      box.body.innerHTML = `
        <div class="two-col">
          <div class="panel"><h4>Modelo original</h4><div class="math-block">
            <div class="obj">${esc(f.objective)}</div><div class="st">sujeito a</div>
            ${f.constraints.map(c => `<div class="cl"><span class="rn">${esc(c.name)}</span>${esc(c.text)}</div>`).join('')}
            ${f.signs.map(s => `<div class="cl">${esc(s)}</div>`).join('')}
            ${f.integrality ? `<div class="cl">${esc(f.integrality)}</div>` : ''}</div></div>
          <div class="panel"><h4>Forma padrão (Simplex)</h4><div class="std-form">
            <div><b>${esc(sf.objective)}</b></div>
            ${sf.constraints.map(c => `<div>${esc(c)}</div>`).join('')}
            <div>${esc(sf.nonnegativity)}</div>
            ${sf.notes.length ? `<div class="notes">${sf.notes.map(esc).join('<br>')}</div>` : ''}</div></div>
        </div>
        <p class="text-muted small mt-3 mb-0">Folgas (S) entram nas restrições ≤, excessos (E) nas ≥ e artificiais (A) nas ≥ e =.
          ${d.needs_artificial ? 'Este modelo exige variáveis artificiais: o Simplex usará a Fase 1 (ou o Grande M).' : 'A base inicial é formada pelas folgas (origem).'}</p>`;
    } catch (e) {
      box.body.innerHTML = `<div class="sf-alert sf-alert-danger">${esc(e.message)}</div>`;
    }
  }

  async function showDual() {
    const m = current();
    const errs = validate(m);
    if (errs.length) { markErrors(errs); showErrorBox('Corrija o modelo antes de convertê-lo em dual:', errs); return; }
    const box = SF.ui.modal('Conversão primal → dual', '<div class="text-muted">Convertendo…</div>');
    try {
      const d = await SF.api.dualForm(toPayload(m));
      box.body.innerHTML = SF.dual.formulationHtml(d);
      box.foot.innerHTML = `<button type="button" class="btn btn-sf-ghost" data-bs-dismiss="modal">Fechar</button>
        <button type="button" class="btn btn-sf-primary" id="openDualEditor">Abrir o dual no editor</button>`;
      box.foot.querySelector('#openDualEditor').onclick = () => {
        load(fromJson(d.dual_model));
        box.hide();
        toast('O problema dual foi carregado no editor. O primal pode ser recuperado com “Restaurar modelo”.', 'success', 6000);
        SF.state.saved = clone(m);
      };
    } catch (e) {
      box.body.innerHTML = `<div class="sf-alert sf-alert-danger">${esc(e.message)}</div>`;
    }
  }

  // ------------------------------------------------------------ resolver
  async function solve() {
    const m = current();
    const errs = validate(m);
    markErrors(errs);
    if (errs.length) {
      showErrorBox(`O modelo possui ${errs.length} pendência${errs.length > 1 ? 's' : ''}:`, errs);
      toast('Corrija os campos destacados antes de resolver.', 'error');
      const first = document.querySelector('#view-model .is-invalid');
      if (first) first.focus();
      else $('#modelErrors').scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    showErrorBox(null);
    SF.ui.loading(true, 'Executando o Simplex…');
    const t0 = performance.now();
    try {
      const data = await SF.api.solveAll(toPayload(m));
      SF.state.saved = clone(m);
      SF.state.results = data;
      try { sessionStorage.setItem('sf-results', JSON.stringify(data)); } catch (e) { /* resultado grande demais */ }
      const ms = Math.round(performance.now() - t0);
      toast(`${esc(data.summary.status_label)} · ${ms} ms`, data.summary.status === 'optimal' ? 'success' : 'warning');
      if (location.hash === '#/resultados') SF.results.render();
      else location.hash = '#/resultados';
    } catch (e) {
      if (e.details && e.details.length) {
        const mapped = e.details.map(d => ({ field: d.field, msg: d.message }));
        markErrors(mapped);
        showErrorBox(e.message, mapped);
      }
      toast(esc(e.message), 'error', 8000);
    } finally {
      SF.ui.loading(false);
    }
  }

  // ------------------------------------------------------------ eventos
  function bind() {
    $('#probName').addEventListener('input', e => { current().name = e.target.value; changed(); });
    $('#senseGroup').addEventListener('click', e => {
      const b = e.target.closest('button[data-sense]');
      if (!b) return;
      current().sense = b.dataset.sense;
      $$('#senseGroup button').forEach(x => x.setAttribute('aria-checked', String(x === b)));
      changed();
    });
    $('#senseGroup').addEventListener('keydown', e => {
      if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      current().sense = current().sense === 'max' ? 'min' : 'max';
      render();
      $(`#senseGroup [data-sense="${current().sense}"]`).focus();
      changed();
    });
    $('#nvarMinus').addEventListener('click', () => setN(current().c.length - 1));
    $('#nvarPlus').addEventListener('click', () => setN(current().c.length + 1));

    const view = $('#view-model');
    view.addEventListener('input', e => {
      const t = e.target, k = t.dataset.kind;
      if (!k) return;
      const m = current();
      const i = Number(t.dataset.i), j = Number(t.dataset.j);
      if (k === 'c') m.c[j] = t.value;
      else if (k === 'a') m.cons[i].a[j] = t.value;
      else if (k === 'b') m.cons[i].b = t.value;
      else return;
      if (t.classList.contains('is-invalid') && isNum(t.value)) { t.classList.remove('is-invalid'); t.removeAttribute('aria-invalid'); }
      changed();
    });
    view.addEventListener('change', e => {
      const t = e.target, k = t.dataset.kind;
      const m = current();
      if (k === 'domain') m.vars[Number(t.dataset.j)].domain = t.value;
      else if (k === 'sign') m.vars[Number(t.dataset.j)].sign = t.value;
      else if (k === 'op') m.cons[Number(t.dataset.i)].op = t.value;
      else return;
      changed();
    });
    view.addEventListener('focusin', e => {
      if (e.target.matches('input.num-input')) setTimeout(() => e.target.select(), 0);
    });
    $('#consList').addEventListener('click', e => {
      const b = e.target.closest('[data-del]');
      if (b) removeCons(Number(b.dataset.del));
    });
    // Enter em um campo numérico avança para o próximo
    view.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.ctrlKey && e.target.matches('input.num-input')) {
        e.preventDefault();
        const all = $$('#view-model input.num-input');
        const idx = all.indexOf(e.target);
        if (idx >= 0 && idx < all.length - 1) all[idx + 1].focus();
      }
    });
    $('#methodCards').addEventListener('click', e => {
      const b = e.target.closest('.method-card');
      if (!b || b.disabled) return;
      const key = b.dataset.method;
      if (key === 'simplex') { toast('O Simplex Tabular é o método principal e é sempre executado.', 'info', 3000); return; }
      current().methods[key] = !current().methods[key];
      b.setAttribute('aria-pressed', String(current().methods[key]));
      changed();
    });
    $('#optRule').addEventListener('change', e => { current().options.rule = e.target.value; changed(); });
    $('#optIter').addEventListener('change', e => { current().options.maxIter = Math.max(1, Math.min(1000, Number(e.target.value) || 200)); e.target.value = current().options.maxIter; changed(); });
    $('#optNodes').addEventListener('change', e => { current().options.maxNodes = Math.max(1, Math.min(5000, Number(e.target.value) || 500)); e.target.value = current().options.maxNodes; changed(); });
    $('#optInteger').addEventListener('change', e => { current().options.integer = e.target.checked; changed(); });
    $('#optDualCalc').addEventListener('change', e => { current().options.dual = e.target.checked; changed(); });

    $('#btnAddCons').addEventListener('click', addCons);
    $('#btnClear').addEventListener('click', clearModel);
    $('#btnRestore').addEventListener('click', restoreModel);
    $('#btnFormulation').addEventListener('click', showFormulation);
    $('#btnDual').addEventListener('click', showDual);
    $('#btnSolve').addEventListener('click', solve);
    $('#btnSolveMobile').addEventListener('click', solve);
    $('#btnSaveModel').addEventListener('click', saveJson);
    $('#fileOpenModel').addEventListener('change', e => { openFile(e.target.files[0]); e.target.value = ''; });
    document.addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !$('#view-model').hidden) { e.preventDefault(); solve(); }
    });
  }

  function init() {
    const saved = SF.ui.load('sf-model');
    SF.state.model = saved ? normalize(saved) : fromExample(SF.examples[0]);
    bind();
    render();
  }

  SF.model = { init, render, load, blankModel, fromExample, fromJson, toPayload, openFile, validate, normalize, current, solve };
})(window.SF);
