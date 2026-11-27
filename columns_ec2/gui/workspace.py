"""Task-oriented desktop workspace using the existing calculation commands."""
from __future__ import annotations

import os
import sys
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox


UI_FONT = 'Segoe UI' if sys.platform == 'win32' else 'DejaVu Sans'


PARAMETERS = (
    'var_cover', 'var_fyk', 'var_concrete_default', 'var_l0y', 'var_l0z',
    'var_calc_mode', 'var_reduce_cases', 'var_code_backend', 'var_creep_RH',
    'var_creep_t0', 'var_service_case', 'var_rebar_strategy', 'var_eta_target',
    'var_eta_min', 'var_eta_max', 'var_as_excess', 'var_ec23_strength_class',
    'var_ec23_tref', 'var_ec23_t0',
)


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


class Workspace:
    """Keep data views and callbacks; replace the crowded navigation and forms."""

    def __init__(self, app):
        self.app = app
        self.busy = False
        self.awaiting_results = False
        self.result_token = None
        self.data_token = None
        self.run_signature = None
        self.result_signature = None
        self.result_data_token = None
        self.summary_token = None
        self.group = 'home'
        self._after_id = None
        self._callbacks = queue.SimpleQueue()
        self._tk_after = app.after
        self._ui_thread = threading.get_ident()
        # Calculation callbacks must be registered by the Tk thread. The
        # legacy worker calls after() from a background thread.
        def schedule(ms, func=None, *args):
            if func is not None and threading.get_ident() != self._ui_thread:
                self._callbacks.put((ms, func, args))
                return None
            return self._tk_after(ms, func, *args)
        app.after = schedule
        self._style()
        self.nb = next(w for w in walk(app) if isinstance(w, ttk.Notebook))
        self.original_tabs = list(self.nb.tabs())
        self.original_titles = {t: self.nb.tab(t, 'text') for t in self.original_tabs}
        self.right = self.nb.master
        self.paned = self.right.master
        self.root = self.paned.master
        self.sidebar = app.nametowidget(self.paned.panes()[0])
        # Retain legacy variables and callback registrations, but display each
        # user action only once in the task workspace.
        for child in self.sidebar.winfo_children():
            child.grid_remove()
        self._header()
        self._rail()
        self._pages()
        self._toolbar()
        self.nb.bind('<<NotebookTabChanged>>', self._tab_changed, add='+')
        app.bind('<Control-o>', lambda e: self.import_data(), add='+')
        app.bind('<F5>', lambda e: self.calculate(), add='+')
        app.bind('<Destroy>', self._destroy, add='+')
        app.minsize(1000, 650)
        app.geometry('1360x860')
        app.title('ColumnsEC2 0.2.0 | Pilares de betão armado')
        self.show('home')
        app.after(200, lambda: self.paned.sashpos(0, 205))
        self._poll()
        self._drain_callbacks()

    def _drain_callbacks(self):
        while not self._callbacks.empty():
            ms, func, args = self._callbacks.get()
            self._tk_after(ms, func, *args)
        self._drain_id = self._tk_after(50, self._drain_callbacks)

    def _style(self):
        style = ttk.Style(self.app)
        style.theme_use('clam')
        style.configure('.', font=(UI_FONT, 10), background='#f4f6f8', foreground='#243244')
        style.configure('TFrame', background='#f4f6f8')
        style.configure('TLabel', background='#f4f6f8')
        style.configure('TButton', padding=(12, 8))
        style.configure('Primary.TButton', background='#164e63', foreground='white', font=(UI_FONT, 10, 'bold'))
        style.map('Primary.TButton', background=[('active', '#21677e'), ('disabled', '#dce3e9')], foreground=[('disabled', '#6b7280')])
        style.configure('Nav.TButton', anchor='w', padding=(16, 12), borderwidth=0)
        style.configure('Selected.Nav.TButton', background='#dcebf0', foreground='#164e63', font=(UI_FONT, 10, 'bold'))
        style.configure('Title.TLabel', font=(UI_FONT, 20, 'bold'), foreground='#142d3a')
        style.configure('Section.TLabel', font=(UI_FONT, 13, 'bold'))
        style.configure('Subtle.TLabel', font=(UI_FONT, 9), foreground='#5b6878')
        style.configure('TLabelframe', padding=14, bordercolor='#d8dfe6')
        style.configure('TLabelframe.Label', font=(UI_FONT, 10, 'bold'))
        style.configure('Treeview', rowheight=28, font=(UI_FONT, 10), background='white', fieldbackground='white')
        style.configure('Treeview.Heading', background='#e5e7eb', foreground='#202c38', font=(UI_FONT, 10, 'bold'), padding=(6, 7))
        style.map('Treeview', background=[('selected', '#dcebf0')], foreground=[('selected', '#102f40')])
        style.configure('TNotebook.Tab', padding=(14, 9))
        style.configure('TEntry', fieldbackground='white', padding=5)

    def _header(self):
        self.paned.grid_configure(row=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        header = ttk.Frame(self.root, padding=(16, 8, 16, 16))
        header.grid(row=0, column=0, sticky='ew')
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text='ColumnsEC2', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(header, text='Pilares de betão armado  /  Eurocódigo 2', style='Subtle.TLabel').grid(row=1, column=0, sticky='w')
        self.file_label = ttk.Label(header, text='Nenhum ficheiro importado', style='Subtle.TLabel', anchor='e')
        self.file_label.grid(row=0, column=1, sticky='e')
        self.count_label = ttk.Label(header, text='Importe uma tabela para começar', style='Subtle.TLabel', anchor='e')
        self.count_label.grid(row=1, column=1, sticky='e')

    def _rail(self):
        rail = ttk.Frame(self.sidebar, padding=(10, 16))
        rail.grid(row=0, column=0, columnspan=2, sticky='nsew')
        ttk.Label(rail, text='PROJETO', style='Subtle.TLabel').pack(anchor='w', padx=12, pady=(0, 12))
        self.nav = {}
        for key, label in [('home', 'Visão geral'), ('data', '1   Dados'), ('settings', '2   Configuração'), ('results', '3   Resultados'), ('export', '4   Exportar'), ('diagnostics', 'Diagnóstico'), ('help', 'Ajuda')]:
            b = ttk.Button(rail, text=label, style='Nav.TButton', command=lambda k=key: self.show(k))
            b.pack(fill='x', pady=2)
            self.nav[key] = b
        ttk.Separator(rail).pack(fill='x', pady=18)
        ttk.Label(rail, text='Atalhos\nCtrl+O  Importar\nF5         Calcular', style='Subtle.TLabel', justify='left').pack(anchor='w', padx=12)
        self.step_label = ttk.Label(rail, text='A aguardar dados', style='Subtle.TLabel', wraplength=165)
        self.step_label.pack(anchor='w', padx=12, pady=24)

    def _new_page(self, title):
        page = ttk.Frame(self.nb, padding=16)
        self.nb.add(page, text=title)
        return page

    def _scroll_content(self, page):
        page.rowconfigure(0, weight=1)
        page.columnconfigure(0, weight=1)
        canvas = tk.Canvas(page, highlightthickness=0, background='#f4f6f8')
        scrollbar = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        body = ttk.Frame(canvas, padding=8)
        window = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        def wheel(event):
            canvas.yview_scroll(-1 if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0 else 1, 'units')
        canvas.bind('<MouseWheel>', wheel)
        canvas.bind('<Button-4>', wheel)
        canvas.bind('<Button-5>', wheel)
        return body

    def _pages(self):
        self.home = self._new_page('Visão geral')
        home_body = self._scroll_content(self.home)
        ttk.Label(home_body, text='Do modelo de esforços ao quadro de pilares', style='Section.TLabel').pack(anchor='w', pady=(0, 8))
        ttk.Label(home_body, text='Um percurso simples para preparar, calcular e documentar o projeto.', style='Subtle.TLabel').pack(anchor='w', pady=(0, 20))
        for title, text, group in [
            ('1  Importar os esforços', 'CSV, Excel ou tabela da área de transferência. Confirme as barras, os pisos e os nomes das prumadas.', 'data'),
            ('2  Rever as hipóteses', 'Defina os materiais, comprimentos efetivos, combinação ELS e estratégia de armadura.', 'settings'),
            ('3  Calcular e decidir', 'Consulte o resumo por tramo e os avisos. Os detalhes de cada caso ficam disponíveis nos resultados.', 'results'),
            ('4  Preparar a documentação', 'Exporte o Excel de cálculo, o relatório PDF ou o quadro de pilares em DXF.', 'export'),
        ]:
            card = ttk.LabelFrame(home_body, text=title)
            card.pack(fill='x', pady=(0, 12))
            ttk.Label(card, text=text, wraplength=700).pack(side='left', fill='x', expand=True)
            ttk.Button(card, text='Abrir', command=lambda g=group: self.show(g)).pack(side='right', padx=(12, 0))
        self.overview = tk.StringVar(value='Sem resultados calculados.')
        ttk.Label(home_body, textvariable=self.overview, style='Section.TLabel', wraplength=750).pack(anchor='w', pady=12)
        self.settings = self._new_page('Configuração')
        self._settings()
        self.exports = self._new_page('Exportar')
        self._exports()
        self.decision = self._new_page('Decisão por tramo')
        ttk.Label(self.decision, text='Armadura adotada e verificações por tramo', style='Section.TLabel').pack(anchor='w', pady=(0, 8))
        ttk.Label(self.decision, text='Duplo clique numa linha para consultar os motivos dos avisos e os estados de cada verificação.', style='Subtle.TLabel', wraplength=850).pack(anchor='w', pady=(0, 12))
        table = ttk.Frame(self.decision)
        table.pack(fill='both', expand=True)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        columns = ('Prumada', 'Piso', 'Barra', 'Combinação', 'Secção [cm]', 'Armadura adotada', 'Utilização', 'Estado')
        self.decision_tree = ttk.Treeview(table, columns=columns, show='headings')
        for name, width in zip(columns, (100, 115, 65, 90, 95, 310, 85, 90)):
            self.decision_tree.heading(name, text=name)
            self.decision_tree.column(name, width=width, minwidth=65, stretch=name == 'Armadura adotada')
        sy = ttk.Scrollbar(table, orient='vertical', command=self.decision_tree.yview)
        sx = ttk.Scrollbar(table, orient='horizontal', command=self.decision_tree.xview)
        self.decision_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.decision_tree.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.decision_tree.tag_configure('Aviso', background='#fff5dd')
        self.decision_tree.tag_configure('Falha', background='#fde7e7')
        self.decision_tree.bind('<Double-1>', self._details)
        self.decision_rows = {}
        self.all_tabs = list(self.nb.tabs())
        self.groups = {
            'home': [str(self.home)],
            'settings': [str(self.settings)],
            'export': [str(self.exports)],
            'data': [], 'results': [], 'diagnostics': [], 'help': [],
        }
        for t in self.original_tabs:
            title = self.original_titles[t].lower()
            if any(x in title for x in ('instru','notes','notas')): group = 'help'
            elif any(x in title for x in ('resumo','summary','result','falha','failure','relatório','report')): group = 'results'
            elif any(x in title for x in ('colar','paste','tabela','table','qualidade','quality')): group = 'data'
            else: group = 'diagnostics'
            self.groups[group].append(t)
        # The compact decision view comes before per-case detail.
        self.groups['results'].sort(key=lambda t: 0 if any(x in self.original_titles[t].lower() for x in ('resumo', 'summary')) else 1)
        summary = str(self.app.tab_summary)
        if summary in self.groups['results']:
            self.groups['results'].remove(summary)
            self.groups['diagnostics'].insert(0, summary)
            self.nb.tab(summary, text='Resumo detalhado')
        self.groups['results'].insert(0, str(self.decision))
        self.nb.tab(self.app.tab_results, text='Casos calculados')
        self.nb.tab(self.app.tab_report, text='Notas da análise')

    def _refresh_decisions(self):
        from columns_ec2.runtime.loader import runtime_object
        resolver = runtime_object('_v682_prumada_from_row')
        summary = self.app.df_summary
        if summary.empty: summary = self.app.df_results
        self.decision_tree.delete(*self.decision_tree.get_children())
        self.decision_rows.clear()
        for _, row in summary.iterrows():
            def value(*names):
                for name in names:
                    text = str(row.get(name, '')).strip()
                    if text.lower() not in ('', 'nan', 'none', '<na>', '-'):
                        return text
                return '-'
            section = value('Secção [cm]')
            if section == '-': section = f'{value("b_cm")} × {value("h_cm")}'
            util = value('η_NMyMz', 'utilizacao')
            try: util = f'{float(util):.3f}'
            except ValueError: pass
            state = value('estado_global', 'Estado', 'status')
            vals = (resolver(row), value('Piso', 'story'), value('member'), value('case'), section,
                    value('Solução', 'solucao_completa', 'solucao'), util, state)
            iid = self.decision_tree.insert('', 'end', values=vals, tags=(state,))
            self.decision_rows[iid] = row

    def _details(self, _event=None):
        selected = self.decision_tree.selection()
        if not selected: return
        row = self.decision_rows[selected[0]]
        window = tk.Toplevel(self.app)
        window.title('Verificações do tramo')
        window.geometry('740x480')
        text = tk.Text(window, wrap='word', font=(UI_FONT, 11), padx=20, pady=20, background='white', foreground='#243244')
        text.pack(fill='both', expand=True)
        labels = [('Prumada', 'name'), ('Piso', 'story'), ('Barra', 'member'), ('Combinação', 'case'), ('Estado global', 'estado_global'), ('Resistência', 'estado_resistente'), ('Corte', 'estado_corte'), ('Torção', 'estado_torcao'), ('ELS', 'service_status'), ('Pormenorização', 'estado_pormenorizacao'), ('Decisão técnica', 'decisao_tecnica'), ('Falha', 'failure_reason'), ('Avisos técnicos', 'failure_warnings'), ('Avisos de pormenorização', 'detailing_warnings')]
        for label, key in labels:
            val = str(row.get(key, '')).strip()
            if val.lower() not in ('', 'nan', 'none', '<na>', '-'):
                text.insert('end', f'{label}: {val}\n\n')
        text.configure(state='disabled')
        ttk.Button(window, text='Fechar', command=window.destroy).pack(anchor='e', padx=14, pady=10)

    def _field(self, parent, row, label, var_name, values=None):
        var = getattr(self.app, var_name, None)
        if var is None:
            return None
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(0, 18), pady=7)
        widget = ttk.Combobox(parent, textvariable=var, values=values, state='readonly', width=34) if values else ttk.Entry(parent, textvariable=var, width=16)
        widget.grid(row=row, column=1, sticky='ew', pady=7)
        parent.columnconfigure(1, weight=1)
        return widget

    def _settings(self):
        ttk.Label(self.settings, text='Hipóteses do projeto', style='Section.TLabel').pack(anchor='w', pady=(0, 12))
        tabs = ttk.Notebook(self.settings)
        tabs.pack(fill='both', expand=True)
        bodies = []
        for title in ('Materiais e análise', 'Armaduras', 'Opções avançadas'):
            page = ttk.Frame(tabs)
            tabs.add(page, text=title)
            bodies.append(self._scroll_content(page))
        basic, rebar, advanced = bodies
        self._field(basic, 0, 'Recobrimento nominal [mm]', 'var_cover')
        self._field(basic, 1, 'Classe do aço', 'var_fyk', ['A400', 'A500'])
        ttk.Label(basic, text='Betão importado').grid(row=2, column=0, sticky='w', pady=7)
        ttk.Label(basic, textvariable=getattr(self.app, 'var_concrete_detected', self.app.var_concrete_default)).grid(row=2, column=1, sticky='w')
        self._field(basic, 3, 'Modo de cálculo', 'var_calc_mode', ['Pré-dimensionamento', 'Dimensionamento'])
        self._field(basic, 4, 'Comprimento efetivo y / L', 'var_l0y')
        self._field(basic, 5, 'Comprimento efetivo z / L', 'var_l0z')
        self._field(basic, 6, 'Combinação ELS (número)', 'var_service_case')
        ttk.Label(basic, text='Sem combinação indicada: a avaliação ELS permanece simplificada.', style='Subtle.TLabel').grid(row=7, column=0, columnspan=2, sticky='w', pady=(0, 8))
        self._field(basic, 8, 'Humidade relativa [%]', 'var_creep_RH')
        self._field(basic, 9, 'Idade do betão ao carregamento [dias]', 'var_creep_t0')
        ttk.Label(basic, text='Fluência e dimensão equivalente: cálculo automático.', style='Subtle.TLabel').grid(row=10, column=0, columnspan=2, sticky='w')
        self._field(rebar, 0, 'Estratégia de seleção', 'var_rebar_strategy', ['Económica', 'Equilibrada', 'Robusta'])
        ttk.Label(rebar, text='Económica: menor área de aço. Equilibrada: utilização próxima do alvo.\nRobusta: menor utilização resistente.', wraplength=700, style='Subtle.TLabel').grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 16))
        self.equilibrium = ttk.LabelFrame(rebar, text='Critérios da estratégia equilibrada')
        self.equilibrium.grid(row=2, column=0, columnspan=2, sticky='ew')
        for i, (label, name) in enumerate([('Utilização alvo [-]', 'var_eta_target'), ('Utilização mínima [-]', 'var_eta_min'), ('Utilização máxima [-]', 'var_eta_max'), ('Excesso máximo de armadura [-]', 'var_as_excess')]):
            self._field(self.equilibrium, i, label, name)
        def strategy(*_):
            enabled = str(self.app.var_rebar_strategy.get()).lower().startswith(('equil', 'balanc'))
            for w in walk(self.equilibrium):
                if isinstance(w, ttk.Entry): w.state(['!disabled'] if enabled else ['disabled'])
        self.app.var_rebar_strategy.trace_add('write', strategy)
        strategy()
        from columns_ec2.runtime.loader import runtime_object
        self._field(advanced, 0, 'Norma / motor de cálculo', 'var_code_backend', runtime_object('BACKEND_DISPLAY_CHOICES_V59'))
        ttk.Checkbutton(advanced, text='Reduzir para casos governantes', variable=self.app.var_reduce_cases).grid(row=1, column=0, columnspan=2, sticky='w', pady=12)
        self._field(advanced, 2, 'Classe de desenvolvimento (EC2:2023)', 'var_ec23_strength_class', ['CS', 'CN', 'CR'])
        self._field(advanced, 3, 'Idade de referência (EC2:2023) [dias]', 'var_ec23_tref')
        self._field(advanced, 4, 'Idade ao carregamento (EC2:2023) [dias]', 'var_ec23_t0')
        ttk.Label(advanced, text='Consulte a cobertura do motor na área Diagnóstico para rever o âmbito das verificações.', style='Subtle.TLabel', wraplength=700).grid(row=5, column=0, columnspan=2, sticky='w', pady=16)
        self._field(advanced, 6, 'Idioma das saídas', 'var_language', ['PT', 'EN-UK'])

    def _exports(self):
        body = self._scroll_content(self.exports)
        ttk.Label(body, text='Documentação do projeto', style='Section.TLabel').pack(anchor='w', pady=(0, 12))
        self.export_hint = ttk.Label(body, text='Calcule o projeto para disponibilizar as exportações.', style='Subtle.TLabel', wraplength=700)
        self.export_hint.pack(anchor='w', pady=(0, 18))
        self.export_buttons = []
        for title, text, method in [('Excel de cálculo', 'Dados, casos governantes, resultados e verificações detalhadas.', 'export_excel'), ('Relatório PDF', 'Resumo, relatório técnico ou memória de cálculo.', 'export_pdf_report'), ('Quadro de pilares DXF', 'Quadro organizado por prumada e piso para edição em CAD.', 'export_columns_dxf')]:
            box = ttk.LabelFrame(body, text=title)
            box.pack(fill='x', pady=(0, 16))
            ttk.Label(box, text=text, wraplength=700).pack(anchor='w', pady=(0, 8))
            if method == 'export_pdf_report':
                ttk.Combobox(box, textvariable=self.app.var_pdf_level, values=['Resumo executivo', 'Relatório técnico', 'Memória de cálculo'], state='readonly', width=28).pack(anchor='w', pady=(0, 10))
            # Legacy versions expose different names for the DXF command.
            if method == 'export_columns_dxf':
                command = next((getattr(self.app, n) for n in ('export_columns_dxf', 'export_dxf') if hasattr(self.app, n)), None)
            else: command = getattr(self.app, method)
            if command is None:
                from columns_ec2.runtime.loader import runtime_object
                command = lambda: runtime_object('_export_columns_dxf_rc25')(self.app)
            b = ttk.Button(box, text='Exportar', command=lambda c=command: self._export(c))
            b.pack(anchor='w')
            self.export_buttons.append(b)

    def _toolbar(self):
        self.nb.grid_configure(row=1)
        self.right.rowconfigure(0, weight=0)
        self.right.rowconfigure(1, weight=1)
        bar = ttk.Frame(self.right, padding=(12, 8))
        bar.grid(row=0, column=0, sticky='ew')
        self.page_title = ttk.Label(bar, text='', style='Section.TLabel')
        self.page_title.pack(side='left')
        self.calc_button = ttk.Button(bar, text='Calcular  F5', command=self.calculate, style='Primary.TButton')
        self.calc_button.pack(side='right', padx=(8, 0))
        self.import_button = ttk.Button(bar, text='Importar ficheiro', command=self.import_data)
        self.import_button.pack(side='right')
        # These are the only global import/calculate actions.
        for tab in (getattr(self.app, 'tab_input', None),):
            if tab is None: continue
            actions = ttk.Frame(tab, padding=8)
            actions.pack(side='bottom', fill='x')
            ttk.Button(actions, text='Colar tabela', command=lambda: self._import(self.app.paste_clipboard)).pack(side='left')
            ttk.Button(actions, text='Modelo de tabela', command=self.app.export_template).pack(side='left', padx=8)
        # Existing table widgets may use grid, so create filter controls in a
        # dedicated notebook page rather than mixing geometry managers.
        self.filters = self._new_page('Filtrar resultados')
        self.failure_labels = {'Todos': 'Todos', 'Pormenorização': 'pormenorizacao', 'Armadura insuficiente': 'armadura_insuficiente', 'Esbelteza': 'esbelteza', 'Resistência biaxial': 'resistencia_biaxial', 'Dados incompletos': 'dados_incompletos', 'Outra': 'outra'}
        self.failure_filter = tk.StringVar(master=self.app, value='Todos')
        for i, (label, name, values) in enumerate([('Barra', 'var_filter_member', None), ('Estado', 'var_filter_status', ['Todos', 'OK', 'Aviso', 'Falha', 'Pré-dimensionado']), ('Tipo de falha', 'var_filter_fail', list(self.failure_labels))]):
            widget = self._field(self.filters, i, label, name, values)
            if name == 'var_filter_fail': widget.configure(textvariable=self.failure_filter)
        ttk.Button(self.filters, text='Aplicar aos resultados', command=self._filter).grid(row=3, column=0, pady=16, sticky='w')
        ttk.Button(self.filters, text='Limpar filtros', command=self._clear_filters).grid(row=3, column=1, pady=16, sticky='w')
        self.all_tabs.append(str(self.filters))
        self.groups['results'].append(str(self.filters))

    def _filter(self):
        self.app.var_filter_fail.set(self.failure_labels[self.failure_filter.get()])
        self.app.apply_filters()
        self.show('results')
        self.nb.select(self.app.tab_results)

    def _clear_filters(self):
        self.failure_filter.set('Todos')
        self.app.clear_filters()

    def _tab_changed(self, _event=None):
        # Legacy import callbacks can select a formerly hidden tab directly.
        selected = self.nb.select()
        for group, tabs in self.groups.items():
            if selected in tabs and group != self.group:
                self.show(group, selected)
                break

    def show(self, group, selected=None):
        self.group = group
        visible = self.groups[group]
        for t in self.all_tabs:
            if t not in visible: self.nb.hide(t)
        for t in visible:
            self.nb.insert('end', t)
        if visible: self.nb.select(selected or visible[0])
        titles = {'home': 'Visão geral', 'data': 'Dados de entrada', 'settings': 'Configuração', 'results': 'Revisão de resultados', 'export': 'Exportar', 'diagnostics': 'Diagnóstico e rastreabilidade', 'help': 'Ajuda e referências'}
        self.page_title.configure(text=titles[group])
        for key, b in self.nav.items():
            b.configure(style='Selected.Nav.TButton' if key == group else 'Nav.TButton')

    def _signature(self):
        return tuple((n, str(getattr(self.app, n).get())) for n in PARAMETERS if hasattr(self.app, n))

    def _import(self, command):
        if self.busy or self._thread_running(): return
        command()
        self._poll(schedule=False)
        if len(self.app.df_clean): self.show('data', str(self.app.tab_input))

    def import_data(self):
        self._import(self.app.import_file)

    def calculate(self):
        if self.busy or self._thread_running(): return
        if self.app.df_clean.empty:
            messagebox.showinfo('Dados de entrada', 'Importe uma tabela de esforços antes de calcular.', parent=self.app)
            self.show('data')
            return
        self.run_signature = self._signature()
        self.run_data_token = id(self.app.df_clean)
        previous_thread = getattr(self.app, 'analysis_thread', None)
        self.app.run_design()
        self.awaiting_results = getattr(self.app, 'analysis_thread', None) is not previous_thread
        self._poll(schedule=False)

    def _thread_running(self):
        thread = getattr(self.app, 'analysis_thread', None)
        return thread is not None and thread.is_alive()

    def _export(self, command):
        if not self._current_results():
            messagebox.showinfo('Resultados', 'Calcule novamente após alterar os dados ou as hipóteses.', parent=self.app)
            return
        command()

    def _current_results(self):
        return (not self.app.df_results.empty and not self.busy
                and self.result_signature == self._signature()
                and self.result_data_token == id(self.app.df_clean))

    def _poll(self, schedule=True):
        running = self._thread_running()
        self.busy = running or self.awaiting_results
        data = self.app.df_clean
        results = self.app.df_results
        token = id(results)
        finished = (not running and (not self.awaiting_results or
                    (self.app.progress_var.get() >= 99 and
                     str(self.app.status_var.get()).startswith('Cálculo concluído'))))
        if not results.empty and token != self.result_token and finished:
            self.result_token = token
            if self.awaiting_results:
                self.result_signature = self.run_signature
                self.result_data_token = getattr(self, 'run_data_token', None)
                self.awaiting_results = False
                self.busy = False
                self.show('results')
            status = results.get('estado_global', results.get('status'))
            counts = status.value_counts().to_dict() if status is not None else {}
            self.overview.set(f'{len(results)} casos calculados  ·  {counts.get("OK", 0)} OK  ·  {counts.get("Aviso", 0)} avisos  ·  {counts.get("Falha", 0)} falhas')
        if self.awaiting_results and not running and str(self.app.status_var.get()).startswith('Falha na análise'):
            self.awaiting_results = False
            self.busy = False
            self.result_signature = None
        summary_token = (id(self.app.df_summary), self.result_token)
        if not results.empty and not self.busy and summary_token != self.summary_token:
            self.summary_token = summary_token
            self._refresh_decisions()
        if id(data) != self.data_token:
            self.data_token = id(data)
            name = os.path.basename(getattr(self.app, 'input_file_path', '') or '')
            self.file_label.configure(text=name or ('Tabela importada' if len(data) else 'Nenhum ficheiro importado'))
            members = data['member'].nunique() if 'member' in data else 0
            self.count_label.configure(text=f'{len(data):,} registos  ·  {members} barras'.replace(',', ' ') if len(data) else 'Importe uma tabela para começar')
        self.calc_button.state(['disabled'] if self.busy or data.empty else ['!disabled'])
        self.import_button.state(['disabled'] if self.busy else ['!disabled'])
        current = self._current_results()
        for b in self.export_buttons: b.state(['!disabled'] if current else ['disabled'])
        hint = 'A calcular…' if self.busy else ('Resultados disponíveis para exportação.' if current else ('Dados ou hipóteses alterados. Volte a calcular.' if not results.empty else 'Calcule o projeto para disponibilizar as exportações.'))
        self.export_hint.configure(text=hint)
        self.step_label.configure(text='A calcular…' if self.busy else ('Resultados atualizados' if current else ('Pronto para configurar' if not data.empty else 'A aguardar dados')))
        if schedule: self._after_id = self.app.after(500, self._poll)

    def _destroy(self, event):
        if event.widget is self.app and self._after_id:
            self.app.after_cancel(self._after_id)
            self.app.after_cancel(self._drain_id)
            self._after_id = None


def install_workspace(app):
    app.workspace = Workspace(app)
    return app.workspace
