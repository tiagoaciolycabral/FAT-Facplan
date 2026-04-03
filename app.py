from __future__ import annotations

import csv
import io
import json
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    import py7zr  # type: ignore
except Exception:
    py7zr = None

st.set_page_config(page_title='FAT Facplan', page_icon='📗', layout='wide')

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(82,183,136,.16), transparent 24%),
            linear-gradient(180deg, #f3fbf6 0%, #eef7f0 42%, #ffffff 100%);
    }
    .hero {
        background: linear-gradient(135deg, #0f5f43 0%, #147a57 50%, #52b788 100%);
        border-radius: 24px; padding: 28px 30px; color: white; margin-bottom: 12px;
        box-shadow: 0 20px 50px rgba(15,95,67,.16);
    }
    .card {background: white; border-radius: 18px; padding: 16px; border: 1px solid rgba(15,95,67,.08); box-shadow: 0 12px 30px rgba(24,84,54,.08);}
    .metric-label {font-size: .78rem; text-transform: uppercase; color: #537164;}
    .metric-value {font-size: 1.8rem; font-weight: 700; color: #0f5f43;}
    .section-title {color: #0f5f43; font-size: 1.1rem; font-weight: 700; margin: 6px 0 10px 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class='hero'>
        <h1 style='margin:0'>FAT Facplan | Análise Expandida de Faturamento</h1>
        <p style='margin:8px 0 0 0'>Importe arquivos <b>.7z</b>, <b>.zip</b>, <b>.csv</b>, <b>.txt</b>, <b>.xlsx</b> ou <b>.xls</b> para análise recorrente por prestador, evento/TUSS, glosa e separação entre <b>NORMAL</b> e <b>RECURSO</b>.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

KEY_COLUMNS = ['BENEFICIARIO', 'SENHA', 'DATAATENDIMENTO', 'CODIGO', 'HORARIO']
MIN_COLUMNS = {'TIPOOPERACAO', 'PEG', 'VALORAPRESENTADO', 'VALORGLOSADO', 'VALORLIBERADO'}


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)


def _looks_like_faturamento(df: pd.DataFrame) -> bool:
    cols = {str(c).strip().upper() for c in df.columns}
    return len(cols & MIN_COLUMNS) >= 4 and ('TIPOOPERACAO' in cols or 'PEG' in cols)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]
    for col in ['VALORAPRESENTADO', 'VALORGLOSADO', 'VALORLIBERADO', 'QTDAPRESENTADA', 'QTDPAGA']:
        if col in df.columns:
            df[col] = _to_float(df[col])
    for col in ['TIPOOPERACAO', 'PRESTADOR', 'EVENTOTGE', 'DESCRICAOGLOSA', 'GUIATISSPRESTADOR']:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna('').str.strip()
    return df


def _read_delimited(raw: bytes) -> pd.DataFrame:
    text = None
    for enc in ['utf-8', 'iso-8859-1', 'latin1', 'cp1252']:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    text = text or raw.decode('latin1', errors='ignore')
    sample = text[:20000]
    best = ';'
    score = -1
    for sep in [';', ',', '\t', '|']:
        reader = csv.reader(io.StringIO(sample), delimiter=sep)
        widths = [len(r) for _, r in zip(range(25), reader) if r]
        s = sum(1 for w in widths if w > 1)
        if s > score:
            score = s
            best = sep
    return pd.read_csv(io.StringIO(text), sep=best, dtype=str, low_memory=False)


def _extract_uploaded(uploaded) -> list[tuple[str, pd.DataFrame]]:
    datasets: list[tuple[str, pd.DataFrame]] = []
    suffix = Path(uploaded.name).suffix.lower()
    raw = uploaded.getvalue()
    if suffix in {'.csv', '.txt', ''}:
        datasets.append((uploaded.name, _read_delimited(raw)))
    elif suffix in {'.xlsx', '.xls'}:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        book = pd.ExcelFile(tmp_path)
        for sheet in book.sheet_names:
            try:
                datasets.append((f'{uploaded.name}::{sheet}', pd.read_excel(book, sheet_name=sheet)))
            except Exception:
                pass
        tmp_path.unlink(missing_ok=True)
    elif suffix == '.zip':
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if name.endswith('/'):
                    continue
                content = zf.read(name)
                fake = type('FakeUpload', (), {'name': Path(name).name, 'getvalue': lambda self=content: content})
                datasets.extend(_extract_uploaded(fake))
    elif suffix == '.7z':
        if py7zr is None:
            raise RuntimeError('py7zr não disponível no ambiente.')
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = Path(tmp_dir) / uploaded.name
            archive_path.write_bytes(raw)
            with py7zr.SevenZipFile(archive_path, mode='r') as zf:
                zf.extractall(path=tmp_dir)
            for file in Path(tmp_dir).rglob('*'):
                if file.is_file() and file.suffix.lower() in {'.csv', '.txt', '.xlsx', '.xls', ''}:
                    content = file.read_bytes()
                    fake = type('FakeUpload', (), {'name': file.name, 'getvalue': lambda self=content: content})
                    datasets.extend(_extract_uploaded(fake))
    return datasets


def _summarize_dataset(name: str, df: pd.DataFrame) -> dict:
    n = _normalize(df)
    if not _looks_like_faturamento(n):
        return {'dataset': name, 'valido': False}
    tipo = n['TIPOOPERACAO'].astype(str).str.upper() if 'TIPOOPERACAO' in n.columns else pd.Series([''] * len(n))
    normal = n[tipo == 'NORMAL'].copy()
    recurso = n[tipo == 'RECURSO'].copy()
    valor_apresentado_normal = float(normal['VALORAPRESENTADO'].sum()) if 'VALORAPRESENTADO' in normal.columns else 0.0
    valor_apresentado_recurso = float(recurso['VALORAPRESENTADO'].sum()) if 'VALORAPRESENTADO' in recurso.columns else 0.0
    valor_glosado_recurso = float(recurso['VALORGLOSADO'].sum()) if 'VALORGLOSADO' in recurso.columns else 0.0
    valor_liberado_recurso = float(recurso['VALORLIBERADO'].sum()) if 'VALORLIBERADO' in recurso.columns else 0.0
    inflacao = (valor_apresentado_recurso / valor_apresentado_normal * 100.0) if valor_apresentado_normal else 0.0
    deferimento = (valor_liberado_recurso / valor_apresentado_recurso * 100.0) if valor_apresentado_recurso else 0.0

    def agg(src: pd.DataFrame, group_col: str, value_col: str = 'VALORAPRESENTADO', top: int = 15) -> pd.DataFrame:
        if src.empty or group_col not in src.columns or value_col not in src.columns:
            return pd.DataFrame()
        tmp = src.groupby(group_col, dropna=False)[value_col].sum().reset_index().sort_values(value_col, ascending=False).head(top)
        tmp.columns = [group_col, value_col]
        return tmp

    assoc = pd.DataFrame()
    if not recurso.empty and not normal.empty and set(KEY_COLUMNS).issubset(recurso.columns) and set(KEY_COLUMNS).issubset(normal.columns):
        left = recurso[KEY_COLUMNS + ['VALORAPRESENTADO']].copy()
        right = normal[KEY_COLUMNS + ['VALORGLOSADO']].copy()
        for col in KEY_COLUMNS:
            left[col] = left[col].astype(str).fillna('')
            right[col] = right[col].astype(str).fillna('')
        rk = left.groupby(KEY_COLUMNS, dropna=False)['VALORAPRESENTADO'].sum().reset_index()
        nk = right.groupby(KEY_COLUMNS, dropna=False)['VALORGLOSADO'].sum().reset_index()
        assoc = rk.merge(nk, on=KEY_COLUMNS, how='left')
        assoc['match'] = assoc['VALORGLOSADO'].notna().astype(int)
        assoc['score'] = 50
        assoc.loc[assoc['match'] == 1, 'score'] = 85
        assoc.loc[(assoc['match'] == 1) & (assoc['VALORAPRESENTADO'].round(2) == assoc['VALORGLOSADO'].fillna(0).round(2)), 'score'] = 100
        assoc['faixa'] = pd.cut(assoc['score'], bins=[0, 69, 89, 100], labels=['baixa', 'media', 'alta'], include_lowest=True)

    return {
        'dataset': name,
        'valido': True,
        'linhas': int(len(n)),
        'linhas_normal': int(len(normal)),
        'linhas_recurso': int(len(recurso)),
        'valor_apresentado_normal': valor_apresentado_normal,
        'valor_apresentado_recurso': valor_apresentado_recurso,
        'valor_glosado_recurso': valor_glosado_recurso,
        'valor_liberado_recurso': valor_liberado_recurso,
        'inflacao_pct': inflacao,
        'deferimento_pct': deferimento,
        'prestadores': agg(normal, 'PRESTADOR') if 'PRESTADOR' in normal.columns else pd.DataFrame(),
        'eventos': agg(normal, 'EVENTOTGE') if 'EVENTOTGE' in normal.columns else pd.DataFrame(),
        'glosas': agg(recurso if not recurso.empty else n, 'DESCRICAOGLOSA', 'VALORGLOSADO') if 'DESCRICAOGLOSA' in n.columns else pd.DataFrame(),
        'assoc': assoc,
    }


def _to_zip(outputs: dict[str, pd.DataFrame | str | dict]) -> bytes:
    buff = io.BytesIO()
    with zipfile.ZipFile(buff, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, obj in outputs.items():
            if isinstance(obj, pd.DataFrame):
                zf.writestr(name, obj.to_csv(index=False).encode('utf-8-sig'))
            elif isinstance(obj, dict):
                zf.writestr(name, json.dumps(obj, ensure_ascii=False, indent=2).encode('utf-8'))
            else:
                zf.writestr(name, str(obj).encode('utf-8'))
    return buff.getvalue()


uploaded = st.file_uploader('Importe as bases', type=['7z', 'zip', 'csv', 'txt', 'xlsx', 'xls'], accept_multiple_files=True)
processar = st.button('Processar bases', type='primary', use_container_width=True, disabled=not uploaded)

if processar and uploaded:
    summaries = []
    validos = []
    for upl in uploaded:
        try:
            for name, df in _extract_uploaded(upl):
                resumo = _summarize_dataset(name, df)
                summaries.append(resumo)
                if resumo.get('valido'):
                    validos.append(resumo)
        except Exception as exc:
            summaries.append({'dataset': upl.name, 'valido': False, 'erro': str(exc)})

    if not validos:
        st.error('Nenhuma tabela com estrutura de faturamento foi identificada.')
        st.stop()

    resumo_df = pd.DataFrame([{k: v for k, v in s.items() if not isinstance(v, pd.DataFrame)} for s in summaries])
    total_rows = int(sum(s['linhas'] for s in validos))
    total_recurso = int(sum(s['linhas_recurso'] for s in validos))
    total_normal = float(sum(s['valor_apresentado_normal'] for s in validos))
    total_recurso_val = float(sum(s['valor_apresentado_recurso'] for s in validos))
    inflacao = (total_recurso_val / total_normal * 100.0) if total_normal else 0.0
    score_medio = 0.0
    assoc_frames = [s['assoc'] for s in validos if not s['assoc'].empty]
    if assoc_frames:
        score_medio = float(pd.concat(assoc_frames, ignore_index=True)['score'].mean())

    m1, m2, m3, m4, m5 = st.columns(5)
    cards = [
        ('datasets válidos', len(validos)),
        ('linhas totais', f'{total_rows:,}'.replace(',', '.')),
        ('linhas de recurso', f'{total_recurso:,}'.replace(',', '.')),
        ('inflação potencial', f'{inflacao:.2f}%'),
        ('score médio', f'{score_medio:.1f}'),
    ]
    for col, (label, value) in zip([m1, m2, m3, m4, m5], cards):
        col.markdown(f"<div class='card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Resumo por dataset</div>", unsafe_allow_html=True)
    st.dataframe(resumo_df, use_container_width=True, hide_index=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(['Prestadores', 'Eventos', 'Glosas', 'Recurso x Normal', 'Recomendações'])

    with tab1:
        prest = pd.concat([s['prestadores'].assign(dataset=s['dataset']) for s in validos if not s['prestadores'].empty], ignore_index=True)
        if not prest.empty:
            fig = px.bar(prest.sort_values('VALORAPRESENTADO', ascending=False).head(15), x='VALORAPRESENTADO', y='PRESTADOR', orientation='h', color='dataset', title='Top prestadores por valor apresentado normal')
            fig.update_layout(height=520)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(prest, use_container_width=True, hide_index=True)
        else:
            st.info('Sem dados suficientes para prestadores.')

    with tab2:
        evt = pd.concat([s['eventos'].assign(dataset=s['dataset']) for s in validos if not s['eventos'].empty], ignore_index=True)
        if not evt.empty:
            fig = px.bar(evt.sort_values('VALORAPRESENTADO', ascending=False).head(15), x='VALORAPRESENTADO', y='EVENTOTGE', orientation='h', color='dataset', title='Top eventos/TUSS por valor apresentado normal')
            fig.update_layout(height=520)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(evt, use_container_width=True, hide_index=True)
        else:
            st.info('Sem dados suficientes para eventos.')

    with tab3:
        glo = pd.concat([s['glosas'].assign(dataset=s['dataset']) for s in validos if not s['glosas'].empty], ignore_index=True)
        if not glo.empty:
            fig = px.bar(glo.sort_values('VALORGLOSADO', ascending=False).head(15), x='VALORGLOSADO', y='DESCRICAOGLOSA', orientation='h', color='dataset', title='Top glosas por valor glosado')
            fig.update_layout(height=520)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(glo, use_container_width=True, hide_index=True)
        else:
            st.info('Sem dados suficientes para glosas.')

    with tab4:
        if assoc_frames:
            assoc = pd.concat([s['assoc'].assign(dataset=s['dataset']) for s in validos if not s['assoc'].empty], ignore_index=True)
            faixa = assoc.groupby(['dataset', 'faixa'], dropna=False).size().reset_index(name='chaves')
            fig = px.bar(faixa, x='faixa', y='chaves', color='dataset', barmode='group', title='Faixas do score de associação')
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(assoc.head(500), use_container_width=True, hide_index=True)
        else:
            st.info('Sem dados suficientes para associação.')

    with tab5:
        st.markdown('''
        - Considerar **TIPOOPERACAO = NORMAL** como faturamento assistencial principal.
        - Tratar **TIPOOPERACAO = RECURSO** em perspectiva própria.
        - Usar a chave-base **BENEFICIARIO + SENHA + DATAATENDIMENTO + CODIGO + HORARIO** como âncora analítica.
        - Tratar **GUIATISSPRESTADOR** como validador complementar, não como chave obrigatória.
        - Em bases curtas, considerar que parte do recurso pode apontar para períodos anteriores ao recorte.
        ''')
        pacote = _to_zip({
            'resumo_datasets.csv': resumo_df,
            'prestadores.csv': pd.concat([s['prestadores'].assign(dataset=s['dataset']) for s in validos if not s['prestadores'].empty], ignore_index=True) if any(not s['prestadores'].empty for s in validos) else pd.DataFrame(),
            'eventos.csv': pd.concat([s['eventos'].assign(dataset=s['dataset']) for s in validos if not s['eventos'].empty], ignore_index=True) if any(not s['eventos'].empty for s in validos) else pd.DataFrame(),
            'glosas.csv': pd.concat([s['glosas'].assign(dataset=s['dataset']) for s in validos if not s['glosas'].empty], ignore_index=True) if any(not s['glosas'].empty for s in validos) else pd.DataFrame(),
            'associacao.csv': pd.concat([s['assoc'].assign(dataset=s['dataset']) for s in validos if not s['assoc'].empty], ignore_index=True) if assoc_frames else pd.DataFrame(),
            'resumo.json': {'datasets_validos': len(validos), 'linhas_totais': total_rows, 'linhas_recurso': total_recurso, 'inflacao_potencial_pct': round(inflacao, 2), 'score_medio': round(score_medio, 1)},
        })
        st.download_button('Baixar pacote analítico', data=pacote, file_name='fat_facplan_resultados.zip', mime='application/zip', use_container_width=True)
else:
    st.info('Envie uma ou mais bases e clique em Processar bases.')
