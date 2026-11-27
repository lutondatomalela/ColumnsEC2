"""Exercise the desktop workflow with synthetic data (requires a display)."""
from pathlib import Path
import sys
import tempfile
import time
from tkinter import messagebox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from columns_ec2.gui.app import create_app


def main():
    app = create_app()
    errors = []
    completed = []
    app.report_callback_exception = lambda *e: (errors.append(str(e)), app.quit())
    original_dialogs = {n: getattr(messagebox, n) for n in ('showinfo', 'showwarning', 'showerror', 'askyesno')}
    messagebox.showinfo = messagebox.showwarning = lambda *a, **k: None
    messagebox.showerror = lambda *a, **k: errors.append(str(a))
    messagebox.askyesno = lambda *a, **k: False
    ws = app.workspace
    deadline = time.monotonic() + 90
    data = pd.DataFrame([
        {'Member/Node/Case': f'1/{node}/101 (C)', 'FX (kN)': '500',
         'FY (kN)': '0', 'FZ (kN)': '0', 'MX (kNm)': '0', 'MY (kNm)': '20',
         'MZ (kNm)': '10', 'Length (m)': '3', 'Material': 'C30/37',
         'HY (cm)': '30', 'HZ (cm)': '30', 'AX (cm2)': '900',
         'IY (cm4)': '67500', 'IZ (cm4)': '67500', 'Name': 'P1', 'Story': 'Piso 1'}
        for node in (1, 2)
    ])

    def finish():
        try:
            ws._poll(schedule=False)
            assert ws._current_results()
            assert len(ws.decision_tree.get_children()) == 1
            for group in ws.groups:
                ws.show(group)
                app.update_idletasks()
                assert ws.group == group
            ws.show('results')
            first = ws.decision_tree.get_children()[0]
            assert ws.decision_tree.item(first, 'values')[0] == 'P1'
            ws.decision_tree.selection_set(first)
            ws._details()
            with tempfile.TemporaryDirectory() as directory:
                app._write_pdf(str(Path(directory) / 'report.pdf'))
                assert (Path(directory) / 'report.pdf').read_bytes().startswith(b'%PDF')
            app.var_cover.set('40')
            ws._poll(schedule=False)
            assert not ws._current_results()
            assert ws.export_buttons[0].instate(['disabled'])
            app.geometry('1000x650')
            ws.show('settings')
            app.update_idletasks()
            assert app.winfo_width() == 1000
            completed.append(True)
        except Exception as e:
            errors.append(repr(e))
        finally:
            app.quit()

    def poll():
        if time.monotonic() > deadline:
            errors.append('Calculation did not complete within 90 seconds')
            app.quit()
        elif not ws._thread_running() and not app.df_results.empty:
            app.after(1600, finish)
        else:
            app.after(100, poll)

    def start():
        assert ws.calc_button.instate(['disabled'])
        assert ws.export_buttons[0].instate(['disabled'])
        app.load_df(data, source='Synthetic interface check')
        app.var_calc_mode.set('Pré-dimensionamento')
        ws.calculate()
        app.after(100, poll)

    try:
        app.after(600, start)
        app.mainloop()
    finally:
        for name, command in original_dialogs.items(): setattr(messagebox, name, command)
        app.destroy()
    assert completed and not errors, errors
    print('ColumnsEC2 GUI workflow: OK')


if __name__ == '__main__':
    main()
