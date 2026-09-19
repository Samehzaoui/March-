from decimal import Decimal
from .models import Produit

SESSION_KEY = 'panier'


class Panier:
    """Panier d'achat stocké dans la session de l'utilisateur."""

    def __init__(self, request):
        self.session = request.session
        panier = self.session.get(SESSION_KEY)
        if not panier:
            panier = self.session[SESSION_KEY] = {}
        self.panier = panier

    def ajouter(self, produit, quantite=1):
        pid = str(produit.id)
        if pid in self.panier:
            self.panier[pid]['quantite'] += quantite
        else:
            self.panier[pid] = {
                'quantite': quantite,
                'prix': str(produit.prix),
                'nom': produit.nom,
                'unite': produit.get_unite_display(),
            }
        self.sauvegarder()

    def definir_quantite(self, produit_id, quantite):
        pid = str(produit_id)
        if pid in self.panier:
            if quantite <= 0:
                del self.panier[pid]
            else:
                self.panier[pid]['quantite'] = quantite
            self.sauvegarder()

    def supprimer(self, produit_id):
        pid = str(produit_id)
        if pid in self.panier:
            del self.panier[pid]
            self.sauvegarder()

    def vider(self):
        self.session[SESSION_KEY] = {}
        self.sauvegarder()

    def sauvegarder(self):
        self.session.modified = True

    def __iter__(self):
        ids = self.panier.keys()
        produits = Produit.objects.filter(id__in=ids)
        produits_map = {str(p.id): p for p in produits}
        for pid, item in self.panier.items():
            item = item.copy()
            item['produit'] = produits_map.get(pid)
            item['id'] = pid
            item['prix'] = Decimal(item['prix'])
            item['sous_total'] = item['prix'] * item['quantite']
            yield item

    def __len__(self):
        return sum(item['quantite'] for item in self.panier.values())

    def total(self):
        return sum(Decimal(item['prix']) * item['quantite'] for item in self.panier.values())
