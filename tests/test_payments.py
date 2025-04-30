# tests/test_payments.py

import os
import sys
import types
import pytest
import mysql.connector

# Ensure project root on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Stub out config before importing
sys.modules['config'] = types.SimpleNamespace(DB_CONFIG={})

from app import app
import blueprints.paymentHistory.payments as payments_mod

# --- Helper classes to mock DB connections and cursors ---
class DummyCursor:
    def __init__(self, rows=None):
        self._rows = rows or []
    def execute(self, query, params=None):
        pass
    def fetchall(self):
        return self._rows
    def fetchone(self):
        # for _get_pharmacy_id_for_user
        return None
    def close(self):
        pass

class DummyConn:
    def __init__(self, rows=None):
        self._rows = rows or []
    def cursor(self, dictionary=True):
        return DummyCursor(self._rows)
    def close(self):
        pass

@pytest.fixture
def client():
    return app.test_client()

# --- Tests for GET /api/pharmacy/payments ---

def test_get_payments_missing_user(client):
    resp = client.get('/api/pharmacy/payments')
    assert resp.status_code == 400
    assert resp.get_json().get('error') == 'user_id is required'

def test_get_payments_no_pharmacy(monkeypatch, client):
    # stub out connect so cursor exists
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn())
    # force no active pharmacy
    monkeypatch.setattr(payments_mod, '_get_pharmacy_id_for_user', lambda u, c: None)
    resp = client.get('/api/pharmacy/payments?user_id=1')
    assert resp.status_code == 404
    assert resp.get_json().get('error') == 'No active pharmacy found for that user'

def test_get_payments_success(monkeypatch, client):
    # prepare mixed payments
    rows = [
        {'payment_id': 1, 'patient_name': 'A', 'amount': 10.0, 'is_fulfilled': True, 'payment_date': '2025-04-28'},
        {'payment_id': 2, 'patient_name': 'B', 'amount': 20.0, 'is_fulfilled': False, 'payment_date': '2025-04-27'},
        {'payment_id': 3, 'patient_name': 'C', 'amount': 30.0, 'is_fulfilled': True, 'payment_date': '2025-04-26'}
    ]
    # stub pharmacy_id resolution and DB connection
    monkeypatch.setattr(payments_mod, '_get_pharmacy_id_for_user', lambda u, c: 1)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn(rows=rows))

    resp = client.get('/api/pharmacy/payments?user_id=1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'fulfilled' in data and 'unfulfilled' in data
    assert data['fulfilled'] == [rows[0], rows[2]]
    assert data['unfulfilled'] == [rows[1]]