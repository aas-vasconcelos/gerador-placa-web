import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Web", layout="centered", page_icon="👮")

# --- CSS PARA ESTILIZAR O JOYSTICK ---
st.markdown("""
    <style>
    .stButton button {
        width: 100%;
        font-weight: bold;
        border-radius: 8px;
    }
    div[data-testid="column"] {
        text-align: center;
    }
    /* Deixa a imagem do preview com borda sutil */
    img {
        border: 1px solid #ddd;
        border-radius: 5px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- CARREGAMENTO DE RECURSOS ---
@st.cache_resource
def load_resources():
    # Tenta carregar a moldura
    try:
        moldura = Image.open("moldura.png").convert("RGBA")
    except:
        st.error("ERRO: 'moldura.png' não encontrada. Verifique o GitHub.")
        return None, None

    # Tenta carregar o Cascade (IA)
    try:
        path_cv = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(path_cv)
        if face_cascade.empty():
            face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    except:
        return moldura, None
        
    return moldura, face_cascade

MOLDURA_FULL, FACE_CASCADE = load_resources()

# Parâmetros Fixos
POSICAO_FOTO = (113, 321)
TAM_FINAL = (1500, 1500)
FONTE_ARQUIVO = "arial.ttf"

CONFIG_TEXTOS = {
    "situacao": {"box": (135, 608, 80, 961), "cor": (0,0,0), "rotate": 90, "bold": False},
    "natureza": {"box": (328, 1569, 1000, 200), "cor": (255,0,0), "rotate": 0, "bold": True},
    "nome":     {"box": (82, 1853, 1500, 80), "cor": (0,0,0), "rotate": 0, "bold": True},
    "documento":{"box": (82, 1950, 1500, 50), "cor": (0,0,0), "rotate": 0, "bold": False},
    "outras":   {"box": (82, 2017, 1500, 50), "cor": (0,0,0), "rotate": 0, "bold": False}
}

# --- GERENCIAMENTO DE ESTADO ---
if 'zoom' not in st.session_state: st.session_state.zoom = 1.0
if 'off_x' not in st.session_state: st.session_state.off_x = 0
if 'off_y' not in st.session_state: st.session_state.off_y = 0

def reset_state():
    st.session_state.zoom = 1.0
    st.session_state.off_x = 0
    st.session_state.off_y = 0

# --- LÓGICA DE FOCO E CORTE ---
def calcular_auto_foco(pil_img, modo):
    """Calcula zoom/offset para rosto ou corpo e atualiza o estado."""
    if FACE_CASCADE is None: return
    
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5)
    
    h_img, w_img = cv_img.shape[:2]
    cx, cy = w_img // 2, h_img // 2
    lado_ideal = min(h_img, w_img)
    
    if len(faces) > 0:
        (x, y, w, h) = max(faces, key=lambda f: f[2]*f[3])
        if modo == "face":
            lado_ideal = h * 2.5
            cx = x + w // 2
            cy = y + h // 2
        else: # Corpo
            h_proj = h * 8.0
            limite_inf = min(y + h_proj, h_img - (h * 0.2))
            h_util = max(limite_inf - y, h * 1.5)
            lado_ideal = h_util * 1.2
            cx = x + w // 2
            cy = y + h_util // 2
            
    # Atualiza Session State (interface reativa)
    st.session_state.zoom = 1500 / lado_ideal
    st.session_state.off_x = int((w_img / 2 - cx) * st.session_state.zoom)
    st.session_state.off_y = int((h_img / 2 - cy) * st.session_state.zoom)

def gerar_recorte_viewport(img_pil):
    zoom = st.session_state.zoom
    off_x = st.session_state.off_x
    off_y = st.session_state.off_y
    
    w, h = img_pil.size
    cx = (w / 2) - (off_x / zoom)
    cy = (h / 2) - (off_y / zoom)
    
    lado_req = 1500 / zoom
    x1 = int(cx - lado_req / 2)
    y1 = int(cy - lado_req / 2)
    x2 = int(cx + lado_req / 2)
    y2 = int(cy + lado_req / 2)
    
    w_req, h_req = x2 - x1, y2 - y1
    view = Image.new("RGB", (w_req, h_req), (255, 255, 255))
    
    src_x1, src_y1 = max(0, x1), max(0, y1)
    src_x2, src_y2 = min(w, x2), min(h, y2)
    
    if src_x2 > src_x1 and src_y2 > src_y1:
        recorte = img_pil.crop((src_x1, src_y1, src_x2, src_y2))
        view.paste(recorte, (src_x1 - x1, src_y1 - y1))
        
    return view.resize(TAM_FINAL, Image.LANCZOS)

def desenhar_texto(img, texto, chave):
    if not texto: return img
    cfg = CONFIG_TEXTOS[chave]
    x, y, w, h = cfg['box']; cor = cfg['cor']; rot = cfg['rotate']; bold = cfg['bold']
    
    # Seleção de Fonte
    try: font = ImageFont.truetype(FONTE_ARQUIVO, 20)
    except: font = ImageFont.load_default()
    
    w_disp, h_disp = (h, w) if rot in [90, 270] else (w, h)
    
    # Auto-fit do tamanho
    tam = 300
    while tam > 10:
        try: current_font = ImageFont.truetype(FONTE_ARQUIVO, tam)
        except: current_font = ImageFont.load_default(); break
        
        bbox = current_font.getbbox(texto)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= w_disp and th <= h_disp:
            font = current_font
            break
        tam -= 2
        
    if rot == 0:
        d = ImageDraw.Draw(img)
        d.text((x+w/2, y+h/2), texto, font=font, fill=cor, anchor="mm")
    else:
        lay = Image.new('RGBA', (w_disp, h_disp), (255,255,255,0))
        d = ImageDraw.Draw(lay)
        # CORREÇÃO CRÍTICA AQUI (h_disp no lugar de h_d)
        d.text((w_disp/2, h_disp/2), texto, font=font, fill=cor, anchor="mm")
        rot_img = lay.rotate(rot, expand=True)
        ox = x + (w - rot_img.width)//2; oy = y + (h - rot_img.height)//2
        img.paste(rot_img, (ox, oy), mask=rot_img)
    return img

# --- INTERFACE PRINCIPAL ---

st.title("Gerador de Placa - SIV-PC")

# 1. Upload
uploaded_file = st.file_uploader("📂 Carregar Fotografia", type=['jpg', 'jpeg', 'png', 'webp'])

if uploaded_file:
    # Carrega imagem
    image = Image.open(uploaded_file).convert('RGB')
    
    # 2. Layout de Colunas (Dados à esquerda, Controles à direita no PC)
    # No mobile o Streamlit empilha automaticamente
    
    with st.expander("📝 1. Preenchimento dos Dados", expanded=True):
        col_a, col_b = st.columns(2)
        sit = col_a.text_input("Situação", "INDICIADO")
        nat = col_b.text_input("Natureza")
        nome = st.text_input("Nome Completo")
        rg = col_a.text_input("Documento (RG/CPF)")
        outros = col_b.text_input("Outros (BO/Data)")

    st.divider()
    
    # 3. Controles de Ajuste
    st.subheader("🖼️ 2. Enquadramento e Preview")
    
    # Botões Auto
    c_auto1, c_auto2 = st.columns(2)
    if c_auto1.button("🧠 FOCAR ROSTO", use_container_width=True):
        calcular_auto_foco(image, "face")
    if c_auto2.button("🧠 FOCAR CORPO", use_container_width=True):
        calcular_auto_foco(image, "corpo")

    # Joystick
    col1, col2, col3 = st.columns([1, 2, 1])
    step_move = 50 
    step_zoom = 0.1

    with col2:
        if st.button("⬆️", key="up", use_container_width=True):
            st.session_state.off_y += step_move
            
    col_mid1, col_mid2, col_mid3 = st.columns([1, 2, 1])
    with col_mid1:
        if st.button("⬅️", key="left", use_container_width=True):
            st.session_state.off_x += step_move
    with col_mid3:
        if st.button("➡️", key="right", use_container_width=True):
            st.session_state.off_x -= step_move
            
    with col_mid2:
        cz1, cz2 = st.columns(2)
        if cz1.button("➕", use_container_width=True):
            st.session_state.zoom += step_zoom
        if cz2.button("➖", use_container_width=True):
            if st.session_state.zoom > 0.1: st.session_state.zoom -= step_zoom
            
    col_bot1, col_bot2, col_bot3 = st.columns([1, 2, 1])
    with col_bot2:
        if st.button("⬇️", key="down", use_container_width=True):
            st.session_state.off_y -= step_move

    # --- GERAÇÃO REATIVA DA IMAGEM ---
    # O código abaixo roda a cada interação, atualizando o preview instantaneamente
    
    # 1. Recorta a foto baseada no Joystick
    img_crop = gerar_recorte_viewport(image)
    
    # 2. Cola na Moldura
    base_preview = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
    base_preview.paste(img_crop, POSICAO_FOTO)
    base_preview.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
    
    # 3. Escreve os Textos (Usa o que está digitado no momento)
    txts = {"situacao": sit.upper(), "natureza": nat.upper(), "nome": nome.upper(), "documento": rg.upper(), "outras": outros.upper()}
    for k, v in txts.items():
        base_preview = desenhar_texto(base_preview, v, k)
    
    # 4. Exibe o Preview
    st.image(base_preview, caption="Resultado Final (Tempo Real)", use_container_width=True)
    
    # 5. Botão de Download (Já com a imagem pronta)
    buf = io.BytesIO()
    base_preview.save(buf, format="PNG")
    byte_im = buf.getvalue()
    
    nome_arq = f"Placa_{nome.split()[0] if nome else 'INDICIADO'}.png"
    
    st.download_button(
        label="💾 BAIXAR IMAGEM PRONTA",
        data=byte_im,
        file_name=nome_arq,
        mime="image/png",
        use_container_width=True,
        type="primary" # Deixa o botão destacado
    )

else:
    reset_state()
    st.info("👆 Faça o upload da imagem para começar.")
