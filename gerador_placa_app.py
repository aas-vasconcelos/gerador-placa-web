import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Web", layout="centered", page_icon="👮")

# --- CSS (Visual Polido) ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    
    /* Botões grandes e fáceis de clicar */
    div.stButton > button {
        width: 100%;
        height: 50px;
        font-size: 24px;
        font-weight: bold;
        border-radius: 8px;
        border: 1px solid #ccc;
    }
    
    /* Centraliza conteúdo das colunas */
    div[data-testid="column"] {
        display: flex;
        justify_content: center;
        align-items: center;
    }
    
    /* Borda do Preview */
    img {
        border: 2px solid #333;
        border-radius: 4px;
    }
    </style>
""", unsafe_allow_html=True)

# --- RECURSOS ---
@st.cache_resource
def load_resources():
    try:
        moldura = Image.open("moldura.png").convert("RGBA")
    except:
        st.error("ERRO CRÍTICO: 'moldura.png' não encontrada.")
        return None, None
    
    try:
        # Tenta carregar o cascade. Se falhar, retorna None (sem crashar app)
        path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face = cv2.CascadeClassifier(path)
        if face.empty(): face = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    except:
        face = None
        
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

# --- ESTADO SEGURO (Mecanismo Anti-Crash) ---
def init_state():
    if 'zoom' not in st.session_state: st.session_state.zoom = 1.0
    if 'off_x' not in st.session_state: st.session_state.off_x = 0
    if 'off_y' not in st.session_state: st.session_state.off_y = 0
    
    # Proteção: Se valores corrompidos aparecerem (NaN, Infinito), reseta
    if st.session_state.zoom <= 0.01 or np.isnan(st.session_state.zoom):
        st.session_state.zoom = 1.0
        st.session_state.off_x = 0
        st.session_state.off_y = 0

init_state()

# --- CALLBACKS (Ações Imediatas) ---
STEP_MOVE = 40

# Lógica Invertida: Se quero mover a imagem para DIREITA,
# preciso diminuir o offset negativo (ou aumentar o positivo).
# offset positivo = desloca a imagem para direita.
def cb_up(): st.session_state.off_y -= STEP_MOVE
def cb_down(): st.session_state.off_y += STEP_MOVE
def cb_left(): st.session_state.off_x -= STEP_MOVE
def cb_right(): st.session_state.off_x += STEP_MOVE

def cb_zoom_in(): st.session_state.zoom += 0.1
def cb_zoom_out(): 
    if st.session_state.zoom > 0.2: st.session_state.zoom -= 0.1

def cb_auto_foco(pil_img, modo):
    """Calcula e define o estado seguro para foco"""
    if FACE_CASCADE is None: 
        st.toast("⚠️ Detector de rosto não carregado.")
        return
    
    try:
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5)
        
        h_img, w_img = cv_img.shape[:2]
        # Padrão: Centro da imagem
        target_cx, target_cy = w_img // 2, h_img // 2
        lado_ideal = min(h_img, w_img)
        
        if len(faces) > 0:
            (x, y, w, h) = max(faces, key=lambda f: f[2]*f[3])
            
            if modo == "face":
                lado_ideal = h * 2.5
                target_cx = x + w // 2
                target_cy = y + h // 2
            else: # Corpo
                h_proj = h * 8.0
                lim_inf = min(y + h_proj, h_img - (h * 0.2))
                h_util = max(lim_inf - y, h * 1.5)
                lado_ideal = h_util * 1.2
                target_cx = x + w // 2
                target_cy = y + h_util // 2

        # Conversão Matemática para o Estado do Joystick
        # Zoom = Tamanho do Buraco (1500) / Tamanho do Crop (lado_ideal)
        # Ajustamos para a escala relativa da imagem
        new_zoom = 1500 / lado_ideal
        
        # Offset: Distância do centro da imagem original até o centro do alvo
        # offset positivo = move imagem para direita/baixo
        new_off_x = (w_img / 2) - target_cx
        new_off_y = (h_img / 2) - target_cy
        
        # Inverte sinal porque a função de recorte usa subtração
        # off_x positivo na função recorte = move crop para esquerda (imagem vai pra direita)
        # Vamos manter consistente com os botões
        st.session_state.zoom = max(0.1, w_img / lado_ideal) # Simplificação segura
        
        # Centraliza
        st.session_state.off_x = (w_img/2 - target_cx) * st.session_state.zoom
        st.session_state.off_y = (h_img/2 - target_cy) * st.session_state.zoom
        
    except Exception as e:
        st.error(f"Erro no auto-foco: {e}")
        # Reseta em caso de erro matemático
        st.session_state.zoom = 1.0
        st.session_state.off_x = 0
        st.session_state.off_y = 0

# --- FUNÇÕES GRÁFICAS ---
def get_preview_scale(img_pil):
    # Preview pequeno (200px)
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
    # Recupera estado
    zoom = st.session_state.zoom
    # Se zoom for inválido, reseta
    if zoom <= 0: zoom = 1.0
    
    # Aplica offsets (Sinal invertido para corresponder à direção visual do botão)
    # Botão Direita (+) -> Queremos ver a parte esquerda da imagem (crop move esq) -> Imagem visualmente vai pra direita
    off_x = st.session_state.off_x / zoom
    off_y = st.session_state.off_y / zoom
    
    w_img, h_img = img_pil.size
    
    # Centro do recorte
    cx = (w_img / 2) - off_x
    cy = (h_img / 2) - off_y
    
    lado_req = tam_foto[0] / zoom
    
    x1, y1 = int(cx - lado_req/2), int(cy - lado_req/2)
    x2, y2 = int(cx + lado_req/2), int(cy + lado_req/2)
    
    # Cria canvas branco (Viewport)
    view = Image.new("RGB", (int(x2-x1), int(y2-y1)), (255,255,255))
    
    # Intersecção segura
    src_x1, src_y1 = max(0, x1), max(0, y1)
    src_x2, src_y2 = min(w_img, x2), min(h_img, y2)
    
    if src_x2 > src_x1 and src_y2 > src_y1:
        crop = img_pil.crop((src_x1, src_y1, src_x2, src_y2))
        dst_x = src_x1 - x1
        dst_y = src_y1 - y1
        view.paste(crop, (dst_x, dst_y))
        
    return view.resize(tam_foto, Image.LANCZOS)

def gerar_final_hd(img_orig, txts):
    try:
        crop_hd = gerar_recorte(img_orig, MOLDURA_FULL.size, POSICAO_FOTO_FULL, TAM_FINAL_FULL)
        base_hd = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
        base_hd.paste(crop_hd, POSICAO_FOTO_FULL)
        base_hd.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
        for k, v in txts.items():
            base_hd = desenhar_texto(base_hd, v.upper(), k, escala=1.0)
        buf = io.BytesIO()
        base_hd.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        st.error(f"Erro ao gerar download: {e}")
        return None

# --- UI PRINCIPAL ---
st.title("SIV-PC Web")

if MOLDURA_FULL is None:
    st.error("Sistema Parado: Moldura não encontrada.")
    st.stop()

uploaded = st.file_uploader("1. Carregar Fotografia", type=['jpg','png','jpeg'])

if uploaded:
    try:
        img_orig = Image.open(uploaded).convert('RGB')
    except:
        st.error("Arquivo de imagem inválido.")
        st.stop()

    # Proxy para Preview (200px)
    f_escala = get_preview_scale(img_orig)
    w_p, h_p = int(img_orig.width * f_escala), int(img_orig.height * f_escala)
    img_proxy = img_orig.resize((w_p, h_p), Image.NEAREST)
    moldura_p = MOLDURA_FULL.resize((int(MOLDURA_FULL.width * f_escala), int(MOLDURA_FULL.height * f_escala)), Image.NEAREST)
    pos_p = (int(POSICAO_FOTO_FULL[0]*f_escala), int(POSICAO_FOTO_FULL[1]*f_escala))
    tam_p = (int(TAM_FINAL_FULL[0]*f_escala), int(TAM_FINAL_FULL[1]*f_escala))

    # --- CAMPOS CONDENSADOS ---
    with st.container():
        c1, c2, c3 = st.columns([1, 1, 1])
        sit = c1.text_input("Situação", "INDICIADO")
        nat = c2.text_input("Natureza")
        out = c3.text_input("Outros (BO/Data)")
        
        c4, c5 = st.columns([2, 1])
        nome = c4.text_input("Nome Completo")
        rg = c5.text_input("Documento (RG/CPF)")

    st.markdown("---")

    # --- PAINEL DE CONTROLE (Layout Cruz) ---
    
    # Linha 1: Seta Cima
    c_u1, c_u2, c_u3 = st.columns([2, 1, 2])
    with c_u2:
        st.button("⬆️", on_click=cb_up, use_container_width=True)

    # Linha 2: Esq | Preview | Dir
    c_mid_L, c_mid_C, c_mid_R = st.columns([1, 2, 1], vertical_alignment="center")
    
    with c_mid_L:
        st.button("⬅️", on_click=cb_left, use_container_width=True)

    with c_mid_C:
        # Geração do Preview Visual
        try:
            crop_p = gerar_recorte(img_proxy, moldura_p.size, pos_p, tam_p)
            base_p = Image.new("RGBA", moldura_p.size, "WHITE")
            base_p.paste(crop_p, pos_p)
            base_p.paste(moldura_p, (0,0), mask=moldura_p)
            
            txts = {"situacao": sit, "natureza": nat, "nome": nome, "documento": rg, "outras": out}
            for k, v in txts.items():
                base_p = desenhar_texto(base_p, v.upper(), k, escala=f_escala)
                
            st.image(base_p, use_container_width=True)
        except Exception as e:
            st.error(f"Erro Preview: {e}")

    with c_mid_R:
        st.button("➡️", on_click=cb_right, use_container_width=True)

    # Linha 3: Seta Baixo
    c_d1, c_d2, c_d3 = st.columns([2, 1, 2])
    with c_d2:
        st.button("⬇️", on_click=cb_down, use_container_width=True)

    # --- CONTROLES INFERIORES ---
    st.write("")
    
    # Linha de Zoom
    cz_mid, cz_b1, cz_b2, cz_end = st.columns([0.5, 2, 2, 0.5])
    with cz_b1:
        st.button("➕ Zoom", on_click=cb_zoom_in, use_container_width=True)
    with cz_b2:
        st.button("➖ Zoom", on_click=cb_zoom_out, use_container_width=True)

    # Linha de Foco
    cf_mid, cf_b1, cf_b2, cf_end = st.columns([0.5, 2, 2, 0.5])
    with cf_b1:
        st.button("Focar Rosto", on_click=cb_auto_foco, args=(img_orig, "face"), use_container_width=True)
    with cf_b2:
        st.button("Focar Corpo", on_click=cb_auto_foco, args=(img_orig, "corpo"), use_container_width=True)

    # Botão Final
    st.markdown("---")
    
    data_hd = gerar_final_hd(img_orig, txts)
    if data_hd:
        st.download_button(
            label="💾 BAIXAR FOTO FINAL",
            data=data_hd,
            file_name=f"Placa_{nome.split()[0] if nome else 'PC'}.png",
            mime="image/png",
            type="primary",
            use_container_width=True
        )

else:
    init_state() # Reseta se não tiver foto
