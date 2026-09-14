"""Consumo de la API (ids-api) para el cronograma."""
import logging
from datetime import datetime

import requests

from web.constants import API_BASE_URL, api_headers
from web.services.respuestas_api import mensaje_error_api, respuesta_no_autorizada

logger = logging.getLogger(__name__)


def _fecha_iso_a_corta(fecha_iso: str) -> str:
    """2026-03-09 → 09/03 (lo que muestra la tabla)."""
    try:
        return datetime.strptime(str(fecha_iso)[:10], '%Y-%m-%d').strftime('%d/%m')
    except ValueError:
        return str(fecha_iso)


def _clase_para_vista(clase: dict) -> dict:
    """Adapta el DTO de la API al formato de la tabla (contenidos + hito en rojo)."""
    contenidos_crudos = clase.get('contenidos') or []
    contenidos = []
    hitos = []

    for contenido in contenidos_crudos:
        if isinstance(contenido, str):
            if contenido.strip():
                contenidos.append(contenido.strip())
        else:
            texto = str(contenido.get('texto') or '').strip()
            
            if texto and contenido.get('hito'):
                hitos.append(texto)
            elif texto:
                contenidos.append(texto)

    fecha_iso = clase.get('fecha') or ''

    return {
        'id': clase.get('id'),
        'semana': clase.get('semana'),
        'fecha': _fecha_iso_a_corta(fecha_iso),
        'fecha_iso': str(fecha_iso)[:10],
        'tipo': clase.get('tipo') or '',
        'titulo': clase.get('titulo') or '',
        'contenidos': contenidos,
        'hitos': hitos,
        'vigente': bool(clase.get('vigente')),
    }


def _agrupar_semanas(clases: list[dict]) -> list[dict]:
    por_semana: dict[int, list[dict]] = {}

    for clase in clases:
        vista = _clase_para_vista(clase)
        semana = vista.get('semana') or 0
        por_semana.setdefault(semana, []).append(vista)

    return [
        {
            'semana': semana,
            'clases': items,
            'vigente': any(item.get('vigente') for item in items),
        }
        for semana, items in sorted(por_semana.items())
    ]

def obtener_semana_actual(semanas: list[dict]) -> dict | None:
    """Elige el grupo que ids-api marcó con vigente=true."""
    for semana in semanas:
        if semana.get('vigente'):
            return semana

    return None


def obtener_semana_en_curso() -> dict | None:
    """Lee GET /cronograma/clases y devuelve la semana que la API marca como vigente."""
    return obtener_semana_actual(obtener_semanas())

def obtener_semanas() -> list[dict]:
    """Lista el cronograma agrupado por semana, listo para la tabla."""
    try:
        response = requests.get(f'{API_BASE_URL}/cronograma/clases', headers=api_headers(), timeout=10)

        if response.status_code == 200:
            return _agrupar_semanas(response.json() or [])

        if response.status_code == 204:
            return []

    except requests.exceptions.ConnectionError:
        logger.error(f"No se pudo conectar con la API en {API_BASE_URL}")
    except Exception as error:
        logger.error(f"Error al obtener el cronograma: {error}")

    return []


def actualizar_clase(token: str, clase_id: int, datos: dict) -> dict:
    """Actualiza una clase vía PUT /cronograma/clases/<id>."""
    try:
        response = requests.put(
            f'{API_BASE_URL}/cronograma/clases/{clase_id}',
            json=datos,
            headers=api_headers({'Authorization': f'Bearer {token}'}),
            timeout=15,
        )

        no_autorizada = respuesta_no_autorizada(response)
        if no_autorizada:
            return no_autorizada

        if response.status_code == 200:
            return {'ok': True}

        return {'ok': False, 'error': mensaje_error_api(response)}

    except requests.exceptions.ConnectionError:
        logger.error(f"No se pudo conectar con la API en {API_BASE_URL}")
        
        return {'ok': False, 'error': 'No se pudo conectar con el servidor. Intentá más tarde.'}

    except Exception as error:
        logger.error(f"Error al actualizar la clase: {error}")
        
        return {'ok': False, 'error': 'Ocurrió un error al guardar la clase.'}


def body_desde_formulario(form) -> dict:
    """Arma el JSON de la API a partir del form de editar clase."""
    contenidos = []

    for linea in (form.get('contenidos') or '').splitlines():
        texto = linea.strip()
        
        if texto:
            contenidos.append({'texto': texto, 'hito': False})

    for hito in form.getlist('hito'):
        texto = hito.strip()
        
        if texto:
            contenidos.append({'texto': texto, 'hito': True})

    titulo = (form.get('titulo') or '').strip() or None
    semana_texto = (form.get('semana') or '').strip()
    semana = int(semana_texto) if semana_texto.isdigit() else semana_texto

    return {
        'semana': semana,
        'fecha': (form.get('fecha') or '').strip(),
        'tipo': (form.get('tipo') or '').strip(),
        'titulo': titulo,
        'contenidos': contenidos,
    }


def descargar_csv() -> dict:
    """Proxy de GET /cronograma/csv: devuelve el archivo tal cual lo arma la API."""
    try:
        response = requests.get(f'{API_BASE_URL}/cronograma/csv', headers=api_headers(), timeout=15)
        
        if response.status_code == 200:
            return {
                'ok': True,
                'contenido': response.content,
                'disposition': response.headers.get(
                    'Content-Disposition',
                    'attachment; filename="cronograma.csv"',
                ),
            }
        
        return {'ok': False, 'error': mensaje_error_api(response)}
    except requests.exceptions.ConnectionError:
        logger.error(f"No se pudo conectar con la API en {API_BASE_URL}")
        
        return {'ok': False, 'error': 'No se pudo conectar con el servidor. Intentá más tarde.'}
    except Exception as error:
        logger.error(f"Error al descargar el cronograma: {error}")
        
        return {'ok': False, 'error': 'Ocurrió un error al descargar el calendario.'}


def publicar_csv(token: str, archivo) -> dict:
    """Reemplaza el cronograma vía PUT /cronograma/csv (archivo tal cual)."""
    if not archivo or not archivo.filename:
        return {'ok': False, 'error': 'Elegí un archivo CSV para publicar.'}
    
    try:
        response = requests.put(
            f'{API_BASE_URL}/cronograma/csv',
            files={'archivo': (archivo.filename, archivo.stream, 'text/csv')},
            headers=api_headers({'Authorization': f'Bearer {token}'}),
            timeout=30,
        )
        
        no_autorizada = respuesta_no_autorizada(response)
        
        if no_autorizada:
            return no_autorizada
        if response.status_code == 200:
            return {'ok': True}
        
        return {'ok': False, 'error': mensaje_error_api(response)}
    except requests.exceptions.ConnectionError:
        logger.error(f"No se pudo conectar con la API en {API_BASE_URL}")
        
        return {'ok': False, 'error': 'No se pudo conectar con el servidor. Intentá más tarde.'}
    except Exception as error:
        logger.error(f"Error al publicar el CSV: {error}")
        
        return {'ok': False, 'error': 'Ocurrió un error al publicar el calendario.'}
