from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from .models import Produit, Categorie


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
