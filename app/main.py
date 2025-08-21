from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# === Création du dossier static si absent ===
if not os.path.exists("static"):
    os.makedirs("static")

# Montage des fichiers statiques (CSS, images, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


# === PAGE D'ACCUEIL ===
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Contrôle Sécurité</title>
        <link rel="stylesheet" href="/static/cnaps.css">
    </head>
    <body>
        <div class="container">
            <h1>🛡️ Contrôle Sécurité</h1>
            <p>Analysez vos documents en toute simplicité.</p>

            <form id="uploadForm">
                <input type="file" id="fileInput" name="file" accept=".pdf,.png,.jpg" required>
                <button type="submit">Analyser</button>
            </form>

            <div id="result"></div>
        </div>

        <script>
        const form = document.getElementById("uploadForm");
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById("fileInput");
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);

            const res = await fetch("/analyze", {
                method: "POST",
                body: formData
            });

            const data = await res.json();
            document.getElementById("result").innerHTML =
                "<h3>Résultat :</h3><pre>" + JSON.stringify(data, null, 2) + "</pre>";
        });
        </script>
    </body>
    </html>
    """


# === STATUS (HEALTHCHECK) ===
@app.get("/status")
async def status():
    return {"status": "ok", "service": "csi-api"}


# === ANALYSE (Upload de fichier PDF ou image) ===
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        content = await file.read()
        size_kb = len(content) / 1024
        return {
            "filename": file.filename,
            "size_kb": round(size_kb, 2),
            "status": "fichier reçu et analysé"
        }
    except Exception as e:
        return {"error": str(e)}
