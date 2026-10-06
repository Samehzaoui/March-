from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from .models import Avis, Categorie, Commande, ImageAccueil, MoyenPaiement, Produit


def generer_slug_unique(instance, base_slug, model):
    slug = base_slug
    n = 1
    qs = model.objects.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        n += 1
        slug = f"{base_slug}-{n}"
    return slug


@receiver(pre_save, sender=Produit)
def produit_pre_save(sender, instance, **kwargs):
    if not instance.slug:
        instance.slug = generer_slug_unique(instance, slugify(instance.nom), Produit)


@receiver(pre_save, sender=Categorie)
def categorie_pre_save(sender, instance, **kwargs):
    if not instance.slug:
        instance.slug = generer_slug_unique(instance, slugify(instance.nom), Categorie)


@receiver(post_save, sender=Avis)
@receiver(post_delete, sender=Avis)
def avis_modifie(sender, instance, **kwargs):
    """Garde la note moyenne et le nombre d'avis du produit à jour."""
    try:
        produit = Produit.objects.get(pk=instance.produit_id)
    except Produit.DoesNotExist:
        return
    produit.recalculer_avis()


@receiver(post_save, sender=Commande)
def commande_enregistree(sender, instance, **kwargs):
    """Points de fidélité : gain à la livraison, remboursement / retrait à l'annulation."""
    from . import fidelite
    fidelite.synchroniser(instance)


def _catalogue_modifie(sender, **kwargs):
    """Produit, catégorie, bannière ou moyen de paiement modifié : le cache du catalogue n'est plus valable."""
    from . import catalogue
    catalogue.invalider()


for _modele in (Produit, Categorie, ImageAccueil, MoyenPaiement):
    post_save.connect(_catalogue_modifie, sender=_modele, dispatch_uid=f"catalogue_save_{_modele.__name__}")
    post_delete.connect(_catalogue_modifie, sender=_modele, dispatch_uid=f"catalogue_delete_{_modele.__name__}")
