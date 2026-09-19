from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import Categorie, Produit, Commande, LigneCommande
from .panier import Panier
from .forms import CommandeForm


def accueil(request):
    categories = Categorie.objects.all()
    produits_vedette = Produit.objects.filter(disponible=True).order_by('-date_ajout')[:8]
    return render(request, 'boutique/accueil.html', {
        'categories': categories,
        'produits_vedette': produits_vedette,
    })


def liste_produits(request):
    produits = Produit.objects.filter(disponible=True)
    categorie_slug = request.GET.get('categorie')
    type_produit = request.GET.get('type')
    q = request.GET.get('q')
    categorie_active = None

    if categorie_slug:
        categorie_active = get_object_or_404(Categorie, slug=categorie_slug)
        produits = produits.filter(categorie=categorie_active)
    if type_produit in ('legume', 'fruit'):
        produits = produits.filter(categorie__type_produit=type_produit)
    if q:
        produits = produits.filter(Q(nom__icontains=q) | Q(description__icontains=q))

    return render(request, 'boutique/liste_produits.html', {
        'produits': produits,
        'categories': Categorie.objects.all(),
        'categorie_active': categorie_active,
        'type_actif': type_produit,
        'q': q or '',
    })


def categorie_detail(request, slug):
    categorie = get_object_or_404(Categorie, slug=slug)
    produits = categorie.produits.filter(disponible=True)
    return render(request, 'boutique/liste_produits.html', {
        'produits': produits,
        'categories': Categorie.objects.all(),
        'categorie_active': categorie,
        'type_actif': None,
        'q': '',
    })


def produit_detail(request, slug):
    produit = get_object_or_404(Produit, slug=slug)
    produits_similaires = Produit.objects.filter(
        categorie=produit.categorie, disponible=True
    ).exclude(pk=produit.pk)[:4]
    return render(request, 'boutique/produit_detail.html', {
        'produit': produit,
        'produits_similaires': produits_similaires,
    })


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
    return render(request, 'boutique/panier.html', {'panier': panier})


def commander(request):
    panier = Panier(request)
    if len(panier) == 0:
        messages.warning(request, "Votre panier est vide.")
        return redirect('boutique:liste_produits')

    if request.method == 'POST':
        form = CommandeForm(request.POST)
        if form.is_valid():
            commande = form.save()
            for item in panier:
                LigneCommande.objects.create(
                    commande=commande,
                    produit=item['produit'],
                    nom_produit=item['nom'],
                    prix_unitaire=item['prix'],
                    quantite=item['quantite'],
                )
            panier.vider()
            return redirect('boutique:commande_confirmee', commande_id=commande.id)
    else:
        form = CommandeForm()

    return render(request, 'boutique/commander.html', {'form': form, 'panier': panier})


def commande_confirmee(request, commande_id):
    commande = get_object_or_404(Commande, id=commande_id)
    return render(request, 'boutique/commande_confirmee.html', {'commande': commande})
