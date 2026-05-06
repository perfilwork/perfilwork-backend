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

    except Exception as e:
        print("ERROR EXTRACCIÓN:", e)

    return ""


# =========================
# PREPROCESAR
# =========================

def preprocesar_cv(texto):
    lineas = [re.sub(r"\s+", " ", l.strip()) for l in texto.split("\n") if l.strip()]
    return "\n".join(lineas[:350])


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

OBJETIVO:
- Hacerlo más claro
- Más legible
- Más profesional
- Fácil de revisar por reclutadores

REGLAS:
- NO inventar información
- NO eliminar experiencia relevante
- NO usar frases genéricas
- NO repetir funciones similares innecesariamente

CRITERIOS INTELIGENTES:

1. Si el candidato tiene MUCHAS experiencias similares:
- AGRUPAR experiencias repetitivas
- Ejemplo:
  "Experiencia desempeñándose como Soldador en empresas como..."
- Luego resumir funciones comunes

2. Si existen trabajos IMPORTANTES o DIFERENTES:
- Mantenerlos separados y detallados

3. Priorizar:
- especialidad técnica
- años de experiencia
- industrias
- certificaciones
- habilidades concretas

4. Las funciones deben ser ACCIONES REALES:
✔ "Diagnóstico de fallas"
✔ "Soldadura MIG/TIG"
✔ "Lectura de planos"

NO:
✘ "Responsable de..."
✘ "Encargado de..."

ESTRUCTURA:

1. Resumen técnico breve
2. Formación
3. Experiencia laboral
4. Habilidades técnicas
5. Certificaciones
6. Datos adicionales

CV:
{texto_cv}

INFORMACIÓN ADICIONAL:
{info_extra}

Devuelve JSON válido:

{{
"perfil": "...",
"formacion": ["..."],
"experiencia": ["..."],
"competencias": ["..."],
"certificaciones": ["..."],
"info_relevante": "..."
}}
"""

    try:

        print("⏳ Enviando CV a OpenAI...")

        r = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        print("✅ Respuesta recibida")

        contenido = r.choices[0].message.content.strip()
        contenido = contenido.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(contenido)
        except Exception as e:
            print("ERROR JSON:", e)
            data = {}

    except Exception as e:
        print("ERROR OPENAI:", e)
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

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    elements = []

    # HEADER
    elements.append(Paragraph(f"<b>{nombre}</b>", styles["Name"]))
    elements.append(Paragraph(f"<b>{cargo}</b>", styles["Cargo"]))
    elements.append(Paragraph(contacto, styles["BodySmall"]))
    elements.append(Spacer(1, 10))

    # LOGO
    if os.path.exists("logo.png"):
        try:
            elements.append(Image("logo.png", width=100, height=30))
            elements.append(Spacer(1, 10))
        except Exception as e:
            print("ERROR LOGO:", e)

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

@app.route("/crear-cv", methods=["GET", "POST"])
def crear_cv():

    # 🔥 evita Method Not Allowed cuando Render despierta
    if request.method == "GET":
        return "Servicio activo"

    try:

        file = request.files.get("cv")
        info_extra = request.form.get("info_extra", "")

        nombre = request.form.get("nombre", "Nombre")
        cargo = request.form.get("cargo", "Cargo")

        contacto = (
            f"{request.form.get('region','')} | "
            f"{request.form.get('email','')} | "
            f"{request.form.get('telefono','')}"
        )

        texto = extraer_texto(file)

        print("📄 Texto extraído")

        texto_procesado = preprocesar_cv(texto)

        data = mejorar_cv(texto_procesado, info_extra)

        print("🧠 CV mejorado")

        pdf = generar_pdf(nombre, cargo, contacto, data)

        print("📄 PDF generado")

        return Response(
            pdf.getvalue(),
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=cv_mejorado.pdf"
            }
        )

    except Exception as e:
        print("ERROR GENERAL:", e)
        return "Error interno del servidor", 500


if __name__ == "__main__":
    app.run(debug=True)
