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
