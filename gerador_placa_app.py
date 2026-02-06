import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="SIV-PC Web", layout="centered", page_icon="👮")

# --- CSS (Visual Limpo e Botões Grandes) ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    /* Centraliza Imagens */
    div[data-testid="stImage"] {
        display: flex;
        justify_content: center;
    }
    img {
        border: 2px solid #ccc;
        border-radius: 8px;
    }

    /* Botões de Controle (Setas) */
    div.stButton > button {
        width: 100%;
        height: 60px;
        font-size: 30px;
        font-weight: bold;
        border-radius: 10px;
        margin: 0px;
        line-height: 1;
    }
    
    /* Botões de Zoom e Download (Texto Menor) */
    div[data-testid="column"] > div > div > div > div > .stButton > button p {
        font-size: 18px;
    }
    </style>
""", unsafe_allow_html=True)

# --- RECURSOS ---
@st.cache_resource
def load_resources():
    try:
        moldura = Image.open("moldura.png").convert("RGBA")
    except:
        st.error("ERRO: 'moldura.png' ausente no GitHub.")
        return None
    return moldura

MOLDURA_FULL = load_resources()

# Parâmetros Fixos
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

# --- ESTADO INICIAL ---
if 'zoom' not in st.session_state: st.session_state.zoom = 1.0
if 'off_x' not in st.session_state: st.session_state.off_x = 0
if 'off_y' not in st.session_state: st.session_state.off_y = 0

# --- FUNÇÕES GRÁFICAS ---
def get_preview_scale(img_pil):
    # Preview de 300px (Balanço ideal entre qualidade e velocidade)
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

def gerar_recorte(img_pil, tam_final_crop, escala_proxy=1.0):
    """
    Recorta a imagem baseado no Zoom e Offset atuais.
    Lógica: 'Mover Imagem' (Offset positivo = Imagem vai para a direita)
    """
    zoom = st.session_state.zoom
    
    # Ajusta o offset para a escala atual (se for proxy, reduz o movimento)
    move_x = (st.session_state.off_x * escala_proxy) / zoom
    move_y = (st.session_state.off_y * escala_proxy) / zoom
    
    w_img, h_img = img_pil.size
    
    # Centro da Janela de Corte
    # Se quero mover a imagem para a Direita (+X), a janela de corte tem que ir para a Esquerda (-X)
    cx = (w_img / 2) - move_x
    cy = (h_img / 2) - move_y
    
    # Tamanho da Janela de Corte
    lado_req = (tam_final_crop[0] * escala_proxy) / zoom
    
    x1, y1 = int(cx - lado_req/2), int(cy - lado_req/2)
    x2, y2 = int(cx + lado_req/2), int(cy + lado_req/2)
    
    # Canvas Branco (Viewport)
    view = Image.new("RGB", (int(x2-x1), int(y2-y1)), (255,255,255))
    
    # Intersecção com a imagem real
    src_x1, src_y1 = max(0, x1), max(0, y1)
    src_x2, src_y2 = min(w_img, x2), min(h_img, y2)
    
    if src_x2 > src_x1 and src_y2 > src_y1:
        crop = img_pil.crop((src_x1, src_y1, src_x2, src_y2))
        # Cola na posição correta do viewport
        dst_x = src_x1 - x1
        dst_y = src_y1 - y1
        view.paste(crop, (dst_x, dst_y))
        
    return view.resize(tam_final_crop, Image.LANCZOS)

def gerar_final_hd(img_orig, txts):
    try:
        # Gera o recorte em Full HD
        crop_hd = gerar_recorte(img_orig, TAM_FINAL_FULL, escala_proxy=1.0)
        
        base_hd = Image.new("RGBA", MOLDURA_FULL.size, "WHITE")
        base_hd.paste(crop_hd, POSICAO_FOTO_FULL)
        base_hd.paste(MOLDURA_FULL, (0,0), mask=MOLDURA_FULL)
        
        for k, v in txts.items():
            base_hd = desenhar_texto(base_hd, v.upper(), k, escala=1.0)
            
        buf = io.BytesIO(); base_hd.save(buf, format="PNG"); return buf.getvalue()
    except: return None

# --- UI PRINCIPAL ---
st.title("SIV-PC Web")

# 1. UPLOAD (Fixo no topo)
uploaded = st.file_uploader("1. Carregar Fotografia", type=['jpg','png','jpeg'])

if uploaded:
    img_orig = Image.open(uploaded).convert('RGB')
    
    # Prepara Versão Leve (Proxy) para o Preview ficar rápido
    f_escala = get_preview_scale(img_orig)
    w_p, h_p = int(img_orig.width * f_escala), int(img_orig.height * f_escala)
    img_proxy = img_orig.resize((w_p, h_p), Image.NEAREST)
    
    # Moldura Proxy
    moldura_p = MOLDURA_FULL.resize((int(MOLDURA_FULL.width * f_escala), int(MOLDURA_FULL.height * f_escala)), Image.NEAREST)
    pos_p = (int(POSICAO_FOTO_FULL[0]*f_escala), int(POSICAO_FOTO_FULL[1]*f_escala))
    tam_p = (int(TAM_FINAL_FULL[0]*f_escala), int(TAM_FINAL_FULL[1]*f_escala))

    # 2. DADOS DO INDICIADO
    with st.container():
        c1, c2, c3 = st.columns([1, 1, 1])
        sit = c1.text_input("Situação", "INDICIADO")
        nat = c2.text_input("Natureza")
        out = c3.text_input("Outros (BO/Data)")
        c4, c5 = st.columns([2, 1])
        nome = c4.text_input("Nome Completo")
        rg = c5.text_input("Documento (RG/CPF)")

    st.markdown("---")

    # ==========================================================
    # ÁREA "FLUIDA" (FRAGMENT)
    # Tudo aqui dentro atualiza rápido sem recarregar a página toda
    # ==========================================================
    @st.fragment
    def area_ajuste_fluida():
        
        # Callbacks Locais
        STEP = 50
        def mv_up(): st.session_state.off_y -= STEP
        def mv_down(): st.session_state.off_y += STEP
        def mv_left(): st.session_state.off_x -= STEP
        def mv_right(): st.session_state.off_x += STEP
        def z_in(): st.session_state.zoom += 0.1
        def z_out(): 
            if st.session_state.zoom > 0.2: st.session_state.zoom -= 0.1

        # 3. PREVIEW VISUAL
        try:
            crop_p = gerar_recorte(img_proxy, tam_p, escala_proxy=f_escala)
            base_p = Image.new("RGBA", moldura_p.size, "WHITE")
            base_p.paste(crop_p, pos_p)
            base_p.paste(moldura_p, (0,0), mask=moldura_p)
            
            # Texto no Preview (Opcional, pode comentar se quiser mais velocidade)
            txts = {"situacao": sit, "natureza": nat, "nome": nome, "documento": rg, "outras": out}
            for k, v in txts.items():
                base_p = desenhar_texto(base_p, v.upper(), k, escala=f_escala)
                
            st.image(base_p, width=300, caption="Pré-visualização")
        except Exception as e:
            st.error(f"Erro Preview: {e}")

        # 4. CONTROLES (JOYSTICK)
        st.write("")
        
        # Botão CIMA
        c_u1, c_u2, c_u3 = st.columns([1, 1, 1])
        with c_u2: st.button("⬆️", on_click=mv_up, use_container_width=True)

        # Botões ESQ | DIR
        c_m1, c_m2, c_m3 = st.columns([1, 1, 1])
        with c_m1: st.button("⬅️", on_click=mv_left, use_container_width=True)
        with c_m3: st.button("➡️", on_click=mv_right, use_container_width=True)

        # Botão BAIXO
        c_d1, c_d2, c_d3 = st.columns([1, 1, 1])
        with c_d2: st.button("⬇️", on_click=mv_down, use_container_width=True)

        # ZOOM
        st.write("")
        cz1, cz2 = st.columns(2)
        with cz1: st.button("➕ Zoom", on_click=z_in, use_container_width=True)
        with cz2: st.button("➖ Zoom", on_click=z_out, use_container_width=True)

    # Chama a área fluida
    area_ajuste_fluida()

    # 5. DOWNLOAD (Fora do fragment para garantir processamento limpo)
    st.markdown("---")
    
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
    # Reset estado se não tiver foto
    st.session_state.zoom = 1.0
    st.session_state.off_x = 0
    st.session_state.off_y = 0
