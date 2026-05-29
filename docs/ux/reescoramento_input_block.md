# Bloco Opcional: Reescoramento e Desforma

**Contexto**: Manual §26 items 9 e 10 (2026-05-28). Engenheiro fornece estes
dados quando o projeto envolver multiplos pavimentos e/ou exigir
desforma/reescoramento programado. Sem esses dados o sistema gera
pendencias DECIDE-001 e DECIDE-002.

## Onde aparece no estrutura.app

Tela de criacao/edicao de projeto, em uma secao recolhivel "**Reescoramento
e Desforma (opcional)**" — exibida apos os parametros principais
(pe-direito, espessura de laje, sobrecarga).

## Exemplo visual (mockup ASCII)

```
┌─ Reescoramento e Desforma (opcional) ──────────────────────┐
│ [ ] Projeto envolve multiplos pavimentos                   │
│ ┌───────────────────────────────────────────────────────┐  │
│ │ Numero de niveis a manter reescorados:  [ 2 ▾ ]       │  │
│ │ Resistencia do concreto na desforma (fcj):            │  │
│ │   [    21    ] MPa  aos [ 14 ] dias                   │  │
│ │ Modulo de elasticidade (Eci):  [  25600  ] MPa        │  │
│ │ Sobrecarga de uso final:       [   2.5   ] kN/m²      │  │
│ │ Sobrecarga em construcao:      [   1.5   ] kN/m²      │  │
│ │   (default NBR 15696 Anexo C)                         │  │
│ │                                                       │  │
│ │ Calculista responsavel:  [ Eng. Fulano, CREA 12345 ]  │  │
│ └───────────────────────────────────────────────────────┘  │
│                                                            │
│ Prazo de desforma:  [ 14 ] dias                            │
│   ☑ Usar piso normativo de 14 dias (NBR 14931)             │
│                                                            │
│ ▾ Justificativa (se prazo < 14 dias)                       │
│   [_____________________________________________________]  │
│   Anexar laudo do calculista: [ Escolher arquivo ]         │
└────────────────────────────────────────────────────────────┘
```

## Schema (JSON Schema 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://estrutura.app/schemas/reescoramento.v1.json",
  "title": "ReescoramentoInput",
  "description": "Bloco opcional fornecido pelo engenheiro responsavel para habilitar verificadores DECIDE-001/DECIDE-002.",
  "type": "object",
  "properties": {
    "multi_pavimento": {
      "type": "boolean",
      "default": false,
      "description": "Marca o projeto como multi-nivel; ativa DECIDE-001."
    },
    "num_niveis_reescoramento": {
      "type": "integer",
      "minimum": 0,
      "maximum": 6,
      "description": "Quantos niveis inferiores manter reescorados."
    },
    "fcj_aos_dias_mpa": {
      "type": "number",
      "minimum": 5,
      "maximum": 80,
      "description": "Resistencia do concreto (MPa) na idade de desforma."
    },
    "fcj_idade_dias": {
      "type": "integer",
      "minimum": 1,
      "maximum": 90,
      "default": 14,
      "description": "Idade em dias correspondente a fcj_aos_dias_mpa."
    },
    "eci_mpa": {
      "type": "number",
      "minimum": 10000,
      "maximum": 60000,
      "description": "Modulo de elasticidade do concreto (MPa) na desforma."
    },
    "carga_final_kn_m2": {
      "type": "number",
      "minimum": 0,
      "maximum": 50,
      "description": "Sobrecarga de uso final do pavimento (kN/m²)."
    },
    "carga_estado_construcao_kn_m2": {
      "type": "number",
      "default": 1.5,
      "description": "Sobrecarga durante construcao (default NBR 15696 Anexo C: 1.5 kN/m²)."
    },
    "calculista_aprovacao": {
      "type": "string",
      "minLength": 5,
      "description": "Nome + CREA/CAU do calculista que aprovou os parametros."
    },
    "desforma_dias": {
      "type": "integer",
      "minimum": 1,
      "maximum": 90,
      "default": 14,
      "description": "Prazo de desforma adotado. Default = piso NBR 14931 (14)."
    },
    "desforma_justificativa": {
      "type": "string",
      "description": "Obrigatoria quando desforma_dias < 14. Texto livre + anexo opcional."
    },
    "desforma_anexo_laudo": {
      "type": "string",
      "format": "uri",
      "description": "URL/path do laudo tecnico anexado (PDF) quando aplicavel."
    }
  },
  "if": {
    "properties": { "desforma_dias": { "type": "integer", "exclusiveMaximum": 14 } },
    "required": ["desforma_dias"]
  },
  "then": {
    "required": ["desforma_justificativa", "calculista_aprovacao"]
  }
}
```

## Exemplo de payload (cenario tipico de obra residencial)

```json
{
  "multi_pavimento": true,
  "num_niveis_reescoramento": 2,
  "fcj_aos_dias_mpa": 21,
  "fcj_idade_dias": 14,
  "eci_mpa": 25600,
  "carga_final_kn_m2": 2.5,
  "carga_estado_construcao_kn_m2": 1.5,
  "calculista_aprovacao": "Eng. Joao Silva, CREA-SP 12345",
  "desforma_dias": 14,
  "desforma_justificativa": "",
  "desforma_anexo_laudo": ""
}
```

## Exemplo de payload (desforma antecipada com laudo)

```json
{
  "multi_pavimento": true,
  "num_niveis_reescoramento": 2,
  "fcj_aos_dias_mpa": 28,
  "fcj_idade_dias": 10,
  "eci_mpa": 27600,
  "carga_final_kn_m2": 2.0,
  "carga_estado_construcao_kn_m2": 1.5,
  "calculista_aprovacao": "Eng. Maria Souza, CREA-RJ 67890",
  "desforma_dias": 10,
  "desforma_justificativa": "Concreto com aditivo acelerador (Sika SikaRapid); fcj 28 MPa aos 10 dias comprovada por ensaio em corpo-de-prova lote #2026-04-12.",
  "desforma_anexo_laudo": "/uploads/laudos/2026/laudo_desforma_obra_xyz.pdf"
}
```

## Mapeamento para o engine

Os dados acima sao convertidos em `ReescoramentoData` e propagados no
`RuleProject`:

```python
from src.rules.project import ReescoramentoData

data = ReescoramentoData(
    fcj_aos_dias_mpa=payload["fcj_aos_dias_mpa"],
    eci_mpa=payload["eci_mpa"],
    carga_final_kn_m2=payload["carga_final_kn_m2"],
    carga_estado_construcao_kn_m2=payload.get("carga_estado_construcao_kn_m2", 1.5),
    num_niveis_reescoramento=payload.get("num_niveis_reescoramento", 0),
    calculista_aprovacao=payload.get("calculista_aprovacao", ""),
)
```

Pipeline result deve expor:

- `result.reescoramento_data: ReescoramentoData`
- `result.desforma_dias: int`
- `result.desforma_justificativa: str`

E o `RuleProject.from_pipeline_result()` ja consome esses campos (vide
`src/rules/project.py`).

## Comportamento esperado dos verificadores

| Cenario | DECIDE-001 | DECIDE-002 |
|---|---|---|
| Bloco nao preenchido + projeto unico nivel | warning informativo | warning "prazo nao informado" |
| Bloco nao preenchido + multi-nivel | warning "alfa Doka nao calculado" | warning "prazo nao informado" |
| Bloco completo + desforma_dias >= 14 | sem violacao | sem violacao |
| Bloco completo + desforma_dias < 14 sem justificativa | sem violacao | **error** |
| Bloco completo + desforma_dias < 14 com justificativa + calculista | sem violacao | warning informativo |
