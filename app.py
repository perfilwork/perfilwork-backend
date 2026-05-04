import os
import json
from io import BytesIO
from flask import Flask, request, send_file
from flask_cors import CORS
from openai import OpenAI

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# IA → JSON CONTROLADO
# =========================

def generar_cv(data):

    prompt = f"""
Devuelve SOLO JSON válido.

Candidato técnico:

Área: {data.get('area')}
Experiencia: {data.get('experiencia')}
Nivel: {data.get('nivel')}
Detalle: {data.get('detalle')}

Formato JSON:

{{
  "perfil": "...",
  "experiencia": ["...", "...", "..."],
  "competencias": ["...", "...", "..."]
}}

Reglas:
- No usar placeholders
- No inventar empresas
- Texto claro, corto y concreto
- Nada de explicaciones fuera del JSON
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )

        contenido = r.choices[0].message.content

        return json.loads(contenido)

    except Exception as e:
        print("ERROR IA:", e)

        return {
            "perfil": "Profesional técnico con experiencia en su área.",
            "experiencia": ["Experiencia en funciones técnicas"],
            "competencias": ["Trabajo en equipo"]
        }

# =========================
# PDF PRO (MEJORADO)
# =========================

def generar_pdf(nombre, cargo, contacto, data_cv):

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 60

    # LOGO
    try:
        logo = ImageReader("logo.png")
        c.drawImage(logo, width - 150, height - 80, width=120)
    except:
        pass

    # NOMBRE
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, y, nombre)
    y -= 20

    # CARGO
    c.setFont("Helvetica", 12)
    c.drawString(40, y, cargo)
    y -= 15

    # CONTACTO
    c.setFont("Helvetica", 10)
    c.drawString(40, y, contacto)
    y -= 25

    # PERFIL
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "PERFIL")
    y -= 15

    c.setFont("Helvetica", 10)
    c.drawString(40, y, data_cv["perfil"])
    y -= 25

    # EXPERIENCIA
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "EXPERIENCIA")
    y -= 15

    c.setFont("Helvetica", 10)
    for exp in data_cv["experiencia"]:
        c.drawString(50, y, f"- {exp}")
        y -= 12

    y -= 10

    # COMPETENCIAS
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "COMPETENCIAS")
    y -= 15

    for comp in data_cv["competencias"]:
        c.drawString(50, y, f"- {comp}")
        y -= 12

    c.save()
    buffer.seek(0)

    return buffer

# =========================
# ROUTE
# =========================

@app.route("/crear-cv", methods=["GET", "POST"])
def crear_cv():

    data = request.get_json(silent=True)

    if not data:
        data = request.form.to_dict()

    nombre = data.get("nombre", "Nombre")
    cargo = data.get("cargo", "Cargo")

    contacto = f"{data.get('region','')} | {data.get('email','')} | {data.get('telefono','')}"

    data_cv = generar_cv(data)

    pdf = generar_pdf(nombre, cargo, contacto, data_cv)

    return send_file(
        pdf,
        as_attachment=True,
        download_name="cv_perfil_work.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)
