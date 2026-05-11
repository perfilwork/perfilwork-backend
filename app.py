````python
import os
import json
import re
from io import BytesIO

from flask import Flask, request, Response
from flask_cors import CORS
from openai import OpenAI
from supabase import create_client

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    Table,
    TableStyle
)

from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

import docx
import PyPDF2


# =========================
# APP
# =========================

app = Flask(__name__)
CORS(app)


# =========================
# OPENAI
# =========================

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# =========================
# SUPABASE
# =========================

SUPABASE_URL = "https://kybticlgyamdcthljcov.supabase.co"

SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# STYLES
# =========================

styles = getSampleStyleSheet()

styles.add(
    ParagraphStyle(
        name="Body",
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8
    )
)

styles.add(
    ParagraphStyle(
        name="SectionTitle",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.white,
        spaceAfter=10
    )
)

styles.add(
    ParagraphStyle(
        name="Name",
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6
    )
)

styles.add(
    ParagraphStyle(
        name="Cargo",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#2563eb"),
        spaceAfter=8
    )
)

styles.add(
    ParagraphStyle(
        name="Contact",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12
    )
)

styles.add(
    ParagraphStyle(
        name="SidebarText",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=7
    )
)

styles.add(
    ParagraphStyle(
        name="Experience",
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=10
    )
)


# =========================
# EXTRAER TEXTO
# =========================

def extraer_texto(file):

    if not file:
        return ""

    filename = (file.filename or "").lower()

    try:

        if filename.endswith(".docx"):

            doc = docx.Document(file)

            texto = "\n".join(
                [
                    p.text
                    for p in doc.paragraphs
                    if p.text.strip()
                ]
            )

            return texto

        elif filename.endswith(".pdf"):

            reader = PyPDF2.PdfReader(file)

            texto = ""

            for page in reader.pages:
                texto += page.extract_text() or ""

            return texto

    except Exception as e:
        print("ERROR EXTRACCIÓN:", e)

    return ""


# =========================
# PREPROCESAR
# =========================

def preprocesar_cv(texto):

    lineas = [
        re.sub(r"\s+", " ", l.strip())
        for l in texto.split("\n")
        if l.strip()
    ]

    texto_limpio = "\n".join(lineas)

    return texto_limpio[:12000]


# =========================
# NORMALIZAR LISTA
# =========================

def normalizar_lista(valor):

    if isinstance(valor, list):
        return valor

    if isinstance(valor, str):
        return [valor]

    return []


# =========================
# LIMPIAR LISTA
# =========================

def limpiar_lista(lista):

    lista = normalizar_lista(lista)

    resultado = []

    for item in lista:

        if isinstance(item, dict):

            texto = " - ".join(
                [
                    str(v)
                    for v in item.values()
                    if v
                ]
            )

            resultado.append(texto)

        else:
            resultado.append(str(item))

    return resultado


# =========================
# EXTRAER JSON
# =========================

def extraer_json(texto):

    try:

        match = re.search(
            r"\{.*\}",
            texto,
            re.DOTALL
        )

        if match:
            return json.loads(match.group())

    except Exception as e:
        print("ERROR EXTRAER JSON:", e)

    return None


# =========================
# IA
# =========================

def mejorar_cv(texto_cv, info_extra):

    prompt = f"""
Eres especialista en reclutamiento técnico industrial.

Debes transformar este CV en una versión:
- clara
- profesional
- recruiter-friendly
- compacta
- moderna
- fácil de leer

NO inventes información.

Devuelve SOLO JSON válido.

Formato:

{{
"perfil": "...",
"formacion": ["..."],
"experiencia": ["..."],
"competencias": ["..."],
"certificaciones": ["..."],
"info_relevante": "..."
}}

CV:
{texto_cv}

Información adicional:
{info_extra}
"""

    try:

        respuesta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Responde SOLO JSON válido."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            max_tokens=1300
        )

        contenido = (
            respuesta
            .choices[0]
            .message
            .content
            .strip()
        )

        contenido = contenido.replace(
            "```json",
            ""
        )

        contenido = contenido.replace(
            "```",
            ""
        )

        data = extraer_json(contenido)

        if not data:
            raise Exception("JSON inválido")

    except Exception as e:

        print("ERROR OPENAI / JSON:", e)

        data = {
            "perfil": info_extra,
            "formacion": [],
            "experiencia": [],
            "competencias": [],
            "certificaciones": [],
            "info_relevante": info_extra
        }

    data["perfil"] = str(
        data.get("perfil", "")
    )

    data["experiencia"] = limpiar_lista(
        data.get("experiencia", [])
    )

    data["formacion"] = limpiar_lista(
        data.get("formacion", [])
    )

    data["certificaciones"] = limpiar_lista(
        data.get("certificaciones", [])
    )

    data["competencias"] = limpiar_lista(
        data.get("competencias", [])
    )

    data["info_relevante"] = str(
        data.get("info_relevante", info_extra)
    )

    return data


# =========================
# HEADER FOOTER
# =========================

def draw_header_footer(canvas, doc):

    width, height = A4

    if os.path.exists("logo.png"):

        try:

            canvas.drawImage(
                "logo.png",
                40,
                height - 55,
                width=90,
                height=28,
                preserveAspectRatio=True,
                mask='auto'
            )

        except Exception as e:
            print("ERROR LOGO:", e)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#94a3b8"))

    canvas.drawString(
        40,
        18,
        "Perfil.Work · Talento Técnico y Profesional"
    )

    canvas.drawRightString(
        width - 40,
        18,
        "www.perfil.work"
    )


# =========================
# TITULO SECCION
# =========================

def titulo_seccion(texto):

    tabla = Table(
        [[Paragraph(texto, styles["SectionTitle"])]],
        colWidths=[180]
    )

    tabla.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#2563eb")),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ])
    )

    return tabla


# =========================
# PDF
# =========================

def generar_pdf(nombre, cargo, contacto, data):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=35,
        rightMargin=35,
        topMargin=70,
        bottomMargin=35
    )

    elements = []

    # HEADER

    elements.append(
        Paragraph(
            nombre,
            styles["Name"]
        )
    )

    elements.append(
        Paragraph(
            cargo,
            styles["Cargo"]
        )
    )

    elements.append(
        Paragraph(
            contacto,
            styles["Contact"]
        )
    )

    elements.append(
        Spacer(1, 10)
    )

    # RESUMEN

    elements.append(
        titulo_seccion("RESUMEN TÉCNICO")
    )

    elements.append(
        Spacer(1, 10)
    )

    resumen_box = Table(
        [[Paragraph(data["perfil"], styles["Body"])]],
        colWidths=[520]
    )

    resumen_box.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ])
    )

    elements.append(resumen_box)

    elements.append(
        Spacer(1, 18)
    )

    # EXPERIENCIA

    elements.append(
        titulo_seccion("EXPERIENCIA LABORAL")
    )

    elements.append(
        Spacer(1, 10)
    )

    for experiencia in data["experiencia"][:8]:

        limpio = experiencia.lstrip("-• ").strip()

        experiencia_box = Table(
            [[Paragraph(limpio, styles["Experience"])]],
            colWidths=[520]
        )

        experiencia_box.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ])
        )

        elements.append(experiencia_box)

        elements.append(
            Spacer(1, 10)
        )

    # TABLA LATERAL

    izquierda = []

    # FORMACIÓN
    izquierda.append(
        titulo_seccion("FORMACIÓN")
    )

    izquierda.append(
        Spacer(1, 8)
    )

    for item in data["formacion"][:5]:

        izquierda.append(
            Paragraph(
                f"• {item}",
                styles["SidebarText"]
            )
        )

    izquierda.append(
        Spacer(1, 12)
    )

    # HABILIDADES
    izquierda.append(
        titulo_seccion("HABILIDADES")
    )

    izquierda.append(
        Spacer(1, 8)
    )

    for item in data["competencias"][:10]:

        skill = Table(
            [[Paragraph(item, styles["SidebarText"])]],
            colWidths=[170]
        )

        skill.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#dbeafe")),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#1d4ed8")),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ])
        )

        izquierda.append(skill)

        izquierda.append(
            Spacer(1, 5)
        )

    izquierda.append(
        Spacer(1, 12)
    )

    # CERTIFICACIONES
    izquierda.append(
        titulo_seccion("CERTIFICACIONES")
    )

    izquierda.append(
        Spacer(1, 8)
    )

    for item in data["certificaciones"][:5]:

        izquierda.append(
            Paragraph(
                f"• {item}",
                styles["SidebarText"]
            )
        )

    for item in izquierda:
        elements.append(item)

    # DATOS EXTRA

    if data["info_relevante"]:

        elements.append(
            Spacer(1, 16)
        )

        elements.append(
            titulo_seccion("DATOS ADICIONALES")
        )

        elements.append(
            Spacer(1, 10)
        )

        extra_box = Table(
            [[Paragraph(data["info_relevante"], styles["Body"])]],
            colWidths=[520]
        )

        extra_box.setStyle(
            TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ('LEFTPADDING', (0, 0), (-1, -1), 14),
                ('RIGHTPADDING', (0, 0), (-1, -1), 14),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ])
        )

        elements.append(extra_box)

    doc.build(
        elements,
        onFirstPage=draw_header_footer,
        onLaterPages=draw_header_footer
    )

    buffer.seek(0)

    return buffer


# =========================
# ROUTE
# =========================

@app.route("/crear-cv", methods=["GET", "POST"])
def crear_cv():

    if request.method == "GET":
        return "Servicio activo"

    try:

        file = request.files.get("cv")

        info_extra = request.form.get(
            "info_extra",
            ""
        )

        nombre = request.form.get(
            "nombre",
            "Nombre"
        )

        cargo = request.form.get(
            "cargo",
            "Cargo"
        )

        email = request.form.get(
            "email",
            ""
        )

        telefono = request.form.get(
            "telefono",
            ""
        )

        region = request.form.get(
            "region",
            ""
        )

        area = request.form.get(
            "area",
            ""
        )

        experiencia = request.form.get(
            "experiencia",
            ""
        )

        nivel = request.form.get(
            "nivel",
            ""
        )

        sueldo = request.form.get(
            "sueldo",
            ""
        )

        contacto = (
            f"{region} | "
            f"{email} | "
            f"{telefono}"
        )

        try:

            supabase.table(
                "candidatos"
            ).insert({
                "nombre": nombre,
                "email": email,
                "telefono": telefono,
                "region": region,
                "cargo": cargo,
                "area": area,
                "experiencia": experiencia,
                "nivel": nivel,
                "sueldo": sueldo,
                "info_extra": info_extra,
                "cv_url": ""
            }).execute()

            print("✅ Candidato guardado")

        except Exception as e:
            print("ERROR SUPABASE:", e)

        texto = extraer_texto(file)

        texto_procesado = preprocesar_cv(
            texto
        )

        data = mejorar_cv(
            texto_procesado,
            info_extra
        )

        pdf = generar_pdf(
            nombre,
            cargo,
            contacto,
            data
        )

        return Response(
            pdf.getvalue(),
            mimetype="application/pdf",
            headers={
                "Content-Disposition":
                "attachment; filename=cv_mejorado.pdf"
            }
        )

    except Exception as e:

        print("ERROR GENERAL:", e)

        return "Error interno del servidor", 500


if __name__ == "__main__":
    app.run(debug=True)
````
