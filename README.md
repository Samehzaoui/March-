# 🥕 9offty — Application Django de vente de fruits, légumes, poissons & viandes en ligne

Application e-commerce Django destinée au marché tunisien, permettant de vendre
tous types de fruits et légumes en ligne, avec un espace d'administration
(dashboard) protégé par identifiant / mot de passe.

## Fonctionnalités

### Boutique (côté client)
- Page d'accueil avec catégories et nouveautés
- Catalogue de produits filtrable (par type Fruit / Légume, par catégorie, par recherche)
- Fiche produit détaillée (prix en DT, unité, origine, stock, bio ou non)
- Panier d'achat (basé sur la session, pas besoin de créer de compte client)
- Tunnel de commande (nom, téléphone, adresse, gouvernorat, note de livraison)
- Page de confirmation de commande
- Prix en Dinar Tunisien (DT), les 24 gouvernorats disponibles à la livraison

### Nouveautés récentes
- **Catégories multiples et extensibles** : au-delà de Légumes/Fruits, vous pouvez créer des catégories de type Poissons, Viandes, Produits laitiers, Épicerie, etc.
- **Barre de moyens de paiement défilante** (Visa, D17, BH Bank...) affichée sur l'accueil, gérée depuis le dashboard (`/gestion/paiements/`)
- **Diaporama d'arrière-plan sur l'accueil** : 5-6 images qui changent automatiquement toutes les 12 secondes, gérées depuis le dashboard (`/gestion/slides/`)
- **Badges "Nouveau" et "Rupture de stock"** en ruban diagonal sur la photo des produits (automatique : "Nouveau" pendant 7 jours après ajout, "Rupture de stock" dès que la quantité = 0)
- **Menu déroulant dynamique** "Tous les produits" dans la navbar, listant tous les types de catégories existants
- Copyright en pied de page : © 9offty — Développé par Sameh Ezzaoui

### Espace administrateur (dashboard)
- **Page de connexion dédiée** (`/gestion/login/`) avec identifiant + mot de passe,
  distincte de l'admin Django natif
- Tableau de bord avec statistiques : nombre de produits, catégories, commandes,
  chiffre d'affaires, alertes rupture de stock et commandes en attente
- Gestion complète des **produits** (ajout, modification, suppression, upload d'image)
- Gestion des **catégories** (Fruits / Légumes personnalisables)
- Gestion des **commandes** avec changement de statut (en attente, confirmée,
  en livraison, livrée, annulée)
- Toutes les pages du dashboard sont protégées : accès refusé et redirection
  vers la page de connexion si l'utilisateur n'est pas connecté ou n'est pas staff
- L'admin Django natif (`/admin/`) reste également disponible pour une gestion avancée

### Avis, promotions, fidélité et paiement en ligne (nouveau)
- **Avis et notes** sur les produits, réservés aux clients livrés, avec modération (`/gestion/avis/`)
- **Codes promo** en % ou en montant (`/gestion/coupons/`)
- **Programme de fidélité** : points gagnés à la livraison, utilisables sur les commandes
- **Paiement en ligne** Konnect et Flouci, en plus du paiement à la livraison
- Détails et configuration : `GUIDE_PAIEMENT_FIDELITE.md`

### Comptes clients (nouveau)
- **Page unique de connexion / inscription** à onglets animés : SMS, Email, Inscription (`/compte/connexion/`)
- Inscription et connexion par **email + mot de passe**, mot de passe oublié
- Connexion **Google / Facebook / Apple** (voir `GUIDE_CONNEXION_SOCIALE.md`)
- Connexion par **code SMS** conservée

## Installation

```bash
# 1. Créer un environnement virtuel (recommandé)
python3 -m venv venv
source venv/bin/activate        # sous Windows : venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Appliquer les migrations (la base SQLite est déjà fournie et pré-remplie,
#    mais cette commande est utile si vous repartez d'une base vide)
python manage.py migrate

# 4. (Optionnel) recréer un compte administrateur si besoin
python manage.py createsuperuser

# 5. (Optionnel) repeupler le catalogue avec des produits tunisiens de démonstration
python manage.py peupler_donnees

# 6. Lancer le serveur de développement
python manage.py runserver
```

Le site est ensuite accessible sur : **http://127.0.0.1:8000/**

## Accès administrateur par défaut

Un compte administrateur de démonstration est déjà créé dans la base fournie :

- URL de connexion : **http://127.0.0.1:8000/gestion/login/**
- Identifiant : **admin**
- Mot de passe : **Admin@2026**

⚠️ **Pensez à changer ce mot de passe avant toute mise en production**, ou créez
un nouveau compte avec `python manage.py createsuperuser` et supprimez l'ancien
depuis `/admin/`.

## Structure du projet

```
marche_tn/
├── manage.py
├── requirements.txt
├── db.sqlite3                  # base de données SQLite pré-remplie (50 produits)
├── marche_tn/                  # configuration du projet Django
│   ├── settings.py
│   └── urls.py
├── boutique/                   # app publique : catalogue, panier, commandes
│   ├── models.py               # Categorie, Produit, Commande, LigneCommande
│   ├── views.py
│   ├── panier.py               # logique du panier en session
│   ├── forms.py
│   └── management/commands/peupler_donnees.py
├── dashboard/                  # app admin : login, CRUD, statistiques
│   ├── views.py
│   └── urls.py
├── templates/
│   ├── base.html                     # template boutique
│   ├── registration/login.html       # page de connexion admin
│   ├── boutique/                     # templates du site public
│   └── dashboard/                    # templates du dashboard admin
├── static/css/style.css
└── media/                      # images uploadées (produits, catégories)
```

## Notes techniques

- **Base de données** : SQLite par défaut (fichier `db.sqlite3` fourni, déjà
  migré et peuplé avec 50 produits répartis en 2 catégories : Légumes et Fruits).
  Pour un déploiement en production, remplacez par PostgreSQL/MySQL dans
  `marche_tn/settings.py` (section `DATABASES`).
- **Devise** : Dinar Tunisien (DT), prix au format décimal à 3 chiffres
  (ex : 1.250 DT) comme c'est l'usage en Tunisie.
- **Paiement** : le tunnel de commande est conçu pour un paiement à la
  livraison (COD), courant sur le marché tunisien. Aucune passerelle de
  paiement en ligne n'est intégrée par défaut — à ajouter selon vos besoins
  (Flouci, Paymee, D17, etc.).
- **Sécurité** : `DEBUG = True` et `SECRET_KEY` par défaut sont réglés pour le
  développement. **Changez impérativement ces valeurs avant toute mise en ligne**
  (utilisez des variables d'environnement pour `SECRET_KEY`, mettez `DEBUG = False`
  et configurez `ALLOWED_HOSTS`).
- **Images** : en développement, les fichiers médias sont servis directement par
  Django. En production, configurez un serveur de fichiers statiques/médias
  (nginx, S3, etc.).

## Ajouter vos propres produits

Deux façons de procéder :
1. Depuis le **dashboard** (`/gestion/produits/ajouter/`) — recommandé pour un usage quotidien.
2. Depuis l'**admin Django** (`/admin/`) — pour une gestion en masse ou avancée.

Bonne vente ! 🥬🍎🍊
