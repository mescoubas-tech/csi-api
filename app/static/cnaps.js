// app/static/cnaps.js

// ----------- Petits helpers DOM -----------
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// Tuile active par défaut (sera mise à jour quand on choisit un fichier)
let ACTIVE_KEY = "planning";

document.addEventListener("DOMContentLoaded", () => {
  const btnAnalyze = $("#btnAnalyze");
  const btnExport  = $("#btnExport");
  const out        = $("#output");

  // Année en pied de page si présente
  const year = $("#year");
  if (year) year.textContent = String(new Date().getFullYear());

  // Autoriser aussi .jpeg / .jpg partout
  $$('input[type="file"]').forEach(input => {
    const current = (input.getAttribute("accept") || "").trim();
    const extra = ".jpeg,.jpg";
    if (!current) {
      input.setAttribute("accept", extra);
    } else if (!current.includes(".jpeg") && !current.includes(".jpg")) {
      input.setAttribute("accept", current + "," + extra);
    }
  });

  // S'assurer que chaque tuile possède un badge ✓ (caché par défaut)
  $$(".tile").forEach(tile => {
    const head = $(".tile-head", tile);
    if (!head) return;
    if (!$(".ok", head)) {
      const ok = document.createElement("span");
      ok.className = "ok";
      ok.textContent = "✔";
      ok.hidden = true;
      head.appendChild(ok);
    }
  });

  // Dictionnaire pour étiqueter le bouton Analyser dynamiquement
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
    if (btnAnalyze) btnAnalyze.textContent = `Analyser ${lib}`;
    ACTIVE_KEY = key;

    // Export PDF uniquement pour les plannings
    const enableExport = key === "planning";
    if (btnExport) {
      btnExport.disabled = !enableExport;
      btnExport.title = enableExport ? "" : "Export PDF disponible uniquement pour les plannings";
      btnExport.classList.toggle("disabled", !enableExport);
    }
  }

  // Gestion des changements de fichier pour chaque tuile
  $$(".tile").forEach(tile => {
    const input  = $('input[type="file"]', tile);
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

  // Libellé initial
  setAnalyzeLabel(ACTIVE_KEY);

  // ----------- Bouton Analyser -----------
  if (btnAnalyze) {
    btnAnalyze.addEventListener("click", async () => {
      const tile  = $(`.tile[data-key="${ACTIVE_KEY}"]`);
      const input = tile ? $('input[type="file"]', tile) : null;
      if (!out) return;

      out.hidden = false;

      if (!input || !input.files || input.files.length === 0) {
        out.textContent = "Veuillez sélectionner un fichier pour cette rubrique.";
        return;
      }

      // Cas PLANNING : ouvrir d'abord l'onglet (politique pop-up Safari/Chrome),
      // ensuite fetch et injection du HTML.
      if (ACTIVE_KEY === "planning") {
        const win = window.open("about:blank", "_blank");
        if (!win) {
          out.textContent = "La fenêtre de résultat a été bloquée. Autorisez les pop-ups pour ce site.";
          return;
        }
        try {
          // Écran de chargement
          win.document.open();
          win.document.write(`
            <!doctype html>
            <meta charset="utf-8">
            <title>Analyse des plannings — chargement…</title>
            <style>
              body{font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:32px;color:#111;background:#fff}
              .muted{color:#666}
            </style>
            <h1>Analyse des plannings</h1>
            <p class="muted">Chargement en cours…</p>
          `);
          win.document.close();

          out.textContent = "Analyse en cours…";
          const form = new FormData();
          form.append("file", input.files[0]);

          const resp = await fetch("/planning/analyze/html", { method: "POST", body: form });
          const html = await resp.text();

          if (!resp.ok) {
            win.document.open();
            win.document.write(`<pre style="white-space:pre-wrap;color:#b00020">${html}</pre>`);
            win.document.close();
            out.textContent = "Erreur d'analyse: " + html;
            return;
          }

          win.document.open();
          win.document.write(html);
          win.document.close();

          out.textContent = "Rapport ouvert dans un nouvel onglet.";
        } catch (e) {
          const msg = (e && e.message) ? e.message : String(e);
          try {
            win.document.open();
            win.document.write(`<pre style="white-space:pre-wrap;color:#b00020">Erreur: ${msg}</pre>`);
            win.document.close();
          } catch (_) { /* ignore */ }
          out.textContent = "Erreur: " + msg;
        }
        return;
      }

      // Autres rubriques : placeholder pour futures analyses spécifiques
      out.textContent = "Analyse pour cette rubrique : bientôt disponible.";
    });
  }

  // ----------- Bouton Export PDF (plannings) -----------
  if (btnExport) {
    btnExport.addEventListener("click", async () => {
      const tile  = $('.tile[data-key="planning"]');
      const input = tile ? $('input[type="file"]', tile) : null;
      if (!out) return;

      out.hidden = false;

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
        if (!r.ok) {
          out.textContent = "Erreur: " + (await r.text());
          return;
        }

        const blob = await r.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement("a");
        a.href = url;
        a.download = "rapport_audit_plannings.pdf";
        a.click();

        out.textContent = "Rapport téléchargé.";
      } catch (e) {
        out.textContent = "Erreur: " + (e && e.message ? e.message : e);
      }
    });
  }
});
