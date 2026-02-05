import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Web", layout="centered", page_icon="👮")

# --- CSS PARA ESTILIZAR O JOYSTICK (OPCIONAL, MAS AJUDA) ---
st.markdown("""
    <style>
    .stButton button {
        width: 100%;
        font-weight: bold;
    }
    div[data-testid="column"] {
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- CARREGAMENTO DE RECURSOS ---
@st.cache_resource
def load_resources():
    try:
        moldura = Image.open("moldura.png").convert("RGBA")
    except:
        st.error("ERRO: 'moldura.png' não encontrada. Faça o upload no GitHub.")
        return None, None

    try:
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
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

# --- GERENCIAMENTO DE ESTADO (SESSION STATE) ---
if 'zoom' not in st.session_state: st.session_state.zoom = 1.0
if 'off_x' not in st.session_state: st.session_state.off_x = 0
if 'off_y' not in st.session_state: st.session_state.off_y = 0

# --- FUNÇÕES DE LÓGICA ---

def reset_state():
    st.session_state.zoom = 1.0
    st.session_state.off_x = 0
    st.session_state.off_y = 0

def calcular_auto_foco(pil_img, modo):
    """Calcula os valores de Zoom e Offset para focar no rosto/corpo, mas NÃO recorta.
       Apenas atualiza os controles manuais para a posição ideal."""
    if FACE_CASCADE is None: return
    
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5)
    
    h_img, w_img = cv_img.shape[:2]
    
    # Valores padrão (centro)
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
            
    # Converte a geometria detectada para Zoom e Offset do nosso sistema
    # Zoom = Tamanho do Buraco (1500) / Tamanho da Área na Foto (lado_ideal)
    novo_zoom = 1500 / lado_ideal
    
    # Offset = Distância do centro da foto até o centro desejado, ajustado pelo zoom
    # Fórmula inversa: cx = (w/2) - (off / zoom)  --> off = (w/2 - cx) * zoom
    novo_off_x = int((w_img / 2 - cx) * novo_zoom)
    novo_off_y = int((h_img / 2 - cy) * novo_zoom)
    
    # Atualiza Estado
    st.session_state.zoom = novo_zoom
    st.session_state.off_x = novo_off_x
    st.session_state.off_y = novo_off_y

def gerar_recorte_viewport(img_pil):
    """Gera o recorte baseado no Zoom e Offset atuais do Session State"""
    zoom = st.session_state.zoom
    off_x = st.session_state.off_x
    off_y = st.session_state.off_y
    
    w, h = img_pil.size
    
    # Centro desejado
    cx = (w / 2) - (off_x / zoom)
    cy = (h / 2) - (off_y / zoom)
    
    # Tamanho da área a recortar (Viewport)
    lado_req = 1500 / zoom
    
    x1 = int(cx - lado_req / 2)
    y1 = int(cy - lado_req / 2)
    x2 = int(cx + lado_req / 2)
    y2 = int(cy + lado_req / 2)
    
    # Crop Seguro com Padding Branco
    w_req, h_req = x2 - x1, y2 - y1
    view = Image.new("RGB", (w_req, h_req), (255, 255, 255))
    
    src_x1, src_y1 = max(0, x1), max(0, y1)
    src_x2, src_y2 = min(w, x2), min(h, y2)
    
    if src_x2 > src_x1 and src_y2 > src_y1:
        recorte = img_pil.crop((src_x1, src_y1, src_x2, src_y2))
        dst_x = src_x1 - x1
        dst_y = src_y1 - y1
        view.paste(recorte, (dst_x, dst_y))
        
    return view.resize(TAM_FINAL, Image.LANCZOS)

def desenhar_texto(img, texto, chave):
    if not texto: return img
    cfg = CONFIG_TEXTOS[chave]
    x, y, w, h = cfg['box']; cor = cfg['cor']; rot = cfg['rotate']; bold = cfg['bold']
    
    # Tenta carregar fonte, fallback para padrão se der erro
    try:
        font_name = FONTE_ARQUIVO
        font = ImageFont.truetype(font_name, 20)
    except:
        font = ImageFont.load_default()
    
    w_disp, h_disp = (h, w) if rot in [90, 270] else (w, h)
    
    # Loop de ajuste de tamanho
    tam = 300
    while tam > 10:
        try:
            current_font = ImageFont.truetype(font_name, tam)
        except:
            current_font = ImageFont.load_default()
            break # Se não tem arial, usa default e sai
            
        bbox = current_font.getbbox(texto)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
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
        d.text((w_disp/2, h_d/2), texto, font=font, fill=cor, anchor="mm")
        rot_img = lay.rotate(rot, expand=True)
        ox = x + (w - rot_img.width)//2; oy = y + (h - rot_img.height)//2
        img.paste(rot_img, (ox, oy), mask=rot_img)
    return img

# --- INTERFACE PRINCIPAL ---

st.title("Gerador de Placa - SIV-PC")

# 1. Upload
uploaded_file = st.file_uploader("📂 Carregar Fotografia", type=['jpg', 'jpeg', 'png', 'webp'])

if uploaded_file:
    image = Image.open(uploaded_file).convert('RGB')
    
    # 2. Dados
    with st.expander("📝 1. Preenchimento dos Dados", expanded=True):
        col_a, col_b = st.columns(2)
        sit = col_a.text_input("Situação", "INDICIADO")
        nat = col_b.text_input("Natureza")
        nome = st.text_input("Nome Completo")
        rg = col_a.text_input("Documento (RG/CPF)")
        outros = col_b.text_input("Outros (BO/Data)")

    st.divider()
    st.subheader("🖼️ 2. Ajuste da Imagem")
    
    # 3. Botões de Inteligência (Foco Automático)
    c_auto1, c_auto2 = st.columns(2)
    if c_auto1.button("🧠 FOCAR ROSTO (Auto)", use_container_width=True):
        calcular_auto_foco(image, "face")
    
    if c_auto2.button("🧠 FOCAR CORPO (Auto)", use_container_width=True):
        calcular_auto_foco(image, "corpo")

    # 4. Joystick de Controle
    st.write("Ajuste Fino Manual:")
    
    # Layout do Joystick 3x3
    col1, col2, col3 = st.columns([1, 2, 1])
    
    # Passo do movimento (pixels) e passo do zoom
    step_move = 50 
    step_zoom = 0.1

    with col2:
        if st.button("⬆️ Cima", key="up", use_container_width=True):
            st.session_state.off_y += step_move
            
    col_mid1, col_mid2, col_mid3 = st.columns([1, 2, 1])
    with col_mid1:
        if st.button("⬅️ Esq", key="left", use_container_width=True):
            st.session_state.off_x += step_move
    with col_mid3:
        if st.button("Dir ➡️", key="right", use_container_width=True):
            st.session_state.off_x -= step_move
            
    # Controles de Zoom no Centro
    with col_mid2:
        cz1, cz2 = st.columns(2)
        if cz1.button("➕ Zoom", use_container_width=True):
            st.session_state.zoom += step_zoom
        if cz2.button("➖ Zoom", use_container_width=True):
            if st.session_state.zoom > 0.1: st.session_state.zoom -= step_zoom
            
    col_bot1, col_bot2, col_bot3 = st.columns([1, 2, 1])
    with col_bot2:
        if st.button("⬇️ Baixo", key="down", use_container_width=True):
            st.session_state.off_y -= step_move

    # Mostra valores atuais (Debug visual)
    st.caption(f"Zoom: {st.session_state.zoom:.2f} | X: {st.session_state.off_x} | Y: {st.session_state.off_y}")

    # 5. Preview Completo
    st.divider()
    
    # Botão para gerar o preview pesado
    if st.button("📸 ATUALIZAR PREVIEW COM DADOS (Visualizar Resultado Final)", type="primary", use_container_width=True):
        # 1. Gera o recorte da foto
        img_crop = gerar_recorte_viewport(image)
        
        # 2. Monta na moldura
        base_preview = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
        base_preview.paste(img_crop, POSICAO_FOTO)
        base_preview.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
        
        # 3. Desenha os Textos
        txts = {"situacao": sit.upper(), "natureza": nat.upper(), "nome": nome.upper(), "documento": rg.upper(), "outras": outros.upper()}
        for k, v in txts.items():
            base_preview = desenhar_texto(base_preview, v, k)
            
        # 4. Mostra na tela (Reduzido para caber)
        st.image(base_preview, caption="Resultado Final (Prévia)", use_container_width=True)
        
        # 5. Prepara Botão de Download (Só aparece se o preview foi gerado)
        buf = io.BytesIO()
        base_preview.save(buf, format="PNG")
        byte_im = buf.getvalue()
        
        nome_arquivo = f"Placa_{nome.split()[0] if nome else 'INDICIADO'}.png"
        
        st.download_button(
            label="💾 BAIXAR IMAGEM PRONTA",
            data=byte_im,
            file_name=nome_arquivo,
            mime="image/png",
            use_container_width=True
        )

else:
    # Reseta estado se não tiver imagem carregada
    reset_state()
