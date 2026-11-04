/* =====================================================================
   SimpliFlix — tela de resultados (painel lateral + abas)
   ===================================================================== */
(function (SF) {
  'use strict';
  const { $, esc, fmt, statusClass } = SF.ui;
  let activeTab = 'summary';

  const TAB_DEFS = [
    { key: 'summary', label: 'Resumo' },
    { key: 'graph', label: 'Método Gráfico' },
    { key: 'simplex', label: 'Simplex Tabular' },
    { key: 'algebraic', label: 'Método Algébrico' },
    { key: 'integer', label: 'Solução Inteira' },
    { key: 'dual', label: 'Solução Dual' },
    { key: 'analysis', label: 'Análise Matemática' },
  ];

  function availableTabs(r) {
    return TAB_DEFS.filter(t => {
      if (t.key === 'graph') return r.graphical && r.graphical.available;
      if (t.key === 'algebraic') return !!r.algebraic;
      if (t.key === 'integer') return !!r.integer;
      if (t.key === 'dual') return !!r.dual;
      return true;
    });
  }

  // ------------------------------------------------------------ painel lateral
  function sideHtml(r) {
    const m = r.model, s = r.summary, f = m.formulation;
    const zl = m.sense === 'max' ? 'Z máximo' : 'Z mínimo';
    return `
      <div class="side-card">
        <h3>Problema</h3>
        <div class="fw-bold mb-1">${esc(m.name)}</div>
        <div class="math-block small">
          <div class="obj">${esc(f.objective)}</div><div class="st">sujeito a</div>
          ${f.constraints.map(c => `<div class="cl"><span class="rn">${esc(c.name)}</span>${esc(c.text)}</div>`).join('')}
          ${f.signs.map(x => `<div class="cl">${esc(x)}</div>`).join('')}
          ${f.integrality ? `<div class="cl">${esc(f.integrality)}</div>` : ''}
        </div>
      </div>
      <div class="side-card">
        <h3>Resultado</h3>
        <span class="badge-st ${statusClass(s.status)}">${esc(s.status_label)}</span>
        ${s.objective_value ? `<div class="mt-2 mono fw-bold fs-5">${zl} = ${fmt(s.objective_value)}</div>
          <div class="mono small mt-1">${s.solution.map(v => `${esc(v.name)} = ${fmt(v.exact)}`).join('<br>')}</div>` :
          `<p class="small mt-2 mb-0">${esc(s.message)}</p>`}
        <div class="small text-muted mt-2">${esc(r.primary_label)} · ${s.iterations} iteraç${s.iterations === 1 ? 'ão' : 'ões'}</div>
      </div>
      <div class="side-card side-actions">
        <a href="#/modelar" class="btn btn-sf-ghost">Editar modelo</a>
        <button type="button" class="btn btn-sf-ghost" data-side="save">Salvar modelo (JSON)</button>
        <button type="button" class="btn btn-sf-ghost" data-side="export">Exportar resultado</button>
        <button type="button" class="btn btn-sf-soft" data-side="new">Novo problema</button>
      </div>`;
  }

  // ------------------------------------------------------------ resumo
  function summaryHtml(r) {
    const s = r.summary, m = r.model;
    const zl = m.sense === 'max' ? 'Z máximo' : 'Z mínimo';
    let html = `<div class="hero-result st-${s.status}">
      <div class="lbl">${s.status === 'optimal' ? 'Solução ótima' : esc(s.status_label)}</div>`;
    if (s.status === 'optimal') {
      html += `<div class="zval">${fmt(s.objective_value)}<small>${zl}</small></div>
        <div class="var-chips">${s.solution.map(v => `<span class="var-chip"><b>${esc(v.name)}</b> = ${fmt(v.exact)}${SF.state.numMode === 'frac' && v.exact.includes('/') ? `<small>≈ ${esc(v.decimal)}</small>` : ''}</span>`).join('')}</div>`;
    } else {
      html += `<p class="mt-2 mb-0 fs-6">${esc(s.message)}</p>`;
    }
    html += '</div>';

    html += `<div class="info-grid">
      <div class="info-item"><span>Tipo</span><strong>${esc(m.sense_label)}</strong></div>
      <div class="info-item"><span>Função objetivo</span><strong class="mono small">${esc(m.formulation.objective)}</strong></div>
      <div class="info-item"><span>Variáveis</span><strong>${m.n_variables}</strong></div>
      <div class="info-item"><span>Restrições</span><strong>${m.n_constraints}</strong></div>
      <div class="info-item"><span>Método</span><strong>${esc(r.primary_label)}</strong></div>
      <div class="info-item"><span>Iterações</span><strong>${s.iterations}</strong></div>
      <div class="info-item"><span>Status</span><strong><span class="badge-st ${statusClass(s.status)}">${esc(s.status_label)}</span></strong></div>
    </div>`;

    const mult = s.multiple;
    if (mult && mult.has_multiple) {
      const alt = mult.alternatives[0];
      html += `<div class="sf-alert sf-alert-violet"><h3>Soluções ótimas múltiplas</h3>${esc(mult.explanation)}
        <div class="two-col mt-2">
          <div class="panel"><h4>Solução ótima original</h4><div class="mono">${s.solution.map(v => `${esc(v.name)} = ${fmt(v.exact)}`).join(', ')}</div><div class="mono">Z = ${fmt(s.objective_value)}</div></div>
          <div class="panel"><h4>Solução alternativa ${alt.type === 'ray' ? '(semirreta)' : `(entra ${esc(alt.variable)})`}</h4><div class="mono">${alt.solution.map(v => `${esc(v.name)} = ${fmt(v.exact)}`).join(', ')}</div><div class="mono">Z = ${fmt(alt.objective)}</div></div>
        </div><p class="small mb-0 mt-2">Ambas produzem o mesmo valor de Z. Detalhes e tabela alternativa na aba <b>Análise Matemática</b>.</p></div>`;
    } else if (mult && mult.zero_reduced && mult.zero_reduced.length) {
      html += `<div class="sf-alert sf-alert-info">${esc(mult.explanation)}</div>`;
    }
    if (s.degenerate) {
      html += `<div class="sf-alert sf-alert-warning"><h3>Degenerescência</h3>Ao menos uma tabela apresentou variável básica com valor zero.
        Iterações degeneradas não alteram Z; a regra de desempate (e a troca automática para Bland em caso de repetição de base) evita ciclagem.</div>`;
    }

    if (s.constraints && s.constraints.length) {
      html += `<h3 class="section-title">Análise das restrições no ponto ótimo <small>restrições ativas determinam o ótimo</small></h3>
        <div class="table-wrap"><table class="sf-table cards-sm"><thead><tr><th>Restrição</th><th>Expressão</th><th>Valor no ótimo</th><th>Limite</th><th>Folga / excesso</th><th>Situação</th></tr></thead><tbody>
        ${s.constraints.map(c => `<tr class="${c.active ? 'row-active' : ''}"><td data-label="Restrição" class="mono">${esc(c.name)}</td>
          <td data-label="Expressão" class="mono">${esc(c.expression)}</td><td data-label="Valor" class="num">${fmt(c.value)}</td>
          <td data-label="Limite" class="num">${SF.ui.OP[c.operator]} ${fmt(c.rhs)}</td>
          <td data-label="${esc(c.gap_type)}" class="num">${c.operator === '=' ? '—' : fmt(c.gap) + ' <small class="text-muted">' + esc(c.gap_type) + '</small>'}</td>
          <td data-label="Situação">${c.active ? '<span class="badge-st st-violet">Ativa</span>' : '<span class="badge-st st-info">Não ativa</span>'}</td></tr>`).join('')}
        </tbody></table></div>`;
    }
    if (r.integer) {
      html += `<h3 class="section-title">Contínua × arredondada × inteira ótima</h3>${SF.integer.comparisonTable(r, r.integer)}`;
    }
    const mt = Object.keys(r.tabular);
    if (mt.length > 1) {
      html += `<h3 class="section-title">Métodos tabulares executados</h3><div class="table-wrap"><table class="sf-table cards-sm"><thead><tr><th>Método</th><th>Status</th><th>Iterações</th><th>Z</th></tr></thead><tbody>
        ${mt.map(k => { const t = r.tabular[k]; return `<tr><td data-label="Método"><b>${esc(t.method_label)}</b></td><td data-label="Status"><span class="badge-st ${statusClass(t.status)}">${esc(t.status_label)}</span></td>
          <td data-label="Iterações" class="num">${t.iterations}</td><td data-label="Z" class="num">${t.objective_value ? fmt(t.objective_value) : '—'}</td></tr>`; }).join('')}</tbody></table></div>`;
    }
    if (r.model.n_variables !== 2) {
      html += `<div class="sf-alert sf-alert-info mt-3"><h3>Visualização gráfica</h3>${esc(r.graphical.message || '')}</div>`;
    }
    return html;
  }

  // ------------------------------------------------------------ simplex
  function renderSimplex(panel, r) {
    const keys = Object.keys(r.tabular);
    let sel = keys.includes(r.primary_method) ? r.primary_method : keys[0];
    panel.innerHTML = `
      ${keys.length > 1 ? `<div class="seg-mini mb-3" role="tablist" aria-label="Variante do Simplex">${keys.map(k => `<button type="button" data-variant="${k}" aria-pressed="${k === sel}">${esc(r.tabular[k].method_label)}</button>`).join('')}</div>` : ''}
      <div class="variant-msg"></div><div class="variant-player"></div>`;
    const draw = () => {
      const t = r.tabular[sel];
      panel.querySelector('.variant-msg').innerHTML = `<div class="sf-alert ${t.status === 'optimal' ? 'sf-alert-success' : 'sf-alert-warning'}">
        <b>${esc(t.method_label)}:</b> ${esc(t.message)} <span class="text-muted">(${t.iterations} iteraç${t.iterations === 1 ? 'ão' : 'ões'})</span></div>`;
      SF.simplex.createPlayer(panel.querySelector('.variant-player'), t);
    };
    panel.querySelectorAll('[data-variant]').forEach(b => b.addEventListener('click', () => {
      sel = b.dataset.variant;
      panel.querySelectorAll('[data-variant]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      draw();
    }));
    draw();
  }

  // ------------------------------------------------------------ algébrico
  function algebraicHtml(a) {
    if (!a) return '';
    let html = `<div class="sf-alert sf-alert-info"><h3>Método algébrico — soluções básicas</h3>
      Na forma padrão há <b>${a.m}</b> equações e <b>${a.N}</b> variáveis. Fixando ${a.N - a.m} variáveis não básicas em zero, resolve-se o sistema
      para as ${a.m} básicas. São C(${a.N}, ${a.m}) = <b>${a.total_combinations}</b> combinações. ${esc(a.message)}</div>`;
    html += `<div class="panel mb-3"><h4>Sistema na forma padrão</h4><div class="std-form">${a.equations.map(e => `<div>${esc(e)}</div>`).join('')}
      <div>${esc(a.variables.join(', '))} ≥ 0</div>${a.notes.length ? `<div class="notes">${a.notes.map(esc).join('<br>')}</div>` : ''}</div></div>`;
    if (a.rank_note) html += `<div class="sf-alert sf-alert-warning">${esc(a.rank_note)}</div>`;
    if (!a.solutions.length) return html;
    html += `<div class="d-flex flex-wrap gap-2 align-items-center mb-2">
      <span class="badge-st st-ok">Viáveis: ${a.feasible_count}</span><span class="badge-st st-bad">Inviáveis: ${a.infeasible_count}</span>
      <span class="badge-st st-warn">Singulares: ${a.singular_count}</span>
      <label class="sf-check ms-auto"><input type="checkbox" id="algOnlyFeasible"> Mostrar apenas viáveis</label></div>
      <div class="table-wrap"><table class="sf-table cards-sm" id="algTable"><thead><tr><th>#</th><th>Básicas</th><th>Não básicas (= 0)</th><th>Valores</th><th>Decisão</th><th>Z</th><th>Situação</th></tr></thead><tbody>
      ${a.solutions.map((s, i) => {
        const st = s.status === 'feasible' ? (s.optimal ? '<span class="badge-st st-ok">Ótima</span>' : '<span class="badge-st st-info">Viável</span>')
          : s.status === 'infeasible' ? '<span class="badge-st st-bad">Inviável (valor &lt; 0)</span>' : '<span class="badge-st st-warn">Base singular</span>';
        const vals = s.values ? Object.entries(s.values).map(([k, v]) => `${esc(k)}=${fmt(v)}`).join(', ') : '—';
        return `<tr class="${s.optimal ? 'row-opt' : ''}" data-status="${s.status}"><td data-label="#" class="mono">${i + 1}</td><td data-label="Básicas" class="mono">${esc(s.basic.join(', '))}</td>
          <td data-label="Não básicas" class="mono">${esc(s.nonbasic.join(', '))}</td><td data-label="Valores" class="mono">${vals}</td>
          <td data-label="Decisão" class="mono">${s.x ? '(' + s.x.map(fmt).join(', ') + ')' : '—'}</td>
          <td data-label="Z" class="num">${s.objective && s.status === 'feasible' ? fmt(s.objective) : '—'}</td><td data-label="Situação">${st}</td></tr>`;
      }).join('')}</tbody></table></div>`;
    return html;
  }

  // ------------------------------------------------------------ análise
  function analysisHtml(r) {
    const a = r.analysis;
    const prim = r.tabular[r.primary_method];
    let html = `<div class="sf-alert ${a.all_ok ? 'sf-alert-success' : 'sf-alert-danger'}"><h3>Consistência entre métodos</h3>${esc(a.message)}</div>
      <ul class="checklist mb-4">${a.checks.map(c => `<li><span class="ic ${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '✗'}</span><div class="ct"><strong>${esc(c.label)}</strong><small>${esc(c.detail)}</small></div></li>`).join('')}</ul>`;
    if (!prim.proof) {
      html += `<div class="sf-alert sf-alert-info">${esc(prim.message)}</div>`;
      return html;
    }
    const p = prim.proof;
    html += `<h3 class="section-title">Identificação algébrica da solução ótima</h3>
      <div class="two-col">
        <div class="panel"><h4>1. Variáveis básicas (coluna b da tabela final)</h4>
          <div class="mono">${p.basic.map(b => `${esc(b.name)} = ${fmt(b.value)}`).join('<br>')}</div>
          <h4 class="mt-3">Variáveis não básicas (= 0)</h4><div class="mono">${esc(p.nonbasic.join(', ')) || '—'}</div>
          <p class="small text-muted mt-2 mb-0">${esc(p.feasibility)}</p></div>
        <div class="panel"><h4>2. Condição de otimalidade: ${esc(p.condition)}</h4>
          <ul class="checklist">${p.reduced_checks.map(c => `<li><span class="ic ${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '✗'}</span><div class="ct"><strong class="mono">${esc(c.name)}: Cj − Zj = ${fmt(c.reduced)}</strong></div></li>`).join('') || '<li>Todas as variáveis são básicas.</li>'}</ul></div>
      </div>
      <div class="panel mt-3"><h4>3. Valor da função objetivo</h4><div class="mono">${esc(p.z_expansion)}</div></div>
      <div class="panel mt-3"><h4>4. Substituição nas restrições</h4><ul class="checklist">
        ${p.substitution.map(sx => `<li><span class="ic ${sx.ok ? 'ok' : 'bad'}">${sx.ok ? '✓' : '✗'}</span><div class="ct"><strong class="mono">${esc(sx.name)}: ${esc(sx.text)}</strong></div></li>`).join('')}</ul></div>`;
    const finalStep = prim.steps[prim.steps.length - 1];
    if (finalStep && finalStep.tableau) {
      html += `<h3 class="section-title">Tabela final do Simplex</h3>${SF.simplex.tableauHtml(finalStep.tableau, finalStep.decision)}`;
    }
    if (prim.dual_values) {
      html += `<h3 class="section-title">Preços-sombra e custos reduzidos</h3><div class="two-col">
        <div class="table-wrap"><table class="sf-table"><thead><tr><th>Restrição</th><th>Preço-sombra (yᵢ)</th></tr></thead><tbody>
          ${prim.dual_values.map(d => `<tr><td class="mono">${esc(d.constraint)}</td><td class="num">${d.value ? fmt(d.value) : '—'}</td></tr>`).join('')}</tbody></table></div>
        <div class="table-wrap"><table class="sf-table"><thead><tr><th>Variável</th><th>Cj − Zj</th><th>Base?</th></tr></thead><tbody>
          ${prim.reduced_costs.map(d => `<tr><td class="mono">${esc(d.variable)}</td><td class="num">${fmt(d.reduced)}</td><td>${d.basic ? 'básica' : 'não básica'}</td></tr>`).join('')}</tbody></table></div></div>`;
    }
    const mult = prim.multiple;
    if (mult) {
      html += `<h3 class="section-title">Verificação de soluções múltiplas</h3>
        <div class="sf-alert ${mult.has_multiple ? 'sf-alert-violet' : 'sf-alert-info'}">${esc(mult.explanation)}</div>`;
      if (mult.checks.length) html += `<ul class="checklist mb-3">${mult.checks.map(c => `<li><span class="ic ${c.result === 'vertex' || c.result === 'ray' ? 'ok' : 'bad'}">${c.result === 'vertex' || c.result === 'ray' ? '✓' : '–'}</span><div class="ct"><strong>${esc(c.text)}</strong></div></li>`).join('')}</ul>`;
      mult.alternatives.forEach(alt => {
        html += `<div class="panel mb-3"><h4>Solução alternativa — ${alt.type === 'ray' ? 'semirreta de soluções' : `entra ${esc(alt.variable)}, sai ${esc(alt.leaving)} (θ = ${fmt(alt.theta)})`}</h4>
          <div class="mono mb-2">${alt.solution.map(v => `${esc(v.name)} = ${fmt(v.exact)}`).join(', ')} &nbsp;→&nbsp; Z = ${fmt(alt.objective)} (mesmo valor ótimo)</div>
          ${alt.operations ? `<ol class="ops mb-2">${alt.operations.map(o => `<li>${esc(o.text)}</li>`).join('')}</ol>` : ''}
          ${alt.tableau ? SF.simplex.tableauHtml(alt.tableau, {}, { noLegend: true }) : ''}</div>`;
      });
    }
    return html;
  }

  // ------------------------------------------------------------ montagem
  function render() {
    const r = SF.state.results;
    const side = $('#sidePanel');
    const tabs = $('#resultTabs');
    const panels = $('#tabPanels');
    if (!r) {
      side.innerHTML = '';
      tabs.innerHTML = '';
      panels.innerHTML = `<div class="empty-state sf-card"><h3>Nenhum resultado ainda</h3><p>Monte um modelo e clique em <b>Resolver problema</b>.</p>
        <a href="#/modelar" class="btn btn-sf-primary">Ir para a modelagem</a></div>`;
      return;
    }
    side.innerHTML = sideHtml(r);
    side.onclick = e => {
      const b = e.target.closest('[data-side]');
      if (!b) return;
      if (b.dataset.side === 'export') exportResult();
      if (b.dataset.side === 'save') SF.ui.download(`${SF.ui.slug(r.model.name)}.json`, { format: 'simpliflix-model', version: 1, model: r.model_json });
      if (b.dataset.side === 'new') { SF.model.load(SF.model.blankModel()); location.hash = '#/modelar'; }
    };
    if (window.innerWidth < 992) {
      const body = $('#sideBody');
      body.classList.remove('show');
      $('.side-toggle').setAttribute('aria-expanded', 'false');
    }
    const avail = availableTabs(r);
    if (!avail.some(t => t.key === activeTab)) activeTab = 'summary';
    tabs.innerHTML = avail.map(t => `<button type="button" role="tab" id="tab-${t.key}" aria-controls="panel-${t.key}" aria-selected="${t.key === activeTab}" tabindex="${t.key === activeTab ? 0 : -1}" data-tab="${t.key}">${esc(t.label)}</button>`).join('');
    panels.innerHTML = avail.map(t => `<div class="tab-panel" role="tabpanel" id="panel-${t.key}" aria-labelledby="tab-${t.key}" tabindex="0" ${t.key === activeTab ? '' : 'hidden'}></div>`).join('');
    drawn.clear();
    showTab(activeTab);
  }

  const drawn = new Set();
  function drawPanel(key) {
    const r = SF.state.results;
    const p = $(`#panel-${key}`);
    if (!p) return;
    if (key === 'summary') p.innerHTML = summaryHtml(r);
    else if (key === 'graph') SF.graphics.render(p, r.graphical);
    else if (key === 'simplex') renderSimplex(p, r);
    else if (key === 'algebraic') {
      p.innerHTML = algebraicHtml(r.algebraic);
      const cb = p.querySelector('#algOnlyFeasible');
      if (cb) cb.addEventListener('change', () => p.querySelectorAll('#algTable tbody tr').forEach(tr => { tr.hidden = cb.checked && tr.dataset.status !== 'feasible'; }));
    }
    else if (key === 'integer') SF.integer.render(p, r.integer, r);
    else if (key === 'dual') SF.dual.render(p, r.dual, r);
    else if (key === 'analysis') p.innerHTML = analysisHtml(r);
    drawn.add(key);
  }

  function showTab(key) {
    activeTab = key;
    document.querySelectorAll('#resultTabs [data-tab]').forEach(b => {
      const on = b.dataset.tab === key;
      b.setAttribute('aria-selected', String(on));
      b.tabIndex = on ? 0 : -1;
    });
    document.querySelectorAll('#tabPanels .tab-panel').forEach(p => { p.hidden = p.id !== `panel-${key}`; });
    if (!drawn.has(key)) drawPanel(key);
    if (key === 'graph' && window.Plotly) {
      const pl = document.querySelector('#panel-graph .js-plotly-plot');
      if (pl) Plotly.Plots.resize(pl);
    }
  }

  function exportResult() {
    const r = SF.state.results;
    SF.ui.download(`${SF.ui.slug(r.model.name)}-resultado.json`, { format: 'simpliflix-result', version: 1, generated_at: new Date().toISOString(), data: r });
  }

  function bind() {
    $('#resultTabs').addEventListener('click', e => {
      const b = e.target.closest('[data-tab]');
      if (b) showTab(b.dataset.tab);
    });
    $('#resultTabs').addEventListener('keydown', e => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
      const btns = Array.from(document.querySelectorAll('#resultTabs [data-tab]'));
      let i = btns.findIndex(b => b.dataset.tab === activeTab);
      if (e.key === 'ArrowRight') i = (i + 1) % btns.length;
      if (e.key === 'ArrowLeft') i = (i - 1 + btns.length) % btns.length;
      if (e.key === 'Home') i = 0;
      if (e.key === 'End') i = btns.length - 1;
      e.preventDefault();
      showTab(btns[i].dataset.tab);
      btns[i].focus();
    });
    $('#btnExportResult').addEventListener('click', () => { if (SF.state.results) exportResult(); });
    document.addEventListener('sf:nummode', () => {
      // redesenha as abas estáticas no novo formato numérico (players se atualizam sozinhos)
      if (!SF.state.results || $('#view-results').hidden) return;
      ['summary', 'analysis', 'algebraic'].forEach(k => { if (drawn.has(k)) drawPanel(k); });
      $('#sidePanel').innerHTML = sideHtml(SF.state.results);
    });
  }

  function restore() {
    if (SF.state.results) return;
    try { const s = sessionStorage.getItem('sf-results'); if (s) SF.state.results = JSON.parse(s); } catch (e) { /* */ }
  }

  SF.results = { render, bind, restore, showTab };
})(window.SF);
