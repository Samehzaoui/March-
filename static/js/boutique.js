/* 9offty : sélecteur de quantité (− / +) et animation du bouton « Ajouter au panier ». */
(function () {
  'use strict';

  var mouvementReduit = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Quantité ---------- */
  function initialiserQuantite(bloc) {
    var champ = bloc.querySelector('input[type="number"]');
    var moins = bloc.querySelector('[data-qte-moins]');
    var plus = bloc.querySelector('[data-qte-plus]');
    if (!champ || !moins || !plus) return;
    var min = parseInt(champ.min, 10) || 1;
    var max = champ.max ? parseInt(champ.max, 10) : Infinity;

    function valeur() {
      var v = parseInt(champ.value, 10);
      return isNaN(v) ? min : v;
    }
    function majBoutons() {
      moins.disabled = valeur() <= min;
      plus.disabled = valeur() >= max;
    }
    function corriger() {
      champ.value = Math.min(Math.max(valeur(), min), max);
      majBoutons();
    }
    moins.addEventListener('click', function () { champ.value = valeur() - 1; corriger(); });
    plus.addEventListener('click', function () { champ.value = valeur() + 1; corriger(); });
    champ.addEventListener('input', majBoutons);
    champ.addEventListener('change', corriger);
    champ.addEventListener('blur', corriger);
    moins.hidden = false;       /* sans JavaScript, seul le champ numérique reste visible et utilisable */
    plus.hidden = false;
    corriger();
  }

  /* ---------- Animation d'ajout : le colis tombe dans le panier, puis la page se recharge ---------- */
  document.addEventListener('submit', function (e) {
    var formulaire = e.target;
    if (!formulaire.matches || !formulaire.matches('[data-ajout-anime]')) return;
    if (formulaire.dataset.envoye === '1') { e.preventDefault(); return; }      /* anti double-clic */
    formulaire.dataset.envoye = '1';
    var bouton = formulaire.querySelector('.btn-ajouter');
    if (mouvementReduit || !bouton) return;                                      /* envoi immédiat */
    e.preventDefault();
    bouton.classList.add('is-added');
    setTimeout(function () { formulaire.submit(); }, 550);
  });

  /* Retour arrière du navigateur : on remet les boutons à zéro. */
  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    document.querySelectorAll('[data-ajout-anime]').forEach(function (f) {
      delete f.dataset.envoye;
      var b = f.querySelector('.btn-ajouter');
      if (b) b.classList.remove('is-added');
    });
  });

  function demarrer() { document.querySelectorAll('[data-qte]').forEach(initialiserQuantite); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer);
  else demarrer();
})();
