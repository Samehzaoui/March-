import re

from django.core.exceptions import ValidationError

_LETTRE_ARABE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')


def valider_arabe(valeur):
    """Le nom en arabe doit contenir au moins une lettre arabe (évite de coller le nom français par erreur)."""
    if valeur and not _LETTRE_ARABE.search(valeur):
        raise ValidationError("Écrivez ce nom en lettres arabes (ex : طماطم).", code='pas_arabe')
