# Roteiro operacional recorrente - v3

## Objetivo
Padronizar a ingestão, a leitura e a emissão de análises de faturamento de prestadores em arquivos individuais ou lotes, com foco em governança analítica, segregação entre `NORMAL` e `RECURSO`, visão expandida por prestador e normalização estrutural de eventos.

## Etapas

1. Receber arquivos `.7z`, `.zip`, `.csv`, `.txt`, `.xlsx` ou `.xls`.
2. Executar o aplicativo web de análise.
3. Validar se há código de evento vazio, zero ou inválido.
4. Consolidar por `CODIGO_EFETIVO` e `EVENTOTGE_EFETIVO`.
5. Ler faturamento principal em `NORMAL` e recurso em perspectiva própria.
6. Avaliar score de associação com chave-base `BENEFICIARIO + SENHA + DATAATENDIMENTO + CODIGO_EFETIVO + HORARIO`.
7. Emitir visão executiva, técnica e pacote de evidências.

## Regras fixadas

- Não somar `VALORAPRESENTADO` de `NORMAL` e `RECURSO` no mesmo KPI principal.
- Tratar `GUIATISSPRESTADOR` como reforço, não como chave obrigatória.
- Preservar `FLAG_CODIGO_INFERIDO` e `FLAG_CODIGO_INVALIDO_ORIGINAL` para rastreabilidade.
- Em bases curtas, considerar que parte do recurso pode apontar para processamento anterior ao recorte.
