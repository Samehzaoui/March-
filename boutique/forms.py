from django import forms
from .models import Commande, Produit, Categorie, MoyenPaiement, ImageAccueil


class CommandeForm(forms.ModelForm):
    class Meta:
        model = Commande
        fields = ['nom_client', 'telephone', 'email', 'gouvernorat', 'adresse', 'note']
        widgets = {
            'nom_client': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom et prénom'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+216 ..........'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'exemple@mail.com'}),
            'gouvernorat': forms.Select(attrs={'class': 'form-select'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Rue, ville, code postal'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Instructions de livraison (optionnel)'}),
        }


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
