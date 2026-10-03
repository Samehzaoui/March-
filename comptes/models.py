from django.conf import settings
from django.db import models


class ProfilClient(models.Model):
    """Compte client identifié par son numéro de mobile (connexion par code SMS)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='profil', on_delete=models.CASCADE)
    telephone = models.CharField(max_length=20, unique=True, help_text="Format international : +216XXXXXXXX")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Profil client"
        verbose_name_plural = "Profils clients"

    def __str__(self):
        return self.telephone


class CodeSMS(models.Model):
    """Code à usage unique envoyé par SMS. Seule l'empreinte (HMAC) du code est stockée."""
    OBJET_CONNEXION = 'connexion'
    OBJET_COMMANDE = 'commande'
    OBJET_CHOICES = [
        (OBJET_CONNEXION, 'Connexion'),
        (OBJET_COMMANDE, 'Validation de commande'),
    ]

    telephone = models.CharField(max_length=20, db_index=True)
    objet = models.CharField(max_length=20, choices=OBJET_CHOICES)
    commande = models.ForeignKey('boutique.Commande', null=True, blank=True,
                                 on_delete=models.CASCADE, related_name='codes_sms')
    code_hash = models.CharField(max_length=64)
    cree_le = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateTimeField()
    tentatives = models.PositiveSmallIntegerField(default=0)
    utilise = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Code SMS"
        verbose_name_plural = "Codes SMS"
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.get_objet_display()} - {self.telephone} ({self.cree_le:%d/%m/%Y %H:%M})"
