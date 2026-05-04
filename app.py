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

# =========================
# CONFIG
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# GENERAR CV
# =========================

def generar_cv(data):

    prompt = f"""
Actúa como asistente de redacción de CV.

Área: {data.get('area')}
Experiencia: {data.get('experiencia')}
Nivel: {data.get('nivel')}
Región: {data.get('region')}
Detalle: {data.get('detalle')}

INSTRUCCIONES:
- No inventar información
- Redacción simple y clara
- Formato estándar

FORMATO:

PERFIL PROFESIONAL:
EXPERIENCIA:
COMPETENCIAS:
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        texto = r.choices[0].message.content

    except Exception as e:
        print("ERROR OPENAI:", e)
        texto = f"""
PERFIL PROFESIONAL:
Profesional del área {data.get('area')} con experiencia en {data.get('experiencia')}.
"""

    texto = texto.replace("**", "")
    return texto

# =========================
# PDF
# =========================

def generar_pdf(nombre, cargo, contacto, texto_cv):

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4

    try:
        logo = ImageReader("logo.png")
        c.drawImage(logo, 20, height - 60, width=120)
    except:
        pass

    y = height - 100

    c.setFont("Helvetica-Bold", 16)
    c.drawString(20, y, nombre)
    y -= 20

    c.setFont("Helvetica", 12)
    c.drawString(20, y, cargo)
    y -= 15

    c.drawString(20, y, contacto)
    y -= 25

    for line in texto_cv.split("\n"):

        line = line.strip()

        if not line:
            y -= 8
            continue

        if line.upper() in ["PERFIL PROFESIONAL:", "EXPERIENCIA:", "COMPETENCIAS:"]:
            c.setFont("Helvetica-Bold", 12)
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

    # 🔥 SOLUCIÓN REAL
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

# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(debug=True)
