from django import forms
from .models import Avis, Commande, Coupon, Produit, Categorie, MoyenPaiement, ImageAccueil


class CommandeForm(forms.ModelForm):
    """Formulaire de commande.

    - Client connecté par SMS : son numéro vérifié est utilisé (champ masqué).
    - Client connecté par email / Google / Facebook / Apple : il saisit un mobile
      tunisien, qui recevra le code SMS de validation de la commande.
    """
    class Meta:
        model = Commande
        fields = ['nom_client', 'telephone', 'email', 'gouvernorat', 'adresse', 'note']
        widgets = {
            'nom_client': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom et prénom'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '22 123 456', 'inputmode': 'numeric'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'exemple@mail.com'}),
            'gouvernorat': forms.Select(attrs={'class': 'form-select'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Rue, ville, code postal'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Instructions de livraison (optionnel)'}),
        }

    def __init__(self, *args, telephone_verifie=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.telephone_verifie = telephone_verifie
        if telephone_verifie:
            del self.fields['telephone']
        else:
            self.fields['telephone'].required = True
            self.fields['telephone'].label = "Téléphone mobile"
            self.fields['telephone'].help_text = "Un code de validation vous sera envoyé par SMS à ce numéro."

    def clean_telephone(self):
        from comptes.services import normaliser_telephone
        tel = normaliser_telephone(self.cleaned_data.get('telephone', ''))
        if not tel:
            raise forms.ValidationError("Numéro invalide. Entrez un mobile tunisien à 8 chiffres (ex : 22 123 456).")
        return tel


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = ['categorie', 'nom', 'slug', 'description', 'image', 'prix', 'unite',
                  'stock', 'origine', 'bio', 'disponible']
        widgets = {
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'genere-automatiquement-si-vide'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'prix': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'unite': forms.Select(attrs={'class': 'form-select'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'origine': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'disponible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {'slug': None}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class MoyenPaiementForm(forms.ModelForm):
    class Meta:
        model = MoyenPaiement
        fields = ['nom', 'logo', 'ordre', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Visa, D17, BH Bank...'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ImageAccueilForm(forms.ModelForm):
    class Meta:
        model = ImageAccueil
        fields = ['titre', 'image', 'ordre', 'actif']
        widgets = {
            'titre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optionnel'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ['nom', 'slug', 'type_produit', 'image']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'genere-automatiquement-si-vide'}),
            'type_produit': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class AvisForm(forms.ModelForm):
    note = forms.TypedChoiceField(
        label="Votre note", coerce=int, choices=[(i, str(i)) for i in range(5, 0, -1)],
        error_messages={'required': "Choisissez une note de 1 à 5 étoiles.",
                        'invalid_choice': "Choisissez une note de 1 à 5 étoiles."},
    )

    class Meta:
        model = Avis
        fields = ['note', 'commentaire']
        widgets = {
            'commentaire': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'maxlength': 1000,
                                                 'placeholder': "Votre expérience avec ce produit (facultatif)"}),
        }


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'description', 'type_remise', 'valeur', 'montant_minimum',
                  'date_debut', 'date_fin', 'utilisations_max', 'utilisations_par_client', 'actif']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'BIENVENUE10'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usage interne (facultatif)'}),
            'type_remise': forms.Select(attrs={'class': 'form-select'}),
            'valeur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'montant_minimum': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'date_debut': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'date_fin': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'utilisations_max': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'utilisations_par_client': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nom in ('date_debut', 'date_fin'):
            self.fields[nom].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d']

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()
