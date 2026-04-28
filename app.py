import os
import sqlite3
from io import BytesIO

from flask import Flask, request, send_file
from flask_cors import CORS

from openai import OpenAI

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# =========================
# APP
# =========================

app = Flask(__name__)
CORS(app)

# =========================
# CONFIG
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

DB_NAME = "leads.db"

# =========================
# DB INIT
# =========================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        correo TEXT,
        whatsapp TEXT,
        region TEXT,
        cargo TEXT,
        area TEXT,
        experiencia TEXT,
        nivel TEXT,
        sueldo TEXT,
        detalle TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# SAVE LEAD
# =========================

def guardar_lead(data):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO leads
    (nombre, correo, whatsapp, region, cargo, area, experiencia, nivel, sueldo, detalle)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["nombre"],
        data["correo"],
        data["whatsapp"],
        data["region"],
        data["cargo"],
        data["area"],
        data["experiencia"],
        data["nivel"],
        data["sueldo"],
        data["detalle"]
    ))

    conn.commit()
    conn.close()

# =========================
# IA + FALLBACK
# =========================

def generar_cv(data):

    prompt = f"""
Redacta un CV profesional en español para Chile, estilo técnico industrial.

Datos:
Nombre: {data['nombre']}
Cargo objetivo: {data['cargo']}
Área técnica: {data['area']}
Experiencia: {data['experiencia']}
Nivel: {data['nivel']}
Región: {data['region']}
Información adicional: {data['detalle']}

Entrega SOLO estas secciones:

PERFIL PROFESIONAL:
EXPERIENCIA DESTACADA:
COMPETENCIAS TÉCNICAS:
CERTIFICACIONES Y DATOS RELEVANTES:

No inventes información.
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return r.choices[0].message.content

    except Exception:

        return f"""
PERFIL PROFESIONAL:
Profesional orientado al área de {data['area']}, con experiencia de {data['experiencia']}. 
Cuenta con nivel declarado: {data['nivel']}. Enfocado en seguridad, cumplimiento y resultados.

EXPERIENCIA DESTACADA:
Experiencia relacionada al cargo de {data['cargo']} en funciones técnicas y operativas.

COMPETENCIAS TÉCNICAS:
• {data['area']}
• Trabajo en equipo
• Resolución de problemas
• Cumplimiento de procedimientos
• Orientación a resultados

CERTIFICACIONES Y DATOS RELEVANTES:
{data['detalle'] if data['detalle'] else 'Información adicional entregada por el candidato.'}
"""

# =========================
# PDF
# =========================

def wrap_text(texto, largo=95):
    palabras = texto.split()
    lineas = []
    actual = ""

    for palabra in palabras:
        if len(actual + " " + palabra) <= largo:
            actual += " " + palabra if actual else palabra
        else:
            lineas.append(actual)
            actual = palabra

    if actual:
        lineas.append(actual)

    return lineas

def crear_pdf(data, contenido):

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 40

    # LOGO
    if os.path.exists("logo.png"):
        pdf.drawImage(
            ImageReader("logo.png"),
            35,
            y - 15,
            width=110,
            height=30,
            preserveAspectRatio=True,
            mask='auto'
        )

    y -= 50

    # HEADER
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(35, y, data["nombre"].upper())

    y -= 24
    pdf.setFont("Helvetica", 12)
    pdf.drawString(35, y, data["cargo"])

    y -= 18
    pdf.drawString(35, y, f"{data['region']} | {data['correo']} | {data['whatsapp']}")

    y -= 28

    # BODY
    for linea in contenido.split("\n"):

        linea = linea.strip()

        if not linea:
            y -= 8
            continue

        if y < 70:
            pdf.showPage()
            y = height - 40

        if linea.endswith(":"):
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(35, y, linea)
            y -= 18
            pdf.setFont("Helvetica", 11)

        else:
            pdf.setFont("Helvetica", 11)

            for l in wrap_text(linea):
                pdf.drawString(35, y, l)
                y -= 15

    # FOOTER
    pdf.setFont("Helvetica", 9)
    pdf.drawString(35, 25, "Generado por Perfil.Work | www.perfil.work")

    pdf.save()
    buffer.seek(0)

    return buffer

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return "Perfil.Work Backend Online"

@app.route("/leads")
def leads():

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    SELECT id,nombre,correo,whatsapp,region,cargo,area
    FROM leads
    ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    html = "<h2>Leads Perfil.Work</h2><table border=1 cellpadding=8>"
    html += "<tr><th>ID</th><th>Nombre</th><th>Correo</th><th>WhatsApp</th><th>Región</th><th>Cargo</th><th>Área</th></tr>"

    for row in rows:
        html += "<tr>" + "".join([f"<td>{x}</td>" for x in row]) + "</tr>"

    html += "</table>"

    return html

@app.route("/crear-cv", methods=["POST"])
def crear_cv():

    data = {
        "nombre": request.form.get("nombre", ""),
        "correo": request.form.get("correo", ""),
        "whatsapp": request.form.get("whatsapp", ""),
        "region": request.form.get("region", ""),
        "cargo": request.form.get("cargo", ""),
        "area": request.form.get("area", ""),
        "experiencia": request.form.get("experiencia", ""),
        "nivel": request.form.get("nivel", ""),
        "sueldo": request.form.get("sueldo", ""),
        "detalle": request.form.get("detalle", "")
    }

    guardar_lead(data)

    contenido = generar_cv(data)

    pdf = crear_pdf(data, contenido)

    nombre = f"CV_{data['nombre'].replace(' ','_')}.pdf"

    return send_file(
        pdf,
        as_attachment=True,
        download_name=nombre,
        mimetype="application/pdf"
    )

# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
