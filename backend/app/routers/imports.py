"""
Endpoints de importación (sección 7 y 42).

Flujo:
  POST /api/imports/preview   -> sube el archivo, detecta entidad, normaliza,
                                  compara contra existentes y devuelve una
                                  previsualización + un import_token temporal.
  POST /api/imports/confirm   -> usando el import_token, persiste los
                                  movimientos nuevos, evitando duplicados,
                                  detecta transferencias y categoriza.

El import_token vive en una caché en memoria con TTL. Para un despliegue
multi-instancia esto debería moverse a Redis; documentado como limitación
conocida de esta primera versión (sección 58).

Los formatos soportados dependen del parser de cada entidad:

  - imagin: CSV/XLSX
  - MyInvestor: CSV/XLSX
  - Trade Republic: PDF

Se permite PDF explícitamente porque Trade Republic exporta los movimientos
de cuenta en este formato.
"""

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Account, ImportBatch, Transaction, TransactionType, User
from app.parsers.registry import detect_institution, get_parser
from app.schemas import ImportConfirmRequest
from app.services.categorizer import categorize_transaction
from app.services.dedup import compute_fingerprint, compute_fingerprints_for_batch
from app.services.transfer_detector import detect_internal_transfers


router = APIRouter(
    prefix="/api/imports",
    tags=["imports"],
)

settings = get_settings()


# Caché temporal de previsualizaciones:
# token -> {
#     expires_at,
#     institution,
#     transactions,
#     account_id,
# }
#
# Para un despliegue multi-instancia debería moverse a Redis.
_PREVIEW_CACHE: dict[str, dict] = {}

PREVIEW_TTL_SECONDS = 900


# ---------------------------------------------------------------------------
# Extensiones permitidas
# ---------------------------------------------------------------------------

def _get_allowed_extensions() -> tuple[str, ...]:
    """
    Obtiene las extensiones permitidas desde configuración y garantiza que
    PDF esté soportado.

    Esto es importante porque una configuración antigua puede tener algo como:

        ALLOWED_UPLOAD_EXTENSIONS=.csv,.xlsx,.xls

    y, aunque Trade Republic tenga parser PDF, el endpoint rechazaría
    el archivo antes de llegar al parser.

    Si PDF ya está configurado, no se duplica.
    """
    configured = getattr(
        settings,
        "allowed_upload_extensions",
        "",
    ) or ""

    extensions: list[str] = []

    for extension in configured.split(","):
        extension = extension.strip().lower()

        if not extension:
            continue

        if not extension.startswith("."):
            extension = f".{extension}"

        if extension not in extensions:
            extensions.append(extension)

    # Trade Republic utiliza PDF.
    if ".pdf" not in extensions:
        extensions.append(".pdf")

    return tuple(extensions)


ALLOWED_EXTENSIONS = _get_allowed_extensions()


def _is_allowed_file(filename: str) -> bool:
    """
    Comprueba la extensión del archivo.

    No dependemos únicamente de UploadFile.content_type porque algunos
    clientes/proxies envían application/octet-stream incluso para PDFs.
    """
    if not filename:
        return False

    filename_lower = filename.lower().strip()

    return filename_lower.endswith(ALLOWED_EXTENSIONS)


def _cleanup_cache():
    now = time.time()

    expired = [
        key
        for key, value in _PREVIEW_CACHE.items()
        if value["expires_at"] < now
    ]

    for key in expired:
        del _PREVIEW_CACHE[key]


# ---------------------------------------------------------------------------
# Listado de importaciones
# ---------------------------------------------------------------------------

@router.get("")
def list_imports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    batches = (
        db.query(ImportBatch)
        .filter(ImportBatch.user_id == user.id)
        .order_by(ImportBatch.created_at.desc())
        .all()
    )

    return [
        {
            "id": batch.id,
            "filename": batch.filename,
            "institution": batch.institution,
            "total_rows": batch.total_rows,
            "imported_rows": batch.imported_rows,
            "duplicate_rows": batch.duplicate_rows,
            "error_rows": batch.error_rows,
            "status": batch.status,
            "created_at": batch.created_at.isoformat(),
        }
        for batch in batches
    ]


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

@router.post("/preview")
def preview_import(
    file: UploadFile = File(...),
    institution: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _cleanup_cache()

    filename = file.filename or ""

    # ---------------------------------------------------------------
    # Validación del formato
    # ---------------------------------------------------------------

    if not _is_allowed_file(filename):
        raise HTTPException(
            status_code=400,
            detail=(
                "Formato no soportado. "
                f"Permitidos: {ALLOWED_EXTENSIONS}"
            ),
        )

    # ---------------------------------------------------------------
    # Lectura del archivo
    # ---------------------------------------------------------------

    file_bytes = file.file.read()

    max_bytes = (
        settings.max_upload_size_mb
        * 1024
        * 1024
    )

    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                "El archivo supera el límite de "
                f"{settings.max_upload_size_mb}MB"
            ),
        )

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="El archivo está vacío.",
        )

    # ---------------------------------------------------------------
    # Detección de entidad
    #
    # detect_institution() debe encargarse de llamar a los parsers.
    # En el caso de Trade Republic, el parser reconoce:
    #
    #   - extensión PDF
    #   - TRANSACCIONES DE CUENTA
    #   - ENTRADA DE DINERO
    #   - SALIDA DE DINERO
    #   - BALANCE
    #
    # Por tanto, no convertimos el PDF ni intentamos leerlo como CSV aquí.
    # ---------------------------------------------------------------

    detected_institution, confidence = detect_institution(
        file_bytes,
        filename,
    )

# Si el usuario indica una entidad, respetamos esa selección.
# Si no indica ninguna y el detector no reconoce el archivo,
# asumimos que es un extracto de Trade Republic.
    chosen_institution = (
        institution
        or detected_institution
        or "trade_republic"
    )

# Si hemos tenido que hacer fallback a Trade Republic,
# dejamos una confianza baja pero permitimos continuar.
    if not detected_institution and not institution:
        confidence = 0.0

    # ---------------------------------------------------------------
    # Obtener parser
    # ---------------------------------------------------------------

    try:
        parser = get_parser(chosen_institution)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No existe un parser configurado para "
                f"'{chosen_institution}': {exc}"
            ),
        ) from exc

    # ---------------------------------------------------------------
    # Parsear
    #
    # Aquí es donde:
    #
    #   imagin      -> CSV/XLSX
    #   MyInvestor  -> CSV/XLSX
    #   Trade Rep.  -> PDF
    #
    # Cada parser decide cómo interpretar el contenido.
    # ---------------------------------------------------------------

    result = parser.parse(
        file_bytes,
        filename,
    )

    # ---------------------------------------------------------------
    # Buscar fingerprints existentes
    # ---------------------------------------------------------------

    existing_fingerprints: set[str] = set()

    user_accounts = (
        db.query(Account)
        .filter(
            Account.user_id == user.id,
            Account.institution == chosen_institution,
        )
        .all()
    )

    account_ids = [
        account.id
        for account in user_accounts
    ]

    if account_ids:
        rows = (
            db.query(Transaction.fingerprint)
            .filter(
                Transaction.account_id.in_(account_ids)
            )
            .all()
        )

        existing_fingerprints = {
            row[0]
            for row in rows
            if row[0]
        }

    # ---------------------------------------------------------------
    # Construir preview
    # ---------------------------------------------------------------

    sample = []

    new_count = 0
    dup_count = 0

    placeholder_account_id = (
        account_ids[0]
        if account_ids
        else "PREVIEW"
    )

    batch_fingerprints = compute_fingerprints_for_batch(
        placeholder_account_id,
        result.transactions,
    )

    for i, tx in enumerate(result.transactions):
        fingerprint = batch_fingerprints[i]

        is_dup = fingerprint in existing_fingerprints

        if is_dup:
            dup_count += 1
        else:
            new_count += 1

        if i < 50:
            sample.append(
                {
                    "row_index": i,
                    "date": (
                        tx.date.strftime("%d/%m/%Y")
                        if tx.date
                        else None
                    ),
                    "value_date": (
                        tx.value_date.strftime("%d/%m/%Y")
                        if tx.value_date
                        else None
                    ),
                    "description": tx.description,
                    "amount": (
                        f"{tx.amount:.2f}"
                        if tx.amount is not None
                        else None
                    ),
                    "currency": tx.currency,
                    "detected_type": tx.type,
                    "is_duplicate": is_dup,
                }
            )

    # ---------------------------------------------------------------
    # Errores del parser
    # ---------------------------------------------------------------

    for err in result.errors[:20]:
        sample.append(
            {
                "row_index": err.row_index,
                "date": None,
                "value_date": None,
                "description": err.message,
                "amount": None,
                "currency": None,
                "detected_type": None,
                "is_duplicate": False,
                "error": err.message,
            }
        )

    # ---------------------------------------------------------------
    # Guardar preview temporal
    # ---------------------------------------------------------------

    token = str(uuid.uuid4())

    _PREVIEW_CACHE[token] = {
        "expires_at": (
            time.time()
            + PREVIEW_TTL_SECONDS
        ),
        "institution": chosen_institution,
        "transactions": result.transactions,
        "filename": filename,
        "total_rows": result.total_rows,
        "error_rows": len(result.errors),
    }

    return {
        "detected_institution": detected_institution,
        "confidence": confidence,
        "chosen_institution": chosen_institution,
        "filename": filename,
        "file_extension": (
            filename.rsplit(".", 1)[-1].lower()
            if "." in filename
            else None
        ),
        "total_rows": result.total_rows,
        "new_rows": new_count,
        "duplicate_rows": dup_count,
        "error_rows": len(result.errors),
        "sample": sample,
        "import_token": token,
        "existing_accounts": [
            {
                "id": account.id,
                "account_name": account.account_name,
            }
            for account in user_accounts
        ],
    }


# ---------------------------------------------------------------------------
# Confirmación
# ---------------------------------------------------------------------------

@router.post("/confirm")
def confirm_import(
    payload: ImportConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _cleanup_cache()

    cached = _PREVIEW_CACHE.get(
        payload.import_token
    )

    if not cached:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "La previsualización ha expirado. "
                "Vuelve a subir el archivo."
            ),
        )

    # ---------------------------------------------------------------
    # Resolver cuenta destino
    # ---------------------------------------------------------------

    account: Optional[Account] = None

    if payload.account_id:
        account = (
            db.query(Account)
            .filter(
                Account.id == payload.account_id,
                Account.user_id == user.id,
            )
            .first()
        )

        if not account:
            raise HTTPException(
                status_code=404,
                detail="Cuenta no encontrada",
            )

    else:
        name = (
            payload.new_account_name
            or f"{payload.institution} - cuenta principal"
        )

        account = Account(
            user_id=user.id,
            institution=payload.institution,
            account_name=name,
            account_type=(
                "investment"
                if payload.institution == "trade_republic"
                else "checking"
            ),
            currency="EUR",
        )

        db.add(account)
        db.flush()

    # ---------------------------------------------------------------
    # Crear batch
    # ---------------------------------------------------------------

    batch = ImportBatch(
        user_id=user.id,
        account_id=account.id,
        institution=payload.institution,
        filename=cached["filename"],
        total_rows=cached["total_rows"],
        error_rows=cached["error_rows"],
        status="completed",
    )

    db.add(batch)
    db.flush()

    # ---------------------------------------------------------------
    # Persistir transacciones
    # ---------------------------------------------------------------

    imported = 0
    duplicates = 0

    batch_fingerprints = compute_fingerprints_for_batch(
        account.id,
        cached["transactions"],
    )

    for i, tx in enumerate(cached["transactions"]):
        fingerprint = batch_fingerprints[i]

        exists = (
            db.query(Transaction.id)
            .filter(
                Transaction.account_id == account.id,
                Transaction.fingerprint == fingerprint,
            )
            .first()
        )

        if exists:
            duplicates += 1
            continue

        try:
            tx_type = TransactionType(tx.type)
        except ValueError:
            tx_type = TransactionType.UNKNOWN

        db_tx = Transaction(
            account_id=account.id,
            external_id=tx.external_id,
            fingerprint=fingerprint,
            date=tx.date,
            value_date=tx.value_date,
            amount=tx.amount,
            currency=tx.currency,
            description=tx.description,
            raw_description=tx.raw_description,
            type=tx_type,
            merchant=tx.merchant,
            counterparty=tx.counterparty,
            is_bizum=tx.is_bizum,
            bizum_direction=tx.bizum_direction,
            bizum_recipient=tx.bizum_recipient,
            source=tx.source,
            import_batch_id=batch.id,
        )

        db.add(db_tx)
        db.flush()

        categorize_transaction(
            db,
            user.id,
            db_tx,
        )

        imported += 1

    # ---------------------------------------------------------------
    # Actualizar batch
    # ---------------------------------------------------------------

    batch.imported_rows = imported
    batch.duplicate_rows = duplicates

    db.commit()

    # ---------------------------------------------------------------
    # Detectar transferencias internas
    # ---------------------------------------------------------------

    pairs = detect_internal_transfers(
        db,
        user.id,
    )

    # ---------------------------------------------------------------
    # Eliminar preview consumida
    # ---------------------------------------------------------------

    del _PREVIEW_CACHE[payload.import_token]

    return {
        "import_batch_id": batch.id,
        "account_id": account.id,
        "imported": imported,
        "duplicates": duplicates,
        "transfer_pairs_detected": pairs,
    }