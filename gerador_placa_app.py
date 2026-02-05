import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Web", layout="centered", page_icon="👮")

# --- CARREGAMENTO DE RECURSOS (CACHED) ---
@st.cache_resource
def load_resources():
    # Tenta carregar localmente. No GitHub, os arquivos devem estar na raiz.
    try:
        moldura = Image.open("moldura.png").convert("RGBA")
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        if face_cascade.empty():
            # Tenta ler arquivo local se o do sistema falhar
            face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
        return moldura, face_cascade
    except Exception as e:
        return None, None

MOLDURA_FULL, FACE_CASCADE = load_resources()

# Se der erro no carregamento
if MOLDURA_FULL is None:
    st.error("Erro crítico: 'moldura.png' não encontrado. Verifique os arquivos no GitHub.")
    st.stop()

# Constantes
POSICAO_FOTO = (113, 321)
TAM_FINAL = (1500, 1500)
FONTE_ARQUIVO = "arial.ttf"

# Configuração de Texto
CONFIG_TEXTOS = {
    "situacao": {"box": (135, 608, 80, 961), "cor": (0,0,0), "rotate": 90, "bold": False},
    "natureza": {"box": (328, 1569, 1000, 200), "cor": (255,0,0), "rotate": 0, "bold": True},
    "nome":     {"box": (82, 1853, 1500, 80), "cor": (0,0,0), "rotate": 0, "bold": True},
    "documento":{"box": (82, 1950, 1500, 50), "cor": (0,0,0), "rotate": 0, "bold": False},
    "outras":   {"box": (82, 2017, 1500, 50), "cor": (0,0,0), "rotate": 0, "bold": False}
}

# --- FUNÇÕES DE LÓGICA (Reaproveitadas) ---
def desenhar_texto(img, texto, chave):
    cfg = CONFIG_TEXTOS[chave]
    x, y, w, h = cfg['box']; cor = cfg['cor']; rot = cfg['rotate']; bold = cfg['bold']
    if not texto: return img
    
    # Fonte
    try: font = ImageFont.truetype(FONTE_ARQUIVO, 20)
    except: font = ImageFont.load_default()
    
    w_disp, h_disp = (h, w) if rot in [90, 270] else (w, h)
    tam = 300
    while tam > 10:
        try: font = ImageFont.truetype(FONTE_ARQUIVO, tam)
        except: break
        bb = font.getbbox(texto)
        if (bb[2]-bb[0]) <= w_disp and (bb[3]-bb[1]) <= h_disp: break
        tam -= 2
        
    if rot == 0:
        d = ImageDraw.Draw(img)
        d.text((x+w/2, y+h/2), texto, font=font, fill=cor, anchor="mm")
    else:
        lay = Image.new('RGBA', (w_disp, h_disp), (255,255,255,0))
        d = ImageDraw.Draw(lay)
        d.text((w_disp/2, h_disp/2), texto, font=font, fill=cor, anchor="mm")
        rot_img = lay.rotate(rot, expand=True)
        ox = x + (w - rot_img.width)//2; oy = y + (h - rot_img.height)//2
        img.paste(rot_img, (ox, oy), mask=rot_img)
    return img

def crop_viewport(img_pil, x1, y1, x2, y2):
    w_req, h_req = int(x2 - x1), int(y2 - y1)
    view = Image.new("RGB", (w_req, h_req), (255, 255, 255))
    img_w, img_h = img_pil.size
    src_x1, src_y1 = max(0, x1), max(0, y1)
    src_x2, src_y2 = min(img_w, x2), min(img_h, y2)
    if src_x2 > src_x1 and src_y2 > src_y1:
        recorte = img_pil.crop((int(src_x1), int(src_y1), int(src_x2), int(src_y2)))
        view.paste(recorte, (int(src_x1 - x1), int(src_y1 - y1)))
    return view.resize(TAM_FINAL, Image.LANCZOS)

def processar_auto(pil_img, modo):
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5)
    h_o, w_o = cv_img.shape[:2]
    
    cx, cy, lado = w_o//2, h_o//2, min(h_o, w_o) # Default
    
    if len(faces) > 0:
        (x, y, w, h) = max(faces, key=lambda f: f[2]*f[3])
        if modo == "face":
            lado = h * 2.5
            cy = y + h//2
            cx = x + w//2
        else:
            h_proj = h * 8.0
            lim = min(y + h_proj, h_o - (h*0.2))
            h_util = max(lim - y, h * 1.5)
            lado = h_util * 1.2
            cy = y + h_util/2
            cx = x + w//2
            
    return crop_viewport(pil_img, cx - lado/2, cy - lado/2, cx + lado/2, cy + lado/2)

# --- INTERFACE GRÁFICA WEB ---
st.title("Gerador de Placa - Polícia Civil")
st.write("Versão Web - Compatível com Mobile")

# Upload
uploaded_file = st.file_uploader("Selecione a Fotografia", type=['jpg', 'jpeg', 'png', 'webp'])

if uploaded_file:
    image = Image.open(uploaded_file).convert('RGB')
    
    # Dados
    with st.expander("📝 Dados do Indiciado", expanded=True):
        col1, col2 = st.columns(2)
        sit = col1.text_input("Situação", "INDICIADO")
        nat = col2.text_input("Natureza")
        nome = st.text_input("Nome Completo")
        rg = col1.text_input("Documento (RG/CPF)")
        outros = col2.text_input("Outros (BO/Data)")

    # Abas de Edição
    tab1, tab2, tab3 = st.tabs(["👤 Rosto (Auto)", "🧍 Corpo (Auto)", "🖐️ Manual"])
    
    img_final_crop = None

    with tab1:
        if st.button("Processar Rosto Automático"):
            img_final_crop = processar_auto(image, "face")
            st.image(img_final_crop, caption="Recorte Automático", width=300)

    with tab2:
        if st.button("Processar Corpo Automático"):
            img_final_crop = processar_auto(image, "corpo")
            st.image(img_final_crop, caption="Recorte Automático", width=300)

    with tab3:
        st.info("Ajuste os controles abaixo para enquadrar")
        zoom = st.slider("Zoom", 0.1, 4.0, 1.0, 0.05)
        # Sliders substituem o 'arrastar' do mouse
        off_x = st.slider("Mover Horizontal", -1000, 1000, 0, 10)
        off_y = st.slider("Mover Vertical", -1000, 1000, 0, 10)
        
        # Preview em tempo real (baixa resolução para ser rápido)
        # Lógica Manual Simplificada para Web
        w, h = image.size
        w_z, h_z = int(w * zoom), int(h * zoom)
        
        # Calcula centro
        cx = (w/2) - (off_x / zoom)
        cy = (h/2) - (off_y / zoom)
        
        # Define o tamanho do 'quadrado' que queremos pegar da imagem original
        # O buraco final é 1500px. Se zoom é 1.0, pegamos 1500px.
        # Se zoom é 0.5, pegamos 3000px.
        lado_req = 1500 / zoom
        
        x1, y1 = cx - lado_req/2, cy - lado_req/2
        x2, y2 = cx + lado_req/2, cy + lado_req/2
        
        img_preview_crop = crop_viewport(image, x1, y1, x2, y2)
        st.image(img_preview_crop, caption="Pré-visualização do Recorte", width=300)
        img_final_crop = img_preview_crop # Define este como o final se estiver nesta aba

    # --- BOTÃO DE GERAR FINAL ---
    st.divider()
    if img_final_crop is not None:
        # Montagem Final
        base = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
        base.paste(img_final_crop, POSICAO_FOTO)
        base.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
        
        # Textos
        txts = {"situacao": sit.upper(), "natureza": nat.upper(), "nome": nome.upper(), "documento": rg.upper(), "outras": outros.upper()}
        for k, v in txts.items():
            base = desenhar_texto(base, v, k)
            
        # Converter para Bytes para Download
        buf = io.BytesIO()
        base.save(buf, format="PNG")
        byte_im = buf.getvalue()
        
        nome_arquivo = f"Placa_{nome.split()[0] if nome else 'SEM_NOME'}.png"
        
        st.success("✅ Imagem Gerada com Sucesso!")
        st.download_button(
            label="⬇️ BAIXAR PLACA FINAL",
            data=byte_im,
            file_name=nome_arquivo,
            mime="image/png",
            use_container_width=True
        )