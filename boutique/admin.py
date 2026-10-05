from django.contrib import admin
from .models import (Avis, Categorie, Commande, Coupon, ImageAccueil, LigneCommande, MoyenPaiement,
                     MouvementPoints, Produit)


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'type_produit', 'slug')
    prepopulated_fields = {'slug': ('nom',)}
    list_filter = ('type_produit',)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ('nom', 'categorie', 'prix', 'unite', 'stock', 'disponible', 'bio')
    list_filter = ('categorie', 'disponible', 'bio')
    search_fields = ('nom', 'description')
    prepopulated_fields = {'slug': ('nom',)}


class LigneCommandeInline(admin.TabularInline):
    model = LigneCommande
    extra = 0
    readonly_fields = ('produit', 'nom_produit', 'prix_unitaire', 'quantite')


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom_client', 'telephone', 'gouvernorat', 'statut', 'mode_paiement', 'statut_paiement', 'date_commande')
    list_filter = ('statut', 'mode_paiement', 'statut_paiement', 'gouvernorat')
    search_fields = ('nom_client', 'telephone', 'email')
    inlines = [LigneCommandeInline]


@admin.register(MoyenPaiement)
class MoyenPaiementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre', 'actif')
    list_editable = ('ordre', 'actif')


@admin.register(ImageAccueil)
class ImageAccueilAdmin(admin.ModelAdmin):
    list_display = ('titre', 'ordre', 'actif')
    list_editable = ('ordre', 'actif')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'type_remise', 'valeur', 'montant_minimum', 'date_fin', 'actif')
    list_filter = ('type_remise', 'actif')
    search_fields = ('code', 'description')


@admin.register(Avis)
class AvisAdmin(admin.ModelAdmin):
    list_display = ('produit', 'client', 'note', 'visible', 'cree_le')
    list_filter = ('visible', 'note')
    search_fields = ('produit__nom', 'commentaire')


@admin.register(MouvementPoints)
class MouvementPointsAdmin(admin.ModelAdmin):
    list_display = ('client', 'points', 'type', 'commande', 'cree_le')
    list_filter = ('type',)
    readonly_fields = ('client', 'points', 'type', 'commande', 'cree_le')
