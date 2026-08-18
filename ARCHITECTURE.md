# Arquitectura

## 1. Visión general del despliegue

```mermaid
flowchart TB
    U[Usuario] -->|HTTPS| RP[Reverse proxy<br/>Nginx/Caddy/Traefik]
    RP --> FE[Frontend Next.js<br/>puerto 3000]
    RP --> BE[Backend FastAPI<br/>puerto 8000]
    FE -->|fetch API, credentials: include| BE
    BE -->|red interna Docker<br/>sin puerto publicado| DB[(PostgreSQL 16)]
```

`docker-compose.yml` define dos redes: `finapp_public` (frontend y backend)
y `finapp_internal` (backend y base de datos, `internal: true`, sin salida
a Internet ni acceso desde el host).

## 2. Flujo de importación

```mermaid
sequenceDiagram
    participant U as Usuario
    participant FE as Frontend
    participant BE as Backend
    participant P as BankParser
    participant DB as PostgreSQL

    U->>FE: Sube archivo (drag&drop)
    FE->>BE: POST /api/imports/preview
    BE->>P: detect() + parse()
    P-->>BE: NormalizedTransaction[]
    BE->>DB: compara huellas existentes
    BE-->>FE: preview (nuevos/duplicados/errores) + import_token
    U->>FE: Confirma importación
    FE->>BE: POST /api/imports/confirm
    BE->>DB: inserta movimientos nuevos (ignora duplicados)
    BE->>BE: TransferDetector.detect_internal_transfers()
    BE->>BE: Categorizer.categorize_transaction() por movimiento
    BE-->>FE: resumen de la importación
```

## 3. Interfaces extensibles

El núcleo de la aplicación nunca depende de un banco concreto: todo pasa
por interfaces (`app/parsers/base.py`, `app/services/*.py`).

```mermaid
classDiagram
    class BankParser {
        <<abstract>>
        +detect(filename, header_row, sample_text) float
        +parse(file_bytes, filename) ParseResult
    }
    class ImaginParser
    class MyInvestorParser
    class TradeRepublicParser
    BankParser <|-- ImaginParser
    BankParser <|-- MyInvestorParser
    BankParser <|-- TradeRepublicParser

    class TransactionProvider {
        <<abstract>>
        +fetch(**kwargs) ParseResult
    }
    class FileImportProvider
    class PSD2Provider {
        <<no implementado>>
    }
    TransactionProvider <|-- FileImportProvider
    TransactionProvider <|-- PSD2Provider
```

Añadir un nuevo banco = crear una clase que implemente `BankParser` y
registrarla en `app/parsers/registry.py`. Nada más del sistema cambia.

Añadir Open Banking/PSD2 en el futuro = implementar `PSD2Provider.fetch()`
usando un agregador licenciado; el resto del pipeline (normalización,
deduplicación, categorización, analítica) es idéntico porque todos
consumen `NormalizedTransaction`, no el formato original del banco.

## 4. Modelo de datos (resumen)

```mermaid
erDiagram
    User ||--o{ Account : tiene
    User ||--o{ CategoryRule : define
    User ||--o{ BizumContact : guarda
    Account ||--o{ Transaction : contiene
    Account ||--o{ ImportBatch : recibe
    Category ||--o{ Subcategory : agrupa
    Category ||--o{ Transaction : clasifica
    Transaction }o--|| Transaction : "transfer_pair_id (autoreferencia)"
```

Ver `backend/app/models.py` para el detalle completo de columnas.

## 5. Reglas de cálculo financiero (sección 47 del spec original)

Implementadas en `backend/app/services/analytics_engine.py`:

- **Ingresos** = suma de `amount > 0`, excluyendo transferencias internas.
- **Gastos** = suma de `amount < 0`, excluyendo transferencias internas
  y excluyendo compras de inversión (`INVESTMENT_BUY`).
- **Ahorro** = Ingresos − Gastos.
- **Inversión** = suma de movimientos `INVESTMENT_BUY` (valor absoluto).

Todos los importes se almacenan como `NUMERIC(14,2)` en PostgreSQL y se
manipulan como `Decimal` en Python — nunca `float` — para evitar errores
de redondeo en cifras financieras.

## 6. Deduplicación

`backend/app/services/dedup.py`: huella SHA-256 de
`cuenta + fecha + importe + descripción normalizada + moneda`, o del
`external_id` cuando el archivo lo proporciona. Restricción `UNIQUE` en
base de datos (`uq_transaction_fingerprint`) como segunda barrera además
de la comprobación explícita antes de insertar.
