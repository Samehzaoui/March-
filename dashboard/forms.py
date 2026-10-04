from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from allauth.account.models import EmailAddress

from comptes.models import ProfilClient
from comptes.services import normaliser_telephone

User = get_user_model()


class ClientCreationForm(forms.Form):
    """Création d'un compte client depuis le dashboard.

    Le client pourra ensuite se connecter par SMS (si un téléphone est saisi),
    par email + mot de passe (si email et mot de passe sont saisis) ou
    via « mot de passe oublié ».
    """
    first_name = forms.CharField(label="Prénom", max_length=150,
                                 widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}))
    last_name = forms.CharField(label="Nom", max_length=150,
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label="Email", required=False,
                             widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'client@exemple.com'}))
    telephone = forms.CharField(label="Téléphone mobile", required=False,
                                widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '22 123 456',
                                                              'inputmode': 'numeric'}),
                                help_text="Numéro tunisien à 8 chiffres : permet la connexion par code SMS.")
    password1 = forms.CharField(label="Mot de passe", required=False, strip=False,
                                widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
                                help_text="Facultatif. Sans mot de passe, le client se connecte par SMS ou via « mot de passe oublié ».")
    password2 = forms.CharField(label="Confirmer le mot de passe", required=False, strip=False,
                                widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}))
    is_active = forms.BooleanField(label="Compte actif", required=False, initial=True,
                                   widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and (User.objects.filter(email__iexact=email).exists()
                      or EmailAddress.objects.filter(email__iexact=email).exists()):
            raise ValidationError("Un compte existe déjà avec cet email.")
        return email

    def clean_telephone(self):
        brut = self.cleaned_data.get('telephone', '').strip()
        if not brut:
            return ''
        tel = normaliser_telephone(brut)
        if not tel:
            raise ValidationError("Numéro invalide. Entrez un mobile tunisien à 8 chiffres (ex : 22 123 456).")
        if ProfilClient.objects.filter(telephone=tel).exists():
            raise ValidationError("Un compte existe déjà avec ce numéro.")
        return tel

    def clean(self):
        data = super().clean()
        email, tel = data.get('email'), data.get('telephone')
        p1, p2 = data.get('password1', ''), data.get('password2', '')

        if not self.errors.get('email') and not self.errors.get('telephone') and not email and not tel:
            raise ValidationError("Renseignez au moins un email ou un numéro de téléphone.")

        if p1 or p2:
            if p1 != p2:
                self.add_error('password2', "Les deux mots de passe ne correspondent pas.")
            elif not email:
                self.add_error('password1', "Un mot de passe nécessite un email (identifiant de connexion).")
            else:
                provisoire = User(username=email, email=email,
                                  first_name=data.get('first_name', ''), last_name=data.get('last_name', ''))
                try:
                    validate_password(p1, provisoire)
                except ValidationError as e:
                    self.add_error('password1', e)

        identifiant = self._identifiant(email, tel)
        if identifiant and User.objects.filter(username__iexact=identifiant).exists():
            raise ValidationError("Un compte utilise déjà cet identifiant.")
        return data

    @staticmethod
    def _identifiant(email, tel):
        if email:
            return email
        if tel:
            return f"tel{tel.lstrip('+')}"  # même format que les comptes créés par SMS
        return ''

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = User(username=self._identifiant(d['email'], d['telephone']), email=d['email'],
                    first_name=d['first_name'], last_name=d['last_name'],
                    is_active=d['is_active'], is_staff=False, is_superuser=False)
        if d['password1']:
            user.set_password(d['password1'])
        else:
            user.set_unusable_password()
        user.save()
        if d['telephone']:
            ProfilClient.objects.create(user=user, telephone=d['telephone'])
        if d['email']:
            EmailAddress.objects.create(user=user, email=d['email'], primary=True, verified=False)
        return user
