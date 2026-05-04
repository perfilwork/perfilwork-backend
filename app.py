import os
import json
from io import BytesIO
from flask import Flask, request, send_file
from flask_cors import CORS
from openai import OpenAI

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Image

import docx
import PyPDF2

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

styles = getSampleStyleSheet()

# =========================
# EXTRAER TEXTO CV
# =========================

def extraer_texto(file):
    filename = file.filename.lower()

    if filename.endswith(".docx"):
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs])

    elif filename.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file)
        texto = ""
        for page in reader.pages:
            texto += page.extract_text() or ""
        return texto

    return ""

# =========================
# IA (LÓGICA CORRECTA)
# =========================

def mejorar_cv(cv_texto, info_extra):

    prompt = f"""
Eres especialista en reclutamiento técnico industrial en Chile.

Tu tarea es MEJORAR un CV real.

NO estás creando uno nuevo.

---

OBJETIVO:
- Ordenar información
- Mejorar redacción
- Hacerlo claro y profesional
- Mantener la trayectoria completa del candidato

---

REGLAS CRÍTICAS:

- NO inventar información
- NO eliminar experiencia relevante
- NO resumir en exceso
- NO agregar frases genéricas
- NO agregar notas ni explicaciones

---

SOBRE EXPERIENCIA:

- Si hay muchas experiencias, puedes AGRUPAR por tipo o continuidad
- Mantener trayectoria clara (cronológica o agrupada)
- NO eliminar trabajos reales

---

SOBRE INFORMACIÓN ADICIONAL:

- Crear sección: "INFORMACIÓN RELEVANTE"
- Integrar sin duplicar contenido

---

CV ORIGINAL:
{cv_texto}

---

INFORMACIÓN ADICIONAL:
{info_extra}

---

FORMATO DE RESPUESTA (JSON PURO):

{{
  "perfil": "...",
  "experiencia": ["...", "..."],
  "formacion": ["...", "..."],
  "certificaciones": ["...", "..."],
  "competencias": ["...", "..."],
  "info_relevante": "..."
}}
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        contenido = r.choices[0].message.content
        contenido = contenido.replace("```json", "").replace("```", "")

        return json.loads(contenido)

    except Exception as e:
        print("ERROR IA:", e)

        return {
            "perfil": cv_texto[:300],
            "experiencia": [],
            "formacion": [],
            "certificaciones": [],
            "competencias": [],
            "info_relevante": info_extra
        }

# =========================
# PDF LIMPIO Y LEGIBLE
# =========================

def generar_pdf(nombre, cargo, contacto, data):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []

    # LOGO
    if os.path.exists("logo.png"):
        logo = Image("logo.png", width=120, height=40)
        elements.append(logo)
        elements.append(Spacer(1, 10))

    # HEADER
    elements.append(Paragraph(f"<b>{nombre}</b>", styles["Title"]))
    elements.append(Paragraph(cargo, styles["Normal"]))
    elements.append(Paragraph(contacto, styles["Normal"]))
    elements.append(Spacer(1, 12))

    # PERFIL
    elements.append(Paragraph("<b>PERFIL PROFESIONAL</b>", styles["Heading3"]))
    elements.append(Paragraph(data.get("perfil", ""), styles["Normal"]))
    elements.append(Spacer(1, 10))

    # EXPERIENCIA
    if data.get("experiencia"):
        elements.append(Paragraph("<b>EXPERIENCIA</b>", styles["Heading3"]))
        elements.append(
            ListFlowable(
                [Paragraph(e, styles["Normal"]) for e in data["experiencia"]]
            )
        )
        elements.append(Spacer(1, 10))

    # FORMACIÓN
    if data.get("formacion"):
        elements.append(Paragraph("<b>FORMACIÓN</b>", styles["Heading3"]))
        elements.append(
            ListFlowable(
                [Paragraph(f, styles["Normal"]) for f in data["formacion"]]
            )
        )
        elements.append(Spacer(1, 10))

    # CERTIFICACIONES
    if data.get("certificaciones"):
        elements.append(Paragraph("<b>CERTIFICACIONES</b>", styles["Heading3"]))
        elements.append(
            ListFlowable(
                [Paragraph(c, styles["Normal"]) for c in data["certificaciones"]]
            )
        )
        elements.append(Spacer(1, 10))

    # COMPETENCIAS
    if data.get("competencias"):
        elements.append(Paragraph("<b>COMPETENCIAS</b>", styles["Heading3"]))
        elements.append(
            ListFlowable(
                [Paragraph(c, styles["Normal"]) for c in data["competencias"]]
            )
        )
        elements.append(Spacer(1, 10))

    # INFO RELEVANTE
    if data.get("info_relevante"):
        elements.append(Paragraph("<b>INFORMACIÓN RELEVANTE</b>", styles["Heading3"]))
        elements.append(Paragraph(data["info_relevante"], styles["Normal"]))

    doc.build(elements)

    buffer.seek(0)
    return buffer

# =========================
# ROUTE
# =========================

@app.route("/crear-cv", methods=["POST"])
def crear_cv():

    file = request.files.get("cv")
    info_extra = request.form.get("info_extra", "")

    nombre = request.form.get("nombre", "Nombre")
    cargo = request.form.get("cargo", "Cargo")

    contacto = f"{request.form.get('region','')} | {request.form.get('email','')} | {request.form.get('telefono','')}"

    texto_cv = extraer_texto(file)

    data_cv = mejorar_cv(texto_cv, info_extra)

    pdf = generar_pdf(nombre, cargo, contacto, data_cv)

    return send_file(
        pdf,
        as_attachment=True,
        download_name="cv_mejorado.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)
