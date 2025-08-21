// petit utilitaire
const $ = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => Array.from(root.querySelectorAll(sel));

document.addEventListener("DOMContentLoaded", () => {
  $("#year").textContent = new Date().getFullYear();

  // Affiche le nom et coche ✓ quand un fichier est choisi
  $$(".tile").forEach(tile => {
    const input = $("input[type=file]", tile);
    const nameBox = $(".file-name", tile);
    const ok = $(".ok", tile);
    input.addEventListener("change", () => {
      const files = Array.from(input.files || []);
      nameBox.textContent = files.map(f => f.name).join(", ");
      if (ok) ok.hidden = files.length === 0;
    });
  });

  // Analyse PLANNING
  $("#btnAnalyze").addEventListener("click", async () => {
    const tile = $('.tile[data-key="planning"]');
    const input = $('input[type=file]', tile);
    const out = $("#output");
    out.hidden = false;
    out.textContent = "Analyse en cours…";
    if (!input.files || input.files.length === 0) {
      out.textContent = "Veuillez sélectionner un fichier de planning.";
      return;
    }
    const form = new FormData();
    form.append("file", input.files[0]);
    try {
      const r = await fetch("/planning/analyze", { method: "POST", body: form });
      const t = await r.text();
      try { out.textContent = JSON.stringify(JSON.parse(t), null, 2); }
      catch { out.textContent = t; }
    } catch (e) {
      out.textContent = "Erreur: " + e.message;
    }
  });

  // Export rapport PDF (à partir du même fichier planning)
  $("#btnExport").addEventListener("click", async () => {
    const tile = $('.tile[data-key="planning"]');
    const input = $('input[type=file]', tile);
    const out = $("#output");
    out.hidden = false;
    out.textContent = "Génération du rapport…";
    if (!input.files || input.files.length === 0) {
      out.textContent = "Veuillez sélectionner un fichier de planning.";
      return;
    }
    const form = new FormData();
    form.append("file", input.files[0]);
    try {
      const r = await fetch("/planning/export/report", { method: "POST", body: form });
      if (!r.ok) { out.textContent = "Erreur: " + await r.text(); return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'rapport_audit_plannings.pdf'; a.click();
      out.textContent = "Rapport téléchargé.";
    } catch (e) {
      out.textContent = "Erreur: " + e.message;
    }
  });
});
