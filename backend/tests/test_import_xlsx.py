import io
import zipfile
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.services.imports.fields import FileType
from app.services.imports.normalize import DateFormat, DecimalSeparator
from app.services.imports.parsing import FileRejected, NativeType, ParsedRow, parse_file
from app.services.imports.validation import Dimensions, RowValidator, ValidationOptions

HEADER = ["Data", "Unidade", "Processo", "Valor", "Natureza", "Documento"]


def xlsx(sheets: dict[str, list[list]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_celulas_nativas_viram_texto_canonico_tipado():
    content = xlsx(
        {
            "Despesas": [
                HEADER,
                [datetime(2026, 9, 30), "CD-01", "REC", 1234.56, "direct", "NF-1"],
                [None, None, None, None, None, None],  # linha vazia é ignorada
                [date(2026, 9, 30), "CD-01", "REC", 10, "direct", 123],
            ]
        }
    )
    parsed = parse_file("despesas.xlsx", content)
    assert parsed.sheets == ["Despesas"]
    assert parsed.sheet == "Despesas"
    assert parsed.columns == HEADER
    first, second = parsed.rows
    assert first.row_number == 2
    assert first.values["Data"] == "2026-09-30"
    assert first.values["Valor"] == "1234.56"
    assert first.native_types == {
        "Data": NativeType.DATE,
        "Valor": NativeType.NUMBER,
    }
    assert second.row_number == 4
    assert second.values["Documento"] == "123"


def test_float_sem_ruido_binario():
    parsed = parse_file("x.xlsx", xlsx({"A": [["v"], [0.1], [1e-05], [3.0]]}))
    assert [r.values["v"] for r in parsed.rows] == ["0.1", "0.00001", "3"]


def test_escolha_de_aba():
    content = xlsx({"Resumo": [["x"], [1]], "Dados": [["y"], [2]]})
    parsed = parse_file("x.xlsx", content, sheet="Dados")
    assert parsed.sheets == ["Resumo", "Dados"]
    assert parsed.columns == ["y"]
    with pytest.raises(FileRejected) as exc:
        parse_file("x.xlsx", content, sheet="Outra")
    assert exc.value.code == "UNKNOWN_SHEET"


def test_colunas_vazias_a_direita_sao_ignoradas():
    parsed = parse_file("x.xlsx", xlsx({"A": [["a", "b", None, None], [1, 2, None, None]]}))
    assert parsed.columns == ["a", "b"]


def test_staging_preserva_tipos_nativos():
    row = ParsedRow(2, {"Valor": "1234.56"}, {"Valor": NativeType.NUMBER})
    assert ParsedRow.from_staging(2, row.to_staging()) == row
    plain = ParsedRow(3, {"a": "1"})
    assert plain.to_staging() == {"a": "1"}


def macro_file() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/vbaProject.bin", b"macro")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"nao e zip", "UNSUPPORTED_FILE_TYPE"),
        (macro_file(), "MACROS_NOT_ALLOWED"),
    ],
)
def test_xlsx_rejeitado(content, code):
    with pytest.raises(FileRejected) as exc:
        parse_file("x.xlsx", content)
    assert exc.value.code == code


def test_xlsm_nao_e_suportado():
    with pytest.raises(FileRejected) as exc:
        parse_file("x.xlsm", b"qualquer")
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"


def test_numero_nativo_ignora_convencao_brasileira_e_texto_segue_convencao():
    dims = Dimensions(
        units={"CD-01": 1}, processes={"REC": 2}, accounts={}, cost_centers={}, drivers={}
    )
    mapping = {
        "competence_date": "Data",
        "unit_code": "Unidade",
        "process_code": "Processo",
        "amount": "Valor",
        "nature": "Natureza",
        "source_key": "Documento",
    }
    validator = RowValidator(
        FileType.EXPENSES,
        mapping,
        {},
        ValidationOptions(DateFormat.DMY, DecimalSeparator.COMMA),
        dims,
    )
    native = ParsedRow(
        2,
        {
            "Data": "2026-09-30",
            "Unidade": "CD-01",
            "Processo": "REC",
            "Valor": "1234.56",
            "Natureza": "direct",
            "Documento": "NF-1",
        },
        {"Data": NativeType.DATE, "Valor": NativeType.NUMBER},
    )
    result = validator.validate(native)
    assert result.is_valid
    assert result.values["amount"] == Decimal("1234.56")
    assert result.values["competence_date"] == date(2026, 9, 30)

    # O mesmo texto digitado (não nativo) segue a convenção brasileira escolhida.
    typed = ParsedRow(3, {**native.values, "Data": "30/09/2026", "Valor": "1.234,56"})
    assert validator.validate(typed).values["amount"] == Decimal("1234.56")
    wrong = ParsedRow(4, {**native.values, "Valor": "1234.56"})
    assert not validator.validate(wrong).is_valid
