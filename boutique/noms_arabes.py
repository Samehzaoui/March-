"""Noms arabes suggérés pour les produits de démonstration (fruits et légumes du marché tunisien).

Ce sont des SUGGESTIONS en arabe usuel, à relire : plusieurs produits ont un nom différent selon les régions
(ex. persil : بقدونس / معدنوس). Modifiez-les librement dans le dashboard (fiche produit > « Nom en arabe »).
Le nom français peut contenir un complément entre parenthèses : seule la partie avant la parenthèse est utilisée.
"""
import unicodedata

NOMS_AR = {
    # Légumes
    "Tomate": "طماطم", "Pomme de terre": "بطاطا", "Oignon": "بصل", "Ail": "ثوم",
    "Poivron vert": "فلفل أخضر", "Poivron rouge": "فلفل أحمر", "Piment fort": "فلفل حار",
    "Courgette": "كوسة", "Aubergine": "باذنجان", "Carotte": "جزر", "Concombre": "خيار",
    "Laitue": "خس", "Persil": "بقدونس", "Coriandre": "كزبرة", "Menthe": "نعناع",
    "Fève fraîche": "فول طازج", "Petit pois": "جلبانة", "Chou blanc": "كرنب أبيض",
    "Chou-fleur": "قرنبيط", "Betterave": "شمندر", "Navet": "لفت", "Radis": "فجل",
    "Épinard": "سبانخ", "Fenouil": "شمر", "Artichaut": "خرشوف", "Courge": "قرع",
    "Haricot vert": "لوبيا خضراء", "Céleri": "كرفس", "Petit piment vert doux": "فلفل أخضر حلو",
    "Citrouille": "قرع حلو",
    # Fruits
    "Orange Maltaise": "برتقال مالطي", "Clémentine": "كليمنتين", "Citron": "ليمون", "Pomme": "تفاح",
    "Poire": "كمثرى", "Banane": "موز", "Fraise": "فراولة", "Raisin": "عنب", "Pastèque": "دلاع",
    "Melon": "بطيخ", "Pêche": "خوخ", "Abricot": "مشمش", "Figue de Barbarie": "تين شوكي",
    "Figue fraîche": "تين طازج", "Grenade": "رمان", "Datte Deglet Nour": "تمر دقلة نور",
    "Mandarine": "ماندرين", "Pamplemousse": "جريب فروت", "Coing": "سفرجل",
}


def _cle(texte):
    """« Menthe (Nãanãa) » -> « menthe » : sans parenthèse, accents ni majuscules."""
    base = texte.split('(')[0].strip().lower()
    decompose = unicodedata.normalize('NFKD', base)
    return ''.join(c for c in decompose if not unicodedata.combining(c))


_INDEX = {_cle(nom): arabe for nom, arabe in NOMS_AR.items()}


def nom_arabe_pour(nom_francais):
    """Nom arabe suggéré, ou chaîne vide si le produit n'est pas dans la liste."""
    return _INDEX.get(_cle(nom_francais or ''), '')
