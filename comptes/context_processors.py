from boutique.models import Commande


def commandes_a_valider(request):
    """Commandes confirmées par l'admin dont le client doit saisir le code SMS (bannière du site)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    a_valider = Commande.objects.filter(client=user, statut='confirmee', validee_par_client=False)
    return {'commandes_a_valider': list(a_valider.only('id')[:5])}
