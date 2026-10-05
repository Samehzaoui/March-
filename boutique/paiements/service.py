"""Cycle de vie d'un paiement en ligne : démarrage, vérification auprès du fournisseur, enregistrement."""
import logging

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from boutique.models import Commande

from . import ErreurPaiement, en_millimes, fournisseurs_actifs, obtenir

logger = logging.getLogger(__name__)


def demarrer(commande, fournisseur):
    """Crée le paiement chez le fournisseur et retourne l'adresse où envoyer le client."""
    if fournisseur not in dict(fournisseurs_actifs()):
        raise ErreurPaiement("Ce mode de paiement n'est pas disponible.")
    if commande.total <= 0:
        raise ErreurPaiement("Cette commande n'a rien à payer.")
    initialisation = obtenir(fournisseur).initier(commande)
    Commande.objects.filter(pk=commande.pk).update(
        mode_paiement=fournisseur, statut_paiement='en_attente', reference_paiement=initialisation.reference,
    )
    return initialisation.url


def marquer_paye(commande, par='fournisseur'):
    """Enregistre le paiement (à appeler dans une transaction, commande verrouillée)."""
    commande.statut_paiement = 'paye'
    commande.paye_le = timezone.now()
    champs = ['statut_paiement', 'paye_le', 'date_maj']
    # Le paiement en ligne fait foi : plus besoin du code SMS de validation.
    if commande.statut in ('confirmee', 'en_livraison', 'livree') and not commande.validee_par_client:
        commande.validee_par_client = True
        commande.date_validation_client = timezone.now()
        champs += ['validee_par_client', 'date_validation_client']
    commande.save(update_fields=champs)
    logger.info("Commande %s marquée payée (%s).", commande.pk, par)


def synchroniser(commande_id, delai_anti_spam=8):
    """Interroge le fournisseur et met la commande à jour. Retourne la commande à jour.

    On ne fait JAMAIS confiance à ce que le navigateur ou un webhook annonce : seule la réponse
    du fournisseur (appel authentifié avec nos clés) fait foi.
    """
    commande = Commande.objects.get(pk=commande_id)
    if not commande.paiement_en_ligne or not commande.reference_paiement:
        return commande
    if commande.statut_paiement in ('paye', 'rembourse'):
        return commande
    if not cache.add(f'paiement-verif-{commande.pk}', 1, delai_anti_spam):
        return commande  # vérifié il y a quelques secondes (évite de saturer l'API du fournisseur)

    try:
        verification = obtenir(commande.mode_paiement).verifier(commande.reference_paiement)
    except ErreurPaiement as e:
        logger.warning("Vérification du paiement impossible (commande %s) : %s", commande.pk, e)
        return commande

    with transaction.atomic():
        commande = Commande.objects.select_for_update().get(pk=commande_id)
        if commande.statut_paiement in ('paye', 'rembourse'):
            return commande
        if verification.statut == 'paye':
            attendu = en_millimes(commande.total)
            if verification.montant_millimes is not None and verification.montant_millimes != attendu:
                # Anormal : on n'enregistre rien automatiquement, l'admin contrôle chez le fournisseur.
                logger.error("Montant inattendu (commande %s) : reçu %s, attendu %s millimes. Contrôle manuel requis.",
                             commande.pk, verification.montant_millimes, attendu)
                return commande
            marquer_paye(commande)
        elif verification.statut == 'echoue' and commande.statut_paiement == 'en_attente':
            commande.statut_paiement = 'echoue'
            commande.save(update_fields=['statut_paiement', 'date_maj'])
    return commande
