import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Web", layout="centered", page_icon="👮")

# --- CSS (Ajustes de Layout e Botões) ---
st.markdown("""
    <style>
    /* Reduz espaço no topo */
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Botões grandes e preenchendo a célula */
    div.stButton > button {
        width: 100%;
        height: 50px;
        font-size: 24px;
        font-weight: bold;
        border-radius: 8px;
        margin: 0px;
    }
    
    /* Centralização geral */
    div[data-testid="column"] {
        text-align: center;
        display: flex;
        justify_content: center;
        align-items: center;
    }
    
    /* Borda no Preview */
    img {
        border: 2px solid #ddd;
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

# --- ESTADO E CALLBACKS (A Solução do Lag) ---
if 'zoom' not in st.session_state: st.session_state.zoom = 1.0
if 'off_x' not in st.session_state: st.session_state.off_x = 0
if 'off_y' not in st.session_state: st.session_state.off_y = 0

# Passo de movimento (pixels)
STEP = 40

# Callbacks para botões (Executam ANTES do re-run)
def cb_up(): st.session_state.off_y -= STEP  # Invertido para lógica intuitiva
def cb_down(): st.session_state.off_y += STEP
def cb_left(): st.session_state.off_x -= STEP
def cb_right(): st.session_state.off_x += STEP
def cb_zoom_in(): st.session_state.zoom += 0.1
def cb_zoom_out(): 
    if st.session_state.zoom > 0.15: st.session_state.zoom -= 0.1

def cb_auto_foco(pil_img, modo):
    """Callback para foco automático"""
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
            cx, cy = x + w // 2, y + h // 2
        else:
            h_proj = h * 8.0
            limite_inf = min(y + h_proj, h_img - (h * 0.2))
            h_util = max(limite_inf - y, h * 1.5)
            lado_ideal = h_util * 1.2
            cx, cy = x + w // 2, y + h_util // 2
            
    # Atualiza estado direto
    st.session_state.zoom = 1500 / lado_ideal # Base de cálculo aproximada
    # Ajuste fino para a escala real da imagem carregada
    # (Fator de correção zoom visual vs zoom real)
    st.session_state.zoom = w_img / lado_ideal 
    
    st.session_state.off_x = int((w_img / 2 - cx) * st.session_state.zoom)
    st.session_state.off_y = int((h_img / 2 - cy) * st.session_state.zoom)


# --- FUNÇÕES DE DESENHO ---
def get_preview_scale(img_pil):
    # Preview fixo em 200px (bem pequeno como pedido)
    return 200 / max(img_pil.size)

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
    # Inversão de lógica aplicada nos botões, aqui mantém a matemática padrão
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

def gerar_final_hd(img_orig, txts):
    crop_hd = gerar_recorte(img_orig, MOLDURA_FULL.size, POSICAO_FOTO_FULL, TAM_FINAL_FULL)
    base_hd = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
    base_hd.paste(crop_hd, POSICAO_FOTO_FULL)
    base_hd.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
    for k, v in txts.items():
        base_hd = desenhar_texto(base_hd, v.upper(), k, escala=1.0)
    buf = io.BytesIO(); base_hd.save(buf, format="PNG"); return buf.getvalue()

# --- INTERFACE ---
st.title("SIV-PC Web")

uploaded = st.file_uploader("1. Carregar Fotografia", type=['jpg','png','jpeg'])

if uploaded:
    img_orig = Image.open(uploaded).convert('RGB')
    
    # Prepara Proxy (Preview Leve)
    f_escala = get_preview_scale(img_orig)
    w_p, h_p = int(img_orig.width * f_escala), int(img_orig.height * f_escala)
    img_proxy = img_orig.resize((w_p, h_p), Image.NEAREST)
    moldura_p = MOLDURA_FULL.resize((int(MOLDURA_FULL.width * f_escala), int(MOLDURA_FULL.height * f_escala)), Image.NEAREST)
    pos_p = (int(POSICAO_FOTO_FULL[0]*f_escala), int(POSICAO_FOTO_FULL[1]*f_escala))
    tam_p = (int(TAM_FINAL_FULL[0]*f_escala), int(TAM_FINAL_FULL[1]*f_escala))

    # --- DADOS CONDENSADOS ---
    with st.container():
        # Linha 1: 3 Campos
        c1, c2, c3 = st.columns([1, 1, 1])
        sit = c1.text_input("Situação", "INDICIADO")
        nat = c2.text_input("Natureza")
        out = c3.text_input("Outros (BO/Data)")
        
        # Linha 2: 2 Campos
        c4, c5 = st.columns([2, 1])
        nome = c4.text_input("Nome Completo")
        rg = c5.text_input("Documento (RG/CPF)")

    st.write("---")

    # --- JOYSTICK CENTRALIZADO ---
    
    # 1. Botão Cima
    c_up1, c_up2, c_up3 = st.columns([2, 1, 2])
    with c_up2:
        st.button("⬆️", on_click=cb_up, use_container_width=True)

    # 2. Linha Meio (Esq - FOTO - Dir)
    # vertical_alignment="center" garante que setas fiquem no meio da altura da foto
    c_mid_L, c_mid_C, c_mid_R = st.columns([1, 2, 1], vertical_alignment="center")
    
    with c_mid_L:
        st.button("⬅️", on_click=cb_left, use_container_width=True)

    with c_mid_C:
        # GERA PREVIEW
        crop_p = gerar_recorte(img_proxy, moldura_p.size, pos_p, tam_p)
        base_p = Image.new("RGBA", moldura_p.size, "WHITE")
        base_p.paste(crop_p, pos_p)
        base_p.paste(moldura_p, (0,0), mask=moldura_p)
        
        txts = {"situacao": sit, "natureza": nat, "nome": nome, "documento": rg, "outras": out}
        for k, v in txts.items():
            base_p = desenhar_texto(base_p, v.upper(), k, escala=f_escala)
            
        st.image(base_p, use_container_width=True)

    with c_mid_R:
        st.button("➡️", on_click=cb_right, use_container_width=True)

    # 3. Botão Baixo
    c_dw1, c_dw2, c_dw3 = st.columns([2, 1, 2])
    with c_dw2:
        st.button("⬇️", on_click=cb_down, use_container_width=True)

    # --- CONTROLES INFERIORES ---
    st.write("") # Espaço
    
    # Zoom e Foco
    cz1, cz2, cz3, cz4 = st.columns([1, 1, 1.5, 1.5])
    with cz1:
        st.button("➕ Zoom", on_click=cb_zoom_in, use_container_width=True)
    with cz2:
        st.button("➖ Zoom", on_click=cb_zoom_out, use_container_width=True)
    with cz3:
        st.button("Focar Rosto", on_click=cb_auto_foco, args=(img_orig, "face"), use_container_width=True)
    with cz4:
        st.button("Focar Corpo", on_click=cb_auto_foco, args=(img_orig, "corpo"), use_container_width=True)

    # Botão Final
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
    st.info("👆 Carregue a foto para começar.")
    # Reset state
    st.session_state.zoom = 1.0
    st.session_state.off_x = 0
    st.session_state.off_y = 0
