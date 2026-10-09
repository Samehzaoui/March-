import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from boutique.models import Categorie, Produit
from boutique.noms_arabes import nom_arabe_pour

LEGUMES = [
    ("Tomate", "Nabeul", "kg", (0.8, 2.0)),
    ("Pomme de terre", "Kairouan", "kg", (0.9, 1.6)),
    ("Oignon", "Béja", "kg", (0.9, 1.5)),
    ("Ail", "Nabeul", "kg", (6.0, 10.0)),
    ("Poivron vert", "Bizerte", "kg", (1.5, 2.8)),
    ("Poivron rouge", "Bizerte", "kg", (2.0, 3.2)),
    ("Piment fort (Felfel)", "Nabeul", "kg", (2.0, 3.5)),
    ("Courgette", "Cap Bon", "kg", (1.2, 2.2)),
    ("Aubergine", "Kairouan", "kg", (1.0, 2.0)),
    ("Carotte", "Bizerte", "kg", (0.9, 1.6)),
    ("Concombre", "Nabeul", "kg", (1.0, 1.8)),
    ("Laitue", "Ariana", "piece", (0.6, 1.2)),
    ("Persil", "Manouba", "botte", (0.4, 0.8)),
    ("Coriandre", "Manouba", "botte", (0.4, 0.8)),
    ("Menthe (Nãanãa)", "Nabeul", "botte", (0.5, 1.0)),
    ("Fève fraîche (Foul)", "Bizerte", "kg", (2.0, 3.5)),
    ("Petit pois (Jelbana)", "Cap Bon", "kg", (2.5, 4.0)),
    ("Chou blanc", "Béja", "piece", (1.0, 1.8)),
    ("Chou-fleur", "Béja", "piece", (1.5, 2.5)),
    ("Betterave", "Kairouan", "kg", (1.0, 1.8)),
    ("Navet", "Jendouba", "kg", (0.9, 1.5)),
    ("Radis", "Ariana", "botte", (0.5, 1.0)),
    ("Épinard", "Manouba", "kg", (1.5, 2.5)),
    ("Fenouil", "Nabeul", "piece", (1.0, 1.8)),
    ("Artichaut", "Nabeul", "piece", (1.5, 2.8)),
    ("Courge (Gara)", "Kairouan", "kg", (1.0, 1.8)),
    ("Haricot vert (Loubia)", "Cap Bon", "kg", (2.5, 4.0)),
    ("Céleri", "Manouba", "botte", (0.6, 1.2)),
    ("Petit piment vert doux", "Nabeul", "kg", (2.0, 3.0)),
    ("Citrouille (Gra3 hlou)", "Sfax", "kg", (0.8, 1.5)),
]

FRUITS = [
    ("Orange Maltaise", "Cap Bon", "kg", (1.5, 2.8)),
    ("Clémentine", "Nabeul", "kg", (2.0, 3.5)),
    ("Citron", "Cap Bon", "kg", (1.8, 3.0)),
    ("Pomme", "Kasserine", "kg", (3.0, 5.0)),
    ("Poire", "Kasserine", "kg", (3.5, 5.5)),
    ("Banane", "Import", "kg", (2.5, 4.0)),
    ("Fraise", "Kalâa Kebira", "kg", (5.0, 9.0)),
    ("Raisin", "Grombalia", "kg", (3.0, 6.0)),
    ("Pastèque (Dallaa)", "Kairouan", "piece", (4.0, 9.0)),
    ("Melon (Bittikh)", "Kairouan", "piece", (3.0, 6.0)),
    ("Pêche", "Cap Bon", "kg", (3.5, 6.0)),
    ("Abricot", "Cap Bon", "kg", (4.0, 7.0)),
    ("Figue de Barbarie (Handhi)", "Kasserine", "kg", (2.0, 3.5)),
    ("Figue fraîche", "Djebba", "kg", (5.0, 10.0)),
    ("Grenade (Rmen)", "Testour", "kg", (3.0, 5.5)),
    ("Datte Deglet Nour", "Kébili", "kg", (10.0, 20.0)),
    ("Nèfle (Mesmari)", "Cap Bon", "kg", (4.0, 7.0)),
    ("Mandarine", "Nabeul", "kg", (2.0, 3.5)),
    ("Pamplemousse", "Cap Bon", "kg", (1.8, 3.0)),
    ("Coing", "Hammamet", "kg", (2.5, 4.0)),
]

DESCRIPTIONS_LEGUME = "Légume frais sélectionné auprès des producteurs locaux tunisiens, récolté à maturité pour garantir saveur et fraîcheur."
DESCRIPTIONS_FRUIT = "Fruit frais et savoureux, cueilli à point dans les vergers tunisiens pour une qualité optimale."


class Command(BaseCommand):
    help = "Peuple la base de données avec des catégories et produits (fruits & légumes) du marché tunisien."

    def add_arguments(self, parser):
        parser.add_argument('--vider', action='store_true', help="Supprime les produits/catégories existants avant de peupler.")

    def handle(self, *args, **options):
        if options['vider']:
            Produit.objects.all().delete()
            Categorie.objects.all().delete()
            self.stdout.write(self.style.WARNING("Anciennes données supprimées."))

        cat_legumes, _ = Categorie.objects.get_or_create(
            nom="Légumes", defaults={'slug': 'legumes', 'type_produit': 'legume'})
        cat_fruits, _ = Categorie.objects.get_or_create(
            nom="Fruits", defaults={'slug': 'fruits', 'type_produit': 'fruit'})

        total = 0
        for nom, origine, unite, (prix_min, prix_max) in LEGUMES:
            slug = slugify(nom)
            prix = Decimal(str(round(random.uniform(prix_min, prix_max), 3)))
            obj, cree = Produit.objects.get_or_create(
                slug=slug,
                defaults=dict(
                    categorie=cat_legumes, nom=nom, nom_ar=nom_arabe_pour(nom), description=DESCRIPTIONS_LEGUME,
                    prix=prix, unite=unite, stock=random.randint(20, 200),
                    origine=origine, bio=random.random() < 0.2, disponible=True,
                )
            )
            total += 1 if cree else 0

        for nom, origine, unite, (prix_min, prix_max) in FRUITS:
            slug = slugify(nom)
            prix = Decimal(str(round(random.uniform(prix_min, prix_max), 3)))
            obj, cree = Produit.objects.get_or_create(
                slug=slug,
                defaults=dict(
                    categorie=cat_fruits, nom=nom, nom_ar=nom_arabe_pour(nom), description=DESCRIPTIONS_FRUIT,
                    prix=prix, unite=unite, stock=random.randint(20, 200),
                    origine=origine, bio=random.random() < 0.2, disponible=True,
                )
            )
            total += 1 if cree else 0

        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {total} nouveaux produits créés dans 2 catégories (Légumes: {len(LEGUMES)}, Fruits: {len(FRUITS)})."
        ))
