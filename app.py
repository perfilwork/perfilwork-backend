from flask import Flask, request
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB_NAME = "candidatos.db"


# ---------------------------------------------------
# BASE DE DATOS
# ---------------------------------------------------
def conectar():
    return sqlite3.connect(DB_NAME)


def iniciar_db():
    conn = conectar()
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


iniciar_db()


# ---------------------------------------------------
# HOME
# ---------------------------------------------------
@app.route("/")
def home():
    return """
    <h2 style='font-family:Arial;padding:30px'>
    Perfil.Work Backend OK 🚀
    </h2>
    """


# ---------------------------------------------------
# GUARDAR CANDIDATO
# ---------------------------------------------------
def guardar_candidato(data):

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO candidatos (
        fecha,nombre,correo,whatsapp,region,cargo,
        area,experiencia,nivel,sueldo,detalle
    )
    VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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


# ---------------------------------------------------
# FORMULARIO POST
# ---------------------------------------------------
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

    guardar_candidato(data)

    return f"""
    <html>
    <head>
    <style>
    body {{
        font-family:Arial;
        background:#f8fafc;
        display:flex;
        justify-content:center;
        align-items:center;
        height:100vh;
        margin:0;
    }}
    .box {{
        background:#fff;
        padding:42px;
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
        line-height:1.55;
    }}
    .emoji {{
        font-size:56px;
        margin-bottom:14px;
    }}
    </style>
    </head>
    <body>
        <div class="box">
            <div class="emoji">🚀</div>
            <h1>{data["nombre"]}, recibimos tu CV</h1>
            <p>
            Tus datos fueron guardados correctamente.<br>
            Estamos preparando una versión profesional con IA.
            </p>
        </div>
    </body>
    </html>
    """


# ---------------------------------------------------
# PANEL LEADS
# ---------------------------------------------------
@app.route("/leads")
def leads():

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    SELECT fecha,nombre,correo,whatsapp,region,cargo,
           area,experiencia,nivel,sueldo
    FROM candidatos
    ORDER BY id DESC
    """)

    filas = cur.fetchall()
    conn.close()

    rows = ""

    for f in filas:
        rows += f"""
        <tr>
            <td>{f[0]}</td>
            <td>{f[1]}</td>
            <td>{f[2]}</td>
            <td>{f[3]}</td>
            <td>{f[4]}</td>
            <td>{f[5]}</td>
            <td>{f[6]}</td>
            <td>{f[7]}</td>
            <td>{f[8]}</td>
            <td>{f[9]}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
    <style>
    body {{
        font-family:Arial;
        background:#f8fafc;
        padding:28px;
    }}
    h1 {{
        color:#2563eb;
        margin-bottom:20px;
    }}
    table {{
        width:100%;
        border-collapse:collapse;
        background:#fff;
        box-shadow:0 10px 25px rgba(0,0,0,.05);
        border-radius:14px;
        overflow:hidden;
    }}
    th {{
        background:#2563eb;
        color:white;
        padding:12px;
        font-size:14px;
        text-align:left;
    }}
    td {{
        padding:12px;
        border-bottom:1px solid #e2e8f0;
        font-size:14px;
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
            {rows}
        </table>

    </body>
    </html>
    """


# ---------------------------------------------------
# RUN
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
