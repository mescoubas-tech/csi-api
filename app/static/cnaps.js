// Helpers
const $  = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

// Etat courant : tuile active (dernière où des fichiers ont été choisis)
let ACTIVE_KEY = "planning";

document.addEventListener("DOMContentLoaded", () => {
  const btnAnalyze = $("#btnAnalyze");
  const btnExport  = $("#btnExport");
  const out        = $("#output");

  // Année pied de page
  const y = $("#year"); if (y) y.textContent = new Date().getFullYear();

  // Ajoute .jpeg et .jpg à tous les inputs (sans casser l'existant)
  $$('input[type="file"]').forEach(input => {
    const current = (input.getAttribute('accept') || '').trim();
    const extra = '.jpeg,.jpg';
    if (!current) {
      input.setAttribute('accept', extra);
    } else if (!current.includes('.jpeg') && !current.includes('.jpg')) {
      input.setAttribute('accept', current + ',' + extra);
    }
  });

  // Assure la présence du badge ✓ dans chaque tuile (si manquant)
  $$(".tile").forEach(tile => {
    const head = $(".tile-head", tile);
    if (head && !$(".ok", head)) {
      const ok = document.createElement("span");
      ok.className = "ok";
      ok.textContent = "✔";
      ok.hidden = true;
      head.appendChild(ok);
    }
  });

  // Noms lisibles pour le bouton Analyser
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

  function setAnalyzeLabel(key) {
    const lib = LABELS[key] || "la sélection";
    btnAnalyze.textContent = `Analyser ${lib}`;
    ACTIVE_KEY = key;

    // Export PDF uniquement pour plannings
    const enableExport = key === "planning";
    btnExport.disabled = !enableExport;
    btnExport.title    = enableExport ? "" : "Export PDF disponible uniquement pour les plannings";
    btnExport.classList.toggle("disabled", !enableExport);
  }

  // Affiche nom(s) fichier(s) + coche verte + devient tuile active
  $$(".tile").forEach(tile => {
    const input  = $("input[type=file]", tile);
    const nameEl = $(".file-name", tile);
    const ok     = $(".ok", tile);

    if (!input) return;

    input.addEventListener("change", () => {
      const files = Array.from(input.files || []);
      if (nameEl) {
        nameEl.textContent = files.map(f => f.name).join(", ") || "aucun fichier sélectionné";
      }
      if (ok) ok.hidden = files.length === 0;

      if (files.length > 0) {
        setAnalyzeLabel(tile.dataset.key);
      }
    });
  });

  // Label initial
  setAnalyzeLabel(ACTIVE_KEY);

  // --- Action ANALYZE ---
  btnAnalyze.addEventListener("click", async () => {
    const tile  = $(`.tile[data-key="${ACTIVE_KEY}"]`);
    const input = tile ? $('input[type=file]', tile) : null;
    if (!out) return;

    out.hidden  = false;

    if (!input || !input.files || input.files.length === 0) {
      out.textContent = "Veuillez sélectionner un fichier pour cette rubrique.";
      return;
    }

    // Cas PLANNING : on POSTe et on ouvre la page de résultat dans un nouvel onglet
    if (ACTIVE_KEY === "planning") {
      try {
        out.textContent = "Analyse en cours…";
        const form = new FormData();
        form.append("file", input.files[0]);

        const r = await fetch("/planning/analyze/html", { method: "POST", body: form });
        const html = await r.text();

        if (!r.ok) {
          out.textContent = `Erreur d'analyse: ${html}`;
          return;
        }

        const win = window.open("", "_blank");
        if (!win) {
          out.textContent = "La fenêtre de résultat a été bloquée par le navigateur. Autorisez les pop-ups pour ce site.";
          return;
        }
        win.document.open();
        win.document.write(html);
        win.document.close();

        out.textContent = "Rapport ouvert dans un nouvel onglet.";
      } catch (e) {
        out.textContent = "Erreur: " + (e && e.message ? e.message : e);
      }
      return;
    }

    // Autres rubriques : message temporaire (branchements futurs)
    out.textContent = `Analyse pour « ${LABELS[ACTIVE_KEY] || ACTIVE_KEY} » : bientôt disponible.`;
  });

  // --- Action EXPORT (PDF pour plannings) ---
  btnExport.addEventListener("click", async () => {
    const tile  = $('.tile[data-key="planning"]');
    const input = tile ? $('input[type=file]', tile) : null;
    if (!out) return;

    out.hidden  = false;

    if (btnExport.disabled) {
      out.textContent = "L’export PDF est disponible uniquement pour les plannings.";
      return;
    }
    if (!input || !input.files || input.files.length === 0) {
      out.textContent = "Veuillez sélectionner un fichier de planning.";
      return;
    }

    try {
      out.textContent = "Génération du rapport…";
      const form = new FormData();
      form.append("file", input.files[0]);
      const r = await fetch("/planning/export/report", { method: "POST", body: form });
      if (!r.ok) { out.textContent = "Erreur: " + (await r.text()); return; }
      const blob = await r.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = 'rapport_audit_plannings.pdf'; a.click();
      out.textContent = "Rapport téléchargé.";
    } catch (e) {
      out.textContent = "Erreur: " + (e && e.message ? e.message : e);
    }
  });
});
