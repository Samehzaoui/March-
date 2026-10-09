from django.core.management.base import BaseCommand

from boutique.models import Produit
from boutique.noms_arabes import nom_arabe_pour


class Command(BaseCommand):
    help = ("Remplit le « Nom en arabe » des produits de démonstration (tomate, oignon, orange...). "
            "Ne modifie jamais un nom arabe déjà saisi, sauf avec --ecraser.")

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Affiche ce qui serait fait, sans rien écrire.")
        parser.add_argument('--ecraser', action='store_true', help="Remplace aussi les noms arabes déjà saisis.")

    def handle(self, *args, **options):
        a_faire, deja, inconnus = [], 0, []
        for produit in Produit.objects.all().order_by('nom'):
            suggestion = nom_arabe_pour(produit.nom)
            if not suggestion:
                inconnus.append(produit.nom)
            elif produit.nom_ar and not options['ecraser']:
                deja += 1
            elif produit.nom_ar != suggestion:
                a_faire.append((produit, suggestion))

        for produit, suggestion in a_faire:
            self.stdout.write(f"  {produit.nom:34s} -> {suggestion}")
            if not options['dry_run']:
                produit.nom_ar = suggestion
                produit.save()          # save() : le cache du catalogue est vidé automatiquement

        verbe = "à remplir" if options['dry_run'] else "remplis"
        self.stdout.write(self.style.SUCCESS(f"\n{len(a_faire)} nom(s) arabe(s) {verbe}, {deja} déjà saisi(s) (conservés)."))
        if inconnus:
            self.stdout.write(self.style.WARNING(
                f"{len(inconnus)} produit(s) sans suggestion, à compléter dans le dashboard : " + ", ".join(inconnus)))
        if options['dry_run']:
            self.stdout.write("(mode --dry-run : rien n'a été écrit)")
