# FAT Facplan

Aplicativo web em Streamlit para análise recorrente de bases de faturamento de prestadores, com foco em:

- ingestão de arquivos `.7z`, `.zip`, `.csv`, `.txt`, `.xlsx` e `.xls`;
- separação entre `NORMAL` e `RECURSO`;
- visão executiva e técnica por dataset;
- leitura por prestador, evento/TUSS e glosa;
- score analítico simplificado de associação `RECURSO x NORMAL`.

## Executar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar no Render

Start command:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

## Regras operacionais adotadas

1. `TIPOOPERACAO = NORMAL` como faturamento assistencial principal.
2. `TIPOOPERACAO = RECURSO` em perspectiva própria.
3. Chave-base de associação: `BENEFICIARIO + SENHA + DATAATENDIMENTO + CODIGO + HORARIO`.
4. `GUIATISSPRESTADOR` como validador complementar, não como chave obrigatória.
5. Em bases curtas, considerar que parte do recurso pode apontar para processamentos anteriores ao recorte.
