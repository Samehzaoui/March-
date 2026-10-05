# Avis, coupons, fidélité et paiement en ligne

## Installation
```
pip install -r requirements.txt
python manage.py migrate        # applique la migration boutique 0004
python manage.py runserver
```
Pensez à sauvegarder la base avant (`sauvegarde.ps1`).

## ⭐ Avis et notes
- Un client peut noter un produit (1 à 5 étoiles + commentaire) **uniquement si une commande contenant ce produit a été livrée**. Badge « Achat vérifié ».
- Un avis par client et par produit (il peut le modifier ou le supprimer).
- Publication immédiate. Modération : **Dashboard > ⭐ Avis** (masquer / afficher / supprimer). Un avis masqué n'entre plus dans la note moyenne.
- Seuls le prénom et l'initiale du nom sont affichés, jamais l'email ni le téléphone.

## 🏷️ Coupons
**Dashboard > 🏷️ Coupons > Nouveau coupon.**
- Remise en **pourcentage** ou en **montant fixe** (jamais supérieure au sous-total).
- Options : achat minimum, dates de début / fin, nombre total d'utilisations, nombre d'utilisations **par client** (compte ou numéro de téléphone), activation.
- Le client saisit le code dans son **panier**. Les commandes annulées ne comptent pas dans les utilisations.
- Supprimer un coupon ne change pas les commandes déjà passées (le code et la remise restent enregistrés).

## ⭐ Fidélité
Valeurs par défaut (modifiables dans `.env`, voir `.env.example`) :
| Règle | Valeur |
|---|---|
| Gain | 1 point par dinar payé, crédité **quand la commande passe à « livrée »** |
| Valeur | 100 points = 2 DT |
| Utilisation | à partir de 100 points, jusqu'à 50 % du montant de la commande |
| Commande annulée | points utilisés rendus, points gagnés retirés |

- Le client voit son solde dans **Mes commandes** et coche « Utiliser mes points » à la commande.
- Chaque mouvement est enregistré (impossible de créditer deux fois la même commande).
- **Dashboard > Clients > fiche client** : solde, historique et ajustement manuel (geste commercial, correction).

## 💳 Paiement en ligne
Le paiement à la livraison reste proposé. Les modes en ligne n'apparaissent que si les clés correspondantes sont dans `.env`.

### Konnect (carte bancaire, e-Dinar, Flouci, wallet Konnect)
1. Créez un compte test sur https://dashboard.sandbox.konnect.network, puis une organisation.
2. Récupérez votre **clé API** et l'**ID de votre wallet** (tableau de bord > Credentials).
3. Dans `.env` :
   ```
   KONNECT_ENV=sandbox
   KONNECT_API_KEY=...
   KONNECT_WALLET_ID=...
   SITE_URL=http://127.0.0.1:8000
   ```
4. Relancez le serveur : l'option « Payer en ligne » apparaît à la commande.
5. Cartes de test (sandbox uniquement) : Visa `4509 2111 1111 1119`, exp. 12/26, CVC 748 → paiement réussi. Mastercard `5471 2511 1111 1116`, exp. 11/23, CVC 858 → paiement refusé.
6. **Production** : créez un compte sur https://dashboard.konnect.network, mettez `KONNECT_ENV=production`, vos vraies clés et `SITE_URL=https://votre-domaine.tn`.

### Flouci
1. Créez un compte sur https://fr.flouci.com/business, ouvrez « Compte développeur API » et créez une application de test.
2. `.env` : `FLOUCI_PUBLIC_KEY=...` et `FLOUCI_PRIVATE_KEY=...`
3. Les clés de production s'activent selon la procédure « Go Live » de la documentation Flouci (https://docs.flouci.com).

### Comment ça se passe
1. Le client confirme sa commande → elle est créée (« paiement en attente ») et il est envoyé sur la page du fournisseur.
2. À son retour, **le site interroge le fournisseur** avec vos clés pour savoir si le paiement est réel. L'adresse de retour et les notifications (webhooks) ne sont jamais crues sur parole : un faux appel ne peut pas valider une commande.
3. Le montant confirmé doit être égal au total de la commande, sinon rien n'est enregistré et un message d'erreur apparaît dans les journaux (à contrôler dans le tableau de bord du fournisseur).
4. Paiement non abouti : le client peut **réessayer**, **vérifier son paiement** ou **payer à la livraison** depuis la page de la commande ou « Mes commandes ».
5. Côté admin (**fiche commande**) :
   - une commande payée en ligne ne peut pas être confirmée tant que le paiement n'est pas reçu ;
   - une fois payée, elle **n'a plus besoin du code SMS** de validation ;
   - boutons « Vérifier chez le fournisseur » et « Marquer comme payé » (secours, après contrôle sur le tableau de bord du fournisseur) ;
   - commande annulée mais payée : **le remboursement se fait chez le fournisseur** (pas automatique), puis cliquez « J'ai remboursé le client ».

### En local (sur votre PC)
Les notifications serveur à serveur de Konnect et Flouci ne peuvent pas joindre `127.0.0.1`. En test local, c'est le **retour du navigateur** du client qui déclenche la vérification, et le bouton **« Vérifier mon paiement »** fonctionne dans tous les cas. En production (site en HTTPS), les notifications arrivent aussi.

## Tests
```
python manage.py test
```
Aucun appel réseau réel : les réponses de Konnect et Flouci sont simulées.
