"""Leitura estrutural de arquivos CSV (seção 10, passos 1 a 4 do pipeline)."""

import csv
import hashlib
import io
from dataclasses import dataclass

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000
SUPPORTED_EXTENSIONS = (".csv",)


class FileRejected(Exception):
    """Arquivo recusado antes de qualquer leitura de linhas."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedRow:
    row_number: int  # linha no arquivo, contando o cabeçalho como linha 1
    values: dict[str, str]


@dataclass(frozen=True)
class ParsedFile:
    columns: list[str]
    rows: list[ParsedRow]
    sha256: str
    delimiter: str


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FileRejected("INVALID_ENCODING", "Não foi possível ler o arquivo como texto.")


def parse_csv(filename: str, content: bytes) -> ParsedFile:
    if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise FileRejected("UNSUPPORTED_FILE_TYPE", "Formato não suportado. Envie um arquivo .csv.")
    if len(content) == 0:
        raise FileRejected("EMPTY_FILE", "O arquivo está vazio.")
    if len(content) > MAX_FILE_BYTES:
        raise FileRejected("FILE_TOO_LARGE", "O arquivo excede o limite de 5 MB.")
    if b"\x00" in content[:4096]:
        raise FileRejected("UNSUPPORTED_FILE_TYPE", "O conteúdo não parece ser um CSV de texto.")

    text = _decode(content)
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise FileRejected("EMPTY_FILE", "O arquivo não tem cabeçalho.") from None

    columns = [col.strip() for col in header]
    if not any(columns):
        raise FileRejected(
            "MISSING_HEADER", "A primeira linha precisa conter os nomes das colunas."
        )
    if len(set(columns)) != len(columns):
        raise FileRejected("DUPLICATE_COLUMN", "O cabeçalho tem colunas com nomes repetidos.")

    rows: list[ParsedRow] = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue  # linha totalmente vazia
        if len(rows) >= MAX_ROWS:
            raise FileRejected("TOO_MANY_ROWS", f"O arquivo excede o limite de {MAX_ROWS} linhas.")
        padded = values + [""] * (len(columns) - len(values))
        rows.append(ParsedRow(reader.line_num, dict(zip(columns, padded, strict=False))))

    return ParsedFile(
        columns=columns,
        rows=rows,
        sha256=hashlib.sha256(content).hexdigest(),
        delimiter=delimiter,
    )
