from datetime import datetime
from decimal import Decimal

from app.parsers.base import NormalizedTransaction
from app.services.dedup import compute_fingerprint, compute_fingerprints_for_batch


def _tx(**overrides) -> NormalizedTransaction:
    base = dict(
        date=datetime(2026, 7, 1),
        amount=Decimal("-54.20"),
        currency="EUR",
        description="MERCADONA",
        raw_description="MERCADONA",
        source="imagin",
    )
    base.update(overrides)
    return NormalizedTransaction(**base)


def test_same_transaction_produces_same_fingerprint():
    tx1 = _tx()
    tx2 = _tx()
    assert compute_fingerprint("account-1", tx1) == compute_fingerprint("account-1", tx2)


def test_different_amount_produces_different_fingerprint():
    tx1 = _tx(amount=Decimal("-54.20"))
    tx2 = _tx(amount=Decimal("-54.21"))
    assert compute_fingerprint("account-1", tx1) != compute_fingerprint("account-1", tx2)


def test_different_account_produces_different_fingerprint():
    tx = _tx()
    assert compute_fingerprint("account-1", tx) != compute_fingerprint("account-2", tx)


def test_external_id_takes_precedence():
    tx1 = _tx(external_id="EXT-123", description="A")
    tx2 = _tx(external_id="EXT-123", description="B")
    # Mismo external_id -> misma huella aunque cambie la descripción
    assert compute_fingerprint("account-1", tx1) == compute_fingerprint("account-1", tx2)


def test_description_case_and_whitespace_normalized():
    tx1 = _tx(description="Mercadona   Madrid")
    tx2 = _tx(description="MERCADONA MADRID")
    assert compute_fingerprint("account-1", tx1) == compute_fingerprint("account-1", tx2)


def test_batch_gives_distinct_fingerprints_to_identical_transactions():
    """
    Dos Bizums idénticos (misma fecha, importe y descripción) en el mismo
    lote deben recibir huellas distintas, para que ninguno se descarte como
    'duplicado' del otro. Ver docstring de app/services/dedup.py.
    """
    bizum1 = _tx(description="BIZUM DE JUAN PEREZ", amount=Decimal("20.00"))
    otro = _tx(description="MERCADONA", amount=Decimal("-15.30"))
    bizum2 = _tx(description="BIZUM DE JUAN PEREZ", amount=Decimal("20.00"))

    fingerprints = compute_fingerprints_for_batch("account-1", [bizum1, otro, bizum2])

    assert len(fingerprints) == 3
    assert len(set(fingerprints)) == 3  # las tres deben ser distintas entre sí


def test_batch_reimport_produces_identical_fingerprints():
    """
    Reimportar exactamente el mismo lote (mismo orden) debe producir
    exactamente las mismas huellas, para que la reimportación siga
    detectándose correctamente como duplicado.
    """
    batch = [
        _tx(description="BIZUM DE JUAN PEREZ", amount=Decimal("20.00")),
        _tx(description="MERCADONA", amount=Decimal("-15.30")),
        _tx(description="BIZUM DE JUAN PEREZ", amount=Decimal("20.00")),
    ]

    first = compute_fingerprints_for_batch("account-1", batch)
    second = compute_fingerprints_for_batch("account-1", batch)

    assert first == second


def test_batch_single_occurrence_matches_first_seq_of_group():
    """La huella de una transacción aislada coincide con la de seq=0 dentro de un grupo,
    de forma que un fichero que solo trae una de esas repeticiones se sigue detectando
    como duplicado de la primera ocurrencia ya importada."""
    grouped = compute_fingerprints_for_batch(
        "account-1",
        [
            _tx(description="BIZUM DE JUAN PEREZ", amount=Decimal("20.00")),
            _tx(description="BIZUM DE JUAN PEREZ", amount=Decimal("20.00")),
        ],
    )
    isolated = compute_fingerprints_for_batch(
        "account-1",
        [_tx(description="BIZUM DE JUAN PEREZ", amount=Decimal("20.00"))],
    )
    assert isolated[0] == grouped[0]


def test_batch_respects_external_id_ignoring_seq():
    """Si el banco aporta external_id, ese identificador manda y no se agrupa por seq,
    incluso si dos filas del lote comparten el mismo external_id (se tratan como
    la misma transacción, igual que sin batch)."""
    tx1 = _tx(external_id="EXT-1", description="A")
    tx2 = _tx(external_id="EXT-1", description="B")
    fingerprints = compute_fingerprints_for_batch("account-1", [tx1, tx2])
    assert fingerprints[0] == fingerprints[1]
