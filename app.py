from flask import Flask, request
import sqlite3
from datetime import datetime

app = Flask(__name__)

# ------------------------
# BASE DE DATOS
# ------------------------
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

# ------------------------
# HOME
# ------------------------
@app.route("/")
def home():
    return "Perfil.Work Backend OK"

# ------------------------
# FORMULARIO
# ------------------------
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
    h1 {{color:#2563eb}}
    p {{font-size:18px;color:#475569;line-height:1.5}}
    </style>
    </head>
    <body>
        <div class="box">
            <div style="font-size:54px;">🚀</div>
            <h1>{nombre}, recibimos tu CV</h1>
            <p>
            Ya guardamos tus datos correctamente.<br>
            Estamos preparando una versión profesional con IA.
            </p>
        </div>
    </body>
    </html>
    """

# ------------------------
# PANEL LEADS
# ------------------------
@app.route("/leads")
def leads():

    conn = sqlite3.connect("candidatos.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT fecha,nombre,correo,whatsapp,region,cargo,
           area,experiencia,nivel,sueldo
    FROM candidatos
    ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    tabla = ""

    for r in rows:
        tabla += f"""
        <tr>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td>{r[2]}</td>
            <td>{r[3]}</td>
            <td>{r[4]}</td>
            <td>{r[5]}</td>
            <td>{r[6]}</td>
            <td>{r[7]}</td>
            <td>{r[8]}</td>
            <td>{r[9]}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
    <style>
    body {{
        font-family: Arial;
        background:#f8fafc;
        padding:30px;
    }}
    h1 {{
        color:#2563eb;
        margin-bottom:20px;
    }}
    table {{
        width:100%;
        border-collapse:collapse;
        background:white;
        box-shadow:0 10px 25px rgba(0,0,0,.05);
        border-radius:14px;
        overflow:hidden;
    }}
    th,td {{
        padding:12px;
        border-bottom:1px solid #e2e8f0;
        text-align:left;
        font-size:14px;
    }}
    th {{
        background:#2563eb;
        color:white;
    }}
    tr:hover {{
        background:#f1f5f9;
    }}
    </style>
    </head>
    <body>
        <h1>📋 Leads Perfil.Work</h1>
        <table>
            <tr>
                <th>Fecha</th>
                <th>Nombre</th>
                <th>Correo</th>
                <th>WhatsApp</th>
                <th>Región</th>
                <th>Cargo</th>
                <th>Área</th>
                <th>Exp.</th>
                <th>Nivel</th>
                <th>Sueldo</th>
            </tr>
            {tabla}
        </table>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
