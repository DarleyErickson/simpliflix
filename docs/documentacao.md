# SimpliFlix — Documentação matemática e técnica

Este documento descreve as rotinas matemáticas implementadas no back-end (`backend/app/algorithms`) e as decisões de projeto.

---

## 1. Representação numérica

Todo o núcleo trabalha com **números racionais exatos** (`fractions.Fraction`):

- entradas JSON são convertidas pela representação decimal (0.1 → 1/10) ou por texto (`"3/4"`);
- testes como "custo reduzido igual a zero", "empate na razão mínima" e "variável básica nula" são **exatos**, sem tolerâncias arbitrárias de ponto flutuante;
- as tabelas são exibidas em frações (com alternância para decimal na interface).

No **Método do Grande M**, cada custo é um `MValue` = `c + m·M`, comparado lexicograficamente (primeiro `m`, depois `c`). Assim, M é tratado como "arbitrariamente grande" sem escolher um número específico.

NumPy é usado onde o ponto flutuante é adequado: amostragem das curvas de nível e da janela do gráfico.

## 2. Modelo e forma padrão (`lp_model.py`, `simplex.py`)

Modelo: otimizar `Z = c·x` sujeito a `Aᵢ·x (≤ | ≥ | =) bᵢ`, com cada variável `≥ 0`, `≤ 0` ou livre.

Conversão para a forma padrão (`build_standard_form`):

| Situação | Transformação |
|---|---|
| `xⱼ ≤ 0` | `xⱼ = −xⱼ'`, com `xⱼ' ≥ 0` |
| `xⱼ` livre | `xⱼ = xⱼ⁺ − xⱼ⁻`, com `xⱼ⁺, xⱼ⁻ ≥ 0` |
| `bᵢ < 0` | linha multiplicada por −1 e operador invertido |
| `≤` | `+ Sᵢ` (folga) |
| `≥` | `− Eᵢ` (excesso) `+ Aᵢ` (artificial) |
| `=` | `+ Aᵢ` (artificial) |

A base inicial é formada pelas colunas identidade (folgas e artificiais).

## 3. Tabela Simplex (`simplex_tableau.py`)

| Elemento | Definição |
|---|---|
| `Cj` | coeficiente da coluna j na função objetivo da fase corrente |
| `CB` | custos das variáveis básicas |
| `Zj` | `Σᵢ CBᵢ · aᵢⱼ` |
| `Cj − Zj` | custo reduzido de j |
| `Z` | `Σᵢ CBᵢ · bᵢ` |

**Critério de otimalidade:** MAX → todo `Cj − Zj ≤ 0`; MIN → todo `Cj − Zj ≥ 0`.

**Pivoteamento** no elemento `p = a_rk`:

```
L_r ← L_r ÷ p
L_i ← L_i − a_ik · L_r      (i ≠ r)
```

Cada operação é registrada em texto (ex.: `L2 ← L2 − 3·L1`) e exibida na interface.

## 4. Simplex primal (`run_iterations`)

1. Calcula `Cj − Zj` para as colunas não básicas.
2. Se nenhuma melhora Z → **ótimo** (critério comprovado).
3. **Variável que entra:**
   - Dantzig (padrão): maior `Cj − Zj` (MAX) / menor (MIN); empate → menor índice;
   - Bland: menor índice entre as que melhoram Z.
4. **Teste da razão mínima:** `θ = min { bᵢ / aᵢₖ : aᵢₖ > 0 }`; empate → variável básica de menor índice.
   Se não houver `aᵢₖ > 0` → **ilimitado**.
5. Pivoteamento e nova tabela.
6. **Anticiclagem:** se uma base já visitada reaparece, o algoritmo passa à regra de Bland, que garante término.
7. **Limite de iterações** (padrão 200): o algoritmo para e informa que a otimalidade **não** foi comprovada; nenhuma solução é apresentada como ótima.

**Degenerescência:** registrada sempre que alguma variável básica vale 0. Um pivô com `θ = 0` é sinalizado como degenerado (Z não muda).

## 5. Método das Duas Fases (`two_phase.py`)

- **Fase 1:** `min W = Σ artificiais`. Se `W* > 0` → **inviável**.
- Se `W* = 0` e ainda há artificial na base (valor 0), ela é retirada por pivô degenerado em qualquer coluna não artificial com coeficiente ≠ 0; se não houver, a linha é **redundante** e é removida.
- **Fase 2:** colunas artificiais ocultadas (mas mantidas internamente para leitura de `B⁻¹`), `Cj` original, `Zj` e `Cj − Zj` recalculados.

Sem restrições `≥`/`=` e com `b ≥ 0`, executa-se diretamente uma única fase a partir das folgas.

## 6. Método do Grande M (`big_m.py`)

Artificiais com custo `−M` (MAX) ou `+M` (MIN). A escolha da coluna de entrada prioriza candidatos cuja parte em M melhora a função. Ao final:

- artificial positiva na base → **inviável**;
- coluna ilimitada com artificial positiva → **inviável**;
- caso contrário, ótimo/ilimitado como no Simplex.

## 7. Simplex Dual (`dual_simplex.py`)

Todas as restrições em forma `≤` (`≥` multiplicada por −1; `=` desdobrada) e base de folgas. Exige tabela **dual-viável** (critério de otimalidade já satisfeito).

1. Sai a variável básica com `bᵣ` mais negativo; se todos `b ≥ 0` → ótimo.
2. Se a linha r não tem `aᵣⱼ < 0` → **primal inviável**.
3. Entra `k = argmin { |Cⱼ − Zⱼ| / |aᵣⱼ| : aᵣⱼ < 0 }`.

Se a tabela inicial não for dual-viável, o método informa que não se aplica e indica Duas Fases ou Grande M.

## 8. Solução ótima, preços-sombra e soluções múltiplas

- **Solução:** básicas = coluna `b`; não básicas = 0; mapeamento de volta às variáveis originais (`x = x⁺ − x⁻`, `x = −x'`).
- **Identificação algébrica** (`algebraic_proof`): lista as básicas, verifica o sinal de cada `Cj − Zj`, expande `Z = Σ cⱼ·xⱼ` e substitui a solução em cada restrição.
- **Preços-sombra:** `y = c_B·B⁻¹`, lido como `Zj` das colunas identidade (folgas/artificiais) na tabela final; corrigido pelo sinal das linhas multiplicadas por −1.
- **Soluções múltiplas** (`detect_alternatives`): para cada não básica com `Cj − Zj = 0` faz-se o teste da razão:
  - sem `aᵢₖ > 0` → semirreta de soluções ótimas;
  - `θ = 0` → pivô degenerado, mesmo ponto (**não** conta como solução distinta);
  - `θ > 0` → pivoteia-se uma cópia da tabela e compara-se a nova solução; se for diferente, a multiplicidade é **confirmada** e a tabela alternativa é exibida.

## 9. Método Algébrico (`algebraic_method.py`)

Forma padrão sem artificiais (`m` equações, `N` variáveis). Para cada uma das `C(N, m)` escolhas de básicas, resolve-se `B·x_B = b` por Gauss-Jordan exato:

- `B` singular → não é base;
- algum `x_B < 0` → solução básica inviável;
- `x_B ≥ 0` → solução básica viável (vértice). A melhor é a ótima (se o problema for limitado, o que o Simplex confirma).

## 10. Método Gráfico (`graphical_method.py`)

1. Semiplanos: cada restrição e cada condição de sinal.
2. Interseções de todos os pares de retas-fronteira (regra de Cramer, exata).
3. **Vértices** = interseções que satisfazem todas as restrições.
4. **Cone de recessão:** direções `d` (ao longo das retas e dos eixos) com `a·d ≤ 0` (≤), `≥ 0` (≥), `= 0` (=). Se existir `d ≠ 0` → região ilimitada; se `c·d` melhorar Z → problema ilimitado.
5. Ótimo = melhor Z entre os vértices; empate entre dois vértices → **segmento** de soluções ótimas; direção com `c·d = 0` → **semirreta**.
6. Desenho: a região é recortada por uma janela retangular (Sutherland–Hodgman exato). Em regiões ilimitadas, a janela é só uma moldura.
7. **Curvas de nível:** retas `c₁x₁ + c₂x₂ = k` para valores de k até Z*; a curva ótima é destacada, e uma seta indica o sentido de melhoria (∇Z para MAX, −∇Z para MIN). Um controle deslizante move a curva de nível.
8. **Pontos inteiros:** todos os pontos da grade dentro da janela que satisfazem as restrições (amostragem acima de 6.000 pontos).

## 11. Branch and Bound (`branch_and_bound.py`)

Cada nó = modelo original + restrições de ramificação, resolvido pelo **Simplex próprio** (Duas Fases).

- **Poda por inviabilidade:** relaxação inviável.
- **Poda por integralidade:** relaxação já inteira → candidata a incumbente.
- **Poda por limitante:** Z da relaxação não é melhor que a incumbente.
- **Ramificação:** variável inteira mais fracionária `xⱼ = v` → `xⱼ ≤ ⌊v⌋` e `xⱼ ≥ ⌈v⌉`.
- **Seleção de nós:** melhor limitante (best-bound).
- **Término:** fila vazia → ótimo **comprovado**; limite de nós → melhor solução encontrada, **sem** prova de otimalidade (informado explicitamente).

Se nenhuma variável for marcada como inteira, todas as variáveis de decisão são tratadas como inteiras (isso é informado ao usuário).

**Conferência:** com 2 variáveis inteiras e região limitada, todos os pontos inteiros da caixa envolvente são enumerados e o melhor é comparado ao do B&B.

## 12. Arredondamento (`integer_solver.py`)

1. Arredonda cada variável inteira ao inteiro mais próximo (0,5 → para cima).
2. Verifica cada restrição e cada condição de sinal individualmente.
3. Se for inviável, testa todas as combinações `⌊xⱼ⌋ / ⌈xⱼ⌉` das variáveis fracionárias (até 12 → 4.096 combinações) e apresenta a melhor viável como **"arredondamento ajustado"**, deixando explícito que é uma heurística.

O arredondamento **nunca** é declarado ótimo; a interface compara contínua × arredondada × inteira ótima.

## 13. Problema dual (`dual_model.py`)

| Primal MAX | Dual MIN | | Primal MIN | Dual MAX |
|---|---|---|---|---|
| restrição ≤ | yᵢ ≥ 0 | | restrição ≥ | yᵢ ≥ 0 |
| restrição ≥ | yᵢ ≤ 0 | | restrição ≤ | yᵢ ≤ 0 |
| restrição = | yᵢ livre | | restrição = | yᵢ livre |
| xⱼ ≥ 0 | restrição dual ≥ | | xⱼ ≥ 0 | restrição dual ≤ |
| xⱼ ≤ 0 | restrição dual ≤ | | xⱼ ≤ 0 | restrição dual ≥ |
| xⱼ livre | restrição dual = | | xⱼ livre | restrição dual = |

Dual: `otimizar W = b·y` sujeito a `(Aᵀy)ⱼ (op) cⱼ`. O dual é resolvido pelo mesmo Simplex tabular (todas as tabelas). São verificados:

- dualidade forte (`Z* = W*`);
- preços-sombra lidos na tabela do primal × solução do dual;
- folgas complementares: `yᵢ·folgaᵢ = 0` e `xⱼ·folga_dualⱼ = 0`.

## 14. Verificações de consistência (`solver_service.py`)

A cada resolução são conferidos automaticamente:

- Z da tabela final = `c·x` avaliado diretamente;
- solução satisfaz todas as restrições;
- todos os métodos tabulares executados concordam;
- método gráfico × Simplex; método algébrico × Simplex;
- dualidade forte;
- ótimo inteiro não supera o contínuo;
- Branch and Bound × enumeração;
- em problemas inviáveis/ilimitados, o gráfico, o método algébrico e o dual confirmam o diagnóstico.

## 15. Validação e erros

- **Front-end:** campos vazios, números inválidos, operador ausente, função objetivo nula, restrição sem coeficientes; campos destacados com mensagem.
- **Back-end** (`validation_service.py`, `model_service.py`): repete todas as verificações, além de quantidade de coeficientes, limites incoerentes, valores não finitos ou grandes demais, nomes repetidos e limites de tamanho. As respostas trazem `field` + `message` em português; exceções internas viram uma mensagem genérica (HTTP 500), sem rastreamento.
