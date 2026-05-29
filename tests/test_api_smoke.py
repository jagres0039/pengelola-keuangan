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


def test_profile_mode_default_and_toggle(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}

    # default: standar
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 200
    assert r.json()["profile_mode"] == "standar"

    # switch to pengusaha
    r = client.patch("/api/auth/me", json={"profile_mode": "pengusaha"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["profile_mode"] == "pengusaha"

    # persisted on next /me
    r = client.get("/api/auth/me", headers=h)
    assert r.json()["profile_mode"] == "pengusaha"

    # invalid value rejected
    r = client.patch("/api/auth/me", json={"profile_mode": "bukan-mode"}, headers=h)
    assert r.status_code == 422

    # switch back to standar
    r = client.patch("/api/auth/me", json={"profile_mode": "standar"}, headers=h)
    assert r.status_code == 200
    assert r.json()["profile_mode"] == "standar"


def test_contacts_crud(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}

    # empty list
    r = client.get("/api/contacts", headers=h)
    assert r.status_code == 200
    assert r.json() == []

    # create customer
    r = client.post(
        "/api/contacts",
        json={
            "name": "Toko Maju Jaya",
            "kind": "customer",
            "phone": "081234567890",
            "address": "Jl. Mawar 1",
            "notes": "langganan setia",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    customer = r.json()
    assert customer["kind"] == "customer"
    assert customer["archived"] is False

    # create supplier
    r = client.post(
        "/api/contacts",
        json={"name": "PT Pemasok Bahan", "kind": "supplier"},
        headers=h,
    )
    assert r.status_code == 201
    supplier = r.json()

    # list returns both (sorted by name)
    r = client.get("/api/contacts", headers=h)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert rows[0]["name"] == "PT Pemasok Bahan"
    assert rows[1]["name"] == "Toko Maju Jaya"

    # filter by kind=customer
    r = client.get("/api/contacts?kind=customer", headers=h)
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == customer["id"]

    # search
    r = client.get("/api/contacts?q=maju", headers=h)
    assert len(r.json()) == 1

    # patch
    r = client.patch(
        f"/api/contacts/{customer['id']}",
        json={"phone": "0811-9999"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["phone"] == "0811-9999"

    # archive (soft-delete)
    r = client.post(f"/api/contacts/{customer['id']}/archive", headers=h)
    assert r.status_code == 200
    assert r.json()["archived"] is True

    # default list excludes archived
    r = client.get("/api/contacts", headers=h)
    assert len(r.json()) == 1

    # include_archived=true brings it back
    r = client.get("/api/contacts?include_archived=true", headers=h)
    assert len(r.json()) == 2

    # unarchive
    r = client.post(f"/api/contacts/{customer['id']}/unarchive", headers=h)
    assert r.status_code == 200
    assert r.json()["archived"] is False

    # invalid kind on create -> 422
    r = client.post("/api/contacts", json={"name": "X", "kind": "stranger"}, headers=h)
    assert r.status_code == 422

    # hard delete supplier
    r = client.delete(f"/api/contacts/{supplier['id']}", headers=h)
    assert r.status_code == 204
    r = client.get("/api/contacts", headers=h)
    assert len(r.json()) == 1


def test_contacts_data_isolation(client: TestClient) -> None:
    a_token = _register(client, "a@example.com")
    b_token = _register(client, "b@example.com")
    a_h = {"Authorization": f"Bearer {a_token}"}
    b_h = {"Authorization": f"Bearer {b_token}"}

    r = client.post("/api/contacts", json={"name": "Customer A"}, headers=a_h)
    contact_id = r.json()["id"]

    # B can't see A's contact
    assert client.get("/api/contacts", headers=b_h).json() == []
    # B can't fetch A's contact directly
    assert client.get(f"/api/contacts/{contact_id}", headers=b_h).status_code == 404
    # B can't patch
    assert (
        client.patch(f"/api/contacts/{contact_id}", json={"name": "h4x"}, headers=b_h).status_code
        == 404
    )
    # B can't delete
    assert client.delete(f"/api/contacts/{contact_id}", headers=b_h).status_code == 404


def test_accounts_and_transfers(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}

    # empty list
    r = client.get("/api/accounts", headers=h)
    assert r.status_code == 200
    assert r.json() == []

    # create cash account with opening_balance=100000
    r = client.post(
        "/api/accounts",
        json={"name": "Kas Tunai", "kind": "cash", "opening_balance": "100000"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    cash = r.json()
    assert Decimal(cash["balance"]) == Decimal("100000")
    assert cash["kind"] == "cash"
    assert cash["archived"] is False

    # create bank account with 0 opening
    r = client.post(
        "/api/accounts",
        json={"name": "BCA", "kind": "bank"},
        headers=h,
    )
    bca = r.json()

    # post income to cash
    r = client.post(
        "/api/transactions",
        json={
            "type": "in",
            "amount": "50000",
            "account_id": cash["id"],
            "note": "jualan",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    tx_in = r.json()
    assert tx_in["account_id"] == cash["id"]
    assert tx_in["account_name"] == "Kas Tunai"

    # post expense from cash
    r = client.post(
        "/api/transactions",
        json={
            "type": "out",
            "amount": "20000",
            "account_id": cash["id"],
        },
        headers=h,
    )
    assert r.status_code == 201

    # cash balance = 100000 + 50000 - 20000 = 130000
    r = client.get(f"/api/accounts/{cash['id']}", headers=h)
    assert Decimal(r.json()["balance"]) == Decimal("130000")

    # transfer 30000 cash -> bca
    r = client.post(
        "/api/transfers",
        json={
            "from_account_id": cash["id"],
            "to_account_id": bca["id"],
            "amount": "30000",
            "note": "setor BCA",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    tr = r.json()
    assert Decimal(tr["amount"]) == Decimal("30000")
    assert tr["from_account_name"] == "Kas Tunai"
    assert tr["to_account_name"] == "BCA"

    # cash balance = 130000 - 30000 = 100000; bca = 0 + 30000 = 30000
    r = client.get("/api/accounts", headers=h)
    balances = {a["name"]: Decimal(a["balance"]) for a in r.json()}
    assert balances["Kas Tunai"] == Decimal("100000")
    assert balances["BCA"] == Decimal("30000")

    # self-transfer rejected
    r = client.post(
        "/api/transfers",
        json={
            "from_account_id": cash["id"],
            "to_account_id": cash["id"],
            "amount": "1000",
        },
        headers=h,
    )
    assert r.status_code == 400

    # negative amount rejected (validated by schema gt=0)
    r = client.post(
        "/api/transfers",
        json={
            "from_account_id": cash["id"],
            "to_account_id": bca["id"],
            "amount": "-5",
        },
        headers=h,
    )
    assert r.status_code == 422

    # delete with refs returns 409
    r = client.delete(f"/api/accounts/{cash['id']}", headers=h)
    assert r.status_code == 409

    # archive cash
    r = client.post(f"/api/accounts/{cash['id']}/archive", headers=h)
    assert r.status_code == 200
    assert r.json()["archived"] is True

    # list excludes archived by default
    r = client.get("/api/accounts", headers=h)
    names = [a["name"] for a in r.json()]
    assert "Kas Tunai" not in names
    assert "BCA" in names

    # invalid account_id on transaction
    r = client.post(
        "/api/transactions",
        json={"type": "in", "amount": "1000", "account_id": 999999},
        headers=h,
    )
    assert r.status_code == 400


def test_accounts_data_isolation(client: TestClient) -> None:
    a_token = _register(client, "a-acc@example.com")
    b_token = _register(client, "b-acc@example.com")
    a_h = {"Authorization": f"Bearer {a_token}"}
    b_h = {"Authorization": f"Bearer {b_token}"}

    r = client.post(
        "/api/accounts",
        json={"name": "A's wallet", "opening_balance": "1000"},
        headers=a_h,
    )
    acc_id = r.json()["id"]

    # B can't see A's account
    assert client.get("/api/accounts", headers=b_h).json() == []
    assert client.get(f"/api/accounts/{acc_id}", headers=b_h).status_code == 404
    assert (
        client.patch(f"/api/accounts/{acc_id}", json={"name": "h4x"}, headers=b_h).status_code
        == 404
    )

    # B can't reference A's account in a transfer
    r = client.post("/api/accounts", json={"name": "B's wallet"}, headers=b_h)
    b_acc = r.json()["id"]
    r = client.post(
        "/api/transfers",
        json={
            "from_account_id": acc_id,
            "to_account_id": b_acc,
            "amount": "100",
        },
        headers=b_h,
    )
    assert r.status_code == 404

    # B can't reference A's account on a transaction
    r = client.post(
        "/api/transactions",
        json={"type": "in", "amount": "100", "account_id": acc_id},
        headers=b_h,
    )
    assert r.status_code == 400


def test_inventory_crud_and_movements(client: TestClient) -> None:
    token = _register(client)
    h = {"Authorization": f"Bearer {token}"}

    # empty
    assert client.get("/api/inventory", headers=h).json() == []

    # create with initial stock
    r = client.post(
        "/api/inventory",
        json={
            "name": "Sabun Cuci",
            "sku": "SC-001",
            "unit": "pcs",
            "initial_stock": "10",
            "initial_cost": "5000",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert Decimal(item["stock"]) == Decimal("10")
    assert Decimal(item["last_cost"]) == Decimal("5000")
    item_id = item["id"]

    # purchase 5 more at higher cost
    r = client.post(
        f"/api/inventory/{item_id}/movements",
        json={"qty_delta": "5", "unit_cost": "5500", "reason": "purchase"},
        headers=h,
    )
    assert r.status_code == 201

    # sale 3 (negative qty_delta)
    r = client.post(
        f"/api/inventory/{item_id}/movements",
        json={"qty_delta": "-3", "reason": "sale"},
        headers=h,
    )
    assert r.status_code == 201

    # stock = 10 + 5 - 3 = 12; last_cost = 5500 (from latest purchase)
    r = client.get(f"/api/inventory/{item_id}", headers=h)
    assert Decimal(r.json()["stock"]) == Decimal("12")
    assert Decimal(r.json()["last_cost"]) == Decimal("5500")

    # zero qty_delta rejected
    r = client.post(
        f"/api/inventory/{item_id}/movements",
        json={"qty_delta": "0", "reason": "adjustment"},
        headers=h,
    )
    assert r.status_code == 400

    # over-sell rejected (current stock 12, trying to take 100)
    r = client.post(
        f"/api/inventory/{item_id}/movements",
        json={"qty_delta": "-100", "reason": "sale"},
        headers=h,
    )
    assert r.status_code == 400

    # movement history
    r = client.get(f"/api/inventory/{item_id}/movements", headers=h)
    assert len(r.json()) == 3

    # search by name
    r = client.get("/api/inventory?q=sabun", headers=h)
    assert len(r.json()) == 1

    # patch metadata
    r = client.patch(
        f"/api/inventory/{item_id}",
        json={"name": "Sabun Cuci Sereh", "unit": "btl"},
        headers=h,
    )
    assert r.json()["name"] == "Sabun Cuci Sereh"
    assert r.json()["unit"] == "btl"

    # archive
    r = client.post(f"/api/inventory/{item_id}/archive", headers=h)
    assert r.json()["archived"] is True
    assert client.get("/api/inventory", headers=h).json() == []
    assert (
        len(client.get("/api/inventory?include_archived=true", headers=h).json())
        == 1
    )

    # invalid reason rejected by schema
    r = client.post(
        f"/api/inventory/{item_id}/movements",
        json={"qty_delta": "1", "reason": "stolen"},
        headers=h,
    )
    assert r.status_code == 422


def test_inventory_data_isolation(client: TestClient) -> None:
    a_token = _register(client, "a-inv@example.com")
    b_token = _register(client, "b-inv@example.com")
    a_h = {"Authorization": f"Bearer {a_token}"}
    b_h = {"Authorization": f"Bearer {b_token}"}

    r = client.post(
        "/api/inventory",
        json={"name": "Item A", "initial_stock": "5", "initial_cost": "1000"},
        headers=a_h,
    )
    item_id = r.json()["id"]

    # B can't see / patch / delete A's item
    assert client.get("/api/inventory", headers=b_h).json() == []
    assert client.get(f"/api/inventory/{item_id}", headers=b_h).status_code == 404
    assert (
        client.patch(
            f"/api/inventory/{item_id}", json={"name": "h4x"}, headers=b_h
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/inventory/{item_id}/movements",
            json={"qty_delta": "1", "reason": "purchase"},
            headers=b_h,
        ).status_code
        == 404
    )
    assert client.delete(f"/api/inventory/{item_id}", headers=b_h).status_code == 404
