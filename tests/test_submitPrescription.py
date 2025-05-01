# tests/test_prescriptions_api.py

from app import app
import os
import sys
import types
import pytest
import mysql.connector

# Ensure project root on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Stub config before importing app
sys.modules['config'] = types.SimpleNamespace(DB_CONFIG={})


# --- Helper classes ---

class DummyCursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def execute(self, query, params=None):
        pass

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def close(self):
        pass


class DummyConn:
    def __init__(self, rows=None):
        self._rows = rows or []

    def cursor(self, dictionary=True):
        return DummyCursor(self._rows.copy())

    def close(self):
        pass


@pytest.fixture
def client():
    return app.test_client()

# --- Tests for list_drugs ---


def test_list_drugs_success(monkeypatch, client):
    sample = [
        {'drug_id': 1, 'name': 'Metformin', 'description': 'Desc1'},
        {'drug_id': 2, 'name': 'Orlistat', 'description': 'Desc2'}
    ]
    # fetchall returns sample
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: DummyConn(sample))
    resp = client.get('/api/prescriptions/drugs')
    assert resp.status_code == 200
    assert resp.get_json() == sample


class ErrorConn(DummyConn):
    def cursor(self, dictionary=True):
        raise mysql.connector.Error('db fail')


def test_list_drugs_error(monkeypatch, client):
    # simulate DB failure on connect
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: ErrorConn())
    resp = client.get('/api/prescriptions/drugs')
    # setup error should give a 500
    assert resp.status_code == 500


# --- Tests for request_prescription ---

REQUEST_URL = '/api/prescriptions/request'


def test_request_no_json(client):
    resp = client.post(REQUEST_URL)
    assert resp.status_code == 400
    assert 'Request body must be JSON' in resp.get_json().get('error')


@pytest.mark.parametrize('payload,field', [
    ({'patient_id': 1, 'drug_id': 2, 'dosage': 'd', 'instructions': 'i'}, 'doctor_id'),
    ({'doctor_id': 1, 'drug_id': 2, 'dosage': 'd', 'instructions': 'i'}, 'patient_id'),
    ({'doctor_id': 1, 'patient_id': 2, 'dosage': 'd', 'instructions': 'i'}, 'drug_id'),
    ({'doctor_id': 1, 'patient_id': 2, 'drug_id': 3, 'instructions': 'i'}, 'dosage'),
    ({'doctor_id': 1, 'patient_id': 2, 'drug_id': 3, 'dosage': 'd'}, 'instructions'),
])
def test_request_missing_field(client, payload, field):
    resp = client.post(REQUEST_URL, json=payload)
    assert resp.status_code == 400
    assert f'Missing required field: {field}' in resp.get_json().get('error')


def test_request_invalid_types(client):
    payload = {'doctor_id': 'x', 'patient_id': 'y', 'drug_id': 'z', 'dosage': 'd', 'instructions': 'i'}
    resp = client.post(REQUEST_URL, json=payload)
    assert resp.status_code == 400
    assert 'must be integers' in resp.get_json().get('error')


class NoDrugConn(DummyConn):
    def cursor(self, dictionary=True):
        return DummyCursor(rows=[])


def test_request_drug_not_found(monkeypatch, client):
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: NoDrugConn())
    payload = {'doctor_id': 1, 'patient_id': 2, 'drug_id': 99, 'dosage': 'd', 'instructions': 'i'}
    resp = client.post(REQUEST_URL, json=payload)
    assert resp.status_code == 404
    assert 'Drug id 99 not found' in resp.get_json().get('error')


class NoPrefConn(DummyConn):
    def __init__(self): super().__init__([{1: 1}, None])

    def cursor(self, dictionary=True):
        return DummyCursor(rows=self._rows.copy())


def test_request_no_pref(monkeypatch, client):
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: NoPrefConn())
    payload = {'doctor_id': 1, 'patient_id': 2, 'drug_id': 3, 'dosage': 'd', 'instructions': 'i'}
    resp = client.post(REQUEST_URL, json=payload)
    assert resp.status_code == 400
    assert 'No preferred pharmacy set for patient 2' in resp.get_json().get('error')


class SuccessConn:
    def __init__(self): self.calls = 0
    def cursor(self, dictionary=True): return self
    def execute(self, query, params=None): self.calls += 1

    def fetchone(self):
        # first: drug exists, second: pref
        if self.calls == 1:
            return {1: 1}
        if self.calls == 2:
            return {'pharmacy_id': 5}
        return None

    @property
    def lastrowid(self): return 555
    def commit(self): pass
    def close(self): pass


def test_request_success(monkeypatch, client):
    monkeypatch.setattr(mysql.connector, 'connect', lambda **kw: SuccessConn())
    payload = {'doctor_id': 1, 'patient_id': 2, 'drug_id': 3, 'dosage': 'd', 'instructions': 'i'}
    resp = client.post(REQUEST_URL, json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['message'] == 'Prescription requested successfully'
    assert data['prescription_id'] == 555
