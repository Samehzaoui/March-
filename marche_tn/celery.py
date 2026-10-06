"""Application Celery : exécute des tâches (envoi de SMS et d'emails) en arrière-plan.

Sans Redis configuré (variable REDIS_URL vide), Celery reste en mode « direct » : les tâches s'exécutent tout de suite,
comme avant. Voir GUIDE_PERFORMANCE.md.
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marche_tn.settings')

app = Celery('marche_tn')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
