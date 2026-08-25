"""
Parser de exportaciones CSV/XLSX de MyInvestor.

Distingue movimientos de cuenta corriente de operaciones de inversión
cuando la exportación lo permite.

IMPORTANTE:
MyInvestor puede exportar simultáneamente:

    Fecha de operación
    Fecha de valor
    Concepto
    Importe
    Divisa

La fecha principal de la transacción es SIEMPRE "Fecha de operación".
"Fecha de valor" se conserva como value_date.

No se debe usar "Fecha de valor" como date.
"""

from __future__ import annotations

import io
import re

import pandas as pd

from app.parsers.base import (
    BankParser,
    NormalizedTransaction,
    ParseError,
    ParseResult,
)
from app.parsers.imagin import (
    _normalize_header,
    _parse_amount,
    _parse_date,
)


# IMPORTANTE:
# "fecha valor" NO está en date.
#
# Esto evita el bug que hacía que MyInvestor utilizase:
#
#     Fecha de valor
#
# como fecha principal.
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
        "operacion",
        "operation",
        "description",
    ],
    "amount": [
        "importe",
        "importe (eur)",
        "importe eur",
        "cantidad",
        "amount",
    ],
    "currency": [
        "divisa",
        "moneda",
        "currency",
    ],
    "op_type": [
        "tipo",
        "tipo operacion",
        "tipo de operacion",
        "type",
    ],
    "counterparty": [
        "contrapartida",
        "beneficiario",
        "ordenante",
        "counterparty",
    ],
}


BUY_RE = re.compile(
    r"\b(COMPRA|SUSCRIPCION|SUSCRIPCIÓN)\b",
    re.IGNORECASE,
)

SELL_RE = re.compile(
    r"\b(VENTA|REEMBOLSO)\b",
    re.IGNORECASE,
)

DIVIDEND_RE = re.compile(
    r"\bDIVIDEND",
    re.IGNORECASE,
)

INTEREST_RE = re.compile(
    r"\b(INTERES|INTERESES|INTERÉS|INTERESES)\b",
    re.IGNORECASE,
)

FEE_RE = re.compile(
    r"\b(COMISION|COMISIONES|COMISIÓN|COMISIONES)\b",
    re.IGNORECASE,
)

TRANSFER_RE = re.compile(
    r"\b(TRANSFERENCIA|TRASPASO)\b",
    re.IGNORECASE,
)

# MyInvestor exporta muchas operaciones de fondos/ETFs directamente con el
# nombre de la gestora al inicio del concepto (sin la palabra "compra"),
# por ejemplo:
#
#   VANGUARD FTSE ALL-WORLD UCITS ETF
#   ISHARES CORE MSCI WORLD
#   FIDELITY INDEX WORLD FUND
#
# Estos movimientos son inversiones y deben tratarse como tal aunque no
# contengan ninguna palabra clave de compra/venta explícita.
INVESTMENT_FUND_RE = re.compile(
    r"^\s*(VANGUARD|ISHARES|FIDELITY|MSCI)\b",
    re.IGNORECASE,
)


def _map_columns(columns: list[str]) -> dict[str, str]:
    normalized = {
        original: _normalize_header(original)
        for original in columns
    }

    mapping: dict[str, str] = {}

    for field, aliases in COLUMN_ALIASES.items():
        alias_set = {
            _normalize_header(alias)
            for alias in aliases
        }

        for original, normalized_name in normalized.items():
            if normalized_name in alias_set:
                mapping[field] = original
                break

    return mapping


class MyInvestorParser(BankParser):
    institution_key = "myinvestor"

    def detect(
        self,
        filename: str,
        header_row: list[str],
        sample_text: str,
    ) -> float:
        score = 0.0

        filename_lower = filename.lower()

        if "myinvestor" in filename_lower:
            score += 0.5

        mapping = _map_columns(header_row)

        if {
            "date",
            "description",
            "amount",
        }.issubset(mapping.keys()):
            score += 0.35

        sample_lower = sample_text.lower()

        if any(
            keyword in sample_lower
            for keyword in [
                "fondo",
                "traspaso",
                "myinvestor",
                "fecha de operación",
                "fecha de operacion",
            ]
        ):
            score += 0.1

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

            # La fecha principal es EXCLUSIVAMENTE
            # Fecha de operación.
            date_val = _parse_date(
                row.get(mapping["date"])
            )

            # Fecha de valor queda separada.
            value_date = None

            if mapping.get("value_date"):
                value_date = _parse_date(
                    row.get(mapping["value_date"])
                )

            amount_val = _parse_amount(
                row.get(mapping["amount"])
            )

            op_type_raw = ""

            if mapping.get("op_type"):
                op_type_raw = str(
                    row.get(mapping["op_type"], "") or ""
                ).strip()

            counterparty = None

            if mapping.get("counterparty"):
                raw_counterparty = row.get(
                    mapping["counterparty"]
                )

                if (
                    raw_counterparty is not None
                    and str(raw_counterparty).strip().lower()
                    not in {"", "nan", "none"}
                ):
                    counterparty = str(
                        raw_counterparty
                    ).strip()

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

            combined = f"{raw_desc} {op_type_raw}"

            tx_type = "UNKNOWN"

            if BUY_RE.search(combined):
                tx_type = "INVESTMENT_BUY"

            elif SELL_RE.search(combined):
                tx_type = "INVESTMENT_SELL"

            elif DIVIDEND_RE.search(combined):
                tx_type = "DIVIDEND"

            elif INTEREST_RE.search(combined):
                tx_type = "INTEREST"

            elif FEE_RE.search(combined):
                tx_type = "FEE"

            elif TRANSFER_RE.search(combined):
                tx_type = "TRANSFER"

            elif INVESTMENT_FUND_RE.search(raw_desc):
                # Concepto es directamente el nombre de un fondo/ETF
                # (VANGUARD/ISHARES/FIDELITY) sin palabra de compra/venta
                # explícita. Se infiere la dirección por el signo del
                # importe: dinero saliendo = compra, dinero entrando = venta.
                tx_type = (
                    "INVESTMENT_SELL"
                    if amount_val > 0
                    else "INVESTMENT_BUY"
                )

            elif amount_val > 0:
                tx_type = "INCOME"

            elif amount_val < 0:
                tx_type = "EXPENSE"

            is_transfer_hint = tx_type == "TRANSFER"

            # Activo (nombre del fondo/ETF) para operaciones de inversión.
            merchant = None

            if tx_type in {
                "INVESTMENT_BUY",
                "INVESTMENT_SELL",
                "DIVIDEND",
            }:
                merchant = raw_desc

            currency = "EUR"

            if mapping.get("currency"):
                raw_currency = row.get(
                    mapping["currency"]
                )

                if (
                    raw_currency is not None
                    and str(raw_currency).strip()
                ):
                    currency = str(
                        raw_currency
                    ).strip().upper()

            transactions.append(
                NormalizedTransaction(
                    date=date_val,
                    value_date=value_date,
                    amount=amount_val,
                    currency=currency,
                    description=raw_desc,
                    raw_description=raw_desc,
                    source=self.institution_key,
                    type=tx_type,
                    merchant=merchant,
                    counterparty=counterparty,
                    is_transfer_hint=is_transfer_hint,
                )
            )

        return ParseResult(
            self.institution_key,
            transactions,
            errors,
            len(df),
        )