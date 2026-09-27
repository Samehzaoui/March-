from .models import Categorie


def types_categories(request):
    """Rend disponible partout la liste des types de produits utilisés,
    pour construire le menu déroulant 'Tous les produits' dans la navbar."""
    types_utilises = (
        Categorie.objects.values_list('type_produit', flat=True).distinct()
    )
    choices_dict = dict(Categorie.TYPE_CHOICES)
    types_disponibles = [
        (code, choices_dict.get(code, code)) for code in types_utilises
    ]
    types_disponibles.sort(key=lambda t: t[1])
    return {'types_produits_nav': types_disponibles}
