from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import catalogue, fidelite
from .commandes import SESSION_COUPON, ErreurCommande, calculer_recapitulatif, creer_commande, telephone_verifie
from .forms import AvisForm, CommandeForm
from .models import Avis, Categorie, Commande, Coupon, ImageAccueil, LigneCommande, MoyenPaiement, Produit
from .paiements import ErreurPaiement, fournisseurs_actifs
from .paiements import service as paiement_service
from .panier import Panier


def accueil(request):
    return render(request, 'boutique/accueil.html', {
        'categories': catalogue.categories(),
        'produits_vedette': catalogue.produits_vedette(),
        'slides': catalogue.slides_actifs(),
        'moyens_paiement': catalogue.moyens_paiement_actifs(),
    })


def _categorie_par_slug(slug):
    for categorie in catalogue.categories():
        if categorie.slug == slug:
            return categorie
    raise Http404("Catégorie introuvable.")


def liste_produits(request):
    categorie_slug = request.GET.get('categorie')
    type_produit = request.GET.get('type')
    q = (request.GET.get('q') or '').strip()
    categorie_active = _categorie_par_slug(categorie_slug) if categorie_slug else None
    if type_produit not in dict(Categorie.TYPE_CHOICES):
        type_produit = None

    if q:   # une recherche libre n'est pas mise en cache
        produits = Produit.objects.filter(disponible=True).select_related('categorie')
        if categorie_active:
            produits = produits.filter(categorie=categorie_active)
        if type_produit:
            produits = produits.filter(categorie__type_produit=type_produit)
        produits = produits.filter(Q(nom__icontains=q) | Q(nom_ar__icontains=q) | Q(description__icontains=q))
    else:
        produits = catalogue.produits(categorie_slug if categorie_active else None, type_produit)

    return render(request, 'boutique/liste_produits.html', {
        'produits': produits,
        'categories': catalogue.categories(),
        'categorie_active': categorie_active,
        'type_actif': type_produit,
        'q': q,
    })


def categorie_detail(request, slug):
    categorie = _categorie_par_slug(slug)
    return render(request, 'boutique/liste_produits.html', {
        'produits': catalogue.produits(categorie.slug, None),
        'categories': catalogue.categories(),
        'categorie_active': categorie,
        'type_actif': None,
        'q': '',
    })


def _nom_public(user):
    """Prénom + initiale du nom : on n'affiche jamais l'email ni le téléphone d'un client."""
    prenom = (user.first_name or '').strip()
    nom = (user.last_name or '').strip()
    if prenom:
        return f"{prenom} {nom[0]}." if nom else prenom
    derniere = user.commandes.exclude(nom_client='').order_by('-date_commande').first()
    if derniere:
        morceaux = derniere.nom_client.split()
        return f"{morceaux[0]} {morceaux[1][0]}." if len(morceaux) > 1 else morceaux[0]
    return "Client 9offty"


def _peut_noter(user, produit):
    """Seuls les clients dont une commande contenant ce produit a été livrée peuvent donner un avis."""
    return user.is_authenticated and LigneCommande.objects.filter(
        produit=produit, commande__client=user, commande__statut='livree').exists()


def produit_detail(request, slug):
    produit = get_object_or_404(Produit, slug=slug)
    produits_similaires = catalogue.similaires(produit)

    avis = list(produit.avis.filter(visible=True).select_related('client')[:50])
    for a in avis:
        a.auteur = _nom_public(a.client)
    repartition = {r['note']: r['n'] for r in produit.avis.filter(visible=True).values('note').annotate(n=Count('id'))}
    total_avis = sum(repartition.values())
    barres = [(n, repartition.get(n, 0), round(100 * repartition.get(n, 0) / total_avis) if total_avis else 0)
              for n in range(5, 0, -1)]

    mon_avis = produit.avis.filter(client=request.user).first() if request.user.is_authenticated else None
    return render(request, 'boutique/produit_detail.html', {
        'produit': produit,
        'produits_similaires': produits_similaires,
        'avis': avis,
        'barres': barres,
        'mon_avis': mon_avis,
        'peut_noter': _peut_noter(request.user, produit),
        'form_avis': AvisForm(instance=mon_avis),
    })


@login_required(login_url='comptes:connexion')
@require_POST
def avis_poster(request, slug):
    produit = get_object_or_404(Produit, slug=slug)
    if not _peut_noter(request.user, produit):
        messages.error(request, "Vous pourrez donner votre avis une fois votre commande livrée.")
        return redirect(produit.get_absolute_url())
    existant = produit.avis.filter(client=request.user).first()
    form = AvisForm(request.POST, instance=existant)
    if form.is_valid():
        avis = form.save(commit=False)
        avis.produit, avis.client = produit, request.user
        avis.save()
        messages.success(request, "Merci ! Votre avis a été enregistré.")
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect(produit.get_absolute_url() + '#avis')


@login_required(login_url='comptes:connexion')
@require_POST
def avis_supprimer(request, slug):
    produit = get_object_or_404(Produit, slug=slug)
    produit.avis.filter(client=request.user).delete()
    messages.success(request, "Votre avis a été supprimé.")
    return redirect(produit.get_absolute_url() + '#avis')


@require_POST
def panier_ajouter(request, produit_id):
    produit = get_object_or_404(Produit, id=produit_id)
    panier = Panier(request)
    try:
        quantite = int(request.POST.get('quantite', 1))
    except (TypeError, ValueError):
        quantite = 1
    quantite = max(1, quantite)
    panier.ajouter(produit, quantite)
    messages.success(request, f"« {produit.nom} » a été ajouté au panier.")
    return redirect(request.POST.get('next') or 'boutique:panier')


@require_POST
def panier_modifier(request, produit_id):
    panier = Panier(request)
    try:
        quantite = int(request.POST.get('quantite', 1))
    except (TypeError, ValueError):
        quantite = 1
    panier.definir_quantite(produit_id, quantite)
    return redirect('boutique:panier')


def panier_supprimer(request, produit_id):
    panier = Panier(request)
    panier.supprimer(produit_id)
    return redirect('boutique:panier')


def voir_panier(request):
    panier = Panier(request)
    recap = calculer_recapitulatif(request, panier)
    if recap['coupon_erreur']:
        messages.warning(request, recap['coupon_erreur'])
    return render(request, 'boutique/panier.html', {'panier': panier, 'recap': recap})


@require_POST
def panier_coupon_appliquer(request):
    panier = Panier(request)
    code = (request.POST.get('code') or '').strip().upper()[:40]
    if not code:
        messages.error(request, "Saisissez un code promo.")
        return redirect('boutique:panier')
    coupon = Coupon.objects.filter(code=code).first()
    if coupon is None:
        messages.error(request, "Ce code promo n'existe pas.")
        return redirect('boutique:panier')
    user = request.user if request.user.is_authenticated else None
    ok, message = coupon.verifier(Decimal(panier.total()), user, telephone_verifie(user) if user else None)
    if not ok:
        messages.error(request, message)
        return redirect('boutique:panier')
    request.session[SESSION_COUPON] = coupon.code
    messages.success(request, f"Code {coupon.code} appliqué : {coupon.libelle_remise}.")
    return redirect('boutique:panier')


@require_POST
def panier_coupon_retirer(request):
    request.session.pop(SESSION_COUPON, None)
    messages.info(request, "Code promo retiré.")
    return redirect('boutique:panier')


def _modes_paiement():
    return [('livraison', "Payer à la livraison")] + fournisseurs_actifs()


@login_required(login_url='comptes:connexion')
def commander(request):
    panier = Panier(request)
    if len(panier) == 0:
        messages.warning(request, "Votre panier est vide.")
        return redirect('boutique:liste_produits')

    tel_verifie = telephone_verifie(request.user)
    modes = _modes_paiement()
    codes_modes = [c for c, _ in modes]
    mode = request.POST.get('mode_paiement', 'livraison') if request.method == 'POST' else 'livraison'
    if mode not in codes_modes:
        mode = 'livraison'
    utiliser_points = request.method == 'POST' and request.POST.get('utiliser_points') == 'on'

    if request.method == 'POST':
        form = CommandeForm(request.POST, telephone_verifie=tel_verifie)
        if form.is_valid():
            try:
                commande = creer_commande(request, form, panier, utiliser_points=utiliser_points, mode_paiement=mode)
            except ErreurCommande as e:
                messages.error(request, str(e))
                return redirect('boutique:commander')
            panier.vider()
            if commande.paiement_en_ligne:
                try:
                    return redirect(paiement_service.demarrer(commande, commande.mode_paiement))
                except ErreurPaiement as e:
                    messages.warning(request, f"{e} Votre commande #{commande.pk} est enregistrée : "
                                              "vous pouvez réessayer le paiement ou payer à la livraison.")
            return redirect('boutique:commande_confirmee', commande_id=commande.id)
    else:
        derniere = Commande.objects.filter(client=request.user).first()
        initial = {}
        if derniere:
            initial = {'nom_client': derniere.nom_client, 'email': derniere.email,
                       'gouvernorat': derniere.gouvernorat, 'adresse': derniere.adresse}
        form = CommandeForm(initial=initial, telephone_verifie=tel_verifie)

    recap = calculer_recapitulatif(request, panier, utiliser_points=utiliser_points)
    return render(request, 'boutique/commander.html', {
        'form': form, 'panier': panier, 'telephone': tel_verifie, 'recap': recap,
        'modes': modes, 'mode_choisi': mode, 'utiliser_points': utiliser_points,
        'total_avant_points': recap['total'] + recap['remise_points'],
    })


@login_required(login_url='comptes:connexion')
def commande_confirmee(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id, client=request.user)
    return render(request, 'boutique/commande_confirmee.html', {
        'commande': commande, 'fournisseurs': fournisseurs_actifs(),
        'solde_points': fidelite.solde(request.user),
    })
