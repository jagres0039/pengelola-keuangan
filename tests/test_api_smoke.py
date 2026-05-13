"""End-to-end API smoke tests using an in-memory SQLite DB."""

from __future__ import annotations

import os
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pengelola_keuangan.db.models import Base


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Any) -> Iterator[None]:
    """Reset the DB engine + cached settings for each test."""
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-production-pls-32+chars"
    os.environ["GEMINI_API_KEY"] = ""  # OCR disabled in smoke tests

    # Reset singletons that read settings at import-time
    import pengelola_keuangan.config as config_mod
    import pengelola_keuangan.db.session as session_mod

    config_mod._settings = None
    session_mod._engine = None
    session_mod._SessionLocal = None

    from pengelola_keuangan.db.session import get_engine

    engine = get_engine()
    Base.metadata.create_all(engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(engine)
        config_mod._settings = None
        session_mod.reset_engine_for_tests()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Build a fresh FastAPI test client."""
    from pengelola_keuangan.api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


def _register(client: TestClient, email: str = "alice@example.com") -> str:
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "passw0rd!", "first_name": "Alice"},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["access_token"])


def test_health(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_login_me_flow(client: TestClient) -> None:
    # register
    r = client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "secret123", "first_name": "Bob"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]

    # /me
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "bob@example.com"
    assert body["first_name"] == "Bob"
    assert body["telegram_linked"] is False

    # duplicate registration is rejected
    r = client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "secret123"},
    )
    assert r.status_code == 409

    # login with wrong password fails
    r = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrong"})
    assert r.status_code == 401

    # login with right password works
    r = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "secret123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_me_requires_auth(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_categories_seeded_after_register(client: TestClient) -> None:
    token = _register(client)
    r = client.get("/api/categories", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    cats = r.json()
    names_in = {c["name"] for c in cats if c["type"] == "in"}
    names_out = {c["name"] for c in cats if c["type"] == "out"}
    assert "Gaji" in names_in
    assert "Makanan" in names_out


def test_transaction_crud(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}

    # find Makanan category
    cats = client.get("/api/categories", headers=h).json()
    makanan = next(c for c in cats if c["name"] == "Makanan" and c["type"] == "out")

    # create transaction
    r = client.post(
        "/api/transactions",
        json={"type": "out", "amount": "35000", "category_id": makanan["id"], "note": "siang"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    tx = r.json()
    assert Decimal(tx["amount"]) == Decimal("35000")
    assert tx["category_name"] == "Makanan"

    # list returns it
    r = client.get("/api/transactions", headers=h)
    assert r.status_code == 200
    assert any(t["id"] == tx["id"] for t in r.json())

    # update note
    r = client.patch(f"/api/transactions/{tx['id']}", json={"note": "sarapan"}, headers=h)
    assert r.status_code == 200
    assert r.json()["note"] == "sarapan"

    # delete
    r = client.delete(f"/api/transactions/{tx['id']}", headers=h)
    assert r.status_code == 204


def test_summary_endpoint(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}
    cats = client.get("/api/categories", headers=h).json()
    gaji = next(c for c in cats if c["name"] == "Gaji")
    makanan = next(c for c in cats if c["name"] == "Makanan" and c["type"] == "out")

    client.post(
        "/api/transactions",
        json={"type": "in", "amount": "5000000", "category_id": gaji["id"]},
        headers=h,
    )
    client.post(
        "/api/transactions",
        json={"type": "out", "amount": "35000", "category_id": makanan["id"]},
        headers=h,
    )

    r = client.get("/api/summary", headers=h)
    assert r.status_code == 200
    s = r.json()
    assert Decimal(s["total_income"]) == Decimal("5000000")
    assert Decimal(s["total_expense"]) == Decimal("35000")
    assert Decimal(s["balance"]) == Decimal("4965000")


def test_data_isolation_between_users(client: TestClient) -> None:
    a_token = _register(client, "a@example.com")
    b_token = _register(client, "b@example.com")
    a_h = {"Authorization": f"Bearer {a_token}"}
    b_h = {"Authorization": f"Bearer {b_token}"}

    cats_a = client.get("/api/categories", headers=a_h).json()
    makanan_a = next(c for c in cats_a if c["name"] == "Makanan" and c["type"] == "out")

    r = client.post(
        "/api/transactions",
        json={"type": "out", "amount": "12345", "category_id": makanan_a["id"]},
        headers=a_h,
    )
    assert r.status_code == 201
    tx_a_id = r.json()["id"]

    # B sees zero transactions
    assert client.get("/api/transactions", headers=b_h).json() == []

    # B cannot read or delete A's transaction
    assert client.delete(f"/api/transactions/{tx_a_id}", headers=b_h).status_code == 404


def test_budget_endpoints(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}
    cats = client.get("/api/categories", headers=h).json()
    makanan = next(c for c in cats if c["name"] == "Makanan" and c["type"] == "out")

    r = client.put(
        "/api/budgets",
        json={"category_id": makanan["id"], "monthly_limit": "1500000"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert Decimal(body["monthly_limit"]) == Decimal("1500000")

    r = client.get("/api/budgets", headers=h)
    assert r.status_code == 200
    assert any(b["category_id"] == makanan["id"] for b in r.json())


def test_receipt_ocr_disabled_returns_503(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}
    files = {"image": ("test.jpg", b"fake-bytes", "image/jpeg")}
    r = client.post("/api/receipt/ocr", headers=h, files=files)
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.text


def test_link_code_issued(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/auth/link-code", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert len(data["code"]) == 6
    assert data["code"].isalnum()
