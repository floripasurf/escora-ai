# Piloto controlado de locadoras

Objetivo: abrir o self-service para 2 ou 3 locadoras antes de liberar geral,
validando o caminho completo: cadastro, primeira unidade, inventario proprio,
calculo em modo estoque e confianca no resultado.

## Perfis minimos

1. Estoque completo: escoras, torres e vigas com quantidades reais.
2. Estoque parcial: menos modelos que o estoque completo, mas com ao menos um item disponivel.
3. Equipamentos proprios: escora ou torre cadastrada com capacidade, altura ou curva propria.

## Provisionamento

Use inventarios reais em `.json`, `.csv` ou `.xlsx`:

```bash
python3 scripts/provision_pilot_locadoras.py \
  --data-dir /private/tmp/escora-ai-pilots \
  --owner-password 'trocar-esta-senha' \
  --complete /caminho/estoque-completo.xlsx \
  --partial /caminho/estoque-parcial.xlsx \
  --custom /caminho/equipamentos-proprios.xlsx
```

Antes de gravar:

```bash
python3 scripts/provision_pilot_locadoras.py \
  --dry-run \
  --complete /caminho/estoque-completo.xlsx \
  --partial /caminho/estoque-parcial.xlsx \
  --custom /caminho/equipamentos-proprios.xlsx
```

O script cria os owners:

- `piloto-complete@estrutura.app`
- `piloto-partial@estrutura.app`
- `piloto-custom@estrutura.app`

## Gate de validacao

- Cada owner consegue entrar e ver sua unidade.
- A aba Inventario mostra locadora, unidade, nome do inventario e data de atualizacao.
- Upload XLSX mostra preview antes de salvar.
- Importacao permite `Substituir tudo` e `Atualizar quantidades`.
- Historico registra ator, data, arquivo e diferenca.
- Resultado do job informa a unidade/estoque usado no calculo.
- Viewer nao cria job nem altera inventario.
