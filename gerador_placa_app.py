import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Web", layout="wide", page_icon="👮") # Layout WIDE usa a tela toda

# --- CSS (Estilo Compacto) ---
st.markdown("""
    <style>
    .stButton button {
        width: 100%;
        font-weight: bold;
        padding: 0.2rem; /* Botões mais finos */
    }
    .block-container {
        padding-top: 2rem; /* Menos espaço no topo */
    }
    img {
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
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

# Constantes Originais
POSICAO_FOTO_FULL = (113, 321)
TAM_FINAL_FULL = (1500, 1500)
FONTE_ARQUIVO = "arial.ttf"

# Configuração de Texto (Escala 1:1)
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

# --- LÓGICA DE ESCALA (A Mágica da Velocidade) ---
def get_preview_scale(img_pil):
    """Calcula fator de redução para o preview ficar leve (max 600px)"""
    w, h = img_pil.size
    fator = 600 / max(w, h)
    return fator if fator < 1 else 1.0

# --- TEXTO ---
def desenhar_texto(img, texto, chave, escala=1.0):
    """Desenha texto ajustado à escala (Preview ou Full)"""
    if not texto: return img
    cfg = CONFIG_TEXTOS[chave]
    
    # Aplica escala nas coordenadas da caixa
    x, y, w, h = [int(v * escala) for v in cfg['box']]
    rot = cfg['rotate']
    
    # Fonte também escala
    try: font_n = FONTE_ARQUIVO
    except: font_n = "arial.ttf"
    
    # Ajuste de tamanho da fonte
    w_disp, h_disp = (h, w) if rot in [90, 270] else (w, h)
    tam = int(300 * escala) # Começa grande proporcionalmente
    
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

# --- CORTE ---
def gerar_recorte(img_pil, moldura_size, pos_foto, tam_foto):
    """Gera o recorte visual baseado no estado do joystick"""
    zoom = st.session_state.zoom
    # Ajusta sensibilidade do offset pelo zoom (para ficar preciso)
    off_x = st.session_state.off_x / zoom
    off_y = st.session_state.off_y / zoom
    
    w_img, h_img = img_pil.size
    
    # Centro da imagem + deslocamento
    cx = (w_img / 2) - off_x
    cy = (h_img / 2) - off_y
    
    # Tamanho do recorte necessário na imagem original
    lado_req = tam_foto[0] / zoom
    
    x1, y1 = int(cx - lado_req/2), int(cy - lado_req/2)
    x2, y2 = int(cx + lado_req/2), int(cy + lado_req/2)
    
    # Viewport
    view = Image.new("RGB", (int(x2-x1), int(y2-y1)), (255,255,255))
    src_x1, src_y1 = max(0, x1), max(0, y1)
    src_x2, src_y2 = min(w_img, x2), min(h_img, y2)
    
    if src_x2 > src_x1 and src_y2 > src_y1:
        crop = img_pil.crop((src_x1, src_y1, src_x2, src_y2))
        view.paste(crop, (src_x1 - x1, src_y1 - y1))
        
    return view.resize(tam_foto, Image.LANCZOS)

# --- AUTO FOCO ---
def auto_foco(img_cv, modo):
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5)
    h, w = img_cv.shape[:2]
    cx, cy, lado = w//2, h//2, min(h, w)
    
    if len(faces) > 0:
        (fx, fy, fw, fh) = max(faces, key=lambda f: f[2]*f[3])
        if modo == "face":
            lado = fh * 2.5
            cx, cy = fx + fw//2, fy + fh//2
        else:
            lado = max((min(fy + fh*8, h) - fy)*1.2, fh*1.5)
            cx, cy = fx + fw//2, fy + lado//2.4
            
    # Converte geometria para Zoom e Offset do SessionState
    # O cálculo é agnóstico de escala (funciona no preview e no full)
    novo_zoom = 1500 / lado # Baseado no alvo de 1500px (proporcional)
    # Mas espere, se estamos no preview, o alvo é menor.
    # Correção: O zoom é relativo à imagem que estamos vendo.
    # Se a imagem é pequena, o lado é pequeno. A proporção se mantém.
    
    # Atualiza Session
    st.session_state.zoom = TAM_FINAL_FULL[0] / (lado * (TAM_FINAL_FULL[0]/1500)) # Simplificado: zoom é abstrato
    # Vamos usar lógica simples: Zoom 1.0 = Imagem preenche buraco.
    st.session_state.zoom = w / lado # Aproximação inicial
    
    # Recalcula offset
    st.session_state.off_x = (w/2 - cx) * st.session_state.zoom
    st.session_state.off_y = (h/2 - cy) * st.session_state.zoom


# --- UI PRINCIPAL ---
st.title("SIV-PC Web")

col_upload, col_dados = st.columns([1, 2])
with col_upload:
    uploaded = st.file_uploader("📂 Carregar Foto", type=['jpg','png','jpeg'])

with col_dados:
    c1, c2 = st.columns(2)
    sit = c1.text_input("Situação", "INDICIADO")
    nat = c2.text_input("Natureza")
    nome = st.text_input("Nome")
    c3, c4 = st.columns(2)
    rg = c3.text_input("RG/CPF")
    out = c4.text_input("Outros")

if uploaded:
    # 1. Carrega Original e cria Proxy (Preview Leve)
    img_orig = Image.open(uploaded).convert('RGB')
    
    # Cria versão leve (max 600px) para exibir na tela
    fator_escala = get_preview_scale(img_orig)
    w_prev, h_prev = int(img_orig.width * fator_escala), int(img_orig.height * fator_escala)
    img_proxy = img_orig.resize((w_prev, h_prev), Image.NEAREST) # NEAREST é super rápido
    
    # Prepara Moldura Preview (também reduzida)
    moldura_prev = MOLDURA_FULL.resize((int(MOLDURA_FULL.width * fator_escala), int(MOLDURA_FULL.height * fator_escala)), Image.NEAREST)
    
    # Parâmetros ajustados para a escala do preview
    pos_foto_prev = (int(POSICAO_FOTO_FULL[0] * fator_escala), int(POSICAO_FOTO_FULL[1] * fator_escala))
    tam_foto_prev = (int(TAM_FINAL_FULL[0] * fator_escala), int(TAM_FINAL_FULL[1] * fator_escala))

    # --- LAYOUT LADO A LADO ---
    st.divider()
    col_ctrl, col_view = st.columns([1, 1.5], gap="large")

    with col_ctrl:
        st.subheader("Ajustes")
        
        # Botões Auto (Usam OpenCV no Proxy, rápido)
        b1, b2 = st.columns(2)
        if b1.button("👤 ROSTO"):
            # Calcula na imagem PROXY (rápida)
            calcular_foco_proxy = np.array(img_proxy)
            auto_foco(calcular_foco_proxy, "face")
            
        if b2.button("🧍 CORPO"):
            calcular_foco_proxy = np.array(img_proxy)
            auto_foco(calcular_foco_proxy, "corpo")

        # Joystick Compacto
        st.write("")
        c_joy = st.container()
        with c_joy:
            jc1, jc2, jc3 = st.columns([1,2,1])
            step = 30 # Pixel step no preview
            
            with jc2: 
                if st.button("⬆️"): st.session_state.off_y += step
            
            jc_m1, jc_m2, jc_m3 = st.columns([1,2,1])
            with jc_m1: 
                if st.button("⬅️"): st.session_state.off_x += step
            with jc_m3: 
                if st.button("➡️"): st.session_state.off_x -= step
                
            jc_b1, jc_b2, jc_b3 = st.columns([1,2,1])
            with jc_b2: 
                if st.button("⬇️"): st.session_state.off_y -= step
        
        # Zoom Slider (Mais rápido que botões)
        st.write("Zoom:")
        zoom_val = st.slider("Nível de Zoom", 0.1, 5.0, st.session_state.zoom, 0.1, label_visibility="collapsed")
        st.session_state.zoom = zoom_val

    with col_view:
        # GERA PREVIEW (Usando imagens pequenas = Rápido)
        # 1. Recorta Proxy
        crop_prev = gerar_recorte(img_proxy, moldura_prev.size, pos_foto_prev, tam_foto_prev)
        
        # 2. Cola Moldura Proxy
        base_prev = Image.new("RGBA", moldura_prev.size, "WHITE")
        base_prev.paste(crop_prev, pos_foto_prev)
        base_prev.paste(moldura_prev, (0,0), mask=moldura_prev)
        
        # 3. Desenha Texto (com escala reduzida)
        txts = {"situacao": sit, "natureza": nat, "nome": nome, "documento": rg, "outras": out}
        for k, v in txts.items():
            base_prev = desenhar_texto(base_prev, v.upper(), k, escala=fator_escala)
            
        st.image(base_prev, width=450, caption="Pré-visualização (Baixa Resolução)")
        
        # --- DOWNLOAD (Processamento Pesado só aqui) ---
        # Botão separado para processar o Full HD
        # Evita travar a interface durante o ajuste
        
        # Preparar buffer do download com função callback (Lazy)
        def gerar_final_hd():
            # Aqui sim usamos a MOLDURA_FULL e img_orig
            crop_hd = gerar_recorte(img_orig, MOLDURA_FULL.size, POSICAO_FOTO_FULL, TAM_FINAL_FULL)
            
            base_hd = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
            base_hd.paste(crop_hd, POSICAO_FOTO_FULL)
            base_hd.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
            
            for k, v in txts.items():
                base_hd = desenhar_texto(base_hd, v.upper(), k, escala=1.0)
                
            buf = io.BytesIO()
            base_hd.save(buf, format="PNG")
            return buf.getvalue()

        st.download_button(
            label="💾 BAIXAR EM ALTA RESOLUÇÃO",
            data=gerar_final_hd(),
            file_name=f"Placa_{nome.split()[0] if nome else 'PC'}.png",
            mime="image/png",
            type="primary",
            use_container_width=True
        )
else:
    reset_state()
    st.info("Carregue uma imagem para começar.")
