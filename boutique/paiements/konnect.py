"""Konnect (konnect.network) — carte bancaire, e-Dinar, Flouci et wallet Konnect.

Doc : https://docs.konnect.network — init-payment, webhook (GET ?payment_ref=...), get-payment-details.
Les montants sont en millimes. Un paiement est réussi quand payment.status == "completed".
"""
import logging

import requests
from django.conf import settings
from django.urls import reverse

from .base import ErreurPaiement, Initialisation, Verification, en_millimes, url_https_du_domaine

logger = logging.getLogger(__name__)

CODE = 'konnect'
LIBELLE = "Payer en ligne : carte bancaire, e-Dinar, Flouci (via Konnect)"


def est_configure():
    return bool(settings.KONNECT_API_KEY and settings.KONNECT_WALLET_ID)


def _api():
    if settings.KONNECT_ENV == 'production':
        return 'https://api.konnect.network/api/v2'
    return 'https://api.sandbox.konnect.network/api/v2'


def _entetes():
    return {'x-api-key': settings.KONNECT_API_KEY, 'Content-Type': 'application/json'}


def _telephone_local(commande):
    """+21622123456 -> 22123456 (format attendu par Konnect)."""
    tel = (commande.telephone or '').replace(' ', '')
    return tel[4:] if tel.startswith('+216') and len(tel) == 12 else ''


def initier(commande):
    if not est_configure():
        raise ErreurPaiement("Konnect n'est pas configuré.")
    retour = settings.SITE_URL + reverse('boutique:paiement_retour', args=[commande.pk])
    webhook = settings.SITE_URL + reverse('boutique:paiement_webhook_konnect')
    prenom, _, nom = (commande.nom_client or '').strip().partition(' ')
    corps = {
        'receiverWalletId': settings.KONNECT_WALLET_ID,
        'token': 'TND',
        'amount': en_millimes(commande.total),
        'type': 'immediate',
        'description': f"Commande #{commande.pk} - 9offty",
        'acceptedPaymentMethods': ['wallet', 'bank_card', 'e-DINAR'],
        'lifespan': 60,
        'orderId': str(commande.pk),
        'webhook': webhook,
        'successUrl': retour,
        'failUrl': retour,
        'theme': 'light',
    }
    if prenom:
        corps['firstName'] = prenom
    if nom:
        corps['lastName'] = nom
    if _telephone_local(commande):
        corps['phoneNumber'] = _telephone_local(commande)
    if commande.email:
        corps['email'] = commande.email
    try:
        r = requests.post(f"{_api()}/payments/init-payment", json=corps, headers=_entetes(),
                          timeout=settings.PAIEMENT_TIMEOUT, allow_redirects=False)
    except requests.RequestException as e:
        logger.warning("Konnect injoignable (commande %s) : %s", commande.pk, e)
        raise ErreurPaiement("Le service de paiement est momentanément indisponible.") from e
    if r.status_code not in (200, 201):
        logger.error("Konnect init-payment refusé (commande %s) : %s %s", commande.pk, r.status_code, r.text[:300])
        raise ErreurPaiement("Le service de paiement a refusé la demande.")
    try:
        data = r.json()
        url, reference = data['payUrl'], data['paymentRef']
    except (ValueError, KeyError, TypeError) as e:
        logger.error("Réponse Konnect inattendue (commande %s) : %s", commande.pk, r.text[:300])
        raise ErreurPaiement("Réponse inattendue du service de paiement.") from e
    if not url_https_du_domaine(url, 'konnect.network') or not reference:
        logger.error("Adresse de paiement Konnect suspecte (commande %s) : %s", commande.pk, url)
        raise ErreurPaiement("Réponse inattendue du service de paiement.")
    return Initialisation(url=url, reference=str(reference))


def verifier(reference):
    try:
        r = requests.get(f"{_api()}/payments/{reference}", headers=_entetes(),
                         timeout=settings.PAIEMENT_TIMEOUT, allow_redirects=False)
    except requests.RequestException as e:
        raise ErreurPaiement("Le service de paiement est momentanément indisponible.") from e
    if r.status_code != 200:
        raise ErreurPaiement(f"Vérification impossible (code {r.status_code}).")
    try:
        data = r.json()
        paiement = data.get('payment', data)
        statut_konnect = paiement.get('status')
    except (ValueError, AttributeError) as e:
        raise ErreurPaiement("Réponse inattendue du service de paiement.") from e
    montant = paiement.get('amount')
    # « pending » = pas encore payé OU tentative échouée : le client peut réessayer.
    statut = 'paye' if statut_konnect == 'completed' else 'en_attente'
    return Verification(statut=statut, montant_millimes=int(montant) if montant is not None else None, brut=data)
