from django.contrib import admin
from .models import Categorie, Produit, Commande, LigneCommande, MoyenPaiement, ImageAccueil


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
    list_display = ('id', 'nom_client', 'telephone', 'gouvernorat', 'statut', 'date_commande')
    list_filter = ('statut', 'gouvernorat')
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
