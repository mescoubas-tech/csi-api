// Helpers
const $  = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

document.addEventListener("DOMContentLoaded", () => {
  $("#year").textContent = new Date().getFullYear();

  // Mapping "clé tuile" -> libellé bouton + endpoints (si dispo)
  const LABELS = {
    aut: "l’autorisation d’exercer",
    agd: "l’agrément dirigeant",
    aap: "l’attestation d’assurance professionnelle",
    kbis: "l’extrait Kbis",
    statuts: "les statuts de l’entreprise",
    dsn: "les déclarations sociales nominatives (DSN)",
    urssaf_vigilance: "l’attestation de vigilance URSSAF",
    releves: "les relevés de comptes",
    liasse: "la dernière liasse fiscale",
    grand_livre: "le grand livre de comptes",
    planning: "les plannings",
    paie: "les bulletins de paie",
    factures: "les factures",
    sous_traitants_liste: "la liste des sous-traitants",
    sous_traitants_vigilance: "les attestations URSSAF des sous-traitants",
    contrats_st: "les contrats de sous-traitance",
    carte_pro_modele: "le modèle de carte professionnelle",
    rup: "le registre unique du personnel",
    rci: "le registre des contrôles internes",
    dpae: "les justificatifs DPAE",
    factures_st: "les factures des sous-traitants",
  };

  // Seuls les plannings sont branchés pour le moment
  const ENDPOINTS = {
    planning: {
      analyze: "/planning/analyze",
      export:  "/planning/export/report",
    },
    // d'autres viendront ici: dsn: { analyze: "/dsn/analyze", ... }
  };

  // Etat courant : dernière tuile qui a reçu un fichier
  let ACTIVE_KEY = "planning";

  const btnAnalyze = $("#btnAnalyze");
  const btnExport  = $("#btnExport");
  const out        = $("#output");

  function setAnalyzeLabel(key) {
    const lib = LABELS[key] || "la sélection";
    btnAnalyze.textContent = `Analyser ${lib}`;
    ACTIVE_KEY = key;

    // Export PDF uniquement pour les plannings
    const enableExport = key === "planning";
    btnExport.disabled = !enableExport;
    btnExport.title    = enableExport ? "" : "Export PDF disponible pour les plannings";
    btnExport.classList.toggle("disabled", !enableExport);
  }

  // Affiche le nom + coche verte quand on choisit un fichier,
  // et devient la tuile active (donc le bouton change).
  $$(".tile").forEach(tile => {
    const input  = $("input[type=file]", tile);
    const nameEl = $(".file-name", tile);
    const ok     = $(".ok", tile);

    input.addEventListener("change", () => {
      const files = Array.from(input.files || []);
      nameEl.textContent = files.map(f => f.name).join(", ") || "aucun fichier sélectionné";
      if (ok) ok.hidden = files.length === 0;

      // si on a sélectionné au moins un fichier, cette tuile devient l'action courante
      if (files.length > 0) {
        setAnalyzeLabel(tile.dataset.key);
      }
    });
  });

  // Label initial (plannings par défaut)
  setAnalyzeLabel(ACTIVE_KEY);

  // --- Action ANALYZE (dynamique) ---
  btnAnalyze.addEventListener("click", async () => {
    const tile  = $(`.tile[data-key="${ACTIVE_KEY}"]`);
    const input = $('input[type=file]', tile);
    out.hidden  = false;

    if (!input.files || input.files.length === 0) {
      out.textContent = "Veuillez sélectionner un fichier pour cette rubrique.";
      return;
    }

    // Endpoint ?
    const cfg = ENDPOINTS[ACTIVE_KEY];
    if (!cfg || !cfg.analyze) {
      out.textContent = `Analyse pour « ${LABELS[ACTIVE_KEY] || ACTIVE_KEY} » : bientôt disponible.`;
      return;
    }

    // Envoi
    try {
      out.textContent = "Analyse en cours…";
      const form = new FormData();
      form.append("file", input.files[0]); // 1 fichier pour l’instant

      const r = await fetch(cfg.analyze, { method: "POST", body: form });
      const t = await r.text();
      try { out.textContent = JSON.stringify(JSON.parse(t), null, 2); }
      catch { out.textContent = t; }
    } catch (e) {
      out.textContent = "Erreur: " + e.message;
    }
  });

  // --- Action EXPORT (seulement plannings) ---
  btnExport.addEventListener("click", async () => {
    const tile  = $('.tile[data-key="planning"]');
    const input = $('input[type=file]', tile);
    out.hidden  = false;

    if (btnExport.disabled) {
      out.textContent = "L’export PDF est disponible uniquement pour les plannings.";
      return;
    }
    if (!input.files || input.files.length === 0) {
      out.textContent = "Veuillez sélectionner un fichier de planning.";
      return;
    }

    try {
      out.textContent = "Génération du rapport…";
      const form = new FormData();
      form.append("file", input.files[0]);
      const r = await fetch(ENDPOINTS.planning.export, { method: "POST", body: form });
      if (!r.ok) { out.textContent = "Erreur: " + await r.text(); return; }
      const blob = await r.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = 'rapport_audit_plannings.pdf'; a.click();
      out.textContent = "Rapport téléchargé.";
    } catch (e) {
      out.textContent = "Erreur: " + e.message;
    }
  });
});
.btn.disabled,
button:disabled {
  opacity: .5;
  cursor: not-allowed;
}
