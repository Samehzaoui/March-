from django import template

register = template.Library()

EMOJIS = {
    'legume': '🥕',
    'fruit': '🍊',
    'poisson': '🐟',
    'viande': '🥩',
    'produit_laitier': '🧀',
    'epicerie': '🛒',
    'autre': '📦',
}


@register.filter
def emoji_type(type_produit):
    return EMOJIS.get(type_produit, '📦')


@register.filter
def etoiles(note):
    """3.6 -> ★★★★☆ (arrondi à l'entier le plus proche)."""
    try:
        n = max(0, min(5, int(round(float(note)))))
    except (TypeError, ValueError):
        n = 0
    return '★' * n + '☆' * (5 - n)
