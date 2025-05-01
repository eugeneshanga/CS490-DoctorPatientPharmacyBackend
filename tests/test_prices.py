# tests/test_prices.py

import blueprints.drugPrices.prices as prices_mod
from app import app
import os
import sys
import types
import pytest
import mysql.connector

# Ensure project root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Stub out config before importing
sys.modules['config'] = types.SimpleNamespace(DB_CONFIG={})


# --- Helper classes to mock DB connections and cursors ---

class DummyCursor:
    def __init__(self, rows=None, rowcount=1):
        self._rows = rows or []
        self.rowcount = rowcount

    def execute(self, query, params=None):
        pass

    def fetchall(self):
        return self._rows

    def fetchone(self):
        # not used here
        return None

    def close(self):
        pass


class DummyConn:
    def __init__(self, rows=None, rowcount=1):
        self._rows = rows or []
        self._rowcount = rowcount

    def cursor(self, dictionary=False):
        # dictionary=True for get_prices, False for update_price
        if dictionary:
            return DummyCursor(rows=self._rows)
        return DummyCursor(rowcount=self._rowcount)

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def client():
    return app.test_client()

# --- Tests for GET /api/prices/current-prices ---


def test_get_prices_missing_user(client):
    resp = client.get('/api/prices/current-prices')
    assert resp.status_code == 400
    assert resp.get_json().get('error') == 'user_id is required'


def test_get_prices_no_pharmacy(monkeypatch, client):
    # stub out connect so cursor() works
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn())
    # force no active pharmacy
    monkeypatch.setattr(prices_mod, '_get_pharmacy_id_for_user', lambda user_id, cursor: None)
    resp = client.get('/api/prices/current-prices?user_id=5')
    assert resp.status_code == 404
    assert resp.get_json().get('error') == 'No active pharmacy'


def test_get_prices_success(monkeypatch, client):
    sample = [
        {'drug_id': 1, 'name': 'Metformin', 'description': 'Desc', 'price': 10.5},
        {'drug_id': 2, 'name': 'Orlistat', 'description': 'Desc2', 'price': 20.0}
    ]
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn(rows=sample))
    monkeypatch.setattr(prices_mod, '_get_pharmacy_id_for_user', lambda user_id, cursor: 1)
    resp = client.get('/api/prices/current-prices?user_id=5')
    assert resp.status_code == 200
    assert resp.get_json() == sample

# --- Tests for PATCH /api/prices/update ---


UPDATE_URL = '/api/prices/update'


@pytest.mark.parametrize('payload', [
    {},
    {'user_id': 1},
    {'user_id': 1, 'drug_id': 2},
    {'user_id': 1, 'price': 5.0},
    {'drug_id': 2, 'price': 5.0}
])
def test_update_price_missing_fields(client, payload):
    resp = client.patch(UPDATE_URL, json=payload)
    assert resp.status_code == 400
    assert 'required' in resp.get_json().get('error')


def test_update_price_no_pharmacy(monkeypatch, client):
    # stub out connect so cursor() works
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn())
    # missing active pharmacy
    monkeypatch.setattr(prices_mod, '_get_pharmacy_id_for_user', lambda u, c: None)
    payload = {'user_id': 1, 'drug_id': 2, 'price': 5.0}
    resp = client.patch(UPDATE_URL, json=payload)
    assert resp.status_code == 404
    assert resp.get_json().get('error') == 'No active pharmacy'


def test_update_price_existing(monkeypatch, client):
    # simulate update affecting existing row
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn(rowcount=2))
    monkeypatch.setattr(prices_mod, '_get_pharmacy_id_for_user', lambda u, c: 1)
    payload = {'user_id': 1, 'drug_id': 2, 'price': 15.0}
    resp = client.patch(UPDATE_URL, json=payload)
    assert resp.status_code == 200
    assert resp.get_json().get('message') == 'Price updated'


def test_update_price_insert(monkeypatch, client):
    # simulate update affecting 0 rows triggers insert
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn(rowcount=0))
    monkeypatch.setattr(prices_mod, '_get_pharmacy_id_for_user', lambda u, c: 1)
    payload = {'user_id': 1, 'drug_id': 3, 'price': 25.0}
    resp = client.patch(UPDATE_URL, json=payload)
    assert resp.status_code == 200
    assert resp.get_json().get('message') == 'Price updated'
