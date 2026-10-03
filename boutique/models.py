from django.conf import settings
from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator


class Categorie(models.Model):
    TYPE_CHOICES = [
        ('legume', 'Légume'),
        ('fruit', 'Fruit'),
        ('poisson', 'Poisson'),
        ('viande', 'Viande'),
        ('produit_laitier', 'Produit laitier'),
        ('epicerie', 'Épicerie'),
        ('autre', 'Autre'),
    ]
    nom = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True)
    type_produit = models.CharField(max_length=20, choices=TYPE_CHOICES, default='legume')
    image = models.ImageField(upload_to='categories/', blank=True, null=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['nom']

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        return reverse('boutique:categorie', args=[self.slug])


class Produit(models.Model):
    UNITE_CHOICES = [
        ('kg', 'Kilogramme'),
        ('piece', 'Pièce'),
        ('botte', 'Botte'),
        ('caisse', 'Caisse'),
    ]
    categorie = models.ForeignKey(Categorie, related_name='produits', on_delete=models.CASCADE)
    nom = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='produits/', blank=True, null=True)
    prix = models.DecimalField(max_digits=8, decimal_places=3, validators=[MinValueValidator(0)],
                                help_text="Prix en TND")
    unite = models.CharField(max_length=10, choices=UNITE_CHOICES, default='kg')
    stock = models.PositiveIntegerField(default=0, help_text="Quantité disponible")
    origine = models.CharField(max_length=100, blank=True, help_text="Ex: Nabeul, Cap Bon, Kairouan...")
    bio = models.BooleanField(default=False, verbose_name="Produit Bio")
    disponible = models.BooleanField(default=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.get_unite_display()})"

    def get_absolute_url(self):
        return reverse('boutique:produit_detail', args=[self.slug])

    @property
    def en_stock(self):
        return self.stock > 0 and self.disponible

    @property
    def est_nouveau(self):
        """Vrai si le produit a été ajouté il y a moins de 7 jours."""
        from django.utils import timezone
        from datetime import timedelta
        if not self.date_ajout:
            return False
        return timezone.now() - self.date_ajout <= timedelta(days=7)


class Commande(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('confirmee', 'Confirmée'),
        ('en_livraison', 'En livraison'),
        ('livree', 'Livrée'),
        ('annulee', 'Annulée'),
    ]
    GOUVERNORAT_CHOICES = [
        ('Ariana', 'Ariana'), ('Béja', 'Béja'), ('Ben Arous', 'Ben Arous'),
        ('Bizerte', 'Bizerte'), ('Gabès', 'Gabès'), ('Gafsa', 'Gafsa'),
        ('Jendouba', 'Jendouba'), ('Kairouan', 'Kairouan'), ('Kasserine', 'Kasserine'),
        ('Kébili', 'Kébili'), ('Kef', 'Le Kef'), ('Mahdia', 'Mahdia'),
        ('Manouba', 'Manouba'), ('Médenine', 'Médenine'), ('Monastir', 'Monastir'),
        ('Nabeul', 'Nabeul'), ('Sfax', 'Sfax'), ('Sidi Bouzid', 'Sidi Bouzid'),
        ('Siliana', 'Siliana'), ('Sousse', 'Sousse'), ('Tataouine', 'Tataouine'),
        ('Tozeur', 'Tozeur'), ('Tunis', 'Tunis'), ('Zaghouan', 'Zaghouan'),
    ]
    nom_client = models.CharField(max_length=150)
    telephone = models.CharField(max_length=20)
    adresse = models.TextField()
    gouvernorat = models.CharField(max_length=30, choices=GOUVERNORAT_CHOICES, default='Monastir')
    email = models.EmailField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_commande = models.DateTimeField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)
    note = models.TextField(blank=True, help_text="Note du client ou consigne de livraison")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='commandes')
    validee_par_client = models.BooleanField(default=False, help_text="Le client a saisi le code reçu par SMS")
    date_validation_client = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        ordering = ['-date_commande']

    def __str__(self):
        return f"Commande #{self.pk} - {self.nom_client}"

    @property
    def total(self):
        return sum(ligne.sous_total for ligne in self.lignes.all())


class LigneCommande(models.Model):
    commande = models.ForeignKey(Commande, related_name='lignes', on_delete=models.CASCADE)
    produit = models.ForeignKey(Produit, related_name='lignes_commande', on_delete=models.SET_NULL, null=True)
    nom_produit = models.CharField(max_length=150)
    prix_unitaire = models.DecimalField(max_digits=8, decimal_places=3)
    quantite = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantite} x {self.nom_produit}"

    @property
    def sous_total(self):
        return self.prix_unitaire * self.quantite


class MoyenPaiement(models.Model):
    """Logo d'un moyen de paiement affiché en barre défilante sur l'accueil."""
    nom = models.CharField(max_length=80, help_text="Ex: Visa, D17, BH Bank, Mastercard...")
    logo = models.ImageField(upload_to='paiements/')
    ordre = models.PositiveIntegerField(default=0, help_text="Ordre d'affichage (plus petit = plus à gauche)")
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Moyen de paiement"
        verbose_name_plural = "Moyens de paiement"
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class ImageAccueil(models.Model):
    """Image du diaporama d'arrière-plan de la page d'accueil."""
    titre = models.CharField(max_length=150, blank=True, help_text="Titre optionnel affiché sur l'image")
    image = models.ImageField(upload_to='accueil_slides/')
    ordre = models.PositiveIntegerField(default=0, help_text="Ordre d'affichage dans le diaporama")
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Image d'accueil"
        verbose_name_plural = "Images d'accueil"
        ordering = ['ordre', 'id']

    def __str__(self):
        return self.titre or f"Slide #{self.pk}"
