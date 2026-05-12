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


def mejorar_cv(texto_cv, info_extra):
    prompt = f"""
Eres especialista en reclutamiento tecnico industrial en Chile.
Transforma este CV en version profesional recruiter-friendly para mineria, construccion, mantenimiento, electricidad.

REGLAS:
- NO inventes informacion que no este en el CV.
- Experiencias con empresa, cargo, periodo y funciones SEPARADOS.
- Funciones: bullets cortos y concretos.

Devuelve SOLO JSON valido:

{{
  "perfil": "2-3 lineas resumiendo perfil tecnico.",
  "experiencia": [
    {{
      "empresa": "Nombre empresa",
      "cargo": "Cargo",
      "periodo": "Año inicio - Año termino",
      "funciones": ["Funcion 1", "Funcion 2", "Funcion 3"]
    }}
  ],
  "formacion": [
    {{
      "titulo": "Titulo o carrera",
      "institucion": "Institucion",
      "anio": "Año"
    }}
  ],
  "competencias": ["Habilidad 1", "Habilidad 2"],
  "certificaciones": ["Certificacion 1"],
  "info_relevante": "Disponibilidad, licencias, etc."
}}

CV:
{texto_cv}

Info adicional:
{info_extra}
"""
    try:
        respuesta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Responde SOLO JSON valido. Sin markdown ni explicaciones."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1800
        )
        contenido = respuesta.choices[0].message.content.strip()
        contenido = contenido.replace("```json", "").replace("```", "")
        data = extraer_json(contenido)
        if not data:
            raise Exception("JSON invalido")
    except Exception as e:
        print("ERROR OPENAI:", e)
        data = {"perfil": info_extra, "experiencia": [], "formacion": [], "competencias": [], "certificaciones": [], "info_relevante": info_extra}

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

    formacion_ok = []
    for item in data.get("formacion", []):
        if isinstance(item, dict):
            formacion_ok.append({"titulo": str(item.get("titulo", "")), "institucion": str(item.get("institucion", "")), "anio": str(item.get("anio", ""))})
        elif isinstance(item, str):
            formacion_ok.append({"titulo": item, "institucion": "", "anio": ""})
    data["formacion"] = formacion_ok

    data["competencias"] = [str(c) for c in data.get("competencias", [])] if isinstance(data.get("competencias"), list) else []
    data["certificaciones"] = [str(c) for c in data.get("certificaciones", [])] if isinstance(data.get("certificaciones"), list) else []
    data["perfil"] = str(data.get("perfil", ""))
    data["info_relevante"] = str(data.get("info_relevante", ""))
    return data


def obtener_iniciales(nombre):
    partes = nombre.strip().split()
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    elif len(partes) == 1:
        return partes[0][:2].upper()
    return "PW"


def generar_html(nombre, cargo, email, telefono, region, sueldo, nivel, area, data):
    iniciales = obtener_iniciales(nombre)

    badges = []
    if sueldo:
        badges.append(f'<span class="badge">$ {sueldo}</span>')
    if nivel:
        badges.append(f'<span class="badge">{nivel}</span>')
    if area:
        badges.append(f'<span class="badge">{area}</span>')
    badges_html = "".join(badges)

    exp_html = ""
    for exp in data["experiencia"][:7]:
        funciones_items = "".join([f"<li>{f}</li>" for f in exp["funciones"][:4]])
        funciones_block = f'<ul class="exp-bullets">{funciones_items}</ul>' if funciones_items else ""
        exp_html += f"""
        <div class="exp-card">
          <table class="exp-table"><tr>
            <td class="exp-left">
              <div class="exp-empresa">{exp['empresa']}</div>
              <div class="exp-cargo">{exp['cargo']}</div>
            </td>
            <td class="exp-right"><div class="exp-periodo">{exp['periodo']}</div></td>
          </tr></table>
          {funciones_block}
        </div>"""

    formacion_html = ""
    for f in data["formacion"][:4]:
        anio = f"· {f['anio']}" if f["anio"] else ""
        formacion_html += f'<div class="s-edu"><div class="s-edu-titulo">{f["titulo"]}</div><div class="s-edu-inst">{f["institucion"]} {anio}</div></div>'

    skills_html = "".join([f'<span class="skill-pill">{c}</span>' for c in data["competencias"][:10]])
    certs_html = "".join([f'<div class="s-cert"><span class="cert-dot">&#9679;</span><span class="cert-txt">{c}</span></div>' for c in data["certificaciones"][:5]])

    contacto_html = ""
    if email:
        contacto_html += f'<div class="contact-row"><span class="contact-icon">&#9993;</span> <span class="contact-text">{email}</span></div>'
    if telefono:
        contacto_html += f'<div class="contact-row"><span class="contact-icon">&#9742;</span> <span class="contact-text">{telefono}</span></div>'
    if region:
        contacto_html += f'<div class="contact-row"><span class="contact-icon">&#9679;</span> <span class="contact-text">{region}</span></div>'

    info_html = f'<div class="section-label">Informacion adicional</div><div class="info-box">{data["info_relevante"]}</div>' if data["info_relevante"] else ""
    skills_section = f'<div class="s-divider"></div><div class="s-label">Habilidades tecnicas</div><div class="skills-wrap">{skills_html}</div>' if skills_html else ""
    formacion_section = f'<div class="s-divider"></div><div class="s-label">Formacion</div>{formacion_html}' if formacion_html else ""
    certs_section = f'<div class="s-divider"></div><div class="s-label">Certificaciones</div>{certs_html}' if certs_html else ""
    exp_section = f'<div class="section-label">Experiencia laboral</div>{exp_html}' if exp_html else ""

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<style>
@page {{ size: A4; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 13px; color: #334155; background: #ffffff; }}
.layout-table {{ width: 210mm; min-height: 297mm; border-collapse: collapse; }}
.col-sidebar {{ width: 70mm; background-color: #0f2137; vertical-align: top; padding: 20px 15px; }}
.col-main {{ vertical-align: top; padding: 22px 20px 0 20px; background-color: #ffffff; }}
.logo-area {{ text-align: center; padding-bottom: 14px; border-bottom: 1px solid #1e3a5f; margin-bottom: 14px; }}
.logo-text {{ font-size: 16px; color: #e2e8f0; font-weight: bold; margin-bottom: 3px; }}
.logo-light {{ color: #94a3b8; font-weight: normal; }}
.logo-tagline {{ font-size: 9px; color: #475569; letter-spacing: 0.5px; }}
.logo-icons {{ margin-bottom: 5px; }}
.lc {{ display: inline-block; border-radius: 50%; }}
.lc1 {{ width: 16px; height: 16px; background-color: #e05a4e; }}
.lc2 {{ width: 13px; height: 13px; background-color: #4a90d9; margin-left: -4px; vertical-align: bottom; }}
.lc3 {{ width: 10px; height: 10px; background-color: #2ec4a5; margin-left: -5px; vertical-align: bottom; }}
.avatar-wrap {{ text-align: center; margin-bottom: 9px; }}
.avatar-circle {{ display: inline-block; width: 50px; height: 50px; background-color: #1d4ed8; border-radius: 25px; text-align: center; padding-top: 11px; }}
.avatar-text {{ font-size: 18px; font-weight: bold; color: #ffffff; }}
.s-nombre {{ font-size: 13px; font-weight: bold; color: #f1f5f9; text-align: center; margin-bottom: 3px; line-height: 1.3; }}
.s-cargo {{ font-size: 10px; color: #60a5fa; text-align: center; text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 13px; line-height: 1.3; }}
.s-divider {{ height: 1px; background-color: #1e3a5f; margin: 10px 0; }}
.s-label {{ font-size: 9px; color: #60a5fa; text-transform: uppercase; letter-spacing: 1px; font-weight: bold; margin-bottom: 7px; margin-top: 3px; }}
.contact-row {{ margin-bottom: 6px; line-height: 1.5; }}
.contact-icon {{ font-size: 10px; color: #3b82f6; margin-right: 5px; }}
.contact-text {{ font-size: 10px; color: #94a3b8; }}
.skills-wrap {{ margin-bottom: 4px; }}
.skill-pill {{ display: inline-block; background-color: #1e3a5f; color: #93c5fd; font-size: 9px; padding: 3px 8px; border-radius: 10px; margin: 3px 3px 0 0; line-height: 1.5; }}
.s-edu {{ margin-bottom: 8px; }}
.s-edu-titulo {{ font-size: 10px; color: #cbd5e1; font-weight: bold; line-height: 1.4; }}
.s-edu-inst {{ font-size: 9px; color: #64748b; line-height: 1.4; }}
.s-cert {{ margin-bottom: 5px; line-height: 1.5; }}
.cert-dot {{ font-size: 7px; color: #1d4ed8; margin-right: 5px; }}
.cert-txt {{ font-size: 10px; color: #94a3b8; }}
.m-header {{ padding-bottom: 12px; border-bottom: 2px solid #1d4ed8; margin-bottom: 14px; }}
.m-nombre {{ font-size: 22px; font-weight: bold; color: #0f172a; letter-spacing: -0.3px; margin-bottom: 3px; line-height: 1.2; }}
.m-cargo-label {{ font-size: 11px; font-weight: bold; color: #1d4ed8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }}
.m-perfil {{ font-size: 11px; color: #475569; line-height: 1.7; margin-bottom: 8px; }}
.badge {{ display: inline-block; background-color: #eff6ff; color: #1d4ed8; font-size: 9px; font-weight: bold; padding: 3px 9px; border-radius: 10px; border: 1px solid #bfdbfe; margin-right: 4px; margin-bottom: 3px; }}
.section-label {{ font-size: 9px; font-weight: bold; color: #1d4ed8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 9px; margin-top: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; }}
.exp-card {{ border-left: 3px solid #1d4ed8; padding: 9px 11px; margin-bottom: 9px; background-color: #f8fafc; }}
.exp-table {{ width: 100%; border-collapse: collapse; }}
.exp-left {{ vertical-align: top; }}
.exp-right {{ vertical-align: top; text-align: right; white-space: nowrap; padding-left: 6px; }}
.exp-empresa {{ font-size: 12px; font-weight: bold; color: #0f172a; line-height: 1.4; }}
.exp-cargo {{ font-size: 11px; color: #1d4ed8; font-weight: bold; line-height: 1.4; }}
.exp-periodo {{ font-size: 10px; color: #94a3b8; }}
.exp-bullets {{ padding-left: 13px; margin-top: 5px; }}
.exp-bullets li {{ font-size: 10px; color: #475569; line-height: 1.6; margin-bottom: 2px; }}
.info-box {{ background-color: #f0f7ff; border: 1px solid #bfdbfe; padding: 9px 12px; font-size: 10px; color: #1e3a5f; line-height: 1.7; margin-bottom: 4px; }}
.footer-bar {{ background-color: #0f2137; margin-top: 14px; padding: 8px 20px; }}
.footer-table {{ width: 100%; border-collapse: collapse; }}
.footer-left {{ font-size: 9px; color: #94a3b8; vertical-align: middle; }}
.footer-bold {{ color: #e2e8f0; font-weight: bold; }}
.footer-right {{ font-size: 9px; color: #475569; text-align: right; vertical-align: middle; }}
</style></head><body>
<table class="layout-table"><tr>
  <td class="col-sidebar">
    <div class="logo-area">
      <div class="logo-icons"><span class="lc lc1"></span><span class="lc lc2"></span><span class="lc lc3"></span></div>
      <div class="logo-text">perfil<span class="logo-light">.work</span></div>
      <div class="logo-tagline">talento que impulsa resultados</div>
    </div>
    <div class="avatar-wrap"><div class="avatar-circle"><span class="avatar-text">{iniciales}</span></div></div>
    <div class="s-nombre">{nombre}</div>
    <div class="s-cargo">{cargo}</div>
    <div class="s-divider"></div>
    <div class="s-label">Contacto</div>
    {contacto_html}
    {skills_section}
    {formacion_section}
    {certs_section}
  </td>
  <td class="col-main">
    <div class="m-header">
      <div class="m-nombre">{nombre}</div>
      <div class="m-cargo-label">{cargo}</div>
      <div class="m-perfil">{data['perfil']}</div>
      <div>{badges_html}</div>
    </div>
    {exp_section}
    {info_html}
    <div class="footer-bar">
      <table class="footer-table"><tr>
        <td class="footer-left"><span class="footer-bold">perfil</span>.work · talento que impulsa resultados</td>
        <td class="footer-right">Generado por perfil.work</td>
      </tr></table>
    </div>
  </td>
</tr></table>
</body></html>"""


def generar_pdf(nombre, cargo, email, telefono, region, sueldo, nivel, area, data):
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
        data = mejorar_cv(texto_procesado, info_extra)
        pdf = generar_pdf(nombre, cargo, email, telefono, region, sueldo, nivel, area, data)

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
