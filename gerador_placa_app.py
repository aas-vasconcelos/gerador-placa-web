import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# --- CONFIGURAÇÕES DA PÁGINA (Compacta) ---
st.set_page_config(page_title="SIV-PC Web", layout="wide", page_icon="👮")

# --- CSS PARA ALINHAMENTO PERFEITO ---
st.markdown("""
    <style>
    /* Remove espaços em branco excessivos do topo */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    
    /* Estilo dos Botões do Joystick */
    div.stButton > button {
        width: 100%;
        padding: 0px 5px;
        font-size: 20px;
        line-height: 1.5;
        border-radius: 8px;
        height: 50px; /* Altura fixa para alinhar */
    }
    
    /* Centraliza colunas */
    div[data-testid="column"] { text-align: center; }
    
    /* Borda no Preview */
    img { border: 1px solid #ccc; border-radius: 5px; }
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

# --- LÓGICA (Escala Reduzida para Performance) ---
def get_preview_scale(img_pil):
    # Reduz para max 350px para ser MUITO rápido e pequeno na tela
    w, h = img_pil.size
    fator = 350 / max(w, h)
    return fator if fator < 1 else 1.0

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

# --- DOWNLOADER LAZY (HD) ---
def gerar_final_hd(img_orig, txts):
    crop_hd = gerar_recorte(img_orig, MOLDURA_FULL.size, POSICAO_FOTO_FULL, TAM_FINAL_FULL)
    base_hd = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
    base_hd.paste(crop_hd, POSICAO_FOTO_FULL)
    base_hd.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
    for k, v in txts.items():
        base_hd = desenhar_texto(base_hd, v.upper(), k, escala=1.0)
    buf = io.BytesIO(); base_hd.save(buf, format="PNG"); return buf.getvalue()

# --- INTERFACE PRINCIPAL (3 COLUNAS) ---
st.title("SIV-PC Web")

# Linha 1: Upload (Ocupa largura total para ser fácil clicar)
uploaded = st.file_uploader("1. Carregar Foto", type=['jpg','png','jpeg'])

if uploaded:
    img_orig = Image.open(uploaded).convert('RGB')
    
    # Criar Proxy Leve (350px max)
    f_escala = get_preview_scale(img_orig)
    w_p, h_p = int(img_orig.width * f_escala), int(img_orig.height * f_escala)
    img_proxy = img_orig.resize((w_p, h_p), Image.NEAREST)
    moldura_p = MOLDURA_FULL.resize((int(MOLDURA_FULL.width * f_escala), int(MOLDURA_FULL.height * f_escala)), Image.NEAREST)
    pos_p = (int(POSICAO_FOTO_FULL[0]*f_escala), int(POSICAO_FOTO_FULL[1]*f_escala))
    tam_p = (int(TAM_FINAL_FULL[0]*f_escala), int(TAM_FINAL_FULL[1]*f_escala))

    # --- ÁREA DE TRABALHO (3 COLUNAS) ---
    c_inputs, c_ctrl, c_view = st.columns([1.5, 1.2, 1.2], gap="medium")

    # COLUNA 1: DADOS
    with c_inputs:
        st.subheader("📝 Dados")
        nome = st.text_input("Nome")
        c1a, c1b = st.columns(2)
        rg = c1a.text_input("RG/CPF")
        sit = c1b.text_input("Situação", "INDICIADO")
        c2a, c2b = st.columns(2)
        nat = c2a.text_input("Natureza")
        out = c2b.text_input("Outros")

    # COLUNA 2: CONTROLES
    with c_ctrl:
        st.subheader("🎛️ Ajustes")
        
        # Botões Auto
        b1, b2 = st.columns(2)
        if b1.button("ROSTO", use_container_width=True): auto_foco(np.array(img_proxy), "face")
        if b2.button("CORPO", use_container_width=True): auto_foco(np.array(img_proxy), "corpo")

        st.markdown("---")
        
        # Joystick Compacto (Layout em Grade)
        step = 30
        
        # Linha Cima
        j1, j2, j3 = st.columns([1,1,1])
        with j2: 
            if st.button("⬆️", use_container_width=True): st.session_state.off_y += step
            
        # Linha Meio (Esq - Zoom - Dir)
        j4, j5, j6 = st.columns([1,1,1])
        with j4: 
            if st.button("⬅️", use_container_width=True): st.session_state.off_x += step
        with j5:
            st.write(f"Zoom: {st.session_state.zoom:.1f}x") # Label central
        with j6: 
            if st.button("➡️", use_container_width=True): st.session_state.off_x -= step
            
        # Linha Baixo
        j7, j8, j9 = st.columns([1,1,1])
        with j8: 
            if st.button("⬇️", use_container_width=True): st.session_state.off_y -= step
            
        # Zoom Slider (Rápido)
        st.session_state.zoom = st.slider("Nível de Zoom", 0.1, 5.0, st.session_state.zoom, 0.1)

    # COLUNA 3: PREVIEW (Miniatura)
    with c_view:
        st.subheader("👁️ Preview")
        
        # Processamento Visual Leve
        crop_p = gerar_recorte(img_proxy, moldura_p.size, pos_p, tam_p)
        base_p = Image.new("RGBA", moldura_p.size, "WHITE")
        base_p.paste(crop_p, pos_p)
        base_p.paste(moldura_p, (0,0), mask=moldura_p)
        
        txts = {"situacao": sit, "natureza": nat, "nome": nome, "documento": rg, "outras": out}
        for k, v in txts.items():
            base_p = desenhar_texto(base_p, v.upper(), k, escala=f_escala)
            
        st.image(base_p, caption="Visualização Reduzida", width=280) # TAMANHO FIXO PEQUENO
        
        # Download HD
        st.download_button(
            label="💾 BAIXAR ORIGINAL",
            data=gerar_final_hd(img_orig, txts),
            file_name=f"Placa_{nome.split()[0] if nome else 'PC'}.png",
            mime="image/png",
            type="primary",
            use_container_width=True
        )

else:
    reset_state()
    st.info("Aguardando upload...")
