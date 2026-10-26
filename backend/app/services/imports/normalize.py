"""Normalização de valores de planilhas brasileiras.

Não adivinha formatos ambíguos: a convenção de datas e de separador decimal é
escolhida pelo usuário e o que não se encaixa nela vira erro.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class DateFormat(StrEnum):
    ISO = "iso"  # 2026-09-30
    DMY = "dmy"  # 30/09/2026


class DecimalSeparator(StrEnum):
    COMMA = ","  # 1.234,56 ou 1234,56
    DOT = "."  # 1234.56 ou 1,234.56


_DATE_FORMATS = {DateFormat.ISO: "%Y-%m-%d", DateFormat.DMY: "%d/%m/%Y"}

_NUMBER_PATTERNS = {
    DecimalSeparator.COMMA: re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$"),
    DecimalSeparator.DOT: re.compile(r"^-?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$"),
}


def clean(value: str | None) -> str:
    return (value or "").strip()


def parse_date(value: str, fmt: DateFormat) -> date | None:
    try:
        return datetime.strptime(value, _DATE_FORMATS[fmt]).date()
    except ValueError:
        return None


def parse_number(value: str, separator: DecimalSeparator) -> Decimal | None:
    """Converte texto em Decimal segundo a convenção; aceita 'R$' e espaços."""
    text = value.replace("R$", "").replace(" ", "").replace(" ", "")
    if not _NUMBER_PATTERNS[separator].match(text):
        return None
    if separator is DecimalSeparator.COMMA:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None
