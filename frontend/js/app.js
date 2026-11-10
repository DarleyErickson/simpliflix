/* =====================================================================
   SimpliFlix — inicialização e navegação (Início → Modelagem → Resultados)
   Roteamento por hash: #/  ·  #/modelar  ·  #/resultados
   ===================================================================== */
(function (SF) {
  'use strict';
  const { $, $$, esc } = SF.ui;

  const ROUTES = { '': 'home', '#/': 'home', '#/modelar': 'model', '#/resultados': 'results' };
  let lastView = null;

  function route() {
    const view = ROUTES[location.hash] || 'home';
    $$('.view').forEach(v => { v.hidden = v.dataset.view !== view; });
    $$('.mainnav a').forEach(a => a.classList.toggle('active', a.dataset.route === view));
    $$('.mainnav a').forEach(a => (a.dataset.route === view ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
    const titles = { home: 'SimpliFlix · Programação Linear', model: 'Modelagem · SimpliFlix', results: 'Resultados · SimpliFlix' };
    document.title = titles[view];
    if (view === 'home') renderHome();
    if (view === 'model') SF.model.render();
    if (view === 'results') SF.results.render();
    if (lastView !== view) {
      window.scrollTo({ top: 0, behavior: 'instant' });
      const h1 = document.querySelector(`#view-${view} h1`);
      if (h1 && lastView) { h1.setAttribute('tabindex', '-1'); h1.focus({ preventScroll: true }); }
    }
    lastView = view;
  }

  function tagClass(t) {
    if (t === 'MAX') return 't-max';
    if (t === 'MIN') return 't-min';
    if (/Inteira|B&B/.test(t)) return 't-int';
    if (/Inviável|Ilimitado/.test(t)) return 't-bad';
    if (/Múltiplas|Degenerado|Duas Fases/.test(t)) return 't-warn';
    return '';
  }

  function renderHome() {
    const cards = $('#exampleCards');
    if (!cards.dataset.done) {
      cards.innerHTML = SF.examples.map(ex => {
        const names = ex.model.c.map((_, j) => `X${j + 1}`);
        return `<button type="button" class="poster" role="listitem" data-example="${ex.id}" aria-label="Abrir exemplo: ${esc(ex.title)}">
          <span class="play" aria-hidden="true">▶</span>
          <div class="tags">${ex.tags.map(t => `<span class="tag ${tagClass(t)}">${esc(t)}</span>`).join('')}</div>
          <h3>${esc(ex.title)}</h3><p>${esc(ex.desc)}</p>
          <code>${ex.model.sense.toUpperCase()} Z = ${esc(SF.ui.linear(ex.model.c, names))}</code></button>`;
      }).join('');
      cards.dataset.done = '1';
      $('#methodsInfo').innerHTML = SF.methodsInfo.filter(m => m.key !== 'simplex').map(m => `<li><span class="mi" aria-hidden="true">${m.ico}</span>
        <h3>${esc(m.title)}</h3><p>${esc(m.desc)}</p></li>`).join('');
    }
    // continuar de onde parou
    const saved = SF.ui.load('sf-model');
    const row = $('#continueRow');
    if (saved && saved.c) {
      const names = saved.c.map((_, j) => `X${j + 1}`);
      const safe = saved.c.map(v => (isFinite(SF.ui.fracToFloat(String(v).replace(',', '.'))) ? v : '0'));
      $('#continueCards').innerHTML = `<button type="button" class="poster" data-continue="model">
          <span class="play" aria-hidden="true">▶</span><div class="tags"><span class="tag">Modelo em edição</span></div>
          <h3>${esc(saved.name || 'Modelo sem nome')}</h3><p>${saved.c.length} variáveis · ${(saved.cons || []).length} restrições</p>
          <code>${esc(String(saved.sense).toUpperCase())} Z = ${esc(SF.ui.linear(safe, names))}</code></button>
        ${SF.state.results ? `<button type="button" class="poster" data-continue="results"><span class="play" aria-hidden="true">▶</span>
          <div class="tags"><span class="tag t-max">Resultado</span></div><h3>Últimos resultados</h3>
          <p>${esc(SF.state.results.summary.status_label)}</p><code>${esc(SF.state.results.model.formulation.objective)}</code></button>` : ''}`;
      row.hidden = false;
    } else row.hidden = true;
  }

  function bindHome() {
    $('#exampleCards').addEventListener('click', e => {
      const b = e.target.closest('[data-example]');
      if (!b) return;
      const ex = SF.examples.find(x => x.id === b.dataset.example);
      SF.model.load(SF.model.fromExample(ex));
      location.hash = '#/modelar';
      SF.ui.toast(`Exemplo “${esc(ex.title)}” carregado. Ajuste o modelo ou clique em <b>Resolver problema</b>.`, 'success');
    });
    $('#continueCards').addEventListener('click', e => {
      const b = e.target.closest('[data-continue]');
      if (b) location.hash = b.dataset.continue === 'results' ? '#/resultados' : '#/modelar';
    });
    $('#btnNewProblem').addEventListener('click', e => {
      e.preventDefault();
      SF.state.saved = SF.state.model ? JSON.parse(JSON.stringify(SF.state.model)) : null;
      SF.model.load(SF.model.blankModel(), { snapshot: false });
      location.hash = '#/modelar';
    });
    const openLabel = $('#btnOpenProblem');
    openLabel.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#fileOpenHome').click(); } });
    $('#fileOpenHome').addEventListener('change', e => {
      SF.model.openFile(e.target.files[0], () => { location.hash = '#/modelar'; });
      e.target.value = '';
    });
    document.querySelectorAll('label[for="fileOpenModel"]').forEach(l => l.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('#fileOpenModel').click(); }
    }));
  }

  function init() {
    SF.ui.initTheme();
    SF.model.init();
    SF.results.bind();
    SF.results.restore();
    bindHome();
    window.addEventListener('hashchange', route);
    route();
    SF.api.health();
    setInterval(SF.api.health, 30000);
  }

  document.addEventListener('DOMContentLoaded', init);
})(window.SF);
