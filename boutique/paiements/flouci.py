"""Flouci Payment API v2 — portefeuille Flouci et carte bancaire.

Doc : https://docs.flouci.com — generate_payment, verify_payment/{id}.
Les montants sont en millimes. Un paiement est réussi quand success == true ET result.status == "SUCCESS".
"""
import logging

import requests
from django.conf import settings
from django.urls import reverse

from .base import ErreurPaiement, Initialisation, Verification, en_millimes, url_https_du_domaine

logger = logging.getLogger(__name__)

CODE = 'flouci'
LIBELLE = "Payer en ligne avec Flouci (portefeuille ou carte)"
API = 'https://developers.flouci.com/api/v2'


def est_configure():
    return bool(settings.FLOUCI_PUBLIC_KEY and settings.FLOUCI_PRIVATE_KEY)


def _entetes():
    return {'Authorization': f"Bearer {settings.FLOUCI_PUBLIC_KEY}:{settings.FLOUCI_PRIVATE_KEY}",
            'Content-Type': 'application/json'}


def initier(commande):
    if not est_configure():
        raise ErreurPaiement("Flouci n'est pas configuré.")
    retour = settings.SITE_URL + reverse('boutique:paiement_retour', args=[commande.pk])
    corps = {
        'amount': str(en_millimes(commande.total)),
        'developer_tracking_id': f"commande-{commande.pk}",
        'accept_card': True,
        'success_link': retour,
        'fail_link': retour,
        'webhook': settings.SITE_URL + reverse('boutique:paiement_webhook_flouci'),
        'session_timeout_secs': 1800,
    }
    try:
        r = requests.post(f"{API}/generate_payment", json=corps, headers=_entetes(),
                          timeout=settings.PAIEMENT_TIMEOUT, allow_redirects=False)
    except requests.RequestException as e:
        logger.warning("Flouci injoignable (commande %s) : %s", commande.pk, e)
        raise ErreurPaiement("Le service de paiement est momentanément indisponible.") from e
    if r.status_code not in (200, 201):
        logger.error("Flouci generate_payment refusé (commande %s) : %s %s", commande.pk, r.status_code, r.text[:300])
        raise ErreurPaiement("Le service de paiement a refusé la demande.")
    try:
        resultat = r.json()['result']
        if not resultat.get('success'):
            raise KeyError('success')
        url, reference = resultat['link'], resultat['payment_id']
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        logger.error("Réponse Flouci inattendue (commande %s) : %s", commande.pk, r.text[:300])
        raise ErreurPaiement("Réponse inattendue du service de paiement.") from e
    if not url_https_du_domaine(url, 'flouci.com') or not reference:
        logger.error("Adresse de paiement Flouci suspecte (commande %s) : %s", commande.pk, url)
        raise ErreurPaiement("Réponse inattendue du service de paiement.")
    return Initialisation(url=url, reference=str(reference))


_STATUTS = {
    'SUCCESS': 'paye',
    'PENDING': 'en_attente',
    'PREAUTH_SUCCESS': 'en_attente',
    'EXPIRED': 'echoue',
    'FAILURE': 'echoue',
    'SYSTEM_FAILURE': 'echoue',
}


def verifier(reference):
    try:
        r = requests.get(f"{API}/verify_payment/{reference}", headers=_entetes(),
                         timeout=settings.PAIEMENT_TIMEOUT, allow_redirects=False)
    except requests.RequestException as e:
        raise ErreurPaiement("Le service de paiement est momentanément indisponible.") from e
    if r.status_code != 200:
        raise ErreurPaiement(f"Vérification impossible (code {r.status_code}).")
    try:
        data = r.json()
        if data.get('success') is not True:
            raise ErreurPaiement("Flouci n'a pas confirmé la requête de vérification.")
        resultat = data['result']
        statut = _STATUTS.get(resultat.get('status'), 'en_attente')
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        raise ErreurPaiement("Réponse inattendue du service de paiement.") from e
    montant = resultat.get('amount')
    return Verification(statut=statut, montant_millimes=int(montant) if montant is not None else None, brut=data)
