/* =====================================================================
   SimpliFlix — "player" das iterações do Simplex
   Cada tabela é um episódio: controles de primeira/anterior/próxima/última,
   reprodução automática, destaque de entrada, saída e pivô.
   ===================================================================== */
(function (SF) {
  'use strict';
  const { esc, fmt, valueOf, h } = SF.ui;

  const PHASE = { 0: '', 1: 'Fase 1', 2: 'Fase 2' };
  const FINAL_TYPES = ['optimal', 'unbounded', 'infeasible', 'iteration_limit', 'not_applicable'];

  /** Títulos de cada passo: "Tabela inicial", "Iteração k", "Fase 2 · tabela inicial"… */
  function labels(steps) {
    let pivots = 0;
    return steps.map((s, i) => {
      const t = s.decision ? s.decision.type : '';
      let title, short;
      if (i === 0) { title = 'Tabela inicial'; short = 'T0'; }
      else if (s.intro && s.phase === 2) { title = 'Fase 2 · tabela inicial'; short = 'F2·T0'; }
      else { title = `Iteração ${pivots}`; short = `Ep ${pivots}`; }
      if (FINAL_TYPES.includes(t)) { title += ' (final)'; }
      if (t === 'pivot' || t === 'dual_pivot' || t === 'drive_out') pivots += 1;
      return { title, short, final: FINAL_TYPES.includes(t), bad: ['unbounded', 'infeasible', 'iteration_limit', 'not_applicable'].includes(t) };
    });
  }

  function improving(v, sense) {
    const x = valueOf(v);
    return sense === 'max' ? x > 0 : x < 0;
  }

  /** HTML de uma tabela Simplex com destaques da decisão tomada sobre ela. */
  function tableauHtml(t, dec, opts = {}) {
    dec = dec || {};
    const hasEnter = dec.entering_col !== undefined && dec.entering_col !== null;
    const enterCol = hasEnter ? dec.entering_col : -1;
    const leaveRow = dec.leaving_row !== undefined ? dec.leaving_row : -1;
    const showRatios = Array.isArray(dec.ratios) && dec.ratios.length > 0;
    const thetaMin = dec.theta;
    const cls = j => (j === enterCol ? ' col-enter' : '');
    let html = '<div class="tableau-wrap"><table class="tableau"><thead><tr>';
    html += '<th class="rowhead" scope="col">Base</th><th scope="col" title="Custo das variáveis básicas">CB</th>';
    t.columns.forEach((c, j) => { html += `<th scope="col" class="kind-${t.kinds[j]}${cls(j)}" title="${esc(kindLabel(t.kinds[j]))}">${esc(c)}</th>`; });
    html += '<th scope="col" class="rhs" title="Lado direito (valores das variáveis básicas)">b</th>';
    if (showRatios) html += '<th scope="col" class="theta" title="Razão b ÷ coeficiente da coluna que entra">θ = b/a</th>';
    html += '</tr></thead><tbody>';
    // linha Cj
    html += '<tr class="cj-row"><th class="rowhead" scope="row" colspan="2" title="Coeficientes da função objetivo">Cj</th>';
    t.cj.forEach((v, j) => { html += `<td class="${cls(j)}">${fmt(v)}</td>`; });
    html += '<td class="rhs"></td>' + (showRatios ? '<td class="theta"></td>' : '') + '</tr>';
    // linhas das restrições
    t.rows.forEach((row, i) => {
      const leave = i === leaveRow;
      html += `<tr class="${leave ? 'row-leave' : ''}"><td class="basis">${esc(t.basis[i])}</td><td class="cb">${fmt(t.cb[i])}</td>`;
      row.forEach((v, j) => {
        const piv = leave && j === enterCol;
        html += `<td class="${piv ? 'pivot' : ''}${cls(j)}"${piv ? ' title="Elemento pivô"' : ''}>${fmt(v)}</td>`;
      });
      const neg = valueOf(t.rhs[i]) < 0;
      html += `<td class="rhs${neg ? ' neg-rhs' : ''}">${fmt(t.rhs[i])}</td>`;
      if (showRatios) {
        const r = dec.ratios.find(x => x.row === i);
        const isMin = r && r.valid && i === leaveRow;
        html += `<td class="theta${isMin ? ' min' : ''}">${r && r.valid ? fmt(r.ratio) + (isMin ? ' ◀' : '') : '—'}</td>`;
      }
      html += '</tr>';
    });
    // Zj
    html += '<tr class="zj-row"><th class="rowhead" scope="row" colspan="2" title="Zj = Σ CB·aij">Zj</th>';
    t.zj.forEach((v, j) => { html += `<td class="${cls(j)}">${fmt(v)}</td>`; });
    html += `<td class="rhs z-cell" title="Valor atual da função objetivo">Z = ${fmt(t.z)}</td>${showRatios ? '<td class="theta"></td>' : ''}</tr>`;
    // Cj − Zj
    html += '<tr class="red-row"><th class="rowhead" scope="row" colspan="2" title="Custo reduzido">Cj − Zj</th>';
    t.reduced.forEach((v, j) => {
      const basic = t.basis_cols.includes(j);
      const imp = !basic && improving(v, t.sense);
      html += `<td class="${imp ? 'improve' : ''}${cls(j)}">${fmt(v)}</td>`;
    });
    html += `<td class="rhs"></td>${showRatios ? '<td class="theta"></td>' : ''}</tr>`;
    // razões do Simplex Dual (por coluna)
    if (Array.isArray(dec.col_ratios) && dec.col_ratios.length) {
      html += '<tr class="cj-row"><th class="rowhead" scope="row" colspan="2" title="|Cj − Zj| ÷ |a_rj| para a_rj < 0">Razão dual</th>';
      t.columns.forEach((c, j) => {
        const r = dec.col_ratios.find(x => x.col === j);
        html += `<td class="${cls(j)}">${r && r.valid ? fmt(r.ratio) : ''}</td>`;
      });
      html += `<td class="rhs"></td>${showRatios ? '<td class="theta"></td>' : ''}</tr>`;
    }
    html += '</tbody></table></div>';
    if (!opts.noLegend) {
      html += `<div class="legend">
        <span><i style="background:var(--t-enter)"></i>coluna que entra</span>
        <span><i style="background:var(--t-leave)"></i>linha que sai</span>
        <span><i style="background:var(--t-pivot)"></i>elemento pivô</span>
        <span style="color:var(--accent)">■ Cj − Zj que melhora Z</span>
        <span style="color:var(--info)">■ folga/excesso</span><span style="color:var(--warning)">■ artificial</span></div>`;
    }
    return html;
  }

  function kindLabel(k) {
    return { decision: 'variável de decisão', slack: 'variável de folga', surplus: 'variável de excesso', artificial: 'variável artificial' }[k] || k;
  }

  function decisionHtml(step) {
    const d = step.decision || {};
    let left = '';
    if (step.intro) left += `<div class="intro-note">${esc(step.intro)}</div>`;
    if (d.type === 'pivot' || d.type === 'dual_pivot' || d.type === 'drive_out') {
      left += `<div class="chips">
        <span class="chip in">Entra: ${esc(d.entering)}</span>
        <span class="chip out">Sai: ${esc(d.leaving)}</span>
        <span class="chip pv">Pivô: ${fmt(d.pivot)}</span>
        ${d.theta !== undefined ? `<span class="chip">θ = ${fmt(d.theta)}</span>` : ''}
        ${d.z_after !== undefined ? `<span class="chip">Z: ${fmt(d.z_before)} → ${fmt(d.z_after)}</span>` : ''}
        ${d.rule === 'bland' ? '<span class="chip">Regra de Bland</span>' : ''}</div>`;
      left += `<p class="explain">${esc(d.explanation)}</p>`;
      if (d.degenerate) left += '<div class="verdict info mt-2">⚠ Iteração degenerada: θ = 0, a solução não muda (possível ciclagem é tratada pela regra de Bland).</div>';
    } else if (d.type) {
      const cls = d.type === 'optimal' ? 'ok' : d.type === 'remove_row' ? 'info' : 'bad';
      const title = { optimal: 'Critério de otimalidade satisfeito', unbounded: 'Problema ilimitado', infeasible: 'Problema inviável',
        iteration_limit: 'Limite de iterações', not_applicable: 'Método não aplicável', remove_row: 'Restrição redundante' }[d.type] || d.type;
      left += `<div class="verdict ${cls}"><strong>${esc(title)}.</strong> ${esc(d.explanation)}</div>`;
    }
    if (step.degenerate && d.type !== 'pivot') left += '<p class="text-muted small mt-2 mb-0">Solução básica degenerada: há variável básica com valor 0.</p>';
    let right = '';
    if (d.operations && d.operations.length) {
      right += `<h4>Operações elementares (pivoteamento)</h4><ol class="ops">${d.operations.map(o => `<li>${esc(o.text)}</li>`).join('')}</ol>
        <p class="text-muted small mt-2 mb-0">A linha pivô é dividida pelo pivô; as demais linhas recebem múltiplos dela para zerar a coluna de ${esc(d.entering)}.</p>`;
    } else if (d.type === 'optimal') {
      right += `<h4>Leitura da solução</h4><p class="explain">As variáveis básicas assumem os valores da coluna <b>b</b>; as não básicas valem 0.
        O valor ótimo de Z aparece na linha Zj.</p>`;
    } else {
      right += `<h4>Componentes da tabela</h4>${componentsHelp()}`;
    }
    return `<div class="decision"><div class="decision-box"><h4>Decisão desta etapa</h4>${left}</div><div class="decision-box">${right}</div></div>`;
  }

  function componentsHelp() {
    return `<ul class="explain small ps-3 mb-0">
      <li><b>Cj</b>: coeficiente de cada variável na função objetivo.</li>
      <li><b>Base / CB</b>: variáveis básicas e seus custos.</li>
      <li><b>b</b>: valores atuais das variáveis básicas.</li>
      <li><b>Zj</b> = Σ CB·aij: quanto Z perde/ganha ao introduzir 1 unidade de j.</li>
      <li><b>Cj − Zj</b>: custo reduzido; indica se a variável melhora Z.</li>
      <li><b>θ</b>: razão b ÷ a usada no teste da razão mínima.</li></ul>`;
  }

  function stdFormHtml(sf) {
    if (!sf) return '';
    const blocks = [];
    const one = (title, f) => f ? `<div class="panel"><h4>${title}</h4><div class="std-form"><div><b>${esc(f.objective)}</b></div>
      ${f.constraints.map(c => `<div>${esc(c)}</div>`).join('')}<div>${esc(f.nonnegativity)}</div>
      ${f.notes && f.notes.length ? `<div class="notes">${f.notes.map(esc).join('<br>')}</div>` : ''}</div></div>` : '';
    if (sf.phase1) blocks.push(one('Fase 1 — minimizar a soma das artificiais', sf.phase1));
    if (sf.phase2) blocks.push(one(sf.phase1 ? 'Fase 2 — função objetivo original' : 'Forma padrão', sf.phase2));
    if (sf.bigm) blocks.push(one('Forma padrão com penalidade M', sf.bigm));
    if (sf.dual_simplex) blocks.push(one('Forma ≤ com folgas (Simplex Dual)', sf.dual_simplex));
    if (!blocks.length) return '';
    return `<details class="sf-card p-3 mb-3"><summary class="fw-bold">Forma padrão utilizada</summary>
      <div class="${blocks.length > 1 ? 'two-col' : ''} mt-3">${blocks.join('')}</div></details>`;
  }

  /** Cria o player em `container` para um resultado tabular. */
  function createPlayer(container, result, opts = {}) {
    const steps = result.steps || [];
    const labs = labels(steps);
    let idx = opts.start === 'last' ? steps.length - 1 : 0;
    let timer = null;
    let allMode = false;
    const seen = new Set([idx]);
    const uid = 'p' + Math.random().toString(36).slice(2, 8);

    container.innerHTML = `
      ${opts.hideStd ? '' : stdFormHtml(result.standard_form)}
      <div class="episodes" role="tablist" aria-label="Tabelas do Simplex" id="${uid}-eps"></div>
      <div class="player" tabindex="0" aria-label="Controles das iterações (use as setas ← →)">
        <button type="button" class="pbtn" data-act="first" aria-label="Primeira tabela" title="Primeira">⏮</button>
        <button type="button" class="pbtn" data-act="prev" aria-label="Iteração anterior" title="Anterior">◀</button>
        <button type="button" class="pbtn play" data-act="play" aria-label="Reproduzir automaticamente" title="Reprodução automática">▶</button>
        <button type="button" class="pbtn" data-act="next" aria-label="Próxima iteração" title="Próxima">▶▏</button>
        <button type="button" class="pbtn" data-act="last" aria-label="Última tabela" title="Última">⏭</button>
        <div class="pprog"><div class="bar" data-act="seek" title="Clique para saltar"><span></span></div><small aria-live="polite"></small></div>
        <div class="popts">
          <select class="form-select form-select-sm sf-input" data-act="speed" aria-label="Velocidade" style="width:auto;min-height:32px">
            <option value="2500">Lento</option><option value="1600" selected>Normal</option><option value="900">Rápido</option></select>
          <div class="seg-mini" role="group" aria-label="Formato numérico">
            <button type="button" data-num="frac" aria-pressed="${SF.state.numMode === 'frac'}">Fração</button>
            <button type="button" data-num="dec" aria-pressed="${SF.state.numMode === 'dec'}">Decimal</button></div>
          <div class="seg-mini" role="group" aria-label="Modo de exibição">
            <button type="button" data-view="one" aria-pressed="true">Episódio</button>
            <button type="button" data-view="all" aria-pressed="false">Todas</button></div>
        </div>
      </div>
      <div class="step-view" aria-live="polite"></div>`;

    const eps = container.querySelector('.episodes');
    const view = container.querySelector('.step-view');
    const bar = container.querySelector('.pprog .bar span');
    const prog = container.querySelector('.pprog small');
    const playBtn = container.querySelector('[data-act="play"]');

    function renderEpisodes() {
      eps.innerHTML = steps.map((s, i) => {
        const l = labs[i];
        const z = s.tableau ? fmt(s.tableau.z) : '';
        const ph = PHASE[s.phase] ? `${PHASE[s.phase]}` : (i === 0 ? 'Início' : 'Episódio');
        return `<button type="button" role="tab" class="ep${i === idx ? ' active' : ''}${seen.has(i) ? ' seen' : ''}${l.final ? (l.bad ? ' bad' : ' final') : ''}"
          aria-selected="${i === idx}" data-i="${i}"><small>${esc(ph)}</small><strong>${esc(l.short)}</strong><span class="ep-z">Z = ${z}</span></button>`;
      }).join('');
      const a = eps.querySelector('.ep.active');
      if (a && a.scrollIntoView) {
        const r = a.getBoundingClientRect(), pr = eps.getBoundingClientRect();
        if (r.left < pr.left || r.right > pr.right) eps.scrollLeft += (r.left - pr.left) - pr.width / 2 + r.width / 2;
      }
    }

    function stepHtml(i) {
      const s = steps[i];
      const l = labs[i];
      const ph = PHASE[s.phase] ? `<span class="phase-pill">${PHASE[s.phase]}</span>` : '';
      return `<div class="step-head"><h3>${ph}${esc(l.title)}</h3><span class="zbig">Z = ${s.tableau ? fmt(s.tableau.z) : '—'}</span></div>
        ${s.tableau ? tableauHtml(s.tableau, s.decision, { noLegend: allMode && i > 0 }) : ''}
        ${decisionHtml(s)}`;
    }

    function render() {
      if (!steps.length) { view.innerHTML = '<div class="empty-state">Nenhuma tabela registrada.</div>'; return; }
      renderEpisodes();
      if (allMode) {
        view.innerHTML = steps.map((_, i) => `<div class="sf-card">${stepHtml(i)}</div>`).join('');
      } else {
        view.innerHTML = stepHtml(idx);
      }
      bar.style.width = `${steps.length > 1 ? (idx / (steps.length - 1)) * 100 : 100}%`;
      prog.textContent = `${labs[idx].title} · tabela ${idx + 1} de ${steps.length}`;
      container.querySelector('[data-act="first"]').disabled = idx === 0;
      container.querySelector('[data-act="prev"]').disabled = idx === 0;
      container.querySelector('[data-act="next"]').disabled = idx === steps.length - 1;
      container.querySelector('[data-act="last"]').disabled = idx === steps.length - 1;
    }

    function go(i) {
      idx = Math.max(0, Math.min(steps.length - 1, i));
      seen.add(idx);
      render();
    }
    function stop() {
      clearInterval(timer); timer = null;
      playBtn.textContent = '▶'; playBtn.setAttribute('aria-label', 'Reproduzir automaticamente');
    }
    function play() {
      if (timer) { stop(); return; }
      if (idx >= steps.length - 1) go(0);
      const speed = Number(container.querySelector('[data-act="speed"]').value);
      playBtn.textContent = '❚❚'; playBtn.setAttribute('aria-label', 'Pausar');
      timer = setInterval(() => {
        if (idx >= steps.length - 1) { stop(); return; }
        go(idx + 1);
      }, speed);
    }

    container.addEventListener('click', e => {
      const b = e.target.closest('[data-act],[data-i],[data-num],[data-view]');
      if (!b || !container.contains(b)) return;
      if (b.dataset.i !== undefined && b.classList.contains('ep')) { stop(); go(Number(b.dataset.i)); return; }
      if (b.dataset.num) { SF.state.numMode = b.dataset.num; document.dispatchEvent(new CustomEvent('sf:nummode')); return; }
      if (b.dataset.view) {
        allMode = b.dataset.view === 'all';
        container.querySelectorAll('[data-view]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
        stop(); render(); return;
      }
      const act = b.dataset.act;
      if (act === 'first') { stop(); go(0); }
      else if (act === 'prev') { stop(); go(idx - 1); }
      else if (act === 'next') { stop(); go(idx + 1); }
      else if (act === 'last') { stop(); go(steps.length - 1); }
      else if (act === 'play') play();
      else if (act === 'seek') {
        const r = b.getBoundingClientRect();
        stop(); go(Math.round(((e.clientX - r.left) / r.width) * (steps.length - 1)));
      }
    });
    container.querySelector('.player').addEventListener('keydown', e => {
      if (e.key === 'ArrowRight') { e.preventDefault(); stop(); go(idx + 1); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); stop(); go(idx - 1); }
      if (e.key === 'Home') { e.preventDefault(); stop(); go(0); }
      if (e.key === 'End') { e.preventDefault(); stop(); go(steps.length - 1); }
      if (e.key === ' ') { e.preventDefault(); play(); }
    });
    const onNum = () => {
      if (!document.body.contains(container)) { document.removeEventListener('sf:nummode', onNum); return; }
      container.querySelectorAll('[data-num]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.num === SF.state.numMode)));
      render();
    };
    document.addEventListener('sf:nummode', onNum);
    render();
    return { go, stop };
  }

  SF.simplex = { createPlayer, tableauHtml, labels, stdFormHtml, componentsHelp };
})(window.SF);
