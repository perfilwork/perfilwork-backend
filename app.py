import os
import sqlite3
from io import BytesIO
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

from openai import OpenAI

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

app = Flask(__name__)
CORS(app)

# =========================
# CONFIG
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# IA CV
# =========================

def generar_cv(data):
    prompt = f"""
Actúa como experto en reclutamiento técnico industrial en Chile.

Tu tarea es redactar un CV profesional, claro, breve y altamente empleable.

DATOS DEL CANDIDATO:
Área: {data.get('area')}
Experiencia: {data.get('experiencia')}
Nivel: {data.get('nivel')}
Región: {data.get('region')}
Detalle: {data.get('detalle')}

INSTRUCCIONES CLAVE:
- NO inventar empresas, fechas ni certificaciones
- NO usar placeholders como [empresa] o [año]
- Si falta información, omitirla sin mencionarlo
- Redacción concreta, sin frases vacías
- Enfocado en empleabilidad real en industria (minería, plantas, montaje, etc.)
- Máximo impacto con el menor texto posible

FORMATO:

PERFIL PROFESIONAL:
EXPERIENCIA DESTACADA:
COMPETENCIAS TÉCNICAS:
CERTIFICACIONES Y DATOS RELEVANTES:

Tono: directo, técnico, profesional.
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return r.choices[0].message.content

    except Exception as e:
        print("ERROR OPENAI:", e)

        # fallback simple si falla IA
        return f"""
PERFIL PROFESIONAL:
Profesional del área {data.get('area')} con experiencia en {data.get('experiencia')}.

COMPETENCIAS TÉCNICAS:
- Trabajo en equipo
- Cumplimiento de normas de seguridad

EXPERIENCIA DESTACADA:
Experiencia en funciones técnicas relacionadas al cargo.

CERTIFICACIONES:
No especificadas
"""

# =========================
# PDF
# =========================

def generar_pdf(nombre, cargo, contacto, texto_cv):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4

    # LOGO
    try:
        logo = ImageReader("logo.png")
        c.drawImage(logo, 20, height - 60, width=120, preserveAspectRatio=True, mask='auto')
    except:
        pass

    y = height - 100

    # Nombre
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20, y, nombre)
    y -= 20

    # Cargo
    c.setFont("Helvetica", 12)
    c.drawString(20, y, cargo)
    y -= 15

    # Contacto
    c.drawString(20, y, contacto)
    y -= 25

    # Texto CV
    c.setFont("Helvetica", 10)

    for line in texto_cv.split("\n"):
        if y < 40:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 40

        c.drawString(20, y, line.strip())
        y -= 14

    c.save()

    buffer.seek(0)
    return buffer

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return "Perfil.Work Backend Online"

@app.route("/crear-cv", methods=["POST"])
def crear_cv():
    data = request.json

    nombre = data.get("nombre", "Nombre Apellido")
    cargo = data.get("cargo", "Cargo")
    contacto = f"{data.get('region', '')} | {data.get('email', '')} | {data.get('telefono', '')}"

    texto = generar_cv(data)

    pdf = generar_pdf(nombre, cargo, contacto, texto)

    return send_file(
        pdf,
        as_attachment=True,
        download_name="cv_perfil_work.pdf",
        mimetype="application/pdf"
    )

# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(debug=True)
