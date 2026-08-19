from decimal import Decimal

from app.parsers.imagin import ImaginParser
from app.parsers.myinvestor import MyInvestorParser
from app.parsers.trade_republic import TradeRepublicParser

IMAGIN_CSV = b"""Fecha,Concepto,Importe,Saldo
01/07/2026,NOMINA EMPRESA FICTICIA SL,2100.00,2450.30
02/07/2026,MERCADONA,-54.20,2396.10
03/07/2026,BIZUM A Maria,-30.00,2366.10
04/07/2026,BIZUM,-12.50,2353.60
"""

MYINVESTOR_CSV = b"""Fecha,Concepto,Importe,Tipo
01/07/2026,TRASPASO DESDE IMAGIN,300.00,Transferencia
05/07/2026,COMPRA FONDO INDEXADO GLOBAL,-300.00,Compra
15/08/2026,DIVIDENDO ETF,4.50,Dividendo
"""

TRADE_REPUBLIC_PDF_TEXT = """TRANSACCIONES DE CUENTA
FECHA TIPO DESCRIPCIÓN ENTRADA DE DINERO SALIDA DE DINERO BALANCE
16 sept 2025
Transferencia Incoming transfer from PABLO MERA GOMEZ 10,00 € 10,00 €
17 sept 2025
Transferencia Incoming transfer from PABLO MERA GOMEZ 1.000,00 € 1.010,00 €
27 sept 2025
Transacción con tarjeta MEDIA MARKT PUERTO REAL 72,99 € 937,01 €
30 sept 2025
Transacción con tarjeta EMASA CADIZ 12,35 € 924,66 €
RESUMEN DEL BALANCE
"""


def test_imagin_detects_columns_and_parses_amounts():
    parser = ImaginParser()
    result = parser.parse(IMAGIN_CSV, "imagin_movimientos.csv")
    assert result.total_rows == 4
    assert len(result.errors) == 0
    assert result.transactions[0].amount == Decimal("2100.00")
    assert result.transactions[0].type == "INCOME"
    assert result.transactions[1].type == "EXPENSE"


def test_imagin_bizum_recipient_extracted_when_present():
    parser = ImaginParser()
    result = parser.parse(IMAGIN_CSV, "imagin_movimientos.csv")
    bizum_with_name = result.transactions[2]
    assert bizum_with_name.is_bizum is True
    assert bizum_with_name.bizum_recipient == "Maria"
    assert bizum_with_name.bizum_direction == "SENT"


def test_imagin_bizum_recipient_null_when_not_available():
    """Requisito crítico: nunca inventar el destinatario de un Bizum."""
    parser = ImaginParser()
    result = parser.parse(IMAGIN_CSV, "imagin_movimientos.csv")
    bizum_without_name = result.transactions[3]
    assert bizum_without_name.is_bizum is True
    assert bizum_without_name.bizum_recipient is None


def test_imagin_detect_confidence_high_for_matching_file():
    parser = ImaginParser()
    header = ["Fecha", "Concepto", "Importe", "Saldo"]
    score = parser.detect("imagin_export.csv", header, "BIZUM A Maria")
    assert score >= 0.7


def test_myinvestor_distinguishes_investment_from_transfer():
    parser = MyInvestorParser()
    result = parser.parse(MYINVESTOR_CSV, "myinvestor_export.csv")
    types = [t.type for t in result.transactions]
    assert "TRANSFER" in types
    assert "INVESTMENT_BUY" in types
    assert "DIVIDEND" in types


def test_trade_republic_uses_balance_to_resolve_positive_and_negative_movements(monkeypatch):
    parser = TradeRepublicParser()
    monkeypatch.setattr(
        "app.parsers.trade_republic._extract_pdf_text",
        lambda _: TRADE_REPUBLIC_PDF_TEXT,
    )
    result = parser.parse(b"%PDF-fake", "trade_republic_export.pdf")
    assert [t.amount for t in result.transactions] == [
        Decimal("10.00"),
        Decimal("1000.00"),
        Decimal("-72.99"),
        Decimal("-12.35"),
    ]
    # Las transferencias entrantes son dinero real y deben contabilizarse
    # como ingreso (INCOME). Solo se excluyen del análisis si
    # TransferDetector las confirma como transferencia entre cuentas
    # propias del usuario (is_internal_transfer), lo cual es un paso
    # posterior e independiente del parseo.
    assert [t.type for t in result.transactions] == [
        "INCOME", "INCOME", "EXPENSE", "EXPENSE"
    ]
    assert [t.is_transfer_hint for t in result.transactions] == [
        True, True, False, False
    ]


def test_trade_republic_stops_at_balance_summary(monkeypatch):
    parser = TradeRepublicParser()
    monkeypatch.setattr(
        "app.parsers.trade_republic._extract_pdf_text",
        lambda _: TRADE_REPUBLIC_PDF_TEXT + "\n99 oct 2025 Fake 999,00 € 9999,00 €",
    )
    result = parser.parse(b"%PDF-fake", "trade_republic_export.pdf")
    assert len(result.transactions) == 4
