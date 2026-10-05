from django.urls import path
from . import views, views_paiement

app_name = 'boutique'

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('produits/', views.liste_produits, name='liste_produits'),
    path('categorie/<slug:slug>/', views.categorie_detail, name='categorie'),
    path('produit/<slug:slug>/', views.produit_detail, name='produit_detail'),
    path('produit/<slug:slug>/avis/', views.avis_poster, name='avis_poster'),
    path('produit/<slug:slug>/avis/supprimer/', views.avis_supprimer, name='avis_supprimer'),
    path('panier/', views.voir_panier, name='panier'),
    path('panier/coupon/', views.panier_coupon_appliquer, name='panier_coupon_appliquer'),
    path('panier/coupon/retirer/', views.panier_coupon_retirer, name='panier_coupon_retirer'),
    path('panier/ajouter/<int:produit_id>/', views.panier_ajouter, name='panier_ajouter'),
    path('panier/modifier/<int:produit_id>/', views.panier_modifier, name='panier_modifier'),
    path('panier/supprimer/<int:produit_id>/', views.panier_supprimer, name='panier_supprimer'),
    path('commander/', views.commander, name='commander'),
    path('commande/<int:commande_id>/confirmee/', views.commande_confirmee, name='commande_confirmee'),
    path('paiement/retour/<int:commande_id>/', views_paiement.retour, name='paiement_retour'),
    path('paiement/webhook/konnect/', views_paiement.webhook_konnect, name='paiement_webhook_konnect'),
    path('paiement/webhook/flouci/', views_paiement.webhook_flouci, name='paiement_webhook_flouci'),
    path('paiement/<int:commande_id>/reessayer/', views_paiement.reessayer, name='paiement_reessayer'),
    path('paiement/<int:commande_id>/livraison/', views_paiement.passer_a_la_livraison, name='paiement_livraison'),
]
