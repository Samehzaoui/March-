from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q

from boutique.models import Produit, Categorie, Commande, LigneCommande
from boutique.forms import ProduitForm, CategorieForm


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
