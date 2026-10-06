from django.conf import settings

from boutique.models import Commande


def commandes_a_valider(request):
    """Commandes confirmées par l'admin dont le client doit saisir le code SMS (bannière du site)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    a_valider = Commande.objects.filter(client=user, statut='confirmee', validee_par_client=False)
    return {'commandes_a_valider': list(a_valider.only('id')[:5])}


def oauth_disponibles(request):
    """Indique quels boutons de connexion sociale sont réellement configurés (clés présentes dans .env)."""
    def actif(provider):
        apps = settings.SOCIALACCOUNT_PROVIDERS.get(provider, {}).get('APPS', [])
        return any(a.get('client_id') and a.get('secret') for a in apps)
    return {
        'oauth_google': actif('google'),
        'oauth_facebook': actif('facebook'),
        'oauth_apple': actif('apple'),
    }


def sms_mode_test(request):
    """Vrai quand aucun vrai SMS n'est envoyé (développement) : les pages l'indiquent clairement."""
    return {'sms_mode_test': bool(settings.DEBUG and settings.SMS_BACKEND == 'console')}
