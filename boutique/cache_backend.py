"""Cache Redis qui ne fait jamais tomber le site : si Redis est injoignable, on fait comme si le cache était vide.

Le backend Redis standard de Django lève une exception à chaque appel quand Redis est arrêté : toutes les pages
renverraient une erreur 500. Ici, les erreurs de connexion sont journalisées (au plus une fois toutes les 30 s)
puis ignorées : le site reste en ligne, simplement sans accélération.
"""
import functools
import logging
import time

from django.core.cache.backends.redis import RedisCache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)
_dernier_log = 0.0


def _signaler(erreur):
    global _dernier_log
    maintenant = time.monotonic()
    if maintenant - _dernier_log > 30:
        _dernier_log = maintenant
        logger.warning("Cache Redis indisponible, le site continue sans cache : %s", erreur)


def _tolerant(valeur_si_erreur):
    """`valeur_si_erreur` : valeur renvoyée quand Redis ne répond pas (ou fonction qui la calcule)."""
    def decorateur(methode):
        @functools.wraps(methode)
        def enveloppe(self, *args, **kwargs):
            try:
                return methode(self, *args, **kwargs)
            except (RedisError, OSError) as erreur:
                _signaler(erreur)
                if callable(valeur_si_erreur):
                    return valeur_si_erreur(*args, **kwargs)
                return valeur_si_erreur
        return enveloppe
    return decorateur


def _defaut_get(key, default=None, *args, **kwargs):
    return default


class RedisCacheTolerant(RedisCache):
    get = _tolerant(_defaut_get)(RedisCache.get)
    set = _tolerant(None)(RedisCache.set)
    add = _tolerant(True)(RedisCache.add)          # « ajouté » : ne bloque ni les verrous anti-spam ni les compteurs
    delete = _tolerant(False)(RedisCache.delete)
    get_many = _tolerant({})(RedisCache.get_many)
    set_many = _tolerant([])(RedisCache.set_many)
    delete_many = _tolerant(None)(RedisCache.delete_many)
    has_key = _tolerant(False)(RedisCache.has_key)
    incr = _tolerant(None)(RedisCache.incr)
    touch = _tolerant(False)(RedisCache.touch)
    clear = _tolerant(None)(RedisCache.clear)
