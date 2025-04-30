# tests/test_queue.py

import os
import sys
import types
import pytest
import mysql.connector

# Ensure project root on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Stub out config module before importing
sys.modules['config'] = types.SimpleNamespace(DB_CONFIG={})

from app import app
import blueprints.prescriptionQueue.queue as queue_mod

# --- Helper classes for mocking ---
class DummyCursor:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single
        self.call = 0
    def execute(self, query, params=None):
        self.call += 1
    def fetchall(self):
        return self._rows
    def fetchone(self):
        if self._single is not None and self.call == 1:
            return self._single  # prescription lookup
        if self._single is None and self._rows:
            return self._rows.pop(0)
        return None
    def close(self):
        pass

class DummyConn:
    def __init__(self, rows=None, single=None):
        self._rows = rows
        self._single = single
    def cursor(self, dictionary=True):
        return DummyCursor(rows=self._rows, single=self._single)
    def commit(self):
        pass
    def rollback(self):
        pass
    def close(self):
        pass

@pytest.fixture
def client():
    return app.test_client()

# --- Tests for GET /api/pharmacy/queue ---

def test_get_queue_missing_user(client):
    resp = client.get('/api/pharmacy/queue')
    assert resp.status_code == 400
    assert resp.get_json().get('error') == 'user_id is required'


def test_get_queue_no_pharmacy(monkeypatch, client):
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn())
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: None)
    resp = client.get('/api/pharmacy/queue?user_id=1')
    assert resp.status_code == 404
    assert resp.get_json().get('error') == 'No active pharmacy found for that user'


def test_get_queue_success(monkeypatch, client):
    rows = [
        {'prescription_id':10, 'patient_name':'X', 'medication_name':'M1', 'dosage':'1mg', 'requested_at':'2025-04-29T10:00:00'},
        {'prescription_id':11, 'patient_name':'Y', 'medication_name':'M2', 'dosage':'2mg', 'requested_at':'2025-04-29T11:00:00'}
    ]
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: 5)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn(rows=rows))
    resp = client.get('/api/pharmacy/queue?user_id=1')
    assert resp.status_code == 200
    assert resp.get_json() == rows

# --- Tests for POST /api/pharmacy/prescriptions/<id>/fulfill ---

BASE_URL = '/api/pharmacy/prescriptions/'

# Missing user_id
def test_fulfill_missing_user(client):
    resp = client.post(BASE_URL + '1/fulfill')
    assert resp.status_code == 400
    assert resp.get_json().get('error') == 'user_id is required'

# No active pharmacy
def test_fulfill_no_pharmacy(monkeypatch, client):
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn())
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: None)
    resp = client.post(BASE_URL + '1/fulfill?user_id=1')
    assert resp.status_code == 404
    assert resp.get_json().get('error') == 'No active pharmacy found for that user'

# Prescription not found
def test_fulfill_not_found(monkeypatch, client):
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: 5)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn())
    resp = client.post(BASE_URL + '2/fulfill?user_id=1')
    assert resp.status_code == 404
    assert 'Prescription not found' in resp.get_json().get('error')

# Drug not found
def test_fulfill_drug_not_found(monkeypatch, client):
    preset = {'drug_id':7}
    class DrugNotFoundConn(DummyConn):
        def __init__(self): super().__init__(rows=None, single=preset)
        def cursor(self, dictionary=True): return DummyCursor(single=preset)
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: 5)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DrugNotFoundConn())
    resp = client.post(BASE_URL + '3/fulfill?user_id=1')
    assert resp.status_code == 404
    assert f"Drug id {preset['drug_id']} not found" in resp.get_json().get('error')

# Out of stock
def test_fulfill_out_of_stock(monkeypatch, client):
    class OutOfStockConn:
        def __init__(self): self.calls = 0
        def cursor(self, dictionary=True): return self
        def execute(self, query, params=None): self.calls += 1
        def fetchone(self):
            if self.calls == 1:
                return {'drug_id': 8}        # prescription lookup
            if self.calls == 2:
                return {'name': 'DrugX'}     # drug found
            if self.calls == 3:
                return {'stock_quantity': 0} # out of stock
            return None
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass

# Success flow
def test_fulfill_success(monkeypatch, client):
    class SuccessConn:
        def __init__(self): self.calls = 0
        def cursor(self, dictionary=True): return self
        def execute(self, query, params=None): self.calls += 1
        def fetchone(self):
            if self.calls == 1: return {'drug_id': 9}
            if self.calls == 2: return {'name': 'DrugY'}
            if self.calls == 3: return {'stock_quantity': 5}
            return None
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: 5)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: SuccessConn())
    resp = client.post(BASE_URL + '5/fulfill?user_id=1')
    assert resp.status_code == 200
    assert resp.get_json().get('message') == 'Prescription marked as filled'
