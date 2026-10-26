"""Validação de negócio das linhas mapeadas (seção 10, passos 5 a 8 do pipeline).

Funções puras: recebem as linhas, o mapeamento e os cadastros já carregados, e
devolvem para cada linha os valores normalizados ou os problemas encontrados.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.services.imports.fields import (
    EXPENSE_NATURES,
    FieldKind,
    FieldSpec,
    FileType,
    field_specs,
)
from app.services.imports.normalize import (
    DateFormat,
    DecimalSeparator,
    clean,
    parse_date,
    parse_number,
)
from app.services.imports.parsing import ParsedRow

DATE_LABELS = {DateFormat.ISO: "AAAA-MM-DD", DateFormat.DMY: "DD/MM/AAAA"}


class Severity(StrEnum):
    ERROR = "error"  # bloqueia a linha
    WARNING = "warning"  # a linha segue, mas o usuário é avisado


class IssueCode(StrEnum):
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_DATE = "INVALID_DATE"
    INVALID_NUMBER = "INVALID_NUMBER"
    INVALID_NATURE = "INVALID_NATURE"
    INVALID_PERIOD = "INVALID_PERIOD"
    UNKNOWN_UNIT = "UNKNOWN_UNIT"
    UNKNOWN_PROCESS = "UNKNOWN_PROCESS"
    UNKNOWN_ACCOUNT = "UNKNOWN_ACCOUNT"
    UNKNOWN_COST_CENTER = "UNKNOWN_COST_CENTER"
    UNKNOWN_DRIVER = "UNKNOWN_DRIVER"
    UNIT_OF_MEASURE_MISMATCH = "UNIT_OF_MEASURE_MISMATCH"
    NEGATIVE_QUANTITY = "NEGATIVE_QUANTITY"
    ZERO_QUANTITY = "ZERO_QUANTITY"
    ZERO_BUDGET = "ZERO_BUDGET"
    DUPLICATE_SOURCE_KEY = "DUPLICATE_SOURCE_KEY"
    ALREADY_IMPORTED = "ALREADY_IMPORTED"


@dataclass(frozen=True)
class Issue:
    row_number: int
    column: str | None
    code: IssueCode
    message: str
    severity: Severity = Severity.ERROR


@dataclass(frozen=True)
class ValidationOptions:
    date_format: DateFormat = DateFormat.ISO
    decimal_separator: DecimalSeparator = DecimalSeparator.DOT


@dataclass(frozen=True)
class Dimensions:
    """Cadastros ativos, por código."""

    units: Mapping[str, int]
    processes: Mapping[str, int]
    accounts: Mapping[str, int]
    cost_centers: Mapping[str, int]
    drivers: Mapping[str, tuple[int, str]]  # código -> (id, unidade de medida)


@dataclass
class RowResult:
    row_number: int
    values: dict[str, Any] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    already_imported: bool = False

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity is Severity.ERROR for issue in self.issues)


def budget_key(values: Mapping[str, Any]) -> tuple:
    """Chave de negócio do orçamento: período + dimensão."""
    return (
        values["period_start"],
        values["unit_id"],
        values["process_id"],
        values.get("account_id"),
    )


class RowValidator:
    def __init__(
        self,
        file_type: FileType,
        mapping: Mapping[str, str],
        defaults: Mapping[str, str],
        options: ValidationOptions,
        dimensions: Dimensions,
    ):
        self.file_type = file_type
        self.specs = field_specs(file_type)
        self.mapping = mapping
        self.defaults = defaults
        self.options = options
        self.dims = dimensions

    def _raw(self, row: ParsedRow, name: str) -> str:
        column = self.mapping.get(name)
        value = clean(row.values.get(column)) if column else ""
        return value or clean(self.defaults.get(name))

    def _column(self, name: str) -> str:
        return self.mapping.get(name, name)

    def _convert(self, row: ParsedRow, spec: FieldSpec, result: RowResult) -> Any:
        raw = self._raw(row, spec.name)
        if not raw:
            if spec.required:
                result.issues.append(
                    Issue(
                        row.row_number,
                        self._column(spec.name),
                        IssueCode.MISSING_REQUIRED_FIELD,
                        f"Campo obrigatório '{spec.name}' está vazio.",
                    )
                )
            return None

        if spec.kind is FieldKind.DATE:
            fmt = self.options.date_format
            value = parse_date(raw, fmt)
            if value is None:
                result.issues.append(
                    Issue(
                        row.row_number,
                        self._column(spec.name),
                        IssueCode.INVALID_DATE,
                        f"Data '{raw}' não está no formato {DATE_LABELS[fmt]}.",
                    )
                )
            return value

        if spec.kind in (FieldKind.MONEY, FieldKind.QUANTITY):
            value = parse_number(raw, self.options.decimal_separator)
            if value is None:
                result.issues.append(
                    Issue(
                        row.row_number,
                        self._column(spec.name),
                        IssueCode.INVALID_NUMBER,
                        f"Valor '{raw}' não é um número válido.",
                    )
                )
                return None
            places = Decimal("0.01") if spec.kind is FieldKind.MONEY else Decimal("0.0001")
            if value != value.quantize(places):
                result.issues.append(
                    Issue(
                        row.row_number,
                        self._column(spec.name),
                        IssueCode.INVALID_NUMBER,
                        f"Valor '{raw}' tem mais casas decimais que o permitido.",
                    )
                )
                return None
            return value

        return raw

    def _lookup(
        self,
        row: ParsedRow,
        result: RowResult,
        name: str,
        code: str | None,
        table: Mapping[str, Any],
        issue: IssueCode,
        label: str,
    ) -> Any:
        if code is None:
            return None
        if code not in table:
            result.issues.append(
                Issue(
                    row.row_number,
                    self._column(name),
                    issue,
                    f"{label} '{code}' não está cadastrado(a).",
                )
            )
            return None
        return table[code]

    def validate(self, row: ParsedRow) -> RowResult:
        result = RowResult(row_number=row.row_number)
        raw = {name: self._convert(row, spec, result) for name, spec in self.specs.items()}
        values: dict[str, Any] = {}

        def lookup(name: str, table, issue, label, target: str):
            values[target] = self._lookup(row, result, name, raw.get(name), table, issue, label)

        if "unit_code" in raw:
            lookup("unit_code", self.dims.units, IssueCode.UNKNOWN_UNIT, "Unidade", "unit_id")
        if "process_code" in raw:
            lookup(
                "process_code",
                self.dims.processes,
                IssueCode.UNKNOWN_PROCESS,
                "Processo",
                "process_id",
            )
        if "account_code" in raw:
            lookup(
                "account_code", self.dims.accounts, IssueCode.UNKNOWN_ACCOUNT, "Conta", "account_id"
            )
        if "cost_center_code" in raw:
            lookup(
                "cost_center_code",
                self.dims.cost_centers,
                IssueCode.UNKNOWN_COST_CENTER,
                "Centro de custo",
                "cost_center_id",
            )

        match self.file_type:
            case FileType.EXPENSES:
                self._expense_rules(row, raw, values, result)
            case FileType.ACTIVITIES:
                self._activity_rules(row, raw, values, result)
            case FileType.BUDGETS:
                self._budget_rules(row, raw, values, result)

        if result.is_valid:
            result.values = values
        return result

    def _expense_rules(self, row, raw, values, result) -> None:
        nature = raw["nature"].lower() if raw["nature"] else None
        if nature is not None and nature not in EXPENSE_NATURES:
            result.issues.append(
                Issue(
                    row.row_number,
                    self._column("nature"),
                    IssueCode.INVALID_NATURE,
                    f"Natureza '{raw['nature']}' inválida. Use: {', '.join(EXPENSE_NATURES)}.",
                )
            )
        if (
            nature == "direct"
            and raw.get("unit_code") is None
            and raw.get("cost_center_code") is None
        ):
            result.issues.append(
                Issue(
                    row.row_number,
                    self._column("unit_code"),
                    IssueCode.MISSING_REQUIRED_FIELD,
                    "Despesa direta precisa de unidade ou centro de custo.",
                )
            )
        values.update(
            competence_date=raw["competence_date"],
            description=raw.get("description"),
            amount=raw["amount"],
            nature=nature,
            source_key=raw["source_key"],
        )

    def _activity_rules(self, row, raw, values, result) -> None:
        driver = self._lookup(
            row,
            result,
            "driver_code",
            raw["driver_code"],
            self.dims.drivers,
            IssueCode.UNKNOWN_DRIVER,
            "Direcionador",
        )
        uom = raw["unit_of_measure"]
        if driver is not None and uom is not None and uom != driver[1]:
            result.issues.append(
                Issue(
                    row.row_number,
                    self._column("unit_of_measure"),
                    IssueCode.UNIT_OF_MEASURE_MISMATCH,
                    f"Unidade de medida '{uom}' difere da do direcionador ('{driver[1]}').",
                )
            )
        quantity = raw["quantity"]
        if quantity is not None and quantity < 0:
            result.issues.append(
                Issue(
                    row.row_number,
                    self._column("quantity"),
                    IssueCode.NEGATIVE_QUANTITY,
                    "Quantidade negativa não é permitida para atividades.",
                )
            )
        elif quantity == 0:
            result.issues.append(
                Issue(
                    row.row_number,
                    self._column("quantity"),
                    IssueCode.ZERO_QUANTITY,
                    "Quantidade zero: o custo unitário deste escopo ficará N/D.",
                    Severity.WARNING,
                )
            )
        values.update(
            activity_date=raw["activity_date"],
            driver_id=driver[0] if driver else None,
            quantity=quantity,
            unit_of_measure=uom,
            source_key=raw["source_key"],
        )

    def _budget_rules(self, row, raw, values, result) -> None:
        start, end = raw["period_start"], raw["period_end"]
        if isinstance(start, date) and isinstance(end, date) and end < start:
            result.issues.append(
                Issue(
                    row.row_number,
                    self._column("period_end"),
                    IssueCode.INVALID_PERIOD,
                    "O fim do período é anterior ao início.",
                )
            )
        if raw["amount"] == 0:
            result.issues.append(
                Issue(
                    row.row_number,
                    self._column("amount"),
                    IssueCode.ZERO_BUDGET,
                    "Orçamento zero: o desvio percentual ficará sem base orçamentária.",
                    Severity.WARNING,
                )
            )
        values.update(period_start=start, period_end=end, amount=raw["amount"])


def mark_duplicates(
    file_type: FileType,
    results: list[RowResult],
    existing_keys: set,
) -> None:
    """Marca duplicidades dentro do arquivo (erro) e já importadas (aviso; ignoradas no commit).

    `existing_keys` contém `source_key` já gravadas ou, para orçamento, as chaves
    de dimensão de `budget_key`.
    """
    seen: dict[Any, int] = {}
    for result in results:
        if not result.is_valid:
            continue
        key = (
            budget_key(result.values)
            if file_type is FileType.BUDGETS
            else result.values["source_key"]
        )
        column = None if file_type is FileType.BUDGETS else "source_key"
        if key in seen:
            result.issues.append(
                Issue(
                    result.row_number,
                    column,
                    IssueCode.DUPLICATE_SOURCE_KEY,
                    f"Registro repetido no arquivo (mesma chave da linha {seen[key]}).",
                )
            )
            result.values = {}
            continue
        seen[key] = result.row_number
        if key in existing_keys:
            result.already_imported = True
            result.issues.append(
                Issue(
                    result.row_number,
                    column,
                    IssueCode.ALREADY_IMPORTED,
                    "Registro já importado anteriormente; será ignorado na confirmação.",
                    Severity.WARNING,
                )
            )
