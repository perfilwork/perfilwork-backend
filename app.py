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
# PREPROCESAR CV
# =========================

def normalizar_linea(l):
    return re.sub(r"\s+", " ", l.strip())

def preprocesar_cv(texto):
    lineas = [normalizar_linea(l) for l in texto.split("\n") if l.strip()]
    return "\n".join(lineas[:2000])  # limitar tamaño


# =========================
# LIMPIAR RESPUESTA IA
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
# IA SEGURA
# =========================

def mejorar_cv(texto_cv, info_extra):

    prompt = f"""
Eres un especialista en reclutamiento técnico industrial.

Usa SOLO información del CV.

CV:
{texto_cv}

INFO EXTRA:
{info_extra}

Devuelve JSON:

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
        contenido = contenido.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(contenido)
        except:
            print("⚠️ JSON inválido")
            data = {}

    except Exception as e:
        print("ERROR IA:", e)
        data = {}

    # 🔥 fallback seguro SIEMPRE
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
# PDF SEGURO
# =========================

def safe_paragraph(text):
    try:
        return Paragraph(str(text), styles["BodySmall"])
    except:
        return Paragraph("", styles["BodySmall"])


def generar_pdf(nombre, cargo, contacto, data):

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)

    elements = []

    try:
        if os.path.exists("logo.png"):
            elements.append(Image("logo.png", width=120, height=40))
            elements.append(Spacer(1, 8))
    except:
        pass

    elements.append(Paragraph(f"<b>{nombre}</b>", styles["Title"]))
    elements.append(safe_paragraph(cargo))
    elements.append(safe_paragraph(contacto))
    elements.append(Spacer(1, 12))

    if data.get("perfil"):
        elements.append(Paragraph("<b>RESUMEN</b>", styles["Section"]))
        elements.append(safe_paragraph(data["perfil"]))

    if data.get("experiencia"):
        elements.append(Paragraph("<b>EXPERIENCIA</b>", styles["Section"]))
        elements.append(ListFlowable([safe_paragraph(x) for x in data["experiencia"]]))

    if data.get("formacion"):
        elements.append(Paragraph("<b>FORMACIÓN</b>", styles["Section"]))
        elements.append(ListFlowable([safe_paragraph(x) for x in data["formacion"]]))

    if data.get("certificaciones"):
        elements.append(Paragraph("<b>CERTIFICACIONES</b>", styles["Section"]))
        elements.append(ListFlowable([safe_paragraph(x) for x in data["certificaciones"]]))

    if data.get("competencias"):
        elements.append(Paragraph("<b>COMPETENCIAS</b>", styles["Section"]))
        elements.append(ListFlowable([safe_paragraph(x) for x in data["competencias"]]))

    if data.get("info_relevante"):
        elements.append(Paragraph("<b>INFO RELEVANTE</b>", styles["Section"]))
        elements.append(safe_paragraph(data["info_relevante"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# =========================
# ROUTE PRINCIPAL
# =========================

@app.route("/crear-cv", methods=["POST"])
def crear_cv():
    try:
        file = request.files.get("cv")
        info_extra = request.form.get("info_extra", "")

        nombre = request.form.get("nombre", "Nombre")
        cargo = request.form.get("cargo", "Cargo")

        contacto = f"{request.form.get('region','')} | {request.form.get('email','')} | {request.form.get('telefono','')}"

        texto = extraer_texto(file)
        texto_procesado = preprocesar_cv(texto)

        data = mejorar_cv(texto_procesado, info_extra)

        pdf = generar_pdf(nombre, cargo, contacto, data)

        return send_file(
            pdf,
            as_attachment=True,
            download_name="cv_mejorado.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        print("ERROR GENERAL:", e)
        return "Error interno del servidor", 500


if __name__ == "__main__":
    app.run(debug=True)
