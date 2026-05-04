import os
import json
from io import BytesIO
from flask import Flask, request, send_file
from flask_cors import CORS
from openai import OpenAI

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

import docx
import PyPDF2

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# EXTRAER TEXTO DE ARCHIVOS
# =========================

def extraer_texto(file):

    filename = file.filename.lower()

    if filename.endswith(".docx"):
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs])

    elif filename.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file)
        texto = ""
        for page in reader.pages:
            texto += page.extract_text() or ""
        return texto

    return ""

# =========================
# IA (MEJORA CV REAL)
# =========================

def mejorar_cv(cv_texto, info_extra):

    prompt = f"""
Eres experto en reclutamiento técnico en Chile.

Tu tarea es MEJORAR un CV existente.

REGLAS CRÍTICAS:
- NO inventar información
- NO eliminar información relevante
- NO resumir en exceso
- NO agregar placeholders
- NO escribir notas ni recomendaciones
- Mantener TODO lo importante del CV original

OBJETIVO:
- Ordenar
- Mejorar redacción
- Hacerlo más claro para reclutadores

CV ORIGINAL:
{cv_texto}

INFORMACIÓN ADICIONAL DEL CANDIDATO:
{info_extra}

FORMATO DE SALIDA (SOLO JSON):

{{
  "perfil": "...",
  "experiencia": ["...", "..."],
  "competencias": ["...", "..."],
  "certificaciones": ["...", "..."]
}}
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        contenido = r.choices[0].message.content
        contenido = contenido.replace("```json", "").replace("```", "")

        return json.loads(contenido)

    except Exception as e:
        print("ERROR IA:", e)

        return {
            "perfil": cv_texto[:200],
            "experiencia": [],
            "competencias": [],
            "certificaciones": []
        }

# =========================
# UTIL TEXTO
# =========================

def dividir_texto(texto, max_chars):
    palabras = texto.split()
    lineas = []
    actual = ""

    for palabra in palabras:
        if len(actual) + len(palabra) < max_chars:
            actual += palabra + " "
        else:
            lineas.append(actual)
            actual = palabra + " "

    lineas.append(actual)
    return lineas

# =========================
# PDF LIMPIO (NO DISTORSIONADO)
# =========================

def generar_pdf(nombre, cargo, contacto, data):

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 60

    # LOGO BIEN PROPORCIONADO
    try:
        logo = ImageReader("logo.png")
        c.drawImage(logo, width - 150, height - 70, width=120, preserveAspectRatio=True)
    except:
        pass

    # HEADER
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, nombre)
    y -= 20

    c.setFont("Helvetica", 11)
    c.drawString(40, y, cargo)
    y -= 15

    c.setFont("Helvetica", 9)
    c.drawString(40, y, contacto)
    y -= 25

    # PERFIL
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "PERFIL PROFESIONAL")
    y -= 15

    c.setFont("Helvetica", 9)
    for line in dividir_texto(data["perfil"], 90):
        c.drawString(40, y, line)
        y -= 12

    y -= 10

    # EXPERIENCIA
    if data["experiencia"]:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "EXPERIENCIA")
        y -= 15

        for exp in data["experiencia"]:
            for line in dividir_texto(f"- {exp}", 90):
                c.drawString(40, y, line)
                y -= 12

        y -= 10

    # COMPETENCIAS
    if data["competencias"]:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "COMPETENCIAS")
        y -= 15

        for comp in data["competencias"]:
            c.drawString(40, y, f"- {comp}")
            y -= 12

        y -= 10

    # CERTIFICACIONES
    if data["certificaciones"]:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "CERTIFICACIONES")
        y -= 15

        for cert in data["certificaciones"]:
            c.drawString(40, y, f"- {cert}")
            y -= 12

    c.save()
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

    texto_cv = extraer_texto(file)

    data_cv = mejorar_cv(texto_cv, info_extra)

    pdf = generar_pdf(nombre, cargo, contacto, data_cv)

    return send_file(
        pdf,
        as_attachment=True,
        download_name="cv_mejorado.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)
