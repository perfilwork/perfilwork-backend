from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Perfil.Work Backend OK"

@app.route("/crear-cv", methods=["POST"])
def crear_cv():
    data = request.form

    nombre = data.get("nombre", "")
    correo = data.get("correo", "")
    cargo = data.get("cargo", "")
    region = data.get("region", "")
    sueldo = data.get("sueldo", "")

    return jsonify({
        "ok": True,
        "mensaje": "Formulario recibido correctamente",
        "datos": {
            "nombre": nombre,
            "correo": correo,
            "cargo": cargo,
            "region": region,
            "sueldo": sueldo
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
