# Ajuste estrutural de eventos - v3

## Objetivo
Corrigir casos em que o evento vem com `CODIGO` vazio, zero ou inválido, enquanto o código correto aparece embutido em `EVENTOTGE` no formato `00081035-PSICOLOGIA DOMICILIAR`.

## Regra adotada

### Campos novos
- `CODIGO_EFETIVO`
- `EVENTOTGE_EFETIVO`
- `FLAG_CODIGO_INFERIDO`
- `FLAG_CODIGO_INVALIDO_ORIGINAL`

### Lógica
1. Se `CODIGO` tiver 8 dígitos válidos, usar o próprio `CODIGO`.
2. Senão, se `ESTRUTURANUMERICA` tiver 8 dígitos válidos, usar `ESTRUTURANUMERICA`.
3. Senão, se `EVENTOTGE` começar com `8 dígitos + hífen`, inferir o código a partir do prefixo.
4. Para a descrição efetiva, remover o prefixo numérico de `EVENTOTGE` quando ele existir.

## Regras analíticas
- Consolidar eventos por `CODIGO_EFETIVO` e `EVENTOTGE_EFETIVO`.
- Usar como chave-base de associação:
  `BENEFICIARIO + SENHA + DATAATENDIMENTO + CODIGO_EFETIVO + HORARIO`
- Preservar `FLAG_CODIGO_INFERIDO` para rastreabilidade.

## Exemplo
- original: `CODIGO = 0`, `EVENTOTGE = 00081035-PSICOLOGIA DOMICILIAR`
- efetivo: `CODIGO_EFETIVO = 00081035`, `EVENTOTGE_EFETIVO = PSICOLOGIA DOMICILIAR`
