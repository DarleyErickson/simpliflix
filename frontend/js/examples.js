/* =====================================================================
   SimpliFlix — exemplos demonstrativos (modelos pré-cadastrados)
   ===================================================================== */
(function (SF) {
  'use strict';
  const V = (n, domain = 'continuous', sign = 'nonneg') => Array.from({ length: n }, () => ({ domain, sign }));

  SF.examples = [
    {
      id: 'mix', title: 'Mix de produção', tags: ['MAX', '2 variáveis', '≤'],
      desc: 'Clássico de fábrica com três recursos limitados. Ótimo único em um vértice.',
      model: { name: 'Mix de produção', sense: 'max', c: ['3', '5'], vars: V(2),
        cons: [{ a: ['1', '0'], op: '<=', b: '4' }, { a: ['0', '2'], op: '<=', b: '12' }, { a: ['3', '2'], op: '<=', b: '18' }] },
    },
    {
      id: 'dieta', title: 'Dieta de custo mínimo', tags: ['MIN', '≥', 'Duas Fases'],
      desc: 'Minimização com restrições ≥: exige variáveis artificiais (Fase 1) e admite o Simplex Dual.',
      model: { name: 'Dieta de custo mínimo', sense: 'min', c: ['2', '3'], vars: V(2),
        cons: [{ a: ['1', '1'], op: '>=', b: '4' }, { a: ['1', '3'], op: '>=', b: '6' }] },
    },
    {
      id: 'inteira', title: 'Arredondar não basta', tags: ['MAX', 'Inteira', 'B&B'],
      desc: 'Ótimo contínuo (2,25; 3,75). O arredondamento (2, 4) é inviável; o ótimo inteiro é (0, 5).',
      model: { name: 'Arredondar não basta', sense: 'max', c: ['5', '8'], vars: V(2, 'integer'),
        cons: [{ a: ['1', '1'], op: '<=', b: '6' }, { a: ['5', '9'], op: '<=', b: '45' }] },
    },
    {
      id: 'multiplas', title: 'Soluções múltiplas', tags: ['MAX', 'Múltiplas'],
      desc: 'A função objetivo é paralela a uma restrição: todo um segmento de soluções é ótimo.',
      model: { name: 'Soluções múltiplas', sense: 'max', c: ['2', '4'], vars: V(2),
        cons: [{ a: ['1', '2'], op: '<=', b: '5' }, { a: ['1', '1'], op: '<=', b: '4' }] },
    },
    {
      id: 'mista', title: 'Restrições mistas', tags: ['MIN', '=', '≥', '≤'],
      desc: 'Combina restrições de igualdade, ≥ e ≤. Solução fracionária (2/5, 9/5).',
      model: { name: 'Restrições mistas', sense: 'min', c: ['4', '1'], vars: V(2),
        cons: [{ a: ['3', '1'], op: '=', b: '3' }, { a: ['4', '3'], op: '>=', b: '6' }, { a: ['1', '2'], op: '<=', b: '4' }] },
    },
    {
      id: 'tres', title: 'Três produtos', tags: ['MAX', '3 variáveis'],
      desc: 'Problema com 3 variáveis: resolvido pelo Simplex (o gráfico 2D não se aplica).',
      model: { name: 'Três produtos', sense: 'max', c: ['3', '2', '5'], vars: V(3),
        cons: [{ a: ['1', '2', '1'], op: '<=', b: '430' }, { a: ['3', '0', '2'], op: '<=', b: '460' }, { a: ['1', '4', '0'], op: '<=', b: '420' }] },
    },
    {
      id: 'degenerado', title: 'Degenerescência', tags: ['MAX', 'Degenerado'],
      desc: 'Empate na razão mínima: uma variável básica assume valor zero durante as iterações.',
      model: { name: 'Degenerescência', sense: 'max', c: ['3', '9'], vars: V(2),
        cons: [{ a: ['1', '4'], op: '<=', b: '8' }, { a: ['1', '2'], op: '<=', b: '4' }] },
    },
    {
      id: 'ilimitado', title: 'Problema ilimitado', tags: ['MAX', 'Ilimitado'],
      desc: 'A região viável é ilimitada no sentido de melhoria: Z cresce sem limite.',
      model: { name: 'Problema ilimitado', sense: 'max', c: ['1', '1'], vars: V(2),
        cons: [{ a: ['1', '-1'], op: '<=', b: '2' }, { a: ['-1', '1'], op: '<=', b: '3' }] },
    },
    {
      id: 'inviavel', title: 'Problema inviável', tags: ['MAX', 'Inviável'],
      desc: 'Restrições contraditórias: a Fase 1 termina com W > 0.',
      model: { name: 'Problema inviável', sense: 'max', c: ['1', '1'], vars: V(2),
        cons: [{ a: ['1', '1'], op: '<=', b: '2' }, { a: ['1', '1'], op: '>=', b: '5' }] },
    },
  ];

  SF.methodsInfo = [
    { key: 'graphical', ico: '◢', title: 'Método Gráfico', desc: 'Região viável, vértices e curvas de nível para problemas com 2 variáveis.' },
    { key: 'algebraic', ico: 'Σ', title: 'Método Algébrico', desc: 'Enumera todas as soluções básicas (combinações de m variáveis) e identifica a melhor viável.' },
    { key: 'simplex', ico: '▶', title: 'Simplex Tabular', desc: 'Método principal: todas as tabelas, entrada, saída, razão mínima e pivô. Usa Duas Fases quando necessário.' },
    { key: 'dual_simplex', ico: '⇅', title: 'Simplex Dual', desc: 'Parte de uma tabela dual-viável e elimina os valores negativos de b, preservando a otimalidade.' },
    { key: 'big_m', ico: 'M', title: 'Método do Grande M', desc: 'Penaliza as variáveis artificiais com custo ±M (tratado simbolicamente, na forma a + bM).' },
    { key: 'two_phase', ico: '2Φ', title: 'Método das Duas Fases', desc: 'Fase 1 minimiza a soma das artificiais; Fase 2 otimiza a função original.' },
  ];
})(window.SF);
