/* =====================================================================
   SimpliFlix — problema dual (formulação, correspondência, resolução)
   ===================================================================== */
(function (SF) {
  'use strict';
  const { esc, fmt } = SF.ui;

  function formBlock(title, f) {
    return `<div class="panel"><h4>${esc(title)}</h4><div class="math-block">
      <div class="obj">${esc(f.objective.replace(/^MAX Z/, 'MAX ' + (title.includes('Dual') ? 'W' : 'Z')).replace(/^MIN Z/, 'MIN ' + (title.includes('Dual') ? 'W' : 'Z')))}</div>
      <div class="st">sujeito a</div>
      ${f.constraints.map(c => `<div class="cl"><span class="rn">${esc(c.name)}</span>${esc(c.text)}</div>`).join('')}
      ${f.signs.map(s => `<div class="cl">${esc(s)}</div>`).join('')}</div></div>`;
  }

  function matrix(rows, rowNames, colNames) {
    return `<div class="table-wrap"><table class="sf-table" style="width:auto"><thead><tr><th></th>${colNames.map(c => `<th class="mono">${esc(c)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((r, i) => `<tr><th class="mono">${esc(rowNames[i])}</th>${r.map(v => `<td class="num">${fmt(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  /** Formulação + regras de correspondência (usado também no modal "Converter em Dual"). */
  function formulationHtml(d) {
    const primalCons = d.primal.constraints.map(c => c.name);
    return `<div class="two-col">${formBlock('Problema primal', d.primal)}${formBlock('Problema Dual', d.dual)}</div>
      <h3 class="section-title mt-4">Correspondência primal ↔ dual</h3>
      <div class="two-col">
        <div class="panel"><h4>Restrição primal → variável dual</h4><ul class="checklist">
          ${d.correspondence_constraints.map(c => `<li><span class="ic ok">${esc(c.dual_var)}</span><div class="ct"><strong class="mono">${esc(c.primal)}</strong><small>${esc(c.rule)}</small></div></li>`).join('')}</ul></div>
        <div class="panel"><h4>Variável primal → restrição dual</h4><ul class="checklist">
          ${d.correspondence_variables.map(c => `<li><span class="ic ok">→</span><div class="ct"><strong class="mono">${esc(c.primal_var)}</strong><small class="mono">${esc(c.dual_con)}</small><br><small>${esc(c.rule)}</small></div></li>`).join('')}</ul></div>
      </div>
      <h3 class="section-title mt-4">Matriz de coeficientes <small>as linhas de A tornam-se colunas no dual (Aᵀ); b e c trocam de papel</small></h3>
      <div class="two-col">
        <div class="panel"><h4>A (primal)</h4>${matrix(d.matrix_A, primalCons, d.primal_vars)}
          <div class="small mt-2"><b>c</b> = (${d.c.map(fmt).join(', ')}) &nbsp; <b>b</b> = (${d.b.map(fmt).join(', ')})</div></div>
        <div class="panel"><h4>Aᵀ (dual)</h4>${matrix(d.matrix_At, d.dual.constraints.map(c => c.name), d.dual_vars)}
          <div class="small mt-2">Função objetivo dual: coeficientes <b>b</b>; lados direitos: <b>c</b>.</div></div>
      </div>`;
  }

  function render(container, d, results) {
    if (!d) { container.innerHTML = '<div class="empty-state">Resolução do dual desativada nas opções avançadas.</div>'; return; }
    const rel = d.relation;
    const dr = d.dual_result;
    let html = '';
    const okRel = rel.equal === true;
    html += `<div class="sf-alert ${okRel ? 'sf-alert-success' : (rel.primal_status === 'optimal' ? 'sf-alert-danger' : 'sf-alert-info')}">
      <h3>Relação primal × dual</h3>${esc(rel.text)}
      ${rel.primal_objective ? `<div class="mono mt-2">Z* (primal) = ${fmt(rel.primal_objective)} &nbsp;&nbsp; W* (dual) = ${fmt(rel.dual_objective)}</div>` : ''}</div>`;
    html += formulationHtml(d);

    if (rel.shadow_prices) {
      html += `<h3 class="section-title mt-4">Variáveis duais (preços-sombra) <small>lidas na tabela ótima do primal × obtidas resolvendo o dual</small></h3>
        <div class="table-wrap"><table class="sf-table cards-sm"><thead><tr><th>Restrição</th><th>Variável dual</th><th>Tabela final do primal (c_B·B⁻¹)</th><th>Solução do dual</th><th>Confere</th></tr></thead><tbody>
        ${rel.shadow_prices.map(r => {
          const same = r.from_primal_tableau && r.from_primal_tableau.exact === r.from_dual_solution.exact;
          return `<tr><td data-label="Restrição" class="mono">${esc(r.constraint)}</td><td data-label="Variável" class="mono">${esc(r.dual_var)}</td>
          <td data-label="Primal" class="num">${r.from_primal_tableau ? fmt(r.from_primal_tableau) : '—'}</td><td data-label="Dual" class="num">${fmt(r.from_dual_solution)}</td>
          <td data-label="Confere">${same ? '<span class="badge-st st-ok">✓</span>' : '<span class="badge-st st-warn">solução dual alternativa</span>'}</td></tr>`;
        }).join('')}</tbody></table></div>
        <p class="text-muted small mt-2">O preço-sombra indica quanto Z* varia por unidade adicional no lado direito da restrição (dentro da faixa de validade da base ótima).</p>`;
      html += `<h3 class="section-title">Folgas complementares</h3><ul class="checklist">
        ${rel.complementary_slackness.map(c => `<li><span class="ic ${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '✗'}</span><div class="ct"><strong class="mono">${esc(c.pair)}</strong><small class="mono">${esc(c.text)}</small></div></li>`).join('')}</ul>`;
    }

    html += `<h3 class="section-title mt-4">Resolução tabular do dual <small>${esc(dr.method_label)} · ${esc(dr.status_label)}</small></h3>`;
    if (dr.solution) {
      html += `<div class="var-chips mb-3">${dr.solution.map(v => `<span class="var-chip"><b>${esc(v.name)}</b> = ${fmt(v.exact)}</span>`).join('')}
        <span class="var-chip"><b>W*</b> = ${fmt(dr.objective_value)}</span></div>`;
    }
    html += `<div class="dual-player"></div>
      <div class="d-flex justify-content-end mt-3"><button type="button" class="btn btn-sf-ghost btn-sm" id="dualToEditor">Abrir o dual no editor</button></div>`;
    container.innerHTML = html;
    SF.simplex.createPlayer(container.querySelector('.dual-player'), dr);
    container.querySelector('#dualToEditor').onclick = () => {
      SF.state.saved = JSON.parse(JSON.stringify(SF.state.model));
      SF.model.load(SF.model.fromJson(d.dual_model), { snapshot: false });
      location.hash = '#/modelar';
      SF.ui.toast('Dual carregado no editor. Use “Restaurar modelo” para voltar ao primal.', 'success', 6000);
    };
  }

  SF.dual = { render, formulationHtml };
})(window.SF);
