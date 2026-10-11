"""Parser de movimientos de cuenta BBVA España (CSV/XLS/XLSX)."""
from __future__ import annotations
import io
import re
import pandas as pd
from app.parsers.imagin import ImaginParser, _normalize_header


class BBVAParser(ImaginParser):
    institution_key = "bbva"

    DATE = {"fecha", "fecha operacion", "fecha de operacion", "date"}
    VALUE_DATE = {"f. valor", "f valor", "fecha valor", "fecha de valor", "fecha valoracion"}
    DESCRIPTION = {"concepto", "descripcion", "detalle", "descripción", "movimiento", "description"}
    AMOUNT = {"importe", "importe eur", "importe (eur)", "amount", "cantidad", "importe del movimiento"}
    DEBIT = {"cargo", "debe", "debitos", "débito", "debit"}
    CREDIT = {"abono", "haber", "creditos", "crédito", "credit"}
    CURRENCY = {"divisa", "moneda", "currency"}

    def detect(self, filename: str, header_row: list[str], sample_text: str) -> float:
        name = filename.lower()
        headers = {_normalize_header(x) for x in header_row}
        text = (sample_text or "").lower()
        score = 0.0
        if "bbva" in name:
            score += 0.55
        if (headers & self.DATE) and (headers & self.DESCRIPTION) and (
            headers & self.AMOUNT or (headers & self.DEBIT and headers & self.CREDIT)
        ):
            score += 0.4
        if "bbva" in text:
            score += 0.1
        return min(score, 1.0)

    def parse(self, file_bytes: bytes, filename: str):
        try:
            if filename.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
            else:
                df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, sep=None, engine="python")
        except Exception as exc:
            from app.parsers.base import ParseError, ParseResult
            return ParseResult(self.institution_key, [], [ParseError(0, f"No se pudo leer el archivo: {exc}")], 0)

        # Se traducen las cabeceras BBVA al esquema común. Si existe Importe,
        # se prefiere frente a Movimiento (que puede ser una etiqueta textual).
        cols = {col: _normalize_header(col) for col in df.columns}
        def find(aliases):
            for col, norm in cols.items():
                if norm in aliases:
                    return col
            return None

        date_col = find(self.DATE)
        value_col = find(self.VALUE_DATE)
        desc_col = find(self.DESCRIPTION)
        amount_col = find(self.AMOUNT)
        debit_col = find(self.DEBIT)
        credit_col = find(self.CREDIT)

        if amount_col is None and (debit_col or credit_col):
            def parse_num(v):
                if v is None or pd.isna(v) or not str(v).strip():
                    return 0.0
                s = str(v).replace("€", "").replace(" ", "").strip()
                if "," in s and "." in s:
                    s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
                elif "," in s:
                    s = s.replace(".", "").replace(",", ".")
                try: return float(s)
                except ValueError: return 0.0
            df["__bbva_importe"] = [
                parse_num(row.get(credit_col)) - parse_num(row.get(debit_col))
                for _, row in df.iterrows()
            ]
            amount_col = "__bbva_importe"

        if not date_col or not desc_col or not amount_col:
            from app.parsers.base import ParseError, ParseResult
            return ParseResult(self.institution_key, [], [ParseError(0, "No se encontraron las columnas requeridas de BBVA (fecha, concepto y importe/cargo/abono).", raw_row=", ".join(map(str, df.columns)))], len(df))

        # Construimos CSV canónico y delegamos normalización, clasificación
        # de movimientos y fechas al parser común.
        canonical = pd.DataFrame({
            "Fecha": df[date_col],
            "Concepto": df[desc_col],
            "Importe": df[amount_col],
        })
        if value_col:
            canonical["Fecha valor"] = df[value_col]
        data = canonical.to_csv(index=False).encode("utf-8")
        return super().parse(data, "bbva_normalized.csv")
