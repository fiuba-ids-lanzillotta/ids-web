from types import SimpleNamespace

import requests
from werkzeug.datastructures import MultiDict

from web.services import cronograma


# --- funciones puras ---

def test_fecha_iso_a_corta():
    assert cronograma._fecha_iso_a_corta('2026-08-17') == '17/08'
    assert cronograma._fecha_iso_a_corta('no-fecha') == 'no-fecha'


def test_clase_para_vista_separa_contenidos_y_hitos():
    vista = cronograma._clase_para_vista({
        'id': 1, 'semana': 3, 'fecha': '2026-08-31', 'tipo': 'Virtual', 'titulo': 'Git',
        'contenidos': ['string suelto', {'texto': 'Commit', 'hito': False}, {'texto': 'Entrega', 'hito': True}],
    })

    assert vista['fecha'] == '31/08'
    assert vista['fecha_iso'] == '2026-08-31'
    assert vista['contenidos'] == ['string suelto', 'Commit']
    assert vista['hitos'] == ['Entrega']


def test_agrupar_semanas_ordena_por_semana():
    grupos = cronograma._agrupar_semanas([
        {'semana': 2, 'fecha': '2026-08-24', 'contenidos': []},
        {'semana': 1, 'fecha': '2026-08-17', 'contenidos': []},
    ])

    assert [grupo['semana'] for grupo in grupos] == [1, 2]

def test_obtener_semana_actual_usa_vigente():
    semanas = cronograma._agrupar_semanas([
        {'semana': 3, 'fecha': '2026-09-02', 'vigente': False, 'contenidos': []},
        {'semana': 4, 'fecha': '2026-09-07', 'vigente': True, 'contenidos': []},
        {'semana': 4, 'fecha': '2026-09-09', 'vigente': True, 'contenidos': []},
    ])

    actual = cronograma.obtener_semana_actual(semanas)

    assert actual['semana'] == 4
    assert len(actual['clases']) == 2


def test_obtener_semana_actual_sin_vigente():
    semanas = cronograma._agrupar_semanas([
        {'semana': 1, 'fecha': '2026-08-17', 'vigente': False, 'contenidos': []},
    ])

    assert cronograma.obtener_semana_actual(semanas) is None

def test_body_desde_formulario():
    form = MultiDict([
        ('semana', '10'), ('fecha', '2026-10-19'), ('tipo', 'Virtual'), ('titulo', 'HTML'),
        ('contenidos', 'Tema A\n  \nTema B'), ('hito', 'Entrega 1'), ('hito', ''),
    ])

    body = cronograma.body_desde_formulario(form)

    assert body['semana'] == 10
    assert body['fecha'] == '2026-10-19'
    assert body['contenidos'] == [
        {'texto': 'Tema A', 'hito': False},
        {'texto': 'Tema B', 'hito': False},
        {'texto': 'Entrega 1', 'hito': True},
    ]


# --- obtener_semanas (requests mockeado) ---

def test_obtener_semanas_ok(monkeypatch, respuesta_falsa, cargar_json):
    clases = cargar_json('json/cronograma/clases.json')
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: respuesta_falsa(200, clases))

    semanas = cronograma.obtener_semanas()

    # Se derivan las expectativas del propio mock (robusto ante cambios de contenido):
    esperadas = sorted({clase['semana'] for clase in clases})
    
    assert [grupo['semana'] for grupo in semanas] == esperadas          # agrupado y ordenado
    assert sum(len(grupo['clases']) for grupo in semanas) == len(clases)  # no se pierde ninguna


def test_obtener_semanas_sin_conexion_devuelve_vacio(monkeypatch):
    def _sin_conexion(*args, **kwargs):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(requests, 'get', _sin_conexion)

    assert cronograma.obtener_semanas() == []


# --- actualizar_clase / descargar_csv / publicar_csv (requests mockeado) ---

def test_actualizar_clase_ok(monkeypatch, respuesta_falsa):
    monkeypatch.setattr(requests, 'put', lambda *args, **kwargs: respuesta_falsa(200))

    assert cronograma.actualizar_clase('tok', 1, {}) == {'ok': True}


def test_actualizar_clase_no_autorizado(monkeypatch, respuesta_falsa):
    monkeypatch.setattr(requests, 'put', lambda *args, **kwargs: respuesta_falsa(403))

    resultado = cronograma.actualizar_clase('tok', 1, {})

    assert resultado['ok'] is False and resultado['unauthorized'] is True


def test_descargar_csv_ok(monkeypatch, respuesta_falsa):
    monkeypatch.setattr(
        requests, 'get',
        lambda *args, **kwargs: respuesta_falsa(
            200, content=b'semana,fecha', headers={'Content-Disposition': 'attachment; filename="x.csv"'},
        ),
    )

    resultado = cronograma.descargar_csv()

    assert resultado['ok'] is True
    assert resultado['contenido'] == b'semana,fecha'
    assert 'filename' in resultado['disposition']


def test_publicar_csv_sin_archivo():
    resultado = cronograma.publicar_csv('tok', None)

    assert resultado['ok'] is False


def test_publicar_csv_ok(monkeypatch, respuesta_falsa):
    monkeypatch.setattr(requests, 'put', lambda *args, **kwargs: respuesta_falsa(200))
    archivo = SimpleNamespace(filename='cronograma.csv', stream=b'')

    assert cronograma.publicar_csv('tok', archivo) == {'ok': True}
