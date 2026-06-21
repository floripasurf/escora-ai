# Manual de Normas e Praticas de Escoramento

Manual operacional para calibracao do Escora.AI na leitura, classificacao,
calculo e posicionamento de escoras, torres, vigas metalicas e acessorios de
escoramento.

Fontes usadas:

- PDF `Treinamento Tecnico Escoramento-20-11-2020.pdf`, Grupo Orguel, 123 paginas
  (releitura visual integral pagina a pagina em 2026-06-11).
- DOCX `Escora_AI_Cadeia_Decisoes R.docx`, com perguntas e respostas de engenheiros.
- ABNT NBR 15696:2009 - TEXTO OFICIAL INTEGRAL (Secoes 1-7 + Anexos A-F, 27 p.),
  lido em 2026-06-11. Substitui as fontes secundarias para citacao normativa.
- ABRASFE - Apresentacao oficial da NBR 15696 (Eng. Fernando Rodrigues dos Santos).
- ABRASFE - "Manual de informacoes basicas de forma e escoramento" r04, Parte 1
  (Jefferson Silva), 15 paginas, lido em 2026-06-11.
- Manual Tecnico JAU (Jau Escoramentos), 36 paginas, lido em 2026-06-11.
- BEDENAROSKI, M. (2021). "Diretrizes para escoramento metalico para lajes de
  concreto moldadas in loco" - TCC UTFPR, Pato Branco/PR (lido na integra,
  75 paginas, em 2026-06-11).
- Manual SH - Catalogo tecnico SH 2020 (5200 linhas de texto extraido).
- Manual de escoramento Doka (2014) e Cimbra Doka d1 (2015), via TCC UTFPR.
- Catalogos web: Mills (TS Mills, Alumills), Peri (MULTIPROP), ULMA (ALUPROP),
  Rohr (Kibloc, ETEM, AluROHR), Lajes Martins (pre-moldadas).
- Catalogos do projeto: `catalog/equipment.yaml`,
  `data/catalogs/telescopic_shores.json`, `data/catalogs/shoring_towers.json`.
- Consolidacao previa do repositorio: `PDF_FINDINGS.md` e `AGENTS.md`.

Nota metodologica: o PDF possui camada textual em varias paginas e tambem
conteudo relevante em imagens/tabelas. As regras abaixo consolidam a extracao
de texto, a leitura visual ja registrada em `PDF_FINDINGS.md` e as respostas de
engenharia do DOCX. Valores numericos devem permanecer rastreaveis por fonte.

REVISAO GERAL 2026-06-11: releitura integral de todas as fontes (PDF Orguel
pagina a pagina, DOCX, TCC UTFPR 75 p.) + 3 manuais novos (NBR 15696:2009
texto oficial, ABRASFE r04, Manual Tecnico JAU). Correcoes principais:
gamma_m = 1.5 (secao 3), significado do 0.224 m (secao 13.6), VM50 20x no
pilar 40x70 (secao 15.1), celula 14cm/14mm da tabela de compensado
(secao 12.2), citacao do ciclo de 14 dias (item 6.5, secao 23.8). Conflitos
de metodologia entre fontes registrados na secao 23.9.

## 1. Hierarquia das Fontes

Quando houver conflito entre fontes, o Escora.AI deve aplicar esta ordem:

| Prioridade | Fonte | Uso |
|---|---|---|
| 1 | ABNT NBR 15696:2009 | Base normativa para formas e escoramentos de concreto |
| 2 | ABNT NBR 6118:2023 | Concreto armado, puncao, deformacoes e criterios estruturais |
| 3 | ABNT NBR 6120:2019 | Pesos especificos e acoes em edificacoes |
| 4 | ABNT NBR 14931 | Execucao de estruturas de concreto |
| 5 | ABNT NBR 6123 | Vento |
| 6 | Manuais tecnicos Orguel | Pratica de dimensionamento, equipamento e montagem |
| 7 | Respostas de engenheiros | Calibracao pratica e heuristicas |
| 8 | Projetos executivos Orguel medidos | Padroes empiricos, desde que nao contrariem norma |
| 9 | Catalogos oficiais de outros fabricantes | Autoridade somente para o equipamento daquele fabricante |
| 10 | Manuais, artigos e sites externos | Referencia complementar; nao substitui norma, catalogo ou engenheiro |

Regra de seguranca: nao inventar valor numerico. Valor sem fonte deve entrar
como pendencia de engenharia.

Nota de vigencia normativa: existe revisao NBR 15696:2023 ("Sistemas de formas
e de escoramentos..."), que absorve a NBR 9532 (extinta), inclui concreto
autoadensavel nos abacos do Anexo D e cria a definicao de "forma perdida".
Este manual cita a edicao 2009 (texto oficial lido na integra em 2026-06-11);
verificar a vigencia da 2023 e tratar concreto autoadensavel (CAA) como
gatilho de pendencia ate incorporacao (na 2009, CAA = pressao hidrostatica
plena, vide secao 23.7).

Fontes externas da secao 23 devem ser tratadas como comparativas. Elas so
podem virar regra automatica quando houver ficha tecnica oficial arquivada no
projeto ou catalogo da locadora cadastrado no sistema.

## 2. Enquadramento Juridico e Responsabilidade

O projeto gerado pelo Escora.AI deve ser tratado como sugestao tecnica
auditavel, nao como responsabilidade final da locadora ou do software.

Texto padrao para memoria de calculo:

```text
Este projeto e uma sugestao tecnica para analise. A responsabilidade quanto
a sua utilizacao fica a cargo do engenheiro responsavel pela obra ou do
engenheiro calculista da estrutura.
```

Todo relatorio deve conter:

- bloco de parametros de entrada;
- bloco de normas e fontes;
- memoria de calculo;
- lista de verificacoes;
- pendencias de revisao;
- ART em branco ou campo equivalente de responsabilidade tecnica.

Conteudo minimo do projeto de escoramento, conforme requisitos NBR 15696
citados no manual Orguel p.24-25:

- plantas;
- cortes;
- vistas;
- detalhes suficientes para nao deixar duvida de montagem;
- cargas nas bases de apoio;
- tensao minima no solo/apoio (acrescimo Orguel; a norma fala "cargas nas
  bases de apoio");
- cargas admissiveis dos equipamentos utilizados.

Para FORMAS, o projeto deve ainda mencionar os criterios de dimensionamento
adotados (NBR 15696 item 4.1.2.2): pressao do concreto, velocidade de
lancamento, altura de concretagem e de vibracao, consistencia do concreto e
metodologia de lancamento. O mesmo item autoriza incorporar catalogos
tecnicos e manuais de montagem de equipamentos industrializados com cargas
admissiveis comprovadas - base normativa do modelo de catalogo-da-locadora
do Escora.AI.

## 3. Parametros Normativos Obrigatorios

| Parametro | Valor | Fonte |
|---|---:|---|
| Peso especifico do concreto armado | 25 kN/m3 = 2550 kgf/m3 | NBR 6120 + NBR 15696 item 4.2.1 + Orguel p.26 |
| Peso especifico do aco | 78 kN/m3 | NBR 15696 item 4.2.1 |
| Peso especifico do aluminio | 28 kN/m3 | NBR 15696 item 4.2.1 |
| Peso proprio forma + escoramento (estimativa) | ~0.5 kN/m2 | ABRASFE (estimativa pratica; valor NAO consta na NBR 15696) |
| Sobrecarga de trabalho distribuida | 2.0 kN/m2 = 204 kgf/m2 | NBR 15696 item 4.2.e + Orguel p.26 |
| Plataforma de trabalho local | 1.5 kN/m2 = 153 kgf/m2 | NBR 15696 item 4.2.k + Orguel p.26-27 |
| Carga estatica minima antes da majoracao | 4.0 kN/m2 = 408 kgf/m2 | NBR 15696 item 4.2.e + Orguel p.26 |
| Vento minimo (verificacao do conjunto e normativamente obrigatoria) | 0.6 kN/m2 = 61.2 kgf/m2 | NBR 6123 + NBR 15696 item 4.2.j e Anexo B.2.2 |
| Esforco horizontal lateral nas formas de laje | 5% da carga vertical aplicada (cada sentido principal) | NBR 15696 item 4.2.l; o "6 - 5% V" do diagrama Orguel p.27 e este MESMO esforco - nao somar duas vezes |
| Efeito dinamico de bomba de concreto | SOMAR ao esforco horizontal de 5% quando houver bombeamento | NBR 15696 item 4.2.l |
| Lancamento acima de 0.20 m | nao e proibido, mas exige sobrecarga adicional calculada | NBR 15696 item 4.2.h |
| Sobrecarga em reescoramento durante construcao | minimo 1.0 kN/m2 | NBR 15696 Anexo C.4.a (NOVO) |
| Sobrecarga para verificacao de flecha | 1.0 kN/m2 | NBR 15696 item 4.3.2 (NOVO) |
| Coeficiente de majoracao das ACOES | gamma_Q = 1.4 (psi0 = 1.0 em todas as variaveis) | NBR 15696 item 4.3.1 |
| Coeficiente de ponderacao do MATERIAL de escoras/torres (compressao/flambagem) | gamma_m = 1.5 - minora a RESISTENCIA (Rd = Rk/1.5); CORRIGIDO: nao e majorador de acao | NBR 15696 item 4.3.1.2 |
| Coeficiente de ponderacao do material aco/aluminio (uso geral) | gamma_m = 1.1 | NBR 15696 item 4.3.1.2 |
| Coeficiente de seguranca contra flambagem (equipamento industrializado metalico) | >= 2.0 sobre ruptura ensaiada | NBR 15696 Anexo A (A.3) |
| Coeficiente de seguranca vigas de MADEIRA industrializada (H20/HT20) | >= 2.25 sobre a resistencia ultima caracteristica | NBR 15696 Anexo A (A.2.1) |
| Fator de seguranca ao tombamento (torres isoladas, vigas externas) | >= 1.5 | Fonte externa comparativa; confirmar com engenharia |
| Compressao perpendicular as fibras (madeira) | 25% da compressao paralela | NBR 15696 item 4.3.1.1 (NOVO) |
| Impacto maximo de lancamento | Limitado a queda de 0.20 m acima do nivel acabado | NBR 15696 item 4.2.g (NOVO) |
| Apoio central de viga continua com 3 apoios | 10/8 qL = +25% | Orguel p.109 |
| Apoios extremos de viga continua | 3/8 qL | Orguel p.109 |

Correcao importante: o DOCX antigo cita `1.50 kN/m2` como sobrecarga de
trabalho. No manual Orguel, `1.50 kN/m2` e carga local de plataforma de
trabalho; a sobrecarga distribuida de concretagem e `2.0 kN/m2`.

Peso proprio do escoramento e das formas deve ser considerado
explicitamente em escoramentos acima de 10 m. Vento tambem deve ser incluido
em escoramentos acima de 10 m ou em locais muito abertos. Fonte: Orguel p.26.

As cargas de concretagem, plataforma e vento nao sao alternativas: sao cargas
atuantes simultaneas em regioes diferentes. A sobrecarga de trabalho cobre a
area de concretagem; a plataforma de trabalho e local; o vento atua
lateralmente quando aplicavel. Fonte: Orguel p.27.

Notas da leitura do texto oficial (2026-06-11):

- O piso de 4.0 kN/m2 (item 4.2.e) e "alem daquela em a)": EXCLUI o peso
  proprio do escoramento e das formas (4.2.a). O minimo aplica-se a
  (peso do concreto + sobrecarga), nao ao total com peso do sistema.
- Aplicacao correta dos coeficientes: acoes majoradas por gamma_Q = 1.4 E
  resistencia da escora/torre minorada por gamma_m = 1.5, SIMULTANEAMENTE
  (Fd <= Rd = Rk/gamma_m). A versao anterior deste manual tratava 1.4 e 1.5
  como alternativas - estava errado.
- A condicionalidade "vento somente acima de 10 m ou local aberto" e
  heuristica Orguel de relevancia pratica. Normativamente, a verificacao do
  conjunto para vento e sempre obrigatoria (4.2.j + Anexos B.2.2 e B.3, que
  exigem ancoragem das formas com escoras de prumo/aprumadores).
- Cargas do rol 4.2 ainda sem regra no motor: (d) carregamentos ASSIMETRICOS
  sobre formas e escoramento (concretagem desbalanceada); (f) efeitos
  dinamicos de maquinas alem dos estaticos; (i) vibracoes do adensamento.
  Tratar como pendencia/alerta quando detectaveis.
- Hiperestaticidade: +25% na reacao do apoio central com 3 apoios; com mais
  apoios o acrescimo e da ordem de +10% (Orguel p.85). O fator 1.25 (ou 1.10)
  aplica-se tambem ao q da viga principal quando as secundarias sao continuas
  (Orguel p.83).
- Madeira (NBR 15696 4.3.1.1 + NBR 7190): valores de calculo prontos para
  formas - vide secao 23.12.

## 4. Tensoes Minimas no Apoio

Toda memoria de calculo deve verificar se a base resiste as tensoes abaixo.
Se nao resistir, o apoio precisa ser redistribuido com sapata maior ou solucao
especifica.

| Equipamento | Tensao minima no apoio |
|---|---:|
| Torre de escoramento | 16.53 kgf/cm2 |
| ESC2000-3100 | 26.45 kgf/cm2 |
| ESC3000-4500 | 17.35 kgf/cm2 |

Fonte: bloco de referencias do manual Orguel p.25.

### 4.1 Bloco Obrigatorio da Memoria de Calculo

Toda memoria de calculo deve trazer, no inicio, os dados abaixo preenchidos
ou explicitamente marcados como "nao informado":

| Campo | Observacao |
|---|---|
| Espessura do compensado | mm e formato da chapa |
| Espessura da laje | cm |
| Peso especifico do concreto | normalmente 2550 kgf/m3 |
| Sobrecarga considerada | minimo 204 kgf/m2 |
| Peso proprio da laje | kgf/m2 |
| Carga de escoramento | kgf/m2 |
| Pe-direito do pavimento | m |
| Carga maxima admissivel por poste | kgf |
| Momento admissivel VM80 | 0.212 tf.m |
| Momento admissivel VM130 | 0.516 tf.m |
| Momento admissivel H20/Aluminio | 0.500 tf.m, salvo catalogo especifico |
| Tensao minima no apoio | conforme tabela da secao 4 |

Fonte: Orguel p.25.

## 5. Roteiro Geral do Escora.AI

1. Ler o arquivo de entrada e identificar unidade, escala e origem.
2. Extrair textos de cotas, espessuras, secoes e pe-direito.
3. IDENTIFICAR O SISTEMA ESTRUTURAL do projeto (secao 5.1) e rotear:
   fluxo completo, fluxo parcial ou bloqueio/revisao.
4. Classificar entidades estruturais: lajes, vigas, pilares, paredes,
   shafts, aberturas, nervuras e elementos de desenho que nao devem ser
   escorados.
5. Montar o modelo estrutural com paineis de laje, eixos de viga, apoios e
   intersecoes.
6. Calcular cargas por laje e por viga com fontes rastreaveis.
7. Decidir tipo de suporte: escora telescopica, torre, misto ou revisao de
   engenharia.
8. Selecionar modelos reais do catalogo conforme altura, capacidade, estoque
   e custo.
9. Gerar grid de escoras/torres respeitando bordas, pilares, alvenarias,
   emendas de compensado e vigas metalicas.
10. Inserir vigas principais, secundarias, barrotes, cruzetas, forcados,
   sapatas, diagonais e travamentos.
11. Calcular consumo, kg/m3, utilizacao e alertas.
12. Gerar DXF, BOM, memoria de calculo, relatorio e observacoes de montagem.
13. Bloquear ou sinalizar saida quando houver regra de erro ou pendencia
   critica.

### 5.1 Identificacao do Sistema Estrutural (Passo Zero da Cadeia)

Um dos primeiros passos da cadeia de decisoes e identificar QUAL sistema
estrutural o projeto usa - a estrategia de escoramento (e a propria
aplicabilidade do Escora.AI) depende disso.

Escopo atual do produto (decisao de 2026-06-11): sistemas COMUNS, em
especial concreto armado (foco principal), alvenaria estrutural e
estruturas metalicas. Os demais sistemas ficam registrados para
identificacao e roteamento correto (bloqueio/revisao), nao para
dimensionamento automatico.

#### Sistemas Estruturais Comuns

| Sistema | Indicadores no projeto | Implicacao para o escoramento | Status no Escora.AI |
|---|---|---|---|
| Concreto armado moldado in loco | Pilares, vigas e lajes; secoes `b x h`; textos `h=`, `Lh=`, `fck`; armaduras | Fluxo COMPLETO deste manual (formas, escoras, torres, VMs, reescoramento) | SUPORTADO - foco principal |
| Concreto pre-moldado | Vigotas/trelicadas, alveolares, paineis; notas de fabricante | Fluxo parcial da secao 7.1 (guias perpendiculares, linha de contraflecha, sem forma completa); vao das vigotas e dado do fabricante | SUPORTADO via secao 7 |
| Alvenaria estrutural | Paredes portantes de blocos ceramicos/concreto com funcao de suporte; SEM pilares/vigas no pavimento tipo; modulacao de blocos; cintas e vergas | Lajes apoiam direto nas paredes: escorar apenas a laje, com guias/barrotes a no maximo 5 cm da alvenaria (secao 11.2); nao ha escoramento de vigas; atencao a cargas nas paredes jovens | SUPORTADO parcial - laje sobre parede portante |
| Estrutura metalica | Perfis de aco (W, I, U, tubulares), textos tipo `W310x38`, steel deck; vaos grandes (galpoes, shoppings); ligacoes parafusadas/soldadas | Em geral DISPENSA escoramento de laje: steel deck e autoportante ate o vao do fabricante (escoramento provisorio pontual somente quando o fabricante exigir); a montagem metalica em si nao e escopo de escoramento de concreto | CASO ESPECIAL - rota steel deck da secao 7 (revisao obrigatoria) |
| Wood frame / Steel frame | Perfis leves de aco galvanizado ou madeira tratada; paineis; construcao leve | Nao ha concreto estrutural a escorar (no maximo contrapiso/laje seca) | FORA DE ESCOPO - bloquear e sinalizar |

#### Construcao Pesada / Infraestrutura (identificar e BLOQUEAR)

| Sistema | Indicadores | Roteamento |
|---|---|---|
| Concreto protendido e macico (pontes, viadutos, barragens) | Textos `protendido`, cordoalhas, OAE; pecas de grande volume; empuxos | Caso especial secao 19.1 (OAE/NBR 7187) + OP-030 (desforma so conforme projeto estrutural); cargas 15-50+ kN/m2 |
| Estruturas metalicas especiais (pontes estaiadas, torres de transmissao) | Estais, treliças de grande porte | Fora de escopo - revisao de engenharia |
| Fundacoes profundas e obras subterraneas (helice continua, tubuloes, paredes diafragma) | Plantas de fundacao, estacas, contencoes | Fora de escopo; valas/contencoes seguem NR-18 (secoes 15.4 e 19.1) - bloquear |

#### Regras de Deteccao e Roteamento

1. Deteccao por TEXTO: `ALVENARIA ESTRUTURAL`, `BLOCO ESTRUTURAL`, perfis
   (`W...x...`, `HP`, `UE`), `STEEL DECK`, `PROTENDIDO`, `CORDOALHA`,
   `ESTACA`, `TUBULAO`, `PAREDE DIAFRAGMA`, `OAE`.
2. Deteccao por GEOMETRIA: malha continua de paredes portantes SEM pilares
   -> alvenaria estrutural; grelha de perfis com secoes de catalogo de aco
   -> metalica; vigotas paralelas -> pre-moldado (secao 7.1).
3. Sistema nao identificado com confianca, mas com pilares + vigas + lajes
   -> assumir concreto armado moldado in loco E registrar pendencia de
   confirmacao.
4. Sistema pesado/fora de escopo detectado -> BLOQUEAR a saida automatica e
   rotear para revisao de engenharia, informando o sistema detectado.
5. Projetos mistos (ex.: nucleo de concreto + lajes steel deck) -> tratar
   cada subsistema pela sua regra; a presenca de qualquer subsistema fora
   de escopo gera revisao.
6. O sistema identificado deve constar no bloco de parametros de entrada do
   relatorio (secao 2) com a fonte da deteccao e o score de confianca.

## 6. Leitura e Reconhecimento do Projeto

### 6.1 Textos e Metadados

Extrair e normalizar:

- pe-direito;
- espessura de laje;
- secoes de vigas (`b x h`);
- identificadores de laje (`h=`, `Lh=`, `e=`);
- cotas em cm, mm e m;
- escalas;
- niveis;
- notas de laje nervurada, pre-moldada, trelicada, alveolar, steel deck ou
  protendida.

Quando o texto estiver ausente, usar valor default apenas com alerta:

- pe-direito default: 2.80 m;
- espessura de laje default: 0.12 m.

### 6.2 Geometria

Reconhecer:

- vigas por layer, polilinhas, retangulos alongados e textos de secao;
- pilares por blocos, retangulos compactos, circulos ou hatches;
- paineis de laje por malha fechada de vigas ou contornos;
- shafts e aberturas por hatches, layers de vazio, textos e contornos internos;
- nervuras por grid ortogonal repetitivo;
- regioes macicas e capiteis por hatches densos ou indicacoes textuais.

### 6.3 Saida de Confianca

Cada elemento classificado deve receber:

- tipo;
- geometria;
- fonte da classificacao;
- score geometrico;
- score textual;
- score final;
- pendencias, se houver.

## 7. Tipos de Laje e Estrategia

| Tipo | Indicadores no desenho | Estrategia |
|---|---|---|
| Macica moldada in loco | Hatch solido, espessura unica, `h=` ou `Lh=` | Forma completa com compensado, barrotes, guias/travessas e escoras/torres |
| Pre-moldada/trelicada | Vigotas e lajotas, linhas paralelas, texto `trelicada` | Sem forma completa; usar guias perpendiculares as vigotas e linha obrigatoria no ponto de contraflecha |
| Alveolar | Painel pre-moldado/protendido, indicacao alveolar | Em geral dispensa escoramento; enviar para revisao |
| Nervurada | Grid de cubetas/nervuras | Preferir sistema Mecaner; apoiar nas nervuras; tratar faixas macicas e capiteis |
| Plana/cogumelo (flat slab) | Sem vigas; capiteis ou engrossamento junto aos pilares (1.5h a 3h alem da face) | Grid regular no campo + DENSIFICACAO no anel ao redor do pilar (zona de puncao) + capitel tratado como sub-painel de espessura maior, com forma propria e escoras/torres dedicadas |
| Steel deck | Texto `steel deck`, forma metalica | Caso especial; exigir revisao ou regra propria |

Para lajes pre-moldadas, o vao maximo das vigotas e dado do fabricante ou do
contratante. O sistema nao deve inventar esse vao.

### 7.1 Lajes Pre-Moldadas e Trelicadas

Regras formalizadas do manual Orguel p.33-36:

- lajes pre-moldadas comuns vencem, em geral, vaos ate 5 m entre apoios;
- os comprimentos das vigotas variam, em geral, de 10 em 10 cm (Orguel p.33);
- nao exigem forma completa;
- exigem guias apoiadas em escoramento vertical;
- dispensam barroteamento;
- guias devem ficar perpendiculares as vigotas;
- deve existir uma linha de escoramento no ponto da contraflecha, geralmente
  no meio do vao;
- alveolares sao excecao para a linha de contraflecha;
- se forem usadas apenas escoras, sem guias, elas devem ser fixadas entre si
  com tubos de amarracao ou sarrafo, sob responsabilidade do cliente.

### 7.2 Lajes Nervuradas e Sistema Mecaner

Regras formalizadas do manual Orguel p.40-49:

- laje nervurada e conjunto de vigas cruzadas solidarizadas por mesa;
- pode usar enchimento permanente (ceramico, EPS/isopor, sical) ou temporario
  (cubas de polipropileno);
- sistema Mecaner e indicado para lajes nervuradas com formas de
  polipropileno;
- Mecaner permite desforma rapida, liberando formas sem retirar as escoras;
- reguas metalicas substituem sarrafo de madeira;
- reguas podem ter 75 mm ou 30 mm de largura;
- as reguas possuem encaixe macho/femea e cabecal com pino;
- a faixa de reescoramento usa Cabecal de Espera intercalado com regua;
- apos a cura, retiram-se escoramento, guias e cubetas, ficando apenas o
  cabecal sobre as reescoras;
- como as reguas Orguel possuem 7.5 cm, cubetas devem descontar essa largura
  em um dos lados. Exemplo: cubeta nominal de 80 cm deve medir 80 x 72.5 cm.

Confirmacao independente (JAU p.29-30): guias de cubeta de 3.0 e 7.5 cm de
largura; guia continua de 0.72 m (coerente com o desconto de 7.5 cm); o
suporte de cubeta vira reescoramento junto com a escora apos a retirada de
cubetas e guias (mesmo fluxo do Cabecal de Espera). Regra de montagem JAU: a
trava mantem o alinhamento entre suporte e guias durante o ajuste - sem ela
o suporte sobe e forma degrau.

Validacao dimensional da deteccao de nervuradas (NBR 6118, via research -
filtro de sanidade da classificacao, secao 6.2): espacamento de nervuras
40-90 cm; largura de nervura 6-16 cm (minimo 5 cm); mesa >= 3 cm e >= 1/15
do espacamento; moldes 40x40 a 80x80 cm; altura total 16-45 cm. Grid
detectado fora dessas faixas deve reprovar a classificacao "nervurada".

## 8. Regra de Pe-Direito e Tipo de Suporte

Esta secao ajusta a diferenca entre pratica geral de locadoras e projetos
Orguel. A Orguel e referencia, mas pode adotar criterios proprios por estoque,
especialmente usando torres em estruturas com menos de 3.50 m. Para calibracao
do Escora.AI como ferramenta ampla de locadoras, a regra deve ser:

| Faixa de pe-direito | Decisao operacional |
|---|---|
| `H <= 3.50 m` | Padrao: escoras simples/telescopicas. Nao usar torre por area ou por capitel sem justificativa estrutural explicita. |
| `3.50 m < H < 4.00 m` | Escora telescopica ESC450 possivel, com verificacao de capacidade derateada. Torre apenas se carga, viga ou geometria exigirem. |
| `4.00 m <= H < 4.50 m` | Torres/andaimes facultativos. Escora ESC450 ainda pode ser usada se passar por capacidade e estabilidade. Emitir alerta de faixa alta. |
| `H >= 4.50 m` | Torre/andaime obrigatorio no criterio Escora.AI por default. Nao selecionar escora telescopica como suporte vertical principal, EXCETO quando o estoque da locadora possuir modelos estendidos (vide nota abaixo). |

Fonte base: manual Orguel p.8-12. A p.9 recomenda escoras para apoios
nivelados, lajes com vao entre vigas ate 4 m e pe-direito ate 3.50 m. A p.12
aponta torres principalmente quando o pe-direito ultrapassa 4.50 m. O corte
`>= 4.50 m` e adotado aqui como criterio conservador e alinhado a pratica
informada pelo usuario.

Nota sobre escoras telescopicas estendidas (> 4.50 m): alguns fabricantes
estao desenvolvendo (e algumas locadoras ja possuem em estoque) escoras
telescopicas com abertura maxima superior a 4.50 m. Quando essas escoras
estiverem cadastradas no catalogo da locadora (`telescopic_shores.json`
ou equivalente), o Escora.AI deve:

1. Permitir selecao de escoras telescopicas para `H >= 4.50 m`, desde que o
   modelo cadastrado cubra a abertura calculada e tenha capacidade adequada.
2. Manter o alerta de faixa alta e exigir verificacao reforcada de capacidade
   e estabilidade (contraventamento lateral, base ampliada, etc).
3. Tratar a regra `H >= 4.50 m` como bloqueio condicional ao catalogo, nao
   como bloqueio absoluto: se nao houver modelo de estoque que atenda, cair
   para torre/andaime.

A interpretacao deve ser: torre/andaime e a opcao DEFAULT acima de 4.50 m,
mas o estoque comanda a decisao final. Em catalogos legados (somente
ESC2000-3100 e ESC3000-4500), o bloqueio acima de 4.50 m permanece.

## 9. Cadeia de Decisao de Suporte

Aplicar em ordem. A primeira regra satisfeita vence.

| Ordem | Pergunta | Resultado |
|---:|---|---|
| 1 | `H >= 4.50 m`? | Torre/andaime obrigatorio, EXCETO se houver escora telescopica estendida cadastrada no catalogo da locadora que cubra a abertura com capacidade adequada |
| 2 | `H <= 3.50 m` e sem condicao estrutural excepcional? | 100% escora telescopica |
| 3 | Carga majorada por ponto supera todas as escoras compativeis? | Torre |
| 4 | Sem torres em estoque e altura/carga permitem escora? | Escora telescopica |
| 5 | Viga externa fora dos limites de escora simples? | Torre ou estaiamento |
| 6 | Viga interna > 10 m ou >40 cm de largura ou >70 cm de altura? | Torre |
| 7 | Viga interna entre 6 e 10 m, ate 40 x 70 cm? | Misto: escoras + torre central |
| 8 | Viga interna ate 6 m, ate 40 x 70 cm? | Escoras + cruzetas |
| 9 | Viga com laje >= 15 cm ou vao > 6 m? | Misto em pontos criticos |
| 10 | Laje >= 20 cm? | Misto, salvo `H <= 3.50 m` sem excepcionalidade |
| 11 | Painel de laje >= 40 m2? | Misto, salvo `H <= 3.50 m` sem excepcionalidade |
| 12 | Laje nervurada >= 25 cm? | Misto ou Mecaner, com revisao |
| 13 | Vao livre > 15 m (laje ou estrutura)? | Cimbramento pesado / projeto especial com revisao de engenharia (regra recuperada do DOCX; cobre corredores longos que escapam do criterio de area >= 40 m2) |
| 14 | Nenhuma regra acionada | Escora telescopica |

Observacao critica: regras de laje grande e laje espessa nao devem gerar torres
em pe-direito baixo automaticamente. Abaixo de 3.50 m, o sistema deve primeiro
tentar resolver por densificacao de escoras e verificacao de capacidade.

Nota sobre escoramento misto (DOCX, resposta 1): em obras de edificacoes os
engenheiros usam misto na MAIORIA dos casos, mesmo em pe-direito baixo, quando
ha justificativa (viga critica, intersecoes, apoio de VM torre a torre). Misto
em pe-direito baixo e aceitavel quando justificado e registrado; o alerta da
secao 18 deve disparar apenas quando a fracao de torres exceder o envelope
empirico sem justificativa estrutural.

Heuristica de posicionamento misto (DOCX, resposta 9): torres e escoras sao
definidas EM CONJUNTO, nao sequencialmente: (1) distribuir as torres de forma
que as VMs primarias fiquem apoiadas de torre a torre (vao da VM = distancia
entre torres); (2) escoras telescopicas entram como apoios intermediarios que
"quebram" o vao de verificacao da VM. A conversao percentual de posicoes
igualmente distribuidas nao garante VM apoiada em torre nas extremidades -
corrigir no motor.

## 10. Regras para Vigas

### 10.1 Vigas Externas

Viga externa pode ser escorada somente com escoras e cruzetas se atender todos:

- largura <= 30 cm;
- altura <= 60 cm;
- comprimento <= 3.00 m.

Se ultrapassar qualquer limite:

- usar torres; ou
- usar estaiamento; ou
- enviar para revisao de engenharia.

Vigas externas com console exigem atencao especial; o manual Orguel indica
console para alturas a partir de 70 cm.

Fonte: Orguel p.111.

### 10.2 Vigas Internas

| Comprimento | Secao | Estrategia |
|---|---|---|
| `L <= 6.00 m` | largura <= 40 cm e altura <= 70 cm | Escoras + cruzetas |
| `6.00 m < L <= 10.00 m` | largura <= 40 cm e altura <= 70 cm | Misto: escoras + torre central |
| `L > 10.00 m` ou largura > 40 cm ou altura > 70 cm | Fora do envelope leve | Torres como apoios principais; escoras admitidas como complemento apoiando as guias ("pode mesclar", Orguel p.113 - harmonizado com OP-016) |

Fonte: Orguel p.112-113. Convergencia independente: o garfo interno JAU (p.16)
tambem limita o travamento de vigas internas a 700 mm de altura - dois
fabricantes confirmam o corte de 70 cm.

### 10.3 Posicionamento em Vigas

- Sob vigas escoradas com telescopicas, o CONJUNTO escora + cruzeta e
  distribuido a cada 0.80 m (razao cruzeta:escora = 1:1 sob vigas), com
  1.00 m como teto absoluto. A cruzeta e montada SOBRE a escora; nao sao
  duas regras independentes. Fonte: DOCX resposta 5 + Orguel. O ratio 0.25
  cruzeta/escora medido em estoque e vies de inventario (medio de obra
  inteira), nao regra de projeto sob viga.
- Torres sob vigas: espacamento maximo pratico 1.50 m, condicionado por VM.
- Intersecoes de vigas sem pilar devem receber escora ou torre.
- Em viga continua com 3 apoios, apoio central recebe +25% de carga.
- Forcados nao devem ser colocados em extremidades em balanco.
- Para viga continua com 3 apoios, a disposicao correta e torre no apoio
  central, absorvendo o acrescimo de 25%, e escoras telescopicas nas
  extremidades. Inverter essa logica pode sobrecarregar as escoras.
- Em lajes com suporte de forcado, o forcado deve ficar dentro da area da
  laje e apoiado por baixo, nao em balanco.

## 11. Regras para Lajes

### 11.1 Grid de Escoras

O grid deve:

- recuar 0.15 m da borda da laje;
- recuar no minimo 0.70 m da face do pilar;
- manter 0.30 m minimo entre escoras;
- verificar se cada ponto esta dentro do poligono real da laje;
- alinhar grids de lajes adjacentes quando possivel;
- usar distribuicao linear em corredores estreitos;
- colocar pelo menos uma escora no centroide quando o grid falhar;
- teto operacional para lajes macicas: grid de referencia 1.00 x 1.00 m
  (convergencia das fontes da secao 23.3); espacamentos maiores somente com
  verificacao de capacidade da escora + VM por momento e flecha;
- em capiteis, faixas macicas de nervuradas e regioes de carga concentrada,
  DENSIFICAR o grid e priorizar torres nesses pontos, mantendo grid regular
  no restante do painel (DOCX resposta 6).

ATENCAO sobre proveniencia (correcao de 2026-06-11): a tabela de espacamento
por espessura usada no motor (10-16 cm -> 1.30 m; 17-24 -> 1.20 m; 25-30 ->
1.10 m; 31+ -> 1.00 m) NAO e da NBR 15696 (a norma nao prescreve espacamento
de escoras fora do reescoramento). As tres primeiras linhas vem da tabela
Lajes Martins para LINHAS de escoramento de lajes PRE-MOLDADAS (secao 23.4);
a linha "31+" nao existe em nenhuma fonte. Para lajes macicas, usar o teto
operacional de 1.00 x 1.00 m acima.

### 11.2 Bordas, Alvenaria e Barrotes

| Situacao | Regra |
|---|---|
| Com forma lateral de parede | Primeiro barrote a 20-40 cm da borda da forma |
| Laje encostada em parede de concreto | Primeiro barrote a 5 cm da borda do concreto |
| Alvenaria estrutural | Guias/barrotes a no maximo 5 cm |
| Emenda de compensado | A emenda deve cair no eixo do barrote; ACRESCENTAR um barrote extra por linha de emenda (transpasse de barrotes, Orguel p.115) - impacta BOM de VM80 |
| Espacamento de barrotes | Multiplo do comprimento da chapa: 220 ou 244 CM (o PDF Orguel p.114 grafa "mm" por erro; chapas sao 2.20/2.44 m; espacamentos praticos = 220/n ou 244/n cm: 55, 61, 73...) |

Fonte: Orguel p.105-107 e p.114-115.

## 12. Espacamento de Barrotes por Compensado

### 12.1 Propriedades do Compensado

Propriedades do manual Orguel p.78:

| e mm | M adm kgf.m/m | E.I kgf.m2/m | Peso kg/m2 |
|---:|---:|---:|---:|
| 12 | 26 | 98 | 7.0 |
| 14 | 36 | 156 | 8.0 |
| 15 | 41 | 192 | 9.0 |
| 17 | 53 | 279 | 10.0 |
| 18 | 60 | 331 | 10.5 |
| 20 | 73 | 455 | 12.0 |
| 21 | 81 | 526 | 12.5 |

Parametros comuns:

- tensao admissivel a flexao: 110 kgf/cm2;
- modulo de elasticidade medio: 68200 kgf/cm2.

### 12.2 Tabela de Vaos Maximos

Tabela canonica do manual Orguel p.89. Valores em cm. Cada celula contem:
`2 apoios / 4 apoios` (o cabecalho do PDF diz explicitamente "PARA 2 / 4
APOIOS"; o segundo valor corresponde a 3 vaos, nao a "3+ apoios" generico).

| Laje (cm) | Carga kgf/m2 | 12 mm | 14 mm | 15 mm | 17 mm | 18 mm | 20 mm | 21 mm |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 408 | 42/50 | 48/61 | 50/61 | 58/69 | 61/71 | 68/84 | 71/84 |
| 9 | 434 | 41/49 | 48/49 | 50/60 | 57/68 | 60/70 | 66/79 | 70/82 |
| 10 | 459 | 40/49 | 47/49 | 50/60 | 55/67 | 59/69 | 65/77 | 68/80 |
| 11 | 485 | 39/48 | 46/48 | 49/59 | 54/66 | 58/68 | 64/76 | 67/79 |
| 12 | 510 | 38/47 | 45/47 | 48/59 | 53/64 | 57/67 | 63/75 | 66/78 |
| 13 | 536 | 38/46 | 44/46 | 47/58 | 53/64 | 56/66 | 62/74 | 65/77 |
| 14 | 561 | 37/45 | 44/45 | 47/57 | 52/63 | 55/64 | 61/73 | 64/76 |
| 15 | 587 | 37/45 | 43/45 | 46/56 | 51/62 | 54/63 | 60/72 | 63/75 |
| 16 | 612 | 36/44 | 42/44 | 45/55 | 50/61 | 53/62 | 60/71 | 62/74 |
| 18 | 663 | 35/43 | 41/43 | 44/54 | 50/60 | 52/62 | 58/70 | 61/72 |
| 20 | 714 | 34/42 | 40/42 | 43/52 | 49/59 | 51/61 | 56/69 | 59/70 |
| 22 | 765 | 33/41 | 39/41 | 42/51 | 48/58 | 51/60 | 55/66 | 58/69 |
| 25 | 842 | 33/40 | 38/40 | 41/50 | 46/56 | 49/60 | 53/65 | 56/67 |
| 28 | 918 | 32/39 | 37/39 | 40/48 | 45/55 | 48/58 | 52/63 | 54/64 |
| 30 | 969 | 31/38 | 36/38 | 39/47 | 44/54 | 47/57 | 51/62 | 53/64 |
| 35 | 1097 | 30/36 | 35/36 | 37/46 | 42/51 | 45/54 | 50/60 | 51/62 |
| 40 | 1224 | 29/35 | 33/35 | 36/44 | 41/50 | 43/53 | 48/58 | 50/60 |
| 50 | 1479 | 27/33 | 31/33 | 34/41 | 38/47 | 41/49 | 45/55 | 47/57 |
| 60 | 1734 | 25/31 | 30/31 | 32/39 | 36/44 | 38/47 | 43/52 | 45/54 |
| 80 | 2244 | 23/29 | 27/29 | 29/36 | 34/40 | 35/43 | 39/48 | 41/50 |
| 100 | 2754 | 22/27 | 25/27 | 27/33 | 31/38 | 33/40 | 37/44 | 38/47 |

Notas de calibracao (2026-06-11):

- O exemplo canonico Orguel p.88-89 adota espacamento de 55 cm (= 220/4,
  multiplo da chapa) para laje 10 cm / compensado 14 mm, EXCEDENDO a propria
  tabela (47/49 cm). O Escora.AI deve obedecer a tabela; tratar o exemplo
  como pratica de campo nao conservadora.
- O fabricante JAU publica tabelas equivalentes ja QUANTIZADAS em fracoes da
  chapa (L/4, L/5, L/6...), o que garante emenda em eixo de barrote por
  construcao. Transcricao integral na secao 23.11. Em geral os valores JAU
  aproximam-se da coluna "4 apoios" Orguel; nao intercambiar entre
  fabricantes.

## 13. Equipamentos

### 13.1 Escoras Telescopicas

| Modelo | Abertura | Flauta (tubo interno) | Capa (tubo externo) | Uso |
|---|---:|---:|---:|---|
| ESC Junior | 2.00-3.10 m | 42.20 mm | 50.80 mm | Somente venda; nao deve ser padrao de locacao se nao estiver no estoque |
| ESC 2000-3100 | 2.00-3.10 m | 42.20 mm | 50.80 mm | Padrao para pe-direito baixo |
| ESC 3000-4500 | 3.00-4.50 m | 50.80 mm | 60.30 mm | Padrao para faixa intermediaria |
| ESC Estendida | > 4.50 m | varia por fabricante | varia por fabricante | Modelos em desenvolvimento; algumas locadoras ja possuem em estoque. Cadastrar dimensoes reais no catalogo da locadora antes de habilitar |

Capacidade da ESC Junior conforme abertura (NOVO - p.11):

| Abertura m | 2.00 | 2.10 | 2.20 | 2.30 | 2.40 | 2.50 | 2.60 | 2.70 | 2.80 | 2.90 | 3.00 | 3.10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kgf | 2000 | 1900 | 1800 | 1700 | 1550 | 1425 | 1300 | 1225 | 1150 | 1100 | 1050 | 1000 |

Capacidade da ESC 2000-3100 conforme abertura:

| Abertura m | 2.00 | 2.10 | 2.20 | 2.30 | 2.40 | 2.50 | 2.60 | 2.70 | 2.80 | 2.90 | 3.00 | 3.10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kgf | 3200 | 2850 | 2650 | 2550 | 2400 | 2250 | 2100 | 1900 | 1800 | 1650 | 1550 | 1500 |

Capacidade da ESC 3000-4500 conforme abertura:

| Abertura m | 3.00 | 3.10 | 3.20 | 3.30 | 3.40 | 3.50 | 3.60 | 3.70 | 3.80 | 3.90 | 4.00 | 4.10 | 4.20 | 4.30 | 4.40 | 4.50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kgf | 2100 | 2000 | 1900 | 1800 | 1700 | 1650 | 1550 | 1500 | 1400 | 1350 | 1250 | 1150 | 1050 | 950 | 850 | 750 |

Regra de selecao por abertura: usar a tabela cuja faixa engloba a `abertura_escora` calculada. Quando a abertura cair na faixa 3.00-3.10 m, comparar ESC 2000-3100 (1550-1500 kgf) com ESC 3000-4500 (2100-2000 kgf) e escolher a que tiver maior margem para a carga solicitada, considerando estoque.

Fonte: Orguel p.11.

### 13.2 Torres

Torres sao indicadas quando:

- pe-direito exige;
- carga supera a capacidade das escoras;
- viga interna/externa exige pela regra 16;
- ha grandes alturas, passagens, rampas ou projeto especial;
- o projeto exige rigidez, estabilidade ou apoio de VM torre a torre.

Capacidade da torre em funcao do numero de modulos de 1.50 m (curva Orguel p.86).
CORRECAO: a curva esta rotulada como "Carga no montante"; os valores plotados
(2000, 1900, 1850, 1800...) sao kgf por montante, nao kN por torre. Para obter
a capacidade total da torre, multiplicar por 4 montantes.

| Modulos | Altura m | Carga kgf/montante | Carga total kgf/torre (4 montantes) | kN/torre |
|---:|---:|---:|---:|---:|
| 1 | 1.5 | 2000 | 8000 | 78 |
| 2 | 3.0 | 1900 | 7600 | 75 |
| 3 | 4.5 | 1850 | 7400 | 73 |
| 4 | 6.0 | 1800 | 7200 | 71 |
| 5 | 7.5 | 1770 | 7080 | 69 |
| 6 | 9.0 | 1750 | 7000 | 69 |
| 7 | 10.5 | 1730 | 6920 | 68 |
| 8 | 12.0 | 1710 | 6840 | 67 |
| 9 | 13.5 | 1690 | 6760 | 66 |
| 10 | 15.0 | 1670 | 6680 | 66 |
| 11 | 16.5 | 1650 | 6600 | 65 |
| 12 | 18.0 | 1630 | 6520 | 64 |
| 13 | 19.5 | 1610 | 6440 | 63 |
| 14 | 21.0 | 1590 | 6360 | 62 |
| 15 | 22.5 | 1570 | 6280 | 62 |
| 16 | 24.0 | 1550 | 6200 | 61 |
| 17 | 25.5 | 1530 | 6120 | 60 |
| 18 | 27.0 | 1510 | 6040 | 59 |
| 19 | 28.5 | 1490 | 5960 | 58 |
| 20 | 30.0 | 1470 | 5880 | 58 |

Conversao: 1 kgf = 9.80665e-3 kN, arredondado.

Regra de uso: comparar a carga descarregada por torre (carga distribuida x
area de influencia da torre, ou somatorio de cargas de vigas apoiadas) com a
linha correspondente a altura/numero de modulos. Aplicar fator de seguranca
adicional quando a utilizacao ultrapassar 80%.

Revisao de 2026-05-27: a imagem da curva Orguel foi conferida em 300 dpi. O
ponto do modulo 14 e 1590 kgf/montante; a leitura anterior como 1500 era erro
visual por baixa resolucao.

Confirmacoes de 2026-06-11:

- O Manual Tecnico JAU (p.06) publica a MESMA curva, ponto a ponto, inclusive
  modulo 14 = 1590 - e curva de mercado comum para torres de quadros de
  1.50 m. Confirmacao definitiva da tabela acima por fonte independente.
- Unidade kgf/montante corroborada por dupla evidencia: Orguel p.85 ("carga
  no poste = 2,0 tf") e JAU p.02 ("CARGA MAXIMA POR POSTE: 20 kN = 2000 kgf").
  O eixo do grafico (em ambos os manuais) esta rotulado "kN" por erro grafico.
- "Andaime" neste manual significa TORRE DE CARGA. Andaime fachadeiro/de
  acesso (carga 150-200 kgf/m2, apenas circulacao) NUNCA pode ser usado como
  escoramento; andaime multidirecional somente com verificacao especifica de
  engenharia. Fonte externa comparativa.

### 13.3 Vigas Metalicas e Perfis

Conceito (Orguel p.19):

- **Viga primaria (principal):** vigas que atuam no sentido longitudinal dos
  vaos das lajes, apoiadas sobre os forcados, transmitindo cargas para as
  torres ou escoras.
- **Viga secundaria (barrote):** ultima peca do escoramento antes da forma
  das lajes. Serve de apoio para o compensado e transmite as cargas para as
  vigas primarias.

Catalogo de propriedades:

| Tipo | Material | E.I kgf.m2 | M adm kgf.m | Cortante adm kgf | Peso kg/m | Uso |
|---|---|---:|---:|---:|---:|---|
| VM80 | Metalica | 14965 | 212 | - | 6.41 | Secundaria, travessas, apoio de forma |
| VM130 | Metalica | 47094 | 516 | - | 9.70 | Principal, guias, vigas de distribuicao |
| VM50 | Metalica | - | ~81.6 (0.80 kN.m - catalogo do projeto/DOCX; PENDENCIA de ficha tecnica oficial) | - | variavel | Travamento de pilares (PDF p.20: uso EXCLUSIVO); laterais de vigas e regra de uso ampliado vem de resposta de engenharia |
| ALU14 | Aluminio | 20309 | 409 | 2100 (JAU VA140, perfil identico) | 4.00 | Opcao tecnica leve, primaria/secundaria |
| ALU20 | Aluminio | - | 800 | - | 6.35 | Opcao tecnica robusta |
| HT20/H20 | Madeira | 51758 | 500 | - | 5.17 | Escoramento de lajes e vigas (Orguel p.21); tambem rampas |

Verificacao normativa das VMs (NBR 15696 Anexo B.2.1): o vao admissivel e o
MENOR entre os calculos como viga isostatica e como viga continua, limitado
pelas TRES verificacoes - flexao, CORTANTE e flecha (4.3.2). O motor hoje
verifica momento e flecha; a verificacao de cortante esta pendente
(valores admissiveis do fabricante, item 4.4).

Nota de peso da ALU14: a tabela Orguel p.69 e o catalogo JAU (VA140) dizem
4.00 kg/m; a tabela de comprimentos Orguel p.21 implica ~3.82 kg/m
(22.92 kg / 6.00 m). Adotado 4.00 kg/m (duas fontes); divergencia registrada.

Referencia comparativa de outros fabricantes (nao intercambiar valores):
JAU VA165 (M 878 kgf.m, E.I 50500, cortante 3350 kgf, 6.00 kg/m, secao
165 x 127 mm - modelo distinto da ALU20, nao fundir); JAU TJ3 aco 3"
(M 250, E.I 15960, cortante 3160, 6.00 kg/m - classe da VM80, ~18% mais
resistente); JAU PT2 perfil travamento 2" (M 110, E.I 5670, cortante 1978,
4.39 kg/m - classe da VM50, com valores rastreaveis).

Comprimentos disponiveis por modelo (NOVO - Orguel p.20):

| VM 80 (mm) | VM 130 (mm) | VM 50 (mm) |
|---:|---:|---:|
| 1000 | - | 650 |
| 1550 | 1550 | 1000 |
| 2050 | 2050 | 1550 |
| 2550 | 2550 | 2050 |
| 3100 | 3100 | 2550 |
| 3600 | 3600 | 3100 |
| 4100 | 4100 | 3600 |
| - | - | 4100 |

Comprimentos disponiveis ALU14 e H20 (NOVO - Orguel p.21):

| ALU14 (mm) | H20 (mm) |
|---:|---:|
| 1500 | 1000 |
| 2000 | 1800 |
| 2500 | 2050 |
| 3000 | 2450 |
| 3500 | 2550 |
| 4000 | 2900 |
| 6000 | 3300 |
| - | 3600 |
| - | 3900 |
| - | 4500 |
| - | 4800 |
| - | 4900 |

H20: altura do perfil 200 mm. JAU VA140 (perfil identico a ALU14):
comprimentos 1500 a 4500 mm em passos de 500 mm; sarrafo embutido de
cedrinho 40 x 40 mm.

Selecao de comprimento: usar a VM cujo comprimento seja o menor maior que o
vao calculado mais a folga de apoio. Vao maximo do barrote deve respeitar
`Lmax_Bar = 4 x M_adm / P` para carga pontual no meio (vide secao 22).

Resposta de engenharia: regra geral usa VM130 como principal, VM80 como
secundaria e VM50 apenas em travamentos de pilares e laterais de vigas.
ALU14 e H20 podem ser usadas como principal/secundaria conforme projeto e
estoque.

### 13.4 Paineis e Diagonais de Torre (NOVO - p.13)

Paineis disponiveis (componente lateral da torre, dimensao = largura x altura):

| Largura (mm) | Altura (mm) |
|---:|---:|
| 1000 | 1000 |
| 1000 | 1250 |
| 1000 | 1500 |
| 1540 | 1000 |
| 1540 | 1250 |
| 1540 | 1500 |

Diagonal em X com dois furos (componente A/B):

| Modelo | A (menor) mm | B (maior) mm |
|---:|---:|---:|
| 1 | 1200 | 1410 |
| 2 | 1680 | 1840 |
| 3 | 2150 | 2280 |

Diagonal em X (DX) - travamento da torre:

| Modelo | Comprimento mm |
|---:|---:|
| 1 | 1200 |
| 2 | 1410 |
| 3 | 1680 |
| 4 | 1840 |
| 5 | 2150 |
| 6 | 2280 |

Selecao de DX por largura da torre e altura do painel (NOVO - Orguel
p.14-16, desenhos cotados):

| Largura da torre (cm) | Painel h = 1.00 m | Painel h = 1.50 m |
|---:|---:|---:|
| 100 | DX 1200 | DX 1410 |
| 155 | DX 1680 | DX 1840 |
| 205 | DX 2150 | DX 2280 |

Obs.: o painel de 1.25 m nao aparece pareado nos desenhos - nao inventar;
gerar pendencia se a combinacao ocorrer.

Diagonal Tubular (DT) - travamento horizontal entre torres:

| Modelo | Comprimento mm |
|---:|---:|
| 1 | 1415 |
| 2 | 1840 |
| 3 | 2180 |
| 4 | 2280 |
| 5 | 2540 |

### 13.5 Tabela de Selecao de DT por DX + Painel (NOVO - p.17)

Esta tabela e canonica para escolher o tamanho da Diagonal Tubular em funcao
da Diagonal em X (DX, em cm) e do tamanho do Painel (em cm):

| DX (cm) | Painel (cm) | DT (mm) |
|---:|---:|---:|
| 155 | 154 | 2180 |
| 155 | 100 | 1840 |
| 205 | 154 | 2540 |
| 205 | 100 | 2280 |
| 100 | 154 | 1840 |
| 100 | 100 | 1415 |

Regra de implementacao: ao montar torres, o motor deve:

1. Determinar o tamanho do painel pela altura da torre desejada.
2. Determinar o DX pelo afastamento longitudinal entre torres.
3. Olhar a tabela acima para selecionar o DT correto.
4. Verificar disponibilidade em estoque do DT escolhido.

### 13.6 Altura de Equipamento

CORRECAO IMPORTANTE (2026-06-11): o significado do `0.224 m` estava INVERTIDO
nas versoes anteriores deste manual. No exemplo Orguel p.89, `0.224 m` e a
ALTURA DA PILHA forma + vigamento, nao "ajuste de sapata + forcado":

```text
0.224 m = h_guia (VM130 = 0.130) + h_barrote (VM80 = 0.080)
        + e_compensado (14 mm = 0.014)
```

Sapata + forcado sao o RESIDUAL do ajuste (0.49 m no exemplo da laje;
0.176 m no exemplo da viga). Consequencia: 0.224 NAO e constante universal -
parametrizar como `h_pilha = h_guia + h_barrote + e_compensado` (ex.:
compensado 18 mm com VM130+VM80 -> 0.228 m; pilha Doka H20+H20 -> 0.414 m).

Para torres em laje (pe-direito piso a piso, Orguel p.88-89):

```text
H_torre = pe_direito - espessura_laje - h_pilha
```

Para escoras em laje:

```text
abertura_escora = pe_direito - espessura_laje - h_pilha
```

Para torres sob viga (Orguel p.89: (3.30 - 0.90 - 0.224) = 2.176 m):

```text
H_torre_viga = pe_direito - altura_viga - h_pilha
```

Para escoras sob viga (revisar no motor: o desconto da pilha de forma/guia
tambem se aplica quando ha guia + fundo de forma sob a viga):

```text
abertura_escora = pe_direito - altura_viga [- h_pilha quando houver guia]
```

Combinacao de paineis de torre (Orguel p.87-95): selecionar a combinacao de
paineis (1.00/1.25/1.50 m) que chegue a ate 0.49 m abaixo da altura-alvo,
com o residual absorvido por sapata ajustavel (curso 300 mm) + forcado.
Exemplo canonico: H_alvo 2.99 m -> 2 paineis (1.50 + 1.00) + 0.49 m de
ajuste. Quando o residual for menor que o curso minimo, usar sapata simples
de encaixe e deixar o ajuste no forcado ajustavel (caso da viga, residual
0.176 m).

Folga de desforma (JAU p.07/08/09/32): ao usar sapata/fuso em abertura
minima, deixar no minimo 10 cm de curso livre (rosca) em algum fuso do
conjunto para permitir a descida na desforma. Verificador novo recomendado.

Sistemas Doka: base e forcado ajustaveis de 0.07 a 0.45 m cada (TCC p.48);
modulos de torre Doka: 0.90 / 1.20 / 1.80 m (TCC p.26/38). Nao aplicar o
residual Orguel a sistemas de outros fabricantes.

### 13.7 Estabilidade Global de Torres (NOVO - 2026-06-11)

Regras consolidadas de JAU (fonte oficial brasileira) e fontes externas:

| Regra | Valor | Fonte |
|---|---|---|
| Esbeltez de torre isolada | Altura total <= 4 x a MENOR dimensao da base; acima disso, estaiamento ou contraventamento OBRIGATORIO | JAU p.04 |
| Torres agrupadas sob carga concentrada | Interligar as torres proximas com cantoneiras/barras de ligacao (300/500 mm) encaixadas no pino da trava junto com as DX | JAU p.11 |
| Torres adjacentes em linha | Interligar com DT horizontais para estabilidade global | JAU + fontes externas |
| Diagonais | Obrigatorias nas 4 faces; travamento horizontal no topo e na base | Fontes externas comparativas |
| Apoio em solo | Pranchoes/sole plates sob as sapatas; nunca apoiar direto no solo | NBR 15696 item 6.3.d + ABRASFE r04 p.4 |
| Sapata alongada (curso 400-700 mm) | Limita a torre a UMA altura de quadro (1 modulo) | JAU p.08 |
| Transpasse de viga principal sobre torre | Somente com suporte/forcado ajustavel DUPLO em todas as pernas do quadro + encunhamento com madeira | JAU p.09 |
| Gatilhos de revisao | Torre > 8 m: revisao de engenharia; > 20 m: projeto especial | Fontes externas comparativas |
| Tombamento | Fator de seguranca >= 1.5 (torres isoladas e vigas externas) | Fonte externa comparativa |
| Estaiamento de periferia | Torres de periferia devem ser estaiadas ANTES de serem utilizadas (durante a montagem) | ABRASFE r04 p.6 + Orguel p.111; ABRASFE RT003-2015 |

Itens de fontes externas devem ser confirmados com engenharia antes de
virarem bloqueio automatico; os itens JAU/NBR/ABRASFE podem virar regra.

## 14. Acessorios

| Componente | Regra |
|---|---|
| Sapata simples | Base 110 x 110 mm (Orguel); JAU sapata ajustavel base 130 x 100 mm - dimensao por fabricante |
| Sapata ajustavel | Regulagem 300 mm (curso util JAU: 40-300 mm) |
| Sapata alongada (JAU) | Curso 400-700 mm; base 168 x 150 mm; restricao: 1 modulo de quadro apenas |
| Forcado fixo simples | Altura 65 mm, abertura 85 mm |
| Forcado de ajuste simples (NOVO - p.18) | Altura 65 mm, abertura 85 mm |
| Forcado para vigas metalicas (NOVO - p.18) | Altura 65 mm, abertura 85 mm |
| Forcado fixo duplo | Altura 70 mm, abertura 205 mm |
| Forcado H20 | Altura 180 mm, abertura 170 mm |
| Forcado ajustavel duplo H20 | Regulagem haste 300 mm, altura 180 mm, abertura 170 mm |
| Suporte ajustavel duplo (JAU) | Curso 80-350 mm; comporta DUAS vigas; unico indicado para transpasse de principais em torres |
| Barra de ligacao | 300 ou 500 mm |
| Console/mao francesa | Base 540 mm, comprimento 710 mm, altura 250 mm |
| Cruzeta (JAU) | Comprimento 895 mm; alturas uteis: Escora I 2.17 m / Escora II 2.90 m |
| Tirante agulha RR (JAU) | Comprimentos 650/750/1000/1300 mm; carga admissivel 50 kN = 5000 kgf |
| Tirante 5/8" SAE 1045 (JAU) | 250 a 3000 mm (passo 250); carga admissivel 70 kN = 7000 kgf |
| Coluna de amarracao (JAU) | Tubo 42.2 mm, parede 3 mm, 0.25-6.00 m; uniao entre torres |

Fonte: Orguel p.18 + JAU p.07-09, 11, 14-15, 24, 35.

Regra de tripes (JAU pag. 70): tripe OBRIGATORIO em escora de extremidade de
viga e em transpasse de viga; dispensavel em escoras intermediarias. Regular
todas as escoras para o pe-direito ANTES da montagem (gabarito ou escora
padrao); parafusar os suportes nas escoras antes de iniciar. Regra de BOM:
n_tripes = escoras em extremidade + escoras em transpasse de linhas de viga.

Quantificacao de cruzetas: sob vigas, 1 cruzeta por escora (conjunto a cada
0.80 m, secao 10.3). A regra "4 cruzetas por torre" do catalogo do projeto e
atipica (sob torre normalmente usa-se forcado/barrote) - confirmar com
engenharia antes de manter no BOM.

## 15. Travamento

### 15.1 Pilares

| Face do pilar | Estrategia |
|---|---|
| Ate 25 cm | VM80 (ou VM50) + tirantes |
| >40 cm | VMs nos quatro lados; alternancia de travessas pode reduzir material |
| >90 cm | Adicionar VM vertical para reduzir vao entre tirantes |

Para pilares >40 cm, o travamento pode alternar travessas em dois lados para
reduzir consumo de equipamentos. Para pilares >90 cm, deve-se considerar uma
ou mais vigas metalicas na posicao vertical, diminuindo o vao entre tirantes.

Espacamento vertical entre conjuntos (CORRIGIDO 2026-06-11): NAO e fixo em
80 cm. O criterio Orguel p.64 e "vao maximo resistido pela forma" (de
madeira/compensado, vide secao 12), que decresce com a pressao lateral do
concreto (profundidade). Evidencias: pilar 25/75 usa 80/80/80/80 + 20 cm na
base (p.62); pilar 25x100 usa 34 + 7x33 + 20 cm (p.64, altura 285 cm). O
DOCX (resposta 4) confirma: "espacamento entre conjuntos definido em funcao
da forma de madeira".

Composicao do conjunto-padrao de travamento (DOCX resposta 4): 2 VM50 (ou
VM80) + 2 barras de ancoragem com porca por conjunto. BOM deterministico:
n_conjuntos = altura util / espacamento admissivel da forma.

Referencia quantitativa JAU (p.22, compensado 18 mm) - espacamento entre
tirantes decresce com a profundidade da coluna de concreto: perfil 2" de
1.23 m (topo) a 0.50 m (4 m de profundidade); perfil 3"/VJ3 de 1.70 m a
0.70 m. Confirma que "80 cm fixo" NAO e conservador para perfil 2" abaixo
de ~1.5 m de coluna. Tabelas completas no manual JAU; ligar ao calculo de
pressao da secao 23.7.

Aprumadores (JAU p.25-26): face ate 120 cm -> 3 aprumadores (2 na lateral
maior + 1 na menor); 120-180 -> 4; 180-240 -> 5; 240-300 -> 6. Lateral menor
> 50 cm usa 2. CONFLITO registrado em 23.9: exemplo Orguel 25x100 usa 6.
Regra de seguranca JAU: aprumador NAO recebe pressao lateral do concreto
(aprumador != travamento); fixacao da sapata articulada no piso e
responsabilidade do contratante.

Exemplo canonico - Travamento de pilar 25 x 100 cm (NOVO - Orguel p.64):

| Item | Codigo | Quantidade |
|---|---|---:|
| VM 80 horizontal | VM80 1550 | 16 x 1 = 16 pecas |
| Tirante curto | Tirante 650 | 16 x 1 = 16 pecas |
| VM vertical | VM 80 2550 | 2 x 1 = 2 pecas |
| Tirante longo | Tirante 1000 | 3 x 1 = 3 pecas |
| Aprumador | Aprumador de pilar | 6 x 1 = 6 pecas |

Exemplo canonico - Travamento de pilar 40 x 70 cm (Orguel p.63):

| Item | Codigo | Quantidade |
|---|---|---:|
| VM 50 ou VM 80 lateral | VM50 1000 | 20 x (CORRIGIDO 2026-06-11: o PDF diz 20x, 5 niveis x 4 lados; a versao anterior registrava 10x) |
| Tirante | Tirante 1000 | 10 x |
| Tirante | Tirante 1500 | 10 x |

Exemplo canonico - Travamento de pilar 25 x 75 cm (NOVO - Orguel p.62):

| Item | Codigo | Quantidade |
|---|---|---:|
| VM 80 horizontal | VM80 1550 | 10 x |
| Tirante curto | Tirante 650 | 10 x |

Espacamentos verticais do 25/75: 80/80/80/80 cm + 20 cm na base. Materiais
de travamento (Orguel p.62): tirantes, tensores, cantoneiras de fixacao,
aprumadores, sapatas articuladas e VMs (VM50 ou VM80).

Fonte: Orguel p.62-64.

### 15.2 Laterais de Vigas

Travamento lateral e necessario para paineis laterais >60 cm ou quando o
cliente exigir.

Quantidade de tirantes por VM:

| VM mm | Tirantes |
|---:|---:|
| 1000 | 2 |
| 1550 | 2 |
| 2050 | 3 |
| 2550 | 3 |
| 3100 | 4 |
| 3600 | 5 |
| 4100 | 5 |

Restricao de espacamento (Orguel p.65 + DOCX resposta 4): o espacamento
entre tirantes/barras de ancoragem e determinado pelo comprimento da VM OU
pelo vao maximo de 1.00 m - o que for MENOR. Alvo pratico: 0.80 a 1.00 m
entre barras de ancoragem.

Formula para tirante:

```text
tirante = 2 x 5.5 + 2 x 8.0 + 2 x e + L
```

Onde `e` e a espessura da forma e `L` e a largura da viga. Os 5.5 cm sao o
minimo de barra livre (rosca) exigido pelas porcas de cada lado; 8.0 cm e a
largura da VM80. Fonte: Orguel p.66.

Capacidades de tirantes (referencia JAU p.24, por fabricante): tirante
agulha RR = 50 kN; tirante 5/8" SAE 1045 = 70 kN. Permite verificacao de
tracao no tirante (carga = pressao lateral x area de influencia do tirante).

### 15.3 Fundo de Vigas

Tirantes e cantoneiras devem ficar entre cruzetas ou entre barrotes.
Quantidade: numero de tirantes igual ao numero de cruzetas ou barrotes no
fundo da viga. Fonte: Orguel p.67.

Composicao do conjunto (DOCX resposta 4): 2 cantoneiras de fixacao + 1 barra
de ancoragem com porca, por cruzeta (viga com escoras) ou por barrote/
secundaria (viga com torres). Sem essa composicao o BOM sai incompleto em
cantoneiras e porcas.

### 15.4 Formas Verticais de Paredes e Muros (NOVO - 2026-06-11)

Subsistema registrado para roteamento; o motor deve trata-lo como caso
especial ate implementacao propria:

- Tirantes passantes (tie-rods/she-bolts/dywidag) dimensionados pela pressao
  lateral do concreto (Anexo D, secao 23.7): espacamento = f(P, capacidade
  do tirante - vide capacidades JAU na secao 15.2).
- Gravatas/travessas distribuem a carga dos tirantes; espacadores garantem
  a espessura.
- Face unica (muro contra terreno): escoras inclinadas a 45-60 graus
  apoiadas no piso + ancoragens.
- NOTA ANTI-ERRO: a espessura da parede NAO altera a pressao do concreto;
  a variavel de ajuste e o espacamento de tirantes.
- Desforma de formas verticais: referencia usual fck >= 15 MPa (NBR 6118,
  fonte de research); confirmar com o calculista (pendencia obrigatoria).
- Aberturas provisorias proximas ao fundo para limpeza em formas estreitas
  e altas (NBR 15696 item 6.4 + ABRASFE r04).
- Valas/trincheiras (NR-18: obrigatorio escorar > 1.25 m em solo instavel e
  > 2.0 m sempre): FORA DE ESCOPO do Escora.AI - bloquear e enviar para
  revisao de engenharia.

## 16. Reescoramento

Reescoramento e subsistema proprio. Nao misturar com o escoramento inicial
sem identificar etapa, carga considerada e nivel ativado.

Conceito (NBR 15696 - Orguel p.53):

- Apos a concretagem, as escoras sao removidas ou liberadas de tensao.
- A laje precisa ter resistencia suficiente para suportar seu peso proprio.
- Ao ser ativada (desforma), a laje deforma e passa a transferir cargas dos
  niveis superiores.
- Se nao houver desforma/liberacao das tensoes, a carga total e transferida
  para a fundacao (ou demais lajes inferiores), pois a 1a laje nao foi
  ativada - configuracao que pode chegar a 200% de sobrecarga.

Reescoramento remanescente (Orguel p.54-55):

1. Uma tira de chapa compensada com aproximadamente 15 cm de largura e
   inserida durante a montagem do sistema.
2. Escoras intermediarias (que serao o escoramento remanescente) sao
   posicionadas sob essa tira.
3. Realiza-se a desforma do sistema de escoramento para liberacao do
   pavimento superior, restando a tira de chapa compensada e as escoras
   remanescentes.

Terminologia normativa (NBR 15696 via Orguel p.52): desforma COM ativacao da
laje = "Reescoramento"; desforma SEM ativacao da laje = "Escoramento
Remanescente" (reescoramento parcial). Usar os termos corretos nas notas de
projeto.

Regras quantitativas:

- concreto precisa de aproximadamente 28 dias para cura total;
- desforma/liberacao ativa a laje e permite redistribuicao de carga;
- sem desforma/liberacao a carga e transferida 200% para a fundacao e e
  pratica ruim;
- reescoramento remanescente deixa uma faixa de compensado de 15 cm;
- vao livre maximo no reescoramento: 2.00 m - "mesmo que as cargas
  calculadas permitam, nao se deve ultrapassar, EXCETO se aprovado pelo
  calculista da obra" (Orguel p.59);
- reescoramento 50% considera metade da carga;
- reescoramento 25% considera um quarto da carga;
- remanescente durante concretagem superior considera carga plena + niveis
  superiores;
- OBRIGATORIO colocar no projeto notas de reescoramento com a carga e a
  parcela considerada, validadas pelo contratante (Orguel p.59);
- em lajes NERVURADAS, posicionar reescoras sob as INTERSECOES de nervuras;
  densidade de referencia ~1 suporte por 1.5 m2 (fonte externa comparativa).

Processo de remocao do reescoramento (NOVO - Orguel p.56-57):

- Vao simples: aliviar as escoras CENTRAIS em direcao aos apoios; voltar as
  escoras centrais retirando-as definitivamente ate os apoios.
- Lajes continuas/multiplos vaos: aliviar as escoras das EXTREMIDADES para o
  apoio; voltar as escoras subsequentes as extremidades, retirando-as
  definitivamente ate os apoios.
- Nunca remover em ordem que carregue subitamente um ponto central.

Pratica de montagem (Orguel p.58): quando o pe-direito permitir, usar escoras
SEM acessorios no reescoramento; quando nao permitir, consultar o cliente
para definir se o material fica totalmente preso ou se guias/barrotes sao
retirados para reaproveitamento.

Conteudo obrigatorio do projeto de reescoramento (NBR 15696 Anexo C.2/C.3):
peso proprio da laje; dimensoes dos panos; ciclo de concretagem dos
pavimentos posteriores; sobrecarga de utilizacao evolutiva; sobrecarga de
uso e cargas permanentes do calculo definitivo; resistencia e modulo de
elasticidade nos prazos de retirada e aos 28 dias; deformacao vertical por
carga aplicada nas escoras/torres; distribuicao e posicionamento dos
elementos; verificacao das capacidades dos pavimentos inferiores nas
diversas idades e dos superiores na retirada dos remanescentes; processo de
remocao considerando o funcionamento global. O projeto de reescoramento e
incumbencia do responsavel tecnico pela execucao.

Fonte: Orguel p.50-60 + NBR 15696 Anexo C (texto oficial).

## 17. Regras Operacionais de Montagem

| ID | Regra | Fonte |
|---|---|---|
| OP-001 | Apoiar em base firme; preparo da base e responsabilidade do cliente | Orguel p.97 |
| OP-002 | Escoras e torres devem estar aprumadas | Orguel p.98 |
| OP-003 | Topo e base devem ser ajustados sem folgas | Orguel p.99 |
| OP-004 | Guias devem ser apoiadas e cunhadas corretamente | Orguel p.100 |
| OP-005 | Madeiramento do fundo da forma deve seguir projeto | Orguel p.101 |
| OP-006 | Tempo de cura e responsabilidade do cliente/calculista | Orguel p.102 |
| OP-007 | Equipamentos devem ser inspecionados antes do uso | Orguel p.103 |
| OP-008 | Nao alterar projeto sem comunicacao tecnica | Orguel p.104 |
| OP-009 | Travamento e amarracao das formas sao responsabilidade do cliente | Orguel p.104 |
| OP-010 | Forcados nao podem ser locados em balanco; suporte do forcado em viga deve estar sempre apoiado | Orguel p.109 |
| OP-011 | Vigas continuas com 3 apoios sobrecarregam apoio central em 25% (10/8 qL); extremos = 3/8 qL | Orguel p.109 |
| OP-012 | Vigas externas: largura <=30 cm, altura <=60 cm, comprimento <=3 m podem usar escora+cruzeta; acima disso, torres | Orguel p.111 |
| OP-013 | Vigas externas com console: altura >=70 cm aparece no detalhe de console; confirmar obrigatoriedade | Orguel p.111 |
| OP-014 | Vigas internas <=6 m, ate 40 x 70 cm: escoras com cruzetas | Orguel p.112 |
| OP-015 | Vigas internas 6-10 m, ate 40 x 70 cm: escoras + torre central | Orguel p.112 |
| OP-016 | Vigas internas >10 m: torres + escoras (pode mesclar) | Orguel p.113 |
| OP-017 | Vigas externas perifericas precisam ser estaiadas para evitar tombamento | Orguel p.111 |
| OP-018 | Problemas de montagem devem ser levados para revisao conjunta com engenharia | Orguel p.104 |
| OP-019 | Em lajes, suporte de forcado deve ficar dentro da area escorada, apoiado por baixo | Orguel p.108 |
| OP-020 | Escoramento ou forma NUNCA apoiados diretamente no solo; usar lastro, piso de concreto ou pranchoes | NBR 15696 item 6.3.d + ABRASFE r04 p.4 |
| OP-021 | Tubulacoes de bombeamento de concreto NUNCA fixadas ao escoramento ou as formas; fixar aos pilares ja concretados | NBR 15696 item 6.4 + ABRASFE r04 p.13 |
| OP-022 | Plataforma de trabalho: largura minima 60 cm; PROIBIDO usar para estocagem de materiais (ex: aco da armacao) | ABRASFE r04 p.10 |
| OP-023 | Inspecao pre-concretagem obrigatoria: dimensoes, nivelamento e prumo das formas (tolerancias NBR 14931 item 9.2.4) e posicao/condicao dos escoramentos | NBR 15696 item 6.4 |
| OP-024 | Evitar acumulo de concreto sobre formas e escoramento (nao ultrapassar sobrecargas de projeto) | NBR 15696 item 6.4 + ABRASFE r04 p.13 |
| OP-025 | Formas absorventes: molhar ate saturacao antes da concretagem, com furos para escoamento (salvo concreto aparente com especificacao contraria) | NBR 15696 item 6.4 |
| OP-026 | Formas de paredes/pilares/vigas estreitas e altas: deixar aberturas provisorias proximas ao fundo para limpeza | NBR 15696 item 6.4 |
| OP-027 | Desmoldante: aplicar exclusivamente na forma ANTES da colocacao da armadura | NBR 15696 item 6.3.k + ABRASFE r04 p.12 |
| OP-028 | Folga de desforma: deixar >= 10 cm de curso livre (rosca) em algum fuso do conjunto sapata/forcado | JAU p.07/32 |
| OP-029 | Checar em obra se a abertura real da escora coincide com a do projeto (desniveis de piso alteram a abertura e a capacidade) | JAU p.12 |
| OP-030 | Concreto protendido: remocao de formas/escoramento somente conforme programacao do projeto estrutural | NBR 15696 item 6.5 |
| OP-031 | Tempo de retirada nao pode impedir a livre movimentacao de juntas de retracao/dilatacao e articulacoes | NBR 15696 item 6.5 |
| OP-032 | Responsavel tecnico deve acompanhar flechas reais vs plano de desforma e reportar diferencas ao projetista | NBR 15696 item 6.5 + ABRASFE r04 p.15 |
| OP-033 | Contraflechas de vigas (inclusive trelicadas) devem ser indicadas nos desenhos de projeto | ABRASFE r04 p.5 |
| OP-034 | Concentracao de componentes e furos em uma regiao da estrutura deve ser verificada pelo projetista estrutural | NBR 15696 item 6.3.g |
| OP-035 | Evitar formas perdidas; quando inevitaveis, verificar durabilidade, compatibilidade, estabilidade e ancoragem | NBR 15696 itens 6.3.j |

Essas regras devem aparecer como notas padrao nos relatorios.

## 18. Validacao por Consumo e Envelope

Pelas respostas dos engenheiros, as taxas usuais em aplicacoes comuns giram em
torno de:

- 12 a 16 kg/m3 de equipamento por volume de concreto;
- utilizacao de torres em estruturas leves: 60% a 80%;
- em vigas, a utilizacao de torres pode ser menor.

DEFINICAO DA METRICA (pendencia esclarecida em 2026-06-11): os dados dos 4
projetos do TCC UTFPR (32-48 kg de equipamento por m2 de laje) so sao
compativeis com o envelope 12-16 kg/m3 se a metrica for por m3 de VOLUME
ESCORADO (area x pe-direito), nao por m3 de concreto da laje (que daria
~240 kg/m3). Confirmar a definicao com engenharia antes de calibrar alertas.

Envelope empirico de fracao de torres em escoramento misto (12 projetos
executivos Orguel medidos em 2026-04-07; nivel 8 da hierarquia):

- vigas mistas: 29% a 44% de torres;
- lajes mistas: 13% a 22% de torres.

Fracao fora do envelope sem justificativa estrutural registrada -> alerta.

O Escora.AI deve emitir alerta quando:

- kg/m3 < 12 ou > 16;
- utilizacao de escora > 100%;
- utilizacao de torre fora do envelope esperado sem justificativa;
- quantidade de torres em pe-direito baixo indicar vies de estoque Orguel;
- laje grande/espessa abaixo de 3.50 m virar misto sem falha de capacidade.

## 19. Simbologia e Saida

Simbologia desejada no DXF:

- escora telescopica: simbolo pontual simples, padrao definido no projeto;
- torre: simbolo de torre, preferencialmente quadrado/duplo;
- vigas metalicas: linhas paralelas ou blocos com etiqueta VM80, VM130, VM50;
- cruzetas e forcados: quantificar no BOM, desenhar quando necessario;
- regioes de revisao: hatch ou marcador especifico;
- cotas sempre em relacao a estrutura concretada, como pilar ou parede.

Fonte para cotagem: Orguel p.23.

### 19.1 Casos Especiais

As paginas 116-121 do manual Orguel indicam casos fora da cadeia automatica
padrao. O Escora.AI deve detectar e sinalizar revisao obrigatoria quando
aparecerem:

| Caso | Indicacao operacional |
|---|---|
| Lajes nervuradas especiais | Usar rota Mecaner ou revisao de engenharia |
| Escoramento com ALU14 | Opcao tecnica leve; verificar estoque e flecha |
| Grandes alturas | Acima de 10 m, incluir peso proprio do escoramento, vento e projeto especial |
| Escoramento aereo para passagens | Fora do automatico; exige estudo de estabilidade e interferencias |
| H20 para rampas | Tratar inclinacao/rampa como caso especial |
| Vao livre > 15 m | Cimbramento pesado; projeto especial com revisao |
| OAE (pontes, viadutos) | Fora do automatico; NBR 7187 exige documentacao propria, cargas 15-50+ kN/m2 e controle de contraflecha |
| Valas, trincheiras e contencoes | Fora de escopo (NR-18); bloquear e enviar para engenharia |
| Concreto autoadensavel (CAA) | Pressao hidrostatica plena nas formas verticais (Anexo D 2009); revisao obrigatoria |
| Projetos especiais | Bloquear saida automatica final e pedir engenharia |

Esses casos podem gerar proposta ou pre-dimensionamento, mas nao devem sair
como projeto executivo automatico sem revisao.

## 20. Checklist de Saida

Antes de liberar um projeto, verificar:

- sistema estrutural foi identificado e registrado (secao 5.1), com bloqueio
  para sistemas fora de escopo;
- pe-direito foi extraido ou default foi sinalizado;
- espessura de laje foi extraida ou default foi sinalizado;
- carga distribuida usa 2.0 kN/m2, nao 1.5 kN/m2;
- carga minima de 4.0 kN/m2 foi respeitada;
- apoio central de viga continua recebeu +25%;
- nenhum apoio ficou dentro da zona de pilar;
- nenhum ponto saiu do poligono de laje;
- pe-direito baixo nao recebeu torre por heuristica de area apenas;
- `H >= 4.50 m` nao recebeu escora telescopica comum como suporte principal
  quando nao houver modelo estendido cadastrado;
- emendas de compensado caem em eixo de barrote, com +1 barrote por emenda;
- VM escolhida passa por momento, flecha E cortante (NBR 15696 Anexo B);
- folga de desforma >= 10 cm de curso livre em algum fuso (OP-028);
- havendo bomba de concreto, efeito dinamico somado ao esforco de 5%;
- tripes contabilizados em extremidades e transpasses de viga;
- BOM inclui sapatas, forcados, cruzetas, diagonais, barras e travamentos;
- relatorio mostra tensoes de apoio;
- relatorio inclui disclaimer de responsabilidade;
- saida possui lista de pendencias para engenharia.

## 21. Pendencias de Implementacao no Escora.AI

1. Alterar a regra de baixo pe-direito do motor de `<= 3.10 m` para
   `<= 3.50 m`, com bloqueio de torres automaticas por area/espessura nessa
   faixa.
2. Corrigir a sobrecarga default de trabalho para `2.0 kN/m2` quando ainda
   houver `1.5 kN/m2` como carga distribuida.
3. Separar `plataforma de trabalho` como carga local, aplicada apenas quando
   houver passarela/plataforma modelada.
4. Parametrizar a faixa `4.00 m <= H < 4.50 m` como alerta de torre
   facultativa, nao como obrigacao.
5. Aplicar `H >= 4.50 m` como bloqueio CONDICIONAL para escoras telescopicas:
   bloqueio absoluto somente quando o catalogo da locadora nao possuir
   modelo estendido (>4.50 m) que cubra a abertura calculada com capacidade
   adequada. Se houver, permitir selecao com alerta de faixa alta e
   verificacao reforcada de estabilidade.
6. Implementar verificador de emendas de compensado em eixo de barrote.
7. Implementar seletor de DT/diagonal de torre pela tabela Orguel p.17
   (secao 13.5).
8. Exigir fonte (`Source`) em cada valor numerico gerado.
9. Implementar catalogo completo de comprimentos VM80/VM130/VM50
   (secao 13.3).
10. Implementar tabela ESC Junior como modelo alternativo (somente venda),
    nao como default de locacao (secao 13.1).
11. Corrigir interpretacao da curva de decrescimo de torre - valores sao em
    kgf por montante, nao kN por torre (secao 13.2).
12. Implementar verificador de tirantes em travamento de pilares conforme
    secao do pilar (secao 15.1 - exemplos 25x100 e 40x70).
13. Implementar formulas de calculo secoes 22.2-22.5 (vao maximo de barrote,
    momento da guia, selecao de escora por capacidade).
14. Implementar limites de flecha por faixa de vao (secao 22.3 - L/400, L/415,
    L/423, L/429).
15. Criar testes de regressao para:
    - laje 3.20 m e grande area continua usando escoras, nao torres;
    - laje 3.80 m com ESC450 e alerta;
    - laje 4.20 m com ESC450 possivel e torre facultativa;
    - laje 4.50 m bloqueando escora telescopica comum quando nao houver
      modelo estendido em catalogo;
    - viga interna 6-10 m com torre central;
    - viga interna >10 m com torres;
    - viga externa pequena com escora+cruzeta;
    - viga externa fora de limite com torre/estaiamento;
    - exemplo Orguel viga 30x80 com q = 856.8 kgf/m (secao 22.1);
    - exemplo Orguel ALU14 laje 20 cm com Ls = 2.05 m bi-apoiada (secao 22.3);
    - travamento pilar 25x100 com BOM canonico (secao 15.1).
16. Corrigir no motor a constante 0.224 m: parametrizar como
    `h_pilha = h_guia + h_barrote + e_compensado` (secao 13.6) e aplicar o
    desconto tambem em torres/escoras sob viga.
17. Implementar verificacao de CORTANTE nas VMs (NBR 15696 Anexo B/4.4) ao
    lado de momento e flecha; usar o menor vao entre isostatico e continuo.
18. Implementar +1 barrote por linha de emenda de compensado (Orguel p.115)
    no `vm_grid_builder` e no BOM.
19. Corrigir travamento pilar 40x70: VM50 1000 = 20x (nao 10x).
20. Corrigir a atribuicao da tabela de espacamento por espessura no motor
    (nao e NBR 15696; e Lajes Martins/pre-moldadas + linha 31+ sem fonte) e
    adotar teto 1.00 x 1.00 m para macicas (secao 11.1).
21. Implementar posicionamento misto torre-a-torre (secao 9, heuristica do
    DOCX): torres como apoios de extremidade das VMs primarias, escoras
    quebrando o vao.
22. Implementar conjunto escora+cruzeta 1:1 a cada 0.80 m sob vigas
    (secao 10.3) substituindo o ratio 0.25 de estoque.
23. Implementar verificador de folga de desforma >= 10 cm (OP-028) e regra
    de tripes (secao 14).
24. Somar efeito dinamico de bomba ao esforco horizontal de 5% quando o
    parametro "bombeamento" estiver ativo (NBR 4.2.l).
25. Corrigir docstring de `tests/engine/test_vm_grid_builder.py:305-310`:
    o painel de 217 m2 e o PROJETO 1 do TCC UTFPR (nao o Projeto 2); os
    "245/450 mm" sao comprimentos de vigas H20 Eco (2.45/4.50 m), nao
    espacamentos; espacamento real executado = 48.8 cm.
26. Implementar esbeltez 4:1 e interligacao de torres (secao 13.7).
27. Registrar gamma_m = 1.5 como minoracao de resistencia no motor (hoje o
    GAMMA_F=1.4 majora acoes - correto - mas a checagem de escora/torre deve
    usar Rd = Rk/1.5 alem do >= 2.0 sobre ruptura do Anexo A).
28. Implementar o classificador de SISTEMA ESTRUTURAL como passo zero do
    pipeline (secao 5.1): deteccao por texto e geometria, roteamento
    (completo / parcial / caso especial / bloqueio), registro no relatorio
    com score de confianca, e testes para alvenaria estrutural, metalica/
    steel deck e sistemas pesados.

## 22. Metodologia de Calculo (Exemplos Canonicos Orguel)

### 22.1 Carga Linear em Viga de Concreto (NOVO - p.71)

Exemplo: viga 30 x 80 cm com peso especifico 2550 kgf/m3 e sobrecarga
204 kgf/m2.

```text
q_viga = 0.30 m x 0.80 m x 2550 kgf/m3 = 612 kgf/m
       + (204 kgf/m2 x 0.30 m sobrecarga de trabalho) = 612 + 61.2 = 673.2 kgf/m
```

Para a parcela da laje carregando o escoramento da viga:

```text
q_laje = (0.10 m x 2550 kgf/m3) + 204 kgf/m2 = 459 kgf/m2
       x 0.40 m = 183.6 kgf/m
```

Total: `q_total = 673.2 + 183.6 = 856.8 kgf/m`

Nota: para vigas de periferia, considerar adicionalmente a projecao da
plataforma externa com sobrecarga de 1.5 kN/m2, multiplicada pela largura
dessa plataforma.

### 22.2 Vao Maximo do Barrote por Momento (NOVO - p.72)

Para carga concentrada P no meio do vao L, momento maximo:

```text
M_max = (P x L) / 4
L_max_Bar = (4 x M_adm) / P
```

Derivacao do P (Orguel p.72): P = q x L_influencia, onde L_influencia =
(L1 + L2)/2 e a media dos vaos adjacentes do fundo de viga. No exemplo,
L_influencia = 0.49 m (vao maximo adotado para o fundo de viga) e
q = 856.7 kgf/m, logo P = 856.7 x 0.49 = 419.8 kgf.

Exemplo VM80 com M_adm = 212 kgf.m e P = 419.8 kgf:

```text
L_max_VM80 = (4 x 212) / 419.8 = 2.02 m
```

### 22.3 Vao Maximo de Viga Secundaria por Momento e Flecha (NOVO - p.81-82)

Para carga distribuida q em viga bi-apoiada, vao maximo:

```text
L_max(MOMENTO) = sqrt(8 x M_adm / q)
L_max(FLECHA)  = (384 x E.I / (5 x q x 415))^(1/3)
```

Onde 415 e o limite de relacao L/415 para flecha admissivel.

Limites de flecha admissivel adotados pela Orguel:

| Vao L | Flecha L/x |
|---|---|
| L <= 2.00 m | L/400 |
| 2.00 m < L <= 2.50 m | L/415 |
| 2.50 m < L <= 2.75 m | L/423 |
| 2.75 m < L <= 3.00 m | L/429 |

Tres criterios de flecha coexistem (conflito registrado em 23.9):

| Criterio | Formula | Status |
|---|---|---|
| NBR 15696 item 4.3.2 | u_lim = 1 + L/500 (mm), com peso proprio + 1.0 kN/m2 SEM majoracao | NORMATIVO |
| Orguel (tabela acima) | L/400 a L/429, escalonado por vao | Default do Escora.AI (mais restritivo em vaos longos) |
| ABRASFE r04 p.11 | L/400 para qualquer vao | Alternativa documentada (menos conservadora que Orguel acima de 2.00 m) |

Exemplo ALU14 (M_adm=409 kgf.m, E.I=20309 kgf.m2), laje 20 cm, q=435.54 kgf/m:

```text
L_max(MOMENTO) bi-apoiada = sqrt(8 x 409 / 435.54) = 2.74 m
L_max(FLECHA)  bi-apoiada = ((384 x 20309) / (5 x 435.54 x 415))^(1/3) = 2.05 m
```

Adotar o menor: `Ls = 2.05 m`.

Para 3 ou mais apoios (vigas continuas), recalcular com q = 0.61 x 714:

```text
L_max(MOMENTO) 3+ apoios = sqrt(10 x 409 / 435.54) = 3.06 m
L_max(FLECHA)  3+ apoios = ((581 x 20309) / (4 x 435.54 x 415))^(1/3) = 2.53 m
```

Adotar `Ls = 2.05 m` se a viga for continua mas restritiva, ou usar valor
maior se passar nas verificacoes. ATENCAO: vigas continuas com 3 apoios
sobrecarregam o apoio central em 25%, e o momento negativo pode ditar a
verificacao - sem acrescimo de 25% no momento positivo entre apoios.

### 22.4 Selecao de Escora por Capacidade (NOVO - p.92-93)

Metodologia para escora sob viga ou em area de influencia da laje:

1. Calcular a carga distribuida `q` da laje (peso proprio + sobrecarga).
2. Calcular a area de influencia da escora (definida pelo grid).
3. Carga total na escora: `q_escora = q x area_influencia`. Metodo
   alternativo para lajes armadas em duas direcoes: trapezios a 45 graus
   para as reacoes de apoio (TCC p.40 / NBR 15696).
4. Calcular abertura da escora: `abertura = pe_direito - laje - 0.224 m`.
5. Procurar capacidade na tabela da secao 13.1 para a abertura.
6. Verificar utilizacao: `util = q_escora / capacidade_tabelada`.
7. Adotar margem de seguranca, com `util <= 80%` em situacoes nominais.

Exemplo (p.92): area de influencia = 5, laje + viga 30x80:

```text
q = 0.75 + (0.50/2 x 0.46) + (0.55/2 x 0.46) = 0.99 tf/m
q_escora = ((0.60 + 1.71) / 2) x 0.99 = 1.14 tf
q_escora / 2 escoras = 0.57 tf = 570 kgf
```

A escora ESC2000-3100 a 2.20 m de abertura (2650 kgf) tem folga de
`1 - 570/2650 = 78%` - dentro do envelope.

### 22.5 Calculo de Momento da Guia (NOVO - p.94)

Para guia bi-apoiada submetida a carga distribuida q:

```text
M = (P x L^2) / 8
```

Onde P e a carga linear (kgf/m) e L o vao (m).

Exemplo VM130 sob laje (area de influencia 7):

```text
q = 1.375 x 0.46 = 0.6325 tf/m
L = 1.65 m
M = (0.6325 x 1.65^2) / 8 = 0.215 tf.m
```

Verificacao: `M < M_adm_VM130 = 0.516 tf.m` -> OK.

Guias duplas sob VIGA (NOVO - Orguel p.94): sob viga ha DUAS guias VM130,
uma de cada lado; o momento total e dividido por 2:

```text
q = 0.75 + (0.50/2 x 0.46 + 0.55/2 x 0.46) = 0.99 tf/m
M_total = (0.99 x 2.05^2) / 8 = 0.52 tf.m
M_por_guia = 0.52 / 2 lados = 0.26 tf.m < 0.516 -> OK
```

Mesma logica para torre sob guia (Orguel p.91): a carga divide-se pelos
2 postes que recebem a guia (q = 1.863 tf / 2 postes = 0.93 tf por poste).

### 22.5.1 Exemplos Adicionais do Pavimento Canonico (NOVO - Orguel p.73-85)

Vao maximo da guia VM130 com torre no meio do vao (p.73):

```text
P = q x 0.5 = 856.7 x 0.5 = 428.35 kgf/m
L_max = sqrt(8 x 516 / 428.35) = 3.10 m
```

Carga nos postes com pilar engravatado (p.74-76; layout 50/150/100/150/50):

```text
P1 (escora pontual): L_inf = (0.50 + 1.50)/2 = 1.00 m -> P1 = 428.35 kgf
P2 (apoio central, +25% hiperestatico): L_inf = (1.50 + 1.00)/2 = 1.25 m
   P2 = 428.35 x 1.25 x 1.25 = 669.30 kgf < capacidade do poste -> OK
```

Viga principal ALU14 com secundarias BI-APOIADAS (p.82; laje 20 cm,
DX 1.55 m, secundaria 2.05 m):

```text
q = (1.55 + 2.05)/2 x 714 = 1285.2 kgf/m
L_max(MOMENTO) = 1.60 m ; L_max(FLECHA, L/400) = 1.45 m -> Lp = 1.45 m
(sem acrescimo de 25% - momento negativo nao governa)
```

Viga principal ALU14 com secundarias CONTINUAS - 3 apoios (p.83): aplicar
x1.25 na carga da principal:

```text
q = (1.55 + 2.05)/2 x 1.25 x 714 = 1606.5 kgf/m
L_max(MOMENTO) = sqrt(8 x 409 / 1606.5) = 1.43 m
L_max(FLECHA)  = (384 x 20309 / (5 x 1606.5 x 400))^(1/3) = 1.34 m
-> Lp = 1.34 m. Comprimentos praticos: ALU14 3.00 m (1.34+1.0),
   4.00 m (1.0+1.34+1.0) ou 4.50 m.
```

Verificacao do poste mais carregado (p.85):

```text
Bi-apoiadas: P_max = 714 x (1.00+1.34)/2 x (2.05+1.55)/2 = 1503.7 kgf
Continuas (+25%, ou +10% conforme quantidade de apoios):
P_max = 1.25 x 1503.7 = 1879.63 kgf < 2.0 tf (capacidade do poste) -> OK
```

### 22.6 Algoritmo de Dimensionamento de Pavimento

Sequencia recomendada para o motor:

1. Definir grid de escoras/torres com afastamentos preliminares.
2. Calcular carga distribuida `q` por painel de laje (peso proprio + 204 kgf/m2).
3. Calcular area de influencia por escora.
4. Selecionar modelo de escora pela tabela da secao 13.1.
5. Verificar utilizacao <= 80%; senao, densificar grid e refazer.
6. Definir vigas secundarias (barrotes): selecionar VM por momento, flecha e
   cortante (secoes 22.2 e 22.3; cortante por valor do fabricante, Anexo B).
7. Definir vigas primarias (guias): selecionar VM por momento, flecha e
   cortante (secao 22.5); sob viga, dividir momento por 2 guias.
8. Verificar emendas de compensado em eixo de barrote.
9. Verificar tensoes de apoio na base (secao 4).
10. Gerar BOM, memoria de calculo e DXF.

## 23. Fontes Externas Complementares e Tabelas Comparativas

Esta secao consolida pesquisa em fontes externas (NBR 15696 oficial, manuais
SH, Doka, Mills, Peri, ULMA, Rohr, Lajes Martins, TCC UTFPR) para complementar
a base Orguel, sinalizar conflitos e preencher lacunas.

### 23.1 Capacidades de Escoras Telescopicas por Fabricante

Comparativo entre fabricantes para mesma abertura. Valores em kN (carga
maxima axial admissivel). `-` indica fora de faixa do equipamento.

Uso correto desta tabela: comparar ordem de grandeza e orientar cadastro de
estoque. Para dimensionar um projeto real, usar sempre a curva oficial do
modelo efetivamente locado. Nao interpolar entre fabricantes e nao aplicar
capacidade de Peri/SH/Mills/ULMA a uma escora Orguel/Mecanor.

Pesquisa externa 2026-05-27: PERI, SH, Doka, Mills e ULMA confirmam que o
mercado possui escoras/prumos estendidos e sistemas de torre acima de 4.50 m.
Isso nao altera a regra Orguel para ESC2000-3100 e ESC3000-4500: acima de
4.50 m, a selecao de escora telescopica so pode ocorrer quando houver modelo
estendido cadastrado no estoque, com curva oficial anexada.

| Abertura m | Orguel ESC2000-3100 | Orguel ESC3000-4500 | SH LIGHT | SH STANDARD Hunnebeck | SH PLUS | SH EXTRA Hunnebeck | SH SUPER | SH LUME | Peri MP250 | Peri MP350 | Peri MP480 | Peri MP625 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.80 | - | - | - | 25.0 | - | - | - | - | - | - | - | - |
| 2.00 | 32 | - | 18.0 | 25.0 | 25.0 | - | - | - | - | - | - | - |
| 2.20 | 26.5 | - | 17.0 | 25.0 | 25.0 | - | - | - | - | - | - | - |
| 2.50 | 22.5 | - | 14.0 | 22.5 | 22.5 | 25.0 | 35.0 | - | 99.3 | - | - | - |
| 3.00 | 15.5 | 21 | 9.0 | - | 15.0 | 21.5 | 26.6 | - | - | 96.0 | - | - |
| 3.10 | 15.0 | 20 | 8.0 | - | 13.5 | 20.0 | 25.0 | - | - | 96.0 | - | - |
| 3.50 | - | 16.5 | - | - | - | 14.0 | 20.0 | 68.0 | - | 96.0 | - | - |
| 4.00 | - | 12.5 | - | - | - | 8.0 | 20.0 | 58.0 | - | - | 94.0 | - |
| 4.15 | - | - | - | - | - | 6.0 | - | 55.0 | - | - | 94.0 | - |
| 4.50 | - | 7.5 | - | - | - | - | - | 45.5 | - | - | 94.0 | - |
| 4.80 | - | - | - | - | - | - | - | ~40.0 | - | - | 94.0 | - |
| 5.00 | - | - | - | - | - | - | - | 34.0 | - | - | - | - |
| 5.50 | - | - | - | - | - | - | - | 26.0 | - | - | - | - |
| 6.00 | - | - | - | - | - | - | - | 20.0 | - | - | - | 57.9 |
| 6.25 | - | - | - | - | - | - | - | - | - | - | - | 57.9 |

Conclusoes:

- Orguel ESC2000-3100 a 2.00 m (32 kN) entrega ~28% mais capacidade que a
  Standard Hunnebeck SH (25 kN) na mesma abertura.
- Faixa 3.00-4.50 m: Orguel ESC3000-4500 e mais conservadora que SH EXTRA e
  SH SUPER.
- SH LUME e PERI MP625 ja cobrem aberturas ate 6.00-6.25 m com cargas
  significativas (20-58 kN). CONFIRMA a tendencia do mercado de oferecer
  escoras estendidas acima de 4.50 m.

Escoras JAU (Manual Tecnico JAU p.12-13, lido 2026-06-11):

| Modelo | Abertura | Flauta | Corpo | Peso | Capacidade |
|---|---|---:|---:|---:|---|
| JAU Escora I | 1.70-3.10 m | 48.3 mm | 60.3 mm | 13.58 kg | NAO PUBLICADA no manual JAU |
| JAU Escora II | 2.44-4.50 m | 48.3 mm | 60.3 mm | 18.00 kg | NAO PUBLICADA no manual JAU |

O manual JAU nao traz curva de capacidade por abertura. Pela regra da secao
1, as escoras JAU so podem ser cadastradas com PENDENCIA de engenharia ate
obtencao da ficha tecnica oficial. NAO aplicar a curva Orguel (tubos e
faixas de abertura diferentes). O teto de 4.50 m do catalogo JAU confirma a
regra da secao 8 (nenhum modelo estendido).

### 23.2 Capacidades de Torres por Fabricante

| Sistema | Capacidade nominal por montante (poste) | Altura util | Observacao |
|---|---:|---:|---|
| Orguel torre padrao (modulo 1.5 m) | 20 kN modulo 1, decaindo ate 14.7 kN no modulo 20 | 1.5-30 m | Por 4 montantes -> 80 kN a 58.8 kN |
| JAU QJ3 (quadro 1537 mm) / QJ4 (quadro 990 mm) | 20 kN/poste, com a MESMA curva de decrescimo da Orguel (secao 13.2) | modulos 1.00/1.25/1.50 m | Quadros QJ-3A/B/C e QJ-4A/B/C, 11.9-18.6 kg; confirma curva de mercado comum |
| Mills TS-3A/3B/3C/TS-4 | 20 kN (~2 tf) | modular | Sistema leve modular |
| Mills Alumills (aluminio) | 140 kN (~14 tf) | 1.50-6.00 m | Sistema pesado aluminio |
| SH LTT (torre de carga) | 60-90 kN/m2 (sistema completo) | conforme projeto | Sistema modular |
| ULMA ALUPROP | ate 90 kN | ate 12 m | Aluminio, formacao de torre |
| Peri MULTIPROP MP625 | 57.9 kN por escora | 4.30-6.25 m | Pode formar torres ate 12 m |

NOTA: A capacidade Mills Alumills de 14 tf por poste e ~7x maior que a torre
Orguel padrao (2 tf por montante). Isso explica por que sistemas Alumills/Peri
sao escolhidos em obras de alta carga e pe-direito grande.

### 23.3 Espacamentos de Escoras por Sistema (Comparativo)

| Fonte | Distancia max escoras | Distancia max viga secundaria (barrote) | Distancia max viga primaria | Observacao |
|---|---|---|---|---|
| Orguel | 1.00 m (sob viga); grid livre por capacidade | multiplo de 220/244 mm (chapa) | nao especifica explicitamente | secoes 11.1 e 10.3 |
| Doka Dokaflex 1-2-4 | 1.00 m | 0.50 m | 2.00 m | Valido para lajes <= 30 cm; acima disso sai da regra 1-2-4 e exige calculo especifico (TCC p.36 - nao ha "regra de reducao" na fonte) |
| NBR 15696 (geral) | nao prescreve - depende do calculo | calculo por momento + flecha | calculo por momento + flecha | item 4.3 |
| NBR 15696 (reescoramento) | max 2.00 m x 2.00 m | - | - | Anexo C.4.b |
| Lajes Martins (pre-moldadas) | linha 1.00-1.30 m (varia c/ altura laje) | tabua 1" x 30 cm | - | Lajes pre-moldadas |
| Rohr | conforme calculo | conforme calculo | conforme calculo | Catalogo individual |
| Escoras-Metalicas (IW8) | ~1.00 m x 1.00 m | - | - | Pratica corrente |

Conclusao: a referencia operacional convergente e 1.00 m x 1.00 m para grid
de escoras em lajes macicas tipicas. Distancias maiores precisam justificativa
de calculo.

Regras Dokaflex adicionais (TCC p.37, marcador "1"): distancia maxima da
viga de BORDA = 0.50 m; transpasse MINIMO de 0.50 m das secundarias sobre as
primarias. Comprimentos usuais: primaria H20 top 3.90 m, secundaria H20 top
2.65 m. Capacidade da base/pata Doka: 30 kN (TCC p.44).

Dados empiricos dos 4 projetos do TCC UTFPR (Quadros 4/5, p.43/70):

| Projeto | Area pav. m2 | Laje | Dist. max torres | Pe-direito | kg equip./m2 laje |
|---|---:|---:|---:|---:|---:|
| 1 (Pato Branco) | 217.15 | 20 cm | 1.68 m | 2.78-2.98 m | 47.9 |
| 2 (Fco. Beltrao) | 948.41 | 20 cm | 1.88 m | 3.04 m | 32.1 |
| 3 (Dois Vizinhos) | 992.53 | 20 cm | 1.90 m | 3.04 m | 34.3 |
| 4 (Pato Branco) | 378.90 | 20 cm | 2.13 m | 3.74 m | 36.5 |

Media da distancia maxima entre torres: 1.89 m; o limite de 2.00 m e pratica
de projeto consolidada (a atribuicao do TCC a NBR 15696 e leitura frouxa do
Anexo C de reescoramento - a norma nao prescreve para escoramento inicial).
Espacamento de secundarias executado: 48.8 cm (abaixo do maximo Doka de
0.50 m). Projetos 3 e 4 sao candidatos a novos testes de regressao.

### 23.4 Espacamento de Escoras em Lajes Pre-Moldadas (Lajes Martins)

Distancia entre LINHAS de escoras (escoras perpendiculares as vigotas):

| Altura total da laje (cm) | Distancia entre linhas (m) |
|---:|---:|
| 10 a 16 | 1.30 |
| 17 a 24 | 1.20 |
| 25 a 30 | 1.10 |

Material padrao: "tabuas de 1" x 30 cm em pe, apoiadas em pontaletes"
(escoramento de madeira tradicional).

Cura: molhagem durante os 5 primeiros dias pos-concretagem.

Altura maxima de lancamento do concreto: 15 cm (Lajes Martins) vs. 20 cm
(NBR 15696 item 4.2.g). USAR 15 cm em lajes pre-moldadas como criterio
conservador.

### 23.5 Contraflecha em Lajes Pre-Moldadas (Lajes Martins)

| Vao da laje (m) | Contraflecha (cm) |
|---:|---:|
| 2.00 a 3.00 | 0.5 |
| 3.00 a 4.00 | 1.0 |
| 4.00 a 5.00 | 1.5 |
| 5.00 a 6.00 | 2.0 |

Regra NBR 6118: a contraflecha isolada nao pode causar desvio do plano maior
que L/350.

### 23.6 Fator de Carga alfa para Desforma (Manual Doka 2014, via TCC p.37)

Citacao corrigida (2026-06-11): a tabela alfa vem do "Manual de escoramento
Doka (2014)"; o "Cimbra Doka d1" e catalogo de 2015 (outra fonte do TCC).
Verificacao celula a celula em 2026-06-11: as 32 celulas de alfa e os 8
valores de EG conferem 100% com o TCC p.37 (Quadro 1).

Para verificar a resistencia minima do concreto necessaria para desforma:

```text
alfa = (EG + N_estado_construcao) / (EG + EG_projeto + N_estado_final)
```

Onde:
- EG = peso proprio = 25 kN/m3 x espessura da laje
- N_estado_construcao = sobrecarga de construcao = 1.50 kN/m2 na referencia Doka
- EG_projeto = sobrecarga de projeto = 2.00 kN/m2
- N_estado_final = sobrecarga final de uso (varia por uso)

Tabela do fator de carga alfa por espessura de laje (Doka):

| Espessura (m) | Carga permanente EG (kN/m2) | alfa (NLfinal=2.0) | alfa (NLfinal=3.0) | alfa (NLfinal=4.0) | alfa (NLfinal=5.0) |
|---:|---:|---:|---:|---:|---:|
| 0.14 | 3.50 | 0.67 | 0.59 | 0.53 | 0.48 |
| 0.16 | 4.00 | 0.69 | 0.61 | 0.55 | 0.50 |
| 0.18 | 4.50 | 0.71 | 0.63 | 0.57 | 0.52 |
| 0.20 | 5.00 | 0.72 | 0.65 | 0.59 | 0.54 |
| 0.22 | 5.50 | 0.74 | 0.67 | 0.61 | 0.56 |
| 0.25 | 6.25 | 0.76 | 0.69 | 0.63 | 0.58 |
| 0.30 | 7.50 | 0.78 | 0.72 | 0.67 | 0.62 |
| 0.35 | 8.75 | 0.80 | 0.75 | 0.69 | 0.65 |

Interpretacao: alfa representa a fracao da carga total que estara atuando no
momento da desforma. Multiplicar alfa x carga total para obter a carga real no
estado de construcao, e dimensionar a resistencia do concreto para suportar.

Status no Escora.AI: referencia auxiliar, nao criterio automatico final. Usar
somente quando o calculista/cliente fornecer resistencia do concreto, ciclo de
concretagem e sobrecargas de uso. Caso contrario, gerar pendencia.

### 23.7 Pressao do Concreto em Formas Verticais (NBR 15696 Anexo D)

Consideracoes base do Anexo D:

- Peso especifico do concreto fluido: gamma = 25 kN/m3
- Temperatura de lancamento: 25 graus C
- Endurecimento maximo: 5 h
- Compactacao: vibracao interna
- Forma estanque
- Velocidade maxima de concretagem: 7.0 m/h

Classes de consistencia (abatimento, NBR NM 67):

| Classe | Abatimento (mm) |
|---|---|
| C1 | <= 20 |
| C2 | 20 a 80 |
| C3 | 80 a 140 |
| C4 | > 140 |

Retas do diagrama D.1 (Pb em kN/m2, vb em m/h; texto oficial lido em
2026-06-11):

| Classe | Reta | Status de leitura |
|---|---|---|
| C4 ("concreto liquido") | Pb = 12 x vb + 12 | Legivel |
| C3 | Pb = 10 x vb + 13 | Legivel |
| C2 | ilegivel na copia (coeficiente menor que C3) | PENDENCIA - conferir em exemplar de alta resolucao antes de codificar |
| C1 | Pb = 3.5 x vb + 15 (primeiro digito parcialmente ilegivel) | PENDENCIA - confirmar |

Distribuicao na altura (D.4): diagrama trapezoidal - cresce linearmente de
0 ate Pb na profundidade hs (altura hidrostatica), constante ate h = t x vb
(= 5 x vb com fim de pega em 5 h). Teto absoluto: Pb <= gamma x h
(pressao hidrostatica plena).

Fatores de correcao (D.5) - cadeia completa:

| Fator | Regra | Fonte |
|---|---|---|
| Vibracao interna profunda | Se profundidade de vibracao hr > hs: Pb = 25 x hr. Vibrador externo/acoplado: pressao hidrostatica Pb = 25 x hs nas partes influenciadas | D.5.1 |
| Temperatura do concreto < 25 C | Aumentar Pb E hs em +3% por grau C abaixo de 25 C (ex.: 20 C -> x1.15) | D.5.2 |
| Temperatura > 25 C | NAO pode reduzir Pb/hs | D.5.2/D.5.3 |
| Plastificantes/incorporadores de ar | Considerar via RECLASSIFICACAO da classe de consistencia | D.5.5 |
| Retardadores de pega (Tabela D.1; valida ate 10 m de altura; interpolacao linear permitida) | C1: x1.15 (5h) / x1.45 (15h); C2: x1.25 / x1.80; C3 e C4: x1.40 / x2.15 | D.5.6 |
| Concreto autoadensavel | Pb = gamma_b x h (hidrostatica plena) durante o endurecimento | D.5.7.1 |
| Concreto leve/pesado (Tabela D.2; multiplica Pb, hs inalterado) | alfa = gamma_b/25 (ex.: 10 kN/m3 -> 0.40; 30 -> 1.20; 40 -> 1.60) | D.5.7.2 |

Validade: formas verticais com ate +-5 graus de desvio do prumo (D.1 - unica
tolerancia de prumo propria da NBR 15696). Medidas de reducao de pressao so
podem ser adotadas se garantidas (tecnologia do concreto ou da forma).

Exemplo (parede 3 m, slump 12 cm, vb = 3.9 m/h):
- Pb (25 C) = 12 x vb + 12 = 58.8 kN/m2
- Pb (20 C) = 58.8 x 1.15 = 67.6 kN/m2

ATENCAO (achado de 2026-06-11): slump 12 cm = 120 mm e classe C3, mas o
exemplo usa a reta C4 (12vb+12). Pela reta C3 (10vb+13), Pb = 52 kN/m2.
O valor 58.8 e CONSERVADOR, porem a classificacao esta trocada - manter
58.8 como envelope seguro e registrar a pendencia de conferencia da fonte
original do exemplo.

Faixa tipica de sanidade: 24-48 kN/m2 para vb de 1-3 m/h (fonte de research,
comparativa). Divergencia registrada: a research cita K2 = 1.20 plano para
retardador; o texto oficial (Tabela D.1) da 1.15-2.15 por classe e tempo -
PREVALECE o texto oficial.

### 23.8 Reescoramento - Parametros Adicionais (NBR 15696 Anexo C)

| Parametro | Valor | Fonte |
|---|---|---|
| Distancia maxima entre escoras de reescoramento | 2.0 m x 2.0 m - a norma diz "RECOMENDADAS"; vaos maiores admitidos com justificativa do projetista da estrutura | NBR 15696 C.4.b |
| Sobrecarga minima durante construcao | 1.0 kN/m2 (independentemente de valores "mais privilegiados" informados pelo cliente) | NBR 15696 C.4.a |
| Ciclo minimo de remocao ou remanejamento | 14 dias como piso normativo; reducao somente com analise, planejamento do sistema e fcj/Ec aprovados | NBR 15696 ITEM 6.5 (citacao corrigida 2026-06-11: o valor NAO esta no Anexo C) |
| Cura para uso (resistencia total) | ~28 dias | Norma geral |

Diferenciacao Rohr:
- Sobrecarga em escoramento inicial: 200 kgf/m2 (= 2.0 kN/m2, alinhado a NBR)
- Sobrecarga em reescoramento: 100 kgf/m2 (= 1.0 kN/m2, alinhado a NBR C.4.a)

### 23.9 Conflitos e Divergencias Detectados

| Item | Fonte A | Fonte B | Resolucao adotada |
|---|---|---|---|
| Altura maxima escora telescopica | Orguel ESC max 4.50 m | SH LUME 6.00 m, Peri MP625 6.25 m | Bloqueio acima de 4.50 m e CONDICIONAL ao catalogo da locadora (secao 8) |
| Espacamento maximo escoras em reescoramento | Orguel "2.00 m vao livre" | NBR 15696 "2.00 m x 2.00 m grid" | Adotar NBR (mais explicita) - grid 2.0 x 2.0 m |
| Sobrecargas 2.0 / 1.5 / 1.0 kN/m2 | Orguel: 2.0 distribuida + 1.5 plataforma local | Fontes externas: 1.5 Doka para estado de construcao; 1.0 NBR Anexo C/reescoramento | Separar por uso: 2.0 para concretagem/escoramento inicial; 1.5 apenas plataforma local ou metodo Doka; 1.0 para reescoramento/verificacao especifica |
| Capacidade da escora a 2.00 m | Orguel 32 kN | SH 25 kN, Peri 99.3 kN | Manter capacidade do catalogo da locadora; nao extrapolar Orguel para outros fabricantes |
| Altura maxima de lancamento | NBR 15696 0.20 m | Lajes Martins 0.15 m | Adotar 0.15 m em lajes pre-moldadas; 0.20 m geral |
| Material default de barrote | Doka H20 (madeira industrializada) | Orguel VM80 (metalica) | Catalogo da locadora dita; nao fixar |
| Distancia max viga primaria | Doka 2.00 m | Orguel nao explicita | Adotar 2.00 m como referencia, sempre verificar por calculo |
| Coeficientes 1.4 / 1.5 | Versao anterior deste manual: "1.5 em flambagem; 1.4 nos demais casos" | NBR 15696 oficial: gamma_Q = 1.4 majora ACOES e gamma_m = 1.5 minora RESISTENCIA de escoras/torres, SIMULTANEOS | Adotar texto oficial (corrigido na secao 3) |
| Flecha-limite | NBR 15696: 1 + L/500 (normativo) | ABRASFE r04: L/400 qualquer vao; Orguel: L/400-L/429 escalonado | Default Escora.AI = escalonado Orguel (mais restritivo em vaos longos); NBR e o criterio normativo; ABRASFE como alternativa documentada |
| Coef. seguranca escoras (fonte secundaria) | TCC p.34: >= 2.0 sobre flambagem | TCC p.44: "2.25 sobre resistencia ultima" (inconsistencia interna do TCC) | Manter >= 2.0 do Anexo A (metalicos); 2.25 vale para vigas de MADEIRA industrializada (A.2.1) |
| Espacamento de barrote (metodologia) | Orguel p.89: tabela continua 2/4 apoios | JAU p.27-28: tabela quantizada em fracoes da chapa (L/4...L/8) | Cada fabricante com sua tabela; JAU aproxima a coluna 4 apoios Orguel; quantizacao JAU garante emenda em eixo de barrote (virtude) |
| Escoras telescopicas - geometria | Orguel ESC2000-3100 (2.00-3.10 m, 42.2/50.8) e ESC3000-4500 (3.00-4.50 m, 50.8/60.3) | JAU Escora I (1.70-3.10 m, 48.3/60.3) e II (2.44-4.50 m, 48.3/60.3), SEM curva de capacidade publicada | Nunca transferir capacidade entre fabricantes; JAU exige ficha tecnica (pendencia) |
| Componentes de travamento de torre | Orguel DX 1200-2280 / DT 1415-2540 | JAU DX 1180-2326 / DTT 1500-2510 + coluna de amarracao | Mesma logica de selecao (DX + painel -> transversal); pecas NAO intercambiaveis; catalogo da locadora dita |
| Dimensoes de sapatas/forcados | Orguel: sapata 110x110, forcado simples 65/85 | JAU: sapata 130x100, alongada 168x150, suporte fixo boca 89 | Dimensao por fabricante; registrar no catalogo |
| Numero de aprumadores (pilar face ~100 cm) | Orguel exemplo 25x100: 6 | JAU p.25: minimo 3 (2+1) | Bases de contagem possivelmente diferentes; confirmar com engenharia; usar Orguel para BOM conservador |
| Espacamento vertical de conjuntos em pilar | Pratica "~80 cm" (DOCX/Orguel 25/75) | JAU p.22: decresce com profundidade (0.50-1.23 m perfil 2"); Orguel 25x100: ~33 cm | Criterio correto = vao maximo resistido pela forma (pressao lateral); 80 cm fixo NAO e conservador |
| Viga de aluminio robusta | ALU20: M 800 kgf.m, 6.35 kg/m | JAU VA165: M 878, EI 50500, 6.00 kg/m | Modelos distintos - nao fundir nem interpolar |
| Peso ALU14/VA140 | Orguel p.69 e JAU: 4.00 kg/m | Tabela de comprimentos Orguel p.21 implica 3.82 kg/m | Adotado 4.00 (duas fontes concordantes) |
| Carga de bomba de concreto | Versao anterior: 5% puro | NBR 4.2.l oficial: somar efeito dinamico da bomba aos 5% | Adotado texto oficial |
| Passo do conjunto escora+cruzeta sob viga | DOCX resposta 5 (secao 10.3): 0.80 m alvo / 1.00 m teto | 11 projetos executivos Orguel (gold standard, secao 28.8): cotas e NN 0.50-0.65 m, moda 0.50-0.60 (0.60x127 no 87845) | Default Orguel-like 0.50-0.60 m quando seguir o gold standard; 0.80/1.00 do DOCX permanece como teto do manual — projetos reais sao MAIS densos sob viga que o DOCX |
| Topologia de escoramento de laje | Manual secoes 11.1/23.3: GRID de pontos (teto operacional 1.00 x 1.00 m) | 11 projetos reais: sistema LINE-FIRST — linhas de guia (direcao+pitch por painel) e escoras ao longo da linha, passo verificado por capacidade + VM (secao 28.8) | Modo `slab_layout_mode="line_first"` implementado em paralelo (src/engine/line_first_builder.py + stage_calculate); "grid" permanece default ate validacao em producao |
| Eixo de barroteamento por pavimento | Regra de inspecao visual 2026-06-12: eixo UNICO por pavimento (voto ponderado por area, `_level_primary_axis`) | Projetos reais: direcao POR PAINEL, perpendicular ao vao menor (~50/50 H/V no mesmo pavimento); em edificio nao-ortogonal a guia acompanha o angulo de cada viga (35 angulos no 104004) | A regra de eixo unico de 2026-06-12 fica DEPRECIADA para o modo line-first (direcao por painel); permanece valida apenas no modo grid legado |

### 23.10 Lacunas Preenchidas

| Lacuna no manual original Orguel | Preenchida por | Localizacao no manual |
|---|---|---|
| Esforco horizontal para contraventamento | NBR 15696 item 4.2.l: 5% da carga vertical | secao 3 |
| Coeficientes de ponderacao especificos | NBR 15696 item 4.3.1 | secao 3 |
| Coef. seg. contra flambagem >= 2.0 | NBR 15696 Anexo A | secao 3 |
| Pressao do concreto em formas verticais | NBR 15696 Anexo D | secao 23.7 (NOVA) |
| Fator alfa para desforma | Manual Doka via TCC UTFPR | secao 23.6 (NOVA) |
| Contraflecha em lajes pre-moldadas | Lajes Martins | secao 23.5 (NOVA) |
| Espacamento de escoras em lajes pre-moldadas | Lajes Martins | secao 23.4 (NOVA) |
| Sequencia padrao de montagem | escoras-metalicas.ind.br | secao 24 (NOVA) |
| Sobrecarga de construcao para flecha | NBR 15696 item 4.3.2 (1.0 kN/m2) | secao 3 |
| Capacidades de escoras de outros fabricantes | SH, Peri, Mills, ULMA | secao 23.1 (NOVA) |
| Capacidades de torres de outros fabricantes | SH, Mills, ULMA, Peri | secao 23.2 (NOVA) |
| Significado correto do 0.224 m (pilha forma+VMs) | Releitura Orguel p.89 | secao 13.6 (CORRIGIDA) |
| Anexo D completo (retas, fatores, retardadores, CAA) | NBR 15696 texto oficial | secao 23.7 (EXPANDIDA) |
| Estabilidade global de torres (4:1, interligacao) | JAU + NBR + ABRASFE | secao 13.7 (NOVA) |
| Capacidades de tirantes (50/70 kN) | JAU p.24 | secoes 14 e 15.2 |
| Formas verticais de paredes/muros | research + NBR | secao 15.4 (NOVA) |
| Selecao de DX por torre/painel | Orguel p.14-16 | secao 13.4 |
| Regras operacionais OP-020 a OP-035 | NBR 15696 6.3/6.4/6.5 + ABRASFE r04 + JAU | secao 17 |
| Exemplos canonicos completos do pavimento (p.73-85) | Orguel | secao 22.5.1 (NOVA) |
| Tabelas JAU de espacamento de barrote por chapa | JAU p.27-28 | secao 23.11 (NOVA) |
| Madeira: kmod e fd prontos; Anexos B/E/F | NBR 15696 oficial | secao 23.12 (NOVA) |

### 23.11 Tabelas JAU de Espacamento de Vigas Secundarias (por chapa)

Fonte: Manual Tecnico JAU p.27-28. Valores em cm, ja QUANTIZADOS em fracoes
do comprimento da chapa (emenda sempre em eixo de barrote). Cargas identicas
as da tabela Orguel (2550 kgf/m3 x h + 204). Usar somente com equipamento/
criterio JAU; nao misturar com a tabela Orguel da secao 12.2.

Chapa 122 x 244 cm (fracoes: 61 = L/4; 48.8 = L/5; 40.6 = L/6; 34.8 = L/7;
30.5 = L/8):

| Laje cm | Carga kgf/m2 | 12mm | 14mm | 15mm | 17mm | 18mm | 20mm | 21mm |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8-12 | 408-510 | 48.8 | 48.8 | 61 | 61 | 61 | 61 | 61 |
| 13-20 | 536-714 | 40.6 | 40.6 | 48.8 | 61 | 61 | 61 | 61 |
| 22-25 | 765-842 | 40.6 | 40.6 | 48.8 | 48.8 | 61 | 61 | 61 |
| 28 | 918 | 40.6 | 40.6 | 48.8 | 48.8 | 48.8 | 61 | 61 |
| 30 | 969 | 34.8 | 34.8 | 48.8 | 48.8 | 48.8 | 61 | 61 |
| 35 | 1097 | 34.8 | 34.8 | 40.6 | 48.8 | 48.8 | 61 | 61 |
| 40 | 1224 | 34.8 | 34.8 | 40.6 | 48.8 | 48.8 | 48.8 | 61 |
| 50 | 1479 | 34.8 | 34.8 | 40.6 | 48.8 | 48.8 | 48.8 | 48.8 |
| 60 | 1734 | 30.5 | 30.5 | 40.6 | 40.6 | 48.8 | 48.8 | 48.8 |
| 80 | 2244 | 30.5 | 30.5 | 34.8 | 40.6 | 40.6 | 48.8 | 48.8 |
| 100 | 2754 | 30.5 | 30.5 | 34.8 | 34.8 | 40.6 | 40.6 | 48.8 |

Chapa 110 x 220 cm (fracoes: 73.3 = L/3; 55 = L/4; 44 = L/5; 36.7 = L/6;
31.4 = L/7; 27.5 = L/8):

| Laje cm | Carga kgf/m2 | 12mm | 14mm | 15mm | 17mm | 18mm | 20mm | 21mm |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 408 | 44 | 44 | 55 | 55 | 55 | 73.3 | 73.3 |
| 9-10 | 434-459 | 44 | 44 | 55 | 55 | 55 | 55 | 73.3 |
| 11-18 | 485-663 | 44 | 44 | 55 | 55 | 55 | 55 | 55 |
| 20 | 714 | 44 | 44 | 44 | 55 | 55 | 55 | 55 |
| 22-30 | 765-969 | 36.7 | 36.7 | 44 | 55 | 55 | 55 | 55 |
| 35-40 | 1097-1224 | 36.7 | 36.7 | 44 | 44 | 55 | 55 | 55 |
| 50 | 1479 | 31.4 | 31.4 | 36.7 | 44 | 44 | 55 | 55 |
| 60 | 1734 | 31.4 | 31.4 | 36.7 | 44 | 44 | 44 | 55 |
| 80 | 2244 | 31.4 | 31.4 | 36.7 | 36.7 | 44 | 44 | 44 |
| 100 | 2754 | 27.5 | 27.5 | 31.4 | 36.7 | 36.7 | 44 | 44 |

Linhas intermediarias agrupadas quando os valores coincidem; a transcricao
celula a celula completa esta no relatorio de leitura de 2026-06-11.

Tabela JAU de base dupla (p.32) - altura de viga estrutural compativel por
pilha de vigamento, em funcao da espessura da laje (cm):

| Pilha (principal + secundaria) | Alt. MIN viga (laje 10/15/20/25) | Alt. MAX viga (laje 10/15/20/25) |
|---|---|---|
| VA165 + VA140 | 52.5 / 57.5 / 62.5 / 67.5 | 72.5 / 77.5 / 82.5 / 87.5 |
| VA140 + VA140 | 50.5 / 55.5 / 60.5 / 65.5 | 70.5 / 75.5 / 80.5 / 85.5 |
| VA140 + TJ3 | 43.5 / 48.5 / 53.5 / 58.5 | 63.5 / 68.5 / 73.5 / 78.5 |

### 23.12 Conteudo Normativo Adicional (NBR 15696 oficial, lido 2026-06-11)

Madeira (item 4.3.1.1 + NBR 7190) - valores de calculo prontos para formas
(kmod,1 = 0.9 curta duracao; kmod,2 = 0.8 macica / 1.0 industrializada;
kmod,3 = 0.8; gamma_wc = 1.4 compressao, gamma_wv = 1.8 cisalhamento):

| Verificacao | Madeira macica | Madeira industrializada |
|---|---|---|
| Compressao/tracao paralela e bordas da flexao | fd = 0.411 x fck | fd = 0.514 x fck |
| Compressao perpendicular | fd = 0.103 x fck | fd = 0.129 x fck |
| Cisalhamento | fd = 0.320 x fvk | fd = 0.400 x fvk |

Anexo B (criterios de calculo): vao admissivel da viga = MENOR entre calculo
isostatico e continuo, limitado por flexao, CORTANTE e flecha; tirantes
verificados com esforco axial maximo do fabricante; ancoragem das formas
para vento com escoras de prumo (aprumadores).

Anexo E (ensaios; criterio para aceitar fichas tecnicas de fabricantes):
nivel de confianca 95%; viga ensaiada a flexao com vao 21 x h e carga
central; cortante com apoios a 50 cm; escora ensaiada na abertura maxima,
minima e duas intermediarias, ate ruptura; torre ensaiada montada com altura
minima de 6 m, carga central, ate ruptura. Exigir que curvas declaradas por
fabricantes venham de ensaio compativel com o Anexo E. (Errata da norma: os
Anexos A.2/A.3 remetem ensaios ao "Anexo C", mas o anexo de ensaios e o E.)

Anexo F (fornecedores): engenheiro incumbido, treinamento, manual tecnico,
inspecao de todas as pecas antes da entrega, catalogo com cargas admissiveis
de todos os equipamentos - base normativa para o requisito de "catalogo da
locadora cadastrado" das secoes 1 e 8.

Tolerancias: a NBR 15696 NAO fixa tolerancias numericas proprias de prumo/
nivel - remete a NBR 14931 item 9.2.4. Tolerancias proprias da 15696:
+-5 graus de prumo (validade do Anexo D) e flecha 1 + L/500 (4.3.2).

Escopo e exclusoes: a norma cobre concreto moldado in loco e NAO cobre
seguranca do trabalho (NR-18/NBR 12284). Definicao 3.4: elementos isolados
(vigas laminadas, tubos, parafusos) NAO sao "equipamento industrializado".

## 24. Cadeia de Decisao do Engenheiro (Sequencia Detalhada)

A NBR 15696 nao prescreve sequencia explicita; a sequencia abaixo consolida
boas praticas (Doka, escoras-metalicas.ind.br, ABRASFE) com a cadeia ja
implementada nos roteiros internos das secoes 5 e 9.

Uso no Escora.AI: as secoes 24.1 e 24.2 sao fluxo de engenharia e podem virar
rotina do motor. As secoes 24.3 e 24.4 sao checklists de obra/desmontagem:
devem gerar notas, pendencias e campos de confirmacao, mas nao substituir o
responsavel tecnico da obra.

### 24.1 Pre-Calculo (Engenharia)

Passo zero (antes da ordem abaixo): identificar o SISTEMA ESTRUTURAL do
projeto conforme a secao 5.1 e rotear - concreto armado segue o fluxo
completo; alvenaria estrutural segue fluxo parcial (laje sobre parede
portante); metalica/steel deck, wood/steel frame e construcao pesada seguem
caso especial ou bloqueio.

| Ordem | Passo | Saida esperada |
|---:|---|---|
| 1 | Receber projeto estrutural do calculista | Plantas, cortes, especificacoes |
| 2 | Identificar normas aplicaveis e parametros do cliente | Lista de normas, fcj_min, prazo de desforma, ciclo de concretagem |
| 3 | Levantar geometria: lajes, vigas, pilares, paredes, aberturas | Tabela de elementos a escorar |
| 4 | Identificar pe-direito, espessura de laje, sobrecargas de projeto | Parametros de carga |
| 5 | Aplicar secao 3 - cargas normativas (peso proprio + 2.0 + plataforma + vento) | Carga total por elemento |
| 6 | Verificar secao 1 - hierarquia de fontes para conflitos | Decisao por fonte mais alta |
| 7 | Aplicar secao 8 - regra de pe-direito para tipo de suporte | Telescopica vs torre vs misto |
| 8 | Aplicar secao 9 - cadeia de decisao de suporte (13 perguntas) | Suporte definido por elemento |

### 24.2 Calculo e Selecao

| Ordem | Passo | Saida esperada |
|---:|---|---|
| 9 | Calcular carga por escora/torre conforme area de influencia | q_escora em kgf |
| 10 | Selecionar modelo de escora/torre conforme secoes 13.1 e 13.2 | Modelo + abertura + capacidade |
| 11 | Verificar utilizacao alvo <= 80%; 80-100% exige alerta/revisao; >100% reprova | OK, alerta ou densificar grid |
| 12 | Selecionar vigas primarias e secundarias (secao 13.3) por momento+flecha (secao 22.3) | VM + comprimento |
| 13 | Verificar espacamento de barrotes pela espessura do compensado (secao 12) | Espacamento OK |
| 14 | Posicionar grid de escoras com recuos de borda e pilar (secao 11.1) | Grid 2D validado |
| 15 | Inserir cruzetas, forcados, sapatas, barras de ligacao | Conexoes definidas |
| 16 | Dimensionar travamento lateral de vigas (secao 15.2) e fundo de vigas (secao 15.3) | BOM de tirantes |
| 17 | Dimensionar travamento de pilares (secao 15.1) | BOM por face de pilar |
| 18 | Calcular DT/DX/Painel de torres pela tabela da secao 13.5 | Componentes de torre |
| 19 | Verificar contraventamento (5% da carga vertical - NBR 15696) | Esforco horizontal OK |
| 20 | Verificar tensao no apoio (secao 4) | OK ou redimensionar sapata |
| 21 | Definir plano de reescoramento (secao 16) e parametros da secao 23.8 | Niveis ativos e cargas |
| 22 | Calcular fator alfa para desforma (secao 23.6), quando houver dados do calculista | Resistencia minima fcj ou pendencia |
| 23 | Gerar memoria de calculo (secao 4.1) e plantas | Projeto completo |
| 24 | Listar pendencias e enviar para revisao | Aprovacao ou ajustes |

### 24.3 Montagem em Obra (Sequencia Operacional)

| Ordem | Passo | Verificacao |
|---:|---|---|
| 1 | Analise do projeto tecnico pelo mestre/encarregado | Compreensao do plano |
| 2 | Preparacao do piso (limpeza, nivelamento, sapatas se necessario) | Base regular |
| 3 | Marcacao do gabarito com linhas e cotas a partir de pilares concretados | Eixos marcados |
| 4 | Posicionamento de tripes quando houver escoras isoladas | Tripes alinhados |
| 5 | Posicionamento das escoras/torres nos pontos marcados | Aprumadas |
| 6 | Fixacao de forcados, cruzetas ou cabecais sobre os apoios | Aperto correto |
| 7 | Distribuicao das vigas primarias (sobre forcados) e pre-nivelamento | Niveis aproximados |
| 8 | Distribuicao das vigas secundarias (barrotes) sobre primarias | Niveis aproximados |
| 9 | Apoio do compensado (forma de fundo) sobre os barrotes | Emendas em eixo |
| 10 | Travamento lateral das vigas e travamento de pilares | Conforme secao 15 |
| 11 | Ajuste final de prumo, nivel e contraflecha | Tolerancias |
| 12 | Inspecao final pelo engenheiro responsavel | Liberacao para concretagem |
| 13 | Concretagem com controle de impacto de lancamento; usar 0.20 m como criterio de calculo NBR e 0.15 m em laje pre-moldada quando fabricante exigir | Sem impacto excessivo |

### 24.4 Desmontagem (Sequencia Operacional)

| Ordem | Passo | Verificacao |
|---:|---|---|
| 1 | Verificar fcj atingido (correlacao fcj/Eci - NBR 14931:2023) | >= fcj_minimo para desforma |
| 2 | Retirar primeiro os tirantes e travamentos laterais | Painel lateral pode sair |
| 3 | Aliviar escoras com descida lenta, seguindo sequencia definida no projeto | Carga transferida sem choque |
| 4 | Desmontar barrotes (vigas secundarias) | Liberar compensado |
| 5 | Desmontar guias (vigas primarias) | |
| 6 | Desmontar escoras/torres principais | |
| 7 | Manter escoras remanescentes/reescoramento conforme projeto | Grid <= 2.0 x 2.0 m |
| 8 | Limpar e armazenar equipamentos | Inventario para devolucao |
| 9 | Registrar prazo minimo de desforma/reposicionamento. Usar 14 dias como piso padrao; prazo menor exige analise do sistema, fcj/Ec e aprovacao tecnica | Pendencia se nao houver prazo aprovado |

### 24.5 Pontos de Decisao Criticos do Engenheiro

Estes sao os "pontos de ramificacao" onde o engenheiro escolhe entre
caminhos significativamente diferentes:

1. **Escolha do sistema base** (passo 7-8 pre-calculo): telescopica, torre,
   misto, sistema alternativo (Mecaner, Dokaflex, MULTIPROP, ALUPROP).
   - Criterios: pe-direito, carga, geometria, custo, prazo, estoque.

2. **Escolha do material da viga** (passo 12 calculo): metalica VM, madeira
   industrializada H20, aluminio ALU.
   - Criterios: vao requerido, peso, reutilizacao, custo.

3. **Estrategia de reescoramento** (passo 21): remanescente, 50%, 25%,
   ciclo curto.
   - Criterios: ciclo de concretagem, resistencia do concreto, peso da laje.

4. **Estrategia de travamento de viga** (passo 16): por padrao, paineis
   laterais >60 cm ou exigencia do cliente; outros casos dependem de revisao.
   - Criterios: altura do painel lateral, especificacao do cliente.

5. **Tolerancia de utilizacao** (passo 11): alvo 80%; faixa 80-100% com
   alerta e justificativa; acima de 100% reprovado.
   - Criterios: experiencia, qualidade do equipamento, criticidade da obra.

Cada um desses pontos deve gerar um item explicito no relatorio do Escora.AI
com a justificativa registrada.

### 24.6 Uso da Cadeia pelo Escora.AI

A secao 24 faz sentido como roteiro consolidado, mas deve ser aplicada em
camadas diferentes:

| Camada | Aplicacao no sistema | Comportamento esperado |
|---|---|---|
| Engenharia automatizavel | Itens 24.1 e 24.2 | Calcular, selecionar, bloquear ou gerar alerta |
| Revisao tecnica | Itens 24.5 | Exigir justificativa registrada quando houver ramificacao critica |
| Operacao de obra | Itens 24.3 e 24.4 | Emitir checklist e pendencias, sem declarar liberacao automatica |
| Dados externos | Fator alfa, prazo de desforma, catalogos nao Orguel | Usar somente com documento oficial anexado ou dado aprovado pelo calculista |

Campos que devem bloquear a emissao final quando ausentes:

- resistencia minima para desforma (`fcj_min`) ou criterio aprovado pelo
  calculista;
- ciclo de concretagem e quantidade de niveis ativos para reescoramento;
- catalogo/ficha tecnica do fabricante quando a capacidade nao for Orguel;
- confirmacao de sistema especial quando houver escora acima de 4.50 m ou torre
  fora da tabela Orguel;
- requisito especifico de laje pre-moldada quando usado limite de lancamento
  de 0.15 m, contraflecha ou linhas de escora por fabricante.

## 25. Resumo Executivo das Regras Mais Importantes

- PASSO ZERO: identificar o sistema estrutural (secao 5.1). Escopo atual:
  concreto armado (foco), alvenaria estrutural e estruturas metalicas;
  sistemas pesados/infra sao identificados e bloqueados para revisao.
- Abaixo de 3.50 m, usar escoras simples/telescopicas como padrao.
- Entre 4.00 m e 4.50 m, torres sao facultativas e devem depender de carga,
  geometria, estoque e criterio tecnico.
- A partir de 4.50 m, torres/andaimes sao a opcao default no Escora.AI;
  escoras telescopicas estendidas (>4.50 m) podem ser usadas quando
  cadastradas no catalogo da locadora.
- Sobrecarga distribuida correta e 2.0 kN/m2; 1.5 kN/m2 e plataforma local.
- Vigas externas pequenas podem ir com escora+cruzeta; vigas internas seguem
  envelope proprio de 6 m, 10 m, 40 cm e 70 cm.
- VM130 e principal, VM80 secundaria, VM50 travamento.
- Torre em pe-direito baixo deve ser excecao justificada, nao default herdado
  de estoque Orguel.
- Curva de torre: valores em kgf por montante (multiplicar por 4 para obter
  total da torre).
- Selecao de DT em torres segue tabela canonica DX + Painel (secao 13.5).
- Verificacao de viga secundaria deve ser feita por momento E por flecha
  (adotar o menor vao).
- Vigas continuas com 3 apoios: apoio central recebe 25% a mais (10/8 qL).
- Toda decisao numerica precisa ter fonte e toda saida deve ser revisavel por
  engenheiro.
- Coeficientes: gamma_Q = 1.4 majora as ACOES; gamma_m = 1.5 minora a
  RESISTENCIA de escoras/torres em compressao/flambagem - aplicados
  SIMULTANEAMENTE (NBR 15696 4.3.1/4.3.1.2; corrigido em 2026-06-11).
- O ajuste de altura 0.224 m e a pilha forma + VMs (h_guia + h_barrote +
  e_compensado), parametrizavel; sapata + forcado sao o residual.
- Sob vigas: conjunto escora + cruzeta 1:1 a cada 0.80 m; tirantes do
  travamento lateral a no maximo 1.00 m.
- VMs verificadas por momento, flecha E cortante; sob viga, momento dividido
  entre as 2 guias.
- Hiperestaticidade: +25% (3 apoios) ou +10% (mais apoios) na reacao central
  e na carga da principal com secundarias continuas.
- Torre isolada: altura <= 4x a menor dimensao da base; acima, estaiar ou
  contraventar (JAU); torres de periferia estaiadas antes do uso.
- Emenda de compensado: alem de cair em eixo de barrote, acrescenta +1
  barrote por linha de emenda.
- Coeficiente de seguranca contra flambagem: >= 2.0 sobre carga de ruptura
  ensaiada (NBR 15696 Anexo A).
- Esforco horizontal lateral: 5% da carga vertical em cada sentido principal
  (NBR 15696 item 4.2.l).
- Reescoramento: grid <= 2.0 x 2.0 m e sobrecarga minima de 1.0 kN/m2 durante
  construcao (NBR 15696 Anexo C).
- Remocao/remanejamento de escoramento: 14 dias como piso normativo padrao;
  prazo menor so com analise, fcj/Ec e aprovacao tecnica.
- Cadeia de decisao do engenheiro: pre-calculo (8 passos) -> calculo (16
  passos) -> montagem (13 passos) -> desmontagem (9 passos), conforme secao 24.
- Capacidades de escoras variam significativamente entre fabricantes (vide
  secao 23.1); usar capacidade do catalogo cadastrado, nao extrapolar Orguel.

## 26. Resolucao das Duvidas e Conflitos

Pesquisa complementar realizada em 2026-05-27 com fontes oficiais de
fabricantes, ABRASFE e nova leitura visual do PDF Orguel.

| Item | Status | Resolucao adotada no manual |
|---:|---|---|
| 1 | Resolvido | Existem escoras/prumos estendidos no mercado acima de 4.50 m (SH Lume, PERI MULTIPROP, Doka Eurex, ULMA ALUPROP). No Escora.AI, `H >= 4.50 m` continua bloqueando escora Orguel comum; liberar escora estendida somente se houver modelo e curva oficial no estoque da locadora. |
| 2 | Resolvido | Curva Orguel p.86: modulo 14 = 1590 kgf/montante. A leitura 1500 era erro visual por baixa resolucao. |
| 3 | Resolvido | Unidade da curva Orguel: kgf por montante. O eixo informa carga no montante; os valores 2000, 1900 etc. sao compativeis com 2 tf, nao com kN. A tabela da secao 13.2 converte para kN/torre depois de multiplicar por 4 montantes. |
| 4 | Resolvido | Faixa 3.50-4.50 m: manter como faixa condicional/alerta. Orguel recomenda escora ate 3.50 m e torre principalmente quando o pe-direito ultrapassa 4.50 m; entre esses limites, decidir por capacidade, estabilidade, geometria e estoque. |
| 5 | Resolvido | Compensado deve ser parametro de entrada. O mercado trabalha com 1100 x 2200 mm e 1220 x 2440 mm, alem de variacoes por fabricante. O motor nao deve assumir uma medida unica. |
| 6 | Resolvido com regra conservadora | Viga externa pequena (largura <=30 cm, altura <=60 cm, comprimento <=3 m) pode usar escora + cruzeta. Console em viga externa aparece no manual Orguel para altura >=70 cm; tratar como gatilho de revisao/sistema especial, nao como unica solucao obrigatoria se houver torre, estaiamento ou detalhe aprovado. |
| 7 | Resolvido | Regra 16 de vigas internas deve ser interpretada como envelope por OR: se `L > 10 m` OU largura `> 40 cm` OU altura `> 70 cm`, sai do envelope leve e vai para torre/sistema especial. Se 6-10 m e dimensoes <=40 x 70 cm, usar misto com torre central. Se ate 6 m e dimensoes <=40 x 70 cm, escora + cruzeta. |
| 8 | Resolvido parcialmente | Foram localizadas fontes oficiais para SH, PERI, Doka, Mills e ULMA. A tabela comparativa pode ficar como referencia de cadastro, mas dimensionamento real continua dependente da ficha do modelo efetivamente locado. |
| 9 | Resolvido | Fator alfa Doka e metodo tecnico valido para avaliar desforma/reescoramento, mas so deve ser calculado quando houver dados de resistencia do concreto, carga final, carga de construcao e aprovacao do calculista. Sem esses dados, gerar pendencia. |
| 10 | Resolvido | Ciclo de remocao/remanejamento: usar 14 dias como piso normativo padrao. Reducao abaixo disso so com analise do sistema, concreto com resistencia/deformabilidade comprovadas e aprovacao do responsavel tecnico. |
| 11 | Resolvido | Sobrecargas permanecem separadas: 2.0 kN/m2 para concretagem/escoramento inicial; 1.5 kN/m2 para plataforma local ou metodo Doka; 1.0 kN/m2 para reescoramento/verificacoes especificas do Anexo C. |

Atualizacao 2026-06-11 (releitura integral de todas as fontes + 3 manuais
novos: NBR 15696 oficial, ABRASFE r04, JAU):

| Item | Status | Resolucao |
|---:|---|---|
| 12 | Resolvido | Modulo 14 da curva de torre = 1590 kgf/montante CONFIRMADO DEFINITIVAMENTE: o manual JAU p.06 publica a mesma curva com o ponto legivel. |
| 13 | Resolvido | Unidade kgf/montante confirmada por dupla evidencia textual (Orguel p.85 "2,0 tf"; JAU p.02 "20 kN = 2000 kgf POR POSTE"). O rotulo "kN" do eixo e erro grafico dos dois manuais. |
| 14 | Resolvido | gamma 1.4/1.5: texto oficial esclarece - 1.4 majora acoes, 1.5 minora resistencia do material de escoras/torres; simultaneos (secao 3). |
| 15 | Resolvido | 0.224 m = pilha VM130 + VM80 + compensado 14 mm; sapata+forcado sao o residual (secao 13.6). |
| 16 | Pendente | Retas C1 e C2 do diagrama D.1 (Anexo D) ilegiveis na copia da norma - conferir exemplar de alta resolucao antes de codificar. |
| 17 | Pendente | Exemplo de pressao lateral usa reta C4 para slump de classe C3 - conferir fonte original do exemplo (valor atual e conservador). |
| 18 | Pendente | Obter curva de capacidade das escoras JAU I/II (nao publicada no manual JAU). |
| 19 | Pendente | Confirmar com engenharia a base de contagem de aprumadores (Orguel 6 vs JAU 3 para face ~100 cm). |
| 20 | Pendente | Definir a metrica do envelope 12-16 kg/m3 (volume escorado vs concreto - secao 18). |

Pendencias reais que ainda ficam:

1. Obter ficha tecnica Orguel original da torre para arquivar junto ao sistema,
   embora a curva do PDF ja esteja legivel em 300 dpi.
2. Cadastrar, por locadora, quais modelos estendidos existem de fato no estoque.
3. Definir no produto se fontes externas serao anexadas por obra ou cadastradas
   centralmente no catalogo de equipamentos.
4. Verificar vigencia e obter o texto da NBR 15696:2023 (revisao).
5. Obter a ABRASFE RT003-2015 (escoramento de vigas e lajes de periferia).

## 27. Fontes Externas Pesquisadas

- SH Escoras Metalicas: https://sh.com.br/wp-content/uploads/2023/02/sh-escoras-metalicas.pdf
- PERI MULTIPROP: https://www.peri.com.br/products/multiprop-aluminium-slab-props.html
- Doka Eurex top: https://www.doka.com/web/media/files/doka_floorprop_eurex_top_en.pdf
- Doka fator alfa/reescoramento: https://direct.doka.com/_ext/downloads/downloadcenter/999810914_2021_05_online.pdf
- Qualiplas compensado plastificado: https://qualiplas.com.br/en/produtos/compensado-plastificado/
- Mills Alumills: https://www.mills.com.br/formas-e-escoramentos-detalhes/Escoramento-Alumills
- ULMA ALUPROP: https://www.ulmaconstruction.pt/pt-pt/cofragens/sistemas-escoramento/prumos
- ULMA ALUPROP dados de carga: https://www.ulmaconstruction.de/de-de/schalung/stutzen-traggeruste/stutzen/deckenstutzen-aluprop
- ABRASFE resumo NBR 15696: https://abrasfe.org.br/wp-content/uploads/2015/11/norma-nbr-15696.pdf

Fontes locais adicionadas em 2026-06-11:

- ABNT NBR 15696:2009 texto oficial: `~/Downloads/nbr-15696_2009.pdf`
- ABRASFE "Manual de informacoes basicas de forma e escoramento" r04:
  `~/Downloads/manual-de-informacoes-basicas-de-forma-e-escoramento-r04.pdf`
- Manual Tecnico JAU: `~/Downloads/Manual-Tecnico-JAU.pdf`
- TCC UTFPR (Bedenaroski 2021): `~/Downloads/PB_COECI_2020_2_27.pdf`
  (identico byte a byte ao do repositorio oficial da UTFPR)

## 28. Gap Critico: Grid de Vigas Metalicas Primarias e Secundarias

### 28.1 Observacao

Em projetos Orguel reais (e de outras locadoras como Mills, SH, Peri), o
escoramento de laje SEMPRE inclui um grid completo de vigas metalicas (VMs)
no topo das escoras, com duas camadas:

1. **Vigas primarias (guias)** — geralmente VM130, apoiadas sobre forcados.
   Correm em uma direcao, ligando linhas de escoras adjacentes.
2. **Vigas secundarias (barrotes)** — geralmente VM80, perpendiculares as
   primarias. Apoiam o compensado diretamente e transmitem carga ate as
   guias.

Esse grid existe igualmente para escoras telescopicas e para torres. A
distinção é estrutural: o compensado nunca apoia diretamente nos forcados;
sempre passa pelos barrotes secundarios.

### 28.2 Estado atual do engine (2026-05-28)

| Cenario | Status |
|---|---|
| Lajes MIXED (com torres + escoras telescopicas) | Parcial. `dxf_generator.py:221-274` desenha grid ortogonal de VMs **somente entre torres**, e nao distingue primaria/secundaria. |
| Lajes 100% telescopicas | **Faltando**. Nenhuma linha de VM e desenhada. Apenas pontos de escora. |
| Vigas (estruturais) com torres | Parcial. `dxf_generator.py:154` conecta torres adjacentes sob a viga. |
| Vigas com escora simples | **Faltando**. Sem VM linha desenhada. |
| BOM completo de VMs por comprimento | **Faltando**. So entra no BOM o `distribution_beam` selecionado, sem contar quantidades reais de VM130/VM80 derivadas do grid. |

### 28.3 Impacto

- Projetos gerados pelo Escora.AI parecem incompletos em comparacao com
  projetos Orguel reais — falta a "trama" de VMs que o engenheiro espera
  ver no DXF.
- BOM subestima quantidade de VM130 e VM80 quando o grid completo nao e
  computado.
- Memoria de calculo §4.1 cita momento admissivel da VM, mas o engine nao
  comprova que o vao real de cada VM no grid foi verificado.

### 28.4 Plano de implementacao recomendado

1. ✅ **`src/engine/vm_grid_builder.py`** (IMPLEMENTADO 2026-05-28): a partir do
   grid de escoras posicionadas, gera:
   - linhas de **VM primaria** alinhadas em uma direcao principal
     (perpendicular ao lado maior do painel para minimizar vao individual);
   - linhas de **VM secundaria** perpendiculares, com espacamento
     multiplo do `seam_multiple_mm` do `PlywoodSpec` cadastrado;
   - selecao de comprimento de VM mais economico (catalogo
     `equipment.yaml:available_lengths_mm`) para cada segmento via
     `select_vm_length_mm()`;
   - calculo de momento (M = qL²/8) e flecha (5qL⁴/384EI) por segmento
     contra `moment_adm_kn_m` e flecha admissivel `1 + L/500` (manual
     §22.2-§22.5);
   - BOM agregado por modelo+comprimento via `vm_grid_bom_summary()`.
   17 testes em `tests/engine/test_vm_grid_builder.py` validam o builder
   contra geometrias UTFPR PROJETO 1 (217.15 m2 - corrigido 2026-06-11: o
   docstring do teste dizia "Projeto 2"; o Projeto 2 do TCC tem 948.41 m2.
   Alem disso, "245/450 mm" citados no teste sao COMPRIMENTOS de vigas
   H20 Eco, nao espacamentos; o espacamento executado era 48.8 cm) e
   cenarios canonicos.
2. **`src/output/dxf_generator.py`** (PENDENTE): substituir o grid
   simplificado atual por desenho derivado de `vm_grid_builder` (camadas
   `VM130_Primaria`, `VM80_Secundaria`).
3. **`src/generator/bom_generator.py`** (PENDENTE): consumir
   `vm_grid_bom_summary()` para somar quantidade real de VM por
   modelo/comprimento.
4. **`src/rules/verifiers/struct.py`** (PENDENTE): verificar momento e
   flecha de cada VM contra catalogo (`STRUCT-VM-001`, `STRUCT-VM-002`).
5. **`src/pipeline/stage_calculate.py`** (PENDENTE): chamar
   `build_vm_grid()` para cada SlabResult apos posicionar shores, e
   propagar o `VMGrid` para o CalculationResult.
6. **Testes de regressao** (PENDENTE): comparar grid gerado contra
   projeto Orguel real (84678 ou 92056) como gold standard.

### 28.5 Status de integracao (2026-05-29)

| Etapa | Modulo | Status |
|---|---|---|
| Geracao geometrica | `src/engine/vm_grid_builder.py` | ✅ Implementado + 17 testes |
| Selecao de comprimento por catalogo | `select_vm_length_mm()` | ✅ Implementado |
| Verificacao momento/flecha | `_compute_segment_load_and_moment()` | ✅ Implementado |
| BOM por modelo+comprimento | `vm_grid_bom_summary()` | ✅ Implementado |
| Integracao no pipeline | `stage_calculate.py` (slab_results.vm_grid populated) | ✅ Implementado |
| Desenho no DXF | `dxf_generator.py` (layers VM130_Primaria/VM80_Secundaria + VM_FALHA) | ✅ Implementado |
| Verificadores STRUCT-004 (M) e STRUCT-005 (flecha) | `rules/verifiers/struct.py` | ✅ Implementado + 8 testes |
| BOM final no relatorio | `bom_generator.aggregate_vm_bom/write_vm_bom_csv/aggregate_vm_summary` | ✅ Implementado + 7 testes |
| Propagacao para RuleProject | `SlabPanel.vm_grid` em `rules/project.py` | ✅ Implementado |
| Regressao com projeto real | gold-standard tests | ⏳ Pendente |

Suite atual: **460 testes passando** (445 base + 15 novos VM/STRUCT-VM/BOM).

### 28.6 Como o pipeline usa o VM grid (fluxo end-to-end)

1. `stage_calculate.run_calculation()` posiciona as escoras de cada laje.
2. Apos `validate_result`, chama `build_vm_grid()` passando os
   `ShorePoint` e o `bbox`, com `load_kn_m2 = total_load / area_m2` e
   `default_plywood_spec()` (1220 x 2440, espessura 18mm).
3. O `VMGrid` retornado e gravado em `SlabShoringResult.vm_grid`.
4. `RuleProject.from_pipeline_result()` propaga `vm_grid` para
   `SlabPanel.vm_grid`.
5. Verifiers `STRUCT-004` e `STRUCT-005` percorrem `slab_panels` e
   emitem `Violation(severity=error)` para cada segmento que falha
   momento ou flecha.
6. `dxf_generator.generate_dxf()` desenha cada segmento em camadas:
   - `VM130_Primaria` (cor 170 / amarelo) e `VM80_Secundaria` (cor 1 / vermelho)
   - `VM_FALHA` (cor 6 / magenta) quando o segmento nao passa M ou flecha
7. `bom_generator.aggregate_vm_bom()` consolida quantidade real de VMs
   por modelo+comprimento atraves de todas as lajes.

### 28.8 Padrão Gold-Standard Orguel (11 projetos, 2026-06-12)

Fonte: `docs/research/orguel_gold_standard.md` (analise de 11 projetos
executivos Orguel reais em DXF — pavimento tipo, terreo/transicao,
subsolos, cobertura, nervurada ALU14 e industrial). Regras consolidadas
que definem o modo **line-first** do engine
(`src/engine/line_first_builder.py`, flag `slab_layout_mode="line_first"`
em `stage_calculate.run_calculation` / `run_pipeline` / `process_dxf`;
default permanece `"grid"`).

Regras consolidadas:

1. **Laje e sistema de LINHAS, nao grid de pontos**: linhas de guia
   metalica (VM80 em vaos curtos; VM130 em convencional; ALU14 primaria +
   VM80 secundaria em nervurada/industrial) sobre forcados, escoras AO
   LONGO de cada linha. Barrotes de madeira por cima sao do CLIENTE
   (nota 15 Orguel) — nao se desenham nem se quantificam.
2. **Direcao da guia POR PAINEL**: perpendicular ao vao menor; ~50/50 H/V
   convivem no mesmo pavimento. Em edificio nao-ortogonal a guia acompanha
   o ANGULO da viga dominante do painel. A regra de eixo unico por
   pavimento (2026-06-12) fica DEPRECIADA para o modo line-first.
3. **Pitch entre linhas = vao_perpendicular/n**, faixa 1.10-1.80 m
   (moda global 0.95-1.35; alvo do engine <= 1.55), calculado por painel —
   nao tabelado. Verificado por capacidade da escora
   (pitch x passo <= capacidade derateada / q).
4. **Passo de escora ao longo da guia**: VM130 1.00-2.00 m com moda
   1.20-1.55 (2.00 so em laje h<=12 do 59428); VM80 1.00-1.09 m.
   Verificado por capacidade da escora E pelo vao admissivel da guia
   (M = qL2/8; flecha 5qL4/384EI <= 1 + L/500 — formulas de `vm_checks`).
5. **Extremidade da linha**: a guia corta com gap de 0 a +0.40 m da face
   da viga de concreto (moda +0.30 nos projetos novos; flush 0.00 no 59428
   e 105475). NUNCA atravessa a viga. Default do engine: 0.30 m.
6. **Emendas SEMPRE por transpasse de 0.45-0.70 m** (default 0.65; ate
   0.95 em cobertura), com escora/forcado em CADA ponta do transpasse —
   pares de escoras a ~0.70 m nas emendas, refletidos no BOM. Emenda
   topo-a-topo nao existe nos projetos reais.
7. **Sob viga**: conjunto escora+cruzeta 1:1 a cada **0.50-0.60 m**
   (cotas 50-65 cm; mais denso que os 0.80 m do DOCX — conflito registrado
   na secao 23.9). Torres sob viga a 1.35-1.60 m (cobertura) ou 1.9-2.4 m
   (terreo de pe-direito alto).
8. **Torres em laje a 2.35-2.85 m** centro-a-centro (moda 2.35-2.60),
   paineis 1.00/1.54 m, vao livre ~1.0-1.2 m, guias VM130-310/360 vencendo
   o vao entre torres.
9. **Tripes = 30% do total de escoras** (nota 17 Orguel; arredondar para
   cima), item de BOM — % negociavel (60% no 59428 a pedido do cliente).
10. **Cobertura e torre-first** (35412, 97661): malha de torres + VM130-360
    no lugar de escoras isoladas; exige viga na base da torre, tubo de
    travamento no pe da torre e 2xVM80 nas vigas perpendiculares a
    longarina.
11. Sistemas complementares observados: ALU14 primaria a 1.00 m + escora
    FFD a 2.85 m (nervuradas), Mecanflex 1.50 x 1.20 m (sacadas de
    cobertura), reescoramento dimensionado por projeto (1.0x1.25 a
    1.8x1.4 m), travamento de pilares/vigas como prancha propria.

Status de implementacao (2026-06-12): itens 1-6 e 9 implementados no modo
line-first (`line_first_builder` gera linhas, escoras, transpasses e BOM
com tripes; `stage_calculate` popula `sr.vm_grid` so com guias
role="primaria" — sem secundarias metalicas, item 1). Itens 7, 8, 10 e 11
permanecem como calibracao pendente de `beam_calculator`/`tower_selector`.

### 28.9 Perfil de Metodologia por Locadora (decisao de produto 2026-06-12)

A analise dos 11 projetos Orguel mostrou que o "line-first" sem barrotes
metalicos e a metodologia DA ORGUEL (barrotes de madeira sao fornecimento
do cliente - nota 15 do quadro padrao). Outras locadoras trabalham com
malha dupla metalica (VM130 + VM80) e sistemas Doka usam H20+H20 (regra
1-2-4 da secao 23.3). Nenhum modo e universal: a metodologia e um ATRIBUTO
DA LOCADORA, na mesma logica da hierarquia de fontes ("o catalogo da
locadora dita").

Perfil a cadastrar por locadora (junto do catalogo/inventario em
`data/locadoras.json`):

| Campo | Valores | Default | Status |
|---|---|---|---|
| `laje_layout` | `line_first` (Orguel) / `grid_vm_duplo` (malha VM130+VM80) / `doka_124` | `grid_vm_duplo` | line_first e grid implementados (flag `slab_layout_mode`); doka_124 pendente |
| `eixo_guias` | `unico_pavimento` (malha de pavimento: eixo paralelo ao maior sentido do projeto + pitch unico 1.50 m + lattice global; linhas colineares atravessando as vigas em alinhamento, pecas quebrando na face) / `por_painel` (pratica Orguel: perpendicular ao vao menor de cada painel) | `unico_pavimento` — DECISAO DO REVISOR 2026-06-12 (v8) | implementado (`floor_frame` do line-first); capacidade preservada pelo passo |
| `escoras_equidistantes` | true (L/n constante por guia continua; extras de transpasse/capitel absorvidos) / false (extras explicitos, padrao Orguel literal) | true — decisao do revisor 2026-06-12 (v7) | implementado (`_respace_line_first_shores`) |
| `desenha_barrotes` | true/false (secundarias no DXF e BOM) | true no grid; false no line_first | implementado implicitamente pelo modo |
| `barrote` | `VM80` / `H20` / `madeira_cliente` | VM80 | parcial (catalogo de vigas) |
| `passo_sob_viga_m` | 0.50-0.65 (projetos reais) / 0.80 (DOCX) | 0.80 com alerta | conflito registrado em 23.9 |
| `cobertura` | `torre_first` / `padrao` | `padrao` | torre_first pendente (28.8 item 10) |
| `tripes_fracao` | 0.30 (30% das escoras; 60% a pedido) | 0.30 | implementado no line_first |

Regras de implementacao:

1. O perfil define os DEFAULTS; o engenheiro pode sobrescrever por obra
   (override registrado no relatorio com justificativa).
2. `slab_layout_mode` do pipeline passa a ser derivado do perfil da
   locadora/branch quando nao informado explicitamente.
3. BOM, DXF (camadas), memoria de calculo e verificadores devem reagir ao
   perfil - ex.: line_first nao emite STRUCT de secundaria metalica.
4. Perfis novos (outras locadoras) exigem a mesma validacao gold-standard:
   amostra de projetos reais da empresa antes de calibrar os numeros.
