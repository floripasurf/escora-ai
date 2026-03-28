# Escora.AI — Plano de Milestones

**Objetivo:** Ler qualquer projeto estrutural, identificar automaticamente o método construtivo, aplicar normas adequadas e alocar escoras, torres e andaimes corretamente.

**Estado atual:** MVP funcional para edifícios residenciais/comerciais com escoras telescópicas individuais (lajes maciças, vigas retangulares, pilares detectados por geometria).

---

## Milestone 1: Parser Robusto
**Meta:** Ler 95%+ dos DXFs reais do mercado sem perder elementos

### 1.1 Resolução de blocos INSERT
- `virtual_entities()` para extrair geometria de blocos
- Extração de ATTRIB (nomes P1, V12 dentro de blocos)
- Tratamento de blocos aninhados (recursivo)

### 1.2 Decomposição de polylines multi-segmento
- Quebrar LWPOLYLINE de N pontos em segmentos H/V
- Suportar polylines curvas (ARC segments → discretização)
- Vigas desenhadas como contorno fechado (4 pontos)

### 1.3 Leitura de HATCH
- Extrair polígonos de boundary (polyline path + edge path)
- Usar como confirmação de área de laje
- Filtrar hatches decorativos vs estruturais por layer

### 1.4 Leitura de DIMENSION
- Extrair `actual_measurement` e posição
- Usar para validar escala e confirmar seções de vigas
- Associar dimensões a elementos próximos

### 1.5 Case-insensitive nos labels
- Detectar `p70` igual a `P70` (padrão Cesar/ALG)
- Regex unificado com flag `re.IGNORECASE`

### 1.6 Separação de regiões (planta vs detalhe)
- Clustering espacial para isolar planta principal
- Filtrar detalhes/cortes/carimbo por texto ("DETALHE", "CORTE", "SEÇÃO")
- Usar escala da região principal

**Entregável:** Parser aceita todos os 8 DXFs de teste (CFL, RMM, RUH, E E, ALG, CVS + OAEs) com >90% de detecção correta.

---

## Milestone 2: Classificador de Método Construtivo
**Meta:** Identificar automaticamente o tipo de estrutura e laje

### 2.1 Classificador de tipo de obra
Analisar o DXF e classificar em:

| Tipo | Sinais de Detecção |
|------|-------------------|
| **Edifício residencial/comercial** | Layers numéricos TQS, V1a/P1/L1, escala 1:50, pe-direito 2,6-3,2m |
| **Edifício industrial/galpão** | Grandes vãos (>12m), poucos pilares, treliças, pe-direito >6m |
| **Infraestrutura (OAE)** | Layers FOR-/ARM-/DIM-, textos "ENCONTRO", "TABULEIRO", estaqueamento |
| **Contenção/muro de arrimo** | Textos "MURO", "ARRIMO", "CONTENÇÃO", seção com solo + concreto |

### 2.2 Classificador de tipo de laje

| Tipo | Sinais | Impacto no Escoramento |
|------|--------|----------------------|
| **Maciça** | Sem nervuras internas, texto "LAJE MACIÇA" | Escoramento padrão atual |
| **Nervurada** | Linhas paralelas uniformes, layer 7 com polylines, texto "NERVURADA" | Escoras perpendiculares às nervuras, peso-próprio diferente |
| **Treliçada** | Texto "TRELIÇADA", "PRÉ-MOLDADA" | Apoio linear, sem cubetas, escoramento simplificado |
| **Protendida** | Texto "PROTENDIDA", "CORDOALHA", cabos curvos | Desforma antecipada, contra-flecha maior |
| **Steel deck** | Texto "STEEL DECK", "FORMA METÁLICA" | Forma autoportante parcial, escoramento temporário |

### 2.3 Detecção de laje nervurada por geometria
- Agrupar linhas paralelas dentro de painéis de laje
- Verificar espaçamento uniforme (stddev < 10% da média)
- Extrair: direção, espaçamento, largura da nervura
- Confirmar com texto e layer 7

### 2.4 Motor de regras normativas
Mapear tipo de obra → normas aplicáveis:

| Tipo | Normas | Parâmetros Específicos |
|------|--------|----------------------|
| Edifício | NBR 15696, NBR 6118, NBR 6120 | γf=1,4, q_sobrecarga=1,5 kN/m² |
| OAE/ponte | NBR 15696, NBR 7187, NBR 7188 | Cargas de veículos, cimbramento |
| Contenção | NBR 15696 Anexo D, NBR 11682 | Pressão lateral Pb=12Vb+12 |
| Industrial | NBR 15696, NBR 8681 | Cargas especiais, pontes rolantes |

**Entregável:** Sistema identifica tipo de obra e laje automaticamente, aplica normas corretas sem intervenção do usuário.

---

## Milestone 3: Torres de Escoramento
**Meta:** Calcular e alocar torres quando escoras individuais não servem

### 3.1 Decisor escora vs torre
Critérios automáticos:

| Condição | Solução |
|----------|---------|
| Altura ≤ 4,5m E carga ≤ 20 kN/ponto | Escora telescópica |
| Altura > 4,5m OU carga > 20 kN/ponto | Torre de escoramento |
| Altura > 12m OU vão > 15m | Cimbramento (torre + viga) |
| Laje nervurada pesada (h > 30cm) | Torre com viga de distribuição |

### 3.2 Catálogo de torres
- SH (LTT 12tf, Super LTT 18tf)
- PERI (PEP Ergo, ST100)
- Cuplock (modular, alturas variáveis)
- Ringlock (modular, roseta a cada 50cm)

Campos: fabricante, modelo, capacidade_kn, altura_modulo_m, peso_modulo_kg, dimensao_base_m, preco_aluguel_dia

### 3.3 Layout de torres
- Grid de torres respeitando geometria da laje
- Vigas de distribuição entre torres (VM130, GT24, H20)
- Contraventamento lateral obrigatório (NBR 15696)
- Sapatas/bases niveladas em terreno

### 3.4 Cálculo de carga em torres
- Carga distribuída → carga concentrada por torre
- Verificação de capacidade do módulo
- Verificação de estabilidade lateral (esbeltez)
- Fator de redução por altura (NBR 15696 tabela)

**Entregável:** Sistema decide automaticamente entre escora/torre, posiciona torres no DXF, gera BOM com módulos e acessórios.

---

## Milestone 4: Vigas de Distribuição e Cimbramento
**Meta:** Calcular sistema completo escora+viga para grandes vãos

### 4.1 Catálogo de vigas de distribuição
- VM130 (Versatil Metal): h=130mm, Madm=7,8 kN.m, vãos até 3,5m
- GT24 (PERI): h=240mm, Madm=14,5 kN.m, vãos até 5,0m
- H20 (Doka): h=200mm, Madm=5,0 kN.m, vãos até 3,0m
- Vigas de madeira (6x16cm, 6x12cm)

### 4.2 Seleção automática de viga
- Calcular momento fletor máximo no vão entre escoras/torres
- Selecionar viga com M_adm ≥ M_solicitante
- Verificar flecha: f ≤ L/500

### 4.3 Layout primária + secundária
- Vigas primárias: sobre as escoras/torres (direção principal)
- Vigas secundárias: perpendiculares, apoiadas nas primárias
- Espaçamento das secundárias pela espessura do compensado (18mm)

### 4.4 Cimbramento para OAE
- Torres altas (até 30m) com contraventamento diagonal
- Vigas treliçadas para grandes vãos (>6m)
- Fundações provisórias (sapatas de concreto magro)

**Entregável:** Sistema gera layout completo primária+secundária+escoras, com verificação de momento e flecha.

---

## Milestone 5: Escoramento Lateral e Formas Verticais
**Meta:** Calcular pressão lateral e dimensionar formas de muros/paredes

### 5.1 Pressão lateral do concreto
- NBR 15696 Anexo D: Pb = 12 × Vb + 12
- Fatores K1 (temperatura), K2 (retardador), K3 (superplastificante)
- Diagrama de pressão trapezoidal (cresce até h_max, depois constante)

### 5.2 Dimensionamento de tirantes (tie-rods)
- Carga por tirante = pressão × área de influência
- Espaçamento H × V dos tirantes
- Seleção do diâmetro (she-bolt Ø15, Ø20, Ø26mm)

### 5.3 Formas modulares
- Painéis PERI TRIO / Doka Framax / ULMA
- Seleção de painel por pressão suportada
- Layout de painéis (módulos padrão)

### 5.4 Escoramento de valas
- Cálculo de empuxo ativo (Rankine): Ea = 0,5 × Ka × γ × H²
- Dimensionamento de estroncas telescópicas
- Verificação NR-18 (obrigatório > 1,25m)

**Entregável:** Cálculo de pressão lateral, seleção de tirantes e painéis, dimensionamento de blindagem de valas.

---

## Milestone 6: Reescoramento e Ciclo de Concretagem
**Meta:** Planejar sequência de concretagem com reescoras

### 6.1 Conceito de reescoramento
- Reescora: suporte que permanece após desforma parcial
- Típico: 100% escora → desforma parcial → reescora 50-70%
- NBR 15696: prazo mínimo de escoramento por resistência do concreto

### 6.2 Ciclo pavimento-a-pavimento
- Calcular carga acumulada em pavimentos múltiplos
- Método de Grundy-Kabaila para distribuição de carga
- Definir quantos pavimentos escorados/reescorados simultaneamente

### 6.3 Planejamento temporal
- Integrar com fck, tipo de cimento, temperatura
- Calcular prazo mínimo de desforma (NBR 15696 tabela)
- Gerar cronograma de escoramento/desforma/reescoramento

**Entregável:** Plano de reescoramento com sequência de atividades e prazos por pavimento.

---

## Milestone 7: Suporte a IFC e Multi-formato
**Meta:** Aceitar IFC, DWG, PDF além de DXF

### 7.1 Parser IFC (ifcopenshell)
- IfcSlab → laje com espessura, material, nível
- IfcBeam → viga com seção, vão, apoios
- IfcColumn → pilar com posição, seção
- Mapeamento direto para ClassifiedElement (sem inferência)

### 7.2 DWG melhorado
- `ezdxf.addons.odafc` como método primário
- ODA File Converter no Docker como fallback
- Validação do DXF convertido

### 7.3 PDF de planta (futuro)
- OCR de plantas em PDF (PyMuPDF + Tesseract)
- Detecção de linhas e textos por visão computacional
- Conversão para modelo interno

**Entregável:** Upload de IFC gera resultados equivalentes ao DXF, sem detecção geométrica (elementos já classificados).

---

## Milestone 8: Interface e Experiência do Usuário
**Meta:** Interface profissional que guia o processo e mostra resultados visuais

### 8.1 Visualização 2D interativa
- Renderizar DXF no browser (canvas/SVG)
- Mostrar escoras posicionadas sobre a planta
- Cores por tipo: escoras (verde), torres (azul), vigas (amarelo)
- Zoom, pan, seleção de elementos

### 8.2 Dashboard de resultados
- Resumo: total de escoras, torres, vigas, peso, custo estimado
- Detalhamento por pavimento
- Alertas e avisos (capacidade, espaçamento, altura)
- Comparação antes/depois da revisão do engenheiro

### 8.3 Configuração de parâmetros
- Seleção de fabricante preferido
- Pe-direito por pavimento
- Tipo de concreto e cimento
- Velocidade de concretagem
- Temperatura ambiente

### 8.4 Revisão interativa
- Engenheiro clica para mover/adicionar/remover escoras
- Sistema recalcula em tempo real
- Salva revisão como aprendizado

### 8.5 Exportações
- DXF com escoras posicionadas (overlay ou limpo)
- Excel BOM detalhado (multi-aba)
- PDF relatório técnico (memorial de cálculo)
- CSV para importação em ERP/sistema da locadora

**Entregável:** Interface web completa com visualização, configuração e exportação profissional.

---

## Milestone 9: Otimização de Estoque e Integração com Locadora
**Meta:** Otimizar alocação baseado no estoque real da locadora

### 9.1 Importação de estoque
- CSV/Excel com equipamentos disponíveis
- Quantidades, modelos, fabricantes, estado

### 9.2 Otimizador de alocação
- Minimizar custo total respeitando disponibilidade
- Substituição automática (modelo A esgotado → modelo B compatível)
- Priorizar equipamentos em estoque vs compra/aluguel

### 9.3 Multi-obra
- Alocar estoque entre múltiplas obras simultâneas
- Cronograma de uso (quando libera equipamento)
- Dashboard de utilização do parque de equipamentos

**Entregável:** Sistema sugere lista de material baseado no que a locadora tem, otimizando custo e logística.

---

## Milestone 10: Aprendizado e Inteligência
**Meta:** Sistema que melhora com cada projeto processado

### 10.1 Learning loop refinado
- Comparar output do AI vs revisão do engenheiro
- Registrar padrões: "neste tipo de viga, engenheiro sempre adiciona +1 escora"
- Ajustar parâmetros automaticamente por tipo de projeto

### 10.2 Biblioteca de projetos
- Base de projetos processados (anonimizada)
- Busca por similaridade (mesmas dimensões, tipo de laje, fabricante)
- Sugestão baseada em projetos anteriores similares

### 10.3 Validação cruzada
- Comparar resultados com projetos de referência (Sergio1)
- Métricas de acurácia por tipo de elemento
- Alertas quando resultado diverge muito do esperado

**Entregável:** Sistema que reduz erros progressivamente, converge para o padrão de cada engenheiro/locadora.

---

## Resumo de Prioridades

| # | Milestone | Valor para o Cliente | Complexidade | Dependências |
|---|-----------|---------------------|-------------|-------------|
| 1 | Parser Robusto | Alto — aceita mais arquivos | Médio | Nenhuma |
| 2 | Classificador de Método | Alto — automação inteligente | Médio | M1 |
| 3 | Torres de Escoramento | Alto — cobre 40%+ das obras | Alto | M2 |
| 4 | Vigas de Distribuição | Médio — complementa torres | Médio | M3 |
| 5 | Escoramento Lateral | Médio — novo mercado (formas) | Alto | M2 |
| 6 | Reescoramento | Médio — planejamento avançado | Médio | M3 |
| 7 | IFC + Multi-formato | Alto — abre mercado BIM | Alto | M1 |
| 8 | Interface UX | Alto — experiência profissional | Alto | M1-M4 |
| 9 | Otimização de Estoque | Alto — diferencial para locadoras | Médio | M3, M8 |
| 10 | Aprendizado | Alto — melhoria contínua | Médio | M8, M9 |

**Sequência recomendada:** M1 → M2 → M3 → M4 → M8 (paralelo com M5/M6) → M7 → M9 → M10
