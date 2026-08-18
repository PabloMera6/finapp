"""
Servicio de deduplicación (sección 12).

Regla:
  - Si el archivo aporta external_id -> se usa como parte de la huella.
  - Si no -> huella basada en cuenta + fecha + importe + descripción + moneda
    + número de ocurrencia (seq) dentro de ese mismo grupo.

La huella se compara dentro de la misma cuenta (uq_transaction_fingerprint
en el modelo Transaction), de forma que reimportar el mismo archivo (o uno
con movimientos solapados) no genera duplicados.

Por qué existe "seq":
  Sin un identificador único del banco, dos movimientos reales y distintos
  pueden coincidir exactamente en fecha + importe + descripción (p. ej. dos
  Bizums de la misma cantidad el mismo día, o dos compras iguales en el
  mismo comercio el mismo día). Si la huella no distinguiera entre ellos,
  el segundo movimiento se descartaría como si fuera un duplicado del
  primero, cuando en realidad es una transacción legítima aparte.

  "seq" es la posición (0, 1, 2...) de esa transacción dentro del grupo de
  movimientos que comparten fecha+importe+descripción+moneda, contando en
  el orden en que aparecen en el archivo. Esto hace que:
    - Los N movimientos idénticos de un mismo archivo generen N huellas
      distintas (seq=0, seq=1, ...), así que todos se guardan.
    - Si ese mismo archivo se reimporta tal cual, se generan exactamente
      las mismas N huellas (mismo orden -> mismo seq), así que los N
      movimientos se siguen detectando como duplicados correctamente.
    - Si se importa un archivo distinto que por casualidad solo comparte
      ALGUNOS de esos movimientos (no todos, o en otro orden), el
      comportamiento puede diferir; en ese caso es preferible pecar de
      importar de más (y poder borrar a mano) que de descartar movimientos
      reales silenciosamente.
"""
import hashlib
import re
from collections import defaultdict

from app.parsers.base import NormalizedTransaction


def _normalize_description(desc: str) -> str:
    desc = desc.upper().strip()
    desc = re.sub(r"\s+", " ", desc)
    return desc


def _base_key(tx: NormalizedTransaction) -> str:
    """Clave de agrupación sin seq: identifica movimientos 'iguales a simple vista'."""
    date_key = tx.date.strftime("%Y-%m-%d")
    amount_key = f"{tx.amount:.2f}"
    desc_key = _normalize_description(tx.description)[:80]
    return f"{date_key}|{amount_key}|{desc_key}|{tx.currency}"


def compute_fingerprint(account_id: str, tx: NormalizedTransaction, seq: int = 0) -> str:
    """
    Calcula la huella de una transacción.

    `seq` es el número de ocurrencia (empezando en 0) de esta transacción
    dentro del grupo de movimientos que comparten fecha+importe+descripción
    +moneda en el mismo archivo/lote. Ver docstring del módulo para el porqué.
    Quien llama con una sola transacción aislada (sin agrupar) debe dejar
    seq=0, que es el comportamiento por defecto y previo a este cambio.
    """
    if tx.external_id:
        raw = f"{account_id}|EXT|{tx.external_id}"
    else:
        raw = f"{account_id}|{_base_key(tx)}|SEQ{seq}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_fingerprints_for_batch(
    account_id: str, transactions: list[NormalizedTransaction],
) -> list[str]:
    """
    Calcula las huellas de una lista de transacciones perteneciente al mismo
    archivo/lote, asignando automáticamente el "seq" correcto a cada una
    según cuántas veces haya aparecido ya ese mismo grupo (fecha+importe+
    descripción+moneda) en la lista, en el orden en que vienen.

    Devuelve una lista de huellas en el mismo orden que `transactions`.
    """
    seen_counts: dict[str, int] = defaultdict(int)
    fingerprints = []
    for tx in transactions:
        if tx.external_id:
            fingerprints.append(compute_fingerprint(account_id, tx))
            continue
        key = _base_key(tx)
        seq = seen_counts[key]
        seen_counts[key] += 1
        fingerprints.append(compute_fingerprint(account_id, tx, seq=seq))
    return fingerprints
