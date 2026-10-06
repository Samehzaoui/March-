from . import catalogue


def types_categories(request):
    """Types de produits utilisés, pour le menu déroulant « Tous les produits » de la barre de navigation
    (données en cache : plus de requête SQL à chaque page)."""
    return {'types_produits_nav': catalogue.types_produits_nav()}


def moyens_paiement_global(request):
    """Moyens de paiement actifs, affichés dans la barre défilante du bas de page (données en cache)."""
    return {'moyens_paiement_global': catalogue.moyens_paiement_actifs()}
