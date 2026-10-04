from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q

from boutique.models import Produit, Categorie, Commande, LigneCommande, MoyenPaiement, ImageAccueil
from boutique.forms import ProduitForm, CategorieForm, MoyenPaiementForm, ImageAccueilForm


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
        nouveau_statut = request.POST.get('statut')
        if nouveau_statut in dict(Commande.STATUT_CHOICES):
            commande.statut = nouveau_statut
            commande.save()
            messages.success(request, "Statut de la commande mis à jour.")
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
    """Clients = comptes non staff, avec nb de commandes et total dépensé (hors annulées)."""
    montant = ExpressionWrapper(
        F('commandes__lignes__prix_unitaire') * F('commandes__lignes__quantite'),
        output_field=DecimalField(max_digits=14, decimal_places=3),
    )
    return (_Utilisateur.objects.filter(is_staff=False, is_superuser=False)
            .select_related('profil')
            .prefetch_related('socialaccount_set')
            .annotate(nb_commandes=Count('commandes', distinct=True),
                      total_depense=Sum(montant, filter=Q(commandes__statut__in=_STATUTS_COMPTES))))


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
    return render(request, 'dashboard/client_detail.html', {'client': client, 'commandes': commandes})


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
