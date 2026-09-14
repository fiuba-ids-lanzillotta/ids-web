import requests
import pytest

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True

    return flask_app.test_client()


# --- páginas públicas (services vía requests, mockeado) ---

def test_pagina_inicio_muestra_semana_actual(client, monkeypatch, respuesta_falsa, cargar_json):
    clases = [
        {**clase, 'vigente': clase.get('semana') == 4}
        for clase in cargar_json('json/cronograma/clases.json')
    ]
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: respuesta_falsa(200, clases))

    respuesta = client.get('/')

    assert respuesta.status_code == 200
    assert b'Esta semana' in respuesta.data
    assert b'Semana 4' in respuesta.data
    assert b'Python + Flask' in respuesta.data


def test_pagina_cronograma_ok(client, monkeypatch, respuesta_falsa, cargar_json):
    clases = cargar_json('json/cronograma/clases.json')
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: respuesta_falsa(200, clases))

    respuesta = client.get('/cronograma')

    assert respuesta.status_code == 200


def test_pagina_docentes_ok(client, monkeypatch, respuesta_falsa, cargar_json):
    docentes = cargar_json('json/docentes/lista.json')
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: respuesta_falsa(200, docentes))

    respuesta = client.get('/docentes')

    assert respuesta.status_code == 200


# --- admin (protegido por admin_required) ---

def test_admin_requiere_login(client):
    respuesta = client.get('/admin/')

    assert respuesta.status_code == 302
    assert '/admin/login' in respuesta.headers['Location']


def test_login_exitoso_redirige_al_panel(client, monkeypatch, respuesta_falsa, cargar_json):
    cuerpo = cargar_json('json/auth/login.json')
    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: respuesta_falsa(200, cuerpo))

    respuesta = client.post('/admin/login', data={'usuario': 'admin', 'password': 'secreto'})

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'].endswith('/admin/')


def test_login_fallido_muestra_pagina(client, monkeypatch, respuesta_falsa):
    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: respuesta_falsa(401))

    respuesta = client.post('/admin/login', data={'usuario': 'admin', 'password': 'mala'})

    assert respuesta.status_code == 200
