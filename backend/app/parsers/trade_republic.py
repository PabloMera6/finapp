"""
Parser de exportaciones de Trade Republic.

Trade Republic exporta la información de cuenta en PDF.

El parser procesa exclusivamente la sección:

    TRANSACCIONES DE CUENTA

y deja fuera cualquier contenido posterior, especialmente:

    RESUMEN DEL BALANCE
    a 16 ago 2026
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal

from app.parsers.base import (
    BankParser,
    NormalizedTransaction,
    ParseError,
    ParseResult,
)
from app.parsers.imagin import (
    _normalize_header,
    _parse_amount,
)


# ---------------------------------------------------------------------------
# Meses
# ---------------------------------------------------------------------------

MONTHS = {
    "ene": 1,
    "enero": 1,
    "feb": 2,
    "febrero": 2,
    "mar": 3,
    "marzo": 3,
    "abr": 4,
    "abril": 4,
    "may": 5,
    "mayo": 5,
    "jun": 6,
    "junio": 6,
    "jul": 7,
    "julio": 7,
    "ago": 8,
    "agosto": 8,
    "sep": 9,
    "sept": 9,
    "septiembre": 9,
    "oct": 10,
    "octubre": 10,
    "nov": 11,
    "noviembre": 11,
    "dic": 12,
    "diciembre": 12,
}


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

DATE_TEXT_RE = re.compile(
    r"""
    (?<!\d)
    (?:a\s+)?
    (\d{1,2})
    [\s./-]+
    (ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|
     abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|
     ago(?:sto)?|sep(?:tiembre)?|sept(?:iembre)?|
     oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)
    \.?
    [\s./-]+
    (\d{4})
    (?!\d)
    """,
    re.IGNORECASE | re.VERBOSE,
)


DATE_NUMERIC_RE = re.compile(
    r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)"
)


def _parse_trade_republic_date(raw: str) -> datetime | None:
    """
    Convierte fechas del PDF de Trade Republic.

    Soporta:

        16 sept 2025
        16 sept. 2025
        16 septiembre 2025
        a 16 ago 2026
        16/09/2025
        16-09-2025
        16.09.2025
    """

    if not raw:
        return None

    value = str(raw).strip()

    # ---------------------------------------------------------------
    # Fecha con mes escrito
    # ---------------------------------------------------------------

    match = DATE_TEXT_RE.search(value)

    if match:
        day = int(match.group(1))
        month_text = match.group(2).lower().rstrip(".")
        year = int(match.group(3))

        month = MONTHS.get(month_text)

        if month is not None:
            try:
                return datetime(year, month, day)
            except ValueError:
                return None

    # ---------------------------------------------------------------
    # Fecha numérica
    # ---------------------------------------------------------------

    match = DATE_NUMERIC_RE.search(value)

    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))

        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    return None


def _contains_trade_republic_date(value: str) -> bool:
    return _parse_trade_republic_date(value) is not None


# ---------------------------------------------------------------------------
# Regex de fechas partidas
# ---------------------------------------------------------------------------

PARTIAL_TEXT_DATE_RE = re.compile(
    r"""
    ^\s*
    (\d{1,2})
    [\s./-]+
    (ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|
     abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|
     ago(?:sto)?|sep(?:tiembre)?|sept(?:iembre)?|
     oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)
    \.?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


YEAR_ONLY_RE = re.compile(
    r"^\s*\d{4}\s*$"
)


def _merge_wrapped_date_lines(lines: list[str]) -> list[str]:
    """
    Reconstruye fechas que el extractor del PDF haya partido en dos líneas.

    Ejemplo:

        16 sept
        2025

    se convierte en:

        16 sept 2025

    También soporta:

        16 septiembre
        2025

    Las demás líneas permanecen intactas.
    """

    result: list[str] = []

    i = 0

    while i < len(lines):

        current = _clean_pdf_line(lines[i])

        if (
            i + 1 < len(lines)
            and PARTIAL_TEXT_DATE_RE.match(current)
            and YEAR_ONLY_RE.match(lines[i + 1])
        ):
            year = _clean_pdf_line(lines[i + 1])

            result.append(
                _clean_pdf_line(
                    f"{current} {year}"
                )
            )

            i += 2
            continue

        result.append(current)

        i += 1

    return result


# ---------------------------------------------------------------------------
# Regex de tipos
# ---------------------------------------------------------------------------

BUY_RE = re.compile(
    r"\b("
    r"BUY|COMPRA|SAVINGS?\s*PLAN|"
    r"PLAN\s+DE\s+AHORRO|"
    r"AHORRO"
    r")\b",
    re.IGNORECASE,
)


SELL_RE = re.compile(
    r"\b(SELL|VENTA)\b",
    re.IGNORECASE,
)


DIVIDEND_RE = re.compile(
    r"\b(DIVIDEND|DIVIDENDO|DIVIDENDOS)\b",
    re.IGNORECASE,
)


INTEREST_RE = re.compile(
    r"\b(INTEREST|INTERES|INTERÉS|INTERESES)\b",
    re.IGNORECASE,
)


FEE_RE = re.compile(
    r"\b(FEE|COMISION|COMISIÓN|COMISIONES)\b",
    re.IGNORECASE,
)


TRANSFER_RE = re.compile(
    r"\b(TRANSFER|TRANSFERENCIA|TRANSFERENCIAS)\b",
    re.IGNORECASE,
)


DEPOSIT_RE = re.compile(
    r"\b("
    r"DEPOSIT|INGRESO|TOP.?UP|"
    r"INCOMING\s+TRANSFER|"
    r"TRANSFERENCIA\s+RECIBIDA"
    r")\b",
    re.IGNORECASE,
)


WITHDRAWAL_RE = re.compile(
    r"\b("
    r"WITHDRAWAL|RETIRADA|"
    r"OUTGOING\s+TRANSFER|"
    r"TRANSFERENCIA\s+EMITIDA"
    r")\b",
    re.IGNORECASE,
)


CARD_RE = re.compile(
    r"\b("
    r"CARD|"
    r"TARJETA|"
    r"TRANSAKTION\s+MIT\s+KARTE|"
    r"TRANSACTION\s+WITH\s+CARD|"
    r"TRANSACCIÓN\s+CON\s+TARJETA|"
    r"TRANSACCION\s+CON\s+TARJETA"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _extract_pdf_text(file_bytes: bytes) -> str:
    """
    Intenta primero con pypdf y después con pdfplumber.
    """

    errors: list[str] = []

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))

        pages: list[str] = []

        for page in reader.pages:
            text = page.extract_text() or ""

            if text:
                pages.append(text)

        result = "\n".join(pages)

        if result.strip():
            return result

    except Exception as exc:
        errors.append(f"pypdf: {exc}")

    try:
        import pdfplumber

        pages = []

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""

                if text:
                    pages.append(text)

        result = "\n".join(pages)

        if result.strip():
            return result

    except Exception as exc:
        errors.append(f"pdfplumber: {exc}")

    raise ValueError(
        "No se pudo extraer texto del PDF. "
        + " | ".join(errors)
    )


def _clean_pdf_line(line: str) -> str:
    """
    Normaliza espacios y caracteres especiales del PDF.
    """

    line = str(line).replace("\xa0", " ")
    line = line.replace("\u200b", "")
    line = re.sub(r"\s+", " ", line)

    return line.strip()


# ---------------------------------------------------------------------------
# Importes
# ---------------------------------------------------------------------------

MONEY_RE = re.compile(
    r"""
    [+-]?\s*
    \d{1,3}
    (?:[.\s]\d{3})*
    (?:,\d+)?
    \s*€
    """,
    re.VERBOSE,
)


def _is_money_line(line: str) -> bool:
    """
    Detecta importes del estilo:

        10,00 €
        10 €
        -10,50 €
        1.234,56 €
        +10,00 €
    """

    line = _clean_pdf_line(line)

    return bool(
        MONEY_RE.fullmatch(line)
    )


def _parse_money_line(line: str) -> Decimal | None:
    if not _is_money_line(line):
        return None

    try:
        return _parse_amount(line)
    except Exception:
        return None


def _extract_money_values(text: str) -> list[Decimal]:
    """
    Extrae todos los importes que aparezcan en un texto.

    Esto permite procesar tanto:

        10,00 €

    como:

        10,00 € 10,00 €

    """

    values: list[Decimal] = []

    for match in MONEY_RE.finditer(text):
        try:
            value = _parse_amount(
                match.group(0)
            )

            values.append(value)

        except Exception:
            continue

    return values


# ---------------------------------------------------------------------------
# Sección de transacciones
# ---------------------------------------------------------------------------

def _find_transaction_section(text: str) -> str:
    """
    Extrae exclusivamente TRANSACCIONES DE CUENTA.

    Todo lo que aparezca después de RESUMEN DEL BALANCE se ignora.
    """

    normalized = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    # ---------------------------------------------------------------
    # Buscar inicio
    # ---------------------------------------------------------------

    start_match = re.search(
        r"TRANSACCIONES\s+DE\s+CUENTA",
        normalized,
        re.IGNORECASE,
    )

    if not start_match:
        return ""

    section = normalized[start_match.end():]

    # ---------------------------------------------------------------
    # Buscar final
    # ---------------------------------------------------------------

    end_pattern = re.compile(
        r"""
        (?:
            RESUMEN\s+DEL\s+BALANCE
            |
            RESUMEN\s+DE\s+BALANCE
            |
            RESUMEN\s+DE\s+LA\s+CUENTA
            |
            DETALLES\s+DE\s+LA\s+CUENTA
            |
            DOCUMENTOS
            |
            INFORMACIÓN\s+FISCAL
            |
            INFORMACION\s+FISCAL
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    end_match = end_pattern.search(section)

    if end_match:
        section = section[:end_match.start()]

    return section.strip()


# ---------------------------------------------------------------------------
# Cabeceras
# ---------------------------------------------------------------------------

def _looks_like_header(line: str) -> bool:
    normalized = _normalize_header(line)

    return (
        "fecha" in normalized
        or "date" in normalized
        or "tipo" in normalized
        or "type" in normalized
        or "descripcion" in normalized
        or "description" in normalized
        or "entrada de dinero" in normalized
        or "salida de dinero" in normalized
        or "balance" in normalized
    )


# ---------------------------------------------------------------------------
# Extracción de fecha desde una línea
# ---------------------------------------------------------------------------

def _extract_date_from_line(
    line: str,
) -> tuple[datetime | None, str]:
    """
    Busca una fecha dentro de la línea.

    Devuelve:

        (fecha, texto_sin_fecha)

    Soporta:

        16 sept 2025
        16 sept 2025 Transferencia
        16/09/2025 Transferencia
    """

    match = DATE_TEXT_RE.search(line)

    if match:
        date = _parse_trade_republic_date(
            match.group(0)
        )

        remaining = (
            line[:match.start()]
            + " "
            + line[match.end():]
        )

        return date, _clean_pdf_line(
            remaining
        )

    match = DATE_NUMERIC_RE.search(line)

    if match:
        date = _parse_trade_republic_date(
            match.group(0)
        )

        remaining = (
            line[:match.start()]
            + " "
            + line[match.end():]
        )

        return date, _clean_pdf_line(
            remaining
        )

    return None, line



# ---------------------------------------------------------------------------
# Resolución de signo mediante columna BALANCE
# ---------------------------------------------------------------------------

def _resolve_trade_republic_amounts(candidates: list[dict]) -> list[Decimal]:
    """
    Trade Republic exporta dos columnas monetarias:
      ENTRADA DE DINERO | SALIDA DE DINERO | BALANCE

    El PDF, sin embargo, puede extraer ambas entradas/salidas como importes
    positivos. Por ello el primer importe NO determina por sí solo el signo.

    Usamos el balance acumulado como fuente de verdad:
        balance_actual - balance_anterior = movimiento

    Para la primera fila, si no conocemos el balance anterior, buscamos una
    fila posterior cuyo balance permita validar el signo. Si no es posible,
    conservamos el signo explícito del PDF o, en último caso, el positivo.
    """
    if not candidates:
        return []

    balances = [c.get("balance") for c in candidates]
    raw = [c["movement"] for c in candidates]
    result: list[Decimal] = []

    # Inferir el signo fila a fila usando balances consecutivos.
    for idx, c in enumerate(candidates):
        movement = abs(c["movement"])
        balance = c.get("balance")
        previous_balance = balances[idx - 1] if idx > 0 else None

        if idx > 0 and previous_balance is not None and balance is not None:
            delta = balance - previous_balance
            # Si coincide con el importe de movimiento, es inequívoco.
            if abs(delta) == movement:
                result.append(delta)
                continue

        # Primera fila: usar la siguiente fila como ancla.
        if idx == 0 and balance is not None:
            hint_type = c.get("type")
            if hint_type in {"EXPENSE", "INVESTMENT_BUY", "FEE"}:
                result.append(-movement)
                continue
            if hint_type in {"INCOME", "INVESTMENT_SELL", "DIVIDEND", "INTEREST"}:
                result.append(movement)
                continue
            if DEPOSIT_RE.search(c.get("raw_text", "")):
                result.append(movement)
                continue
            if WITHDRAWAL_RE.search(c.get("raw_text", "")):
                result.append(-movement)
                continue
            for j in range(1, len(candidates)):
                next_balance = balances[j]
                if next_balance is None:
                    continue
                # Si conocemos la suma de movimientos intermedios no podemos
                # asumir todos iguales, pero la siguiente fila suele bastar.
                delta_next = next_balance - balance
                next_movement = abs(raw[j])
                if abs(delta_next) == next_movement:
                    # No revela directamente el signo de la primera fila;
                    # usar el balance previo implícito de la primera operación
                    # cuando el siguiente movimiento sí cuadra.
                    implied_previous = balance - abs(raw[idx])
                    if implied_previous >= 0:
                        result.append(abs(raw[idx]))
                    else:
                        result.append(-abs(raw[idx]))
                    break
            else:
                result.append(c["explicit_amount"])
            continue

        hint_type = c.get("type")
        if hint_type in {"EXPENSE", "INVESTMENT_BUY", "FEE"}:
            result.append(-movement)
        elif hint_type in {"INCOME", "INVESTMENT_SELL", "DIVIDEND", "INTEREST"}:
            result.append(movement)
        elif DEPOSIT_RE.search(c.get("raw_text", "")):
            result.append(movement)
        elif WITHDRAWAL_RE.search(c.get("raw_text", "")):
            result.append(-movement)
        else:
            result.append(c["explicit_amount"])

    return result


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TradeRepublicParser(BankParser):

    institution_key = "trade_republic"

    def detect(
        self,
        filename: str,
        header_row: list[str],
        sample_text: str,
    ) -> float:

        score = 0.0

        filename_lower = filename.lower()

        if (
            "trade" in filename_lower
            and "republic" in filename_lower
        ):
            score += 0.5

        compact_filename = (
            filename_lower
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

        if "traderepublic" in compact_filename:
            score += 0.2

        sample_lower = sample_text.lower()

        if "transacciones de cuenta" in sample_lower:
            score += 0.2

        if (
            "entrada de dinero" in sample_lower
            and "salida de dinero" in sample_lower
        ):
            score += 0.1

        if "balance" in sample_lower:
            score += 0.05

        if filename_lower.endswith(".pdf"):
            score += 0.1

        return min(score, 1.0)

    def parse(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> ParseResult:

        errors: list[ParseError] = []
        transactions: list[NormalizedTransaction] = []

        # ---------------------------------------------------------------
        # Validación de fichero
        # ---------------------------------------------------------------

        if not filename.lower().endswith(".pdf"):
            errors.append(
                ParseError(
                    0,
                    "Trade Republic debe importarse desde un PDF.",
                )
            )

            return ParseResult(
                self.institution_key,
                [],
                errors,
                0,
            )

        # ---------------------------------------------------------------
        # Leer PDF
        # ---------------------------------------------------------------

        try:
            text = _extract_pdf_text(
                file_bytes
            )

        except Exception as exc:
            return ParseResult(
                self.institution_key,
                [],
                [
                    ParseError(
                        0,
                        (
                            "No se pudo leer el PDF de "
                            f"Trade Republic: {exc}"
                        ),
                    )
                ],
                0,
            )

        # ---------------------------------------------------------------
        # Extraer exclusivamente la sección
        # TRANSACCIONES DE CUENTA
        # ---------------------------------------------------------------

        section = _find_transaction_section(
            text
        )

        if not section.strip():
            return ParseResult(
                self.institution_key,
                [],
                [
                    ParseError(
                        0,
                        (
                            "No se encontró la sección "
                            "'TRANSACCIONES DE CUENTA' "
                            "en el PDF de Trade Republic."
                        ),
                    )
                ],
                0,
            )

        # ---------------------------------------------------------------
        # Líneas
        # ---------------------------------------------------------------

        raw_lines = [
            _clean_pdf_line(line)
            for line in section.splitlines()
        ]

        raw_lines = [
            line
            for line in raw_lines
            if line
        ]

        # ---------------------------------------------------------------
        # IMPORTANTE:
        #
        # El extractor del PDF puede devolver:
        #
        #     16 sept
        #     2025
        #
        # en lugar de:
        #
        #     16 sept 2025
        #
        # Reconstruimos la fecha antes de procesar
        # las transacciones.
        # ---------------------------------------------------------------

        lines = _merge_wrapped_date_lines(
            raw_lines
        )

        # ---------------------------------------------------------------
        # Eliminar cabeceras
        # ---------------------------------------------------------------

        lines = [
            line
            for line in lines
            if not _looks_like_header(line)
        ]

        # ---------------------------------------------------------------
        # Procesar transacciones
        # ---------------------------------------------------------------

        i = 0
        parsed_rows = 0
        candidates: list[dict] = []

        while i < len(lines):

            line = lines[i]

            # -----------------------------------------------------------
            # Buscar fecha
            # -----------------------------------------------------------

            date_val, remainder = (
                _extract_date_from_line(line)
            )

            if date_val is None:
                i += 1
                continue

            parsed_rows += 1

            block_start = i + 1
            j = block_start

            # -----------------------------------------------------------
            # Buscar fin del bloque:
            #
            # una nueva fecha significa una nueva transacción.
            # -----------------------------------------------------------

            while j < len(lines):

                next_date, _ = (
                    _extract_date_from_line(
                        lines[j]
                    )
                )

                if (
                    j > block_start
                    and next_date is not None
                ):
                    break

                j += 1

            # -----------------------------------------------------------
            # Construir bloque textual
            # -----------------------------------------------------------

            block_lines: list[str] = []

            if remainder:
                block_lines.append(
                    remainder
                )

            block_lines.extend(
                lines[block_start:j]
            )

            # -----------------------------------------------------------
            # Extraer todos los importes
            # -----------------------------------------------------------

            money_values: list[Decimal] = []

            for block_line in block_lines:

                values = _extract_money_values(
                    block_line
                )

                money_values.extend(
                    values
                )

            # -----------------------------------------------------------
            # Si no hay importes
            # -----------------------------------------------------------

            if not money_values:

                errors.append(
                    ParseError(
                        parsed_rows,
                        (
                            "No se encontraron importes "
                            "para la transacción de "
                            f"{line}"
                        ),
                        raw_row="\n".join(
                            [line] + block_lines
                        ),
                    )
                )

                i = j
                continue

            # -----------------------------------------------------------
            # Quitar importes del texto
            # -----------------------------------------------------------

            text_lines: list[str] = []

            for block_line in block_lines:

                cleaned = MONEY_RE.sub(
                    " ",
                    block_line,
                )

                cleaned = _clean_pdf_line(
                    cleaned
                )

                if cleaned:
                    text_lines.append(
                        cleaned
                    )

            # -----------------------------------------------------------
            # Necesitamos al menos tipo/descripción
            # -----------------------------------------------------------

            if not text_lines:

                errors.append(
                    ParseError(
                        parsed_rows,
                        (
                            "No se encontró tipo o "
                            "descripción para la "
                            f"transacción de {line}"
                        ),
                        raw_row="\n".join(
                            [line] + block_lines
                        ),
                    )
                )

                i = j
                continue

            # -----------------------------------------------------------
            # Tipo y descripción
            # -----------------------------------------------------------

            raw_type = text_lines[0]

            raw_description = " ".join(
                text_lines[1:]
            ).strip()

            if not raw_description:
                raw_description = raw_type

            combined = (
                f"{raw_type} "
                f"{raw_description}"
            ).strip()

            # -----------------------------------------------------------
            # Importe
            #
            # En Trade Republic:
            #
            # primer importe = movimiento
            # segundo importe = balance
            #
            # Ejemplo:
            #
            #     10,00 € 10,00 €
            #
            # primer 10 € = movimiento
            # segundo 10 € = balance
            # -----------------------------------------------------------

            movement_amount = money_values[0]

            # -----------------------------------------------------------
            # Tipo
            # -----------------------------------------------------------

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

            elif DEPOSIT_RE.search(combined):

                tx_type = "TRANSFER"

            elif WITHDRAWAL_RE.search(combined):

                tx_type = "TRANSFER"

            elif TRANSFER_RE.search(combined):

                tx_type = "TRANSFER"

            elif CARD_RE.search(combined):

                tx_type = "EXPENSE"

            elif movement_amount > 0:

                tx_type = "INCOME"

            elif movement_amount < 0:

                tx_type = "EXPENSE"

            # -----------------------------------------------------------
            # Transferencia
            # -----------------------------------------------------------

            is_transfer_hint = (
                tx_type == "TRANSFER"
            )

            # -----------------------------------------------------------
            # Activo
            # -----------------------------------------------------------

            asset = None

            if tx_type in {
                "INVESTMENT_BUY",
                "INVESTMENT_SELL",
                "DIVIDEND",
            }:

                if raw_description:
                    asset = raw_description

            # -----------------------------------------------------------
            # Guardamos el candidato y resolvemos el signo después usando
            # la columna BALANCE.
            #
            # Trade Republic puede presentar:
            #   72,99 € 937,01 €
            # aunque 72,99 € sea una salida. El balance permite determinar
            # que 937,01 - 1.010,00 = -72,99.
            # -----------------------------------------------------------

            balance_value = (
                money_values[-1]
                if len(money_values) >= 2
                else None
            )

            explicit_amount = (
                movement_amount
                if movement_amount != 0
                else Decimal("0")
            )

            candidates.append({
                "date": date_val,
                "movement": movement_amount,
                "balance": balance_value,
                "explicit_amount": explicit_amount,
                "description": raw_description,
                "raw_description": combined,
                "type": tx_type,
                "raw_text": combined,
                "merchant": (
                    asset
                    if tx_type in {
                        "INVESTMENT_BUY",
                        "INVESTMENT_SELL",
                        "DIVIDEND",
                    }
                    else None
                ),
                "is_transfer_hint": is_transfer_hint,
                "extra": {"asset": asset} if asset else {},
            })

            i = j

        # Resolver todos los signos después de tener la secuencia de balances.
        resolved_amounts = _resolve_trade_republic_amounts(candidates)

        for candidate, resolved_amount in zip(candidates, resolved_amounts):
            tx_type = candidate["type"]

            # Si el documento no daba una dirección explícita, el signo
            # resuelto determina ingreso/gasto.
            if tx_type == "UNKNOWN":
                tx_type = "INCOME" if resolved_amount > 0 else "EXPENSE"

            transactions.append(
                NormalizedTransaction(
                    date=candidate["date"],
                    value_date=None,
                    amount=resolved_amount,
                    currency="EUR",
                    description=candidate["description"],
                    raw_description=candidate["raw_description"],
                    source=self.institution_key,
                    type=tx_type,
                    merchant=candidate["merchant"],
                    is_transfer_hint=candidate["is_transfer_hint"],
                    extra=candidate["extra"],
                )
            )

        # ---------------------------------------------------------------
        # Resultado
        # ---------------------------------------------------------------

        if parsed_rows == 0:

            errors.append(
                ParseError(
                    0,
                    (
                        "No se encontraron transacciones "
                        "en la sección "
                        "'TRANSACCIONES DE CUENTA' "
                        "del PDF de Trade Republic."
                    ),
                    raw_row=section[:5000],
                )
            )

        return ParseResult(
            self.institution_key,
            transactions,
            errors,
            parsed_rows,
        )