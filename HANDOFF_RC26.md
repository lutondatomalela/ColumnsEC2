# HANDOFF RC26 — ColumnsEC2 / Dimensionamento de Pilares EC2

## Estado actual

Programa: **ColumnsEC2 — Dimensionamento de Pilares segundo NP EN 1992-1-1 / Eurocódigo 2**  
Versão de trabalho: **v0.9 RC26 Modular**

Objectivo: estabilizar a cadeia completa:

```text
importação de esforços
→ reconstrução member/node/case
→ preservação dos tramos físicos
→ selecção dos casos governantes por tramo
→ dimensionamento local
→ racionalização por prumada
→ exportação Excel/PDF/DXF
```

O foco principal não é apenas minimizar a área de aço por tramo isolado. O objectivo é obter **soluções de armadura racionais por prumada**, com continuidade construtiva, evitando excesso de armadura e soluções pouco práticas.

---

## Ficheiro de referência para testes

Usar o ficheiro:

```text
tests/data/ESFORCOS_PILARES.csv
```

Características esperadas:

```text
Encoding: UTF-16 LE com BOM
Separador: ;
Separador decimal: ,
Linhas de esforços: 16 388
Pares member/case reconstruídos: 8 194
Prumadas únicas: 84
Tramos físicos: 241
Casos por tramo: 34 casos × 2 nós = 68 linhas/tramo
Combinação ELS 302: existe
Linhas da combinação 302: 482 = 241 tramos × 2 nós
```

A coluna principal vem como:

```text
Barra/Nó/Caso
```

Exemplo:

```text
119/ 24/ 101 (C)
```

Deve ser interpretado como:

```text
member = 119
node   = 24
case   = 101
```

Se o programa mostrar cabeçalho como:

```text
ÿþBarra/Nó/Caso
```

ou não preencher `member`, `node`, `case`, a leitura do CSV/BOM ainda está errada.

---

## Histórico resumido das correcções

### RC20
Corrigido erro:

```text
maximum recursion depth exceeded
```

Causa: alias/monkey patching circular entre funções RC18/RC19. A função nova chamava a antiga, mas a antiga já apontava para a nova.

### RC21
Introduzida racionalização de armaduras por prumada.  
Problema: ainda colapsava resultados demasiado cedo para 1 linha por prumada.

### RC22
Melhorou CSV/DXF, mas ainda lia mal UTF-16 LE.  
Sintoma: cabeçalho `ÿþBarra/Nó/Caso`; `member`, `node`, `case` vazios; perda de tramos.

### RC23
Corrigido parsing de CSV UTF-16 LE/BOM.

Validação esperada:

```text
Linhas lidas: 16 388
Pares member/case: 8 194
Tramos físicos: 241
Combinação 302 detectada: sim
```

Problema: cálculo ficou muito lento.

### RC24
Acelerada a redução de casos.

Objectivo:

```text
8 194 pares member/case
→ 241 casos governantes principais
→ 241 tramos físicos preservados
```

Problema: exportações PDF/DXF instáveis.

### RC25
Reescritas exportações PDF/DXF.

Correcções:
- PDF com rotina final directa;
- DXF com rotina final directa;
- DXF deve conter as 84 prumadas;
- limpeza de textos `nan;`;
- PDF usa `phi` em vez de `Ø` para evitar problemas de fonte.

Problema: surgiram 14 falhas artificiais no modo rápido.

### RC26
Introduzido fallback rigoroso.

Lógica:
- usa o modo rápido para os casos normais;
- se o modo rápido falhar em N-My-Mz, activa pesquisa adicional apenas nesse tramo;
- só declara falha depois de testar catálogo alargado.

Validação comunicada:

```text
16 388 linhas importadas
8 194 pares member/case
241 tramos físicos preservados
tempo de dimensionamento: ~24 s
falhas anteriores do modo rápido: 14
falhas finais após fallback RC26: 1
```

Falha remanescente a investigar: **PF51 — PISO 1**.

---

## Regras técnicas obrigatórias

### 1. Preservar tramos físicos

Não agrupar inicialmente apenas por `Name`/`Nome`.

Errado:

```python
groupby("Name")
```

Correcto: trabalhar primeiro por uma chave equivalente a:

```python
["member", "Name", "Story", "Section", "Material"]
```

ou:

```text
member + prumada + piso + secção + material
```

A racionalização por prumada só deve ocorrer depois da verificação local dos **241 tramos**.

---

### 2. Não misturar esforços de casos diferentes

A verificação N-My-Mz deve usar esforços simultâneos:

```text
N, My, Mz do mesmo member + node + case
```

Não fazer envolventes independentes de `N`, `My`, `Mz` misturando nós/casos diferentes.

A sequência correcta é:

```text
1. verificar todos os estados simultâneos member + node + case;
2. calcular η para cada estado;
3. escolher o maior η como governante do tramo.
```

---

### 3. ELS

A combinação **302 existe** no ficheiro de referência.

Se o programa disser:

```text
combinação ELS 302 não encontrada
```

isso é bug de importação/parsing.

Se noutros ficheiros a combinação ELS indicada não existir, o estado deve ser:

```text
ELS não avaliado
```

Não deve contaminar o estado ELU.

---

### 4. Falhas

Não declarar falha estrutural quando:

```text
As_prov vazio
η vazio
solução vazia
```

Isso é falha do algoritmo/catálogo, não conclusão estrutural.

Nestes casos, o programa deve:
- activar fallback rigoroso; ou
- reportar como `Sem solução automática gerada — verificar dados/catálogo`.

Falha estrutural real só deve ser declarada se, após pesquisa rigorosa:

```text
η_NMyMz > 1.00
```

ou:

```text
As_req > As_max
```

ou se a geometria impossibilitar fisicamente a disposição dos varões por recobrimento/espaçamento.

---

## Racionalização de armaduras pretendida

Não aplicar uma regra cega do tipo:

```text
As do piso inferior ≥ As do piso superior
```

Isto pode gerar excesso de armadura.

A regra correcta é:

```text
solução racionalizada por prumada
+ continuidade construtiva
+ adaptação quando muda a secção
+ reforços locais quando necessário
```

Exemplo de transição:

```text
Piso inferior: circular D = 30 cm, 6phi12 no perímetro
Piso superior: rectangular 25×30 cm
```

Soluções aceitáveis para o piso superior, se verificarem:
- `4phi12 nos cantos + 2phi12 nas faces maiores`;
- `4phi12 nos cantos`;
- outra solução equivalente, mantendo o diâmetro dominante quando possível.

O programa deve reinterpretar a distribuição da armadura de acordo com a nova geometria, não copiar cegamente a solução anterior.

---

## Relatórios e exportações

O Excel/PDF devem separar claramente:

```text
ELU N-My-Mz
Corte
Torção
ELS
Pormenorização
Estado global
```

Evitar que tudo apareça como `Aviso`.

O quadro por prumada deve idealmente mostrar:

```text
Prumada
Piso
Secção
Material
Solução local necessária
Armadura contínua adoptada
Reforço local
Solução final
η_NMyMz
Nota de transição
```

Não devem aparecer textos:

```text
nan
nan;
None
```

em relatórios técnicos.

---

## DXF

O quadro de pilares deve exportar todos os pilares/prumadas.

Validação esperada:

```text
84/84 prumadas presentes no DXF
```

Se não couberem num só quadro, paginar/blocar:

```text
Quadro 1: pilares 1–24
Quadro 2: pilares 25–48
Quadro 3: pilares 49–72
Quadro 4: pilares 73–84
```

---

## Pontos pendentes na RC26

1. Confirmar se **PF51 — PISO 1** é falha estrutural real ou falso negativo do catálogo/pesquisa.
2. Confirmar que o Excel final contém exactamente **241 tramos**.
3. Confirmar que a combinação **ELS 302** é avaliada.
4. Confirmar que o PDF exporta sem erro.
5. Confirmar que o DXF exporta sem erro e inclui as **84 prumadas**.
6. Confirmar ausência de `nan`, `nan;`, `None` nos relatórios.
7. Verificar se as soluções de armadura por prumada são construtivas.
8. Melhorar, se necessário, a separação entre:
   - armadura contínua;
   - reforço local;
   - solução final por tramo.

---

## Critérios de aceitação

Usando `tests/data/ESFORCOS_PILARES.csv`, a versão corrigida deve cumprir:

```text
1. Ler CSV UTF-16 LE com BOM.
2. Reconhecer a coluna Barra/Nó/Caso.
3. Extrair member/node/case correctamente.
4. Ler 16 388 linhas.
5. Reconstruir 8 194 pares member/case.
6. Preservar 241 tramos físicos.
7. Detectar e avaliar a combinação ELS 302.
8. O resumo final Excel deve conter 241 tramos.
9. Não pode haver falhas com As_prov vazio ou η vazio.
10. PF51 — PISO 1 deve ser investigado e classificado correctamente.
11. PDF deve exportar sem erro.
12. DXF deve exportar sem erro e conter 84/84 prumadas.
13. Relatórios não podem conter `nan`, `nan;` ou `None`.
14. A racionalização deve ocorrer por prumada apenas depois da verificação local por tramo.
15. Tempo de execução preferencial: inferior a 1–2 minutos no ficheiro de referência.
```

---

## Prompt recomendado para Codex

```text
Open this repository/package and use HANDOFF_RC26.md as the technical context.

Audit the full ColumnsEC2 pipeline using tests/data/ESFORCOS_PILARES.csv.

Focus on:
- CSV UTF-16 LE/BOM import;
- extraction of member/node/case from Barra/Nó/Caso;
- preservation of 241 physical tramos;
- ELS case 302 detection;
- N-My-Mz verification using simultaneous actions from the same member/node/case;
- rigorous fallback for false negatives;
- investigation of PF51 — PISO 1;
- Excel/PDF/DXF export;
- absence of nan/None in reports;
- reinforcement rationalisation by prumada only after local tramo verification.

Implement the required fixes and keep runtime below 1–2 minutes for the reference CSV.
```
