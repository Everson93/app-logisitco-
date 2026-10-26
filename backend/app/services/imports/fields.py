"""Campos padronizados de cada tipo de arquivo (seção 10 da especificação)."""

import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class FileType(StrEnum):
    EXPENSES = "expenses"
    ACTIVITIES = "activities"
    BUDGETS = "budgets"


class FieldKind(StrEnum):
    TEXT = "text"
    CODE = "code"
    DATE = "date"
    MONEY = "money"
    QUANTITY = "quantity"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: FieldKind
    required: bool
    aliases: tuple[str, ...] = ()


FIELDS: dict[FileType, tuple[FieldSpec, ...]] = {
    FileType.EXPENSES: (
        FieldSpec(
            "competence_date",
            FieldKind.DATE,
            True,
            ("data_competencia", "competencia", "data", "data_lancamento"),
        ),
        FieldSpec("unit_code", FieldKind.CODE, False, ("unidade", "cod_unidade")),
        FieldSpec("process_code", FieldKind.CODE, False, ("processo", "cod_processo")),
        FieldSpec("cost_center_code", FieldKind.CODE, False, ("centro_custo", "centro_de_custo")),
        FieldSpec("account_code", FieldKind.CODE, False, ("conta", "conta_contabil")),
        FieldSpec("description", FieldKind.TEXT, False, ("descricao", "historico")),
        FieldSpec("amount", FieldKind.MONEY, True, ("valor", "valor_rs", "montante")),
        FieldSpec("nature", FieldKind.CODE, True, ("natureza", "tipo_custo")),
        FieldSpec("source_key", FieldKind.TEXT, True, ("chave_origem", "documento", "id_origem")),
    ),
    FileType.ACTIVITIES: (
        FieldSpec("activity_date", FieldKind.DATE, True, ("data_atividade", "data")),
        FieldSpec("unit_code", FieldKind.CODE, True, ("unidade", "cod_unidade")),
        FieldSpec("process_code", FieldKind.CODE, True, ("processo", "cod_processo")),
        FieldSpec("driver_code", FieldKind.CODE, True, ("direcionador", "cod_direcionador")),
        FieldSpec("quantity", FieldKind.QUANTITY, True, ("quantidade", "volume", "qtd")),
        FieldSpec("unit_of_measure", FieldKind.CODE, True, ("unidade_medida", "um", "uom")),
        FieldSpec("source_key", FieldKind.TEXT, True, ("chave_origem", "id_origem")),
    ),
    FileType.BUDGETS: (
        FieldSpec("period_start", FieldKind.DATE, True, ("inicio_periodo", "periodo_inicio")),
        FieldSpec("period_end", FieldKind.DATE, True, ("fim_periodo", "periodo_fim")),
        FieldSpec("unit_code", FieldKind.CODE, True, ("unidade", "cod_unidade")),
        FieldSpec("process_code", FieldKind.CODE, True, ("processo", "cod_processo")),
        FieldSpec("account_code", FieldKind.CODE, False, ("conta", "conta_contabil")),
        FieldSpec("amount", FieldKind.MONEY, True, ("valor", "valor_orcado", "orcamento")),
    ),
}

EXPENSE_NATURES = ("direct", "shared", "excluded", "pending_classification")


def field_specs(file_type: FileType) -> dict[str, FieldSpec]:
    return {spec.name: spec for spec in FIELDS[file_type]}


def normalize_header(header: str) -> str:
    """'Data de Competência ' -> 'data_de_competencia'."""
    text = unicodedata.normalize("NFKD", header).encode("ascii", "ignore").decode()
    return "_".join(text.strip().lower().replace("-", " ").replace("/", " ").split())


def suggest_mapping(file_type: FileType, columns: list[str]) -> dict[str, str]:
    """Sugere {campo_padrão: coluna_de_origem} pelo nome ou por apelidos conhecidos."""
    by_normalized = {normalize_header(col): col for col in columns}
    mapping: dict[str, str] = {}
    for spec in FIELDS[file_type]:
        for candidate in (spec.name, *spec.aliases):
            if candidate in by_normalized:
                mapping[spec.name] = by_normalized[candidate]
                break
    return mapping
