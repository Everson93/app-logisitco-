from datetime import date
from decimal import Decimal

import pytest

from app.services.imports.fields import FileType, normalize_header, suggest_mapping
from app.services.imports.normalize import DateFormat, DecimalSeparator, parse_date, parse_number
from app.services.imports.parsing import FileRejected, parse_csv


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1234,56", Decimal("1234.56")),
        ("1.234,56", Decimal("1234.56")),
        ("R$ 1.234.567,89", Decimal("1234567.89")),
        ("-10,5", Decimal("-10.5")),
        ("100", Decimal(100)),
    ],
)
def test_numero_brasileiro(text, expected):
    assert parse_number(text, DecimalSeparator.COMMA) == expected


@pytest.mark.parametrize("text", ["1,234.56", "12.34", "1.23,4.5", "abc", "1..000,00", ""])
def test_numero_brasileiro_ambiguo_ou_invalido_vira_erro(text):
    assert parse_number(text, DecimalSeparator.COMMA) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1234.56", Decimal("1234.56")), ("1,234.56", Decimal("1234.56"))],
)
def test_numero_com_ponto_decimal(text, expected):
    assert parse_number(text, DecimalSeparator.DOT) == expected


def test_numero_com_virgula_rejeitado_na_convencao_de_ponto():
    assert parse_number("1234,56", DecimalSeparator.DOT) is None


def test_datas():
    assert parse_date("2026-09-30", DateFormat.ISO) == date(2026, 9, 30)
    assert parse_date("30/09/2026", DateFormat.DMY) == date(2026, 9, 30)
    assert parse_date("30/09/2026", DateFormat.ISO) is None
    assert parse_date("30/13/2026", DateFormat.DMY) is None


def test_normalize_header():
    assert normalize_header(" Data de Competência ") == "data_de_competencia"


def test_sugere_mapeamento_por_nome_e_apelido():
    columns = ["Data Competência", "Unidade", "Valor", "Natureza", "Chave Origem", "Outra"]
    assert suggest_mapping(FileType.EXPENSES, columns) == {
        "competence_date": "Data Competência",
        "unit_code": "Unidade",
        "amount": "Valor",
        "nature": "Natureza",
        "source_key": "Chave Origem",
    }


def test_parse_csv_com_ponto_e_virgula_e_linhas_vazias():
    content = b"a;b\n1;2\n\n3;4\n"
    parsed = parse_csv("x.csv", content)
    assert parsed.delimiter == ";"
    assert parsed.columns == ["a", "b"]
    assert [r.values for r in parsed.rows] == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
    assert [r.row_number for r in parsed.rows] == [2, 4]


def test_parse_csv_latin1():
    parsed = parse_csv("x.csv", "descricao\nexpedição\n".encode("cp1252"))
    assert parsed.rows[0].values == {"descricao": "expedição"}


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("dados.xlsx", b"a,b\n", "UNSUPPORTED_FILE_TYPE"),
        ("dados.csv", b"", "EMPTY_FILE"),
        ("dados.csv", b"a,a\n1,2\n", "DUPLICATE_COLUMN"),
        ("dados.csv", b"PK\x03\x04\x00\x00", "UNSUPPORTED_FILE_TYPE"),
    ],
)
def test_parse_csv_rejeita(filename, content, code):
    with pytest.raises(FileRejected) as exc:
        parse_csv(filename, content)
    assert exc.value.code == code
