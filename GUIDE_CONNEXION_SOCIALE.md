# Connexion Google / Facebook / Apple — guide de configuration

Le code est prêt. Les boutons s'activent **automatiquement** dès que les clés correspondantes
sont renseignées dans le fichier `.env` (sinon ils s'affichent grisés « bientôt »).
Après modification du `.env`, relancez `python manage.py runserver`.

## Installation (une seule fois)
```
pip install -r requirements.txt
python manage.py migrate
```

## 1. Google (gratuit) — le plus simple
1. https://console.cloud.google.com → créer un projet.
2. « API et services » → « Écran de consentement OAuth » → type Externe → renseigner nom (9offty) et email.
3. « Identifiants » → « Créer des identifiants » → « ID client OAuth » → type **Application Web**.
4. « URI de redirection autorisés » → ajouter :
   - `http://127.0.0.1:8000/accounts/google/login/callback/`
   - `http://localhost:8000/accounts/google/login/callback/`
5. Copier l'ID client et le secret dans `.env` :
   `GOOGLE_CLIENT_ID=...` et `GOOGLE_CLIENT_SECRET=...`

## 2. Facebook (gratuit)
1. https://developers.facebook.com → « Mes applications » → Créer une application (cas d'usage : Facebook Login).
2. Paramètres → Général : copier **ID de l'app** et **Clé secrète**.
3. Produit « Facebook Login » → Paramètres → « URI de redirection OAuth valides » :
   `http://localhost:8000/accounts/facebook/login/callback/`
   (en test local, ouvrez le site via `http://localhost:8000` plutôt que `127.0.0.1`).
4. `.env` : `FACEBOOK_APP_ID=...` et `FACEBOOK_APP_SECRET=...`
5. Tant que l'app est en mode « Développement », seuls vous et les testeurs ajoutés peuvent se connecter.
   Pour le public : passer l'app en mode « Live » (politique de confidentialité requise).

## 3. Apple (payant, HTTPS obligatoire)
- Nécessite un compte **Apple Developer Program (~99 $/an)**.
- Apple refuse `localhost` : il faut un **vrai domaine en HTTPS** (impossible à tester en local simple).
1. developer.apple.com → Identifiers → créer un **App ID** avec « Sign in with Apple ».
2. Créer un **Services ID** (c'est le `APPLE_CLIENT_ID`) → configurer votre domaine et l'URL de retour :
   `https://VOTRE-DOMAINE/accounts/apple/login/callback/`
3. Keys → créer une clé « Sign in with Apple » → télécharger le fichier `.p8` (une seule fois !) → noter le **Key ID**.
4. Noter votre **Team ID** (en haut à droite du portail).
5. `.env` :
   ```
   APPLE_CLIENT_ID=le.services.id
   APPLE_KEY_ID=XXXXXXXXXX
   APPLE_TEAM_ID=YYYYYYYYYY
   APPLE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMIGT...\n-----END PRIVATE KEY-----
   ```
   (clé sur une seule ligne, retours à la ligne remplacés par `\n`)

## Production
- `SITE_DOMAIN=monsite.com` dans `.env`, puis `python manage.py migrate`.
- Remplacer `127.0.0.1:8000` par votre domaine (en `https://`) dans les URI de redirection de chaque plateforme.
- Emails : `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` + paramètres SMTP, et
  `ACCOUNT_EMAIL_VERIFICATION=mandatory` pour imposer la vérification de l'adresse.
- Ne commitez jamais `.env` (déjà dans `.gitignore`).
