/* =====================================================================
   SimpliFlix — cliente da API REST (Fetch API)
   O front-end é independente: por padrão usa a mesma origem quando servido
   pelo FastAPI e http://localhost:8000 quando aberto como arquivo local.
   Pode-se forçar outro endereço com ?api=http://host:porta
   ===================================================================== */
(function (SF) {
  'use strict';

  function detectBase() {
    const q = new URLSearchParams(location.search).get('api');
    if (q) { SF.ui.store('sf-api', q); return q.replace(/\/$/, ''); }
    const saved = SF.ui.load('sf-api');
    if (saved) return saved.replace(/\/$/, '');
    if (location.protocol === 'file:') return 'http://localhost:8000';
    return '';
  }
  const BASE = detectBase();

  class ApiError extends Error {
    constructor(message, details = [], code = 'error', status = 0) {
      super(message);
      this.details = details; this.code = code; this.status = status;
    }
  }

  async function request(path, body, method = 'POST') {
    let resp;
    try {
      resp = await fetch(BASE + path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new ApiError('Não foi possível conectar à API do SimpliFlix. Verifique se o back-end está em execução ' +
        '(uvicorn app.main:app --port 8000).', [], 'network');
    }
    let json = null;
    try { json = await resp.json(); } catch (e) { /* resposta sem JSON */ }
    if (!resp.ok || !json || json.ok === false) {
      const err = json && json.error ? json.error : {};
      throw new ApiError(err.message || `Erro ${resp.status} ao processar a requisição.`, err.details || [], err.code, resp.status);
    }
    return json.data;
  }

  // figura do método gráfico (PNG, SVG ou PDF) gerada no back-end com Matplotlib
  async function figure(body, fmt) {
    let resp;
    try {
      resp = await fetch(`${BASE}/api/solve/graph/figure?fmt=${encodeURIComponent(fmt)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    } catch (e) {
      throw new ApiError('Não foi possível conectar à API do SimpliFlix para gerar a figura.', [], 'network');
    }
    if (!resp.ok) {
      let err = {};
      try { err = (await resp.json()).error || {}; } catch (e) { /* resposta sem JSON */ }
      throw new ApiError(err.message || `Erro ${resp.status} ao gerar a figura.`, err.details || [], err.code, resp.status);
    }
    return resp.blob();
  }

  async function health() {
    const el = document.getElementById('apiStatus');
    try {
      await request('/api/health', null, 'GET');
      el.className = 'api-status online'; el.title = 'API online';
      el.querySelector('.lbl').textContent = 'API online';
      return true;
    } catch (e) {
      el.className = 'api-status offline'; el.title = e.message;
      el.querySelector('.lbl').textContent = 'API offline';
      return false;
    }
  }

  SF.api = {
    BASE, ApiError, health, figure,
    validate: p => request('/api/model/validate', p),
    solveAll: p => request('/api/solve/all', p),
    simplex: p => request('/api/solve/simplex', p),
    graph: p => request('/api/solve/graph', p),
    integer: p => request('/api/solve/integer', p),
    rounding: p => request('/api/solve/rounding', p),
    dual: p => request('/api/solve/dual', p),
    dualForm: p => request('/api/model/dual', p),
  };
})(window.SF);
