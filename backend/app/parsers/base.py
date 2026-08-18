"""
Interfaces base del sistema de importación.

Arquitectura pensada para poder añadir en el futuro:
  - Nuevos bancos (BBVA, Santander, CaixaBank...)
  - Open Banking / PSD2 (implementando TransactionProvider.PSD2Provider)
sin modificar el resto de la aplicación (dashboard, analítica, etc.)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class NormalizedTransaction:
    """Estructura común a la que todos los parsers deben convertir sus datos."""
    date: datetime
    amount: Decimal
    currency: str
    description: str
    raw_description: str
    source: str  # imagin | myinvestor | trade_republic
    external_id: Optional[str] = None
    value_date: Optional[datetime] = None
    merchant: Optional[str] = None
    counterparty: Optional[str] = None
    type: str = "UNKNOWN"
    is_bizum: bool = False
    bizum_direction: Optional[str] = None
    bizum_recipient: Optional[str] = None  # NULL si no se puede determinar. Nunca inventar.
    is_transfer_hint: bool = False  # pista inicial del parser; la confirmación final la hace TransferDetector
    extra: dict = field(default_factory=dict)  # datos originales útiles no mapeados


@dataclass
class ParseError:
    row_index: int
    message: str
    raw_row: Optional[str] = None


@dataclass
class ParseResult:
    institution: str
    transactions: list[NormalizedTransaction]
    errors: list[ParseError]
    total_rows: int


class BankParser(ABC):
    """Contrato que debe implementar cada parser de entidad bancaria."""

    institution_key: str

    @abstractmethod
    def detect(self, filename: str, header_row: list[str], sample_text: str) -> float:
        """
        Devuelve una puntuación de confianza (0.0-1.0) de que el archivo
        pertenece a esta entidad, basada en nombre de archivo y cabeceras.
        """
        raise NotImplementedError

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        """Convierte el archivo crudo en una lista de NormalizedTransaction."""
        raise NotImplementedError


class TransactionProvider(ABC):
    """
    Abstracción de origen de movimientos.
    FileImportProvider (implementado) usa archivos exportados por el usuario.
    PSD2Provider (futuro) usaría Open Banking sin credenciales almacenadas
    por la propia aplicación, delegando en un agregador PSD2 licenciado.
    """

    @abstractmethod
    def fetch(self, **kwargs) -> ParseResult:
        raise NotImplementedError


class FileImportProvider(TransactionProvider):
    def __init__(self, parser: BankParser):
        self.parser = parser

    def fetch(self, file_bytes: bytes, filename: str) -> ParseResult:
        return self.parser.parse(file_bytes, filename)


# Placeholder documentado explícitamente (sección 35): NO implementado en esta versión.
class PSD2Provider(TransactionProvider):
    """
    NO IMPLEMENTADO. Reservado para una futura integración PSD2/Open Banking
    a través de un agregador licenciado (p.ej. un TPP autorizado por el Banco
    de España / EBA). La aplicación nunca almacenará credenciales bancarias
    directamente; en un PSD2Provider real, el token de acceso lo custodiaría
    el agregador, no esta aplicación.
    """

    def fetch(self, **kwargs) -> ParseResult:
        raise NotImplementedError("PSD2 no está implementado en esta versión.")
