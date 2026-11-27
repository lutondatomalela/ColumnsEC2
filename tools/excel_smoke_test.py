"""Regression checks for complete, atomic single-pass workbook output."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import openpyxl
from columns_ec2.excel_export import Value, write


def main():
    res = pd.DataFrame([dict(member='1', case='101', name='P1', prumada=None,
                            story='Piso 1', material='C30/37', n_ed_kN=500.125,
                            my_ed_kNm=20.25, mz_ed_kNm=10.5, as_prov_mm2=804.2477,
                            utilizacao=0.75, status='Aviso', estado_global='Aviso',
                            mrd_y_kNm=40., mrd_z_kNm=35., biaxial_alpha=2.)])
    source = res.copy(deep=True)
    snapshot = SimpleNamespace(df_results=res, df_summary=res.copy(),
        df_pair=pd.DataFrame(), df_calc_input=pd.DataFrame(),
        df_clean=pd.DataFrame({'member': ['1', '1'], 'note': ['=1+1', 'Ø12']}),
        shortlists=pd.DataFrame(), notes=pd.DataFrame(), language='PT',
        info=pd.DataFrame([['Programa', 'ColumnsEC2'], ['Norma', 'EC2']], columns=['Campo', 'Valor']),
        parameters=pd.DataFrame([['Recobrimento [mm]', 30]], columns=['Parâmetro', 'Valor']))
    original_save = openpyxl.Workbook.save
    saves = []
    def save_once(book, path):
        saves.append(path)
        return original_save(book, path)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'output.xlsx'
        with patch.object(openpyxl, 'load_workbook', side_effect=AssertionError('Writer reopened a workbook')):
            with patch.object(openpyxl.Workbook, 'save', save_once): write(snapshot, path)
        assert len(saves) == 1
        pd.testing.assert_frame_equal(snapshot.df_results, source)
        wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
        assert len(wb.sheetnames) == 22
        rows = list(wb['05_Resultados'].values)
        values = dict(zip(rows[0], rows[1]))
        assert values['n_ed_kN'] == 500.125 and values['as_prov_mm2'] == 804.2477
        assert values['prumada'] == 'P1'
        assert wb['02_Entrada_Dados']['B2'].value == '=1+1'
        assert wb['02_Entrada_Dados']['B2'].data_type == 's'
        wb.close()
        before = path.read_bytes()
        with patch('columns_ec2.excel_export.os.replace', side_effect=PermissionError('Locked file')):
            try: write(snapshot, path)
            except PermissionError: pass
            else: raise AssertionError('Replacement failure was hidden')
        assert path.read_bytes() == before
        assert not list(Path(directory).glob('.columnsec2-*.xlsx'))
    print('ColumnsEC2 Excel single-pass / fidelity / atomicity: OK')


if __name__ == '__main__': main()
