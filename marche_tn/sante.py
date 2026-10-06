"""Page /sante/ : indique si la base, le cache et la file d'attente répondent (utile pour la supervision)."""
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


@never_cache
def sante(request):
    etat = {}
    try:
        with connection.cursor() as curseur:
            curseur.execute('SELECT 1')
        etat['base'] = 'ok'
    except Exception:
        etat['base'] = 'ko'

    cache.set('sante', '1', 10)
    etat['cache'] = 'ok' if cache.get('sante') == '1' else 'ko'

    from comptes.sms import file_attente_active
    if file_attente_active():
        try:
            from marche_tn import celery_app
            with celery_app.connection_for_write() as connexion:
                connexion.ensure_connection(max_retries=1, timeout=2)
            etat['file_attente'] = 'ok'
        except Exception:
            etat['file_attente'] = 'ko'
    else:
        etat['file_attente'] = 'direct'      # pas de Celery : envois immédiats

    return JsonResponse(etat, status=200 if 'ko' not in etat.values() else 503)
