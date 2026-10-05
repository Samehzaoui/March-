"""Programme de fidélité : 1 point par dinar payé, points échangeables contre une remise.

Règles (modifiables dans .env, voir settings.py) :
- gain  : FIDELITE_POINTS_PAR_DT points par dinar payé, crédités quand la commande passe à « livrée » ;
- usage : à partir de FIDELITE_MIN_POINTS points, jusqu'à FIDELITE_MAX_POURCENT % de la commande ;
- annulation : points utilisés rendus, points gagnés retirés.
Chaque mouvement est unique par (commande, type) : aucun traitement ne peut être appliqué deux fois.
"""
import math
from decimal import Decimal, ROUND_DOWN

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum

from .models import MILLIME, Commande, MouvementPoints


def solde(user):
    if user is None or not getattr(user, 'is_authenticated', False):
        return 0
    return MouvementPoints.objects.filter(client=user).aggregate(total=Sum('points'))['total'] or 0


def valeur_points(points):
    """Valeur en dinars d'un nombre de points."""
    return (Decimal(points) * settings.FIDELITE_VALEUR_POINT).quantize(MILLIME, rounding=ROUND_DOWN)


def points_a_gagner(montant):
    return max(0, int(math.floor(Decimal(montant) * settings.FIDELITE_POINTS_PAR_DT)))


def points_utilisables(user, base):
    """Points qu'un client peut dépenser sur une commande de `base` dinars (après coupon).

    Retourne (points, remise_en_dinars) ; (0, 0) si le client n'est pas éligible.
    """
    zero = Decimal('0.000')
    s = solde(user)
    base = Decimal(base)
    if s < settings.FIDELITE_MIN_POINTS or base <= 0 or settings.FIDELITE_VALEUR_POINT <= 0:
        return 0, zero
    plafond = (base * settings.FIDELITE_MAX_POURCENT / Decimal(100)).quantize(MILLIME, rounding=ROUND_DOWN)
    max_par_plafond = int(plafond / settings.FIDELITE_VALEUR_POINT)
    points = min(s, max_par_plafond)
    if points <= 0:
        return 0, zero
    return points, valeur_points(points)


def _mouvement_unique(client, commande, type_, points, motif):
    """Crée le mouvement s'il n'existe pas déjà pour cette commande ; retourne True si créé."""
    try:
        with transaction.atomic():
            _, cree = MouvementPoints.objects.get_or_create(
                commande=commande, type=type_,
                defaults={'client': client, 'points': points, 'motif': motif},
            )
        return cree
    except IntegrityError:
        return False


def debiter_utilisation(user, points, commande):
    MouvementPoints.objects.create(
        client=user, points=-points, type=MouvementPoints.TYPE_UTILISATION, commande=commande,
        motif=f"Utilisés sur la commande #{commande.pk}",
    )


def synchroniser(commande):
    """Applique les règles de fidélité selon le statut actuel de la commande (idempotent)."""
    if not commande.client_id:
        return
    client = commande.client

    if commande.statut == 'livree':
        gain = points_a_gagner(commande.total)
        if gain > 0 and _mouvement_unique(client, commande, MouvementPoints.TYPE_GAIN, gain,
                                          f"Commande #{commande.pk} livrée"):
            Commande.objects.filter(pk=commande.pk).update(points_gagnes=gain)
            commande.points_gagnes = gain   # évite qu'un enregistrement ultérieur de cet objet l'écrase par 0

    elif commande.statut == 'annulee':
        if commande.points_utilises > 0:
            _mouvement_unique(client, commande, MouvementPoints.TYPE_REMBOURSEMENT, commande.points_utilises,
                              f"Commande #{commande.pk} annulée : points rendus")
        gain = MouvementPoints.objects.filter(commande=commande, type=MouvementPoints.TYPE_GAIN).first()
        if gain:
            _mouvement_unique(client, commande, MouvementPoints.TYPE_ANNULATION_GAIN, -gain.points,
                              f"Commande #{commande.pk} annulée : points retirés")
