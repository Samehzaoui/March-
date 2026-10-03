from django.urls import path
from . import views

app_name = 'comptes'

urlpatterns = [
    path('connexion/', views.connexion, name='connexion'),
    path('verifier/', views.verifier, name='verifier'),
    path('renvoyer/', views.renvoyer_code_connexion, name='renvoyer'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('commandes/', views.mes_commandes, name='mes_commandes'),
    path('commandes/<int:commande_id>/valider/', views.valider_commande, name='valider_commande'),
    path('commandes/<int:commande_id>/renvoyer-code/', views.renvoyer_code_commande, name='renvoyer_code_commande'),
]
