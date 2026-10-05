"""Retours et notifications des fournisseurs de paiement en ligne."""
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Commande
from .paiements import ErreurPaiement, fournisseurs_actifs
from .paiements import service

logger = logging.getLogger(__name__)


def retour(request, commande_id):
    """Le client revient de la page du fournisseur : on vérifie le paiement côté serveur, puis on l'informe.

    Rien de ce qui figure dans l'adresse n'est cru : seule la réponse du fournisseur compte.
    """
    commande = get_object_or_404(Commande, pk=commande_id)
    commande = service.synchroniser(commande.pk)
    if commande.statut_paiement == 'paye':
        messages.success(request, "Paiement reçu. Merci !")
    elif commande.statut_paiement == 'echoue':
        messages.error(request, "Le paiement n'a pas abouti. Vous pouvez réessayer ou payer à la livraison.")
    elif commande.paiement_en_ligne:
        messages.info(request, "Votre paiement n'est pas encore confirmé. Utilisez « Vérifier mon paiement » dans quelques instants.")
    return redirect('boutique:commande_confirmee', commande_id=commande.pk)


def _reference_depuis_requete(request, *noms):
    for nom in noms:
        valeur = request.GET.get(nom) or request.POST.get(nom)
        if valeur:
            return valeur.strip()[:120]
    if request.body and request.content_type == 'application/json':
        try:
            donnees = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return ''
        if isinstance(donnees, dict):
            for nom in noms:
                if donnees.get(nom):
                    return str(donnees[nom]).strip()[:120]
    return ''


@csrf_exempt
def webhook_konnect(request):
    """Konnect appelle cette adresse avec ?payment_ref=... (et y renvoie aussi le client à la fin du paiement)."""
    reference = _reference_depuis_requete(request, 'payment_ref')
    commande = Commande.objects.filter(reference_paiement=reference).first() if reference else None
    if commande is None:
        raise Http404()
    commande = service.synchroniser(commande.pk, delai_anti_spam=2)
    return redirect('boutique:commande_confirmee', commande_id=commande.pk)


@csrf_exempt
def webhook_flouci(request):
    """Flouci ne signe pas ses notifications : on ne retient que l'identifiant, puis on vérifie auprès de Flouci."""
    reference = _reference_depuis_requete(request, 'payment_id', 'id')
    commande = Commande.objects.filter(reference_paiement=reference).first() if reference else None
    if commande is None:
        return JsonResponse({'ok': False}, status=404)
    commande = service.synchroniser(commande.pk, delai_anti_spam=2)
    return JsonResponse({'ok': True, 'statut': commande.statut_paiement})


@login_required(login_url='comptes:connexion')
@require_POST
def reessayer(request, commande_id):
    commande = get_object_or_404(Commande, pk=commande_id, client=request.user)
    if commande.statut == 'annulee' or commande.statut_paiement not in ('en_attente', 'echoue'):
        return redirect('boutique:commande_confirmee', commande_id=commande.pk)

    # Si le client avait en fait payé, on le constate avant de créer un second paiement.
    if commande.reference_paiement and commande.paiement_en_ligne:
        commande = service.synchroniser(commande.pk, delai_anti_spam=0)
        if commande.statut_paiement == 'paye':
            messages.success(request, "Paiement déjà reçu. Merci !")
            return redirect('boutique:commande_confirmee', commande_id=commande.pk)

    fournisseur = request.POST.get('fournisseur') or commande.mode_paiement
    if fournisseur not in dict(fournisseurs_actifs()):
        fournisseur = commande.mode_paiement
    try:
        return redirect(service.demarrer(commande, fournisseur))
    except ErreurPaiement as e:
        messages.error(request, str(e))
        return redirect('boutique:commande_confirmee', commande_id=commande.pk)


@login_required(login_url='comptes:connexion')
@require_POST
def passer_a_la_livraison(request, commande_id):
    commande = get_object_or_404(Commande, pk=commande_id, client=request.user)
    if commande.statut == 'annulee' or commande.statut_paiement not in ('en_attente', 'echoue'):
        return redirect('boutique:commande_confirmee', commande_id=commande.pk)
    if commande.reference_paiement and commande.paiement_en_ligne:
        commande = service.synchroniser(commande.pk, delai_anti_spam=0)
        if commande.statut_paiement == 'paye':
            messages.success(request, "Votre paiement avait bien été reçu. Merci !")
            return redirect('boutique:commande_confirmee', commande_id=commande.pk)
    Commande.objects.filter(pk=commande.pk).update(mode_paiement='livraison', statut_paiement='a_la_livraison')
    messages.success(request, "C'est noté : vous paierez à la livraison.")
    return redirect('boutique:commande_confirmee', commande_id=commande.pk)
