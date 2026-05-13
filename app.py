import os
import json
import re
from io import BytesIO

from flask import Flask, request, Response
from flask_cors import CORS
from openai import OpenAI
from supabase import create_client
from xhtml2pdf import pisa

import docx
import PyPDF2


app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SUPABASE_URL = "https://kybticlgyamdcthljcov.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def extraer_texto(file):
    if not file:
        return ""
    filename = (file.filename or "").lower()
    try:
        if filename.endswith(".docx"):
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        elif filename.endswith(".pdf"):
            reader = PyPDF2.PdfReader(file)
            texto = ""
            for page in reader.pages:
                texto += page.extract_text() or ""
            return texto
    except Exception as e:
        print("ERROR EXTRACCION:", e)
    return ""


def preprocesar_cv(texto):
    lineas = [re.sub(r"\s+", " ", l.strip()) for l in texto.split("\n") if l.strip()]
    return "\n".join(lineas)[:12000]


def extraer_json(texto):
    try:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print("ERROR JSON:", e)
    return None


def mejorar_cv(texto_cv, info_extra, cargo, area, nivel, experiencia_anios):
    prompt = f"""
Eres un experto en recursos humanos especializado en talento tecnico industrial en Chile, con 30 anos de experiencia reclutando perfiles operativos, tecnicos y profesionales en mineria, construccion, mantenimiento e industria.

Tu mision es leer TODO el contenido del CV y la informacion adicional, y reorganizar esa informacion en un CV profesional estructurado. No es solo ordenar — es interpretar y distribuir correctamente cada dato en la seccion que le corresponde.

DATOS DEL FORMULARIO:
- Cargo: {cargo}
- Area: {area}
- Anos de experiencia declarados: {experiencia_anios}
- Nivel: {nivel}

CV ORIGINAL DEL CANDIDATO (lee todo antes de escribir):
{texto_cv}

INFORMACION ADICIONAL DEL CANDIDATO:
{info_extra}

INSTRUCCIONES CRITICAS — sigue cada una al pie de la letra:

1. PERFIL: Escribe un parrafo unico de 4-5 lineas construido desde cero leyendo TODA la experiencia del CV. Menciona: cuantos anos lleva en el rubro, en que procesos o especialidades es experto, en que industrias o tipos de proyectos ha trabajado, y algun dato especifico que lo diferencie. NO copies la informacion adicional directamente aqui. NO uses frases vacias como "profesional comprometido", "orientado a resultados" o similares.

2. EXPERIENCIA: Ordena del trabajo mas reciente al mas antiguo. Cada entrada debe tener empresa, cargo, periodo y funciones en bullets concretos. Las funciones NO deben repetir el nombre del proyecto — deben describir QUE HIZO el candidato especificamente.

3. COMPETENCIAS: Incluye solo habilidades tecnicas reales — procesos, equipos, herramientas, normas — extraidas del CV y de la informacion adicional. Si la info adicional menciona procesos de soldadura, equipos, sistemas o herramientas, incluyelos aqui.

4. CERTIFICACIONES: Incluye TODAS las calificaciones, certificados, cursos, normas o habilitaciones mencionadas en cualquier parte del CV o de la informacion adicional. Si dice "calificado 2G, 3G, 4G" es una certificacion. Si menciono un curso, es una certificacion.

5. DISPONIBILIDAD: Extrae de la informacion adicional todo lo relacionado con disponibilidad de turno, regimen de trabajo, licencias de conducir, movilizacion propia, disponibilidad geografica, disponibilidad inmediata, etc.

6. Si la informacion adicional menciona caracteristicas personales como "puntual", "responsable", "trabajo en equipo" — incorporalas al perfil de forma natural, no como lista.

7. NO inventes nada. Solo usa informacion que este en el CV o en la informacion adicional.

8. Corrige ortografia y mejora la redaccion sin cambiar los hechos.

Devuelve SOLO JSON valido con esta estructura exacta, sin texto adicional:

{{
  "perfil": "Parrafo unico de 4-5 lineas personalizado y especifico.",
  "experiencia": [
    {{
      "empresa": "Nombre empresa",
      "cargo": "Cargo desempenado",
      "periodo": "Ano inicio - Ano termino",
      "funciones": ["Funcion concreta 1", "Funcion concreta 2", "Funcion concreta 3"]
    }}
  ],
  "formacion": [
    {{
      "titulo": "Titulo o carrera",
      "institucion": "Institucion",
      "anio": "Ano"
    }}
  ],
  "competencias": ["Habilidad tecnica 1", "Habilidad tecnica 2"],
  "certificaciones": ["Certificacion o calificacion 1", "Certificacion 2"],
  "disponibilidad": "Disponibilidad, turno, licencias, movilizacion, etc."
}}
"""
    try:
        respuesta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Responde SOLO con JSON válido. Sin markdown ni explicaciones."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        contenido = respuesta.choices[0].message.content.strip()
        contenido = contenido.replace("```json", "").replace("```", "")
        data = extraer_json(contenido)
        if not data:
            raise Exception("JSON invalido")
    except Exception as e:
        print("ERROR OPENAI:", e)
        data = {"perfil": info_extra, "experiencia": [], "formacion": [], "competencias": [], "certificaciones": [], "disponibilidad": ""}

    # Normalizar experiencia
    experiencias_ok = []
    for exp in data.get("experiencia", []):
        if isinstance(exp, dict):
            experiencias_ok.append({
                "empresa": str(exp.get("empresa", "")),
                "cargo": str(exp.get("cargo", "")),
                "periodo": str(exp.get("periodo", "")),
                "funciones": [str(f) for f in exp.get("funciones", [])] if isinstance(exp.get("funciones"), list) else []
            })
        elif isinstance(exp, str):
            experiencias_ok.append({"empresa": exp, "cargo": "", "periodo": "", "funciones": []})
    data["experiencia"] = experiencias_ok

    # Normalizar formación
    formacion_ok = []
    for item in data.get("formacion", []):
        if isinstance(item, dict):
            anio = str(item.get("anio", "")).strip()
            if anio.lower() in ["año", "anio", "n/a", "-", ""]:
                anio = ""
            formacion_ok.append({
                "titulo": str(item.get("titulo", "")),
                "institucion": str(item.get("institucion", "")),
                "anio": anio
            })
        elif isinstance(item, str):
            formacion_ok.append({"titulo": item, "institucion": "", "anio": ""})
    data["formacion"] = formacion_ok

    data["competencias"] = [str(c) for c in data.get("competencias", [])] if isinstance(data.get("competencias"), list) else []
    data["certificaciones"] = [str(c) for c in data.get("certificaciones", [])] if isinstance(data.get("certificaciones"), list) else []
    data["perfil"] = str(data.get("perfil", ""))
    data["disponibilidad"] = str(data.get("disponibilidad", ""))
    return data


def generar_html(nombre, cargo, email, telefono, region, sueldo, nivel, area, data):

    # Experiencia
    exp_html = ""
    for exp in data["experiencia"][:8]:
        funciones_items = "".join([f"<li>{f}</li>" for f in exp["funciones"][:5]])
        funciones_block = f'<ul class="exp-bullets">{funciones_items}</ul>' if funciones_items else ""
        periodo = f'<span class="exp-periodo">{exp["periodo"]}</span>' if exp["periodo"] else ""
        exp_html += f"""
        <div class="exp-card">
            <div class="exp-top">
                <div class="exp-empresa">{exp['empresa']}</div>
                <div class="exp-periodo-wrap">{periodo}</div>
            </div>
            <div class="exp-cargo">{exp['cargo']}</div>
            {funciones_block}
        </div>"""

    # Formación
    formacion_items = ""
    for f in data["formacion"][:5]:
        anio = f" · {f['anio']}" if f["anio"] else ""
        inst = f" — {f['institucion']}" if f["institucion"] else ""
        formacion_items += f"<li><strong>{f['titulo']}</strong>{inst}{anio}</li>"
    formacion_html = f'<ul class="lista-simple">{formacion_items}</ul>' if formacion_items else ""

    # Competencias
    comp_items = "".join([f"<li>{c}</li>" for c in data["competencias"][:12]])
    competencias_html = f'<ul class="lista-pills">{comp_items}</ul>' if comp_items else ""

    # Certificaciones
    cert_items = "".join([f"<li>{c}</li>" for c in data["certificaciones"][:8]])
    certs_html = f'<ul class="lista-simple">{cert_items}</ul>' if cert_items else ""

    # Disponibilidad
    disp_html = f'<div class="disp-box">{data["disponibilidad"]}</div>' if data["disponibilidad"] else ""

    # Info contacto
    contacto_partes = []
    if region: contacto_partes.append(f"Región {region}")
    if email: contacto_partes.append(email)
    if telefono: contacto_partes.append(telefono)
    contacto_str = "  |  ".join(contacto_partes)

    # Pretensión salarial
    sueldo_html = f'<div class="sueldo">Pretensión salarial: <strong>${sueldo} Pesos Líquidos</strong></div>' if sueldo and sueldo.strip() else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
@page {{
    size: A4;
    margin: 18mm 18mm 15mm 18mm;
}}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: Helvetica, Arial, sans-serif;
    font-size: 11pt;
    color: #1e293b;
    background: #ffffff;
    line-height: 1.5;
}}

/* HEADER */
.header {{
    padding-bottom: 14px;
    margin-bottom: 18px;
    border-bottom: none;
}}

.logo-row {{
    display: block;
    text-align: right;
    margin-bottom: 12px;
}}

.logo-img {{
    height: 44px;
    display: block;
    margin-left: auto;
}}

.nombre {{
    font-size: 22pt;
    font-weight: bold;
    color: #0f172a;
    line-height: 1.2;
    margin-bottom: 4px;
}}

.cargo-titulo {{
    font-size: 12pt;
    color: #114f96;
    font-weight: bold;
    margin-bottom: 8px;
}}

.contacto {{
    font-size: 10pt;
    color: #64748b;
    margin-bottom: 4px;
}}

.sueldo {{
    font-size: 10pt;
    color: #475569;
    margin-top: 4px;
    margin-bottom: 18px;
}}

/* SECCIONES */
.section {{
    margin-bottom: 16px;
}}

.section-title {{
    font-size: 13pt;
    font-weight: bold;
    color: #114f96;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    padding-bottom: 6px;
    margin-bottom: 12px;
    border-bottom: 1.5px solid #e05a4e;
}}

/* PERFIL */
.perfil-texto {{
    font-size: 11pt;
    color: #334155;
    line-height: 1.7;
}}

/* EXPERIENCIA */
.exp-card {{
    margin-bottom: 16px;
    padding-bottom: 14px;
    border-bottom: none;
    padding-left: 10px;
    border-left: 3px solid #e8edf2;
}}

.exp-top {{
    display: table;
    width: 100%;
    margin-bottom: 2px;
}}

.exp-empresa {{
    font-size: 11pt;
    font-weight: bold;
    color: #0f172a;
    display: table-cell;
}}

.exp-periodo-wrap {{
    display: table-cell;
    text-align: right;
    vertical-align: top;
    white-space: nowrap;
    padding-left: 8px;
}}

.exp-periodo {{
    font-size: 9pt;
    color: #94a3b8;
    font-style: italic;
}}

.exp-cargo {{
    font-size: 10pt;
    color: #4a90d9;
    font-weight: 600;
    margin-bottom: 6px;
    margin-top: 2px;
    font-style: italic;
}}

.exp-bullets {{
    padding-left: 16px;
    margin-top: 4px;
}}

.exp-bullets li {{
    font-size: 10.5pt;
    color: #475569;
    margin-bottom: 3px;
    line-height: 1.5;
}}

/* LISTAS */
.lista-simple {{
    padding-left: 16px;
}}

.lista-simple li {{
    font-size: 10.5pt;
    color: #334155;
    margin-bottom: 4px;
    line-height: 1.5;
}}

.lista-pills {{
    padding-left: 0;
    list-style: none;
}}

.lista-pills li {{
    font-size: 10.5pt;
    color: #334155;
    margin-bottom: 4px;
    padding-left: 12px;
    line-height: 1.5;
}}

.lista-pills li:before {{
    content: "> ";
    color: #e05a4e;
}}

/* DISPONIBILIDAD */
.disp-box {{
    font-size: 10.5pt;
    color: #334155;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 10px 14px;
    line-height: 1.6;
}}

/* FOOTER */
.footer {{
    border-top: 0.5px solid #e2e8f0;
    padding-top: 8px;
    margin-top: 20px;
}}

.footer-text {{
    font-size: 8pt;
    color: #94a3b8;
}}

.footer-bold {{
    color: #64748b;
    font-weight: bold;
}}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="logo-row">
        <img src="https://raw.githubusercontent.com/perfilwork/perfilwork-backend/main/logo.png" class="logo-img" alt="Perfil.Work">
    </div>
    <div class="nombre">{nombre}</div>
    <div class="cargo-titulo">{cargo}</div>
    <div class="contacto">{contacto_str}</div>
    {sueldo_html}
</div>

<!-- PERFIL -->
{f'<div class="section"><div class="section-title">Perfil Profesional</div><div class="perfil-texto">{data["perfil"]}</div></div>' if data["perfil"] else ""}

<!-- EXPERIENCIA -->
{f'<div class="section"><div class="section-title">Experiencia Laboral</div>{exp_html}</div>' if exp_html else ""}

<!-- FORMACIÓN -->
{f'<div class="section"><div class="section-title">Formación</div>{formacion_html}</div>' if formacion_html else ""}

<!-- COMPETENCIAS -->
{f'<div class="section"><div class="section-title">Competencias Técnicas</div>{competencias_html}</div>' if competencias_html else ""}

<!-- CERTIFICACIONES -->
{f'<div class="section"><div class="section-title">Certificaciones</div>{certs_html}</div>' if certs_html else ""}

<!-- DISPONIBILIDAD -->
{f'<div class="section"><div class="section-title">Disponibilidad</div>{disp_html}</div>' if disp_html else ""}

<!-- FOOTER -->
<div class="footer">
    <span class="footer-text">Generado por <span class="footer-bold">Perfil.Work</span> | Talento que Impulsa Resultados</span>
</div>

</body>
</html>"""


def generar_pdf(nombre, cargo, email, telefono, region, sueldo, nivel, area, experiencia, data):
    html = generar_html(nombre, cargo, email, telefono, region, sueldo, nivel, area, data)
    buffer = BytesIO()
    pisa.CreatePDF(html, dest=buffer)
    buffer.seek(0)
    return buffer


@app.route("/crear-cv", methods=["GET", "POST"])
def crear_cv():
    if request.method == "GET":
        return "Servicio activo"
    try:
        file        = request.files.get("cv")
        info_extra  = request.form.get("info_extra", "")
        nombre      = request.form.get("nombre", "Nombre")
        cargo       = request.form.get("cargo", "Cargo")
        email       = request.form.get("email", "")
        telefono    = request.form.get("telefono", "")
        region      = request.form.get("region", "")
        area        = request.form.get("area", "")
        experiencia = request.form.get("experiencia", "")
        nivel       = request.form.get("nivel", "")
        sueldo      = request.form.get("sueldo", "")

        try:
            supabase.table("candidatos").insert({
                "nombre": nombre, "email": email, "telefono": telefono,
                "region": region, "cargo": cargo, "area": area,
                "experiencia": experiencia, "nivel": nivel,
                "sueldo": sueldo, "info_extra": info_extra, "cv_url": ""
            }).execute()
            print("Candidato guardado")
        except Exception as e:
            print("ERROR SUPABASE:", e)

        texto = extraer_texto(file)
        texto_procesado = preprocesar_cv(texto)
        data = mejorar_cv(texto_procesado, info_extra, cargo, area, nivel, experiencia)
        pdf = generar_pdf(nombre, cargo, email, telefono, region, sueldo, nivel, area, experiencia, data)

        return Response(
            pdf.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename=cv_mejorado.pdf"}
        )
    except Exception as e:
        print("ERROR GENERAL:", e)
        return "Error interno del servidor", 500


if __name__ == "__main__":
    app.run(debug=True)
