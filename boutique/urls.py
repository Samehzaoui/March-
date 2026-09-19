from django.urls import path
from . import views

app_name = 'boutique'

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('produits/', views.liste_produits, name='liste_produits'),
    path('categorie/<slug:slug>/', views.categorie_detail, name='categorie'),
    path('produit/<slug:slug>/', views.produit_detail, name='produit_detail'),
    path('panier/', views.voir_panier, name='panier'),
    path('panier/ajouter/<int:produit_id>/', views.panier_ajouter, name='panier_ajouter'),
    path('panier/modifier/<int:produit_id>/', views.panier_modifier, name='panier_modifier'),
    path('panier/supprimer/<int:produit_id>/', views.panier_supprimer, name='panier_supprimer'),
    path('commander/', views.commander, name='commander'),
    path('commande/<int:commande_id>/confirmee/', views.commande_confirmee, name='commande_confirmee'),
]
