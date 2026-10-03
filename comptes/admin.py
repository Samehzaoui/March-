from django.contrib import admin
from .models import ProfilClient, CodeSMS


@admin.register(ProfilClient)
class ProfilClientAdmin(admin.ModelAdmin):
    list_display = ('telephone', 'user', 'cree_le')
    search_fields = ('telephone',)


@admin.register(CodeSMS)
class CodeSMSAdmin(admin.ModelAdmin):
    """Lecture seule : sert à l'audit (le code lui-même n'est jamais stocké en clair)."""
    list_display = ('telephone', 'objet', 'commande', 'cree_le', 'expire_le', 'tentatives', 'utilise')
    list_filter = ('objet', 'utilise')
    search_fields = ('telephone',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
