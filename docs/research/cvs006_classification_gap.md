# CVS-COB-FOR-006-R00 — investigação do "buraco de classificação" (x>55, y>44)

Data: 2026-06-12. Pedido do revisor: na ala x>55, y>44 nenhum pilar foi
classificado e o trecho esquerdo da "viga do topo" (y≈55, x<67) não vira viga.

## Conclusão: não existe ala estrutural em x>55, y>44

A região x>55, y>44 do DXF **não é planta**: é a tabela **ESQUEMA DE NÍVEIS**
(caixa 17.82x6.42 m em (63.7–81.5, 51.1–57.5), desenhada no layer `1` — o
mesmo layer estrutural das vigas reais), as legendas de cargas
(ACIDENTAIS/PERMANENTE/PESOS ESPECÍFICOS/PILARES) e os marcadores de corte
A/B (retângulos concêntricos em (55–57, 50–51)). A planta real termina em
x≈54.5 (bordas em x=53.59 layer `1` / x=54.45 layer `42`).

O que o revisor viu no output v11 eram **escoras fantasma**: 52 marcas de
escora de viga sobre as linhas da tabela de níveis (e os marcadores de corte
viravam "pilares" com score 0.54–0.58). Não faltou classificar pilares —
sobrou classificar a tabela como estrutura.

## Causa raiz (corrigida): duplo buffer no filtro de cluster

`_filter_beams_to_main_cluster` (stage_calculate) bufferizava AMBAS as
linhas em 5 m e testava interseção → limiar efetivo de **10 m**. Cadeia:
planta → barra de corte (59–67.9, 45.1, layer `34`, gap 7.2 m) → tabela de
níveis (gap ~6 m). Os 18 falsos beams "Eixo X/Y=..." da tabela entravam no
cluster principal e eram escorados. **Fix**: conexão agora exige
`distance(linha_i, linha_j) < buffer_m` (5 m), como o docstring prometia.
Resultado no CVS-006: 83 → 33 vigas válidas, todas as V1a–V19a reais +
periferia mantidas; tabela, barra de corte, moldura da prancha (x≈0.1) e
caixas de detalhe descartadas; 0 fantasmas em x>55, y>44.

## Limitação profunda (documentada, NÃO corrigida): faixa do topo y≈54.5–55.6

O "trecho esquerdo da viga do topo" (y≈55, x=32.88–53.59) é uma faixa
delimitada por:

- borda inferior: H-segment y=54.50, layer `1` (layer de viga);
- borda superior: H-segment y=55.64, layer `42` (layer NÃO classificado
  como viga: taxa geométrica insuficiente, confiança aprendida 0.17).

O par dista **1.14 m** — acima de `MAX_BEAM_WIDTH = 0.65` do
`segment_classifier`, e não há etiqueta `V*` associada. Geometricamente
isso é um **beiral/platibanda de 1.14 m** (faixa de laje), não uma viga.
O mesmo padrão se repete na borda direita (x=53.59 layer `1` + x=54.45
layer `42`, 0.86 m).

O que faltaria para cobrir esse padrão sem gambiarra:

1. **Detector de faixa de borda** (beiral/platibanda): par de linhas
   paralelas 0.65–1.50 m no PERÍMETRO do casco da planta, com uma das
   bordas colinear ao fechamento das vigas → classificar como painel de
   laje categoria `beiral` (hoje a categorização de painel existe em
   stage_calculate, mas o painel nunca é criado porque o contorno não
   fecha sem a linha do layer `42`).
2. **Pareamento entre layers irmãos**: aceitar par viga/contorno com
   bordas em layers diferentes quando um deles é layer de viga e o outro
   tem >50% dos segmentos colineares/paralelos a segmentos do layer de
   viga (layer `42` é o "espelho" do contorno externo do `1` neste DXF).
   Exige validação em outros projetos para não ressuscitar linhas de cota.

Sem (1)+(2), a faixa fica sem escoramento dedicado — comportamento atual e
aceito; a laje adjacente continua escorada normalmente até a face da viga
V1a/P1–P6.
