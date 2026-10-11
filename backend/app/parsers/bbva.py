"""Parser de la exportación Excel de movimientos de BBVA España."""
from __future__ import annotations

import io
import re
from decimal import Decimal
import pandas as pd

from app.parsers.base import NormalizedTransaction, ParseError, ParseResult
from app.parsers.imagin import _normalize_header, _parse_amount, _parse_date


class BBVAParser:
    institution_key = "bbva"

    # La exportación real de BBVA (Excel) lleva un título y la fecha del
    # informe antes de la cabecera de movimientos.
    DATE = {"date", "fecha", "fecha operacion", "fecha de operacion"}
    VALUE_DATE = {"value date", "fecha valor", "fecha de valor", "f. valor", "f valor"}
    REASON = {"reason", "motivo"}
    MOVEMENT = {"movement", "movimiento"}
    DESCRIPTION = {"concept", "concepto", "description", "descripcion", "detalle"}
    AMOUNT = {"amount", "importe", "importe eur", "importe (eur)", "cantidad"}
    CURRENCY = {"currency", "divisa", "moneda"}
    BALANCE = {"available", "saldo disponible", "saldo"}
    COMMENTS = {"comments", "comentarios"}

    def _read(self, file_bytes: bytes, filename: str):
        if filename.lower().endswith((".xlsx", ".xls")):
            raw = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=object)
        else:
            # Excel export CSVs may use either comma or semicolon separators.
            raw = pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=object, sep=None, engine="python")
        header_idx = None
        for idx in range(min(len(raw), 30)):
            values = {_normalize_header(v) for v in raw.iloc[idx].tolist() if pd.notna(v)}
            has_date = bool(values & self.DATE)
            has_amount = bool(values & self.AMOUNT)
            has_bbva_structure = bool(values & self.VALUE_DATE) and bool(values & self.REASON) and bool(values & self.MOVEMENT)
            if has_date and has_amount and (has_bbva_structure or bool(values & self.DESCRIPTION)):
                header_idx = idx
                break
        if header_idx is None:
            # Fallback for conventional CSVs whose first row is already the header.
            raw = pd.read_excel(io.BytesIO(file_bytes), dtype=object) if filename.lower().endswith((".xlsx", ".xls")) else pd.read_csv(io.BytesIO(file_bytes), dtype=object, sep=None, engine="python")
            return raw
        headers = []
        seen = {}
        for i, val in enumerate(raw.iloc[header_idx].tolist()):
            base = str(val).strip() if pd.notna(val) else f"unnamed_{i}"
            seen[base] = seen.get(base, 0) + 1
            headers.append(base if seen[base] == 1 else f"{base}.{seen[base]}")
        df = raw.iloc[header_idx + 1:].copy()
        df.columns = headers
        return df.dropna(how="all")

    def detect(self, filename: str, header_row: list[str], sample_text: str) -> float:
        name = filename.lower()
        headers = {_normalize_header(x) for x in header_row}
        text = (sample_text or "").lower()
        score = 0.0
        if "bbva" in name:
            score += 0.55
        if {"value date", "date", "reason", "movement", "amount"}.issubset(headers):
            score += 0.9
        elif (headers & self.DATE) and (headers & self.AMOUNT) and ((headers & self.DESCRIPTION) or (headers & self.MOVEMENT)):
            score += 0.45
        if "report generation date" in text and "available" in text:
            score += 0.3
        return min(score, 1.0)

    @staticmethod
    def _find(columns, aliases):
        for col in columns:
            if _normalize_header(col) in aliases:
                return col
        return None

    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        try:
            df = self._read(file_bytes, filename)
        except Exception as exc:
            return ParseResult(self.institution_key, [], [ParseError(0, f"No se pudo leer el archivo BBVA: {exc}")], 0)

        date_col = self._find(df.columns, self.DATE)
        value_col = self._find(df.columns, self.VALUE_DATE)
        reason_col = self._find(df.columns, self.REASON)
        movement_col = self._find(df.columns, self.MOVEMENT)
        desc_col = self._find(df.columns, self.DESCRIPTION)
        amount_col = self._find(df.columns, self.AMOUNT)
        currency_col = self._find(df.columns, self.CURRENCY)
        if not date_col or not amount_col or not (desc_col or movement_col or reason_col):
            return ParseResult(
                self.institution_key, [],
                [ParseError(0, "No se encontraron las columnas requeridas de BBVA (Date, Amount y descripción/Movement).", raw_row=", ".join(map(str, df.columns)))],
                len(df),
            )

        transactions, errors = [], []
        for idx, row in df.iterrows():
            date_val = _parse_date(row.get(date_col))
            amount_val = _parse_amount(row.get(amount_col))
            value_date = _parse_date(row.get(value_col)) if value_col else None

            parts = []
            for col in (reason_col, movement_col, desc_col):
                if col:
                    value = row.get(col)
                    if pd.notna(value) and str(value).strip() and str(value).strip() not in parts:
                        parts.append(str(value).strip())
            description = " - ".join(parts)
            if not description or date_val is None or amount_val is None:
                # Ignorar filas vacías; reportar filas parcialmente cumplimentadas.
                if any(pd.notna(row.get(c)) for c in (date_col, amount_col, reason_col, movement_col, desc_col) if c):
                    errors.append(ParseError(int(idx), "Fecha, importe o descripción inválidos", raw_row=str(row.to_dict())))
                continue

            currency = str(row.get(currency_col)).strip().upper() if currency_col and pd.notna(row.get(currency_col)) else "EUR"
            if currency.lower() in {"nan", "none", ""}:
                currency = "EUR"

            desc_upper = description.upper()
            is_bizum = bool(re.search(r"\bBIZUM\b", desc_upper))
            sent = bool(re.search(r"\b(ENVIADO|ENVIADA|ENVIAR|SENT)\b", desc_upper))
            received = bool(re.search(r"\b(RECIBIDO|RECIBIDA|RECEIVED)\b", desc_upper))
            is_transfer = bool(re.search(r"\b(TRANSFER|TRANSFERENCIA|TRASPASO)\b", desc_upper)) and not is_bizum
            bizum_direction = ("SENT" if sent else "RECEIVED" if received else "SENT" if amount_val < 0 else "RECEIVED") if is_bizum else None
            recipient = None
            if is_bizum:
                match = re.search(r"(?:ENVIADO|ENVIADA|RECIBIDO|RECIBIDA)\s*:\s*(.+)", description, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    candidate = re.sub(r"^bizum\s+(?:de|a)\s+", "", candidate, flags=re.IGNORECASE).strip()
                    if candidate and candidate.lower() not in {"sin concepto", "c", "sin nombre"}:
                        recipient = candidate.title()

            # Los movimientos de transferencia entrantes/salientes siguen
            # siendo ingreso/gasto; is_transfer_hint permite detectar después
            # si se trata de una transferencia entre cuentas propias.
            tx_type = "EXPENSE" if amount_val < 0 else "INCOME" if amount_val > 0 else "UNKNOWN"

            transactions.append(NormalizedTransaction(
                date=date_val,
                value_date=value_date,
                amount=amount_val,
                currency=currency,
                description=description,
                raw_description=description,
                source=self.institution_key,
                type=tx_type,
                is_bizum=is_bizum,
                bizum_direction=bizum_direction,
                bizum_recipient=recipient,
                is_transfer_hint=is_transfer,
                merchant=None if is_bizum or is_transfer else description.split()[0],
            ))

        return ParseResult(self.institution_key, transactions, errors, len(df))
