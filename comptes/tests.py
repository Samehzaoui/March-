import json
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
        with mock.patch('comptes.sms.envoyer_sms', side_effect=sms.SMSError('panne')):
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


# ----------------------------------------------------------------------------- TÂCHES DE FOND (SMS + EMAILS)
from django.core import mail
from django.core.cache import cache as cache_django
from django.test import override_settings


@override_settings(CELERY_TASK_ALWAYS_EAGER=False, SMS_BACKEND='locmem')
class SMSEnArrierePlanTests(TestCase):
    """File d'attente active : le SMS est planifié, jamais envoyé pendant la requête."""
    TEL = '+21622123456'

    def setUp(self):
        sms.outbox.clear()
        cache_django.clear()

    def test_le_sms_est_planifie_pas_envoye_dans_la_requete(self):
        with mock.patch('comptes.tasks.envoyer_sms_tache.apply_async') as planifier:
            resultat = services.envoyer_code_connexion(self.TEL)
        self.assertTrue(resultat.ok)
        self.assertEqual(sms.outbox, [])                                    # rien envoyé en direct
        args = planifier.call_args[1]['args']
        self.assertEqual(args[0], self.TEL)
        self.assertRegex(args[1], r'code de connexion \d{6}')
        entree = CodeSMS.objects.get(telephone=self.TEL)
        self.assertEqual(args[2], entree.pk)
        self.assertFalse(planifier.call_args[1]['retry'])

    def test_file_injoignable_envoi_direct_de_secours(self):
        with mock.patch('comptes.tasks.envoyer_sms_tache.apply_async', side_effect=OSError('redis arrêté')):
            resultat = services.envoyer_code_connexion(self.TEL)
        self.assertTrue(resultat.ok)
        self.assertEqual(len(sms.outbox), 1)                                # le client reçoit quand même son code
        self.assertTrue(CodeSMS.objects.filter(telephone=self.TEL).exists())

    def test_file_et_fournisseur_en_panne_le_client_est_prevenu(self):
        with mock.patch('comptes.tasks.envoyer_sms_tache.apply_async', side_effect=OSError('redis arrêté')), \
             mock.patch('comptes.sms.envoyer_sms', side_effect=sms.SMSError('panne')):
            resultat = services.envoyer_code_connexion(self.TEL)
        self.assertFalse(resultat.ok)
        self.assertFalse(CodeSMS.objects.filter(telephone=self.TEL).exists())

    def test_ancien_code_invalide_et_nouveau_utilisable(self):
        with mock.patch('comptes.tasks.envoyer_sms_tache.apply_async') as planifier:
            services.envoyer_code_connexion(self.TEL)
            CodeSMS.objects.update(cree_le=timezone.now() - timedelta(minutes=2))
            services.envoyer_code_connexion(self.TEL)
        self.assertEqual(CodeSMS.objects.filter(telephone=self.TEL, utilise=False).count(), 1)
        message = planifier.call_args[1]['args'][1]
        code = re.search(r'(\d{6})', message).group(1)
        self.assertEqual(services.verifier_code_connexion(self.TEL, code), (True, None))

    def test_la_tache_envoie_le_sms(self):
        from comptes import tasks
        tasks.envoyer_sms_tache.apply(args=(self.TEL, 'Bonjour', None))
        self.assertEqual(sms.outbox, [{'telephone': self.TEL, 'message': 'Bonjour'}])

    def test_la_tache_reessaie_puis_supprime_le_code_non_livre(self):
        from comptes import tasks
        entree = CodeSMS.objects.create(telephone=self.TEL, objet=CodeSMS.OBJET_CONNEXION, code_hash='x',
                                        expire_le=timezone.now() + timedelta(minutes=5))
        with mock.patch('comptes.tasks.envoyer_sms', side_effect=sms.SMSError('panne')) as envoi:
            resultat = tasks.envoyer_sms_tache.apply(args=(self.TEL, 'msg', entree.pk), throw=False)
        self.assertTrue(resultat.failed())
        self.assertIsInstance(resultat.result, sms.SMSError)
        self.assertEqual(envoi.call_count, 5)                               # 1 essai + 4 nouveaux essais
        self.assertFalse(CodeSMS.objects.filter(pk=entree.pk).exists())     # le client peut en redemander un

    def test_echec_definitif_ne_touche_pas_un_code_deja_utilise(self):
        from comptes import tasks
        entree = CodeSMS.objects.create(telephone=self.TEL, objet=CodeSMS.OBJET_CONNEXION, code_hash='x', utilise=True,
                                        expire_le=timezone.now() + timedelta(minutes=5))
        tasks.TacheSMS().on_failure(sms.SMSError('x'), 'id', (self.TEL, 'm', entree.pk), {}, None)
        self.assertTrue(CodeSMS.objects.filter(pk=entree.pk).exists())


@override_settings(CELERY_TASK_ALWAYS_EAGER=False, EMAIL_BACKEND='comptes.emailing.EmailAsyncBackend',
                   EMAIL_BACKEND_REEL='django.core.mail.backends.locmem.EmailBackend')
class EmailEnArrierePlanTests(TestCase):
    def message(self, **kw):
        m = mail.EmailMultiAlternatives('Sujet é', 'Texte', 'shop@test.tn', ['a@test.tn', 'b@test.tn'],
                                        cc=['c@test.tn'], bcc=['d@test.tn'], reply_to=['r@test.tn'],
                                        headers={'X-Test': '1'}, **kw)
        m.attach_alternative('<p>Bonjour <b>Sami</b></p>', 'text/html')
        return m

    def test_email_planifie_puis_envoye_identique(self):
        from comptes import tasks
        with mock.patch('comptes.tasks.envoyer_email_tache.apply_async') as planifier:
            n = self.message().send()
        self.assertEqual(n, 1)
        self.assertEqual(mail.outbox, [])                                   # rien envoyé pendant la requête
        donnees = planifier.call_args[1]['args'][0]
        json.dumps(donnees)                                                 # sérialisable par Celery
        tasks.envoyer_email_tache.apply(args=(donnees,))                    # ce que fait le worker
        envoye = mail.outbox[0]
        self.assertEqual((envoye.subject, envoye.body, envoye.from_email), ('Sujet é', 'Texte', 'shop@test.tn'))
        self.assertEqual((envoye.to, envoye.cc, envoye.bcc, envoye.reply_to),
                         (['a@test.tn', 'b@test.tn'], ['c@test.tn'], ['d@test.tn'], ['r@test.tn']))
        self.assertEqual(envoye.extra_headers['X-Test'], '1')
        self.assertEqual(envoye.alternatives[0][1], 'text/html')
        self.assertIn('Sami', envoye.alternatives[0][0])

    def test_file_injoignable_envoi_direct(self):
        with mock.patch('comptes.tasks.envoyer_email_tache.apply_async', side_effect=OSError('redis arrêté')):
            n = self.message().send()
        self.assertEqual((n, len(mail.outbox)), (1, 1))

    def test_piece_jointe_envoyee_directement(self):
        m = self.message()
        m.attach('facture.txt', 'contenu', 'text/plain')
        with mock.patch('comptes.tasks.envoyer_email_tache.apply_async') as planifier:
            m.send()
        planifier.assert_not_called()
        self.assertEqual(len(mail.outbox), 1)

    def test_inscription_allauth_passe_par_la_file(self):
        with mock.patch('comptes.tasks.envoyer_email_tache.apply_async') as planifier:
            r = self.client.post('/accounts/signup/', {'email': 'neuf@test.tn', 'password1': 'Zr7!kLm92xQ', 'password2': 'Zr7!kLm92xQ'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(planifier.call_count, 1)
        self.assertIn('neuf@test.tn', planifier.call_args[1]['args'][0]['to'])
        self.assertEqual(mail.outbox, [])
