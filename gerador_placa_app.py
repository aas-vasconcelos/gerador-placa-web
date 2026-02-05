import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Web", layout="centered", page_icon="👮")

# --- CSS (Design Compacto e Centralizado) ---
st.markdown("""
    <style>
    /* Reduz margens do topo */
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Botões de Direção (Setas) */
    .stButton button {
        font-weight: bold;
        font-size: 24px; /* Setas maiores */
        padding: 0px;
        line-height: 1;
        height: 50px;
        border-radius: 8px;
    }
    
    /* Botões de Texto (Foco/Download) - Fonte menor normal */
    div[data-testid="stVerticalBlock"] > div > div > div > div > .stButton button p {
        font-size: 16px;
    }

    /* Centralizar tudo nas colunas */
    div[data-testid="column"] {
        display: flex;
        align-items: center;
        justify_content: center;
        text-align: center;
    }
    
    /* Borda suave no Preview */
    img {
        border: 2px solid #e0e0e0;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- RECURSOS ---
@st.cache_resource
def load_resources():
    try:
        moldura = Image.open("moldura.png").convert("RGBA")
    except:
        st.error("ERRO: 'moldura.png' não encontrada.")
        return None, None
    try:
        path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face = cv2.CascadeClassifier(path)
        if face.empty(): face = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    except:
        return moldura, None
    return moldura, face

MOLDURA_FULL, FACE_CASCADE = load_resources()

# Parâmetros
POSICAO_FOTO_FULL = (113, 321)
TAM_FINAL_FULL = (1500, 1500)
FONTE_ARQUIVO = "arial.ttf"

CONFIG_TEXTOS = {
    "situacao": {"box": (135, 608, 80, 961), "cor": (0,0,0), "rotate": 90, "bold": False},
    "natureza": {"box": (328, 1569, 1000, 200), "cor": (255,0,0), "rotate": 0, "bold": True},
    "nome":     {"box": (82, 1853, 1500, 80), "cor": (0,0,0), "rotate": 0, "bold": True},
    "documento":{"box": (82, 1950, 1500, 50), "cor": (0,0,0), "rotate": 0, "bold": False},
    "outras":   {"box": (82, 2017, 1500, 50), "cor": (0,0,0), "rotate": 0, "bold": False}
}

# --- ESTADO ---
if 'zoom' not in st.session_state: st.session_state.zoom = 1.0
if 'off_x' not in st.session_state: st.session_state.off_x = 0
if 'off_y' not in st.session_state: st.session_state.off_y = 0

def reset_state():
    st.session_state.zoom = 1.0
    st.session_state.off_x = 0
    st.session_state.off_y = 0

# --- LÓGICA RÁPIDA (PROXY) ---
def get_preview_scale(img_pil):
    # Preview fixo em 300px para caber no meio dos botões sem rolar tela
    return 300 / max(img_pil.size)

def desenhar_texto(img, texto, chave, escala=1.0):
    if not texto: return img
    cfg = CONFIG_TEXTOS[chave]
    x, y, w, h = [int(v * escala) for v in cfg['box']]
    rot = cfg['rotate']
    
    try: font_n = FONTE_ARQUIVO
    except: font_n = "arial.ttf"
    
    w_disp, h_disp = (h, w) if rot in [90, 270] else (w, h)
    tam = int(300 * escala)
    
    font = ImageFont.load_default()
    while tam > 8:
        try: font = ImageFont.truetype(font_n, tam)
        except: break
        bbox = font.getbbox(texto)
        if (bbox[2]-bbox[0]) <= w_disp and (bbox[3]-bbox[1]) <= h_disp: break
        tam -= int(2 * escala) if escala > 1 else 1

    draw = ImageDraw.Draw(img)
    cor = cfg['cor']
    
    if rot == 0:
        draw.text((x+w/2, y+h/2), texto, font=font, fill=cor, anchor="mm")
    else:
        lay = Image.new('RGBA', (w_disp, h_disp), (255,255,255,0))
        d = ImageDraw.Draw(lay)
        d.text((w_disp/2, h_disp/2), texto, font=font, fill=cor, anchor="mm")
        rot_img = lay.rotate(rot, expand=True)
        ox = x + (w - rot_img.width)//2
        oy = y + (h - rot_img.height)//2
        img.paste(rot_img, (ox, oy), mask=rot_img)
    return img

def gerar_recorte(img_pil, moldura_size, pos_foto, tam_foto):
    zoom = st.session_state.zoom
    off_x = st.session_state.off_x / zoom
    off_y = st.session_state.off_y / zoom
    
    w_img, h_img = img_pil.size
    cx, cy = (w_img / 2) - off_x, (h_img / 2) - off_y
    lado_req = tam_foto[0] / zoom
    
    x1, y1 = int(cx - lado_req/2), int(cy - lado_req/2)
    x2, y2 = int(cx + lado_req/2), int(cy + lado_req/2)
    
    view = Image.new("RGB", (int(x2-x1), int(y2-y1)), (255,255,255))
    src_x1, src_y1 = max(0, x1), max(0, y1)
    src_x2, src_y2 = min(w_img, x2), min(h_img, y2)
    
    if src_x2 > src_x1 and src_y2 > src_y1:
        crop = img_pil.crop((src_x1, src_y1, src_x2, src_y2))
        view.paste(crop, (src_x1 - x1, src_y1 - y1))
        
    return view.resize(tam_foto, Image.LANCZOS)

def auto_foco(img_cv, modo):
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5)
    h, w = img_cv.shape[:2]
    cx, cy, lado = w//2, h//2, min(h, w)
    
    if len(faces) > 0:
        (fx, fy, fw, fh) = max(faces, key=lambda f: f[2]*f[3])
        if modo == "face":
            lado = fh * 2.5; cx, cy = fx + fw//2, fy + fh//2
        else:
            lado = max((min(fy + fh*8, h) - fy)*1.2, fh*1.5)
            cx, cy = fx + fw//2, fy + lado//2.4
            
    st.session_state.zoom = w / lado
    st.session_state.off_x = (w/2 - cx) * st.session_state.zoom
    st.session_state.off_y = (h/2 - cy) * st.session_state.zoom

def gerar_final_hd(img_orig, txts):
    crop_hd = gerar_recorte(img_orig, MOLDURA_FULL.size, POSICAO_FOTO_FULL, TAM_FINAL_FULL)
    base_hd = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
    base_hd.paste(crop_hd, POSICAO_FOTO_FULL)
    base_hd.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
    for k, v in txts.items():
        base_hd = desenhar_texto(base_hd, v.upper(), k, escala=1.0)
    buf = io.BytesIO(); base_hd.save(buf, format="PNG"); return buf.getvalue()

# --- INTERFACE (Layout Condensado V17) ---
st.title("SIV-PC Web")

# 1. Upload e Instrução
uploaded = st.file_uploader("Carregar Fotografia do Indiciado", type=['jpg','png','jpeg'])

if uploaded:
    img_orig = Image.open(uploaded).convert('RGB')
    
    # Prepara Proxy
    f_escala = get_preview_scale(img_orig)
    w_p, h_p = int(img_orig.width * f_escala), int(img_orig.height * f_escala)
    img_proxy = img_orig.resize((w_p, h_p), Image.NEAREST)
    moldura_p = MOLDURA_FULL.resize((int(MOLDURA_FULL.width * f_escala), int(MOLDURA_FULL.height * f_escala)), Image.NEAREST)
    pos_p = (int(POSICAO_FOTO_FULL[0]*f_escala), int(POSICAO_FOTO_FULL[1]*f_escala))
    tam_p = (int(TAM_FINAL_FULL[0]*f_escala), int(TAM_FINAL_FULL[1]*f_escala))

    # 2. Dados Condensados
    with st.container():
        # Linha 1: Nome
        nome = st.text_input("Nome", placeholder="Nome Completo", label_visibility="collapsed")
        # Linha 2: 4 campos espremidos
        c1, c2, c3, c4 = st.columns(4)
        rg = c1.text_input("RG", placeholder="RG/CPF", label_visibility="collapsed")
        sit = c2.text_input("Situação", value="INDICIADO", label_visibility="collapsed")
        nat = c3.text_input("Natureza", placeholder="Artigo/Natureza", label_visibility="collapsed")
        out = c4.text_input("Outros", placeholder="Data/BO", label_visibility="collapsed")

    st.write("---")

    # 3. PAINEL DE CONTROLE TIPO "CRUZ" (JOYSTICK)
    
    # Passo de movimento
    step = 50 

    # --- LINHA CIMA (Botão UP) ---
    c_up1, c_up2, c_up3 = st.columns([1, 4, 1]) # Coluna central mais larga para alinhar com imagem
    with c_up2:
        if st.button("⬆️", use_container_width=True): st.session_state.off_y += step

    # --- LINHA MEIO (ESQ - PREVIEW - DIR) ---
    c_mid_L, c_mid_C, c_mid_R = st.columns([1, 4, 1])
    
    with c_mid_L:
        # Espaçador para descer o botão para o meio da altura da foto
        st.write("") 
        st.write("")
        st.write("")
        if st.button("⬅️", use_container_width=True): st.session_state.off_x += step

    with c_mid_C:
        # PREVIEW CENTRALIZADO
        crop_p = gerar_recorte(img_proxy, moldura_p.size, pos_p, tam_p)
        base_p = Image.new("RGBA", moldura_p.size, "WHITE")
        base_p.paste(crop_p, pos_p)
        base_p.paste(moldura_p, (0,0), mask=moldura_p)
        
        txts = {"situacao": sit, "natureza": nat, "nome": nome, "documento": rg, "outras": out}
        for k, v in txts.items():
            base_p = desenhar_texto(base_p, v.upper(), k, escala=f_escala)
            
        st.image(base_p, use_container_width=True)

    with c_mid_R:
        st.write("")
        st.write("")
        st.write("")
        if st.button("➡️", use_container_width=True): st.session_state.off_x -= step

    # --- LINHA BAIXO (Botão DOWN) ---
    c_dw1, c_dw2, c_dw3 = st.columns([1, 4, 1])
    with c_dw2:
        if st.button("⬇️", use_container_width=True): st.session_state.off_y -= step

    # --- ZOOM (Abaixo do botão Down) ---
    st.session_state.zoom = st.slider("Zoom", 0.1, 5.0, st.session_state.zoom, 0.1, label_visibility="collapsed")

    # --- BOTÕES DE FOCO ---
    cf1, cf2 = st.columns(2)
    if cf1.button("Focar Rosto", use_container_width=True): auto_foco(np.array(img_proxy), "face")
    if cf2.button("Focar Corpo", use_container_width=True): auto_foco(np.array(img_proxy), "corpo")

    # --- DOWNLOAD (Rodapé) ---
    st.write("---")
    st.download_button(
        label="💾 BAIXAR FOTO FINAL",
        data=gerar_final_hd(img_orig, txts),
        file_name=f"Placa_{nome.split()[0] if nome else 'PC'}.png",
        mime="image/png",
        type="primary",
        use_container_width=True
    )

else:
    reset_state()
