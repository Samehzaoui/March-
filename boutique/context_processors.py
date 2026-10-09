from django.conf import settings

from . import catalogue


def types_categories(request):
    """Types de produits utilisés, pour le menu déroulant « Tous les produits » de la barre de navigation
    (données en cache : plus de requête SQL à chaque page)."""
    return {'types_produits_nav': catalogue.types_produits_nav()}


def moyens_paiement_global(request):
    """Moyens de paiement actifs, affichés dans la barre défilante du bas de page (données en cache)."""
    return {'moyens_paiement_global': catalogue.moyens_paiement_actifs()}


def version_statique(request):
    """Date de modification du CSS et du JS, ajoutée à leur adresse (?v=...) :
    le navigateur recharge ces fichiers dès qu'une nouvelle version est installée, sans « Ctrl + F5 »."""
    def version(chemin):
        try:
            return int((settings.BASE_DIR / 'static' / chemin).stat().st_mtime)
        except OSError:
            return 0
    return {'v_css': version('css/style.css'), 'v_js': version('js/boutique.js')}
