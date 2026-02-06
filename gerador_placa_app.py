import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Mobile", layout="centered", page_icon="👮")

# --- CSS AGRESSIVO (Mobile Compacto) ---
st.markdown("""
    <style>
    /* Remove margens inúteis do topo e laterais */
    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    
    /* Centraliza imagem e limita altura para caber na tela junto com botões */
    div[data-testid="stImage"] {
        display: flex;
        justify_content: center;
        margin-bottom: 0px;
    }
    img {
        border: 2px solid #333;
        border-radius: 5px;
        max-height: 35vh; /* Ocupa no máximo 35% da altura da tela */
        object-fit: contain;
    }

    /* ESTILO DOS BOTÕES (Quadrados e Compactos) */
    div.stButton > button {
        width: 100%;
        height: 45px;       /* Altura fixa menor */
        font-size: 20px;    /* Ícone legível */
        font-weight: bold;
        border-radius: 8px;
        margin: 0px;
        padding: 0px;
        line-height: 1;
        border: 1px solid #999;
        background-color: #f0f2f6;
    }
    
    /* Botão de Download (Destaque) */
    div.stDownloadButton > button {
        height: 50px;
        background-color: #ff4b4b;
        color: white;
    }

    /* Reduz espaçamento entre colunas */
    div[data-testid="column"] {
        padding: 0px 2px; /* Quase colado */
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
        return None
    return moldura

MOLDURA_FULL = load_resources()

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

# AJUSTE FINO (10 Pixels)
STEP = 10 

# --- FUNÇÕES GRÁFICAS ---
def get_preview_scale(img_pil):
    # Preview leve para celular (300px)
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

def gerar_recorte(img_pil, moldura_size, pos_foto, tam_foto, escala_proxy=1.0):
    zoom = st.session_state.zoom
    if zoom <= 0.01: zoom = 0.1
    
    # Offset ajustado para a escala e zoom
    off_x = (st.session_state.off_x * escala_proxy) / zoom
    off_y = (st.session_state.off_y * escala_proxy) / zoom
    
    w_img, h_img = img_pil.size
    cx, cy = (w_img / 2) - off_x, (h_img / 2) - off_y
    lado_req = (tam_foto[0] * escala_proxy) / zoom
    
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
    try:
        crop_hd = gerar_recorte(img_orig, MOLDURA_FULL.size, POSICAO_FOTO_FULL, TAM_FINAL_FULL, escala_proxy=1.0)
        base_hd = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
        base_hd.paste(crop_hd, POSICAO_FOTO_FULL)
        base_hd.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
        for k, v in txts.items():
            base_hd = desenhar_texto(base_hd, v.upper(), k, escala=1.0)
        buf = io.BytesIO(); base_hd.save(buf, format="PNG"); return buf.getvalue()
    except: return None

# --- UI PRINCIPAL ---
st.title("SIV-PC Mobile")

uploaded = st.file_uploader("1. Carregar Foto", type=['jpg','png','jpeg'])

if uploaded:
    img_orig = Image.open(uploaded).convert('RGB')
    
    # Proxy
    f_escala = get_preview_scale(img_orig)
    w_p, h_p = int(img_orig.width * f_escala), int(img_orig.height * f_escala)
    img_proxy = img_orig.resize((w_p, h_p), Image.NEAREST)
    moldura_p = MOLDURA_FULL.resize((int(MOLDURA_FULL.width * f_escala), int(MOLDURA_FULL.height * f_escala)), Image.NEAREST)
    pos_p = (int(POSICAO_FOTO_FULL[0]*f_escala), int(POSICAO_FOTO_FULL[1]*f_escala))
    tam_p = (int(TAM_FINAL_FULL[0]*f_escala), int(TAM_FINAL_FULL[1]*f_escala))

    # DADOS (Escondidos num Expander para limpar a tela inicial)
    with st.expander("📝 Preencher Dados (Clique para abrir)", expanded=False):
        sit = st.text_input("Situação", "INDICIADO")
        nat = st.text_input("Natureza")
        nome = st.text_input("Nome")
        rg = st.text_input("RG/CPF")
        out = st.text_input("Outros")

    # ÁREA FLUIDA (IMAGEM + BOTÕES JUNTOS)
    @st.fragment
    def controle_compacto():
        # Callbacks
        def mv_up(): st.session_state.off_y -= STEP
        def mv_down(): st.session_state.off_y += STEP
        def mv_left(): st.session_state.off_x -= STEP
        def mv_right(): st.session_state.off_x += STEP
        def z_in(): st.session_state.zoom += 0.1
        def z_out(): 
            if st.session_state.zoom > 0.2: st.session_state.zoom -= 0.1

        # 1. Preview (No topo da área de controle)
        try:
            crop_p = gerar_recorte(img_proxy, tam_p, escala_proxy=f_escala)
            base_p = Image.new("RGBA", moldura_p.size, "WHITE")
            base_p.paste(crop_p, pos_p)
            base_p.paste(moldura_p, (0,0), mask=moldura_p)
            # Sem texto no preview para ser ultra rápido
            st.image(base_p, caption="Ajuste Fino (Preview)")
        except: pass

        # 2. Painel de Controle (Grade 3x3 Compacta)
        # Layout inteligente: 
        # [ Zoom - ] [  CIMA  ] [ Zoom + ]
        # [   ESQ  ] [ BAIXO  ] [  DIR   ]
        
        c1, c2, c3 = st.columns([1, 1, 1], gap="small")
        
        with c1:
            st.button("➖", on_click=z_out, use_container_width=True, help="Diminuir Zoom")
            st.button("⬅️", on_click=mv_left, use_container_width=True)
            
        with c2:
            st.button("⬆️", on_click=mv_up, use_container_width=True)
            st.button("⬇️", on_click=mv_down, use_container_width=True)
            
        with c3:
            st.button("➕", on_click=z_in, use_container_width=True, help="Aumentar Zoom")
            st.button("➡️", on_click=mv_right, use_container_width=True)

    controle_compacto()

    # DOWNLOAD (Fixo no rodapé)
    st.write("")
    txts_final = {"situacao": sit, "natureza": nat, "nome": nome, "documento": rg, "outras": out}
    hd_data = gerar_final_hd(img_orig, txts_final)
    
    if hd_data:
        st.download_button(
            label="💾 BAIXAR FOTO FINAL",
            data=hd_data,
            file_name=f"Placa_{nome.split()[0] if nome else 'PC'}.png",
            mime="image/png",
            type="primary",
            use_container_width=True
        )

else:
    st.session_state.zoom = 1.0
    st.session_state.off_x = 0
    st.session_state.off_y = 0
