import os
from io import BytesIO
from flask import Flask, request, send_file
from flask_cors import CORS
from openai import OpenAI

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

app = Flask(__name__)
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# IA MEJORADA (GRATIS)
# =========================

def generar_cv(data):

    prompt = f"""
Actúa como redactor de CV para perfiles técnicos en Chile.

Crea un CV claro, profesional y completo.

DATOS:
Área: {data.get('area')}
Experiencia: {data.get('experiencia')}
Nivel: {data.get('nivel')}
Región: {data.get('region')}
Detalle: {data.get('detalle')}

INSTRUCCIONES:
- No inventar empresas
- No usar placeholders
- Redacción concreta pero completa
- Que se vea trabajado (no corto)
- Enfocado en empleabilidad real

FORMATO:

PERFIL PROFESIONAL:
(4-5 líneas claras)

EXPERIENCIA:
(4-6 bullets bien explicados)

COMPETENCIAS:
(5-8 habilidades técnicas)

CERTIFICACIONES:
(si no hay, omitir)
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )
        texto = r.choices[0].message.content

    except Exception as e:
        print("ERROR OPENAI:", e)
        texto = f"""
PERFIL PROFESIONAL:
Profesional del área {data.get('area')} con experiencia en {data.get('experiencia')}.

EXPERIENCIA:
- Experiencia en funciones técnicas
- Trabajo en equipo
- Cumplimiento de normas

COMPETENCIAS:
- Trabajo en equipo
- Seguridad
"""

    texto = texto.replace("**", "")
    return texto

# =========================
# PDF MEJORADO
# =========================

def generar_pdf(nombre, cargo, contacto, texto_cv):

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # LOGO
    try:
        logo = ImageReader("logo.png")
        c.drawImage(logo, 20, height - 70, width=140)
    except:
        pass

    y = height - 110

    # NOMBRE
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20, y, nombre)
    y -= 22

    # CARGO
    c.setFont("Helvetica", 12)
    c.drawString(20, y, cargo)
    y -= 16

    # CONTACTO
    c.setFont("Helvetica", 10)
    c.drawString(20, y, contacto)
    y -= 25

    # CONTENIDO
    for line in texto_cv.split("\n"):

        line = line.strip()

        if not line:
            y -= 8
            continue

        if line.upper() in [
            "PERFIL PROFESIONAL:",
            "EXPERIENCIA:",
            "COMPETENCIAS:",
            "CERTIFICACIONES:"
        ]:
            c.setFont("Helvetica-Bold", 13)
            y -= 5
        else:
            c.setFont("Helvetica", 10)

        if y < 40:
            c.showPage()
            y = height - 40

        c.drawString(20, y, line)
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

@app.route("/crear-cv", methods=["GET", "POST"])
def crear_cv():

    data = request.get_json(silent=True)

    if not data:
        data = request.form.to_dict()

    nombre = data.get("nombre", "Nombre Apellido")
    cargo = data.get("cargo", "Cargo")

    contacto = f"{data.get('region','')} | {data.get('email','')} | {data.get('telefono','')}"

    texto = generar_cv(data)
    pdf = generar_pdf(nombre, cargo, contacto, texto)

    return send_file(
        pdf,
        as_attachment=True,
        download_name="cv_perfil_work.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)
