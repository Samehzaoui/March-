# Performance et robustesse : PostgreSQL, Redis, Celery, cache

## Ce qui est en place
| Sujet | Sans `REDIS_URL` (développement) | Avec `REDIS_URL` (production) |
|---|---|---|
| Base de données | PostgreSQL | PostgreSQL (+ `DB_CONN_MAX_AGE=60`) |
| SMS et emails | envoyés tout de suite | envoyés par un **worker Celery** en arrière-plan |
| Cache du catalogue | mémoire du serveur | **Redis**, partagé entre tous les processus |

**Rien à installer pour développer** : sans `REDIS_URL`, le site se comporte exactement comme avant.

## Ce qui est mis en cache (et ce qui ne l'est pas)
- En cache : liste des produits (accueil, catalogue, catégories), produits similaires, catégories, menu « Tous les produits », bannières, moyens de paiement.
- **Jamais en cache : les pages entières.** Une page contient le panier, le menu « Mon compte » et des jetons de sécurité propres à chaque visiteur : les partager serait dangereux (un visiteur verrait le compte d'un autre). On met donc les *données* en cache, pas les pages.
- Le cache se vide **tout seul** dès que vous modifiez un produit, une catégorie, une bannière, un moyen de paiement, ou qu'un avis change une note. Filet de sécurité : 5 minutes maximum (`CACHE_TTL_CATALOGUE`).
- Les recherches libres (`?q=`) ne sont pas mises en cache.
- Limite : une modification faite en SQL direct ou par `queryset.update()` ne vide pas le cache avant 5 minutes.
- **Redis arrêté ? Le site continue** : le cache est simplement ignoré (un avertissement est journalisé, au plus toutes les 30 s).

## Ce qui part en arrière-plan
- Codes SMS (connexion et validation de commande) : la requête n'attend plus le fournisseur SMS. En cas d'échec, **4 nouveaux essais** avec attente croissante ; si tous échouent, le code non livré est supprimé et le client peut en redemander un.
- Emails (confirmation d'adresse, mot de passe oublié). 5 nouveaux essais.
- **Redis injoignable au moment de l'envoi ? Le SMS ou l'email part immédiatement**, comme sans Celery : rien n'est perdu.
- Les paiements en ligne ne passent pas par Celery : la vérification doit rester immédiate pour afficher le résultat au client.

## Activer Redis et Celery
### 1. Installer Redis
Redis n'existe pas officiellement pour Windows. Trois solutions :
- **Docker Desktop** (le plus simple) : `docker run -d --name redis-9offty -p 6379:6379 redis:7-alpine`
- **WSL2** (Ubuntu) : `sudo apt install redis-server` puis `sudo service redis-server start`
- **Memurai** (compatible Redis, version développeur gratuite) : https://www.memurai.com

Sur un serveur Linux : `sudo apt install redis-server`.

### 2. Configurer `.env`
```
REDIS_URL=redis://127.0.0.1:6379/0
```
Puis `pip install -r requirements.txt` (Celery et le client Redis y sont).

### 3. Lancer le worker, dans un second terminal
```powershell
cd C:\marche_tn
.\.venv\Scripts\Activate.ps1
python -m celery -A marche_tn worker -l info -P solo
```
**Sous Windows, `-P solo` est obligatoire** (le mode par défaut ne fonctionne pas). Sous Linux : `celery -A marche_tn worker -l info --concurrency=4`.

Gardez ce terminal ouvert : sans worker, les tâches s'accumulent dans Redis et les SMS/emails ne partent pas.

### 4. Vérifier
Ouvrez `http://127.0.0.1:8000/sante/` : vous devez voir `{"base": "ok", "cache": "ok", "file_attente": "ok"}`.
Sans Redis, `file_attente` indique `direct`. Si une valeur est `ko` (code HTTP 503), le service concerné ne répond pas.

## Production : liste de contrôle
- **Redis ne doit jamais être exposé sur Internet** (écoute sur `127.0.0.1`, ou mot de passe : `REDIS_URL=redis://:motdepasse@hote:6379/0`). Les codes SMS et les liens de réinitialisation de mot de passe transitent par la file.
- `DB_CONN_MAX_AGE=60` dans `.env`.
- Garder le worker en marche avec un service système. Exemple `/etc/systemd/system/9offty-worker.service` :
  ```
  [Unit]
  Description=Worker Celery 9offty
  After=network.target redis-server.service

  [Service]
  User=www-data
  WorkingDirectory=/srv/9offty
  ExecStart=/srv/9offty/.venv/bin/celery -A marche_tn worker -l info --concurrency=4
  Restart=always

  [Install]
  WantedBy=multi-user.target
  ```
- Après un déploiement qui modifie les modèles : augmentez `CACHE_VERSION` (sinon d'anciennes données en cache peuvent rester lisibles 5 minutes).
- Surveiller `/sante/` (code 503 = panne d'un service).
- Un email envoyé deux fois est possible dans de rares cas (le fournisseur a bien reçu le message mais n'a pas répondu à temps) : c'est le prix d'un envoi fiable.
- En production vous aurez aussi besoin d'un vrai serveur web (gunicorn + nginx), de `DEBUG = False` et d'un service pour les fichiers statiques : ce n'est pas couvert ici.

## Tests
`python manage.py test` : 111 tests, sans Redis ni réseau.
