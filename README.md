# SimpliFlix

**Plataforma web para modelagem, resolução e visualização de problemas de Programação Linear pelo Método Simplex.**

Projeto acadêmico da disciplina de **Pesquisa Operacional** — Sistemas de Informação, Universidade Estadual de Montes Claros (UNIMONTES).

> O nome combina **Simplex** com a ideia de uma plataforma de streaming: cada iteração do Simplex é apresentada como um episódio, com controles de "player" (primeira, anterior, reproduzir, próxima, última) até a solução final.

---

## 1. Objetivo

Permitir que o usuário insira um problema de Programação Linear (PPL), escolha os métodos de resolução e acompanhe **como** a resposta é encontrada:

- todas as tabelas do Simplex, com variável que entra, variável que sai, razão mínima, elemento pivô e operações elementares;
- região viável, curvas de nível e ponto ótimo no gráfico (2 variáveis);
- solução inteira ótima (Branch and Bound), solução por arredondamento e comparação entre elas;
- problema dual, preços-sombra e verificação da dualidade forte.

O algoritmo Simplex é **implementado pela equipe**, em Python, em **aritmética racional exata** (`fractions.Fraction`). Nenhuma biblioteca de otimização (linprog, PuLP, OR-Tools) é usada para calcular resultados; o SciPy aparece **somente nos testes**, como conferência.

## 2. Funcionalidades implementadas

| Requisito | Situação | Onde |
|---|---|---|
| Modelagem de PPL (MAX/MIN, ≤ ≥ =, sinais ≥0 / ≤0 / livre, domínio contínuo/inteiro) | ✅ | Tela de modelagem |
| Simplex tabular com todas as iterações | ✅ | Aba *Simplex Tabular* |
| Método das Duas Fases (automático quando há artificiais) | ✅ | `two_phase.py` |
| Método do Grande M (M simbólico, a + bM) | ✅ | `big_m.py` |
| Simplex Dual (método de Lemke) | ✅ | `dual_simplex.py` |
| Método Algébrico (enumeração de soluções básicas) | ✅ | `algebraic_method.py` |
| Solução ótima contínua, identificação algébrica e tabela final | ✅ | Abas *Resumo* e *Análise Matemática* |
| Inviável, ilimitado, degenerescência, limite de iterações | ✅ | Todos os métodos |
| Solução inteira ótima (Branch and Bound com o Simplex próprio) | ✅ | Aba *Solução Inteira* |
| Solução inteira por arredondamento + verificação + ajuste explícito | ✅ | Aba *Solução Inteira* |
| Região viável, vértices, curvas de nível, ponto ótimo (Plotly) | ✅ | Aba *Método Gráfico* |
| **Bônus:** problema dual e resolução tabular | ✅ | Aba *Solução Dual*, botão *Converter em Dual* |
| **Bônus:** soluções ótimas múltiplas (com verificação do pivoteamento) | ✅ | Abas *Resumo*, *Gráfico*, *Análise* |
| **Bônus:** pontos inteiros no gráfico | ✅ | Aba *Método Gráfico* |
| **Bônus:** Simplex Dual como método de resolução | ✅ | Card *Simplex Dual* |
| Interface responsiva (desktop, tablet, smartphone), tema claro/escuro | ✅ | `css/responsive.css` |
| Importar/exportar modelo em JSON, exportar resultado | ✅ | Telas inicial, modelagem e resultados |

Recursos adicionais: frações nas entradas (`3/4`), alternância *fração/decimal* nas tabelas, regra de Bland opcional (e automática quando uma base se repete), preços-sombra, folgas complementares, árvore do B&B navegável (com as iterações de cada nó), conferência do B&B por enumeração (2 variáveis), verificações de consistência entre métodos, atalho `Ctrl + Enter` para resolver.

## 3. Tecnologias

- **Back-end:** Python 3.12+ · FastAPI · Uvicorn · NumPy (amostragens do gráfico) · Matplotlib (figura para relatório) · `fractions` (núcleo exato)
- **Front-end:** HTML5 · CSS3 · JavaScript (sem build) · Bootstrap 5.3 · Plotly.js 2.35 · Fetch API
- **Testes:** pytest · httpx · SciPy (somente validação cruzada)

As bibliotecas do front-end estão em `frontend/assets/vendor/`, portanto o sistema funciona **sem internet** durante a apresentação.

## 4. Arquitetura

```
 Navegador (HTML/CSS/JS + Plotly)            API REST (FastAPI)
┌──────────────────────────────┐   JSON   ┌──────────────────────────────────────┐
│ Início → Modelagem → Result. │ ───────▶ │ routes/      (HTTP, respostas padrão) │
│ model.js  simplex.js  ...    │ ◀─────── │ services/    (validação, orquestração)│
└──────────────────────────────┘          │ algorithms/  (Simplex, B&B, gráfico…) │
                                          │ utils/       (frações, matrizes)      │
                                          └──────────────────────────────────────┘
```

O front-end é independente: pode ser servido pelo próprio FastAPI (padrão, `http://localhost:8000`) ou por qualquer servidor estático, apontando para a API com `?api=http://host:porta`.

### Estrutura de diretórios

```
simpliflix/
├── backend/
│   ├── app/
│   │   ├── main.py                    # aplicação FastAPI, tratamento de erros, arquivos estáticos
│   │   ├── schemas.py                 # formato JSON de entrada
│   │   ├── routes/                    # model, simplex, graph, integer, dual
│   │   ├── algorithms/
│   │   │   ├── lp_model.py            # modelo interno exato
│   │   │   ├── simplex_tableau.py     # tabela, Zj, Cj−Zj, pivoteamento
│   │   │   ├── simplex.py             # forma padrão, laço iterativo, múltiplas, preços-sombra
│   │   │   ├── two_phase.py · big_m.py · dual_simplex.py
│   │   │   ├── algebraic_method.py    # enumeração de soluções básicas
│   │   │   ├── graphical_method.py    # região viável, vértices, curvas de nível
│   │   │   ├── branch_and_bound.py · integer_solver.py
│   │   │   └── dual_model.py          # construção e resolução do dual
│   │   ├── services/                  # validação, conversão do modelo, orquestração, gráfico
│   │   └── utils/                     # numerical_utils (Fraction, MValue), matrix_utils
│   ├── tests/                         # 430 testes (pytest)
│   ├── requirements.txt           # dependências do app
│   └── requirements-dev.txt       # + pytest, httpx, SciPy (testes)
├── frontend/
│   ├── index.html                     # SPA: Início, Modelagem, Resultados
│   ├── css/style.css · responsive.css
│   ├── js/ui.js · api.js · examples.js · model.js · simplex.js · graphics.js · integer.js · dual.js · results.js · app.js
│   └── assets/ (logo, vendor/)
├── docs/documentacao.md               # documentação matemática
├── iniciar.bat · iniciar.sh           # inicialização com um clique
└── README.md
```

## 5. Pré-requisitos

- Python **3.12 ou superior** (testado com 3.14)
- Navegador moderno (Chrome, Edge, Firefox, Safari — desktop ou celular)

## 6. Instalação e execução

### Opção rápida (Windows)

Dê dois cliques em **`iniciar.bat`**. Na primeira execução, ele cria o ambiente virtual e instala as dependências; depois abre `http://localhost:8000`.

### Opção manual

```bash
cd simpliflix/backend
python -m venv .venv
```

Ative o ambiente (`.venv\Scripts\activate` no Windows ou `source .venv/bin/activate` no Linux/macOS) e instale:

```bash
pip install -r requirements.txt
```

#### Executar o back-end (API + front-end)

```bash
uvicorn app.main:app --port 8000
```

- Aplicação: <http://localhost:8000>
- Documentação interativa da API (Swagger): <http://localhost:8000/docs>

#### Executar o front-end separadamente (opcional)

```bash
cd simpliflix/frontend
python -m http.server 5500
```

Acesse `http://localhost:5500/?api=http://localhost:8000`. Abrir `index.html` diretamente (file://) também funciona: a API é procurada em `http://localhost:8000`.

**Uso em celular na mesma rede:** execute `uvicorn app.main:app --host 0.0.0.0 --port 8000` e acesse `http://IP-DO-COMPUTADOR:8000`.

## 7. Como utilizar

1. **Início** — clique em *Criar novo problema*, em *Abrir problema* (JSON salvo) ou em um dos exemplos.
2. **Modelagem**
   - **A. Função objetivo:** MAX/MIN, número de variáveis (botões − / +), coeficientes, domínio (contínua/inteira) e sinal (≥ 0, ≤ 0, livre).
   - **B. Restrições:** coeficientes, operador e lado direito. Botões: *Adicionar restrição*, remover (lixeira), *Limpar modelo*, *Restaurar modelo*, *Visualizar formulação* (inclui a forma padrão) e *Converter em Dual*.
   - **C. Métodos:** o Simplex Tabular é sempre executado; selecione também Gráfico (2 variáveis), Algébrico, Grande M, Duas Fases e Simplex Dual. Em *Opções avançadas*: regra de entrada (Dantzig/Bland), limite de iterações e de nós.
   - Clique em **Resolver problema** (ou `Ctrl + Enter`). Campos inválidos são destacados com mensagens em português.
3. **Resultados** — painel lateral com o problema e a solução; abas *Resumo*, *Método Gráfico*, *Simplex Tabular*, *Método Algébrico*, *Solução Inteira*, *Solução Dual* e *Análise Matemática*. Use *Editar modelo* para voltar sem perder os dados.

### Formato JSON da API

```json
{
  "objective": { "type": "max", "coefficients": [7, 2] },
  "variables": [
    { "name": "X1", "domain": "continuous", "lower_bound": 0 },
    { "name": "X2", "domain": "integer", "sign": "nonneg" }
  ],
  "constraints": [
    { "coefficients": [4, 3], "operator": "<=", "rhs": 20 },
    { "coefficients": [10, 2], "operator": "<=", "rhs": 30 }
  ],
  "options": { "methods": ["graphical", "simplex", "big_m"], "pivot_rule": "dantzig" }
}
```

Coeficientes podem ser números ou textos (`"3/4"`, `"2,5"`). `sign` aceita `nonneg`, `nonpos` e `free`; limites diferentes de zero (`lower_bound`, `upper_bound`) viram restrições explícitas.

### Rotas

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | Status da API |
| POST | `/api/model/validate` | Valida e devolve formulação e forma padrão |
| POST | `/api/model/dual` | Converte o primal em dual |
| POST | `/api/solve/simplex` | Simplex tabular (`options.methods`: `two_phase`, `big_m`, `dual_simplex`) |
| POST | `/api/solve/graph` | Método gráfico |
| POST | `/api/solve/algebraic` | Método algébrico |
| POST | `/api/solve/integer` | Branch and Bound + arredondamento |
| POST | `/api/solve/rounding` | Somente arredondamento |
| POST | `/api/solve/dual` | Formulação e resolução tabular do dual |
| POST | `/api/solve/graph/figure?fmt=png\|svg\|pdf` | Figura do método gráfico (Matplotlib, 300 dpi) para relatório e slides |
| POST | `/api/solve/all` | Tudo o que foi selecionado (usado pela interface) |

Respostas: `{"ok": true, "data": {...}}` (HTTP 200) ou `{"ok": false, "error": {"code", "message", "details": [{"field", "message"}]}}` (HTTP 422 para modelos inválidos, 500 para erros inesperados — sem expor detalhes internos).

## 8. Testes

```bash
cd simpliflix/backend
pip install -r requirements-dev.txt
```

```bash
python -m pytest -q
```

(`requirements-dev.txt` acrescenta pytest, httpx e SciPy, usados apenas nos testes; o app em si só precisa de `requirements.txt`.)

São **430 testes**: os 10 cenários exigidos (maximização, minimização, restrições mistas, artificiais, inviável, ilimitado, inteira ótima, arredondamento inviável, múltiplas soluções, dual), testes de degenerescência, Bland, limite de iterações, variáveis livres/≤0, método gráfico, algébrico, API e validação, além de **300 PPLs aleatórios** e **80 problemas inteiros aleatórios** comparados com o SciPy (HiGHS).

## 9. Limitações conhecidas

- Até 20 variáveis e 40 restrições por modelo (12 variáveis e 30 restrições pela interface).
- O método gráfico é exclusivo para 2 variáveis; para mais variáveis, o sistema informa que uma projeção 2D não representa a região viável.
- O método algébrico é limitado a 3.000 combinações de bases.
- Branch and Bound: limite padrão de 500 nós (configurável até 5.000); ao atingir o limite, o sistema informa que a otimalidade **não** foi comprovada.
- Aritmética exata pode produzir frações com denominadores grandes; use o botão *Decimal* para visualizar valores aproximados.
- O Simplex Dual exige tabela inicial dual-viável; caso contrário, o sistema explica o motivo e recomenda Duas Fases/Grande M.
- Restrições redundantes podem tornar os preços-sombra não únicos.

## 10. Equipe

| Integrante | Responsabilidade |
|---|---|
| Darley Erickson | Back-end e algoritmo Simplex; solução inteira e arredondamento; visualização matemática |
| Henrique Borges | Apoio ao back-end, testes das iterações, recursos gráficos, soluções inteira e múltipla |
| Pedro Matheus | Front-end (HTML, CSS, JS), formulários, integração com a API, responsividade |
| Enzo Melo | Documentação, apresentação, apoio ao design e à prototipação |

A documentação matemática está em [`docs/documentacao.md`](docs/documentacao.md).
