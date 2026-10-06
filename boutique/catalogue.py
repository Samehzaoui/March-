"""Données du catalogue gardées en cache (liste des produits, catégories, bannières, moyens de paiement).

On met en cache des DONNÉES, pas des pages entières : une page contient le panier, le menu « Mon compte » et des
jetons CSRF propres à chaque visiteur, qu'on ne doit jamais partager.

Invalidation : chaque enregistrement ou suppression d'un produit, d'une catégorie, d'une bannière ou d'un moyen de
paiement (et chaque nouvel avis) augmente un numéro de version ; les anciennes entrées ne sont alors plus lues.
Filet de sécurité : durée de vie de CACHE_TTL_CATALOGUE secondes (300 par défaut).
"""
from django.conf import settings
from django.core.cache import cache

from .models import Categorie, ImageAccueil, MoyenPaiement, Produit

CLE_VERSION = 'catalogue:version'


def _ttl():
    return getattr(settings, 'CACHE_TTL_CATALOGUE', 300)


def _version():
    version = cache.get(CLE_VERSION)
    if version is None:
        cache.add(CLE_VERSION, 1, None)
        version = cache.get(CLE_VERSION) or 1
    return version


def invalider():
    """À appeler dès que le catalogue change : toutes les entrées existantes deviennent périmées."""
    try:
        cache.incr(CLE_VERSION)
    except ValueError:                      # clé absente : la version en cours est 1, on passe à 2
        cache.set(CLE_VERSION, 2, None)


def _obtenir(nom, fabriquer):
    cle = f"catalogue:{_version()}:{nom}"
    valeur = cache.get(cle)
    if valeur is None:
        valeur = fabriquer()
        cache.set(cle, valeur, _ttl())
    return valeur


def categories():
    return _obtenir('categories', lambda: list(Categorie.objects.all()))


def types_produits_nav():
    """[(code, libellé)] des types de produits présents, pour le menu « Tous les produits »."""
    def fabriquer():
        libelles = dict(Categorie.TYPE_CHOICES)
        codes = Categorie.objects.values_list('type_produit', flat=True).distinct()
        return sorted(((code, libelles.get(code, code)) for code in codes), key=lambda t: t[1])
    return _obtenir('types_nav', fabriquer)


def moyens_paiement_actifs():
    return _obtenir('moyens_paiement', lambda: list(MoyenPaiement.objects.filter(actif=True)))


def slides_actifs():
    return _obtenir('slides', lambda: list(ImageAccueil.objects.filter(actif=True)))


def produits_vedette():
    return _obtenir('vedette', lambda: list(
        Produit.objects.filter(disponible=True).select_related('categorie').order_by('-date_ajout')[:8]))


def produits(categorie_slug=None, type_produit=None):
    """Produits disponibles d'une catégorie et/ou d'un type (jamais pour une recherche libre)."""
    def fabriquer():
        qs = Produit.objects.filter(disponible=True).select_related('categorie')
        if categorie_slug:
            qs = qs.filter(categorie__slug=categorie_slug)
        if type_produit:
            qs = qs.filter(categorie__type_produit=type_produit)
        return list(qs)
    return _obtenir(f"liste:{categorie_slug or '-'}:{type_produit or '-'}", fabriquer)


def similaires(produit):
    return _obtenir(f"similaires:{produit.pk}", lambda: list(
        Produit.objects.filter(categorie_id=produit.categorie_id, disponible=True)
        .select_related('categorie').exclude(pk=produit.pk)[:4]))
