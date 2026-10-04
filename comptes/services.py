"""Génération, envoi et vérification des codes SMS (connexion client + validation de commande)."""
import math
import re
import secrets
from datetime import timedelta
from typing import NamedTuple

from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import CodeSMS
from .sms import SMSError, envoyer_sms

DELAI_RENVOI_SECONDES = 60      # 1 code max par minute (même numéro, même objet)
MAX_ENVOIS_PAR_HEURE = 5        # 5 codes max par heure et par numéro
MAX_TENTATIVES = 5              # 5 essais max par code
TTL_CONNEXION_MIN = 5           # le code de connexion vaut 5 minutes
TTL_COMMANDE_MIN = 24 * 60      # le code de validation de commande vaut 24 h


class Resultat(NamedTuple):
    ok: bool
    message: str = ''
    attente: bool = False   # True si un code vient déjà d'être envoyé (délai de renvoi)


def normaliser_telephone(brut):
    """Retourne le numéro mobile tunisien au format +216XXXXXXXX, ou None s'il est invalide."""
    if not brut:
        return None
    s = re.sub(r'[\s.\-()]', '', str(brut))
    if s.startswith('+'):
        s = s[1:]
    elif s.startswith('00'):
        s = s[2:]
    if s.startswith('216') and len(s) == 11:
        s = s[3:]
    if re.fullmatch(r'[2459]\d{7}', s):
        return '+216' + s
    return None


def _empreinte(telephone, objet, commande_id, code):
    return salted_hmac('comptes.codesms', f"{telephone}|{objet}|{commande_id or ''}|{code}").hexdigest()


def envoyer_code(telephone, objet, ttl_minutes, construire_message, commande=None):
    maintenant = timezone.now()
    codes = CodeSMS.objects.filter(telephone=telephone, objet=objet, commande=commande)

    dernier = codes.first()
    if dernier:
        ecoule = (maintenant - dernier.cree_le).total_seconds()
        if ecoule < DELAI_RENVOI_SECONDES:
            reste = math.ceil(DELAI_RENVOI_SECONDES - ecoule)
            return Resultat(False, f"Un code vient d'être envoyé. Vous pourrez en demander un nouveau dans {reste} s.", attente=True)

    recents = CodeSMS.objects.filter(telephone=telephone, cree_le__gte=maintenant - timedelta(hours=1)).count()
    if recents >= MAX_ENVOIS_PAR_HEURE:
        return Resultat(False, "Trop de codes demandés pour ce numéro. Réessayez dans une heure.")

    code = f"{secrets.randbelow(10 ** 6):06d}"
    entree = CodeSMS.objects.create(
        telephone=telephone, objet=objet, commande=commande,
        code_hash=_empreinte(telephone, objet, commande.pk if commande else None, code),
        expire_le=maintenant + timedelta(minutes=ttl_minutes),
    )
    try:
        envoyer_sms(telephone, construire_message(code))
    except SMSError:
        entree.delete()
        return Resultat(False, "Impossible d'envoyer le SMS pour le moment. Réessayez dans quelques minutes.")

    codes.exclude(pk=entree.pk).filter(utilise=False).update(utilise=True)   # invalide les anciens codes
    return Resultat(True)


def verifier_code(telephone, objet, code, commande=None):
    """Retourne (ok, message_erreur)."""
    code = (code or '').strip()
    entree = CodeSMS.objects.filter(
        telephone=telephone, objet=objet, commande=commande,
        utilise=False, expire_le__gt=timezone.now(),
    ).first()
    if entree is None:
        return False, "Code expiré ou introuvable. Demandez un nouveau code."

    CodeSMS.objects.filter(pk=entree.pk).update(tentatives=F('tentatives') + 1)
    entree.refresh_from_db(fields=['tentatives'])
    if entree.tentatives > MAX_TENTATIVES:
        CodeSMS.objects.filter(pk=entree.pk).update(utilise=True)
        return False, "Trop de tentatives. Demandez un nouveau code."

    attendu = _empreinte(telephone, objet, commande.pk if commande else None, code)
    if constant_time_compare(entree.code_hash, attendu):
        if CodeSMS.objects.filter(pk=entree.pk, utilise=False).update(utilise=True):
            return True, None
        return False, "Ce code a déjà été utilisé."

    restantes = MAX_TENTATIVES - entree.tentatives
    if restantes <= 0:
        CodeSMS.objects.filter(pk=entree.pk).update(utilise=True)
        return False, "Code incorrect. Plus d'essais possibles : demandez un nouveau code."
    return False, f"Code incorrect. Il vous reste {restantes} essai(s)."


# --- Connexion client ---------------------------------------------------------

def envoyer_code_connexion(telephone):
    return envoyer_code(
        telephone, CodeSMS.OBJET_CONNEXION, TTL_CONNEXION_MIN,
        lambda code: f"9offty: code de connexion {code} (valable {TTL_CONNEXION_MIN} min). Ne le communiquez a personne.",
    )


def verifier_code_connexion(telephone, code):
    return verifier_code(telephone, CodeSMS.OBJET_CONNEXION, code)


# --- Validation de commande ---------------------------------------------------

def envoyer_code_commande(commande):
    telephone = normaliser_telephone(commande.telephone)
    if telephone is None:
        return Resultat(False, "Le numéro de téléphone de cette commande est invalide.")
    return envoyer_code(
        telephone, CodeSMS.OBJET_COMMANDE, TTL_COMMANDE_MIN,
        lambda code: f"9offty: commande #{commande.pk} confirmee. Code de validation: {code} (valable 24h). Saisissez-le sur le site.",
        commande=commande,
    )


def verifier_code_commande(commande, code):
    telephone = normaliser_telephone(commande.telephone)
    if telephone is None:
        return False, "Le numéro de téléphone de cette commande est invalide."
    return verifier_code(telephone, CodeSMS.OBJET_COMMANDE, code, commande)
