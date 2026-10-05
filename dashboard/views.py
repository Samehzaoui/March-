from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q
from django.utils import timezone

from boutique import fidelite
from boutique.models import (Avis, Commande, Coupon, Categorie, ImageAccueil, LigneCommande, MoyenPaiement,
                             MouvementPoints, Produit)
from boutique.forms import ProduitForm, CategorieForm, CouponForm, MoyenPaiementForm, ImageAccueilForm
from boutique.paiements import service as paiement_service
from comptes import services as sms_services


def est_staff(user):
    return user.is_active and user.is_staff


def connexion(request):
    """Page de connexion dédiée à l'espace admin (login / mot de passe)."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard:accueil')

    erreur = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next')
            return redirect(next_url or 'dashboard:accueil')
        elif user is not None and not user.is_staff:
            erreur = "Ce compte n'a pas accès à l'espace administrateur."
        else:
            erreur = "Identifiant ou mot de passe incorrect."

    return render(request, 'registration/login.html', {'erreur': erreur})


def deconnexion(request):
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def accueil(request):
    total_produits = Produit.objects.count()
    total_categories = Categorie.objects.count()
    total_commandes = Commande.objects.count()
    commandes_en_attente = Commande.objects.filter(statut='en_attente').count()
    produits_rupture = Produit.objects.filter(stock=0).count()
    ca_total = sum(c.total for c in Commande.objects.exclude(statut='annulee'))
    dernieres_commandes = Commande.objects.all()[:8]

    return render(request, 'dashboard/accueil.html', {
        'total_produits': total_produits,
        'total_categories': total_categories,
        'total_commandes': total_commandes,
        'commandes_en_attente': commandes_en_attente,
        'produits_rupture': produits_rupture,
        'ca_total': ca_total,
        'dernieres_commandes': dernieres_commandes,
    })


# ---------- Produits ----------

@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def produits_liste(request):
    produits = Produit.objects.select_related('categorie').all()
    q = request.GET.get('q')
    if q:
        produits = produits.filter(Q(nom__icontains=q))
    return render(request, 'dashboard/produits_liste.html', {'produits': produits, 'q': q or ''})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def produit_ajouter(request):
    if request.method == 'POST':
        form = ProduitForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Produit ajouté avec succès.")
            return redirect('dashboard:produits_liste')
    else:
        form = ProduitForm()
    return render(request, 'dashboard/produit_form.html', {'form': form, 'titre': 'Ajouter un produit'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def produit_modifier(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    if request.method == 'POST':
        form = ProduitForm(request.POST, request.FILES, instance=produit)
        if form.is_valid():
            form.save()
            messages.success(request, "Produit mis à jour.")
            return redirect('dashboard:produits_liste')
    else:
        form = ProduitForm(instance=produit)
    return render(request, 'dashboard/produit_form.html', {'form': form, 'titre': f'Modifier « {produit.nom} »'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def produit_supprimer(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    if request.method == 'POST':
        produit.delete()
        messages.success(request, "Produit supprimé.")
        return redirect('dashboard:produits_liste')
    return render(request, 'dashboard/confirmer_suppression.html', {'objet': produit})


# ---------- Catégories ----------

@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def categories_liste(request):
    categories = Categorie.objects.annotate(nb_produits=Count('produits'))
    return render(request, 'dashboard/categories_liste.html', {'categories': categories})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def categorie_ajouter(request):
    if request.method == 'POST':
        form = CategorieForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Catégorie ajoutée avec succès.")
            return redirect('dashboard:categories_liste')
    else:
        form = CategorieForm()
    return render(request, 'dashboard/categorie_form.html', {'form': form, 'titre': 'Ajouter une catégorie'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def categorie_modifier(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == 'POST':
        form = CategorieForm(request.POST, request.FILES, instance=categorie)
        if form.is_valid():
            form.save()
            messages.success(request, "Catégorie mise à jour.")
            return redirect('dashboard:categories_liste')
    else:
        form = CategorieForm(instance=categorie)
    return render(request, 'dashboard/categorie_form.html', {'form': form, 'titre': f'Modifier « {categorie.nom} »'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def categorie_supprimer(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == 'POST':
        categorie.delete()
        messages.success(request, "Catégorie supprimée.")
        return redirect('dashboard:categories_liste')
    return render(request, 'dashboard/confirmer_suppression.html', {'objet': categorie})


# ---------- Commandes ----------

@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def commandes_liste(request):
    commandes = Commande.objects.all()
    statut = request.GET.get('statut')
    if statut:
        commandes = commandes.filter(statut=statut)
    return render(request, 'dashboard/commandes_liste.html', {
        'commandes': commandes,
        'statut_actif': statut or '',
        'statuts': Commande.STATUT_CHOICES,
    })


# ---------- Moyens de paiement ----------

@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def paiements_liste(request):
    moyens = MoyenPaiement.objects.all()
    return render(request, 'dashboard/paiements_liste.html', {'moyens': moyens})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def paiement_ajouter(request):
    if request.method == 'POST':
        form = MoyenPaiementForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Moyen de paiement ajouté.")
            return redirect('dashboard:paiements_liste')
    else:
        form = MoyenPaiementForm()
    return render(request, 'dashboard/paiement_form.html', {'form': form, 'titre': 'Ajouter un moyen de paiement'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def paiement_modifier(request, pk):
    moyen = get_object_or_404(MoyenPaiement, pk=pk)
    if request.method == 'POST':
        form = MoyenPaiementForm(request.POST, request.FILES, instance=moyen)
        if form.is_valid():
            form.save()
            messages.success(request, "Moyen de paiement mis à jour.")
            return redirect('dashboard:paiements_liste')
    else:
        form = MoyenPaiementForm(instance=moyen)
    return render(request, 'dashboard/paiement_form.html', {'form': form, 'titre': f'Modifier « {moyen.nom} »'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def paiement_supprimer(request, pk):
    moyen = get_object_or_404(MoyenPaiement, pk=pk)
    if request.method == 'POST':
        moyen.delete()
        messages.success(request, "Moyen de paiement supprimé.")
        return redirect('dashboard:paiements_liste')
    return render(request, 'dashboard/confirmer_suppression.html', {'objet': moyen})


# ---------- Images d'accueil (diaporama) ----------

@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def slides_liste(request):
    slides = ImageAccueil.objects.all()
    return render(request, 'dashboard/slides_liste.html', {'slides': slides})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def slide_ajouter(request):
    if request.method == 'POST':
        form = ImageAccueilForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Image ajoutée au diaporama.")
            return redirect('dashboard:slides_liste')
    else:
        form = ImageAccueilForm()
    return render(request, 'dashboard/slide_form.html', {'form': form, 'titre': 'Ajouter une image'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def slide_modifier(request, pk):
    slide = get_object_or_404(ImageAccueil, pk=pk)
    if request.method == 'POST':
        form = ImageAccueilForm(request.POST, request.FILES, instance=slide)
        if form.is_valid():
            form.save()
            messages.success(request, "Image mise à jour.")
            return redirect('dashboard:slides_liste')
    else:
        form = ImageAccueilForm(instance=slide)
    return render(request, 'dashboard/slide_form.html', {'form': form, 'titre': "Modifier l'image"})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def slide_supprimer(request, pk):
    slide = get_object_or_404(ImageAccueil, pk=pk)
    if request.method == 'POST':
        slide.delete()
        messages.success(request, "Image supprimée.")
        return redirect('dashboard:slides_liste')
    return render(request, 'dashboard/confirmer_suppression.html', {'objet': slide})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def commande_detail(request, pk):
    commande = get_object_or_404(Commande, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'renvoyer_code':
            if commande.statut == 'confirmee' and not commande.validee_par_client and commande.validation_sms_requise:
                resultat = sms_services.envoyer_code_commande(commande)
                if resultat.ok:
                    messages.success(request, f"Code SMS renvoyé au {commande.telephone}.")
                else:
                    messages.warning(request, resultat.message)
            else:
                messages.warning(request, "Le code ne peut être renvoyé que pour une commande confirmée et non encore validée.")
            return redirect('dashboard:commande_detail', pk=pk)

        if action == 'verifier_paiement':
            if commande.paiement_en_ligne and commande.reference_paiement:
                commande = paiement_service.synchroniser(commande.pk, delai_anti_spam=0)
                if commande.statut_paiement == 'paye':
                    messages.success(request, "Le fournisseur confirme le paiement.")
                else:
                    messages.info(request, "Paiement non confirmé par le fournisseur pour le moment.")
            return redirect('dashboard:commande_detail', pk=pk)

        if action == 'marquer_paye':
            # Cas de secours : paiement vu sur le tableau de bord Konnect / Flouci mais non reçu par le site.
            if commande.paiement_en_ligne and commande.statut_paiement in ('en_attente', 'echoue'):
                paiement_service.marquer_paye(commande, par=f"admin {request.user.username}")
                messages.success(request, "Commande marquée comme payée.")
            return redirect('dashboard:commande_detail', pk=pk)

        if action == 'marquer_rembourse':
            if commande.statut_paiement == 'paye' and commande.statut == 'annulee':
                commande.statut_paiement = 'rembourse'
                commande.save(update_fields=['statut_paiement', 'date_maj'])
                messages.success(request, "Remboursement enregistré. Pensez à l'effectuer chez le fournisseur de paiement.")
            return redirect('dashboard:commande_detail', pk=pk)

        nouveau_statut = request.POST.get('statut')
        if nouveau_statut in dict(Commande.STATUT_CHOICES):
            traitement = nouveau_statut in ('confirmee', 'en_livraison', 'livree')
            if traitement and commande.paiement_en_ligne and commande.statut_paiement != 'paye':
                messages.error(request, "Impossible : le paiement en ligne de cette commande n'est pas encore reçu.")
                return redirect('dashboard:commande_detail', pk=pk)
            if (nouveau_statut in ('en_livraison', 'livree') and commande.validation_sms_requise
                    and not commande.validee_par_client):
                messages.error(request, "Impossible : le client n'a pas encore validé la commande avec le code SMS.")
                return redirect('dashboard:commande_detail', pk=pk)
            ancien_statut = commande.statut
            commande.statut = nouveau_statut
            if traitement and not commande.validation_sms_requise and not commande.validee_par_client:
                # Commande payée en ligne : le paiement vaut validation.
                commande.validee_par_client = True
                commande.date_validation_client = timezone.now()
            commande.save()
            messages.success(request, "Statut de la commande mis à jour.")
            if (nouveau_statut == 'confirmee' and ancien_statut != 'confirmee'
                    and commande.validation_sms_requise and not commande.validee_par_client):
                resultat = sms_services.envoyer_code_commande(commande)
                if resultat.ok:
                    messages.success(request, f"Code de validation envoyé par SMS au {commande.telephone}.")
                else:
                    messages.warning(request, f"Le SMS n'a pas été envoyé : {resultat.message} Utilisez « Renvoyer le code SMS » ci-dessous.")
            return redirect('dashboard:commande_detail', pk=pk)
    return render(request, 'dashboard/commande_detail.html', {'commande': commande})


# ---------- Registre des clients ----------

import csv
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import DecimalField, ExpressionWrapper, F
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

_Utilisateur = get_user_model()

METHODES = [
    ('sms', '📱 SMS'),
    ('email', '✉️ Email'),
    ('google', 'Google'),
    ('facebook', 'Facebook'),
    ('apple', 'Apple'),
]
_STATUTS_COMPTES = ['en_attente', 'confirmee', 'en_livraison', 'livree']  # annulées exclues du total dépensé


def _clients_queryset():
    """Clients = comptes non staff, avec nb de commandes et total dépensé (hors annulées, remises déduites)."""
    from django.db.models import OuterRef, Subquery, Value
    from django.db.models.functions import Coalesce

    decimal = DecimalField(max_digits=14, decimal_places=3)
    zero = Value(Decimal('0'), output_field=decimal)
    articles = (LigneCommande.objects
                .filter(commande__client=OuterRef('pk'), commande__statut__in=_STATUTS_COMPTES)
                .order_by().values('commande__client')
                .annotate(t=Sum(ExpressionWrapper(F('prix_unitaire') * F('quantite'), output_field=decimal)))
                .values('t'))
    remises = (Commande.objects
               .filter(client=OuterRef('pk'), statut__in=_STATUTS_COMPTES)
               .order_by().values('client')
               .annotate(r=Sum(ExpressionWrapper(F('remise_coupon') + F('remise_points'), output_field=decimal)))
               .values('r'))
    return (_Utilisateur.objects.filter(is_staff=False, is_superuser=False)
            .select_related('profil')
            .prefetch_related('socialaccount_set')
            .annotate(nb_commandes=Count('commandes', distinct=True),
                      _articles=Coalesce(Subquery(articles, output_field=decimal), zero),
                      _remises=Coalesce(Subquery(remises, output_field=decimal), zero))
            .annotate(total_depense=ExpressionWrapper(F('_articles') - F('_remises'), output_field=decimal)))


def _methodes_client(u):
    codes = []
    if hasattr(u, 'profil'):
        codes.append('sms')
    for sa in u.socialaccount_set.all():
        if sa.provider in ('google', 'facebook', 'apple') and sa.provider not in codes:
            codes.append(sa.provider)
    if not codes and u.email:
        codes.append('email')
    libelles = dict(METHODES)
    return [(c, libelles.get(c, c)) for c in codes] or [('autre', 'Autre')]


def _telephone_client(u):
    if hasattr(u, 'profil'):
        return u.profil.telephone
    derniere = u.commandes.exclude(telephone='').order_by('-date_commande').first()
    return derniere.telephone if derniere else ''


def _nom_client(u):
    nom = f"{u.first_name} {u.last_name}".strip()
    if nom:
        return nom
    derniere = u.commandes.exclude(nom_client='').order_by('-date_commande').first()
    if derniere:
        return derniere.nom_client
    return u.email.split('@')[0] if u.email else '—'


def _filtrer_clients(request):
    clients = _clients_queryset()
    q = request.GET.get('q', '').strip()
    methode = request.GET.get('methode', '')
    if q:
        clients = clients.filter(
            Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            | Q(profil__telephone__icontains=q) | Q(commandes__nom_client__icontains=q)
            | Q(commandes__telephone__icontains=q)
        ).distinct()
    if methode == 'sms':
        clients = clients.filter(profil__isnull=False)
    elif methode in ('google', 'facebook', 'apple'):
        clients = clients.filter(socialaccount__provider=methode).distinct()
    elif methode == 'email':
        clients = clients.filter(profil__isnull=True, socialaccount__isnull=True).exclude(email='')
    return clients.order_by('-date_joined'), q, methode


def _preparer(u):
    u.methodes = _methodes_client(u)
    u.tel = _telephone_client(u)
    u.nom_affiche = _nom_client(u)
    return u


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def clients_liste(request):
    clients, q, methode = _filtrer_clients(request)
    page = Paginator(clients, 25).get_page(request.GET.get('page'))
    for u in page:
        _preparer(u)

    tous = _Utilisateur.objects.filter(is_staff=False, is_superuser=False)
    debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stats = {
        'total': tous.count(),
        'ce_mois': tous.filter(date_joined__gte=debut_mois).count(),
        'avec_commande': tous.filter(commandes__isnull=False).distinct().count(),
        'sociaux': tous.filter(socialaccount__isnull=False).distinct().count(),
    }
    return render(request, 'dashboard/clients_liste.html', {
        'page': page, 'q': q, 'methode_active': methode, 'methodes': METHODES, 'stats': stats,
    })


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def client_detail(request, pk):
    client = get_object_or_404(_clients_queryset(), pk=pk)
    _preparer(client)
    commandes = client.commandes.prefetch_related('lignes').order_by('-date_commande')
    points = fidelite.solde(client)
    return render(request, 'dashboard/client_detail.html', {
        'client': client, 'commandes': commandes,
        'solde_points': points, 'valeur_points': fidelite.valeur_points(max(points, 0)),
        'mouvements': client.mouvements_points.select_related('commande')[:15],
    })


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
@require_POST
def client_statut(request, pk):
    """Active / désactive un compte client (il ne pourra plus se connecter)."""
    client = get_object_or_404(_Utilisateur, pk=pk, is_staff=False, is_superuser=False)
    client.is_active = not client.is_active
    client.save(update_fields=['is_active'])
    messages.success(request, f"Compte {'réactivé' if client.is_active else 'désactivé'}.")
    return redirect('dashboard:client_detail', pk=pk)


def _cellule_csv(valeur):
    """Neutralise les formules Excel (=, +, -, @) dans les données saisies par les clients."""
    texte = '' if valeur is None else str(valeur)
    return "'" + texte if texte[:1] in ('=', '+', '-', '@') else texte


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def clients_export(request):
    clients, _, _ = _filtrer_clients(request)
    reponse = HttpResponse(content_type='text/csv; charset=utf-8')
    reponse['Content-Disposition'] = f'attachment; filename="clients_{timezone.now():%Y%m%d}.csv"'
    reponse.write('\ufeff')  # BOM pour qu'Excel lise bien les accents
    w = csv.writer(reponse, delimiter=';')
    w.writerow(['Nom', 'Email', 'Téléphone', 'Inscription via', 'Date inscription',
                'Commandes', 'Total dépensé (DT)', 'Actif'])
    for u in clients:
        _preparer(u)
        w.writerow([_cellule_csv(u.nom_affiche), _cellule_csv(u.email), _cellule_csv(u.tel),
                    ', '.join(l for _, l in u.methodes), f"{u.date_joined:%d/%m/%Y}",
                    u.nb_commandes, f"{(u.total_depense or Decimal('0')):.3f}",
                    'oui' if u.is_active else 'non'])
    return reponse


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def client_ajouter(request):
    from .forms import ClientCreationForm
    form = ClientCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        client = form.save()
        messages.success(request, "Client créé avec succès.")
        return redirect('dashboard:client_detail', pk=client.pk)
    return render(request, 'dashboard/client_form.html', {'form': form, 'titre': 'Nouveau client'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
@require_POST
def client_points_ajuster(request, pk):
    """Ajustement manuel des points d'un client (geste commercial, correction)."""
    client = get_object_or_404(_Utilisateur, pk=pk, is_staff=False, is_superuser=False)
    motif = (request.POST.get('motif') or '').strip()[:200]
    try:
        points = int(request.POST.get('points', ''))
    except ValueError:
        points = 0
    if points == 0 or abs(points) > 100000:
        messages.error(request, "Indiquez un nombre de points non nul (positif pour ajouter, négatif pour retirer).")
    elif not motif:
        messages.error(request, "Indiquez le motif de l'ajustement.")
    elif fidelite.solde(client) + points < 0:
        messages.error(request, "Ajustement refusé : le solde deviendrait négatif.")
    else:
        MouvementPoints.objects.create(client=client, points=points, type=MouvementPoints.TYPE_AJUSTEMENT,
                                       motif=f"{motif} (par {request.user.username})")
        messages.success(request, f"{points:+d} points enregistrés.")
    return redirect('dashboard:client_detail', pk=pk)


# ---------- Coupons ----------

@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def coupons_liste(request):
    coupons = Coupon.objects.annotate(
        nb_util=Count('commandes', filter=Q(commandes__statut__in=_STATUTS_COMPTES), distinct=True))
    return render(request, 'dashboard/coupons_liste.html', {'coupons': coupons, 'maintenant': timezone.now()})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def coupon_ajouter(request):
    form = CouponForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Coupon créé.")
        return redirect('dashboard:coupons_liste')
    return render(request, 'dashboard/coupon_form.html', {'form': form, 'titre': 'Nouveau coupon'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def coupon_modifier(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    form = CouponForm(request.POST or None, instance=coupon)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Coupon mis à jour.")
        return redirect('dashboard:coupons_liste')
    return render(request, 'dashboard/coupon_form.html', {'form': form, 'titre': f'Modifier {coupon.code}'})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def coupon_supprimer(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        coupon.delete()
        messages.success(request, "Coupon supprimé (les commandes passées gardent leur remise).")
        return redirect('dashboard:coupons_liste')
    return render(request, 'dashboard/confirmer_suppression.html', {'objet': coupon.code})


# ---------- Avis ----------

@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def avis_liste(request):
    avis = Avis.objects.select_related('produit', 'client')
    etat = request.GET.get('etat', '')
    q = request.GET.get('q', '').strip()
    if etat == 'visibles':
        avis = avis.filter(visible=True)
    elif etat == 'masques':
        avis = avis.filter(visible=False)
    if q:
        avis = avis.filter(Q(produit__nom__icontains=q) | Q(commentaire__icontains=q))
    page = Paginator(avis, 25).get_page(request.GET.get('page'))
    return render(request, 'dashboard/avis_liste.html', {'page': page, 'etat': etat, 'q': q})


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
@require_POST
def avis_basculer(request, pk):
    avis = get_object_or_404(Avis, pk=pk)
    avis.visible = not avis.visible
    avis.save(update_fields=['visible', 'modifie_le'])
    messages.success(request, "Avis affiché sur le site." if avis.visible else "Avis masqué du site.")
    return redirect(request.POST.get('next') or 'dashboard:avis_liste')


@login_required(login_url='dashboard:login')
@user_passes_test(est_staff, login_url='dashboard:login')
def avis_supprimer(request, pk):
    avis = get_object_or_404(Avis, pk=pk)
    if request.method == 'POST':
        avis.delete()
        messages.success(request, "Avis supprimé.")
        return redirect('dashboard:avis_liste')
    return render(request, 'dashboard/confirmer_suppression.html', {'objet': f"avis sur {avis.produit}"})
