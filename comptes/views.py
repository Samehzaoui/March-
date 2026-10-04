from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from boutique.models import Commande
from . import services
from .models import ProfilClient

User = get_user_model()
SESSION_TEL = 'otp_telephone'
SESSION_NEXT = 'otp_next'


def _url_sure(request, url):
    """N'accepte que les redirections vers ce site (évite les open redirects)."""
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return url
    return ''


def _obtenir_ou_creer_client(telephone):
    try:
        return ProfilClient.objects.select_related('user').get(telephone=telephone).user
    except ProfilClient.DoesNotExist:
        pass
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=f"tel{telephone.lstrip('+')}")  # sans mot de passe
            ProfilClient.objects.create(user=user, telephone=telephone)
            return user
    except IntegrityError:
        return ProfilClient.objects.select_related('user').get(telephone=telephone).user


def _masquer(telephone):
    return f"+216 ** *** {telephone[-3:]}"


def connexion(request):
    suivant = _url_sure(request, request.GET.get('next') or request.POST.get('next'))
    if request.user.is_authenticated and hasattr(request.user, 'profil'):
        return redirect(suivant or 'comptes:mes_commandes')

    erreur = None
    if request.method == 'POST':
        telephone = services.normaliser_telephone(request.POST.get('telephone'))
        if not telephone:
            erreur = "Numéro invalide. Entrez un numéro mobile tunisien à 8 chiffres (ex : 22 123 456)."
        else:
            resultat = services.envoyer_code_connexion(telephone)
            if resultat.ok or resultat.attente:
                request.session[SESSION_TEL] = telephone
                request.session[SESSION_NEXT] = suivant
                if resultat.attente:
                    messages.info(request, resultat.message)
                return redirect('comptes:verifier')
            erreur = resultat.message
    return render(request, 'comptes/connexion.html', {
        'erreur': erreur, 'next': suivant, 'telephone_saisi': request.POST.get('telephone', ''),
    })


def verifier(request):
    telephone = request.session.get(SESSION_TEL)
    if not telephone:
        return redirect('comptes:connexion')

    erreur = None
    if request.method == 'POST':
        ok, erreur = services.verifier_code_connexion(telephone, request.POST.get('code'))
        if ok:
            user = _obtenir_ou_creer_client(telephone)
            if not user.is_active:
                erreur = "Ce compte est désactivé. Contactez 9offty."
            else:
                suivant = _url_sure(request, request.session.get(SESSION_NEXT))
                panier = request.session.get('panier')      # conservé même si une autre session était ouverte
                login(request, user)
                if panier:
                    request.session['panier'] = panier
                request.session.pop(SESSION_TEL, None)
                request.session.pop(SESSION_NEXT, None)
                messages.success(request, "Connexion réussie. Bienvenue chez 9offty !")
                return redirect(suivant or 'boutique:accueil')
    return render(request, 'comptes/verifier.html', {
        'telephone_masque': _masquer(telephone), 'erreur': erreur,
    })


@require_POST
def renvoyer_code_connexion(request):
    telephone = request.session.get(SESSION_TEL)
    if not telephone:
        return redirect('comptes:connexion')
    resultat = services.envoyer_code_connexion(telephone)
    if resultat.ok:
        messages.success(request, "Un nouveau code vient d'être envoyé par SMS.")
    else:
        messages.warning(request, resultat.message)
    return redirect('comptes:verifier')


@require_POST
def deconnexion(request):
    logout(request)
    messages.success(request, "Vous êtes déconnecté.")
    return redirect('boutique:accueil')


@login_required(login_url='comptes:connexion')
def mes_commandes(request):
    commandes = Commande.objects.filter(client=request.user).prefetch_related('lignes')
    return render(request, 'comptes/mes_commandes.html', {'commandes': commandes})


@login_required(login_url='comptes:connexion')
def valider_commande(request, commande_id):
    commande = get_object_or_404(Commande, pk=commande_id, client=request.user)
    if commande.validee_par_client:
        messages.info(request, "Cette commande est déjà validée.")
        return redirect('comptes:mes_commandes')
    if commande.statut != 'confirmee':
        messages.warning(request, "Cette commande n'a pas encore été confirmée par 9offty. Vous recevrez un SMS avec le code dès qu'elle le sera.")
        return redirect('comptes:mes_commandes')

    erreur = None
    if request.method == 'POST':
        ok, erreur = services.verifier_code_commande(commande, request.POST.get('code'))
        if ok:
            commande.validee_par_client = True
            commande.date_validation_client = timezone.now()
            commande.save(update_fields=['validee_par_client', 'date_validation_client', 'date_maj'])
            messages.success(request, f"Commande #{commande.pk} validée. Merci ! Nous préparons la livraison.")
            return redirect('comptes:mes_commandes')
    return render(request, 'comptes/valider_commande.html', {'commande': commande, 'erreur': erreur})


@login_required(login_url='comptes:connexion')
@require_POST
def renvoyer_code_commande(request, commande_id):
    commande = get_object_or_404(Commande, pk=commande_id, client=request.user)
    if commande.statut != 'confirmee' or commande.validee_par_client:
        return redirect('comptes:mes_commandes')
    resultat = services.envoyer_code_commande(commande)
    if resultat.ok:
        messages.success(request, "Un nouveau code vient d'être envoyé par SMS.")
    else:
        messages.warning(request, resultat.message)
    return redirect('comptes:valider_commande', commande_id=commande.pk)


def registre(request):
    """Raccourci /registre/ : ouvre la page de connexion directement sur l'onglet Inscription."""
    from urllib.parse import urlencode
    from django.urls import reverse
    suivant = _url_sure(request, request.GET.get('next'))
    requete = '?' + urlencode({'next': suivant}) if suivant else ''
    return redirect(reverse('comptes:connexion') + requete + '#inscription')
