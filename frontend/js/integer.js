/* =====================================================================
   SimpliFlix — solução inteira (Branch and Bound) e arredondamento
   ===================================================================== */
(function (SF) {
  'use strict';
  const { esc, fmt } = SF.ui;

  const NODE_STATUS = {
    incumbent: ['st-ok', 'Ótima inteira'],
    superseded: ['st-info', 'Incumbente superada'],
    integer: ['st-info', 'Inteira (não melhora)'],
    infeasible: ['st-bad', 'Inviável'],
    pruned_bound: ['st-warn', 'Podado por limitante'],
    branched: ['st-violet', 'Ramificado'],
    pending: ['st-warn', 'Não explorado'],
    unbounded: ['st-bad', 'Ilimitado'],
    error: ['st-bad', 'Erro'],
    open: ['st-info', 'Aberto'],
  };
  const BB_STATUS = {
    optimal: ['st-ok', 'Solução inteira comprovadamente ótima'],
    feasible: ['st-warn', 'Melhor solução inteira viável encontrada (otimalidade não comprovada)'],
    infeasible: ['st-bad', 'Sem solução inteira viável'],
    unbounded: ['st-bad', 'Relaxação ilimitada'],
    limit_no_solution: ['st-warn', 'Limite de nós sem solução inteira'],
    error: ['st-bad', 'Erro na resolução'],
  };

  const valsText = list => list.map(v => `${esc(v.name)} = ${fmt(v.exact)}`).join(', ');

  function render(container, data, results) {
    if (!data) { container.innerHTML = '<div class="empty-state">Cálculo da solução inteira desativado nas opções avançadas.</div>'; return; }
    const bb = data.branch_and_bound;
    const r = data.rounding;
    const st = BB_STATUS[bb.status] || ['st-info', bb.status];
    const sense = results.model.sense;
    const zlbl = sense === 'max' ? 'Z máximo' : 'Z mínimo';

    let html = '';
    if (data.note) html += `<div class="sf-alert sf-alert-info">${esc(data.note)}</div>`;
    html += `<div class="hero-result ${bb.status === 'optimal' ? '' : 'st-unbounded'}">
      <div class="lbl">${esc(bb.status === 'optimal' ? 'Solução inteira ótima' : 'Branch and Bound')}</div>
      ${bb.objective_value ? `<div class="zval">${fmt(bb.objective_value)}<small>${zlbl} inteiro</small></div>
        <div class="var-chips">${bb.solution.map(v => `<span class="var-chip"><b>${esc(v.name)}</b> = ${fmt(v.exact)}${v.integer ? '' : '<small>contínua</small>'}</span>`).join('')}</div>` :
        `<div class="zval" style="font-size:1.4rem">${esc(st[1])}</div>`}
    </div>
    <div class="info-grid">
      <div class="info-item"><span>Status</span><strong><span class="badge-st ${st[0]}">${esc(st[1])}</span></strong></div>
      <div class="info-item"><span>Nós analisados</span><strong>${bb.node_count}</strong></div>
      <div class="info-item"><span>Variáveis inteiras</span><strong>${esc(bb.integer_variables.join(', '))}</strong></div>
      <div class="info-item"><span>Limite de nós</span><strong>${bb.max_nodes}</strong></div>
    </div>
    <div class="sf-alert ${bb.proven_optimal ? 'sf-alert-success' : 'sf-alert-warning'}"><h3>Justificativa do encerramento</h3>${esc(bb.message)}</div>`;

    // comparação
    html += `<h3 class="section-title">Comparação das soluções</h3>${comparisonTable(results, data)}`;

    // arredondamento
    html += `<h3 class="section-title">Solução inteira por arredondamento <small>${r.available ? esc(r.rule) : ''}</small></h3>`;
    if (!r.available) html += `<div class="sf-alert sf-alert-info">${esc(r.message)}</div>`;
    else {
      html += `<div class="two-col mb-3">
        <div class="panel"><h4>Solução contínua (Simplex)</h4><div class="mono">${valsText(r.continuous)}</div><div class="mt-1">Z = <b class="mono">${fmt(r.continuous_objective)}</b></div></div>
        <div class="panel"><h4>Após arredondamento</h4><div class="mono">${valsText(r.rounded)}</div><div class="mt-1">Z = <b class="mono">${fmt(r.objective)}</b>
          <span class="badge-st ${r.feasible ? 'st-ok' : 'st-bad'} ms-2">${r.feasible ? 'Viável' : 'Inviável'}</span></div></div></div>
        <div class="sf-alert ${r.feasible ? 'sf-alert-info' : 'sf-alert-danger'}">${esc(r.message)}</div>
        ${checksTable(r.checks)}`;
      if (r.adjusted) {
        const a = r.adjusted;
        html += `<div class="sf-alert ${a.found ? 'sf-alert-warning' : 'sf-alert-danger'} mt-3"><h3>${a.found ? 'Arredondamento ajustado' : 'Busca de ajuste'}</h3>${esc(a.message)}
          ${a.found ? `<div class="mono mt-2">${valsText(a.solution)} &nbsp;→&nbsp; Z = ${fmt(a.objective)}</div>` : ''}</div>`;
      }
    }

    // árvore
    html += `<h3 class="section-title">Árvore do Branch and Bound <small>clique em um nó para ver detalhes</small></h3>
      <div class="bb-legend mb-2">${Object.entries(data.branch_and_bound.status_counts).map(([k, n]) => `<span class="badge-st ${(NODE_STATUS[k] || ['st-info'])[0]}">${esc((NODE_STATUS[k] || [k, k])[1])}: ${n}</span>`).join('')}</div>
      <div class="sf-card p-2"><div class="bb-tree">${treeHtml(bb.nodes)}</div></div>
      <div id="bbDetail"></div>`;

    if (bb.added_constraints.length) {
      html += `<h3 class="section-title">Restrições adicionais criadas na ramificação</h3>
        <div class="chips">${bb.added_constraints.map(c => `<span class="chip">${esc(c)}</span>`).join('')}</div>`;
    }

    const en = data.enumeration;
    if (en) {
      html += `<h3 class="section-title">Conferência por enumeração</h3>
        <div class="sf-alert ${en.performed ? (en.agrees ? 'sf-alert-success' : 'sf-alert-danger') : 'sf-alert-info'}">${esc(en.message)}
        ${en.performed ? `<div class="mt-1"><b>${esc(en.comparison)}</b></div>` : ''}</div>`;
    }

    html += `<h3 class="section-title">Todos os nós</h3><div class="table-wrap"><table class="sf-table cards-sm"><thead><tr>
      <th>Nó</th><th>Restrições do ramo</th><th>Relaxação</th><th>Z</th><th>Situação</th></tr></thead><tbody>
      ${bb.nodes.map(n => `<tr class="${n.id === bb.incumbent_node ? 'row-opt' : ''}"><td data-label="Nó" class="mono">N${n.id}</td>
        <td data-label="Ramo" class="mono">${n.constraints.length ? esc(n.constraints.join(', ')) : 'raiz'}</td>
        <td data-label="Solução" class="mono">${n.solution ? valsText(n.solution) : esc(n.lp_status === 'infeasible' ? 'inviável' : n.lp_status)}</td>
        <td data-label="Z" class="num">${n.objective ? fmt(n.objective) : '—'}</td>
        <td data-label="Situação"><span class="badge-st ${(NODE_STATUS[n.status] || ['st-info'])[0]}">${esc((NODE_STATUS[n.status] || [0, n.status])[1])}</span></td></tr>`).join('')}
      </tbody></table></div>`;

    container.innerHTML = html;
    container.querySelector('.bb-tree').addEventListener('click', e => {
      const b = e.target.closest('.bb-node');
      if (!b) return;
      container.querySelectorAll('.bb-node.sel').forEach(x => x.classList.remove('sel'));
      b.classList.add('sel');
      showNode(container.querySelector('#bbDetail'), bb.nodes[Number(b.dataset.id)], results);
    });
  }

  function treeHtml(nodes) {
    if (!nodes.length) return '';
    const MAX_RENDER = 160;
    const node = n => {
      const st = NODE_STATUS[n.status] || ['st-info', n.status];
      const kids = n.children.filter(c => c < MAX_RENDER).map(c => node(nodes[c])).join('');
      return `<li><button type="button" class="bb-node s-${n.status}" data-id="${n.id}" aria-label="Nó ${n.id}: ${esc(st[1])}">
        <span class="nid">N${n.id}</span> <span class="badge-st ${st[0]}" style="font-size:.62rem;padding:1px 6px">${esc(st[1])}</span>
        ${n.parent !== null ? `<span class="br">${esc(n.branch)}</span>` : '<span class="br">Raiz</span>'}
        <span class="nz">${n.objective ? 'Z = ' + fmt(n.objective) : (n.lp_status === 'infeasible' ? 'inviável' : '')}</span>
      </button>${kids ? `<ul>${kids}</ul>` : ''}</li>`;
    };
    const more = nodes.length > MAX_RENDER ? `<p class="text-muted small text-center">Exibindo os primeiros ${MAX_RENDER} de ${nodes.length} nós na árvore; todos estão listados na tabela abaixo.</p>` : '';
    return `<ul>${node(nodes[0])}</ul>${more}`;
  }

  function showNode(box, n, results) {
    const st = NODE_STATUS[n.status] || ['st-info', n.status];
    box.innerHTML = `<div class="sf-card mt-3">
      <div class="d-flex flex-wrap gap-2 align-items-center mb-2"><h3 class="h6 fw-bold mb-0">Nó N${n.id}</h3>
        <span class="badge-st ${st[0]}">${esc(st[1])}</span><span class="text-muted small">profundidade ${n.depth} · ${n.iterations} iteração(ões) do Simplex</span></div>
      <p class="mb-2"><b>Restrições acumuladas:</b> <span class="mono">${n.constraints.length ? esc(n.constraints.join('; ')) : 'nenhuma (relaxação original)'}</span></p>
      <p class="mb-2"><b>Relaxação linear:</b> <span class="mono">${n.solution ? valsText(n.solution) + ' &nbsp; Z = ' + fmt(n.objective) : esc(n.lp_status)}</span></p>
      <p class="explain mb-3">${esc(n.reason)}</p>
      <button type="button" class="btn btn-sf-soft btn-sm" data-node-iter>Ver iterações do Simplex deste nó</button></div>`;
    box.querySelector('[data-node-iter]').onclick = () => nodeIterations(n, results);
    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /** Re-resolve a relaxação do nó (modelo + restrições do ramo) para exibir todas as tabelas. */
  async function nodeIterations(n, results) {
    const payload = JSON.parse(JSON.stringify(results.model_json));
    const nv = payload.objective.coefficients.length;
    n.branches_raw.forEach(([j, op, val]) => {
      const coefs = Array(nv).fill(0); coefs[j] = 1;
      payload.constraints.push({ name: `${payload.variables[j].name} ${op === '<=' ? '≤' : '≥'} ${val}`, coefficients: coefs, operator: op, rhs: val });
    });
    payload.options = { methods: ['two_phase'] };
    const box = SF.ui.modal(`Nó N${n.id} — relaxação linear`, '<div class="text-muted">Resolvendo…</div>');
    try {
      const d = await SF.api.simplex(payload);
      box.body.innerHTML = `<p class="text-muted">Restrições adicionais do ramo: <span class="mono">${n.constraints.length ? esc(n.constraints.join('; ')) : 'nenhuma'}</span></p><div class="node-player"></div>`;
      SF.simplex.createPlayer(box.body.querySelector('.node-player'), d.result);
    } catch (e) {
      box.body.innerHTML = `<div class="sf-alert sf-alert-danger">${esc(e.message)}</div>`;
    }
  }

  function checksTable(checks) {
    return `<div class="table-wrap"><table class="sf-table cards-sm"><thead><tr><th>Restrição</th><th>Verificação</th><th>Valor</th><th>Limite</th><th>Resultado</th></tr></thead><tbody>
      ${checks.map(c => `<tr><td data-label="Restrição" class="mono">${esc(c.name)}</td><td data-label="Expressão" class="mono">${esc(c.expression)}</td>
        <td data-label="Valor" class="num">${fmt(c.value)}</td><td data-label="Limite" class="num">${SF.ui.OP[c.operator]} ${fmt(c.rhs)}</td>
        <td data-label="Resultado">${c.satisfied ? '<span class="badge-st st-ok">Satisfeita</span>' : '<span class="badge-st st-bad">Violada</span>'}</td></tr>`).join('')}
      </tbody></table></div>`;
  }

  function comparisonTable(results, data) {
    const s = results.summary;
    const r = data ? data.rounding : null;
    const bb = data ? data.branch_and_bound : null;
    const names = results.model.variables.map(v => v.name);
    const rows = [];
    if (s.solution) rows.push({ label: 'Ótima contínua (Simplex)', vals: s.solution, z: s.objective_value, st: '<span class="badge-st st-ok">Ótima (relaxação)</span>' });
    if (r && r.available) {
      rows.push({ label: 'Inteira por arredondamento', vals: r.rounded, z: r.objective,
        st: r.feasible ? '<span class="badge-st st-warn">Viável, sem garantia</span>' : '<span class="badge-st st-bad">Inviável</span>' });
      if (r.adjusted && r.adjusted.found) rows.push({ label: 'Arredondamento ajustado', vals: r.adjusted.solution, z: r.adjusted.objective, st: '<span class="badge-st st-warn">Heurística</span>' });
    }
    if (bb && bb.solution) rows.push({ label: bb.proven_optimal ? 'Inteira ótima (B&B)' : 'Melhor inteira encontrada', vals: bb.solution, z: bb.objective_value,
      st: bb.proven_optimal ? '<span class="badge-st st-ok">Comprovadamente ótima</span>' : '<span class="badge-st st-warn">Não comprovada</span>' });
    if (!rows.length) return '<div class="text-muted">Não há soluções para comparar.</div>';
    return `<div class="table-wrap"><table class="sf-table cards-sm"><thead><tr><th>Solução</th>${names.map(n => `<th>${esc(n)}</th>`).join('')}<th>Z</th><th>Situação</th></tr></thead><tbody>
      ${rows.map(row => `<tr><td data-label="Solução"><b>${esc(row.label)}</b></td>${row.vals.map((v, j) => `<td data-label="${esc(names[j])}" class="num">${fmt(v.exact)}</td>`).join('')}
        <td data-label="Z" class="num"><b>${fmt(row.z)}</b></td><td data-label="Situação">${row.st}</td></tr>`).join('')}</tbody></table></div>`;
  }

  SF.integer = { render, comparisonTable };
})(window.SF);
