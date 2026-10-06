"""Tests : avis, coupons, fidélité, paiement en ligne (Konnect / Flouci simulés — aucun appel réseau réel)."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from comptes.models import ProfilClient

from . import fidelite
from .models import Avis, Categorie, Commande, Coupon, LigneCommande, MouvementPoints, Produit
from .paiements import service as paiement_service

User = get_user_model()
D = Decimal

KONNECT = dict(KONNECT_API_KEY='cle-test', KONNECT_WALLET_ID='wallet-test', KONNECT_ENV='sandbox',
               SITE_URL='https://boutique.test')
FLOUCI = dict(FLOUCI_PUBLIC_KEY='pub', FLOUCI_PRIVATE_KEY='priv', SITE_URL='https://boutique.test')


class Reponse:
    """Fausse réponse HTTP du fournisseur de paiement."""
    def __init__(self, donnees, status=200):
        self._donnees, self.status_code, self.text = donnees, status, str(donnees)

    def json(self):
        return self._donnees


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = Categorie.objects.create(nom='Légumes', slug='legumes', type_produit='legume')
        self.tomate = Produit.objects.create(categorie=self.cat, nom='Tomate', slug='tomate', prix=D('2.000'), stock=100)
        self.oignon = Produit.objects.create(categorie=self.cat, nom='Oignon', slug='oignon', prix=D('1.500'), stock=100)
        self.staff = User.objects.create_user('admin', password='x', is_staff=True, is_superuser=True)
        self.client_sms = self.nouveau_client_sms('+21622123456')

    def nouveau_client_sms(self, tel, prenom='Sami', nom='Trabelsi'):
        u = User.objects.create_user(f"tel{tel.lstrip('+')}", first_name=prenom, last_name=nom)
        ProfilClient.objects.create(user=u, telephone=tel)
        return u

    def commande(self, client=None, statut='en_attente', lignes=((2, 3),), **extra):
        """lignes = ((prix, quantité), ...) ; crée une commande avec ses lignes."""
        c = Commande.objects.create(client=client or self.client_sms, nom_client='Sami T', telephone='+21622123456',
                                    adresse='Rue 1', gouvernorat='Tunis', statut='en_attente', **extra)
        for prix, qte in lignes:
            LigneCommande.objects.create(commande=c, produit=self.tomate, nom_produit='Tomate',
                                         prix_unitaire=D(prix), quantite=qte)
        if statut != 'en_attente':          # le statut change après l'ajout des articles, comme en vrai
            c.statut = statut
            c.save()
        return c

    def donnees_commande(self, **extra):
        d = {'nom_client': 'Sami T', 'email': '', 'gouvernorat': 'Tunis', 'adresse': 'Rue 1, Tunis', 'note': '',
             'mode_paiement': 'livraison'}
        d.update(extra)
        return d

    def remplir_panier(self, client, produit=None, quantite=5):
        produit = produit or self.tomate
        client.post(reverse('boutique:panier_ajouter', args=[produit.id]), {'quantite': quantite})


# ----------------------------------------------------------------------------- AVIS
class TestAvis(Base):
    def poster(self, note='5', commentaire='Excellent', client=None):
        c = client or self.client
        return c.post(reverse('boutique:avis_poster', args=[self.tomate.slug]), {'note': note, 'commentaire': commentaire})

    def test_refuse_sans_commande_livree(self):
        self.client.force_login(self.client_sms)
        self.commande(statut='confirmee', lignes=((2, 1),))
        self.poster()
        self.assertEqual(Avis.objects.count(), 0)

    def test_visiteur_non_connecte_redirige(self):
        r = self.poster()
        self.assertEqual(r.status_code, 302)
        self.assertIn('connexion', r.headers['Location'])
        self.assertEqual(Avis.objects.count(), 0)

    def test_publication_modification_et_moyenne(self):
        self.commande(statut='livree', lignes=((2, 1),))
        self.client.force_login(self.client_sms)
        self.poster('4', 'Bon')
        self.tomate.refresh_from_db()
        self.assertEqual((self.tomate.note_moyenne, self.tomate.nb_avis), (D('4.00'), 1))
        self.poster('2', 'Finalement moyen')            # modification, pas de doublon
        self.assertEqual(Avis.objects.count(), 1)
        self.tomate.refresh_from_db()
        self.assertEqual(self.tomate.note_moyenne, D('2.00'))

        autre = self.nouveau_client_sms('+21655111222', 'Leila', 'B')
        self.commande(client=autre, statut='livree', lignes=((2, 1),))
        c2 = self.client_class(); c2.force_login(autre)
        self.poster('5', client=c2)
        self.tomate.refresh_from_db()
        self.assertEqual((self.tomate.note_moyenne, self.tomate.nb_avis), (D('3.50'), 2))

    def test_note_invalide_refusee(self):
        self.commande(statut='livree', lignes=((2, 1),))
        self.client.force_login(self.client_sms)
        for note in ('0', '6', 'abc', ''):
            self.poster(note)
        self.assertEqual(Avis.objects.count(), 0)

    def test_avis_masque_exclu_de_la_moyenne_et_du_site(self):
        self.commande(statut='livree', lignes=((2, 1),))
        self.client.force_login(self.client_sms)
        self.poster('1', 'Nul')
        avis = Avis.objects.get()
        self.client.logout()
        self.client.force_login(self.staff)
        self.client.post(reverse('dashboard:avis_basculer', args=[avis.pk]))
        self.tomate.refresh_from_db()
        self.assertEqual(self.tomate.nb_avis, 0)
        page = self.client_class().get(self.tomate.get_absolute_url()).content.decode()
        self.assertNotIn('Nul', page)

    def test_commentaire_html_echappe_et_identite_protegee(self):
        self.commande(statut='livree', lignes=((2, 1),))
        self.client.force_login(self.client_sms)
        self.poster('5', '<script>alert(1)</script>')
        page = self.client_class().get(self.tomate.get_absolute_url()).content.decode()
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('Sami T.', page)
        self.assertNotIn('22123456', page)          # le téléphone n'est jamais affiché

    def test_suppression_de_son_avis(self):
        self.commande(statut='livree', lignes=((2, 1),))
        self.client.force_login(self.client_sms)
        self.poster()
        self.client.post(reverse('boutique:avis_supprimer', args=[self.tomate.slug]))
        self.assertEqual(Avis.objects.count(), 0)
        self.tomate.refresh_from_db()
        self.assertEqual(self.tomate.nb_avis, 0)

    def test_etoiles_sur_la_carte_produit(self):
        self.commande(statut='livree', lignes=((2, 1),))
        self.client.force_login(self.client_sms)
        self.poster('4')
        self.assertContains(self.client_class().get(reverse('boutique:liste_produits')), '★★★★☆')


# ----------------------------------------------------------------------------- COUPONS
class TestCoupons(Base):
    def coupon(self, **kw):
        d = dict(code='PROMO10', type_remise='pourcentage', valeur=D('10'), utilisations_par_client=1)
        d.update(kw)
        return Coupon.objects.create(**d)

    def test_calcul_pourcentage_montant_et_plafond(self):
        self.assertEqual(self.coupon(code='A').remise_pour(D('33.333')), D('3.333'))
        self.assertEqual(self.coupon(code='B', type_remise='montant', valeur=D('5')).remise_pour(D('20')), D('5.000'))
        self.assertEqual(self.coupon(code='C', type_remise='montant', valeur=D('50')).remise_pour(D('12')), D('12.000'))

    def test_code_en_majuscules(self):
        self.assertEqual(self.coupon(code='  bienvenue ').code, 'BIENVENUE')

    def test_conditions_de_validite(self):
        now = timezone.now()
        self.assertFalse(self.coupon(code='X1', actif=False).verifier(D('50'))[0])
        self.assertFalse(self.coupon(code='X2', date_fin=now - timezone.timedelta(days=1)).verifier(D('50'))[0])
        self.assertFalse(self.coupon(code='X3', date_debut=now + timezone.timedelta(days=1)).verifier(D('50'))[0])
        mini = self.coupon(code='X4', montant_minimum=D('30'))
        self.assertFalse(mini.verifier(D('29.999'))[0])
        self.assertTrue(mini.verifier(D('30'))[0])

    def test_limite_totale_et_commandes_annulees_non_comptees(self):
        c = self.coupon(code='LIM', utilisations_max=1, utilisations_par_client=None)
        cmd = self.commande(coupon=c, code_coupon='LIM')
        self.assertFalse(c.verifier(D('50'))[0])
        cmd.statut = 'annulee'; cmd.save()
        self.assertTrue(c.verifier(D('50'))[0])

    def test_limite_par_client_par_compte_ou_telephone(self):
        c = self.coupon(code='UNE')
        self.commande(coupon=c, code_coupon='UNE')
        self.assertFalse(c.verifier(D('50'), user=self.client_sms)[0])
        autre_compte_meme_tel = User.objects.create_user('autre')
        self.assertFalse(c.verifier(D('50'), user=autre_compte_meme_tel, telephone='+21622123456')[0])
        self.assertTrue(c.verifier(D('50'), user=autre_compte_meme_tel, telephone='+21699000000')[0])

    def test_application_dans_le_panier(self):
        self.coupon()
        self.client.force_login(self.client_sms)
        self.remplir_panier(self.client, quantite=5)                     # 10,000 DT
        self.client.post(reverse('boutique:panier_coupon_appliquer'), {'code': ' promo10 '})
        page = self.client.get(reverse('boutique:panier')).content.decode()
        self.assertIn('- 1,000 DT', page)        # affichage à la française
        self.assertIn('9,000 DT', page)
        self.client.post(reverse('boutique:panier_coupon_retirer'))
        self.assertNotIn('PROMO10', self.client.get(reverse('boutique:panier')).content.decode())

    def test_code_inconnu_ou_invalide_refuse(self):
        self.coupon(montant_minimum=D('100'))
        self.remplir_panier(self.client, quantite=1)
        for code in ('NOPE', 'PROMO10', ''):
            self.client.post(reverse('boutique:panier_coupon_appliquer'), {'code': code})
        self.assertNotIn('coupon_code', self.client.session)

    def test_commande_avec_coupon_total_net_et_usage_unique(self):
        self.coupon()
        self.client.force_login(self.client_sms)
        self.remplir_panier(self.client, quantite=5)
        self.client.post(reverse('boutique:panier_coupon_appliquer'), {'code': 'PROMO10'})
        r = self.client.post(reverse('boutique:commander'), self.donnees_commande())
        self.assertEqual(r.status_code, 302)
        c = Commande.objects.get()
        self.assertEqual((c.sous_total, c.remise_coupon, c.total, c.code_coupon),
                         (D('10.000'), D('1.000'), D('9.000'), 'PROMO10'))
        self.assertNotIn('coupon_code', self.client.session)
        # 2e commande avec le même code : refusée (1 fois par client)
        self.remplir_panier(self.client, quantite=5)
        self.client.post(reverse('boutique:panier_coupon_appliquer'), {'code': 'PROMO10'})
        self.assertNotIn('coupon_code', self.client.session)


# ----------------------------------------------------------------------------- FIDÉLITÉ
class TestFidelite(Base):
    def test_gain_a_la_livraison_une_seule_fois(self):
        c = self.commande(lignes=((2, 12),))                       # 24,000 DT
        self.assertEqual(fidelite.solde(self.client_sms), 0)
        for _ in range(3):                                         # plusieurs enregistrements : un seul crédit
            c.statut = 'livree'; c.save()
        self.assertEqual(fidelite.solde(self.client_sms), 24)
        c.refresh_from_db()
        self.assertEqual(c.points_gagnes, 24)

    def test_gain_calcule_sur_le_total_apres_remises(self):
        c = self.commande(lignes=((2, 10),), remise_coupon=D('5.000'), statut='livree')   # 20 - 5 = 15 DT
        self.assertEqual(fidelite.solde(self.client_sms), 15)

    def test_annulation_apres_livraison_retire_les_points(self):
        c = self.commande(lignes=((2, 10),), statut='livree')
        self.assertEqual(fidelite.solde(self.client_sms), 20)
        c.statut = 'annulee'; c.save(); c.save()
        self.assertEqual(fidelite.solde(self.client_sms), 0)

    def donner_points(self, n, user=None):
        MouvementPoints.objects.create(client=user or self.client_sms, points=n, type='ajustement', motif='test')

    def test_points_utilisables_minimum_et_plafond(self):
        self.donner_points(99)
        self.assertEqual(fidelite.points_utilisables(self.client_sms, D('50'))[0], 0)       # sous le minimum de 100
        self.donner_points(901)                                                              # 1000 points = 20 DT
        points, remise = fidelite.points_utilisables(self.client_sms, D('10'))               # plafond 50 % = 5 DT
        self.assertEqual((points, remise), (250, D('5.000')))
        self.assertEqual(fidelite.points_utilisables(self.client_sms, D('500'))[0], 1000)   # limité par le solde

    def commander_avec_points(self, quantite=10):
        self.client.force_login(self.client_sms)
        self.remplir_panier(self.client, quantite=quantite)
        return self.client.post(reverse('boutique:commander'), self.donnees_commande(utiliser_points='on'))

    def test_utilisation_a_la_commande_et_remboursement_si_annulee(self):
        self.donner_points(500)                                    # 500 points = 10 DT
        self.commander_avec_points(quantite=10)                    # 20 DT, plafond 10 DT -> 500 points
        c = Commande.objects.get()
        self.assertEqual((c.points_utilises, c.remise_points, c.total), (500, D('10.000'), D('10.000')))
        self.assertEqual(fidelite.solde(self.client_sms), 0)
        c.statut = 'annulee'; c.save(); c.save()
        self.assertEqual(fidelite.solde(self.client_sms), 500)

    def test_impossible_de_depenser_plus_que_son_solde(self):
        self.donner_points(120)
        self.commander_avec_points(quantite=10)
        self.assertEqual(Commande.objects.get().points_utilises, 120)
        self.assertEqual(fidelite.solde(self.client_sms), 0)
        # solde épuisé : cocher à nouveau la case ne fait rien et refuse la commande
        self.commander_avec_points(quantite=10)
        self.assertEqual(Commande.objects.count(), 1)
        self.assertEqual(fidelite.solde(self.client_sms), 0)

    def test_ajustement_manuel_dashboard(self):
        self.client.force_login(self.staff)
        url = reverse('dashboard:client_points_ajuster', args=[self.client_sms.pk])
        self.client.post(url, {'points': '50', 'motif': 'Geste commercial'})
        self.assertEqual(fidelite.solde(self.client_sms), 50)
        self.client.post(url, {'points': '-80', 'motif': 'Erreur'})          # refusé : solde négatif
        self.client.post(url, {'points': '10', 'motif': ''})                 # refusé : sans motif
        self.client.post(url, {'points': '0', 'motif': 'x'})                 # refusé : zéro
        self.assertEqual(fidelite.solde(self.client_sms), 50)

    def test_ajustement_reserve_au_personnel(self):
        self.client.force_login(self.client_sms)
        r = self.client.post(reverse('dashboard:client_points_ajuster', args=[self.client_sms.pk]),
                             {'points': '999', 'motif': 'triche'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(fidelite.solde(self.client_sms), 0)


# ----------------------------------------------------------------------------- COMMANDE
class TestCommande(Base):
    def test_commander_exige_la_connexion(self):
        r = self.client.get(reverse('boutique:commander'))
        self.assertEqual(r.status_code, 302)

    def test_commande_liee_au_compte_et_telephone_verifie(self):
        self.client.force_login(self.client_sms)
        self.remplir_panier(self.client, quantite=2)
        data = self.donnees_commande(telephone='55000000')           # tentative d'imposer un autre numéro
        self.client.post(reverse('boutique:commander'), data)
        c = Commande.objects.get()
        self.assertEqual((c.client, c.telephone), (self.client_sms, '+21622123456'))
        self.assertEqual((c.mode_paiement, c.statut_paiement), ('livraison', 'a_la_livraison'))

    def test_client_email_doit_saisir_un_mobile_valide(self):
        u = User.objects.create_user('ali@test.tn', email='ali@test.tn', password='x')
        self.client.force_login(u)
        self.remplir_panier(self.client, quantite=1)
        self.client.post(reverse('boutique:commander'), self.donnees_commande(telephone='123'))
        self.assertEqual(Commande.objects.count(), 0)
        self.client.post(reverse('boutique:commander'), self.donnees_commande(telephone='22 345 678'))
        self.assertEqual(Commande.objects.get().telephone, '+21622345678')

    def test_page_de_confirmation_reservee_au_proprietaire(self):
        c = self.commande()
        url = reverse('boutique:commande_confirmee', args=[c.pk])
        self.assertEqual(self.client_class().get(url).status_code, 302)       # visiteur : connexion
        autre = self.client_class(); autre.force_login(self.nouveau_client_sms('+21655999888'))
        self.assertEqual(autre.get(url).status_code, 404)                      # autre client : introuvable
        proprio = self.client_class(); proprio.force_login(self.client_sms)
        self.assertEqual(proprio.get(url).status_code, 200)

    def test_total_ne_depasse_jamais_zero(self):
        c = self.commande(lignes=((2, 1),), remise_coupon=D('50'))
        self.assertEqual(c.total, D('0'))


# ----------------------------------------------------------------------------- PAIEMENT EN LIGNE
@override_settings(**KONNECT)
class TestKonnect(Base):
    PAYURL = 'https://gateway.sandbox.konnect.network/pay?payment_ref=REF123'

    def commander_en_ligne(self, mode='konnect', quantite=5):
        self.client.force_login(self.client_sms)
        self.remplir_panier(self.client, quantite=quantite)
        return self.client.post(reverse('boutique:commander'), self.donnees_commande(mode_paiement=mode))

    @mock.patch('boutique.paiements.konnect.requests.post')
    def test_creation_du_paiement(self, post):
        post.return_value = Reponse({'payUrl': self.PAYURL, 'paymentRef': 'REF123'})
        r = self.commander_en_ligne()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers['Location'], self.PAYURL)
        c = Commande.objects.get()
        self.assertEqual((c.mode_paiement, c.statut_paiement, c.reference_paiement), ('konnect', 'en_attente', 'REF123'))
        args, kw = post.call_args
        self.assertEqual(args[0], 'https://api.sandbox.konnect.network/api/v2/payments/init-payment')
        self.assertEqual(kw['headers']['x-api-key'], 'cle-test')
        corps = kw['json']
        self.assertEqual((corps['amount'], corps['token'], corps['receiverWalletId']), (10000, 'TND', 'wallet-test'))
        self.assertEqual(corps['orderId'], str(c.pk))
        self.assertEqual(corps['webhook'], 'https://boutique.test/paiement/webhook/konnect/')
        self.assertEqual(corps['phoneNumber'], '22123456')
        self.assertFalse(kw['allow_redirects'])

    @override_settings(KONNECT_ENV='production')
    @mock.patch('boutique.paiements.konnect.requests.post')
    def test_url_de_production(self, post):
        post.return_value = Reponse({'payUrl': 'https://gateway.konnect.network/pay?payment_ref=R', 'paymentRef': 'R'})
        self.commander_en_ligne()
        self.assertEqual(post.call_args[0][0], 'https://api.konnect.network/api/v2/payments/init-payment')

    @mock.patch('boutique.paiements.konnect.requests.post')
    def test_montant_en_millimes_apres_remises(self, post):
        post.return_value = Reponse({'payUrl': self.PAYURL, 'paymentRef': 'REF123'})
        Coupon.objects.create(code='M', type_remise='montant', valeur=D('1.250'), utilisations_par_client=None)
        self.client.force_login(self.client_sms)
        self.remplir_panier(self.client, quantite=5)
        self.client.post(reverse('boutique:panier_coupon_appliquer'), {'code': 'M'})
        self.client.post(reverse('boutique:commander'), self.donnees_commande(mode_paiement='konnect'))
        self.assertEqual(post.call_args[1]['json']['amount'], 8750)

    @mock.patch('boutique.paiements.konnect.requests.post')
    def test_adresse_de_paiement_suspecte_refusee(self, post):
        post.return_value = Reponse({'payUrl': 'https://pirate.example/pay', 'paymentRef': 'REF123'})
        r = self.commander_en_ligne()
        self.assertNotEqual(r.headers['Location'], 'https://pirate.example/pay')
        c = Commande.objects.get()                                  # la commande reste enregistrée
        self.assertEqual(c.statut_paiement, 'en_attente')
        self.assertEqual(c.reference_paiement, '')

    @mock.patch('boutique.paiements.konnect.requests.post')
    def test_fournisseur_indisponible(self, post):
        import requests as lib
        post.side_effect = lib.ConnectionError('boom')
        r = self.commander_en_ligne()
        self.assertEqual(Commande.objects.count(), 1)
        self.assertIn('confirmee', r.headers['Location'])

    def test_mode_en_ligne_masque_si_non_configure(self):
        with override_settings(KONNECT_API_KEY=''):
            self.client.force_login(self.client_sms)
            self.remplir_panier(self.client)
            page = self.client.get(reverse('boutique:commander')).content.decode()
            self.assertNotIn('Konnect', page)
            self.client.post(reverse('boutique:commander'), self.donnees_commande(mode_paiement='konnect'))
            self.assertEqual(Commande.objects.get().mode_paiement, 'livraison')   # retombe sur la livraison

    def en_attente(self, total_millimes=10000):
        return self.commande(lignes=((2, 5),), mode_paiement='konnect', statut_paiement='en_attente',
                             reference_paiement='REF123')

    @mock.patch('boutique.paiements.konnect.requests.get')
    def test_webhook_paiement_confirme_par_le_fournisseur(self, get):
        c = self.en_attente()
        get.return_value = Reponse({'payment': {'status': 'completed', 'amount': 10000}})
        r = self.client.get(reverse('boutique:paiement_webhook_konnect') + '?payment_ref=REF123')
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'paye')
        self.assertIsNotNone(c.paye_le)
        self.assertEqual(get.call_args[0][0], 'https://api.sandbox.konnect.network/api/v2/payments/REF123')
        self.assertEqual(get.call_args[1]['headers']['x-api-key'], 'cle-test')

    @mock.patch('boutique.paiements.konnect.requests.get')
    def test_webhook_falsifie_ne_valide_rien(self, get):
        """Un attaquant appelle le webhook avec une vraie référence, mais Konnect répond « pending »."""
        c = self.en_attente()
        get.return_value = Reponse({'payment': {'status': 'pending', 'amount': 10000}})
        self.client.get(reverse('boutique:paiement_webhook_konnect') + '?payment_ref=REF123&status=completed')
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'en_attente')

    def test_webhook_reference_inconnue(self):
        self.assertEqual(self.client.get(reverse('boutique:paiement_webhook_konnect') + '?payment_ref=ZZZ').status_code, 404)
        self.assertEqual(self.client.get(reverse('boutique:paiement_webhook_konnect')).status_code, 404)

    @mock.patch('boutique.paiements.konnect.requests.get')
    def test_montant_different_non_enregistre(self, get):
        c = self.en_attente()
        get.return_value = Reponse({'payment': {'status': 'completed', 'amount': 1000}})   # 1 DT au lieu de 10
        self.client.get(reverse('boutique:paiement_webhook_konnect') + '?payment_ref=REF123')
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'en_attente')

    @mock.patch('boutique.paiements.konnect.requests.get')
    def test_retour_navigateur_verifie_cote_serveur(self, get):
        c = self.en_attente()
        get.return_value = Reponse({'payment': {'status': 'completed', 'amount': 10000}})
        r = self.client_class().get(reverse('boutique:paiement_retour', args=[c.pk]) + '?status=failed')
        self.assertIn('confirmee', r.headers['Location'])
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'paye')

    @mock.patch('boutique.paiements.konnect.requests.get')
    def test_anti_spam_une_seule_verification(self, get):
        c = self.en_attente()
        get.return_value = Reponse({'payment': {'status': 'pending', 'amount': 10000}})
        for _ in range(5):
            self.client.get(reverse('boutique:paiement_retour', args=[c.pk]))
        self.assertEqual(get.call_count, 1)

    @mock.patch('boutique.paiements.konnect.requests.get')
    def test_paiement_idempotent(self, get):
        c = self.en_attente()
        get.return_value = Reponse({'payment': {'status': 'completed', 'amount': 10000}})
        paiement_service.synchroniser(c.pk, delai_anti_spam=0)
        premier = Commande.objects.get(pk=c.pk).paye_le
        paiement_service.synchroniser(c.pk, delai_anti_spam=0)
        self.assertEqual(get.call_count, 1)                          # déjà payé : plus d'appel
        self.assertEqual(Commande.objects.get(pk=c.pk).paye_le, premier)

    @mock.patch('boutique.paiements.konnect.requests.post')
    @mock.patch('boutique.paiements.konnect.requests.get')
    def test_reessayer_apres_echec_et_paiement_deja_recu(self, get, post):
        c = self.en_attente()
        c.statut_paiement = 'echoue'; c.save()
        self.client.force_login(self.client_sms)
        # 1) rien n'a été payé : on crée un nouveau paiement
        get.return_value = Reponse({'payment': {'status': 'pending', 'amount': 10000}})
        post.return_value = Reponse({'payUrl': self.PAYURL, 'paymentRef': 'NEUF'})
        r = self.client.post(reverse('boutique:paiement_reessayer', args=[c.pk]), {'fournisseur': 'konnect'})
        self.assertEqual(r.headers['Location'], self.PAYURL)
        c.refresh_from_db()
        self.assertEqual((c.reference_paiement, c.statut_paiement), ('NEUF', 'en_attente'))
        # 2) le client avait en fait payé : pas de second paiement
        post.reset_mock(); cache.clear()
        get.return_value = Reponse({'payment': {'status': 'completed', 'amount': 10000}})
        self.client.post(reverse('boutique:paiement_reessayer', args=[c.pk]), {'fournisseur': 'konnect'})
        post.assert_not_called()
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'paye')

    def test_reessayer_reserve_au_proprietaire(self):
        c = self.en_attente()
        autre = self.client_class(); autre.force_login(self.nouveau_client_sms('+21655999888'))
        self.assertEqual(autre.post(reverse('boutique:paiement_reessayer', args=[c.pk])).status_code, 404)
        self.assertEqual(autre.post(reverse('boutique:paiement_livraison', args=[c.pk])).status_code, 404)

    @mock.patch('boutique.paiements.konnect.requests.get')
    def test_passer_a_la_livraison(self, get):
        c = self.en_attente()
        get.return_value = Reponse({'payment': {'status': 'pending', 'amount': 10000}})
        self.client.force_login(self.client_sms)
        self.client.post(reverse('boutique:paiement_livraison', args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual((c.mode_paiement, c.statut_paiement), ('livraison', 'a_la_livraison'))


@override_settings(**FLOUCI)
class TestFlouci(Base):
    def en_attente(self):
        return self.commande(lignes=((2, 5),), mode_paiement='flouci', statut_paiement='en_attente', reference_paiement='FL1')

    @mock.patch('boutique.paiements.flouci.requests.post')
    def test_creation_du_paiement(self, post):
        post.return_value = Reponse({'result': {'success': True, 'payment_id': 'FL1',
                                                'link': 'https://checkout.flouci.com/shop/FL1'}, 'code': 0})
        self.client.force_login(self.client_sms)
        self.remplir_panier(self.client, quantite=5)
        r = self.client.post(reverse('boutique:commander'), self.donnees_commande(mode_paiement='flouci'))
        self.assertEqual(r.headers['Location'], 'https://checkout.flouci.com/shop/FL1')
        args, kw = post.call_args
        self.assertEqual(args[0], 'https://developers.flouci.com/api/v2/generate_payment')
        self.assertEqual(kw['headers']['Authorization'], 'Bearer pub:priv')
        self.assertEqual(kw['json']['amount'], '10000')
        self.assertEqual(kw['json']['success_link'], f"https://boutique.test/paiement/retour/{Commande.objects.get().pk}/")

    @mock.patch('boutique.paiements.flouci.requests.get')
    def test_verification_des_statuts(self, get):
        for statut_flouci, attendu in (('SUCCESS', 'paye'), ('PENDING', 'en_attente'), ('FAILURE', 'echoue'), ('EXPIRED', 'echoue')):
            with self.subTest(statut_flouci):
                cache.clear()
                c = self.en_attente()
                get.return_value = Reponse({'success': True, 'result': {'status': statut_flouci, 'amount': 10000}})
                r = self.client.post(reverse('boutique:paiement_webhook_flouci'), {'payment_id': 'FL1'})
                self.assertEqual(r.status_code, 200)
                c.refresh_from_db()
                self.assertEqual(c.statut_paiement, attendu)
                self.assertEqual(get.call_args[0][0], 'https://developers.flouci.com/api/v2/verify_payment/FL1')
                c.delete()

    @mock.patch('boutique.paiements.flouci.requests.get')
    def test_reponse_sans_success_true_ignoree(self, get):
        c = self.en_attente()
        get.return_value = Reponse({'success': False, 'result': {'status': 'SUCCESS', 'amount': 10000}})
        self.client.post(reverse('boutique:paiement_webhook_flouci'), {'payment_id': 'FL1'})
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'en_attente')

    def test_webhook_json_et_reference_inconnue(self):
        r = self.client.post(reverse('boutique:paiement_webhook_flouci'), '{"payment_id": "INCONNU"}', content_type='application/json')
        self.assertEqual(r.status_code, 404)


# ----------------------------------------------------------------------------- DASHBOARD
@override_settings(**KONNECT)
class TestDashboardCommandes(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def changer(self, c, statut):
        return self.client.post(reverse('dashboard:commande_detail', args=[c.pk]), {'statut': statut}, follow=True)

    def test_commande_en_ligne_impayee_ne_peut_pas_etre_confirmee(self):
        c = self.commande(mode_paiement='konnect', statut_paiement='en_attente')
        self.changer(c, 'confirmee')
        c.refresh_from_db()
        self.assertEqual(c.statut, 'en_attente')

    def test_commande_payee_en_ligne_confirmee_sans_sms(self):
        c = self.commande(mode_paiement='konnect', statut_paiement='paye')
        with mock.patch('comptes.sms.envoyer_sms') as sms:
            self.changer(c, 'confirmee')
            sms.assert_not_called()
        c.refresh_from_db()
        self.assertEqual(c.statut, 'confirmee')
        self.assertTrue(c.validee_par_client)
        self.changer(c, 'livree')
        c.refresh_from_db()
        self.assertEqual(c.statut, 'livree')

    def test_commande_livraison_garde_le_flux_sms(self):
        c = self.commande()
        with mock.patch('comptes.sms.envoyer_sms') as sms:
            self.changer(c, 'confirmee')
            sms.assert_called_once()
        self.changer(c, 'livree')                        # bloqué tant que le client n'a pas saisi le code
        c.refresh_from_db()
        self.assertEqual(c.statut, 'confirmee')
        self.assertFalse(c.validee_par_client)

    def test_marquer_paye_manuellement_puis_rembourse(self):
        c = self.commande(mode_paiement='konnect', statut_paiement='en_attente', reference_paiement='R')
        self.client.post(reverse('dashboard:commande_detail', args=[c.pk]), {'action': 'marquer_paye'})
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'paye')
        self.client.post(reverse('dashboard:commande_detail', args=[c.pk]), {'action': 'marquer_rembourse'})
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'paye')                 # refusé : commande non annulée
        self.changer(c, 'annulee')
        self.client.post(reverse('dashboard:commande_detail', args=[c.pk]), {'action': 'marquer_rembourse'})
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'rembourse')

    def test_pages_dashboard(self):
        c = self.commande(coupon=Coupon.objects.create(code='Z', valeur=D('10')), code_coupon='Z', remise_coupon=D('1'))
        for nom, args in (('commande_detail', [c.pk]), ('commandes_liste', []), ('accueil', []), ('coupons_liste', []),
                          ('avis_liste', []), ('clients_liste', []), ('client_detail', [self.client_sms.pk])):
            with self.subTest(nom):
                self.assertEqual(self.client.get(reverse(f'dashboard:{nom}', args=args)).status_code, 200)


class TestDashboardCoupons(Base):
    def test_cycle_complet_et_acces_reserve(self):
        client_simple = self.client_class(); client_simple.force_login(self.client_sms)
        self.assertEqual(client_simple.get(reverse('dashboard:coupons_liste')).status_code, 302)

        self.client.force_login(self.staff)
        r = self.client.post(reverse('dashboard:coupon_ajouter'), {
            'code': 'bienvenue10', 'description': '', 'type_remise': 'pourcentage', 'valeur': '10',
            'montant_minimum': '0', 'utilisations_par_client': '1', 'actif': 'on'})
        self.assertEqual(r.status_code, 302)
        coupon = Coupon.objects.get()
        self.assertEqual(coupon.code, 'BIENVENUE10')
        # pourcentage > 100 refusé
        r = self.client.post(reverse('dashboard:coupon_modifier', args=[coupon.pk]), {
            'code': 'BIENVENUE10', 'type_remise': 'pourcentage', 'valeur': '150', 'montant_minimum': '0', 'actif': 'on'})
        self.assertEqual(r.status_code, 200)
        coupon.refresh_from_db()
        self.assertEqual(coupon.valeur, D('10'))
        # suppression : la commande garde sa remise
        cmd = self.commande(coupon=coupon, code_coupon='BIENVENUE10', remise_coupon=D('1'))
        self.client.post(reverse('dashboard:coupon_supprimer', args=[coupon.pk]))
        cmd.refresh_from_db()
        self.assertEqual((cmd.code_coupon, cmd.remise_coupon), ('BIENVENUE10', D('1.000')))


class TestRegistreClients(Base):
    def test_total_depense_net_des_remises_et_hors_annulees(self):
        self.commande(lignes=((2, 10),), remise_coupon=D('4'), statut='livree')       # 20 - 4 = 16
        self.commande(lignes=((2, 5),), statut='en_attente')                           # 10
        self.commande(lignes=((2, 50),), statut='annulee')                             # ignorée
        self.client.force_login(self.staff)
        r = self.client.get(reverse('dashboard:clients_liste'))
        client = next(u for u in r.context['page'] if u.pk == self.client_sms.pk)
        self.assertEqual((client.nb_commandes, client.total_depense), (3, D('26.000')))


# ----------------------------------------------------------------------------- PARCOURS COMPLET
@override_settings(**KONNECT)
class TestParcoursComplet(Base):
    """Un client réel de bout en bout : coupon + points, paiement Konnect, livraison, points gagnés, avis."""

    @mock.patch('boutique.paiements.konnect.requests.get')
    @mock.patch('boutique.paiements.konnect.requests.post')
    def test_du_panier_a_l_avis(self, post, get):
        Coupon.objects.create(code='BIENVENUE10', valeur=D('10'), utilisations_par_client=1)
        MouvementPoints.objects.create(client=self.client_sms, points=200, type='ajustement', motif='bonus')   # 4 DT

        # 1. Panier de 20 DT, coupon -10 % (-2 DT), 200 points (-4 DT) -> 14 DT à payer en ligne
        self.client.force_login(self.client_sms)
        self.remplir_panier(self.client, quantite=10)
        self.client.post(reverse('boutique:panier_coupon_appliquer'), {'code': 'bienvenue10'})
        post.return_value = Reponse({'payUrl': 'https://gateway.konnect.network/pay?payment_ref=R9', 'paymentRef': 'R9'})
        self.client.post(reverse('boutique:commander'),
                         self.donnees_commande(mode_paiement='konnect', utiliser_points='on'))
        c = Commande.objects.get()
        self.assertEqual((c.sous_total, c.remise_coupon, c.remise_points, c.total),
                         (D('20.000'), D('2.000'), D('4.000'), D('14.000')))
        self.assertEqual(post.call_args[1]['json']['amount'], 14000)
        self.assertEqual(fidelite.solde(self.client_sms), 0)

        # 2. Le client paie : Konnect confirme
        get.return_value = Reponse({'payment': {'status': 'completed', 'amount': 14000}})
        self.client.get(reverse('boutique:paiement_webhook_konnect') + '?payment_ref=R9')
        c.refresh_from_db()
        self.assertEqual(c.statut_paiement, 'paye')

        # 3. L'admin confirme puis livre (aucun SMS requis)
        admin = self.client_class(); admin.force_login(self.staff)
        for statut in ('confirmee', 'en_livraison', 'livree'):
            admin.post(reverse('dashboard:commande_detail', args=[c.pk]), {'statut': statut})
        c.refresh_from_db()
        self.assertEqual(c.statut, 'livree')
        self.assertEqual(c.points_gagnes, 14)
        self.assertEqual(fidelite.solde(self.client_sms), 14)

        # 4. Le client donne son avis
        self.client.post(reverse('boutique:avis_poster', args=[self.tomate.slug]), {'note': '5', 'commentaire': 'Frais !'})
        self.tomate.refresh_from_db()
        self.assertEqual((self.tomate.note_moyenne, self.tomate.nb_avis), (D('5.00'), 1))

    def test_connexion_admin_avec_plusieurs_backends(self):
        c = self.client_class()
        r = c.post(reverse('dashboard:login'), {'username': 'admin', 'password': 'x'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(c.get(reverse('dashboard:accueil')).status_code, 200)


# ----------------------------------------------------------------------------- MODE TEST SMS + ICÔNES
class TestModeTestSms(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def confirmer(self, c):
        return self.client.post(reverse('dashboard:commande_detail', args=[c.pk]), {'statut': 'confirmee'}, follow=True)

    @override_settings(DEBUG=True, SMS_BACKEND='console')
    def test_le_code_est_visible_dans_le_dashboard_en_mode_test(self):
        c = self.commande()
        page = self.confirmer(c).content.decode()
        self.assertIn('Mode test', page)
        self.assertRegex(page, r'Code de validation: \d{6}')          # le code du SMS est affiché

    @override_settings(DEBUG=True, SMS_BACKEND='console')
    def test_pas_de_code_affiche_une_fois_la_commande_validee(self):
        c = self.commande()
        self.confirmer(c)
        Commande.objects.filter(pk=c.pk).update(validee_par_client=True)
        self.assertNotIn('Mode test', self.client.get(reverse('dashboard:commande_detail', args=[c.pk])).content.decode())

    @override_settings(DEBUG=False, SMS_BACKEND='console')
    def test_jamais_affiche_hors_debug(self):
        c = self.commande()
        page = self.confirmer(c).content.decode()
        self.assertNotIn('Mode test', page)
        self.assertNotRegex(page, r'Code de validation: \d{6}')

    @override_settings(DEBUG=True, SMS_BACKEND='locmem')
    def test_jamais_affiche_avec_un_vrai_backend(self):
        c = self.commande()
        self.assertNotIn('Mode test', self.confirmer(c).content.decode())

    @override_settings(DEBUG=True, SMS_BACKEND='console')
    def test_avertissement_cote_client_sans_afficher_le_code(self):
        c = self.commande()
        self.confirmer(c)
        client = self.client_class(); client.force_login(self.client_sms)
        page = client.get(reverse('comptes:valider_commande', args=[c.pk])).content.decode()
        self.assertIn('Mode test', page)
        self.assertNotRegex(page, r'\b\d{6}\b')


class TestIcones(Base):
    def test_coche_et_ticket_utilises_et_fichiers_presents(self):
        from django.contrib.staticfiles import finders
        for f in ('img/icone-valide.svg', 'img/coupon.svg', 'img/coupon-mini.svg'):
            self.assertIsNotNone(finders.find(f), f)
        c = self.commande(statut='livree', validee_par_client=True)
        proprio = self.client_class(); proprio.force_login(self.client_sms)
        page = proprio.get(reverse('boutique:commande_confirmee', args=[c.pk])).content.decode()
        self.assertNotIn('✅', page)
        liste = proprio.get(reverse('comptes:mes_commandes')).content.decode()
        self.assertIn('icone-valide.svg', liste)
        self.assertNotIn('✓', liste)
        self.client.force_login(self.staff)
        dash = self.client.get(reverse('dashboard:coupons_liste')).content.decode()
        self.assertIn('coupon-mini.svg', dash)
        self.assertNotIn('🏷️', dash)


# ----------------------------------------------------------------------------- CACHE DU CATALOGUE
from django.db import connection
from django.test.utils import CaptureQueriesContext


class TestCacheCatalogue(Base):
    def setUp(self):
        super().setUp()
        from . import catalogue
        self.catalogue = catalogue
        cache.clear()

    def nb_requetes(self, url, client=None):
        with CaptureQueriesContext(connection) as ctx:
            r = (client or self.client).get(url)
        self.assertEqual(r.status_code, 200)
        return len(ctx), r.content.decode()

    def test_les_pages_catalogue_font_moins_de_requetes_la_deuxieme_fois(self):
        for url in (reverse('boutique:accueil'), reverse('boutique:liste_produits'),
                    reverse('boutique:categorie', args=['legumes']), reverse('boutique:liste_produits') + '?type=legume'):
            with self.subTest(url):
                cache.clear()
                premiere, html1 = self.nb_requetes(url)
                deuxieme, html2 = self.nb_requetes(url)
                self.assertLess(deuxieme, premiere)
                self.assertLessEqual(deuxieme, 3)         # session / utilisateur seulement
                self.assertIn('Tomate', html2) if 'accueil' not in url else None

    def test_un_produit_modifie_apparait_aussitot(self):
        url = reverse('boutique:liste_produits')
        self.assertIn('Tomate', self.nb_requetes(url)[1])
        self.tomate.prix = D('9.990'); self.tomate.save()
        self.assertIn('9,990', self.nb_requetes(url)[1])
        Produit.objects.create(categorie=self.cat, nom='Poivron', slug='poivron', prix=D('3'), stock=5)
        self.assertIn('Poivron', self.nb_requetes(url)[1])
        self.oignon.delete()
        self.assertNotIn('Oignon', self.nb_requetes(url)[1])
        self.tomate.disponible = False; self.tomate.save()
        self.assertNotIn('Tomate', self.nb_requetes(url)[1])

    def test_categories_et_menu_a_jour(self):
        self.nb_requetes(reverse('boutique:accueil'))
        Categorie.objects.create(nom='Fruits', slug='fruits', type_produit='fruit')
        html = self.nb_requetes(reverse('boutique:accueil'))[1]
        self.assertIn('Fruits', html)
        self.assertIn('type=fruit', html)                          # menu « Tous les produits »

    def test_moyens_de_paiement_a_jour(self):
        from .models import MoyenPaiement
        from django.core.files.uploadedfile import SimpleUploadedFile
        logo = SimpleUploadedFile('l.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        m = MoyenPaiement.objects.create(nom='Visa', logo=logo, actif=True)
        self.assertIn('alt="Visa"', self.nb_requetes(reverse('boutique:accueil'))[1])
        m.actif = False; m.save()
        self.assertNotIn('alt="Visa"', self.nb_requetes(reverse('boutique:accueil'))[1])

    def test_note_moyenne_mise_a_jour_apres_un_avis(self):
        url = reverse('boutique:liste_produits')
        self.assertNotIn('★', self.nb_requetes(url)[1])
        self.commande(statut='livree', lignes=((2, 1),))
        self.client.force_login(self.client_sms)
        self.client.post(reverse('boutique:avis_poster', args=[self.tomate.slug]), {'note': '5', 'commentaire': ''})
        self.assertIn('★★★★★', self.nb_requetes(url)[1])

    def test_recherche_jamais_en_cache(self):
        url = reverse('boutique:liste_produits') + '?q=tom'
        self.assertIn('Tomate', self.nb_requetes(url)[1])
        Produit.objects.filter(pk=self.tomate.pk).update(nom='Pasteque')          # modification « directe » : sans signal
        self.assertNotIn('Tomate', self.nb_requetes(url)[1])

    def test_categorie_inconnue_donne_404(self):
        self.assertEqual(self.client.get(reverse('boutique:categorie', args=['nope'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('boutique:liste_produits') + '?categorie=nope').status_code, 404)

    def test_aucune_donnee_de_visiteur_dans_le_cache(self):
        """Le jeton CSRF et l'état de connexion de l'un ne doivent jamais se retrouver chez l'autre."""
        url = reverse('boutique:accueil')
        anonyme = self.client_class()
        connecte = self.client_class(); connecte.force_login(self.client_sms)
        h_anonyme = anonyme.get(url).content.decode()               # remplit le cache
        h_connecte = connecte.get(url).content.decode()             # lit le cache
        import re
        jeton = lambda h: set(re.findall(r'name="csrfmiddlewaretoken" value="([^"]+)"', h))
        self.assertTrue(jeton(h_anonyme))
        self.assertFalse(jeton(h_anonyme) & jeton(h_connecte))
        self.assertIn('Mon compte', h_connecte)
        self.assertNotIn('Mon compte', h_anonyme)
        autre = self.client_class()
        self.assertFalse(jeton(autre.get(url).content.decode()) & jeton(h_connecte))

    def test_version_perdue_reste_coherente(self):
        self.nb_requetes(reverse('boutique:liste_produits'))
        cache.delete(self.catalogue.CLE_VERSION)                    # Redis vidé / clé évincée
        self.tomate.prix = D('7.000'); self.tomate.save()
        self.assertIn('7,000', self.nb_requetes(reverse('boutique:liste_produits'))[1])


class TestCacheRedisTolerant(TestCase):
    """Redis arrêté : le site continue de fonctionner, sans cache."""

    def setUp(self):
        from .cache_backend import RedisCacheTolerant
        self.cache = RedisCacheTolerant('redis://127.0.0.1:1/0', {'OPTIONS': {'socket_connect_timeout': 1}})

    def test_aucune_exception_et_valeurs_neutres(self):
        c = self.cache
        self.assertIsNone(c.get('a'))
        self.assertEqual(c.get('a', 'defaut'), 'defaut')
        self.assertIsNone(c.set('a', 1))
        self.assertTrue(c.add('a', 1))                 # le verrou anti-spam ne bloque jamais quand Redis est arrêté
        self.assertFalse(c.delete('a'))
        self.assertEqual(c.get_many(['a', 'b']), {})
        self.assertFalse(c.has_key('a'))
        self.assertIsNone(c.incr('a'))
        self.assertEqual(c.get_or_set('x', lambda: 5), 5)

    def test_le_catalogue_fonctionne_sans_redis(self):
        with mock.patch('boutique.catalogue.cache', self.cache):
            from . import catalogue
            cat = Categorie.objects.create(nom='L', slug='l', type_produit='legume')
            Produit.objects.create(categorie=cat, nom='Tomate', slug='tomate', prix=D('2'), stock=1)
            self.assertEqual([p.nom for p in catalogue.produits()], ['Tomate'])
            catalogue.invalider()                                            # ne lève rien non plus


class TestSante(TestCase):
    def test_sante_ok(self):
        r = self.client.get(reverse('sante'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'base': 'ok', 'cache': 'ok', 'file_attente': 'direct'})
        self.assertIn('no-store', r.headers['Cache-Control'])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_sante_signale_une_file_injoignable(self):
        from marche_tn import celery_app
        with mock.patch.object(celery_app, 'connection_for_write', side_effect=OSError('refusé')):
            r = self.client.get(reverse('sante'))
        self.assertEqual((r.status_code, r.json()['file_attente']), (503, 'ko'))
