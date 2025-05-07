import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import base64
import re
import pytesseract

# ---------------------------
# Extração de texto (PDF ou imagem)
# ---------------------------
def extrair_texto(arquivo):
    texto = ""
    if arquivo.type == "application/pdf":
        pdf_bytes = arquivo.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            texto += page.get_text()
    elif "image" in arquivo.type:
        imagem = Image.open(arquivo)
        texto += pytesseract.image_to_string(imagem, lang='por')
    return texto

# ---------------------------
# Regras SIAPE Padrão
# ---------------------------
def analise_siape_padrao(idade, texto_ocr):
    erros = []
    if idade < 18 or idade > 90:
        erros.append("Idade fora do intervalo permitido.")
    if re.search(r"CLT|comissionado", texto_ocr, re.IGNORECASE):
        erros.append("Vínculo CLT ou comissionado não aceito no SIAPE.")
    if re.search(r"UPAG.*PB|Paraíba", texto_ocr):
        erros.append("Cliente vinculado à UPAG bloqueada (PB).")
    pensao_temp = re.search(r"término.*(\d{2}/\d{2}/\d{4})", texto_ocr, re.IGNORECASE)
    instituidor = re.search(r"instituidor.*pai", texto_ocr, re.IGNORECASE)
    if pensao_temp and instituidor and idade < 25:
        erros.append("Pensionista temporário com término futuro, idade inferior a 25.")
    if erros:
        return False, "; ".join(erros)
    return True, "Cliente enquadrado no convênio SIAPE."

# ---------------------------
# Regras por Banco
# ---------------------------
def analisar_produtos_banco(banco, idade, margem):
    produtos = {
        "Facta": {"emprestimo_novo": 22 <= idade <= 76 and margem >= 1,
                  "cartao_beneficio": 22 <= idade <= 76 and margem >= 1,
                  "portabilidade": 22 <= idade <= 76,
                  "portabilidade_refin": 22 <= idade <= 76},
        "Banrisul": {"emprestimo_novo": idade <= 80,
                     "cartao_beneficio": idade <= 80 and margem >= 1,
                     "portabilidade": idade <= 80,
                     "portabilidade_refin": idade <= 80},
        "C6 Bank": {"emprestimo_novo": 21 <= idade <= 77,
                    "cartao_beneficio": 21 <= idade <= 77 and margem >= 1,
                    "portabilidade": 21 <= idade <= 77,
                    "portabilidade_refin": 21 <= idade <= 77},
        "Bradesco": {"emprestimo_novo": idade <= 78,
                     "cartao_beneficio": idade <= 78,
                     "portabilidade": idade <= 78,
                     "portabilidade_refin": idade <= 75},
        "Digio": {"emprestimo_novo": idade <= 79,
                  "cartao_beneficio": idade <= 79,
                  "portabilidade": idade <= 79,
                  "portabilidade_refin": idade <= 75},
        "Daycoval": {"emprestimo_novo": idade <= 77,
                     "cartao_beneficio": idade <= 77,
                     "portabilidade": idade <= 77,
                     "portabilidade_refin": idade <= 77},
        "Daycoval CLT": {"emprestimo_novo": idade <= 75,
                         "cartao_beneficio": False,
                         "portabilidade": idade <= 75,
                         "portabilidade_refin": idade <= 73},
        "Daycoval Melhor Idade": {"emprestimo_novo": 73 <= idade <= 84,
                                  "cartao_beneficio": False,
                                  "portabilidade": 73 <= idade <= 84,
                                  "portabilidade_refin": 73 <= idade <= 84},
        "Pan": {"emprestimo_novo": idade <= 77,
                "cartao_beneficio": idade <= 77,
                "portabilidade": idade <= 77,
                "portabilidade_refin": idade <= 77},
        "Safra": {"emprestimo_novo": idade <= 77,
                  "cartao_beneficio": idade <= 77,
                  "portabilidade": idade <= 77,
                  "portabilidade_refin": idade <= 77},
        "Olé": {"emprestimo_novo": idade <= 78,
                "cartao_beneficio": idade <= 78,
                "portabilidade": idade <= 78,
                "portabilidade_refin": idade <= 75},
    }
    return produtos.get(banco, {})

# ---------------------------
# Extração de margem e contratos (ajustada)
# ---------------------------
def extrair_margem_e_contratos(texto):
    margem = 0.0
    margem_match = re.search(r"(margem\s*(?:dispon[ií]vel|líquida)?:?)\s*R\$\s*(\d+[.,]?\d{0,2})", texto, re.IGNORECASE)
    if margem_match:
        margem = float(margem_match.group(2).replace(",", "."))
    
    contratos = []
    linhas = texto.splitlines()
    for linha in linhas:
        match = re.search(r"(\d{6,})[^\n]*?(R\$\s*\d+[.,]\d{2})", linha)
        if match:
            numero = match.group(1)
            valor = float(match.group(2).replace("R$", "").replace(",", "."))
            contratos.append((numero, valor))
    return margem, contratos

# ---------------------------
# Interface
# ---------------------------
def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = get_base64_image("adapt.jpg")

st.set_page_config(page_title="Análise SIAPE - Adapt", layout="centered")
st.markdown(f"""
    <div style='text-align: center;'>
        <img src='data:image/jpeg;base64,{logo_base64}' width='300'/>
        <h1 style='color:white;'>Análise de Crédito – Convênio SIAPE</h1>
    </div>
""", unsafe_allow_html=True)

st.markdown("Envie até dois documentos e veja a elegibilidade.")

arquivos = st.file_uploader("Upload de documentos", type=["pdf", "jpg", "png", "jpeg"], accept_multiple_files=True)
texto_geral = ""
margem_total = 0.0
contratos_extraidos = []

if arquivos:
    for arquivo in arquivos:
        texto = extrair_texto(arquivo)
        texto_geral += texto + "\n"
        margem, contratos = extrair_margem_e_contratos(texto)
        margem_total = max(margem_total, margem)
        contratos_extraidos.extend(contratos)
        st.markdown(f"**Texto extraído de {arquivo.name}:**")
        st.text_area("", texto, height=150)

st.markdown("---")
with st.form("form_cliente"):
    nome = st.text_input("Nome do Cliente")
    idade = st.number_input("Idade do Cliente", min_value=18, max_value=90)
    enviar = st.form_submit_button("Analisar")

if enviar:
    siape_valido, msg = analise_siape_padrao(idade, texto_geral)
    st.subheader(f"Resultado da Análise para {nome.upper()}:")
    if not siape_valido:
        st.error(f"Reprovado: {msg}")
    else:
        st.success(f"Aprovado: {msg}")
        bancos = ["Facta", "Banrisul", "C6 Bank", "Bradesco", "Digio", "Daycoval", "Daycoval CLT", "Daycoval Melhor Idade", "Pan", "Safra", "Olé"]
        colunas = ["emprestimo_novo", "cartao_beneficio", "portabilidade", "portabilidade_refin"]

        for banco in bancos:
            resultado = analisar_produtos_banco(banco, idade, margem_total)
            st.markdown(f"### \U0001F3E6 {banco}")
            for coluna in colunas:
                label = coluna.replace("_", " ").capitalize()
                aprovado = resultado.get(coluna)
                if aprovado and "portabilidade" in coluna and contratos_extraidos:
                    numero, valor = contratos_extraidos[0]
                    st.write(f"*{label}:* ✅ Sim (Contrato: {numero}, Parcela: R$ {valor:.2f})")
                else:
                    st.write(f"*{label}:* {'✅ Sim' if aprovado else '❌ Não'}")

st.markdown("<br><hr><p style='text-align: center; color: gray;'>Agilidade e segurança</p>", unsafe_allow_html=True)
