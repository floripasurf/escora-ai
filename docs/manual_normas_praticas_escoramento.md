# Manual de Normas e Praticas de Escoramento

Manual operacional para calibracao do Escora.AI na leitura, classificacao,
calculo e posicionamento de escoras, torres, vigas metalicas e acessorios de
escoramento.

Fontes usadas:

- PDF `Treinamento Tecnico Escoramento-20-11-2020.pdf`, Grupo Orguel, 123 paginas.
- DOCX `Escora_AI_Cadeia_Decisoes R.docx`, com perguntas e respostas de engenheiros.
- ABNT NBR 15696:2009 (texto oficial, via portatilandaimes.com.br) - normativo.
- ABRASFE - Apresentacao oficial da NBR 15696 (Eng. Fernando Rodrigues dos Santos).
- BEDENAROSKI, M. (2021). "Diretrizes para escoramento metalico para lajes de
  concreto moldadas in loco" - TCC UTFPR, Pato Branco/PR.
- Manual SH - Catalogo tecnico SH 2020 (5200 linhas de texto extraido).
- Manual Doka Cimbra D1 (2014), via TCC UTFPR.
- Catalogos web: Mills (TS Mills, Alumills), Peri (MULTIPROP), ULMA (ALUPROP),
  Rohr (Kibloc, ETEM, AluROHR), Lajes Martins (pre-moldadas).
- Catalogos do projeto: `catalog/equipment.yaml`,
  `data/catalogs/telescopic_shores.json`, `data/catalogs/shoring_towers.json`.
- Consolidacao previa do repositorio: `PDF_FINDINGS.md` e `AGENTS.md`.

Nota metodologica: o PDF possui camada textual em varias paginas e tambem
conteudo relevante em imagens/tabelas. As regras abaixo consolidam a extracao
de texto, a leitura visual ja registrada em `PDF_FINDINGS.md` e as respostas de
engenharia do DOCX. Valores numericos devem permanecer rastreaveis por fonte.

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
- tensao minima no solo/apoio;
- cargas admissiveis dos equipamentos utilizados.

## 3. Parametros Normativos Obrigatorios

| Parametro | Valor | Fonte |
|---|---:|---|
| Peso especifico do concreto armado | 25 kN/m3 = 2550 kgf/m3 | NBR 6120 + NBR 15696 item 4.2.1 + Orguel p.26 |
| Peso especifico do aco | 78 kN/m3 | NBR 15696 item 4.2.1 |
| Peso especifico do aluminio | 28 kN/m3 | NBR 15696 item 4.2.1 |
| Peso proprio forma + escoramento (estimativa) | ~0.5 kN/m2 | ABRASFE/NBR 15696 |
| Sobrecarga de trabalho distribuida | 2.0 kN/m2 = 204 kgf/m2 | NBR 15696 item 4.2.e + Orguel p.26 |
| Plataforma de trabalho local | 1.5 kN/m2 = 153 kgf/m2 | NBR 15696 item 4.2.k + Orguel p.26-27 |
| Carga estatica minima antes da majoracao | 4.0 kN/m2 = 408 kgf/m2 | NBR 15696 item 4.2.e + Orguel p.26 |
| Vento minimo, quando aplicavel | 0.6 kN/m2 = 61.2 kgf/m2 | NBR 6123 + NBR 15696 item 4.2.j + Orguel p.26 |
| Componente lateral adicional de vento | +5% V | Diagrama Orguel p.27 |
| Esforco horizontal lateral nas formas de laje | 5% da carga vertical aplicada (cada sentido principal) | NBR 15696 item 4.2.l (NOVO) |
| Sobrecarga em reescoramento durante construcao | minimo 1.0 kN/m2 | NBR 15696 Anexo C.4.a (NOVO) |
| Sobrecarga para verificacao de flecha | 1.0 kN/m2 | NBR 15696 item 4.3.2 (NOVO) |
| Coeficiente de ponderacao geral | gamma_f = 1.4 | NBR 15696 item 4.3.1 |
| Coeficiente de ponderacao escoras/torres (compressao/flambagem) | gamma_f = 1.5 | NBR 15696 item 4.3.1.2 (NOVO) |
| Coeficiente de ponderacao material aco (uso geral) | gamma_m = 1.1 | NBR 15696 item 4.3.1.2 (NOVO) |
| Coeficiente de seguranca contra flambagem | >= 2.0 sobre ruptura ensaiada | NBR 15696 Anexo A (NOVO) |
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
3. Classificar entidades estruturais: lajes, vigas, pilares, paredes,
   shafts, aberturas, nervuras e elementos de desenho que nao devem ser
   escorados.
4. Montar o modelo estrutural com paineis de laje, eixos de viga, apoios e
   intersecoes.
5. Calcular cargas por laje e por viga com fontes rastreaveis.
6. Decidir tipo de suporte: escora telescopica, torre, misto ou revisao de
   engenharia.
7. Selecionar modelos reais do catalogo conforme altura, capacidade, estoque
   e custo.
8. Gerar grid de escoras/torres respeitando bordas, pilares, alvenarias,
   emendas de compensado e vigas metalicas.
9. Inserir vigas principais, secundarias, barrotes, cruzetas, forcados,
   sapatas, diagonais e travamentos.
10. Calcular consumo, kg/m3, utilizacao e alertas.
11. Gerar DXF, BOM, memoria de calculo, relatorio e observacoes de montagem.
12. Bloquear ou sinalizar saida quando houver regra de erro ou pendencia
   critica.

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
| Steel deck | Texto `steel deck`, forma metalica | Caso especial; exigir revisao ou regra propria |

Para lajes pre-moldadas, o vao maximo das vigotas e dado do fabricante ou do
contratante. O sistema nao deve inventar esse vao.

### 7.1 Lajes Pre-Moldadas e Trelicadas

Regras formalizadas do manual Orguel p.33-36:

- lajes pre-moldadas comuns vencem, em geral, vaos ate 5 m entre apoios;
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
| 13 | Nenhuma regra acionada | Escora telescopica |

Observacao critica: regras de laje grande e laje espessa nao devem gerar torres
em pe-direito baixo automaticamente. Abaixo de 3.50 m, o sistema deve primeiro
tentar resolver por densificacao de escoras e verificacao de capacidade.

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
| `L > 10.00 m` ou largura > 40 cm ou altura > 70 cm | Fora do envelope leve | Torres |

Fonte: Orguel p.112-113.

### 10.3 Posicionamento em Vigas

- Escoras sob vigas: espacamento maximo 1.00 m.
- Cruzetas sob vigas: a cada 0.80 m na pratica de engenharia.
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
- colocar pelo menos uma escora no centroide quando o grid falhar.

### 11.2 Bordas, Alvenaria e Barrotes

| Situacao | Regra |
|---|---|
| Com forma lateral de parede | Primeiro barrote a 20-40 cm da borda da forma |
| Laje encostada em parede de concreto | Primeiro barrote a 5 cm da borda do concreto |
| Alvenaria estrutural | Guias/barrotes a no maximo 5 cm |
| Emenda de compensado | A emenda deve cair no eixo do barrote |
| Espacamento de barrotes | Multiplo do comprimento da chapa: 220 ou 244 mm |

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
`2 apoios / 3+ apoios`.

| Laje (cm) | Carga kgf/m2 | 12 mm | 14 mm | 15 mm | 17 mm | 18 mm | 20 mm | 21 mm |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 408 | 42/50 | 48/61 | 50/61 | 58/69 | 61/71 | 68/84 | 71/84 |
| 9 | 434 | 41/49 | 48/49 | 50/60 | 57/68 | 60/70 | 66/79 | 70/82 |
| 10 | 459 | 40/49 | 47/49 | 50/60 | 55/67 | 59/69 | 65/77 | 68/80 |
| 11 | 485 | 39/48 | 46/48 | 49/59 | 54/66 | 58/68 | 64/76 | 67/79 |
| 12 | 510 | 38/47 | 45/47 | 48/59 | 53/64 | 57/67 | 63/75 | 66/78 |
| 13 | 536 | 38/46 | 44/46 | 47/58 | 53/64 | 56/66 | 62/74 | 65/77 |
| 14 | 561 | 37/45 | 44/46 | 47/57 | 52/63 | 55/64 | 61/73 | 64/76 |
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

### 13.3 Vigas Metalicas e Perfis

Conceito (Orguel p.19):

- **Viga primaria (principal):** vigas que atuam no sentido longitudinal dos
  vaos das lajes, apoiadas sobre os forcados, transmitindo cargas para as
  torres ou escoras.
- **Viga secundaria (barrote):** ultima peca do escoramento antes da forma
  das lajes. Serve de apoio para o compensado e transmite as cargas para as
  vigas primarias.

Catalogo de propriedades:

| Tipo | Material | E.I kgf.m2 | M adm kgf.m | Peso kg/m | Uso |
|---|---|---:|---:|---:|---|
| VM80 | Metalica | 14965 | 212 | 6.41 | Secundaria, travessas, apoio de forma |
| VM130 | Metalica | 47094 | 516 | 9.70 | Principal, guias, vigas de distribuicao |
| VM50 | Metalica | - | - | variavel | Travamento de pilares e laterais de vigas |
| ALU14 | Aluminio | 20309 | 409 | 4.00 | Opcao tecnica leve, primaria/secundaria |
| ALU20 | Aluminio | - | 800 | 6.35 | Opcao tecnica robusta |
| HT20/H20 | Madeira | 51758 | 500 | 5.17 | Opcao tecnica/rampas |

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

Para torres em laje:

```text
H_torre = pe_direito - espessura_laje - 0.224 m
```

Para escoras em laje:

```text
abertura_escora = pe_direito - espessura_laje - 0.224 m
```

Para escoras sob viga:

```text
abertura_escora = pe_direito - altura_viga
```

O valor `0.224 m` representa ajuste conjunto de sapata + forcado no exemplo
Orguel p.89.

## 14. Acessorios

| Componente | Regra |
|---|---|
| Sapata simples | Base 110 x 110 mm |
| Sapata ajustavel | Regulagem 300 mm |
| Forcado fixo simples | Altura 65 mm, abertura 85 mm |
| Forcado fixo duplo | Altura 70 mm, abertura 205 mm |
| Forcado H20 | Altura 180 mm, abertura 170 mm |
| Forcado ajustavel duplo H20 | Regulagem 300 mm |
| Barra de ligacao | 300 ou 500 mm |
| Console/mao francesa | Base 540 mm, comprimento 710 mm, altura 250 mm |

Fonte: Orguel p.18.

## 15. Travamento

### 15.1 Pilares

| Face do pilar | Estrategia |
|---|---|
| Ate 25 cm | VM80 + tirantes, com espacamento vertical de cerca de 80 cm |
| >40 cm | VMs nos quatro lados; alternancia de travessas pode reduzir material |
| >90 cm | Adicionar VM vertical para reduzir vao entre tirantes |

Para pilares >40 cm, o travamento pode alternar travessas em dois lados para
reduzir consumo de equipamentos. Para pilares >90 cm, deve-se considerar uma
ou mais vigas metalicas na posicao vertical, diminuindo o vao entre tirantes.

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
| VM 50 ou VM 80 lateral | VM50 1000 | 10 x |
| Tirante | Tirante 1000 | 10 x |
| Tirante | Tirante 1500 | 10 x |

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

Formula para tirante:

```text
tirante = 2 x 5.5 + 2 x 8.0 + 2 x e + L
```

Onde `e` e a espessura da forma e `L` e a largura da viga. Fonte: Orguel p.66.

### 15.3 Fundo de Vigas

Tirantes e cantoneiras devem ficar entre cruzetas ou entre barrotes.
Quantidade: numero de tirantes igual ao numero de cruzetas ou barrotes no
fundo da viga. Fonte: Orguel p.67.

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

Regras quantitativas:

- concreto precisa de aproximadamente 28 dias para cura total;
- desforma/liberacao ativa a laje e permite redistribuicao de carga;
- sem desforma/liberacao a carga e transferida 200% para a fundacao e e
  pratica ruim;
- reescoramento remanescente deixa uma faixa de compensado de 15 cm;
- vao livre maximo no reescoramento: 2.00 m;
- reescoramento 50% considera metade da carga;
- reescoramento 25% considera um quarto da carga;
- remanescente durante concretagem superior considera carga plena + niveis
  superiores.

Fonte: Orguel p.50-60.

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

Essas regras devem aparecer como notas padrao nos relatorios.

## 18. Validacao por Consumo e Envelope

Pelas respostas dos engenheiros, as taxas usuais em aplicacoes comuns giram em
torno de:

- 12 a 16 kg/m3 de equipamento por volume de concreto;
- utilizacao de torres em estruturas leves: 60% a 80%;
- em vigas, a utilizacao de torres pode ser menor.

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
| Projetos especiais | Bloquear saida automatica final e pedir engenharia |

Esses casos podem gerar proposta ou pre-dimensionamento, mas nao devem sair
como projeto executivo automatico sem revisao.

## 20. Checklist de Saida

Antes de liberar um projeto, verificar:

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
- emendas de compensado caem em eixo de barrote;
- VM escolhida passa por momento e flecha;
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

Formula geral: flecha maxima = `1 + L/500` em mm (Orguel p.81).

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
3. Carga total na escora: `q_escora = q x area_influencia`.
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

### 22.6 Algoritmo de Dimensionamento de Pavimento

Sequencia recomendada para o motor:

1. Definir grid de escoras/torres com afastamentos preliminares.
2. Calcular carga distribuida `q` por painel de laje (peso proprio + 204 kgf/m2).
3. Calcular area de influencia por escora.
4. Selecionar modelo de escora pela tabela da secao 13.1.
5. Verificar utilizacao <= 80%; senao, densificar grid e refazer.
6. Definir vigas secundarias (barrotes): selecionar VM por momento e flecha
   (secoes 22.2 e 22.3).
7. Definir vigas primarias (guias): selecionar VM por momento e flecha
   (secao 22.5).
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

### 23.2 Capacidades de Torres por Fabricante

| Sistema | Capacidade nominal por montante (poste) | Altura util | Observacao |
|---|---:|---:|---|
| Orguel torre padrao (modulo 1.5 m) | 20 kN modulo 1, decaindo ate 14.7 kN no modulo 20 | 1.5-30 m | Por 4 montantes -> 80 kN a 58.8 kN |
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
| Doka Dokaflex 1-2-4 | 1.00 m | 0.50 m | 2.00 m | Sistema base; reduzir se laje >30 cm |
| NBR 15696 (geral) | nao prescreve - depende do calculo | calculo por momento + flecha | calculo por momento + flecha | item 4.3 |
| NBR 15696 (reescoramento) | max 2.00 m x 2.00 m | - | - | Anexo C.4.b |
| Lajes Martins (pre-moldadas) | linha 1.00-1.30 m (varia c/ altura laje) | tabua 1" x 30 cm | - | Lajes pre-moldadas |
| Rohr | conforme calculo | conforme calculo | conforme calculo | Catalogo individual |
| Escoras-Metalicas (IW8) | ~1.00 m x 1.00 m | - | - | Pratica corrente |

Conclusao: a referencia operacional convergente e 1.00 m x 1.00 m para grid
de escoras em lajes macicas tipicas. Distancias maiores precisam justificativa
de calculo.

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

### 23.6 Fator de Carga alfa para Desforma (Manual Doka)

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

Classes de consistencia (abatimento):

| Classe | Abatimento (mm) |
|---|---|
| C1 | <= 20 |
| C2 | 20 a 80 |
| C3 | 80 a 140 |
| C4 | > 140 |

Exemplo NBR 15696 (parede 3m altura, slump 12cm, vb=3.9 m/h):
- Pb (25 graus C) = 12 x Vb + 12 = 58.8 kN/m2
- Pb (20 graus C) = 58.8 x 115% = 67.6 kN/m2 (correcao por temperatura)

### 23.8 Reescoramento - Parametros Adicionais (NBR 15696 Anexo C)

| Parametro | Valor | Fonte |
|---|---|---|
| Distancia maxima entre escoras de reescoramento | 2.0 m x 2.0 m | NBR 15696 C.4.b |
| Sobrecarga minima durante construcao | 1.0 kN/m2 | NBR 15696 C.4.a |
| Ciclo minimo de remocao ou remanejamento | 14 dias como piso normativo; reducao somente com analise, planejamento do sistema e fcj/Ec aprovados | NBR 15696 + responsavel tecnico |
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
| Coeficiente de majoracao | Orguel "1.4" | NBR 15696 1.4 (geral) e 1.5 (escoras/torres compressao) | Aplicar 1.5 em verificacao de flambagem; 1.4 nos demais casos |

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

## 24. Cadeia de Decisao do Engenheiro (Sequencia Detalhada)

A NBR 15696 nao prescreve sequencia explicita; a sequencia abaixo consolida
boas praticas (Doka, escoras-metalicas.ind.br, ABRASFE) com a cadeia ja
implementada nos roteiros internos das secoes 5 e 9.

Uso no Escora.AI: as secoes 24.1 e 24.2 sao fluxo de engenharia e podem virar
rotina do motor. As secoes 24.3 e 24.4 sao checklists de obra/desmontagem:
devem gerar notas, pendencias e campos de confirmacao, mas nao substituir o
responsavel tecnico da obra.

### 24.1 Pre-Calculo (Engenharia)

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
- Coeficiente de ponderacao: 1.4 geral; 1.5 para escoras/torres em compressao
  e flambagem (NBR 15696).
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

Pendencias reais que ainda ficam:

1. Obter ficha tecnica Orguel original da torre para arquivar junto ao sistema,
   embora a curva do PDF ja esteja legivel em 300 dpi.
2. Cadastrar, por locadora, quais modelos estendidos existem de fato no estoque.
3. Definir no produto se fontes externas serao anexadas por obra ou cadastradas
   centralmente no catalogo de equipamentos.

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
   contra geometrias UTFPR Projeto 2 (217m²) e cenarios canonicos.
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
