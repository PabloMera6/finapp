# Finanzas Personales

Aplicación web privada de análisis financiero personal a partir de exportaciones
de movimientos de **imagin**, **MyInvestor** y **Trade Republic**.

No solicita ni almacena credenciales bancarias. Funciona exclusivamente con
archivos (CSV/XLSX) que tú mismo exportas desde cada entidad.

---

## 1. Qué incluye esta versión

- Importación de CSV/XLSX de imagin y MyInvestor y PDF de Trade Republic, con
  detección automática de entidad.
- Normalización a un modelo común (`NormalizedTransaction`).
- Deduplicación por huella (reimportar un archivo no duplica movimientos).
- Detección automática de transferencias entre cuentas propias.
- Motor de categorización por reglas (deterministas + aprendidas del usuario).
- Detección de Bizums, con sección específica para los que no tienen
  destinatario identificable (nunca se inventa el destinatario).
- Dashboard con ingresos/gastos/ahorro/inversión, comparación con el mes
  anterior, gráficos (evolución, categorías, tasa de ahorro).
- Resolución del signo de Trade Republic usando la columna BALANCE cuando
  ENTRADA/SALIDA aparecen como importes siempre positivos.
- Alta y eliminación manual de movimientos desde la pantalla de movimientos.
- Análisis de periodos de hasta 10 años con totales, evolución mensual,
  tasa de ahorro y categorías de gasto.
- Comparador de meses por categoría.
- Detección de gastos recurrentes.
- Insights automáticos basados únicamente en datos reales.
- Exportación de movimientos a CSV.
- Autenticación con usuario único (configurable por variables de entorno),
  cookies HTTPOnly, rate limiting en login.
- Tests automatizados (parsers, deduplicación, transferencias,
  categorización, flujo de importación end-to-end): **19/19 pasan**.

### Limitaciones conocidas

- **Importación PDF**: Trade Republic se procesa desde PDF y se limita a la
  sección `TRANSACCIONES DE CUENTA`; otros bancos siguen usando CSV/XLSX.
- **PSD2/Open Banking**: no implementado; existe `PSD2Provider` como
  placeholder documentado en `app/parsers/base.py`.
- **Caché de previsualización de importación**: vive en memoria del proceso
  backend (TTL de 15 min). Para desplegar con varias réplicas del backend
  habría que moverla a Redis; en un único contenedor (como en este
  `docker-compose.yml`) funciona correctamente.
- **Detección de anomalías (sección 26)**: implementada de forma parcial a
  través de insights de variación mes a mes; no incluye un motor estadístico
  separado.
- **Categorización con LLM opcional (sección 15)**: la arquitectura lo
  permite (interfaz de categorización desacoplada), pero no se ha
  implementado ningún proveedor de IA en esta versión — todo es
  determinista y local.
- Los tests cubren los flujos críticos, pero no son exhaustivos al 100% de
  los 63 apartados del documento de requisitos original.

---

## 2. Arquitectura

```
Internet
   │ HTTPS (reverse proxy externo, no incluido)
   ▼
┌─────────────┐      ┌─────────────┐
│  Frontend   │──────▶   Backend   │
│  Next.js    │ REST │  FastAPI    │
│  :3000      │      │  :8000      │
└─────────────┘      └──────┬──────┘
                             │ red interna Docker
                             ▼
                      ┌─────────────┐
                      │ PostgreSQL  │
                      │ (sin puerto │
                      │  publicado) │
                      └─────────────┘
```

Ver `ARCHITECTURE.md` para diagramas detallados (flujo de importación,
esquema de datos, interfaces extensibles).

**Stack:**

- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind CSS + Recharts.
- Backend: FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2.
- Base de datos: PostgreSQL 16.
- Autenticación: JWT en cookie HTTPOnly, hash Argon2.

---

## 3. Arranque rápido (Docker)

Requisitos: Docker y Docker Compose instalados.

```bash
git clone <este-repositorio>
cd finapp
cp .env.example .env
# Edita .env y rellena POSTGRES_PASSWORD, SECRET_KEY y ADMIN_PASSWORD
# (genera SECRET_KEY con: openssl rand -hex 32)

docker compose up -d --build
```

La aplicación queda disponible en:

- Frontend: http://localhost:3000
- Backend (API): http://localhost:8000

Al arrancar, el backend ejecuta automáticamente las migraciones y crea el
usuario administrador definido en `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`).

Para cargar datos de demostración **completamente ficticios**:

```bash
docker compose exec backend python seed.py --demo
```

---

## 4. Desarrollo local (sin Docker)

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Necesitas un PostgreSQL local. Ejemplo rápido con Docker solo para la DB:
docker run -d --name finapp-db -e POSTGRES_USER=finapp -e POSTGRES_PASSWORD=finapp \
  -e POSTGRES_DB=finapp -p 5432:5432 postgres:16-alpine

export DATABASE_URL="postgresql://finapp:finapp@localhost:5432/finapp"
export SECRET_KEY="dev-secret-key"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="admin1234"

alembic upgrade head
python seed.py --demo   # opcional, datos ficticios de ejemplo

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_URL="http://localhost:8000"
npm run dev
```

Abre http://localhost:3000.

---

## 5. Variables de entorno

Ver `.env.example` para la lista completa. Las más importantes:

| Variable | Descripción |
|---|---|
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL. Obligatoria. |
| `SECRET_KEY` | Clave para firmar los JWT de sesión. Obligatoria, aleatoria. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Credenciales del usuario único inicial. |
| `COOKIE_SECURE` | Pon `true` en producción (requiere HTTPS). |
| `NEXT_PUBLIC_API_URL` | URL pública por la que el navegador llega al backend. |
| `FRONTEND_ORIGIN` | Origen permitido por CORS en el backend. |

**Nunca subas tu `.env` real a git.** Solo `.env.example` debe estar versionado.

---

## 6. Migraciones

```bash
cd backend
# Crear una nueva migración tras modificar app/models.py
alembic revision --autogenerate -m "descripcion del cambio"

# Aplicar migraciones pendientes
alembic upgrade head
```

---

## 7. Tests

```bash
cd backend
export DATABASE_URL="postgresql://finapp:finapp@localhost:5432/finapp_test"
export SECRET_KEY="test-secret"
python -m pytest tests/ -v
```

Cobertura actual: parsers de los 3 bancos, deduplicación, detección de
transferencias internas, motor de categorización (reglas por defecto y
aprendizaje de reglas de usuario), y un flujo de integración completo
(login → importar → deduplicar → listar movimientos).

---

## 8. Despliegue en un VPS

1. Instala Docker y Docker Compose en el VPS.
2. Copia el proyecto (`git clone` o `scp`).
3. Configura `.env` con secretos reales y `COOKIE_SECURE=true`.
4. Levanta la aplicación: `docker compose up -d --build`.
5. Pon un reverse proxy delante (Caddy, Nginx o Traefik) que:
   - Termine HTTPS (por ejemplo con Let's Encrypt).
   - Redirija `/` al frontend (puerto 3000) y `/api` al backend (puerto 8000),
     o publica ambos como subdominios distintos.
6. **No publiques el puerto de PostgreSQL** en el VPS; en `docker-compose.yml`
   la base de datos ya está en una red `internal: true` sin mapeo de puertos.

Ejemplo mínimo de bloque Nginx (ajusta a tu dominio):

```nginx
server {
    listen 443 ssl;
    server_name finanzas.tudominio.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 9. Backup y restauración

```bash
./scripts/backup.sh                              # crea backups/finapp_backup_<fecha>.sql.gz
./scripts/restore.sh backups/finapp_backup_XXXX.sql.gz
```

Ambos scripts operan a través de `docker compose exec`, por lo que
PostgreSQL nunca necesita exponer su puerto a Internet para hacer backup.

---

## 10. Seguridad

- Contraseñas hasheadas con Argon2.
- Sesión mediante JWT en cookie `HTTPOnly`, `SameSite=Lax`, `Secure` en
  producción.
- Rate limiting en el endpoint de login (5 intentos/minuto).
- Todos los endpoints de datos financieros requieren autenticación.
- Validación de tipo y tamaño máximo de archivo en la importación.
- Cálculos monetarios con `Decimal`/`NUMERIC`, nunca `float`.
- Sin registro en logs de importes, descripciones completas, números de
  cuenta o destinatarios (ver `app/main.py`, sección de logging).
- Sin llamadas a servicios de IA externos: la categorización es 100% local
  y determinista en esta versión.

---

## 11. Formatos de archivo esperados por parser

Ejemplos ficticios en `fixtures/`. Los parsers soportan variaciones
razonables de nombres de columna (ver `COLUMN_ALIASES` en cada parser) y
tanto coma como punto como separador decimal.

- `fixtures/imagin_sample.csv`
- `fixtures/myinvestor_sample.csv`
- `fixtures/trade_republic_sample.pdf`

Si tu exportación real usa nombres de columna distintos y no se detecta
correctamente, revisa `app/parsers/<entidad>.py` y añade el alias
correspondiente a `COLUMN_ALIASES` — es el único cambio necesario.

---

## 12. Troubleshooting

- **"No se pudo detectar la entidad automáticamente"**: selecciona la
  entidad manualmente en la pantalla de importación, o añade un alias de
  columna nuevo en el parser correspondiente.
- **El contenedor `backend` no arranca**: comprueba que `db` esté
  `healthy` (`docker compose ps`) y que `SECRET_KEY`/`POSTGRES_PASSWORD`
  estén definidos en `.env`.
- **Login funciona pero las páginas redirigen siempre a `/login`**: revisa
  que `NEXT_PUBLIC_API_URL` (frontend) y `FRONTEND_ORIGIN` (backend)
  coincidan con los orígenes reales, y que las cookies no estén siendo
  bloqueadas por `COOKIE_SECURE=true` en un entorno sin HTTPS.
