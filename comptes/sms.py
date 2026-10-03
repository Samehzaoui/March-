"""Envoi de SMS avec backends interchangeables.

Choisir le backend avec la variable d'environnement SMS_BACKEND :
  - console : affiche le SMS dans le terminal (développement, par défaut)
  - twilio  : envoi réel via Twilio (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM)
  - locmem  : stocke les SMS dans `outbox` (tests automatiques)

Pour un fournisseur tunisien, ajouter une fonction _envoyer_xxx() selon sa documentation
puis l'enregistrer dans BACKENDS.
"""
import base64
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

outbox = []


class SMSError(Exception):
    """L'envoi du SMS a échoué."""


def _envoyer_console(telephone, message):
    print(f"\n{'=' * 60}\n[SMS vers {telephone}]\n{message}\n{'=' * 60}\n", flush=True)


def _envoyer_locmem(telephone, message):
    outbox.append({'telephone': telephone, 'message': message})


def _envoyer_twilio(telephone, message):
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    expediteur = getattr(settings, 'TWILIO_FROM', '')
    if not (sid and token and expediteur):
        raise SMSError("Twilio n'est pas configuré (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM).")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    donnees = urllib.parse.urlencode({'To': telephone, 'From': expediteur, 'Body': message}).encode()
    requete = urllib.request.Request(url, data=donnees, method='POST')
    identifiants = base64.b64encode(f"{sid}:{token}".encode()).decode()
    requete.add_header('Authorization', f'Basic {identifiants}')
    try:
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            if reponse.status not in (200, 201):
                raise SMSError(f"Twilio a répondu avec le code {reponse.status}.")
    except urllib.error.HTTPError as exc:
        logger.error("Twilio HTTP %s : %s", exc.code, exc.read()[:300])
        raise SMSError("Le fournisseur SMS a refusé l'envoi.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.error("Twilio injoignable : %s", exc)
        raise SMSError("Le fournisseur SMS est injoignable.") from exc


BACKENDS = {
    'console': _envoyer_console,
    'locmem': _envoyer_locmem,
    'twilio': _envoyer_twilio,
}


def envoyer_sms(telephone, message):
    nom = getattr(settings, 'SMS_BACKEND', 'console')
    fonction = BACKENDS.get(nom)
    if fonction is None:
        raise SMSError(f"Backend SMS inconnu : {nom}")
    fonction(telephone, message)
