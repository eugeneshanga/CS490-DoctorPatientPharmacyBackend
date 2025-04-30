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
        # rows for fetchall, single for fetchone
        self._rows = rows or []
        self._single = single
    def execute(self, query, params=None):
        pass
    def fetchall(self):
        return self._rows
    def fetchone(self):
        # return single if set, else pop from rows
        if self._single is not None:
            return self._single
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
    # stub connect and force no pharmacy
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn())
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: None)
    resp = client.get('/api/pharmacy/queue?user_id=1')
    assert resp.status_code == 404
    assert resp.get_json().get('error') == 'No active pharmacy found for that user'


def test_get_queue_success(monkeypatch, client):
    # sample pending prescriptions
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

def test_fulfill_missing_user(client):
    resp = client.post(BASE_URL + '1/fulfill')
    assert resp.status_code == 400
    assert resp.get_json().get('error') == 'user_id is required'


def test_fulfill_no_pharmacy(monkeypatch, client):
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn())
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: None)
    resp = client.post(BASE_URL + '1/fulfill?user_id=1')
    assert resp.status_code == 404
    assert resp.get_json().get('error') == 'No active pharmacy found for that user'


def test_fulfill_not_found(monkeypatch, client):
    # pharmacy exists but prescription query returns None
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: 5)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn(single=None))
    resp = client.post(BASE_URL + '2/fulfill?user_id=1')
    assert resp.status_code == 404
    assert 'Prescription not found' in resp.get_json().get('error')


def test_fulfill_drug_not_found(monkeypatch, client):
    # prescription found but drug lookup returns None
    preset = {'drug_id':7}
    # first fetchone returns prescription, second fetchone returns None
    def connect_stub(**kw):
        return DummyConn(rows=None, single=preset)
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: 5)
    monkeypatch.setattr(mysql.connector, 'connect', connect_stub)
    # override cursor.fetchone to return None on second call
    # simplest: return DummyConn with first single=preset, then fetchall rows unused
    resp = client.post(BASE_URL + '3/fulfill?user_id=1')
    assert resp.status_code == 404
    assert f'Drug id {preset["drug_id"]} not found' in resp.get_json().get('error')


def test_fulfill_out_of_stock(monkeypatch, client):
    # prescription and drug found, but inventory 0
    calls = []
    class FlowConn(DummyConn):
        def __init__(self): self.calls=0
        def cursor(self, dictionary=True): return self
        def execute(self, query, params=None): self.calls+=1
        def fetchone(self):
            self.calls
            # call1=pres, call2=drug name, call3=inv
            if self.calls==1: return {'drug_id':8}
            if self.calls==2: return {'name':'DrugX'}
            if self.calls==3: return {'stock_quantity':0}
            return None
        def commit(self): pass
        def close(self): pass
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: 5)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: FlowConn())
    resp = client.post(BASE_URL + '4/fulfill?user_id=1')
    assert resp.status_code == 400
    assert resp.get_json().get('error') == 'Out of stock'


def test_fulfill_success(monkeypatch, client):
    # simulate full flow: pres->drug->inv>0->decrement->mark filled
    class SuccessConn(DummyConn):
        def __init__(self): self.calls=0
        def cursor(self, dictionary=True): return self
        def execute(self, query, params=None): self.calls+=1
        def fetchone(self):
            # 1) pres, 2) drug row, 3) inv
            if self.calls==1: return {'drug_id':9}
            if self.calls==2: return {'name':'DrugY'}
            if self.calls==3: return {'stock_quantity':5}
            return None
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass
    monkeypatch.setattr(queue_mod, '_get_pharmacy_id_for_user', lambda u, c: 5)
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: SuccessConn())
    resp = client.post(BASE_URL + '5/fulfill?user_id=1')
    assert resp.status_code == 200
    assert resp.get_json().get('message') == 'Prescription marked as filled'
