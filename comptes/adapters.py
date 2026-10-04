from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class AccountAdapter(DefaultAccountAdapter):
    """Les clients connectés par email / Google / Facebook / Apple
    arrivent sur la boutique (et non sur le dashboard admin)."""

    def get_login_redirect_url(self, request):
        return request.GET.get('next') or reverse('boutique:accueil')

    def get_signup_redirect_url(self, request):
        return reverse('boutique:accueil')

    def get_logout_redirect_url(self, request):
        return reverse('boutique:accueil')
