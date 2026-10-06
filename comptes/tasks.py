"""Tâches Celery : envoi des SMS et des emails en arrière-plan (nouvel essai automatique en cas d'échec)."""
import logging

from celery import Task, shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from .models import CodeSMS
from .sms import SMSError, envoyer_sms

logger = logging.getLogger(__name__)


class TacheSMS(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Échec définitif (tous les essais épuisés) : on supprime le code qui n'a jamais pu être livré,
        pour que le client puisse en redemander un tout de suite."""
        code_id = args[2] if len(args) > 2 else kwargs.get('code_id')
        if code_id:
            CodeSMS.objects.filter(pk=code_id, utilise=False).delete()
        logger.error("SMS non envoyé après plusieurs essais (tâche %s) : %s", task_id, exc)


@shared_task(base=TacheSMS, bind=True, autoretry_for=(SMSError,), retry_backoff=5, retry_backoff_max=120,
             retry_jitter=True, max_retries=4, ignore_result=True)
def envoyer_sms_tache(self, telephone, message, code_id=None):
    envoyer_sms(telephone, message)


@shared_task(autoretry_for=(Exception,), retry_backoff=10, retry_backoff_max=300, retry_jitter=True,
             max_retries=5, ignore_result=True)
def envoyer_email_tache(donnees):
    """Reconstruit l'email depuis son contenu sérialisé et l'envoie avec le VRAI mode d'envoi (SMTP, console...)."""
    message = EmailMultiAlternatives(
        subject=donnees['subject'], body=donnees['body'], from_email=donnees['from_email'],
        to=donnees['to'], cc=donnees['cc'], bcc=donnees['bcc'], reply_to=donnees['reply_to'],
        headers=donnees['headers'], connection=get_connection(settings.EMAIL_BACKEND_REEL),
    )
    message.content_subtype = donnees.get('subtype', 'plain')
    for contenu, type_mime in donnees.get('alternatives', []):
        message.attach_alternative(contenu, type_mime)
    message.send()
