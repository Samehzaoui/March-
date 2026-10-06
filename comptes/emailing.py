"""Relais d'emails : confie l'envoi à Celery pour ne pas bloquer la requête (inscription, mot de passe oublié...).

Actif seulement quand la file d'attente l'est (REDIS_URL renseigné). Si la file est injoignable, l'email part
immédiatement avec le vrai mode d'envoi : un email n'est jamais perdu à cause de Redis.
"""
import logging

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


def serialiser(message):
    return {
        'subject': message.subject, 'body': message.body, 'from_email': message.from_email,
        'to': list(message.to), 'cc': list(message.cc), 'bcc': list(message.bcc),
        'reply_to': list(message.reply_to), 'headers': dict(message.extra_headers),
        'subtype': message.content_subtype,
        'alternatives': [[contenu, type_mime] for contenu, type_mime in getattr(message, 'alternatives', [])],
    }


class EmailAsyncBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        envoyes = 0
        for message in email_messages or []:
            if self._planifier(message):
                envoyes += 1
            else:
                envoyes += self._envoyer_directement(message)
        return envoyes

    def _planifier(self, message):
        if message.attachments:           # pièces jointes : non transportées dans la file, envoi direct
            return False
        try:
            from .tasks import envoyer_email_tache
            envoyer_email_tache.apply_async(args=(serialiser(message),), retry=False)
            return True
        except Exception:
            logger.exception("File d'attente injoignable : envoi direct de l'email")
            return False

    def _envoyer_directement(self, message):
        connexion = get_connection(settings.EMAIL_BACKEND_REEL, fail_silently=self.fail_silently)
        return connexion.send_messages([message]) or 0
