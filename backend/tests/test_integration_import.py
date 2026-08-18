import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

IMAGIN_CSV = b"""Fecha,Concepto,Importe,Saldo
01/07/2026,NOMINA,2000.00,2000.00
02/07/2026,MERCADONA,-40.00,1960.00
"""


def test_protected_endpoint_requires_auth():
    resp = client.get("/api/dashboard")
    assert resp.status_code == 401


def test_login_wrong_password_returns_401(test_user):
    resp = client.post("/api/auth/login", json={"email": "test@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_full_import_flow(test_user):
    login = client.post("/api/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    assert login.status_code == 200

    files = {"file": ("imagin_test.csv", io.BytesIO(IMAGIN_CSV), "text/csv")}
    preview = client.post("/api/imports/preview", files=files)
    assert preview.status_code == 200
    data = preview.json()
    assert data["chosen_institution"] == "imagin"
    assert data["new_rows"] == 2

    confirm = client.post("/api/imports/confirm", json={
        "import_token": data["import_token"],
        "institution": "imagin",
        "new_account_name": "imagin integration test",
    })
    assert confirm.status_code == 200
    assert confirm.json()["imported"] == 2

    # Reimportar el mismo archivo no debe crear duplicados
    files2 = {"file": ("imagin_test.csv", io.BytesIO(IMAGIN_CSV), "text/csv")}
    preview2 = client.post("/api/imports/preview", files=files2)
    assert preview2.json()["new_rows"] == 0
    assert preview2.json()["duplicate_rows"] == 2

    transactions = client.get("/api/transactions")
    assert transactions.status_code == 200
    assert transactions.json()["total"] >= 2
