@router.post("/planning/export/report")
async def post_export_report(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df = load_schedule(content, file.filename)
        result = analyze(df)

        # Génère le PDF en mémoire
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
        from reportlab.lib.utils import simpleSplit
        from datetime import datetime

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        W, H = A4
        margin = 2*cm
        y = H - margin

        def wrap(text, width, font="Helvetica", size=10):
            return simpleSplit(text, font, size, width)

        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, "Rapport d'audit — Plannings")
        c.setFont("Helvetica", 10)
        c.drawRightString(W - margin, y, datetime.now().strftime("%Y-%m-%d %H:%M"))
        y -= 1.2*cm

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "Synthèse"); y -= 0.6*cm
        c.setFont("Helvetica", 10)
        lines = [
            f"Agents analysés : {result.summary.agents}",
            f"Jours couverts  : {result.summary.days}",
            f"Heures effectives totales : {result.summary.total_hours_effective:.2f} h",
            f"Heures de nuit totales     : {result.summary.total_hours_night:.2f} h",
            f"Nombre d'alertes : {result.summary.alerts_count}",
        ]
        for line in lines:
            c.drawString(margin, y, line); y -= 0.5*cm
        y -= 0.3*cm

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "Alertes"); y -= 0.6*cm
        c.setFont("Helvetica", 10)

        for idx, a in enumerate(result.alerts, start=1):
            block = f"""{idx}. [{a.severity.upper()}] {a.rule_id} — Agent {a.agent_id} — Date: {a.date or '-'}
{a.message}
Preuves: {a.evidence}"""
            for ln in wrap(block, W - 2*margin):
                if y < margin:
                    c.showPage(); y = H - margin; c.setFont("Helvetica", 10)
                c.drawString(margin, y, ln); y -= 0.45*cm
            y -= 0.2*cm

        c.showPage()
        c.save()
        buf.seek(0)

        return StreamingResponse(buf, media_type="application/pdf", headers={
            "Content-Disposition": 'attachment; filename="rapport_audit.pdf"'
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
