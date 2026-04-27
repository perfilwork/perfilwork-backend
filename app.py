from flask import Flask, request
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Crear base si no existe
def init_db():
    conn = sqlite3.connect("candidatos.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS candidatos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
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

@app.route("/")
def home():
    return "Perfil.Work Backend OK"

@app.route("/crear-cv", methods=["POST"])
def crear_cv():

    nombre = request.form.get("nombre", "")
    correo = request.form.get("correo", "")
    whatsapp = request.form.get("whatsapp", "")
    region = request.form.get("region", "")
    cargo = request.form.get("cargo", "")
    area = request.form.get("area", "")
    experiencia = request.form.get("experiencia", "")
    nivel = request.form.get("nivel", "")
    sueldo = request.form.get("sueldo", "")
    detalle = request.form.get("detalle", "")

    conn = sqlite3.connect("candidatos.db")
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO candidatos (
        fecha,nombre,correo,whatsapp,region,cargo,area,
        experiencia,nivel,sueldo,detalle
    )
    VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        nombre, correo, whatsapp, region, cargo, area,
        experiencia, nivel, sueldo, detalle
    ))

    conn.commit()
    conn.close()

    return f"""
    <html>
    <head>
    <title>CV recibido</title>
    <style>
    body {{
        font-family: Arial;
        background:#f8fafc;
        display:flex;
        justify-content:center;
        align-items:center;
        height:100vh;
        margin:0;
    }}
    .box {{
        background:white;
        padding:40px;
        border-radius:24px;
        box-shadow:0 15px 35px rgba(0,0,0,.08);
        max-width:580px;
        text-align:center;
    }}
    h1 {{
        color:#2563eb;
        margin-bottom:15px;
    }}
    p {{
        color:#475569;
        font-size:18px;
        line-height:1.5;
    }}
    .emoji {{
        font-size:54px;
        margin-bottom:16px;
    }}
    </style>
    </head>
    <body>
        <div class="box">
            <div class="emoji">🚀</div>
            <h1>{nombre}, recibimos tu CV</h1>
            <p>
            Ya guardamos tus datos correctamente.<br>
            Estamos preparando una versión profesional con IA.
            </p>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
