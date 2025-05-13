# tests/test_dispense.py

import os
import sys
# ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import types
import pytest
import mysql.connector

# stub out config before importing app.
sys.modules['config'] = types.SimpleNamespace(DB_CONFIG={})

from app import app
import blueprints.dispensePrescription.dispense as disp_mod

# --- helper connection classes ---
class DummyConnEmpty:
    def __init__(self): pass
    def cursor(self, dictionary=True): return DummyCursorEmpty()
    def close(self): pass
class DummyCursorEmpty:
    def execute(self, query, params=None): pass
    def fetchone(self): return None
    def close(self): pass

@pytest.fixture
def client():
    return app.test_client()

# 1) Missing user_id -> 400
def test_no_user_id(client):
    resp = client.post('/api/pharmacy/prescriptions/1/dispense')
    assert resp.status_code == 400
    assert resp.get_json().get('error') == 'user_id is required'

# 2) No active pharmacy -> 404
def test_pharmacy_not_found(monkeypatch, client):
    monkeypatch.setattr(disp_mod, '_get_pharmacy_id_for_user', lambda user_id, cursor: None)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConnEmpty())
    resp = client.post('/api/pharmacy/prescriptions/1/dispense?user_id=1')
    assert resp.status_code == 404
    assert 'No active pharmacy' in resp.get_json().get('error')

# 3) Prescription not found -> 404
class PresNotFoundConn(DummyConnEmpty): pass

def test_prescription_not_found(monkeypatch, client):
    monkeypatch.setattr(disp_mod, '_get_pharmacy_id_for_user', lambda u, c: 1)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: DummyConnEmpty())
    resp = client.post('/api/pharmacy/prescriptions/2/dispense?user_id=1')
    assert resp.status_code == 404
    assert 'Prescription not found' in resp.get_json().get('error')

# 4) Prescription not ready -> 400
class NotReadyConn:
    def cursor(self, dictionary=True): return NotReadyCursor()
    def close(self): pass
class NotReadyCursor:
    def __init__(self): self.call = 0
    def execute(self, query, params=None): self.call += 1
    def fetchone(self):
        # first fetch => pres
        if self.call == 1:
            return {'patient_id':1, 'drug_id':2, 'status':'pending'}
        return None
    def close(self): pass

def test_not_ready(monkeypatch, client):
    monkeypatch.setattr(disp_mod, '_get_pharmacy_id_for_user', lambda u, c: 1)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: NotReadyConn())
    resp = client.post('/api/pharmacy/prescriptions/3/dispense?user_id=1')
    assert resp.status_code == 400
    assert 'not ready for dispense' in resp.get_json().get('error')

# 5) Price not set -> 500
class PriceNoneConn:
    def cursor(self, dictionary=True): return PriceNoneCursor()
    def close(self): pass
class PriceNoneCursor:
    def __init__(self): self.call = 0
    def execute(self, query, params=None): self.call += 1
    def fetchone(self):
        # first fetch => pres
        if self.call == 1:
            return {'patient_id':1, 'drug_id':2, 'status':'filled'}
        # second fetch => price lookup
        if self.call == 2:
            return None
        return None
    def close(self): pass

def test_price_not_set(monkeypatch, client):
    monkeypatch.setattr(disp_mod, '_get_pharmacy_id_for_user', lambda u, c: 1)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: PriceNoneConn())
    resp = client.post('/api/pharmacy/prescriptions/4/dispense?user_id=1')
    assert resp.status_code == 500
    assert 'Price not set for this drug' in resp.get_json().get('error')

# 6) Success -> 200
class SuccessConn:
    def cursor(self, dictionary=True): return SuccessCursor()
    def commit(self): pass
    def close(self): pass
class SuccessCursor:
    def __init__(self): self.call = 0; self.lastrowid = 999
    def execute(self, query, params=None): self.call += 1
    def fetchone(self):
        if self.call == 1:
            return {'patient_id':5, 'drug_id':6, 'status':'filled'}
        if self.call == 2:
            return {'price':42.0}
        return None
    def close(self): pass

def test_success(monkeypatch, client):
    monkeypatch.setattr(disp_mod, '_get_pharmacy_id_for_user', lambda u, c: 1)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: SuccessConn())
    resp = client.post('/api/pharmacy/prescriptions/5/dispense?user_id=1')
    data = resp.get_json()
    assert resp.status_code == 200
    assert data['message'] == 'Prescription dispensed and payment created'
    assert data['prescription_id'] == 5
    assert data['amount'] == 42.0
    assert data['payment_id'] == 999

# 7) Get filled prescriptions -> 200
class FilledConn:
    def cursor(self, dictionary=True): return FilledCursor()
    def close(self): pass
class FilledCursor:
    def execute(self, query, params=None): pass
    def fetchall(self):
        return [{
            'prescription_id':10,
            'patient_name':'Alice',
            'medication_name':'DrugX',
            'dosage':'5mg',
            'requested_at':'2025-04-29T10:00:00'
        }]
    def close(self): pass

def test_get_filled(monkeypatch, client):
    monkeypatch.setattr(disp_mod, '_get_pharmacy_id_for_user', lambda u, c: 1)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kwargs: FilledConn())
    resp = client.get('/api/pharmacy/prescriptions/filled?user_id=1')
    assert resp.status_code == 200
    assert resp.get_json() == [{
        'prescription_id':10,
        'patient_name':'Alice',
        'medication_name':'DrugX',
        'dosage':'5mg',
        'requested_at':'2025-04-29T10:00:00'
    }]
