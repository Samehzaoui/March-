from decimal import Decimal, ROUND_DOWN

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, Q
from django.urls import reverse
from django.utils import timezone

MILLIME = Decimal('0.001')


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
    # Calculés automatiquement à partir des avis visibles
    note_moyenne = models.DecimalField(max_digits=3, decimal_places=2, default=0, editable=False)
    nb_avis = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.get_unite_display()})"

    def get_absolute_url(self):
        return reverse('boutique:produit_detail', args=[self.slug])

    def recalculer_avis(self):
        """Met à jour la note moyenne et le nombre d'avis (avis visibles uniquement)."""
        agg = self.avis.filter(visible=True).aggregate(moyenne=Avg('note'), nb=Count('id'))
        moyenne = Decimal(str(agg['moyenne'] or 0)).quantize(Decimal('0.01'))
        Produit.objects.filter(pk=self.pk).update(note_moyenne=moyenne, nb_avis=agg['nb'] or 0)
        self.note_moyenne, self.nb_avis = moyenne, agg['nb'] or 0
        from . import catalogue   # import tardif : catalogue importe ces modèles
        catalogue.invalider()

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

    # --- Promotions et fidélité ---
    coupon = models.ForeignKey('Coupon', null=True, blank=True, on_delete=models.SET_NULL, related_name='commandes')
    code_coupon = models.CharField(max_length=40, blank=True, help_text="Code utilisé (conservé même si le coupon est supprimé)")
    remise_coupon = models.DecimalField(max_digits=9, decimal_places=3, default=0)
    points_utilises = models.PositiveIntegerField(default=0)
    remise_points = models.DecimalField(max_digits=9, decimal_places=3, default=0)
    points_gagnes = models.PositiveIntegerField(default=0)

    # --- Paiement ---
    MODE_PAIEMENT_CHOICES = [
        ('livraison', 'Paiement à la livraison'),
        ('konnect', 'En ligne (Konnect)'),
        ('flouci', 'En ligne (Flouci)'),
    ]
    STATUT_PAIEMENT_CHOICES = [
        ('a_la_livraison', 'À payer à la livraison'),
        ('en_attente', 'Paiement en attente'),
        ('paye', 'Payé'),
        ('echoue', 'Paiement échoué'),
        ('rembourse', 'Remboursé'),
    ]
    mode_paiement = models.CharField(max_length=15, choices=MODE_PAIEMENT_CHOICES, default='livraison')
    statut_paiement = models.CharField(max_length=15, choices=STATUT_PAIEMENT_CHOICES, default='a_la_livraison')
    reference_paiement = models.CharField(max_length=120, blank=True, db_index=True)
    paye_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        ordering = ['-date_commande']

    def __str__(self):
        return f"Commande #{self.pk} - {self.nom_client}"

    @property
    def sous_total(self):
        """Somme des articles, avant remises."""
        return sum((ligne.sous_total for ligne in self.lignes.all()), Decimal('0'))

    @property
    def remise_totale(self):
        return (self.remise_coupon or 0) + (self.remise_points or 0)

    @property
    def total(self):
        """Montant à payer, remises déduites."""
        return max(self.sous_total - self.remise_totale, Decimal('0'))

    @property
    def paiement_en_ligne(self):
        return self.mode_paiement != 'livraison'

    @property
    def validation_sms_requise(self):
        """Une commande déjà payée en ligne n'a pas besoin du code SMS : le paiement fait foi."""
        return not (self.paiement_en_ligne and self.statut_paiement == 'paye')


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


class Avis(models.Model):
    """Avis d'un client sur un produit (réservé aux clients dont la commande a été livrée)."""
    produit = models.ForeignKey(Produit, related_name='avis', on_delete=models.CASCADE)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='avis', on_delete=models.CASCADE)
    note = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    commentaire = models.TextField(blank=True, max_length=1000)
    visible = models.BooleanField(default=True, help_text="Décochez pour masquer cet avis sur le site")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Avis"
        verbose_name_plural = "Avis"
        ordering = ['-cree_le']
        constraints = [models.UniqueConstraint(fields=['produit', 'client'], name='un_avis_par_client_et_produit')]

    def __str__(self):
        return f"{self.produit} — {self.note}/5"


class Coupon(models.Model):
    """Code promo : remise en pourcentage ou en montant fixe."""
    TYPE_POURCENTAGE = 'pourcentage'
    TYPE_MONTANT = 'montant'
    TYPE_CHOICES = [(TYPE_POURCENTAGE, 'Pourcentage (%)'), (TYPE_MONTANT, 'Montant fixe (DT)')]

    code = models.CharField(max_length=40, unique=True, help_text="Ex : BIENVENUE10 (majuscules automatiques)")
    description = models.CharField(max_length=200, blank=True)
    type_remise = models.CharField(max_length=12, choices=TYPE_CHOICES, default=TYPE_POURCENTAGE)
    valeur = models.DecimalField(max_digits=8, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))],
                                 help_text="10 = 10 % ou 10 DT selon le type")
    montant_minimum = models.DecimalField(max_digits=8, decimal_places=3, default=0,
                                          help_text="Achat minimum (en DT) pour utiliser le code. 0 = aucun.")
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    utilisations_max = models.PositiveIntegerField(null=True, blank=True,
                                                   help_text="Nombre total d'utilisations. Vide = illimité.")
    utilisations_par_client = models.PositiveIntegerField(null=True, blank=True, default=1,
                                                          help_text="Par client. Vide = illimité.")
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"
        ordering = ['-cree_le']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        if self.type_remise == self.TYPE_POURCENTAGE and self.valeur and self.valeur > 100:
            raise ValidationError({'valeur': "Un pourcentage ne peut pas dépasser 100."})
        if self.date_debut and self.date_fin and self.date_fin <= self.date_debut:
            raise ValidationError({'date_fin': "La date de fin doit être après la date de début."})

    @property
    def libelle_remise(self):
        if self.type_remise == self.TYPE_POURCENTAGE:
            return f"-{self.valeur.normalize():f} %"
        return f"-{self.valeur} DT"

    @property
    def nb_utilisations(self):
        return self.commandes.exclude(statut='annulee').count()

    def remise_pour(self, sous_total):
        """Montant de la remise pour ce sous-total (jamais supérieur au sous-total)."""
        sous_total = Decimal(sous_total)
        if self.type_remise == self.TYPE_POURCENTAGE:
            remise = (sous_total * self.valeur / Decimal(100)).quantize(MILLIME, rounding=ROUND_DOWN)
        else:
            remise = self.valeur
        return min(remise, sous_total).quantize(MILLIME)

    def verifier(self, sous_total, user=None, telephone=None):
        """Retourne (True, '') si le code est utilisable, sinon (False, message)."""
        maintenant = timezone.now()
        if not self.actif:
            return False, "Ce code promo n'est plus actif."
        if self.date_debut and maintenant < self.date_debut:
            return False, "Ce code promo n'est pas encore valable."
        if self.date_fin and maintenant > self.date_fin:
            return False, "Ce code promo a expiré."
        if Decimal(sous_total) < self.montant_minimum:
            return False, f"Ce code est valable à partir de {self.montant_minimum} DT d'achats."
        utilisees = self.commandes.exclude(statut='annulee')
        if self.utilisations_max is not None and utilisees.count() >= self.utilisations_max:
            return False, "Ce code promo a atteint sa limite d'utilisation."
        if self.utilisations_par_client is not None:
            critere = Q()
            if user is not None and getattr(user, 'is_authenticated', False):
                critere |= Q(client=user)
            if telephone:
                critere |= Q(telephone=telephone)
            if critere and utilisees.filter(critere).count() >= self.utilisations_par_client:
                return False, "Vous avez déjà utilisé ce code promo."
        return True, ''


class MouvementPoints(models.Model):
    """Journal des points de fidélité d'un client (solde = somme des mouvements)."""
    TYPE_GAIN = 'gain'
    TYPE_UTILISATION = 'utilisation'
    TYPE_REMBOURSEMENT = 'remboursement'
    TYPE_ANNULATION_GAIN = 'annulation_gain'
    TYPE_AJUSTEMENT = 'ajustement'
    TYPE_CHOICES = [
        (TYPE_GAIN, 'Points gagnés (commande livrée)'),
        (TYPE_UTILISATION, 'Points utilisés'),
        (TYPE_REMBOURSEMENT, 'Points rendus (commande annulée)'),
        (TYPE_ANNULATION_GAIN, 'Points retirés (commande annulée)'),
        (TYPE_AJUSTEMENT, 'Ajustement manuel'),
    ]
    client = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='mouvements_points', on_delete=models.CASCADE)
    points = models.IntegerField(help_text="Positif = crédit, négatif = débit")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    commande = models.ForeignKey(Commande, null=True, blank=True, on_delete=models.SET_NULL, related_name='mouvements_points')
    motif = models.CharField(max_length=200, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mouvement de points"
        verbose_name_plural = "Mouvements de points"
        ordering = ['-cree_le', '-id']
        constraints = [
            # Un seul mouvement de chaque type par commande : rend les traitements idempotents.
            models.UniqueConstraint(fields=['commande', 'type'], condition=Q(commande__isnull=False),
                                    name='un_mouvement_par_commande_et_type'),
        ]

    def __str__(self):
        return f"{self.client} {self.points:+d} ({self.get_type_display()})"
