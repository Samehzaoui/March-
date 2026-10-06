try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:      # Celery non installé : les envois de SMS / emails restent synchrones
    celery_app = None
