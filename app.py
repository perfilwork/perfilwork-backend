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
# OPENAI TEXT
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
Sueldo esperado: {data['sueldo']}
Región: {data['region']}
Información adicional: {data['detalle']}

Entrega SOLO estas secciones:

PERFIL PROFESIONAL:
EXPERIENCIA DESTACADA:
COMPETENCIAS TÉCNICAS:
CERTIFICACIONES Y DATOS RELEVANTES:

Redacción profesional, concreta, potente y creíble.
No inventes empleadores ni estudios.
"""

    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return r.choices[0].message.content

# =========================
# PDF
# =========================

def crear_pdf(data, texto):

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4

    y = height - 40

    # LOGO
    if os.path.exists("logo.png"):
        pdf.drawImage(
            ImageReader("logo.png"),
            35,
            y - 20,
            width=95,
            height=28,
            preserveAspectRatio=True,
            mask='auto'
        )

    y -= 50

    # TITULO
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(35, y, data["nombre"].upper())

    y -= 24
    pdf.setFont("Helvetica", 12)
    pdf.drawString(35, y, data["cargo"])

    y -= 18
    pdf.drawString(35, y, f"{data['region']} | {data['correo']} | {data['whatsapp']}")

    y -= 28

    pdf.setFont("Helvetica", 11)

    lines = texto.split("\n")

    for line in lines:

        if y < 70:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 11)

        line = line.strip()

        if not line:
            y -= 8
            continue

        if line.endswith(":"):
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(35, y, line)
            y -= 18
            pdf.setFont("Helvetica", 11)
        else:
            wrapped = dividir_texto(line, 95)
            for w in wrapped:
                pdf.drawString(35, y, w)
                y -= 15

    # FOOTER
    pdf.setFont("Helvetica", 9)
    pdf.drawString(35, 25, "Generado por Perfil.Work | www.perfil.work")

    pdf.save()
    buffer.seek(0)
    return buffer

# =========================
# WRAP TEXT
# =========================

def dividir_texto(texto, largo):
    palabras = texto.split()
    lineas = []
    actual = ""

    for p in palabras:
        if len(actual + " " + p) <= largo:
            actual += " " + p if actual else p
        else:
            lineas.append(actual)
            actual = p

    if actual:
        lineas.append(actual)

    return lineas

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

    for r in rows:
        html += "<tr>" + "".join([f"<td>{x}</td>" for x in r]) + "</tr>"

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

    texto = generar_cv(data)

    pdf_buffer = crear_pdf(data, texto)

    nombre_archivo = f"CV_{data['nombre'].replace(' ','_')}.pdf"

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/pdf"
    )

# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
