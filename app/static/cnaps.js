// app/static/cnaps.js
// Petites fonctions utilitaires communes (statuts / erreurs)
export function showError(msg) {
  const el = document.getElementById("error-status");
  if (!el) return;
  el.textContent = "❌ " + (msg || "Erreur");
  el.style.display = "block";
}
export function showOk(msg) {
  const el = document.getElementById("upload-status");
  if (!el) return;
  el.textContent = "✅ " + (msg || "OK");
  el.style.display = "block";
}
