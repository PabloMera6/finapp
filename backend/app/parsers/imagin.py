"""
Parser de exportaciones CSV/XLSX de imagin.

Las exportaciones bancarias cambian con el tiempo, así que este parser
está versionado por conjunto de cabeceras reconocidas (ver COLUMN_ALIASES).

BankParser es el único contrato utilizado por la aplicación.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.parsers.base import BankParser, NormalizedTransaction, ParseError, ParseResult


# IMPORTANTE:
# "fecha valor" NO pertenece a date.
# Debe ir siempre a value_date.
#
# De esta forma, si imagin exporta:
# Fecha;Concepto;Importe;Saldo disponible
#
# "Fecha" será date.
#
# Si MyInvestor/exportaciones similares contienen:
# Fecha de operación;Fecha de valor;...
#
# cada fecha se asignará a su campo correspondiente.
COLUMN_ALIASES = {
    "date": [
        "fecha",
        "fecha operacion",
        "fecha de operacion",
        "fecha op.",
        "date",
    ],
    "value_date": [
        "fecha valor",
        "fecha de valor",
        "f. valor",
        "value date",
        "value_date",
    ],
    "description": [
        "concepto",
        "descripcion",
        "detalle",
        "description",
    ],
    "amount": [
        "importe",
        "importe (eur)",
        "importe eur",
        "cantidad",
        "amount",
    ],
    "balance": [
        "saldo",
        "saldo disponible",
        "balance",
    ],
}


BIZUM_SENT_RE = re.compile(
    r"BIZUM\s+A\s+(.+)",
    re.IGNORECASE,
)

BIZUM_RECEIVED_RE = re.compile(
    r"BIZUM\s+DE\s+(.+)",
    re.IGNORECASE,
)

BIZUM_GENERIC_RE = re.compile(
    r"\bBIZUM\b",
    re.IGNORECASE,
)

TRANSFER_RE = re.compile(
    r"\b(TRANSFERENCIA|TRASPASO)\b",
    re.IGNORECASE,
)


def _normalize_header(h: str) -> str:
    h = str(h).strip().lower()

    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }

    for a, b in replacements.items():
        h = h.replace(a, b)

    # Normalizamos espacios repetidos.
    h = re.sub(r"\s+", " ", h)

    return h


def _map_columns(columns: list[str]) -> dict[str, str]:
    """
    Mapea las columnas originales a los campos normalizados.

    Es importante que date y value_date sean independientes:
      Fecha / Fecha de operación -> date
      Fecha de valor -> value_date
    """
    normalized = {
        original: _normalize_header(original)
        for original in columns
    }

    mapping: dict[str, str] = {}

    for field, aliases in COLUMN_ALIASES.items():
        alias_set = {_normalize_header(alias) for alias in aliases}

        for original, normalized_name in normalized.items():
            if normalized_name in alias_set:
                mapping[field] = original
                break

    return mapping


def _parse_amount(raw) -> Decimal | None:
    if raw is None:
        return None

    s = str(raw).strip()

    if s == "" or s.lower() in {"nan", "none", "null"}:
        return None

    # Ejemplos soportados:
    # -20,92EUR
    # -20,92 EUR
    # 1.234,56 €
    # 1234.56
    # -375
    s = s.replace("€", "")
    s = re.sub(r"\bEUR\b", "", s, flags=re.IGNORECASE)
    s = s.replace(" ", "")
    s = s.strip()

    if not s:
        return None

    # Soportar:
    # 1.234,56 -> 1234.56
    # 1234,56  -> 1234.56
    # 1234.56  -> 1234.56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")

    # Eliminar cualquier carácter residual excepto signo,
    # dígitos y punto decimal.
    s = re.sub(r"[^0-9.+-]", "", s)

    if not s:
        return None

    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_date(raw) -> datetime | None:
    if raw is None:
        return None

    if isinstance(raw, datetime):
        return raw

    # pandas Timestamp
    if hasattr(raw, "to_pydatetime"):
        try:
            return raw.to_pydatetime()
        except Exception:
            pass

    s = str(raw).strip()

    if not s or s.lower() in {"nat", "nan", "none", "null"}:
        return None

    for fmt in (
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d/%m/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    try:
        parsed = pd.to_datetime(s, dayfirst=True, errors="coerce")

        if pd.isna(parsed):
            return None

        return parsed.to_pydatetime()
    except Exception:
        return None


class ImaginParser(BankParser):
    institution_key = "imagin"

    def detect(
        self,
        filename: str,
        header_row: list[str],
        sample_text: str,
    ) -> float:
        score = 0.0

        filename_lower = filename.lower()

        if "imagin" in filename_lower:
            score += 0.5

        mapping = _map_columns(header_row)

        required = {
            "date",
            "description",
            "amount",
        }

        if required.issubset(mapping.keys()):
            score += 0.4

        if "bizum" in sample_text.lower():
            score += 0.05

        return min(score, 1.0)

    def parse(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> ParseResult:
        errors: list[ParseError] = []
        transactions: list[NormalizedTransaction] = []

        try:
            if filename.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(
                    io.BytesIO(file_bytes),
                    dtype=str,
                )
            else:
                df = pd.read_csv(
                    io.BytesIO(file_bytes),
                    dtype=str,
                    sep=None,
                    engine="python",
                )

        except Exception as exc:
            return ParseResult(
                self.institution_key,
                [],
                [
                    ParseError(
                        0,
                        f"No se pudo leer el archivo: {exc}",
                    )
                ],
                0,
            )

        mapping = _map_columns(list(df.columns))

        missing = {
            "date",
            "description",
            "amount",
        } - mapping.keys()

        if missing:
            errors.append(
                ParseError(
                    0,
                    f"Columnas requeridas no encontradas: {missing}",
                )
            )

            return ParseResult(
                self.institution_key,
                [],
                errors,
                len(df),
            )

        for idx, row in df.iterrows():
            raw_desc = str(
                row.get(mapping["description"], "") or ""
            ).strip()

            date_val = _parse_date(
                row.get(mapping["date"])
            )

            amount_val = _parse_amount(
                row.get(mapping["amount"])
            )

            if (
                date_val is None
                or amount_val is None
                or not raw_desc
            ):
                errors.append(
                    ParseError(
                        int(idx),
                        "Fecha, importe o descripción inválidos",
                        raw_row=str(row.to_dict()),
                    )
                )
                continue

            # Fecha de valor es opcional y NUNCA sustituye a date.
            value_date = None

            if mapping.get("value_date"):
                value_date = _parse_date(
                    row.get(mapping["value_date"])
                )

            is_bizum = bool(
                BIZUM_GENERIC_RE.search(raw_desc)
            )

            bizum_direction = None
            bizum_recipient = None

            if is_bizum:
                sent_match = BIZUM_SENT_RE.search(raw_desc)
                received_match = BIZUM_RECEIVED_RE.search(raw_desc)

                if sent_match:
                    bizum_direction = "SENT"
                    bizum_recipient = (
                        sent_match.group(1).strip().title()
                        or None
                    )

                elif received_match:
                    bizum_direction = "RECEIVED"
                    bizum_recipient = (
                        received_match.group(1).strip().title()
                        or None
                    )

                else:
                    # Si el texto no permite saber la dirección,
                    # usamos el signo del importe.
                    bizum_direction = (
                        "SENT"
                        if amount_val < 0
                        else "RECEIVED"
                    )

                    bizum_recipient = None

            is_transfer_hint = bool(
                TRANSFER_RE.search(raw_desc)
            )

            tx_type = "UNKNOWN"

            if is_bizum:
                tx_type = (
                    "EXPENSE"
                    if amount_val < 0
                    else "INCOME"
                )

            elif is_transfer_hint:
                tx_type = "TRANSFER"

            elif amount_val > 0:
                tx_type = "INCOME"

            elif amount_val < 0:
                tx_type = "EXPENSE"

            transactions.append(
                NormalizedTransaction(
                    date=date_val,
                    value_date=value_date,
                    amount=amount_val,
                    currency="EUR",
                    description=raw_desc,
                    raw_description=raw_desc,
                    source=self.institution_key,
                    type=tx_type,
                    is_bizum=is_bizum,
                    bizum_direction=bizum_direction,
                    bizum_recipient=bizum_recipient,
                    is_transfer_hint=is_transfer_hint,
                    merchant=(
                        None
                        if is_bizum or is_transfer_hint
                        else raw_desc.split()[0]
                        if raw_desc
                        else None
                    ),
                )
            )

        return ParseResult(
            self.institution_key,
            transactions,
            errors,
            len(df),
        )