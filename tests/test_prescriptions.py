# tests/test_prescriptions.py

import os
import sys
# ensure the project root (where app.py lives) is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import types
import pytest
import mysql.connector

# stub out config before importing app
sys.modules['config'] = types.SimpleNamespace(DB_CONFIG={})

from app import app

# Helper classes to mock MySQL connection and cursor
class DummyCursor:
    def __init__(self, rows):
        self._rows = rows
    def execute(self, query, params=None):
        pass
    def fetchall(self):
        return self._rows
    def fetchone(self):
        return self._rows[0] if self._rows else None
    def close(self):
        pass

class DummyConn:
    def __init__(self, rows):
        self._rows = rows
    def cursor(self, dictionary=True):
        return DummyCursor(self._rows)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass

@pytest.fixture
def client():
    return app.test_client()

@pytest.fixture(autouse=True)
def force_pharmacy_id(monkeypatch):
    """
    Force _get_pharmacy_id_for_user to always return 1,
    so that inventory routes never 404.
    """
    import blueprints.pharmacyDashboard.prescriptions as pres_mod
    monkeypatch.setattr(pres_mod, '_get_pharmacy_id_for_user', lambda user_id, cursor: 1)

def test_get_prescriptions(monkeypatch, client):
    rows = [{
        'prescription_id': 1,
        'patient_name': 'John Doe',
        'medication_name': 'Aspirin',
        'dosage': '100mg',
        'status': 'pending',
        'instructions': 'Take once daily',
        'created_at': '2025-04-29'
    }]
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConn(rows))
    resp = client.get('/api/pharmacy/prescriptions')
    assert resp.status_code == 200
    assert resp.get_json() == rows

def test_get_prescription_by_id(monkeypatch, client):
    row = {
        'prescription_id': 2,
        'patient_name': 'Jane Smith',
        'medication_name': 'Tylenol',
        'dosage': '500mg',
        'status': 'filled',
        'instructions': 'Take twice daily',
        'created_at': '2025-04-28'
    }
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConn([row]))
    resp = client.get('/api/pharmacy/prescriptions/2')
    assert resp.status_code == 200
    assert resp.get_json() == row

def test_get_prescription_by_id_not_found(monkeypatch, client):
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConn([]))
    resp = client.get('/api/pharmacy/prescriptions/999')
    assert resp.status_code == 404
    assert 'error' in resp.get_json()

def test_get_requests(monkeypatch, client):
    rows = [{
        'prescription_id': 3,
        'patient_name': 'Alice',
        'medication_name': 'Penicillin',
        'dosage': '250mg',
        'status': 'pending',
        'stock_quantity': 5,
        'inventory_conflict': False
    }]
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConn(rows))
    resp = client.get('/api/pharmacy/requests?pharmacy_id=1')
    assert resp.status_code == 200
    assert resp.get_json() == rows

def test_view_past_transactions_empty(monkeypatch, client):
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConn([]))
    resp = client.get('/api/pharmacy/logs')
    assert resp.status_code == 404
    assert resp.get_json().get('message') == 'No transactions found.'

def test_add_inventory_item(monkeypatch, client):
    # We only need DummyConn([]) because _get_pharmacy_id_for_user is forced to 1,
    # so this simulates "no existing entry" → INSERT path → 201
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConn([]))
    resp = client.post(
        '/api/pharmacy/inventory/add',
        json={'user_id': 1, 'drug_name': 'Aspirin', 'stock_quantity': 10}
    )
    assert resp.status_code == 201
    assert resp.get_json().get('message') == 'Inventory item added successfully'

def test_get_inventory(monkeypatch, client):
    rows = [{'drug_name': 'Aspirin', 'stock_quantity': 20}]
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConn(rows))
    resp = client.get('/api/pharmacy/inventory?user_id=1')
    assert resp.status_code == 200
    assert resp.get_json() == rows

def test_get_pharmacy_id(monkeypatch, client):
    # This endpoint doesn't use our forced helper, so simulate a DB return:
    row = {'pharmacy_id': 99}
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConn([row]))
    resp = client.get('/api/pharmacy/getPharmacyId?user_id=1')
    assert resp.status_code == 200
    assert resp.get_json().get('pharmacy_id') == 99
