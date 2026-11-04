/* =====================================================================
   SimpliFlix — método gráfico (Plotly.js)
   Região viável, retas das restrições, vértices, curvas de nível,
   gradiente, pontos inteiros e marcadores das soluções.
   Todos os dados geométricos vêm do back-end (cálculo exato).
   ===================================================================== */
(function (SF) {
  'use strict';
  const { esc, fmt, cssVar } = SF.ui;

  const LINE_COLORS = ['#4cc3ff', '#ff8a3d', '#2fd28f', '#c86bff', '#ffd23f', '#ff6fa8', '#66e0d0', '#a3a8ff', '#ff9f9f', '#9be15d'];

  function lineBox(c1, c2, k, box) {
    const [xlo, xhi, ylo, yhi] = box;
    const pts = [];
    if (Math.abs(c2) > 1e-15) [xlo, xhi].forEach(x => { const y = (k - c1 * x) / c2; if (y >= ylo - 1e-9 && y <= yhi + 1e-9) pts.push([x, y]); });
    if (Math.abs(c1) > 1e-15) [ylo, yhi].forEach(y => { const x = (k - c2 * y) / c1; if (x >= xlo - 1e-9 && x <= xhi + 1e-9) pts.push([x, y]); });
    if (pts.length < 2) return null;
    pts.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    return [pts[0], pts[pts.length - 1]];
  }
  const num = v => SF.ui.decStr(v, 3);

  function render(container, g) {
    if (!g || !g.available) {
      container.innerHTML = `<div class="sf-alert sf-alert-info"><h3>Método gráfico indisponível</h3>${esc(g ? g.message : '')}</div>`;
      return;
    }
    const [xn, yn] = g.variables;
    const id = 'plot-' + Math.random().toString(36).slice(2, 8);
    const zs = (g.region || []).map(p => g.objective.c[0] * p[0] + g.objective.c[1] * p[1]);
    const box = g.box;
    const corners = [[box[0], box[2]], [box[0], box[3]], [box[1], box[2]], [box[1], box[3]]].map(p => g.objective.c[0] * p[0] + g.objective.c[1] * p[1]);
    const smin = Math.min(...corners), smax = Math.max(...corners);
    const start = g.optimal ? g.optimal.z : (zs.length ? zs[0] : (smin + smax) / 2);
    const statusBadge = { optimal: ['st-ok', 'Ótimo encontrado'], unbounded: ['st-bad', 'Ilimitado'], infeasible: ['st-bad', 'Inviável'] }[g.status];

    container.innerHTML = `
      <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
        <span class="badge-st ${statusBadge[0]}">${statusBadge[1]}</span>
        ${g.region_unbounded ? '<span class="badge-st st-warn">Região ilimitada</span>' : (g.feasible ? '<span class="badge-st st-info">Região limitada</span>' : '')}
        ${g.optimal_set && g.optimal_set.type !== 'point' ? '<span class="badge-st st-violet">Soluções múltiplas</span>' : ''}
        <span class="text-muted small ms-auto">${esc(g.objective.text)}</span>
      </div>
      <p class="explain mb-3">${esc(g.message)}</p>
      <div class="graph-shell"><div id="${id}" class="plot-box" role="img" aria-label="Gráfico da região viável, restrições e curvas de nível"></div>
        <div class="graph-controls" role="group" aria-label="Camadas do gráfico">
          <label class="sf-check"><input type="checkbox" data-layer="region" checked> Região viável</label>
          <label class="sf-check"><input type="checkbox" data-layer="lines" checked> Restrições</label>
          <label class="sf-check"><input type="checkbox" data-layer="levels" checked> Curvas de nível</label>
          <label class="sf-check"><input type="checkbox" data-layer="vertices" checked> Vértices</label>
          <label class="sf-check"><input type="checkbox" data-layer="inter"> Interseções fora da região</label>
          <label class="sf-check"><input type="checkbox" data-layer="int" ${g.integer_points && g.integer_points.count ? 'checked' : ''}> Pontos inteiros</label>
          <label class="sf-check"><input type="checkbox" data-layer="sol" checked> Soluções</label>
        </div>
        <div class="level-slider">
          <label for="${id}-k" class="small fw-bold">Deslocar curva de nível</label>
          <input type="range" id="${id}-k" min="${smin}" max="${smax}" step="any" value="${start}">
          <output for="${id}-k" id="${id}-out"></output>
        </div>
        <p class="text-muted small mx-1 mb-1" id="${id}-hint"></p>
      </div>
      ${verticesTable(g, xn, yn)}`;

    const el = container.querySelector('#' + id);
    const groups = { region: [], lines: [], levels: [], vertices: [], inter: [], int: [], sol: [] };
    const traces = [];
    const push = (grp, t) => { groups[grp].push(traces.length); traces.push(t); };
    const text = cssVar('--text'), muted = cssVar('--muted'), accent = cssVar('--accent'), violet = cssVar('--accent-2');
    const success = cssVar('--success'), warning = cssVar('--warning'), danger = cssVar('--danger');

    // região viável
    if (g.region && g.region.length) {
      const xs = g.region.map(p => p[0]), ys = g.region.map(p => p[1]);
      if (g.region.length >= 3) {
        push('region', { x: [...xs, xs[0]], y: [...ys, ys[0]], type: 'scatter', mode: 'lines', fill: 'toself',
          fillcolor: hexA(violet, 0.22), line: { color: hexA(violet, 0.0), width: 0 }, name: 'Região viável' + (g.region_unbounded ? ' (recortada)' : ''),
          hoverinfo: 'skip' });
      } else {
        push('region', { x: xs, y: ys, type: 'scatter', mode: 'lines+markers', line: { color: violet, width: 6 }, name: 'Região viável', hoverinfo: 'skip' });
      }
    }
    // retas das restrições
    let ci = 0;
    g.lines.forEach(l => {
      if (l.kind === 'sign' || !l.segment) return;
      const color = LINE_COLORS[ci++ % LINE_COLORS.length];
      push('lines', { x: [l.segment[0][0], l.segment[1][0]], y: [l.segment[0][1], l.segment[1][1]], type: 'scatter', mode: 'lines',
        line: { color, width: 2.2 }, name: `${l.name}: ${l.label}`,
        hovertemplate: `<b>${esc(l.name)}</b><br>${esc(l.label)}<br>reta: ${esc(l.equation)}<br>(%{x:.3f}, %{y:.3f})<extra></extra>` });
    });
    // curvas de nível
    g.levels.forEach(lv => {
      push('levels', { x: [lv.segment[0][0], lv.segment[1][0]], y: [lv.segment[0][1], lv.segment[1][1]], type: 'scatter', mode: 'lines',
        line: { color: lv.optimal ? accent : warning, width: lv.optimal ? 3.2 : 1.4, dash: lv.optimal ? 'solid' : 'dash' },
        name: lv.optimal ? `Curva ótima Z* = ${lv.z_text}` : `Z = ${lv.z_text}`, legendgroup: lv.optimal ? 'opt' : 'levels',
        showlegend: lv.optimal || lv === g.levels[0], opacity: lv.optimal ? 1 : 0.75,
        hovertemplate: `${lv.optimal ? 'Curva de nível ótima' : 'Curva de nível'}<br>Z = ${esc(lv.z_text)}<extra></extra>` });
    });
    // vértices
    if (g.vertices.length) {
      push('vertices', { x: g.vertices.map(v => v.x), y: g.vertices.map(v => v.y), type: 'scatter', mode: 'markers', name: 'Vértices',
        marker: { size: 9, color: text, line: { color: cssVar('--surface'), width: 2 } },
        text: g.vertices.map(v => `(${v.x_text}, ${v.y_text})<br>Z = ${v.z_text}<br>ativas: ${v.lines.join(', ')}`),
        hovertemplate: '<b>Vértice</b> %{text}<extra></extra>' });
    }
    const outside = g.intersections.filter(p => !p.feasible);
    if (outside.length) {
      push('inter', { x: outside.map(p => p.x), y: outside.map(p => p.y), type: 'scatter', mode: 'markers', name: 'Interseções fora da região',
        marker: { size: 7, color: 'rgba(0,0,0,0)', line: { color: muted, width: 1.5 } }, visible: false,
        text: outside.map(p => `(${p.x_text}, ${p.y_text})<br>${p.lines.join(' ∩ ')}<br>viola alguma restrição`),
        hovertemplate: '%{text}<extra></extra>' });
    }
    // pontos inteiros
    if (g.integer_points && g.integer_points.points.length) {
      const P = g.integer_points.points;
      push('int', { x: P.map(p => p[0]), y: P.map(p => p[1]), type: 'scatter', mode: 'markers',
        name: `Pontos inteiros viáveis${g.integer_points.sampled ? ' (amostra)' : ''}`,
        marker: { size: 5, color: muted, opacity: 0.8 }, text: P.map(p => num(p[2])),
        hovertemplate: '(%{x}, %{y})<br>Z = %{text}<extra>inteiro viável</extra>' });
    }
    // conjunto ótimo
    if (g.optimal_set && g.optimal_set.type === 'segment') {
      const [a, b] = g.optimal_set.points;
      push('sol', { x: [a[0], b[0]], y: [a[1], b[1]], type: 'scatter', mode: 'lines', line: { color: success, width: 8 }, opacity: 0.8,
        name: 'Segmento de soluções ótimas', hovertemplate: 'Todos os pontos deste segmento são ótimos<extra></extra>' });
    } else if (g.optimal_set && g.optimal_set.type === 'ray') {
      const a = g.optimal_set.points[0], d = g.optimal_set.direction;
      const L = Math.hypot(box[1] - box[0], box[3] - box[2]) * 2;
      push('sol', { x: [a[0], a[0] + d[0] * L], y: [a[1], a[1] + d[1] * L], type: 'scatter', mode: 'lines', line: { color: success, width: 8 }, opacity: 0.8,
        name: 'Semirreta de soluções ótimas', hoverinfo: 'skip' });
    }
    // marcadores de soluções (contínua, arredondada, inteira)
    const MK = {
      continuous: { symbol: 'star', size: 20, color: warning },
      rounded: { symbol: 'diamond', size: 14 },
      adjusted: { symbol: 'triangle-up', size: 14, color: '#4cc3ff' },
      integer: { symbol: 'square', size: 13, color: success },
    };
    (g.markers || []).forEach(mk => {
      const st = MK[mk.type] || { symbol: 'circle', size: 12, color: accent };
      const color = mk.type === 'rounded' ? (mk.feasible ? '#ff8a3d' : danger) : st.color;
      push('sol', { x: [mk.x], y: [mk.y], type: 'scatter', mode: 'markers', name: mk.label,
        marker: { symbol: st.symbol, size: st.size, color, line: { color: '#fff', width: 1.5 } },
        hovertemplate: `<b>${esc(mk.label)}</b><br>${esc(mk.text)}<br>Z = ${esc(mk.z)}<extra></extra>` });
    });
    if (!(g.markers || []).some(m => m.type === 'continuous') && g.optimal) {
      const p = g.optimal.points[0];
      push('sol', { x: [p.x], y: [p.y], type: 'scatter', mode: 'markers', name: 'Ponto ótimo',
        marker: { symbol: 'star', size: 20, color: warning, line: { color: '#fff', width: 1.5 } },
        hovertemplate: `Ótimo (${p.x_text}, ${p.y_text})<br>Z = ${g.optimal.z_text}<extra></extra>` });
    }
    // linha do controle deslizante
    const sliderIdx = traces.length;
    traces.push({ x: [], y: [], type: 'scatter', mode: 'lines', line: { color: violet, width: 2.5, dash: 'dot' }, name: 'Curva de nível (controle)', hoverinfo: 'skip' });

    const grad = g.gradient;
    const layout = {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: cssVar('--font'), color: text, size: 12 },
      margin: { l: 52, r: 16, t: 16, b: 48 },
      xaxis: { title: { text: xn }, range: [box[0], box[1]], gridcolor: hexA(muted, 0.18), zerolinecolor: hexA(text, 0.55), zerolinewidth: 1.5 },
      yaxis: { title: { text: yn }, range: [box[2], box[3]], gridcolor: hexA(muted, 0.18), zerolinecolor: hexA(text, 0.55), zerolinewidth: 1.5 },
      legend: { orientation: 'h', y: -0.18, x: 0, bgcolor: 'rgba(0,0,0,0)', font: { size: 11 } },
      hovermode: 'closest', dragmode: 'pan',
      hoverlabel: { bgcolor: cssVar('--surface-2'), bordercolor: cssVar('--border-strong'), font: { color: text } },
      annotations: g.feasible ? [{
        x: grad.to[0], y: grad.to[1], ax: grad.from[0], ay: grad.from[1], xref: 'x', yref: 'y', axref: 'x', ayref: 'y',
        showarrow: true, arrowhead: 3, arrowsize: 1.3, arrowwidth: 2.4, arrowcolor: accent, text: '', hovertext: grad.text,
      }] : [],
    };
    if (window.innerWidth < 768) { layout.legend.y = -0.32; layout.margin = { l: 44, r: 8, t: 8, b: 40 }; }
    const config = { responsive: true, displaylogo: false, scrollZoom: true, locale: 'pt-BR',
      modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'],
      toImageButtonOptions: { filename: 'simpliflix-grafico', scale: 2 } };

    if (!window.Plotly) {
      el.innerHTML = '<div class="empty-state">Biblioteca Plotly não carregada.</div>';
      return;
    }
    Plotly.newPlot(el, traces, layout, config);

    // camadas
    container.querySelectorAll('[data-layer]').forEach(cb => {
      const apply = () => {
        const ids = groups[cb.dataset.layer];
        if (ids.length) Plotly.restyle(el, { visible: cb.checked ? true : false }, ids);
      };
      cb.addEventListener('change', apply);
      if (!cb.checked) apply();
    });

    // curva de nível móvel
    const slider = container.querySelector(`#${id}-k`);
    const out = container.querySelector(`#${id}-out`);
    const hint = container.querySelector(`#${id}-hint`);
    const zmin = zs.length ? Math.min(...zs) : null, zmax = zs.length ? Math.max(...zs) : null;
    const update = () => {
      const k = Number(slider.value);
      const seg = lineBox(g.objective.c[0], g.objective.c[1], k, box);
      Plotly.restyle(el, { x: [seg ? [seg[0][0], seg[1][0]] : []], y: [seg ? [seg[0][1], seg[1][1]] : []] }, [sliderIdx]);
      out.textContent = `Z = ${num(k)}`;
      let msg;
      if (zmin === null) msg = 'Região viável vazia: nenhuma curva de nível a toca.';
      else if (k < zmin - 1e-9 || k > zmax + 1e-9) msg = 'Esta curva de nível não toca a região viável (nenhum ponto viável tem este valor de Z na área exibida).';
      else msg = 'Esta curva de nível cruza a região viável: existem pontos viáveis com este valor de Z.';
      if (g.optimal && Math.abs(k - g.optimal.z) < Math.max(1e-9, (smax - smin) / 400)) msg = `Curva de nível ótima: Z* = ${g.optimal.z_text}. Deslocá-la no sentido de melhoria a faria sair da região.`;
      hint.textContent = msg + ` Sentido de melhoria: ${g.objective.sense === 'max' ? 'aumento' : 'diminuição'} de Z (seta).`;
    };
    slider.addEventListener('input', update);
    update();

    const onTheme = () => {
      if (!document.body.contains(el)) { document.removeEventListener('sf:theme', onTheme); return; }
      render(container, g);
    };
    document.addEventListener('sf:theme', onTheme, { once: true });
  }

  function verticesTable(g, xn, yn) {
    if (!g.vertices.length) return '';
    const rows = [...g.vertices].sort((a, b) => a.x - b.x || a.y - b.y).map(v => `
      <tr class="${v.optimal ? 'row-opt' : ''}"><td data-label="${esc(xn)}" class="num">${fmt(v.x_text)}</td><td data-label="${esc(yn)}" class="num">${fmt(v.y_text)}</td>
      <td data-label="Z" class="num">${fmt(v.z_text)}</td><td data-label="Retas que se cruzam">${esc(v.lines.join(', '))}</td>
      <td data-label="Situação">${v.optimal ? '<span class="badge-st st-ok">Ótimo</span>' : '<span class="text-muted">—</span>'}</td></tr>`).join('');
    return `<h3 class="section-title mt-4">Vértices da região viável <small>cálculo exato das interseções que satisfazem todas as restrições</small></h3>
      <div class="table-wrap"><table class="sf-table cards-sm"><thead><tr><th>${esc(xn)}</th><th>${esc(yn)}</th><th>Z</th><th>Retas que se cruzam</th><th>Situação</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  }

  function hexA(color, a) {
    color = (color || '').trim();
    if (color.startsWith('#')) {
      let c = color.slice(1);
      if (c.length === 3) c = c.split('').map(x => x + x).join('');
      const n = parseInt(c, 16);
      return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
    }
    return color;
  }

  SF.graphics = { render };
})(window.SF);
