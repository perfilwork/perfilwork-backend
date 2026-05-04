import os
import json
from io import BytesIO
from flask import Flask, request, send_file
from flask_cors import CORS
from openai import OpenAI

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# IA CONTROLADA
# =========================

def generar_cv(data):

    prompt = f"""
Devuelve SOLO JSON válido.

NO agregues notas, explicaciones ni placeholders.

Datos:
Área: {data.get('area')}
Experiencia: {data.get('experiencia')}
Nivel: {data.get('nivel')}
Detalle: {data.get('detalle')}

Formato exacto:

{{
  "perfil": "...",
  "experiencia": ["...", "...", "..."],
  "competencias": ["...", "...", "..."]
}}

Reglas:
- No inventar empresas
- No usar porcentajes ni métricas falsas
- No usar texto genérico tipo "profesional altamente motivado"
- Lenguaje técnico, directo
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        contenido = r.choices[0].message.content

        # limpiar posibles errores
        contenido = contenido.replace("```json", "").replace("```", "")

        return json.loads(contenido)

    except Exception as e:
        print("ERROR IA:", e)

        return {
            "perfil": "Técnico con experiencia en su área.",
            "experiencia": ["Experiencia en funciones técnicas"],
            "competencias": ["Trabajo en equipo"]
        }

# =========================
# PDF MEJORADO
# =========================

def generar_pdf(nombre, cargo, contacto, data_cv):

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 60

    # NOMBRE
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, nombre)
    y -= 20

    # CARGO
    c.setFont("Helvetica", 11)
    c.drawString(40, y, cargo)
    y -= 15

    # CONTACTO
    c.setFont("Helvetica", 9)
    c.drawString(40, y, contacto)
    y -= 25

    # PERFIL
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "PERFIL")
    y -= 15

    c.setFont("Helvetica", 9)
    for line in dividir_texto(data_cv["perfil"], 80):
        c.drawString(40, y, line)
        y -= 12

    y -= 10

    # EXPERIENCIA
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "EXPERIENCIA")
    y -= 15

    for exp in data_cv["experiencia"]:
        for line in dividir_texto(f"- {exp}", 80):
            c.drawString(40, y, line)
            y -= 12

    y -= 10

    # COMPETENCIAS
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "COMPETENCIAS")
    y -= 15

    for comp in data_cv["competencias"]:
        c.drawString(40, y, f"- {comp}")
        y -= 12

    c.save()
    buffer.seek(0)

    return buffer

# =========================
# AJUSTE TEXTO (CLAVE)
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
