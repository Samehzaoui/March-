from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from urllib.parse import urlparse


class ErreurPaiement(Exception):
    """Le fournisseur de paiement est injoignable, mal configuré ou a refusé la demande."""


@dataclass(frozen=True)
class Initialisation:
    url: str        # page de paiement du fournisseur, où envoyer le client
    reference: str  # identifiant du paiement chez le fournisseur


@dataclass(frozen=True)
class Verification:
    statut: str                          # 'paye' | 'en_attente' | 'echoue'
    montant_millimes: Optional[int]      # montant confirmé par le fournisseur (si fourni)
    brut: dict                           # réponse complète, pour les journaux


def en_millimes(montant):
    """Dinars -> millimes (entier) : 12,500 DT -> 12500."""
    return int((Decimal(montant) * 1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def url_https_du_domaine(url, domaine):
    """Vrai si `url` est en HTTPS sur `domaine` (ou un sous-domaine) : on ne redirige jamais le client ailleurs."""
    try:
        p = urlparse(url or '')
    except ValueError:
        return False
    hote = (p.hostname or '').lower()
    return p.scheme == 'https' and (hote == domaine or hote.endswith('.' + domaine))
