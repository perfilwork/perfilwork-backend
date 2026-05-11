import os
import json
import re
from io import BytesIO

from flask import Flask, request, Response
from flask_cors import CORS
from openai import OpenAI
from supabase import create_client
from weasyprint import HTML as WeasyprintHTML

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
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


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
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
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
    lineas = [re.sub(r"\s+", " ", l.strip()) for l in texto.split("\n") if l.strip()]
    return "\n".join(lineas)[:12000]


# =========================
# EXTRAER JSON
# =========================

def extraer_json(texto):
    try:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print("ERROR EXTRAER JSON:", e)
    return None


# =========================
# IA — prompt mejorado para estructura
# =========================

def mejorar_cv(texto_cv, info_extra):

    prompt = f"""
Eres especialista en reclutamiento técnico industrial en Chile y Latinoamérica.

Transforma este CV en una versión profesional, clara y recruiter-friendly para sectores como minería, construcción industrial, mantenimiento, electricidad, mecánica y operaciones.

REGLAS IMPORTANTES:
- NO inventes información que no esté en el CV original o en la información adicional.
- Sé conciso y directo. Evita frases vacías o genéricas.
- Las experiencias laborales deben estar estructuradas con empresa, cargo, período y funciones SEPARADOS.
- Las funciones deben ser bullets cortos, concretos y orientados a logros cuando sea posible.

Devuelve SOLO JSON válido con esta estructura exacta:

{{
  "perfil": "Párrafo corto de 2-3 líneas resumiendo el perfil técnico del candidato.",
  "experiencia": [
    {{
      "empresa": "Nombre de la empresa",
      "cargo": "Cargo desempeñado",
      "periodo": "Año inicio – Año término (ej: 2018 – 2023)",
      "funciones": [
        "Función o logro concreto 1",
        "Función o logro concreto 2",
        "Función o logro concreto 3"
      ]
    }}
  ],
  "formacion": [
    {{
      "titulo": "Nombre del título o carrera",
      "institucion": "Nombre de la institución",
      "anio": "Año de egreso o período"
    }}
  ],
  "competencias": ["Habilidad técnica 1", "Habilidad técnica 2"],
  "certificaciones": ["Certificación 1", "Certificación 2"],
  "info_relevante": "Información adicional relevante: disponibilidad, licencias, turno, etc."
}}

CV del candidato:
{texto_cv}

Información adicional entregada por el candidato:
{info_extra}
"""

    try:
        respuesta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Responde SOLO con JSON válido. Sin texto adicional, sin markdown, sin explicaciones."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1800
        )

        contenido = respuesta.choices[0].message.content.strip()
        contenido = contenido.replace("```json", "").replace("```", "")
        data = extraer_json(contenido)

        if not data:
            raise Exception("JSON inválido")

    except Exception as e:
        print("ERROR OPENAI / JSON:", e)
        data = {
            "perfil": info_extra,
            "experiencia": [],
            "formacion": [],
            "competencias": [],
            "certificaciones": [],
            "info_relevante": info_extra
        }

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
            experiencias_ok.append({
                "empresa": exp,
                "cargo": "",
                "periodo": "",
                "funciones": []
            })
    data["experiencia"] = experiencias_ok

    # Normalizar formación
    formacion_ok = []
    for item in data.get("formacion", []):
        if isinstance(item, dict):
            formacion_ok.append({
                "titulo": str(item.get("titulo", "")),
                "institucion": str(item.get("institucion", "")),
                "anio": str(item.get("anio", ""))
            })
        elif isinstance(item, str):
            formacion_ok.append({"titulo": item, "institucion": "", "anio": ""})
    data["formacion"] = formacion_ok

    # Normalizar listas simples
    data["competencias"] = [str(c) for c in data.get("competencias", [])] if isinstance(data.get("competencias"), list) else []
    data["certificaciones"] = [str(c) for c in data.get("certificaciones", [])] if isinstance(data.get("certificaciones"), list) else []
    data["perfil"] = str(data.get("perfil", ""))
    data["info_relevante"] = str(data.get("info_relevante", ""))

    return data


# =========================
# INICIALES PARA AVATAR
# =========================

def obtener_iniciales(nombre):
    partes = nombre.strip().split()
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    elif len(partes) == 1:
        return partes[0][:2].upper()
    return "PW"


# =========================
# GENERAR HTML DEL CV
# =========================

def generar_html(nombre, cargo, email, telefono, region, sueldo, nivel, area, data):

    iniciales = obtener_iniciales(nombre)

    # Sidebar: experiencia en badges
    badges_html = ""
    if sueldo:
        badges_html += f'<span class="badge">$ {sueldo}</span>'
    if nivel:
        badges_html += f'<span class="badge">{nivel}</span>'
    if area:
        badges_html += f'<span class="badge">{area}</span>'

    # Bloques de experiencia
    exp_html = ""
    for exp in data["experiencia"][:6]:
        funciones_html = "".join([f"<li>{f}</li>" for f in exp["funciones"][:4]])
        exp_html += f"""
        <div class="exp-card">
            <div class="exp-header">
                <div>
                    <div class="exp-empresa">{exp['empresa']}</div>
                    <div class="exp-cargo">{exp['cargo']}</div>
                </div>
                <div class="exp-periodo">{exp['periodo']}</div>
            </div>
            {'<ul class="exp-bullets">' + funciones_html + '</ul>' if funciones_html else ''}
        </div>
        """

    # Formación sidebar
    formacion_html = ""
    for f in data["formacion"][:4]:
        formacion_html += f"""
        <div class="s-edu">
            <div class="s-edu-titulo">{f['titulo']}</div>
            <div class="s-edu-inst">{f['institucion']} {('· ' + f['anio']) if f['anio'] else ''}</div>
        </div>
        """

    # Skills sidebar
    skills_html = "".join([f'<span class="skill-pill">{c}</span>' for c in data["competencias"][:10]])

    # Certificaciones sidebar
    certs_html = "".join([f'<div class="s-cert"><div class="cert-dot"></div><span>{c}</span></div>' for c in data["certificaciones"][:5]])

    # Info relevante
    info_html = ""
    if data["info_relevante"]:
        info_html = f"""
        <div class="section-label">Información adicional</div>
        <div class="info-box">{data['info_relevante']}</div>
        """

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @page {{
    size: A4;
    margin: 0;
  }}

  * {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }}

  body {{
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10px;
    color: #334155;
    background: #fff;
  }}

  .page {{
    width: 210mm;
    min-height: 297mm;
    display: flex;
    flex-direction: row;
  }}

  /* ===== SIDEBAR ===== */
  .sidebar {{
    width: 68mm;
    min-height: 297mm;
    background: #0f2137;
    padding: 20px 15px;
    display: flex;
    flex-direction: column;
    gap: 0;
  }}

  .logo-area {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-bottom: 14px;
    border-bottom: 0.5px solid #1e3a5f;
    margin-bottom: 14px;
  }}

  .logo-row {{
    display: flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 4px;
  }}

  .logo-circles {{
    position: relative;
    width: 26px;
    height: 26px;
    flex-shrink: 0;
  }}

  .lc1 {{
    position: absolute;
    width: 19px;
    height: 19px;
    border-radius: 50%;
    background: #e05a4e;
    top: 0;
    left: 0;
  }}

  .lc2 {{
    position: absolute;
    width: 15px;
    height: 15px;
    border-radius: 50%;
    background: #4a90d9;
    top: 5px;
    left: 7px;
    opacity: 0.9;
  }}

  .lc3 {{
    position: absolute;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #2ec4a5;
    top: 10px;
    left: 3px;
    opacity: 0.92;
  }}

  .logo-text {{
    font-size: 14px;
    color: #e2e8f0;
    letter-spacing: -0.2px;
  }}

  .logo-text b {{
    color: #f1f5f9;
    font-weight: 700;
  }}

  .logo-text span {{
    color: #94a3b8;
    font-weight: 300;
  }}

  .logo-tagline {{
    font-size: 7px;
    color: #475569;
    letter-spacing: 0.8px;
    text-align: center;
  }}

  .avatar {{
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #1d4ed8;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    margin: 0 auto 10px;
    letter-spacing: 1px;
  }}

  .s-nombre {{
    font-size: 11.5px;
    font-weight: 700;
    color: #f1f5f9;
    text-align: center;
    margin-bottom: 3px;
    line-height: 1.3;
  }}

  .s-cargo {{
    font-size: 8.5px;
    color: #60a5fa;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 14px;
    line-height: 1.3;
  }}

  .s-divider {{
    height: 0.5px;
    background: #1e3a5f;
    margin: 10px 0;
  }}

  .s-label {{
    font-size: 7.5px;
    color: #60a5fa;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 700;
    margin-bottom: 7px;
  }}

  .contact-row {{
    display: flex;
    align-items: flex-start;
    gap: 6px;
    margin-bottom: 5px;
  }}

  .contact-icon {{
    color: #3b82f6;
    font-size: 9px;
    margin-top: 1px;
    flex-shrink: 0;
  }}

  .contact-text {{
    font-size: 8.5px;
    color: #94a3b8;
    line-height: 1.4;
    word-break: break-all;
  }}

  .skills-wrap {{
    margin-bottom: 2px;
  }}

  .skill-pill {{
    display: inline-block;
    background: #1e3a5f;
    color: #93c5fd;
    font-size: 7.5px;
    padding: 2px 7px;
    border-radius: 20px;
    margin: 2px 2px 0 0;
    line-height: 1.5;
  }}

  .s-edu {{
    margin-bottom: 7px;
  }}

  .s-edu-titulo {{
    font-size: 8.5px;
    color: #cbd5e1;
    font-weight: 600;
    line-height: 1.35;
  }}

  .s-edu-inst {{
    font-size: 7.5px;
    color: #64748b;
    line-height: 1.35;
  }}

  .s-cert {{
    display: flex;
    align-items: flex-start;
    gap: 5px;
    margin-bottom: 5px;
  }}

  .cert-dot {{
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #1d4ed8;
    margin-top: 3px;
    flex-shrink: 0;
  }}

  .s-cert span {{
    font-size: 8px;
    color: #94a3b8;
    line-height: 1.45;
  }}

  /* ===== MAIN ===== */
  .main {{
    flex: 1;
    padding: 22px 20px 0;
    display: flex;
    flex-direction: column;
  }}

  .m-header {{
    padding-bottom: 12px;
    border-bottom: 2px solid #1d4ed8;
    margin-bottom: 14px;
  }}

  .m-nombre {{
    font-size: 20px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.3px;
    margin-bottom: 2px;
    line-height: 1.2;
  }}

  .m-cargo {{
    font-size: 9.5px;
    font-weight: 700;
    color: #1d4ed8;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 7px;
  }}

  .m-perfil {{
    font-size: 9px;
    color: #475569;
    line-height: 1.6;
    margin-bottom: 8px;
  }}

  .badges {{
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }}

  .badge {{
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 7.5px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 20px;
    border: 0.5px solid #bfdbfe;
  }}

  .section-label {{
    font-size: 7.5px;
    font-weight: 700;
    color: #1d4ed8;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 8px;
    margin-top: 14px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  .section-label::after {{
    content: '';
    flex: 1;
    height: 0.5px;
    background: #e2e8f0;
    display: block;
  }}

  .exp-card {{
    border-left: 2.5px solid #1d4ed8;
    padding: 8px 10px;
    margin-bottom: 8px;
    background: #f8fafc;
    border-radius: 0 3px 3px 0;
  }}

  .exp-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 3px;
  }}

  .exp-empresa {{
    font-size: 9.5px;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.3;
  }}

  .exp-cargo {{
    font-size: 8.5px;
    color: #1d4ed8;
    font-weight: 600;
    line-height: 1.3;
  }}

  .exp-periodo {{
    font-size: 8px;
    color: #94a3b8;
    white-space: nowrap;
    flex-shrink: 0;
    margin-left: 8px;
    margin-top: 1px;
  }}

  .exp-bullets {{
    padding-left: 0;
    list-style: none;
    margin-top: 5px;
  }}

  .exp-bullets li {{
    font-size: 8.5px;
    color: #475569;
    line-height: 1.5;
    padding-left: 10px;
    position: relative;
    margin-bottom: 2px;
  }}

  .exp-bullets li::before {{
    content: '▸';
    position: absolute;
    left: 0;
    color: #3b82f6;
    font-size: 7px;
    top: 2px;
  }}

  .info-box {{
    background: #f0f7ff;
    border: 0.5px solid #bfdbfe;
    border-radius: 3px;
    padding: 8px 10px;
    font-size: 8.5px;
    color: #1e3a5f;
    line-height: 1.6;
    margin-bottom: 4px;
  }}

  /* ===== FOOTER ===== */
  .footer {{
    background: #0f2137;
    margin: 14px -20px 0;
    padding: 7px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .footer-logo {{
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  .footer-circles {{
    position: relative;
    width: 15px;
    height: 15px;
    flex-shrink: 0;
  }}

  .fc1 {{
    position: absolute;
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: #e05a4e;
    top: 0;
    left: 0;
  }}

  .fc2 {{
    position: absolute;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #4a90d9;
    top: 3px;
    left: 4px;
    opacity: 0.9;
  }}

  .fc3 {{
    position: absolute;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #2ec4a5;
    top: 5px;
    left: 2px;
    opacity: 0.92;
  }}

  .footer-brand {{
    font-size: 8px;
    color: #94a3b8;
  }}

  .footer-brand b {{
    color: #e2e8f0;
    font-weight: 700;
  }}

  .footer-generated {{
    font-size: 7.5px;
    color: #475569;
    letter-spacing: 0.3px;
  }}
</style>
</head>
<body>
<div class="page">

  <!-- SIDEBAR -->
  <div class="sidebar">

    <div class="logo-area">
      <div class="logo-row">
        <div class="logo-circles">
          <div class="lc1"></div>
          <div class="lc2"></div>
          <div class="lc3"></div>
        </div>
        <div class="logo-text"><b>perfil</b><span>.work</span></div>
      </div>
      <div class="logo-tagline">talento que impulsa resultados</div>
    </div>

    <div class="avatar">{iniciales}</div>
    <div class="s-nombre">{nombre}</div>
    <div class="s-cargo">{cargo}</div>

    <div class="s-divider"></div>
    <div class="s-label">Contacto</div>

    {'<div class="contact-row"><div class="contact-icon">✉</div><div class="contact-text">' + email + '</div></div>' if email else ''}
    {'<div class="contact-row"><div class="contact-icon">☏</div><div class="contact-text">' + telefono + '</div></div>' if telefono else ''}
    {'<div class="contact-row"><div class="contact-icon">⌖</div><div class="contact-text">' + region + '</div></div>' if region else ''}

    {'<div class="s-divider"></div><div class="s-label">Habilidades técnicas</div><div class="skills-wrap">' + skills_html + '</div>' if skills_html else ''}

    {'<div class="s-divider"></div><div class="s-label">Formación</div>' + formacion_html if formacion_html else ''}

    {'<div class="s-divider"></div><div class="s-label">Certificaciones</div>' + certs_html if certs_html else ''}

  </div>

  <!-- MAIN -->
  <div class="main">

    <div class="m-header">
      <div class="m-nombre">{nombre}</div>
      <div class="m-cargo">{cargo}</div>
      <div class="m-perfil">{data['perfil']}</div>
      <div class="badges">{badges_html}</div>
    </div>

    {'<div class="section-label">Experiencia laboral</div>' + exp_html if exp_html else ''}

    {info_html}

    <div class="footer">
      <div class="footer-logo">
        <div class="footer-circles">
          <div class="fc1"></div>
          <div class="fc2"></div>
          <div class="fc3"></div>
        </div>
        <span class="footer-brand"><b>perfil</b>.work · talento que impulsa resultados</span>
      </div>
      <span class="footer-generated">Generado por perfil.work</span>
    </div>

  </div>

</div>
</body>
</html>
"""
    return html


# =========================
# GENERAR PDF con WeasyPrint
# =========================

def generar_pdf(nombre, cargo, email, telefono, region, sueldo, nivel, area, data):
    html = generar_html(nombre, cargo, email, telefono, region, sueldo, nivel, area, data)
    pdf_bytes = WeasyprintHTML(string=html).write_pdf()
    buffer = BytesIO(pdf_bytes)
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
        file       = request.files.get("cv")
        info_extra = request.form.get("info_extra", "")
        nombre     = request.form.get("nombre", "Nombre")
        cargo      = request.form.get("cargo", "Cargo")
        email      = request.form.get("email", "")
        telefono   = request.form.get("telefono", "")
        region     = request.form.get("region", "")
        area       = request.form.get("area", "")
        experiencia = request.form.get("experiencia", "")
        nivel      = request.form.get("nivel", "")
        sueldo     = request.form.get("sueldo", "")

        # Guardar en Supabase
        try:
            supabase.table("candidatos").insert({
                "nombre":     nombre,
                "email":      email,
                "telefono":   telefono,
                "region":     region,
                "cargo":      cargo,
                "area":       area,
                "experiencia": experiencia,
                "nivel":      nivel,
                "sueldo":     sueldo,
                "info_extra": info_extra,
                "cv_url":     ""
            }).execute()
            print("✅ Candidato guardado en Supabase")
        except Exception as e:
            print("ERROR SUPABASE:", e)

        # Procesar CV
        texto = extraer_texto(file)
        texto_procesado = preprocesar_cv(texto)

        # Mejorar con IA
        data = mejorar_cv(texto_procesado, info_extra)

        # Generar PDF
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
