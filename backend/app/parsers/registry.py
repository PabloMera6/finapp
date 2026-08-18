"""
Registro central de parsers disponibles + detección automática de entidad
(sección 41: "Importación inteligente").
"""
from __future__ import annotations

import io

import pandas as pd

from app.parsers.base import BankParser
from app.parsers.imagin import ImaginParser
from app.parsers.myinvestor import MyInvestorParser
from app.parsers.trade_republic import TradeRepublicParser

PARSERS: dict[str, BankParser] = {
    "imagin": ImaginParser(),
    "myinvestor": MyInvestorParser(),
    "trade_republic": TradeRepublicParser(),
}


def detect_institution(file_bytes: bytes, filename: str) -> tuple[str | None, float]:
    """Devuelve (institution_key, confidence) o (None, 0.0) si no hay coincidencia clara."""
    try:
        lower_name = filename.lower()
        if lower_name.endswith((".xlsx", ".xls")):
            df_head = pd.read_excel(io.BytesIO(file_bytes), dtype=str, nrows=5)
            header_row = list(df_head.columns)
            sample_text = df_head.to_csv(index=False)
        elif lower_name.endswith(".pdf"):
            # Para PDF no existe una fila CSV. Extraemos una pequeña muestra
            # de texto para que Trade Republic pueda detectarse aunque el
            # archivo tenga un nombre genérico.
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            sample_text = "\n".join((page.extract_text() or "") for page in reader.pages[:2])
            header_row = []
        else:
            df_head = pd.read_csv(io.BytesIO(file_bytes), dtype=str, sep=None, engine="python", nrows=5)
            header_row = list(df_head.columns)
            sample_text = df_head.to_csv(index=False)
    except Exception:
        header_row, sample_text = [], filename

    best_key, best_score = None, 0.0
    for key, parser in PARSERS.items():
        score = parser.detect(filename, header_row, sample_text)
        if score > best_score:
            best_key, best_score = key, score

    if best_score < 0.3:
        return None, best_score
    return best_key, best_score


def get_parser(institution: str) -> BankParser:
    if institution not in PARSERS:
        raise ValueError(f"Entidad desconocida: {institution}")
    return PARSERS[institution]
