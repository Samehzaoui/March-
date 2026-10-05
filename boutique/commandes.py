"""Calcul du récapitulatif (coupon, points) et création d'une commande."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from . import fidelite
from .models import Coupon, LigneCommande

SESSION_COUPON = 'coupon_code'
ZERO = Decimal('0.000')


class ErreurCommande(Exception):
    """Commande refusée : le message est affiché tel quel au client."""


def telephone_verifie(user):
    profil = getattr(user, 'profil', None)
    return profil.telephone if profil else None


def calculer_recapitulatif(request, panier, utiliser_points=False):
    """Sous-total, remises et total estimé du panier pour l'utilisateur courant."""
    sous_total = Decimal(panier.total())
    user = request.user if request.user.is_authenticated else None
    coupon, remise_coupon, coupon_erreur = None, ZERO, ''

    code = request.session.get(SESSION_COUPON)
    if code:
        coupon = Coupon.objects.filter(code=code.strip().upper()).first()
        if coupon is None:
            coupon_erreur = "Ce code promo n'existe plus."
        else:
            ok, message = coupon.verifier(sous_total, user, telephone_verifie(user) if user else None)
            if ok:
                remise_coupon = coupon.remise_pour(sous_total)
            else:
                coupon_erreur, coupon = message, None
        if coupon_erreur:
            request.session.pop(SESSION_COUPON, None)

    base = sous_total - remise_coupon
    solde = fidelite.solde(user) if user else 0
    points_possibles, remise_possible = fidelite.points_utilisables(user, base) if user else (0, ZERO)
    points = points_possibles if (utiliser_points and points_possibles) else 0
    remise_points = remise_possible if points else ZERO

    return {
        'sous_total': sous_total,
        'coupon': coupon,
        'remise_coupon': remise_coupon,
        'coupon_erreur': coupon_erreur,
        'solde_points': solde,
        'points_possibles': points_possibles,
        'remise_points_possible': remise_possible,
        'points_utilises': points,
        'remise_points': remise_points,
        'total': max(base - remise_points, ZERO),
    }


def creer_commande(request, form, panier, *, utiliser_points=False, mode_paiement='livraison'):
    """Crée la commande (lignes, coupon, points) de façon atomique. Lève ErreurCommande si refusée."""
    user = request.user
    with transaction.atomic():
        # Verrous : deux commandes simultanées ne peuvent pas dépenser deux fois les mêmes points
        # ni dépasser la limite d'utilisation d'un coupon.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        items = list(panier)
        if not items:
            raise ErreurCommande("Votre panier est vide.")
        sous_total = sum((i['sous_total'] for i in items), Decimal('0'))
        telephone = form.telephone_verifie or form.cleaned_data.get('telephone')

        coupon, remise_coupon = None, ZERO
        code = request.session.get(SESSION_COUPON)
        if code:
            coupon = Coupon.objects.select_for_update().filter(code=code.strip().upper()).first()
            if coupon is None:
                request.session.pop(SESSION_COUPON, None)
                raise ErreurCommande("Ce code promo n'existe plus.")
            ok, message = coupon.verifier(sous_total, user, telephone)
            if not ok:
                request.session.pop(SESSION_COUPON, None)
                raise ErreurCommande(message)
            remise_coupon = coupon.remise_pour(sous_total)

        base = sous_total - remise_coupon
        points, remise_points = 0, ZERO
        if utiliser_points:
            points, remise_points = fidelite.points_utilisables(user, base)
            if points == 0:
                raise ErreurCommande("Vous n'avez pas assez de points pour cette commande.")

        if mode_paiement != 'livraison' and base - remise_points <= 0:
            mode_paiement = 'livraison'  # rien à payer en ligne

        commande = form.save(commit=False)
        commande.client = user
        commande.telephone = telephone
        commande.coupon = coupon
        commande.code_coupon = coupon.code if coupon else ''
        commande.remise_coupon = remise_coupon
        commande.points_utilises = points
        commande.remise_points = remise_points
        commande.mode_paiement = mode_paiement
        commande.statut_paiement = 'a_la_livraison' if mode_paiement == 'livraison' else 'en_attente'
        commande.save()

        for item in items:
            LigneCommande.objects.create(
                commande=commande, produit=item['produit'], nom_produit=item['nom'],
                prix_unitaire=item['prix'], quantite=item['quantite'],
            )
        if points:
            fidelite.debiter_utilisation(user, points, commande)

    request.session.pop(SESSION_COUPON, None)
    return commande
