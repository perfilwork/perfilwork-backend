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

import docx
import PyPDF2

app = Flask(__name__)
from supabase import create_client

SUPABASE_URL = https://kybticlgyamdcthljcov.supabase.co
SUPABASE_KEY = sb_publishable_du1cl5DoY-5BAI1hdUQVow_Hs70jTzB

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(name="BodySmall", fontSize=9, leading=11))
styles.add(ParagraphStyle(name="Section", fontSize=11, leading=14, spaceAfter=6))

# 🔥 nombre más grande
styles.add(ParagraphStyle(name="Name", fontSize=22, leading=24))

styles.add(ParagraphStyle(name="Cargo", fontSize=13, leading=15))


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

            texto = "\n".join(
                [p.text for p in doc.paragraphs if p.text.strip()]
            )

            return texto

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

    lineas = [
        re.sub(r"\s+", " ", l.strip())
        for l in texto.split("\n")
        if l.strip()
    ]

    texto_limpio = "\n".join(lineas)

    return texto_limpio[:12000]


# =========================
# NORMALIZAR LISTAS
# =========================

def normalizar_lista(valor):

    if isinstance(valor, list):
        return valor

    if isinstance(valor, str):
        return [valor]

    return []


# =========================
# LIMPIAR LISTAS
# =========================

def limpiar_lista(lista):

    lista = normalizar_lista(lista)

    resultado = []

    for item in lista:

        if isinstance(item, dict):

            texto = " - ".join(
                [str(v) for v in item.values() if v]
            )

            resultado.append(texto)

        else:
            resultado.append(str(item))

    return resultado


# =========================
# EXTRAER JSON
# =========================

def extraer_json(texto):

    try:

        match = re.search(r"\{.*\}", texto, re.DOTALL)

        if match:
            return json.loads(match.group())

    except Exception as e:
        print("ERROR EXTRAER JSON:", e)

    return None


# =========================
# IA
# =========================

def mejorar_cv(texto_cv, info_extra):

    prompt = f"""
Eres especialista en reclutamiento técnico industrial.

Debes transformar este CV en una versión:
- clara
- profesional
- compacta
- recruiter-friendly
- idealmente de 1 página

IMPORTANTE:
- Lee TODO el CV
- NO inventes información
- NO elimines experiencia importante
- Resume experiencias repetitivas
- Agrupa trabajos similares
- Prioriza especialidades técnicas
- Prioriza lectura rápida

SI existen múltiples trabajos similares:

- NO listar 15 empresas una por una
- AGRUPAR trayectoria por especialidad
- mencionar solo empresas principales
- resumir funciones repetitivas

Ejemplo deseado:

"Experiencia desempeñándose como Soldador Industrial en empresas como Salfa Montajes, SK Industrial, Huachipato y Belfi."

Luego resumir:
- industrias
- tipos de proyectos
- funciones técnicas
- especialidades

La experiencia debe verse profesional y compacta.

SOLO detallar:
- trabajos recientes
- trabajos relevantes
- trabajos técnicamente distintos

Devuelve SOLO JSON válido.

Formato exacto:

{{
"perfil": "...",
"formacion": ["..."],
"experiencia": ["..."],
"competencias": ["..."],
"certificaciones": ["..."],
"info_relevante": "..."
}}

CV:
{texto_cv}

Información adicional:
{info_extra}
"""

    try:

        respuesta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Responde SOLO JSON válido."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            max_tokens=1300
        )

        contenido = respuesta.choices[0].message.content.strip()

        print("===== RESPUESTA IA =====")
        print(contenido)

        contenido = contenido.replace("```json", "")
        contenido = contenido.replace("```", "")
        contenido = contenido.strip()

        data = extraer_json(contenido)

        if not data:
            raise Exception("JSON inválido")

    except Exception as e:

        print("ERROR OPENAI / JSON:", e)

        data = {
            "perfil": info_extra,
            "formacion": [],
            "experiencia": [],
            "competencias": [],
            "certificaciones": [],
            "info_relevante": info_extra
        }

    data["perfil"] = str(data.get("perfil", ""))

    data["experiencia"] = limpiar_lista(
        data.get("experiencia", [])
    )

    data["formacion"] = limpiar_lista(
        data.get("formacion", [])
    )

    data["certificaciones"] = limpiar_lista(
        data.get("certificaciones", [])
    )

    data["competencias"] = limpiar_lista(
        data.get("competencias", [])
    )

    data["info_relevante"] = str(
        data.get("info_relevante", info_extra)
    )

    return data


# =========================
# FOOTER
# =========================

def footer(canvas, doc):

    canvas.setFont("Helvetica", 8)

    canvas.drawString(
        40,
        20,
        "Generado por Perfil.Work | www.perfil.work"
    )


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
        topMargin=35,
        bottomMargin=35
    )

    elements = []

    # LOGO
    if os.path.exists("logo.png"):

        try:

            logo = Image(
                "logo.png",
                width=160,
            )

            elements.append(logo)
            elements.append(Spacer(1, 8))

        except Exception as e:
            print("ERROR LOGO:", e)

    # HEADER
    elements.append(
        Paragraph(f"<b>{nombre}</b>", styles["Name"])
    )

    elements.append(
        Paragraph(f"<b>{cargo}</b>", styles["Cargo"])
    )

    elements.append(
        Paragraph(contacto, styles["BodySmall"])
    )

    elements.append(Spacer(1, 12))

    # PERFIL
    if data.get("perfil"):

        elements.append(
            Paragraph("<b>RESUMEN TÉCNICO</b>", styles["Section"])
        )

        elements.append(
            Paragraph(data["perfil"], styles["BodySmall"])
        )

        elements.append(Spacer(1, 8))

    # EXPERIENCIA
    # EXPERIENCIA
if data.get("experiencia"):

    elements.append(
        Paragraph("<b>EXPERIENCIA LABORAL</b>", styles["Section"])
    )

    experiencia_texto = "<br/>".join([
        x.lstrip("-• ").strip()
        for x in data["experiencia"][:8]
    ])

    elements.append(
        Paragraph(experiencia_texto, styles["BodySmall"])
    )

    elements.append(Spacer(1, 8))

    # FORMACIÓN
    if data.get("formacion"):

        elements.append(
            Paragraph("<b>FORMACIÓN</b>", styles["Section"])
        )

        for x in data["formacion"][:5]:

            limpio = x.lstrip("-• ").strip()

            elements.append(
                Paragraph(f"• {limpio}", styles["BodySmall"])
            )

        elements.append(Spacer(1, 8))

    # HABILIDADES
    if data.get("competencias"):

        elements.append(
            Paragraph("<b>HABILIDADES TÉCNICAS</b>", styles["Section"])
        )

        habilidades = ", ".join(
            [x.lstrip("-• ").strip() for x in data["competencias"][:12]]
        )

        elements.append(
            Paragraph(habilidades, styles["BodySmall"])
        )

        elements.append(Spacer(1, 8))

    # CERTIFICACIONES
    if data.get("certificaciones"):

        elements.append(
            Paragraph("<b>CERTIFICACIONES</b>", styles["Section"])
        )

        for x in data["certificaciones"][:5]:

            limpio = x.lstrip("-• ").strip()

            elements.append(
                Paragraph(f"• {limpio}", styles["BodySmall"])
            )

        elements.append(Spacer(1, 8))

    # EXTRA
    if data.get("info_relevante"):

        elements.append(
            Paragraph("<b>DATOS ADICIONALES</b>", styles["Section"])
        )

        elements.append(
            Paragraph(data["info_relevante"], styles["BodySmall"])
        )

    doc.build(
        elements,
        onFirstPage=footer,
        onLaterPages=footer
    )

    buffer.seek(0)

    return buffer


# =========================
# ROUTE
# =========================

@app.route("/crear-cv", methods=["GET", "POST"])
def crear_cv():

    if request.method == "GET":
        return "Servicio activo"

    try:

        file = request.files.get("cv")

        info_extra = request.form.get(
            "info_extra",
            ""
        )

        nombre = request.form.get(
            "nombre",
            "Nombre"
        )

        cargo = request.form.get(
            "cargo",
            "Cargo"
        )

        contacto = (
            f"{request.form.get('region','')} | "
            f"{request.form.get('email','')} | "
            f"{request.form.get('telefono','')}"
        )

        texto = extraer_texto(file)

        texto_procesado = preprocesar_cv(texto)

        data = mejorar_cv(
            texto_procesado,
            info_extra
        )

        pdf = generar_pdf(
            nombre,
            cargo,
            contacto,
            data
        )

        return Response(
            pdf.getvalue(),
            mimetype="application/pdf",
            headers={
                "Content-Disposition":
                "attachment; filename=cv_mejorado.pdf"
            }
        )

    except Exception as e:

        print("ERROR GENERAL:", e)

        return "Error interno del servidor", 500


if __name__ == "__main__":
    app.run(debug=True)
