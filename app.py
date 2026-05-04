import os
import json
import re
from io import BytesIO
from flask import Flask, request, Response
from flask_cors import CORS
from openai import OpenAI

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

import docx
import PyPDF2

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(name="BodySmall", fontSize=9, leading=12))
styles.add(ParagraphStyle(name="Section", fontSize=11, leading=14, spaceAfter=6))
styles.add(ParagraphStyle(name="Right", alignment=TA_RIGHT))
styles.add(ParagraphStyle(name="Name", fontSize=16, leading=18))
styles.add(ParagraphStyle(name="Cargo", fontSize=12, leading=14))


# =========================
# EXTRAER TEXTO
# =========================

def extraer_texto(file):
    if not file:
        return ""

    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".docx"):
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])

        elif filename.endswith(".pdf"):
            reader = PyPDF2.PdfReader(file)
            texto = ""
            for page in reader.pages:
                texto += page.extract_text() or ""
            return texto
    except:
        pass

    return ""


# =========================
# PREPROCESAR
# =========================

def preprocesar_cv(texto):
    lineas = [re.sub(r"\s+", " ", l.strip()) for l in texto.split("\n") if l.strip()]
    return "\n".join(lineas[:2000])


# =========================
# LIMPIAR LISTAS
# =========================

def limpiar_lista(lista):
    resultado = []
    for item in lista:
        if isinstance(item, dict):
            texto = " - ".join([str(v) for v in item.values() if v])
            resultado.append(texto)
        else:
            resultado.append(str(item))
    return resultado


# =========================
# IA INTELIGENTE
# =========================

def mejorar_cv(texto_cv, info_extra):

    prompt = f"""
Eres un especialista en reclutamiento técnico industrial.

Tu tarea es MEJORAR un CV real.

REGLAS:
- NO inventar información
- NO eliminar experiencia relevante
- NO usar texto genérico
- NO usar empresas ficticias

CRITERIOS CLAVE:
- Si hay muchas experiencias similares → AGRUPARLAS
- Ejemplo:
  "Experiencia en empresas como X, Y, Z desempeñándose como Soldador"
- Priorizar claridad sobre cantidad
- Mantener lo importante
- No hacer listas interminables

OBJETIVO:
- Facilitar lectura para reclutador
- Mostrar experiencia real
- Hacerlo claro y ordenado

CV:
{texto_cv}

INFO EXTRA:
{info_extra}

Devuelve JSON:

{{
"perfil": "...",
"formacion": ["..."],
"experiencia": ["..."],
"certificaciones": ["..."],
"competencias": ["..."],
"info_relevante": "..."
}}
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        contenido = r.choices[0].message.content.strip()
        contenido = contenido.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(contenido)
        except:
            data = {}

    except:
        data = {}

    if not isinstance(data, dict):
        data = {}

    data["perfil"] = str(data.get("perfil", ""))
    data["experiencia"] = limpiar_lista(data.get("experiencia", []))
    data["formacion"] = limpiar_lista(data.get("formacion", []))
    data["certificaciones"] = limpiar_lista(data.get("certificaciones", []))
    data["competencias"] = limpiar_lista(data.get("competencias", []))
    data["info_relevante"] = str(data.get("info_relevante", info_extra))

    return data


# =========================
# FOOTER
# =========================

def footer(canvas, doc):
    canvas.setFont("Helvetica", 8)
    canvas.drawString(40, 20, "Generado por Perfil.Work | www.perfil.work")


# =========================
# PDF
# =========================

def generar_pdf(nombre, cargo, contacto, data):

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)

    elements = []

    # HEADER (nombre izquierda + logo derecha)
    elements.append(Paragraph(f"<b>{nombre}</b>", styles["Name"]))
    elements.append(Paragraph(f"<b>{cargo}</b>", styles["Cargo"]))
    elements.append(Paragraph(contacto, styles["BodySmall"]))
    elements.append(Spacer(1, 10))

    if os.path.exists("logo.png"):
        elements.append(Image("logo.png", width=100, height=30))
        elements.append(Spacer(1, 10))

    # RESUMEN
    if data.get("perfil"):
        elements.append(Paragraph("<b>RESUMEN TÉCNICO</b>", styles["Section"]))
        elements.append(Paragraph(data["perfil"], styles["BodySmall"]))
        elements.append(Spacer(1, 10))

    # FORMACIÓN
    if data.get("formacion"):
        elements.append(Paragraph("<b>FORMACIÓN</b>", styles["Section"]))
        for x in data["formacion"]:
            elements.append(Paragraph(f"• {x}", styles["BodySmall"]))
        elements.append(Spacer(1, 10))

    # EXPERIENCIA
    if data.get("experiencia"):
        elements.append(Paragraph("<b>EXPERIENCIA LABORAL</b>", styles["Section"]))
        for x in data["experiencia"]:
            elements.append(Paragraph(f"• {x}", styles["BodySmall"]))
        elements.append(Spacer(1, 10))

    # HABILIDADES
    if data.get("competencias"):
        elements.append(Paragraph("<b>HABILIDADES TÉCNICAS</b>", styles["Section"]))
        for x in data["competencias"]:
            elements.append(Paragraph(f"• {x}", styles["BodySmall"]))
        elements.append(Spacer(1, 10))

    # CERTIFICACIONES
    if data.get("certificaciones"):
        elements.append(Paragraph("<b>CERTIFICACIONES</b>", styles["Section"]))
        for x in data["certificaciones"]:
            elements.append(Paragraph(f"• {x}", styles["BodySmall"]))
        elements.append(Spacer(1, 10))

    # EXTRA
    if data.get("info_relevante"):
        elements.append(Paragraph("<b>DATOS ADICIONALES</b>", styles["Section"]))
        elements.append(Paragraph(data["info_relevante"], styles["BodySmall"]))

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)
    return buffer


# =========================
# ROUTE
# =========================

@app.route("/crear-cv", methods=["POST"])
def crear_cv():

    file = request.files.get("cv")
    info_extra = request.form.get("info_extra", "")

    nombre = request.form.get("nombre", "Nombre")
    cargo = request.form.get("cargo", "Cargo")

    contacto = f"{request.form.get('region','')} | {request.form.get('email','')} | {request.form.get('telefono','')}"

    texto = extraer_texto(file)
    texto_procesado = preprocesar_cv(texto)

    data = mejorar_cv(texto_procesado, info_extra)

    pdf = generar_pdf(nombre, cargo, contacto, data)

    return Response(
        pdf.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=cv_mejorado.pdf"}
    )


if __name__ == "__main__":
    app.run(debug=True)
