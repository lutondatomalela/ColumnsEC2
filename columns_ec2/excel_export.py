"""Single-pass Excel export of already calculated data; no workbook rewrites."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace, MethodType
import math
import os
import queue
import tempfile
import threading
import time

import pandas as pd

from .runtime.loader import load_runtime


@dataclass(frozen=True)
class Value:
    value: object

    def get(self):
        return self.value


def capture(app):
    """Read all Tk variables on the UI thread, then hand off plain data only."""
    ns = load_runtime()
    snapshot = SimpleNamespace()
    frame_names = {'df_results', 'df_summary', 'df_pair', 'df_calc_input',
                   'df_clean', 'df_repair_attempts', 'df_notes'}
    for name, value in vars(app).items():
        if name in frame_names and isinstance(value, pd.DataFrame):
            setattr(snapshot, name, value.copy(deep=True))
        elif name.startswith('var_') and hasattr(value, 'get'):
            setattr(snapshot, name, Value(value.get()))
    for name in ('input_file_path', '_calculation_perf', '_v68_perf'):
        setattr(snapshot, name, getattr(app, name, {} if name != 'input_file_path' else ''))
    # These two legacy helpers construct Tk variables in default arguments.
    # Evaluate them here, never in the file-writing thread.
    snapshot.info = ns['_v67_info_df'](app)
    snapshot.parameters = ns['_v67_parameters_df'](app)
    for label, var in [('RH [%]', 'var_creep_RH'), ('t0 [dias]', 'var_creep_t0'),
                       ('Estratégia de armadura', 'var_rebar_strategy')]:
        if hasattr(snapshot, var):
            snapshot.parameters.loc[snapshot.parameters.iloc[:, 0].eq(label), 'Valor'] = str(getattr(snapshot, var).get())
    snapshot.shortlists = app.build_shortlists_df().copy(deep=True)
    snapshot.performance = ns['_v68_performance_df'](app)
    snapshot.notes = getattr(snapshot, 'df_notes', pd.DataFrame())
    if snapshot.notes.empty:
        snapshot.notes = app.build_normative_notes().copy(deep=True)
    snapshot.language = str(getattr(snapshot, 'var_language', Value('PT')).get()).upper()
    return snapshot


def frames(snapshot):
    """Keep the complete v0.2 workbook sheet contract, without recalculation."""
    ns = load_runtime()
    clean = ns['_rc25_sanitize_df']
    res = clean(snapshot.df_results)
    summary = clean(snapshot.df_summary)
    # Resolve only the missing label, leaving all numerical results untouched.
    for df in (res, summary):
        if not df.empty:
            df['prumada'] = df.apply(ns['_v682_prumada_from_row'], axis=1)
    def subset(keys):
        return res[[k for k in keys if k in res.columns]].copy()
    states = res.get('estado_global', res.get('status', pd.Series('', index=res.index))).astype(str)
    attempts = getattr(snapshot, 'df_repair_attempts', pd.DataFrame())
    if attempts.empty:
        attempts = ns['_v66_correction_attempt_rows'](res)
    source = SimpleNamespace(df_results=res, df_summary=summary,
                             df_pair=getattr(snapshot, 'df_pair', pd.DataFrame()),
                             df_calc_input=getattr(snapshot, 'df_calc_input', pd.DataFrame()),
                             df_clean=getattr(snapshot, 'df_clean', pd.DataFrame()),
                             _v68_perf=getattr(snapshot, '_v68_perf', {}))
    criteria = pd.DataFrame([
        ('η_NMyMz alvo', getattr(snapshot, 'var_eta_target', Value('0.8')).get()),
        ('η_NMyMz mínimo', getattr(snapshot, 'var_eta_min', Value('0.7')).get()),
        ('η_NMyMz máximo', getattr(snapshot, 'var_eta_max', Value('0.9')).get()),
        ('Excesso máximo de As', getattr(snapshot, 'var_as_excess', Value('0.4')).get()),
        ('Nível PDF', getattr(snapshot, 'var_pdf_level', Value('Relatório técnico')).get()),
    ], columns=['Critério', 'Valor'])
    result = [
        ('00_Info', snapshot.info),
        ('01_Parametros', snapshot.parameters),
        ('02_Entrada_Dados', source.df_clean),
        ('03_Pares_Member_Case', source.df_pair),
        ('04_Casos_Governantes', ns['_v67_governing_cases_df'](source)),
        ('05_Resultados', res),
        ('06_Resumo_Membros', summary),
        ('06B_Estados_Modulo', subset(['name', 'member', 'case', 'estado_global', 'estado_resistente', 'estado_corte', 'estado_torcao', 'estado_els', 'estado_pormenorizacao', 'η_NMyMz', 'solucao_completa', 'solucao', 'decisao_tecnica', 'failure_reason', 'failure_warnings', 'detailing_blocking_issues', 'detailing_warnings'])),
        ('06C_Decisao_Prumadas', summary),
        ('07_Falhas', res[states.str.contains('Falha|Failure|Não conforme', case=False, regex=True)]),
        ('07B_Avisos', res[states.str.contains('Aviso|Warning', case=False, regex=True)]),
        ('09_Shortlists', snapshot.shortlists),
        ('10_ELS', subset([k for k in res if k.startswith('service_') or k in ('member', 'case', 'prumada')])),
        ('11_V_Torcao', subset([k for k in res if 'shear' in k.lower() or 'tors' in k.lower() or k in ('member', 'case', 'prumada', 'v_ed_y_kN', 'v_ed_z_kN', 'mx_ed_kNm')])),
        ('13_Notas', snapshot.notes),
        ('20_Superficie_NMyMz', ns['_v67_surface_points_fast'](source)),
        ('26_Tentativas_Correcao', attempts),
        ('30_Diagnostico_SC', ns['_v66_structuralcodes_diagnostics_df']()),
        ('12_Performance', snapshot.performance if hasattr(snapshot, 'performance') else ns['_v68_performance_df'](source)),
        ('14_Interacao_NMyMz', ns['_v68_interaction_summary'](summary)),
        ('01C_Criterios', criteria),
        ('06D_Quadro_Prumada_Tramo', summary),
    ]
    # Retain imported results and metadata. Sanitisation is presentation only.
    return [(name, clean(df)) for name, df in result]


def write(snapshot, path, progress=lambda percent, text: None):
    """Stream sheets once and atomically replace the destination on success."""
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    ns = load_runtime()
    start = time.perf_counter()
    progress(2, 'A preparar as folhas do Excel…')
    sheets = frames(snapshot)
    wb = Workbook(write_only=True)
    wb.properties.title = 'ColumnsEC2'
    wb.properties.creator = 'https://github.com/lutondatomalela/ColumnsEC2'
    wb.properties.subject = str(snapshot.info.iloc[1, 1])
    wb.properties.description = 'Resultados completos exportados numa única gravação.'
    header_font = Font(name='Calibri', size=10, bold=True, color='202C38')
    header_fill = PatternFill('solid', fgColor='E5E7EB')
    header_alignment = Alignment(vertical='center', wrap_text=True)
    english = snapshot.language.startswith('EN')
    @lru_cache(maxsize=65536)
    def translate(text, header=False):
        if not english: return text
        # Reuse the technical vocabulary, translating each unique label once.
        for name in (('_rc7_translate_header', '_rc8_translate_header', '_rc11_header_en') if header else ('_rc7_translate_technical_en', '_rc8_translate_technical_en', '_rc11_to_technical_en')):
            if name in ns: text = ns[name](text)
        mapping = {**ns.get('_V69_CELL_MAP_PT_EN', {}), **ns.get('_V69_HEADER_MAP_PT_EN', {})}
        return mapping.get(text, text)
    def scalar(value):
        if value is None: return None
        if hasattr(value, 'item'):
            try: value = value.item()
            except (ValueError, AttributeError): pass
        if isinstance(value, float) and not math.isfinite(value): return None
        if isinstance(value, (str, int, float, bool)): return value
        if ns['_rc25_is_nan_scalar'](value): return None
        return str(value)
    total = max(1, sum(len(df) for _, df in sheets))
    done = 0
    used = set()
    target = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.columnsec2-', suffix='.xlsx', dir=target.resolve().parent)
    os.close(fd)
    try:
        for name, df in sheets:
            display = ns.get('_V69_SHEET_MAP_PT_EN', {}).get(name, name) if english else name
            ws = wb.create_sheet(ns['_v67_sheet_name'](display, used))
            ws.freeze_panes = 'A2'
            ws.sheet_view.showGridLines = False
            headers = [translate(str(c), True) for c in df.columns]
            sample = df.head(80)
            for index, header in enumerate(headers, 1):
                values = sample.iloc[:, index-1].map(lambda v: len(str(v)) if v is not None else 0)
                width = min(48, max(12, len(header)+2, int(values.max())+2 if len(values) else 0))
                ws.column_dimensions[get_column_letter(index)].width = width
            ws.auto_filter.ref = f'A1:{get_column_letter(max(1, len(headers)))}{len(df)+1}'
            cells = []
            for header in headers:
                cell = WriteOnlyCell(ws, header)
                cell.font, cell.fill, cell.alignment = header_font, header_fill, header_alignment
                cells.append(cell)
            ws.append(cells)
            raw_sheet = name in ('02_Entrada_Dados', '03_Pares_Member_Case')
            for row_index, row in enumerate(df.itertuples(index=False, name=None), 1):
                values = []
                for value in row:
                    value = scalar(value)
                    if isinstance(value, str):
                        if english and not raw_sheet: value = translate(value)
                        if value.startswith('=') or value == 'ColumnsEC2':
                            cell = WriteOnlyCell(ws, value)
                            cell.data_type = 's'
                            if value == 'ColumnsEC2': cell.hyperlink = wb.properties.creator
                            value = cell
                    values.append(value)
                ws.append(values)
                if row_index % 1000 == 0:
                    progress(min(90, 5 + 85*(done+row_index)/total), f'A exportar {name}: {row_index} / {len(df)} linhas')
            done += len(df)
            progress(min(90, 5 + 85*done/total), f'Folha concluída: {name}')
        progress(94, 'A compactar e gravar o ficheiro Excel…')
        wb.save(temporary)
        os.replace(temporary, target)
        progress(100, f'Excel exportado em {time.perf_counter()-start:.1f} s: {target.name}')
        return time.perf_counter()-start
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def write_excel(app, path):
    return write(capture(app), path)


def export_excel(app):
    from tkinter import filedialog, messagebox
    if getattr(app, '_excel_export_busy', False): return
    if app.df_results.empty:
        messagebox.showinfo('Excel', 'Calcule o projeto antes de exportar.', parent=app)
        return
    filename = filedialog.asksaveasfilename(parent=app, title='Exportar Excel de cálculo', defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
    if not filename: return
    app.status_var.set('A preparar a exportação Excel…')
    app.progress_var.set(0)
    app.update_idletasks()
    try:
        snapshot = capture(app)
    except Exception as error:
        messagebox.showerror('Exportar Excel', str(error), parent=app)
        return
    app._excel_export_busy = True
    updates = queue.SimpleQueue()
    def worker():
        try:
            seconds = write(snapshot, filename, lambda p, text: updates.put(('progress', p, text)))
            updates.put(('done', 100, f'{filename} ({seconds:.1f} s)'))
        except Exception as error:
            updates.put(('error', 0, str(error)))
    def poll():
        last = None
        while not updates.empty():
            last = updates.get()
        if last:
            kind, percent, text = last
            app.progress_var.set(percent)
            if kind == 'error':
                app._excel_export_busy = False
                app.status_var.set('Não foi possível gravar o Excel.')
                messagebox.showerror('Exportar Excel', text + '\n\nSe o ficheiro estiver aberto no Excel, feche-o e tente novamente.', parent=app)
                return
            app.status_var.set(f'Excel exportado: {text}' if kind == 'done' else text)
            if kind == 'done':
                app._excel_export_busy = False
                return
        app.after(100, poll)
    app._excel_export_thread = threading.Thread(target=worker, name='ColumnsEC2-Excel', daemon=True)
    app._excel_export_thread.start()
    app.after(100, poll)


def install_excel_export(app):
    app._write_excel = MethodType(write_excel, app)
    app.export_excel = MethodType(export_excel, app)
    def close():
        if getattr(app, '_excel_export_busy', False):
            from tkinter import messagebox
            messagebox.showinfo('Exportação em curso', 'Aguarde a conclusão da gravação do Excel antes de fechar o programa.', parent=app)
        else:
            app.destroy()
    app.protocol('WM_DELETE_WINDOW', close)
