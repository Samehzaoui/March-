from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _configurer_site(sender, **kwargs):
    """Remplace le Site par défaut 'example.com' par le nom/domaine réels (utilisés dans les emails)."""
    from django.conf import settings
    from django.contrib.sites.models import Site
    try:
        Site.objects.update_or_create(
            pk=settings.SITE_ID,
            defaults={'name': '9offty', 'domain': settings.SITE_DOMAIN},
        )
    except Exception:
        pass


class ComptesConfig(AppConfig):
    name = 'comptes'

    def ready(self):
        post_migrate.connect(_configurer_site, sender=self)
