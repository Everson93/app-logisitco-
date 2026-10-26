from datetime import date
from decimal import Decimal

from app.services.imports.fields import FileType
from app.services.imports.normalize import DateFormat, DecimalSeparator
from app.services.imports.parsing import ParsedRow
from app.services.imports.validation import (
    Dimensions,
    IssueCode,
    RowValidator,
    Severity,
    ValidationOptions,
    mark_duplicates,
)

DIMS = Dimensions(
    units={"CD-01": 1},
    processes={"REC": 10, "PICK": 11},
    accounts={"6101": 100},
    cost_centers={},
    drivers={"pallet_received": (50, "pallet")},
)

EXPENSE_MAPPING = {
    name: name
    for name in (
        "competence_date",
        "unit_code",
        "process_code",
        "account_code",
        "description",
        "amount",
        "nature",
        "source_key",
    )
}


def expense_row(n=2, **overrides):
    values = {
        "competence_date": "2026-09-30",
        "unit_code": "CD-01",
        "process_code": "REC",
        "account_code": "6101",
        "description": "Mão de obra",
        "amount": "24000.00",
        "nature": "direct",
        "source_key": f"ERP-{n}",
    }
    return ParsedRow(n, {**values, **overrides})


def validator(file_type=FileType.EXPENSES, mapping=None, defaults=None, options=None):
    return RowValidator(
        file_type,
        mapping if mapping is not None else EXPENSE_MAPPING,
        defaults or {},
        options or ValidationOptions(),
        DIMS,
    )


def codes(result):
    return [i.code for i in result.issues]


def test_despesa_valida_normalizada():
    result = validator().validate(expense_row())
    assert result.is_valid
    assert result.values == {
        "unit_id": 1,
        "process_id": 10,
        "account_id": 100,
        "cost_center_id": None,
        "competence_date": date(2026, 9, 30),
        "description": "Mão de obra",
        "amount": Decimal("24000.00"),
        "nature": "direct",
        "source_key": "ERP-2",
    }


def test_campo_obrigatorio_vazio_bloqueia_com_linha_e_coluna():
    result = validator().validate(expense_row(amount=""))
    assert not result.is_valid
    (issue,) = result.issues
    assert (issue.row_number, issue.column, issue.code) == (
        2,
        "amount",
        IssueCode.MISSING_REQUIRED_FIELD,
    )
    assert result.values == {}


def test_data_e_numero_invalidos():
    result = validator().validate(expense_row(competence_date="30/13/2026", amount="abc"))
    assert codes(result) == [IssueCode.INVALID_DATE, IssueCode.INVALID_NUMBER]


def test_mais_de_duas_casas_decimais_em_valor():
    assert codes(validator().validate(expense_row(amount="10.001"))) == [IssueCode.INVALID_NUMBER]


def test_dimensoes_desconhecidas():
    result = validator().validate(expense_row(unit_code="X", process_code="Y", account_code="Z"))
    assert codes(result) == [
        IssueCode.UNKNOWN_UNIT,
        IssueCode.UNKNOWN_PROCESS,
        IssueCode.UNKNOWN_ACCOUNT,
    ]


def test_natureza_invalida():
    assert codes(validator().validate(expense_row(nature="outro"))) == [IssueCode.INVALID_NATURE]


def test_custo_compartilhado_sem_processo_e_valido():
    result = validator().validate(expense_row(process_code="", nature="SHARED"))
    assert result.is_valid
    assert result.values["process_id"] is None
    assert result.values["nature"] == "shared"


def test_despesa_direta_sem_unidade_bloqueia():
    result = validator().validate(expense_row(unit_code=""))
    assert codes(result) == [IssueCode.MISSING_REQUIRED_FIELD]


def test_valor_padrao_para_coluna_ausente_e_convencao_brasileira():
    mapping = {k: v for k, v in EXPENSE_MAPPING.items() if k != "unit_code"}
    options = ValidationOptions(DateFormat.DMY, DecimalSeparator.COMMA)
    row = expense_row(competence_date="30/09/2026", amount="1.234,56")
    result = validator(mapping=mapping, defaults={"unit_code": "CD-01"}, options=options).validate(
        row
    )
    assert result.is_valid
    assert result.values["unit_id"] == 1
    assert result.values["amount"] == Decimal("1234.56")


ACTIVITY_MAPPING = {
    n: n
    for n in (
        "activity_date",
        "unit_code",
        "process_code",
        "driver_code",
        "quantity",
        "unit_of_measure",
        "source_key",
    )
}


def activity_row(**overrides):
    values = {
        "activity_date": "2026-09-30",
        "unit_code": "CD-01",
        "process_code": "REC",
        "driver_code": "pallet_received",
        "quantity": "15000",
        "unit_of_measure": "pallet",
        "source_key": "ACT-1",
    }
    return ParsedRow(2, {**values, **overrides})


def test_atividade_quantidade_zero_e_aviso():
    result = validator(FileType.ACTIVITIES, ACTIVITY_MAPPING).validate(activity_row(quantity="0"))
    assert result.is_valid
    assert codes(result) == [IssueCode.ZERO_QUANTITY]
    assert result.issues[0].severity is Severity.WARNING


def test_atividade_quantidade_negativa_bloqueia():
    result = validator(FileType.ACTIVITIES, ACTIVITY_MAPPING).validate(activity_row(quantity="-1"))
    assert codes(result) == [IssueCode.NEGATIVE_QUANTITY]


def test_atividade_unidade_de_medida_incoerente():
    result = validator(FileType.ACTIVITIES, ACTIVITY_MAPPING).validate(
        activity_row(unit_of_measure="box")
    )
    assert codes(result) == [IssueCode.UNIT_OF_MEASURE_MISMATCH]


def test_atividade_direcionador_desconhecido():
    result = validator(FileType.ACTIVITIES, ACTIVITY_MAPPING).validate(
        activity_row(driver_code="xyz")
    )
    assert codes(result) == [IssueCode.UNKNOWN_DRIVER]


BUDGET_MAPPING = {
    n: n
    for n in ("period_start", "period_end", "unit_code", "process_code", "account_code", "amount")
}


def budget_row(n=2, **overrides):
    values = {
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "unit_code": "CD-01",
        "process_code": "REC",
        "account_code": "6101",
        "amount": "24000",
    }
    return ParsedRow(n, {**values, **overrides})


def test_orcamento_zero_e_aviso():
    result = validator(FileType.BUDGETS, BUDGET_MAPPING).validate(budget_row(amount="0"))
    assert result.is_valid
    assert codes(result) == [IssueCode.ZERO_BUDGET]


def test_orcamento_periodo_invertido():
    result = validator(FileType.BUDGETS, BUDGET_MAPPING).validate(
        budget_row(period_end="2026-08-01")
    )
    assert codes(result) == [IssueCode.INVALID_PERIOD]


def test_duplicidade_no_arquivo_bloqueia_a_segunda_linha():
    v = validator()
    results = [
        v.validate(expense_row(2)),
        v.validate(expense_row(3, source_key="ERP-2")),
    ]
    mark_duplicates(FileType.EXPENSES, results, existing_keys=set())
    assert results[0].is_valid
    assert not results[1].is_valid
    assert codes(results[1]) == [IssueCode.DUPLICATE_SOURCE_KEY]


def test_registro_ja_importado_e_aviso_e_marcado():
    results = [validator().validate(expense_row(2))]
    mark_duplicates(FileType.EXPENSES, results, existing_keys={"ERP-2"})
    assert results[0].is_valid
    assert results[0].already_imported
    assert codes(results[0]) == [IssueCode.ALREADY_IMPORTED]


def test_orcamento_duplicado_pela_dimensao():
    v = validator(FileType.BUDGETS, BUDGET_MAPPING)
    results = [v.validate(budget_row(2)), v.validate(budget_row(3, amount="1"))]
    mark_duplicates(FileType.BUDGETS, results, existing_keys=set())
    assert codes(results[1]) == [IssueCode.DUPLICATE_SOURCE_KEY]
