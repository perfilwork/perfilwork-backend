import os
import json
import re
from io import BytesIO
from flask import Flask, request, send_file
from flask_cors import CORS
from openai import OpenAI

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT

import docx
import PyPDF2

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodySmall", fontSize=9, leading=12, alignment=TA_LEFT))
styles.add(ParagraphStyle(name="Section", fontSize=11, leading=14, spaceAfter=6))


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
    except Exception as e:
        print("ERROR EXTRACCIÓN:", e)

    return ""


# =========================
# PREPROCESAR
# =========================

def normalizar_linea(l):
    return re.sub(r"\s+", " ", l.strip())

def es_linea_experiencia(l):
    return bool(re.match(r"^\d{4}", l)) and ":" in l

def limpiar_experiencia(l):
    partes = l.split(":")
    anio = partes[0].strip()
    resto = partes[1].strip()
    resto = resto.replace("(", " - ").replace(")", "")
    return f"{anio} - {resto}"

def preprocesar_cv(texto):
    lineas = [normalizar_linea(l) for l in texto.split("\n") if l.strip()]

    datos, experiencia, formacion = [], [], []
    modo = None

    for l in lineas:
        u = l.upper()

        if "ANTECEDENTES PERSONALES" in u:
            modo = "datos"
            continue
        elif "ANTECEDENTES LABORALES" in u:
            modo = "exp"
            continue
        elif "ANTECEDENTES ACADEMICOS" in u or "CAPACIT" in u:
            modo = "form"
            continue

        if es_linea_experiencia(l):
            experiencia.append(limpiar_experiencia(l))
        elif modo == "form":
            formacion.append(l)
        else:
            datos.append(l)

    texto_limpio = ""

    if datos:
        texto_limpio += "DATOS PERSONALES:\n" + "\n".join(datos[:15]) + "\n\n"

    if experiencia:
        texto_limpio += "EXPERIENCIA LABORAL:\n"
        texto_limpio += "\n".join(f"- {e}" for e in experiencia) + "\n\n"

    if formacion:
        texto_limpio += "FORMACIÓN:\n"
        texto_limpio += "\n".join(f"- {f}" for f in formacion)

    return texto_limpio


# =========================
# LIMPIAR RESPUESTA IA (CRÍTICO)
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
# IA
# =========================

def mejorar_cv(texto_cv, info_extra):

    prompt = f"""
Eres un especialista en reclutamiento técnico industrial.

Usa SOLO la información del CV.

PROHIBIDO:
- inventar empresas
- inventar datos
- usar texto genérico

CV:
{texto_cv}

INFO ADICIONAL:
{info_extra}

Devuelve SOLO JSON válido:

{{
"perfil": "...",
"experiencia": ["..."],
"formacion": ["..."],
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
        contenido = contenido.replace("```json", "").replace("```", "")

        data = json.loads(contenido)

    except Exception as e:
        print("ERROR IA:", e)
        data = {}

    # 🔥 NORMALIZACIÓN (EVITA CRASH)
    data["experiencia"] = limpiar_lista(data.get("experiencia", []))
    data["formacion"] = limpiar_lista(data.get("formacion", []))
    data["certificaciones"] = limpiar_lista(data.get("certificaciones", []))
    data["competencias"] = limpiar_lista(data.get("competencias", []))

    return data


# =========================
# PDF
# =========================

def generar_pdf(nombre, cargo, contacto, data):

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)

    elements = []

    if os.path.exists("logo.png"):
        elements.append(Image("logo.png", width=120, height=40))
        elements.append(Spacer(1, 8))

    elements.append(Paragraph(f"<b>{nombre}</b>", styles["Title"]))
    elements.append(Paragraph(cargo, styles["Normal"]))
    elements.append(Paragraph(contacto, styles["BodySmall"]))
    elements.append(Spacer(1, 12))

    if data.get("perfil"):
        elements.append(Paragraph("<b>RESUMEN</b>", styles["Section"]))
        elements.append(Paragraph(data["perfil"], styles["BodySmall"]))

    if data.get("experiencia"):
        elements.append(Paragraph("<b>EXPERIENCIA LABORAL</b>", styles["Section"]))
        elements.append(ListFlowable([Paragraph(x, styles["BodySmall"]) for x in data["experiencia"]]))

    if data.get("formacion"):
        elements.append(Paragraph("<b>FORMACIÓN</b>", styles["Section"]))
        elements.append(ListFlowable([Paragraph(x, styles["BodySmall"]) for x in data["formacion"]]))

    if data.get("certificaciones"):
        elements.append(Paragraph("<b>CERTIFICACIONES</b>", styles["Section"]))
        elements.append(ListFlowable([Paragraph(x, styles["BodySmall"]) for x in data["certificaciones"]]))

    if data.get("competencias"):
        elements.append(Paragraph("<b>COMPETENCIAS</b>", styles["Section"]))
        elements.append(ListFlowable([Paragraph(x, styles["BodySmall"]) for x in data["competencias"]]))

    if data.get("info_relevante"):
        elements.append(Paragraph("<b>INFORMACIÓN RELEVANTE</b>", styles["Section"]))
        elements.append(Paragraph(data["info_relevante"], styles["BodySmall"]))

    doc.build(elements)
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

    return send_file(pdf, as_attachment=True, download_name="cv_mejorado.pdf", mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=True)
