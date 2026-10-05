from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('login/', views.connexion, name='login'),
    path('logout/', views.deconnexion, name='logout'),
    path('', views.accueil, name='accueil'),

    path('produits/', views.produits_liste, name='produits_liste'),
    path('produits/ajouter/', views.produit_ajouter, name='produit_ajouter'),
    path('produits/<int:pk>/modifier/', views.produit_modifier, name='produit_modifier'),
    path('produits/<int:pk>/supprimer/', views.produit_supprimer, name='produit_supprimer'),

    path('categories/', views.categories_liste, name='categories_liste'),
    path('categories/ajouter/', views.categorie_ajouter, name='categorie_ajouter'),
    path('categories/<int:pk>/modifier/', views.categorie_modifier, name='categorie_modifier'),
    path('categories/<int:pk>/supprimer/', views.categorie_supprimer, name='categorie_supprimer'),

    path('clients/', views.clients_liste, name='clients_liste'),
    path('clients/ajouter/', views.client_ajouter, name='client_ajouter'),
    path('clients/export/', views.clients_export, name='clients_export'),
    path('clients/<int:pk>/', views.client_detail, name='client_detail'),
    path('clients/<int:pk>/statut/', views.client_statut, name='client_statut'),
    path('clients/<int:pk>/points/', views.client_points_ajuster, name='client_points_ajuster'),

    path('coupons/', views.coupons_liste, name='coupons_liste'),
    path('coupons/ajouter/', views.coupon_ajouter, name='coupon_ajouter'),
    path('coupons/<int:pk>/modifier/', views.coupon_modifier, name='coupon_modifier'),
    path('coupons/<int:pk>/supprimer/', views.coupon_supprimer, name='coupon_supprimer'),

    path('avis/', views.avis_liste, name='avis_liste'),
    path('avis/<int:pk>/basculer/', views.avis_basculer, name='avis_basculer'),
    path('avis/<int:pk>/supprimer/', views.avis_supprimer, name='avis_supprimer'),

    path('commandes/', views.commandes_liste, name='commandes_liste'),
    path('commandes/<int:pk>/', views.commande_detail, name='commande_detail'),

    path('paiements/', views.paiements_liste, name='paiements_liste'),
    path('paiements/ajouter/', views.paiement_ajouter, name='paiement_ajouter'),
    path('paiements/<int:pk>/modifier/', views.paiement_modifier, name='paiement_modifier'),
    path('paiements/<int:pk>/supprimer/', views.paiement_supprimer, name='paiement_supprimer'),

    path('slides/', views.slides_liste, name='slides_liste'),
    path('slides/ajouter/', views.slide_ajouter, name='slide_ajouter'),
    path('slides/<int:pk>/modifier/', views.slide_modifier, name='slide_modifier'),
    path('slides/<int:pk>/supprimer/', views.slide_supprimer, name='slide_supprimer'),
]
