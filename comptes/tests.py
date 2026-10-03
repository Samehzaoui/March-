import re
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from boutique.models import Categorie, Commande, LigneCommande, Produit
from . import services, sms
from .models import CodeSMS, ProfilClient

User = get_user_model()
TEL = '+21622123456'


def dernier_code():
    return re.search(r'\b(\d{6})\b', sms.outbox[-1]['message']).group(1)


def mauvais_code(bon):
    return '000000' if bon != '000000' else '111111'


class TelephoneTests(TestCase):
    def test_numeros_valides(self):
        for brut in ['22123456', '22 123 456', '+216 22 123 456', '0021622123456', '21622123456', '22-123-456']:
            self.assertEqual(services.normaliser_telephone(brut), TEL, brut)

    def test_numeros_invalides(self):
        for brut in ['', None, '1234', '71123456', '12345678', '+33612345678', 'abcdefgh']:
            self.assertIsNone(services.normaliser_telephone(brut), brut)


class BaseTest(TestCase):
    def setUp(self):
        sms.outbox.clear()
        cat = Categorie.objects.create(nom='Legumes', slug='legumes')
        self.produit = Produit.objects.create(categorie=cat, nom='Tomate', prix=Decimal('1.500'), stock=50)
        self.user = User.objects.create_user('tel21622123456')
        ProfilClient.objects.create(user=self.user, telephone=TEL)
        self.autre = User.objects.create_user('tel21655999888')
        ProfilClient.objects.create(user=self.autre, telephone='+21655999888')
        self.staff = User.objects.create_user('admin_test', password='x', is_staff=True)

    def creer_commande(self, statut='en_attente'):
        c = Commande.objects.create(nom_client='Ali', telephone=TEL, adresse='Rue 1',
                                    gouvernorat='Tunis', client=self.user, statut=statut)
        LigneCommande.objects.create(commande=c, produit=self.produit, nom_produit='Tomate',
                                     prix_unitaire=Decimal('1.500'), quantite=2)
        return c


@override_settings(SMS_BACKEND='locmem')
class ConnexionSMSTests(BaseTest):
    def test_nouveau_client_cree_puis_connecte(self):
        c = Client()
        r = c.post(reverse('comptes:connexion'), {'telephone': '55 999 111'})
        self.assertRedirects(r, reverse('comptes:verifier'))
        self.assertEqual(len(sms.outbox), 1)
        self.assertEqual(sms.outbox[0]['telephone'], '+21655999111')
        r = c.post(reverse('comptes:verifier'), {'code': dernier_code()})
        self.assertRedirects(r, reverse('boutique:accueil'))
        self.assertIn('_auth_user_id', c.session)
        self.assertTrue(ProfilClient.objects.filter(telephone='+21655999111').exists())

    def test_client_existant_reutilise_son_compte(self):
        c = Client()
        nb = User.objects.count()
        c.post(reverse('comptes:connexion'), {'telephone': TEL})
        c.post(reverse('comptes:verifier'), {'code': dernier_code()})
        self.assertEqual(int(c.session['_auth_user_id']), self.user.pk)
        self.assertEqual(User.objects.count(), nb)

    def test_numero_invalide_aucun_sms(self):
        r = Client().post(reverse('comptes:connexion'), {'telephone': '71123456'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sms.outbox, [])

    def test_cinq_essais_maximum(self):
        c = Client()
        c.post(reverse('comptes:connexion'), {'telephone': TEL})
        bon = dernier_code()
        for _ in range(5):
            c.post(reverse('comptes:verifier'), {'code': mauvais_code(bon)})
        c.post(reverse('comptes:verifier'), {'code': bon})
        self.assertNotIn('_auth_user_id', c.session)

    def test_code_expire(self):
        c = Client()
        c.post(reverse('comptes:connexion'), {'telephone': TEL})
        CodeSMS.objects.update(expire_le=timezone.now() - timedelta(seconds=1))
        c.post(reverse('comptes:verifier'), {'code': dernier_code()})
        self.assertNotIn('_auth_user_id', c.session)

    def test_code_a_usage_unique(self):
        c = Client()
        c.post(reverse('comptes:connexion'), {'telephone': TEL})
        code = dernier_code()
        c.post(reverse('comptes:verifier'), {'code': code})
        c.post(reverse('comptes:deconnexion'))
        self.assertNotIn('_auth_user_id', c.session)
        c.post(reverse('comptes:connexion'), {'telephone': TEL})          # délai de renvoi : pas de nouveau SMS
        c.post(reverse('comptes:verifier'), {'code': code})
        self.assertNotIn('_auth_user_id', c.session)

    def test_delai_entre_deux_envois(self):
        c = Client()
        c.post(reverse('comptes:connexion'), {'telephone': TEL})
        r = c.post(reverse('comptes:connexion'), {'telephone': TEL})
        self.assertRedirects(r, reverse('comptes:verifier'))
        self.assertEqual(len(sms.outbox), 1)

    def test_plafond_par_heure(self):
        for _ in range(5):
            CodeSMS.objects.create(telephone=TEL, objet='connexion', code_hash='x', utilise=True,
                                   expire_le=timezone.now() + timedelta(minutes=5))
        CodeSMS.objects.update(cree_le=timezone.now() - timedelta(minutes=30))
        resultat = services.envoyer_code_connexion(TEL)
        self.assertFalse(resultat.ok)
        self.assertFalse(resultat.attente)
        self.assertEqual(sms.outbox, [])

    def test_echec_fournisseur_ne_laisse_pas_de_code(self):
        with mock.patch('comptes.services.envoyer_sms', side_effect=sms.SMSError('panne')):
            resultat = services.envoyer_code_connexion(TEL)
        self.assertFalse(resultat.ok)
        self.assertEqual(CodeSMS.objects.count(), 0)

    def test_redirection_externe_refusee(self):
        c = Client()
        c.post(reverse('comptes:connexion') + '?next=https://evil.example/', {'telephone': TEL, 'next': 'https://evil.example/'})
        r = c.post(reverse('comptes:verifier'), {'code': dernier_code()})
        self.assertRedirects(r, reverse('boutique:accueil'))


@override_settings(SMS_BACKEND='locmem')
class CommandeClientTests(BaseTest):
    def test_commander_exige_connexion(self):
        r = self.client.get(reverse('boutique:commander'))
        self.assertRedirects(r, f"{reverse('comptes:connexion')}?next={reverse('boutique:commander')}",
                             fetch_redirect_response=False)

    def test_commande_liee_au_numero_verifie(self):
        self.client.force_login(self.user)
        self.client.post(reverse('boutique:panier_ajouter', args=[self.produit.id]), {'quantite': 2})
        r = self.client.post(reverse('boutique:commander'), {
            'nom_client': 'Ali', 'gouvernorat': 'Tunis', 'adresse': 'Rue 1', 'email': '', 'note': '',
            'telephone': '+21600000000',      # ignoré : seul le numéro vérifié compte
        })
        commande = Commande.objects.get()
        self.assertEqual(commande.client, self.user)
        self.assertEqual(commande.telephone, TEL)
        self.assertRedirects(r, reverse('boutique:commande_confirmee', args=[commande.pk]))

    def test_page_confirmation_privee(self):
        commande = self.creer_commande()
        self.client.force_login(self.autre)
        self.assertEqual(self.client.get(reverse('boutique:commande_confirmee', args=[commande.pk])).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('boutique:commande_confirmee', args=[commande.pk])).status_code, 200)


@override_settings(SMS_BACKEND='locmem')
class ValidationCommandeTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.admin = Client()
        self.admin.force_login(self.staff)

    def detail(self, commande):
        return reverse('dashboard:commande_detail', args=[commande.pk])

    def test_confirmation_admin_envoie_le_code(self):
        c = self.creer_commande()
        self.admin.post(self.detail(c), {'statut': 'confirmee'})
        c.refresh_from_db()
        self.assertEqual(c.statut, 'confirmee')
        self.assertEqual(len(sms.outbox), 1)
        self.assertEqual(sms.outbox[0]['telephone'], TEL)
        self.assertIn(f'#{c.pk}', sms.outbox[0]['message'])

    def test_livraison_bloquee_avant_validation(self):
        c = self.creer_commande('confirmee')
        self.admin.post(self.detail(c), {'statut': 'en_livraison'})
        c.refresh_from_db()
        self.assertEqual(c.statut, 'confirmee')

    def test_annulation_toujours_possible(self):
        c = self.creer_commande('confirmee')
        self.admin.post(self.detail(c), {'statut': 'annulee'})
        c.refresh_from_db()
        self.assertEqual(c.statut, 'annulee')

    def test_client_valide_puis_livraison_possible(self):
        c = self.creer_commande()
        self.admin.post(self.detail(c), {'statut': 'confirmee'})
        code = dernier_code()
        self.client.force_login(self.user)
        url = reverse('comptes:valider_commande', args=[c.pk])
        self.client.post(url, {'code': mauvais_code(code)})
        c.refresh_from_db()
        self.assertFalse(c.validee_par_client)
        self.client.post(url, {'code': code})
        c.refresh_from_db()
        self.assertTrue(c.validee_par_client)
        self.assertIsNotNone(c.date_validation_client)
        self.admin.post(self.detail(c), {'statut': 'en_livraison'})
        c.refresh_from_db()
        self.assertEqual(c.statut, 'en_livraison')

    def test_un_autre_client_ne_peut_pas_valider(self):
        c = self.creer_commande('confirmee')
        self.client.force_login(self.autre)
        self.assertEqual(self.client.get(reverse('comptes:valider_commande', args=[c.pk])).status_code, 404)

    def test_pas_de_validation_tant_que_non_confirmee(self):
        c = self.creer_commande('en_attente')
        self.client.force_login(self.user)
        r = self.client.get(reverse('comptes:valider_commande', args=[c.pk]))
        self.assertRedirects(r, reverse('comptes:mes_commandes'))

    def test_renvoi_respecte_le_delai(self):
        c = self.creer_commande()
        self.admin.post(self.detail(c), {'statut': 'confirmee'})
        self.admin.post(self.detail(c), {'action': 'renvoyer_code'})
        self.assertEqual(len(sms.outbox), 1)

    def test_pages_affichees_sans_erreur(self):
        c = self.creer_commande('confirmee')
        self.admin.post(self.detail(c), {'action': 'renvoyer_code'})
        self.assertEqual(self.admin.get(self.detail(c)).status_code, 200)
        self.assertEqual(self.admin.get(reverse('dashboard:commandes_liste')).status_code, 200)
        self.assertEqual(self.admin.get(reverse('dashboard:accueil')).status_code, 200)
        self.client.force_login(self.user)
        for nom, args in [('comptes:mes_commandes', []), ('comptes:valider_commande', [c.pk]),
                          ('boutique:accueil', []), ('boutique:liste_produits', [])]:
            self.assertEqual(self.client.get(reverse(nom, args=args)).status_code, 200, nom)
        self.assertContains(self.client.get(reverse('boutique:accueil')), 'saisissez le code reçu par SMS')
        anonyme = Client()
        self.assertEqual(anonyme.get(reverse('comptes:connexion')).status_code, 200)
