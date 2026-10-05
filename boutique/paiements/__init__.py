"""Paiement en ligne : choix du fournisseur (Konnect, Flouci) et suivi d'un paiement."""
from . import flouci, konnect
from .base import ErreurPaiement, en_millimes  # noqa: F401

FOURNISSEURS = {konnect.CODE: konnect, flouci.CODE: flouci}


def fournisseurs_actifs():
    """[(code, libellé)] des fournisseurs dont les clés sont renseignées dans .env."""
    return [(code, mod.LIBELLE) for code, mod in FOURNISSEURS.items() if mod.est_configure()]


def obtenir(code):
    mod = FOURNISSEURS.get(code)
    if mod is None:
        raise ErreurPaiement("Mode de paiement inconnu.")
    return mod
