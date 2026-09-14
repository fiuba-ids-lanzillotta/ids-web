from flask import Blueprint, render_template

from web.services.cronograma import obtener_semana_en_curso

home_bp = Blueprint('home', __name__)


@home_bp.route('/')
def index():
    return render_template(
        'site/inicio.html',
        semana_actual=obtener_semana_en_curso(),
    )