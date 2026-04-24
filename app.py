from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def home():
    return "Perfil.Work Backend OK"

@app.route("/crear-cv", methods=["POST"])
def crear_cv():

    nombre = request.form.get("nombre", "Candidato")

    return f"""
    <html>
    <head>
    <title>CV en Proceso</title>
    <style>
    body {{
        font-family: Arial, sans-serif;
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
        border-radius:20px;
        box-shadow:0 10px 30px rgba(0,0,0,.08);
        max-width:560px;
        text-align:center;
    }}
    h1 {{
        color:#2563eb;
        margin-bottom:14px;
    }}
    p {{
        color:#475569;
        font-size:18px;
        line-height:1.5;
    }}
    .ok {{
        font-size:52px;
        margin-bottom:15px;
    }}
    .btn {{
        display:inline-block;
        margin-top:22px;
        background:#e85a47;
        color:white;
        padding:14px 24px;
        border-radius:14px;
        text-decoration:none;
        font-weight:bold;
    }}
    </style>
    </head>
    <body>
        <div class="box">
            <div class="ok">🚀</div>
            <h1>{nombre}, recibimos tu CV</h1>
            <p>
            Ya estamos trabajando en una versión más profesional con IA.
            En breve podrás descargar tu nuevo CV.
            </p>
            <a href="file:///C:/RUTA-DE-TU-PC/candidato.html" class="btn">Volver al formulario</a>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
