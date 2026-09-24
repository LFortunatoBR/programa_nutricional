import streamlit as st
import pandas as pd
import requests
import json

# ==========================================
# 1. CONFIGURAÇÃO INICIAL DA PÁGINA
# ==========================================
st.set_page_config(page_title="Calculadora Metabólica Avançada", layout="wide")

# Inicializa o banco de dados do cardápio do usuário na memória
if "cardapio" not in st.session_state:
    st.session_state["cardapio"] = pd.DataFrame(columns=[
        "Alimento", "Quantidade (g)", "Kcal", "Carboidratos (g)", "Proteínas (g)", "Gorduras (g)"
    ])

# ==========================================
# 2. SISTEMA DE AUTENTICAÇÃO
# ==========================================
def verificar_senha():
    """Valida a senha usando st.secrets e mantem o estado da sessão ativo"""
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.markdown("### Acesso Restrito: Sistema Nutricional")
        senha_digitada = st.text_input("Digite a senha de acesso:", type="password")
        
        if st.button("Entrar"):
            if senha_digitada == st.secrets.get("app_password"):
                st.session_state["autenticado"] = True
                st.rerun() 
            else:
                st.error("Senha incorreta. Tente novamente.")
        return False
    
    return True

if not verificar_senha():
    st.stop()

# ==========================================
# 3. FUNÇÕES DE DADOS E INTEGRAÇÕES
# ==========================================
def inferir_restricoes_sangue(nome):
    nome_lower = str(nome).lower()
    evitar = set()
    if any(x in nome_lower for x in ["beef", "carne", "vaca", "porco", "pork", "bacon", "tomate", "tomato", "batata", "potato"]):
        evitar.add("A")
    if any(x in nome_lower for x in ["frango", "chicken", "porco", "pork", "bacon", "milho", "corn", "tomate", "tomato", "amendoim", "peanut"]):
        evitar.add("B")
    if any(x in nome_lower for x in ["trigo", "wheat", "milho", "corn", "leite", "milk", "queijo", "cheese", "porco", "pork"]):
        evitar.add("O")
    if any(x in nome_lower for x in ["frango", "chicken", "milho", "corn", "beef", "vaca"]):
        evitar.add("AB")
    return list(evitar)

def converter_para_float(valor):
    """Converte valores como 'Tr' (Traços), 'NA' ou strings vazias do JSON para 0.0"""
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        valor_limpo = valor.strip().upper()
        if valor_limpo in ["TR", "NA", "", "*"]:
            return 0.0
        try:
            return float(valor_limpo.replace(",", "."))
        except ValueError:
            return 0.0
    return 0.0

@st.cache_data(ttl=86400)
def carregar_taco():
    """Busca e padroniza a Tabela TACO Brasileira a partir do arquivo local"""
    try:
        with open("TACO.json", "r", encoding="utf-8") as f:
            dados = json.load(f)
            
        alimentos_taco = []
        
        for item in dados:
            descricao = item.get("description", "")
            if not descricao:
                continue
            
            kcal = converter_para_float(item.get("energy_kcal", 0))
            prot = converter_para_float(item.get("protein_g", 0))
            carb = converter_para_float(item.get("carbohydrate_g", 0))
            gord = converter_para_float(item.get("lipid_g", 0))
            categoria = item.get("category", "TACO (Brasil)")
            
            alimentos_taco.append({
                "Alimento": descricao,
                "Categoria": categoria,
                "Kcal_100g": kcal,
                "Prot_100g": prot,
                "Carb_100g": carb,
                "Gord_100g": gord,
                "Evitar_Tipo_Sangue": inferir_restricoes_sangue(descricao)
            })
        return pd.DataFrame(alimentos_taco)
    except Exception as e:
        st.error(f"Falha ao carregar a tabela TACO local: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def buscar_alimento_usda(query, max_resultados=5):
    chave_api = st.secrets.get("usda_key", None)
    
    if not chave_api:
        st.warning("⚠️ Chave USDA não configurada no secrets.toml. A busca americana não funcionará.")
        return pd.DataFrame()

    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    parametros = {
        "api_key": chave_api,
        "query": query,
        "dataType": ["Foundation", "SR Legacy"],
        "pageSize": max_resultados
    }
    
    resposta = requests.get(url, params=parametros)
    if resposta.status_code != 200:
        st.error("Erro ao conectar com a base de dados do USDA.")
        return pd.DataFrame()
        
    dados = resposta.json()
    alimentos_processados = []
    
    NUTRIENTES_ALVO = {
        1008: "Kcal_100g",
        1003: "Prot_100g",
        1005: "Carb_100g",
        1004: "Gord_100g"
    }
    
    for item in dados.get('foods', []):
        alimento_dict = {
            "Alimento": item.get('description'),
            "Categoria": item.get('foodCategory', 'USDA (EUA)'),
            "Kcal_100g": 0.0,
            "Prot_100g": 0.0,
            "Carb_100g": 0.0,
            "Gord_100g": 0.0,
            "Evitar_Tipo_Sangue": inferir_restricoes_sangue(item.get('description'))
        }
        
        for nutriente in item.get('foodNutrients', []):
            id_nutriente = nutriente.get('nutrientId')
            if id_nutriente in NUTRIENTES_ALVO:
                nome_coluna = NUTRIENTES_ALVO[id_nutriente]
                alimento_dict[nome_coluna] = round(nutriente.get('value', 0.0), 1)
                
        alimentos_processados.append(alimento_dict)
        
    return pd.DataFrame(alimentos_processados)

# ==========================================
# 4. MOTOR METABÓLICO E DE MACROS
# ==========================================
def calcular_tmb(peso, altura, idade, sexo):
    if sexo == "Masculino":
        return (10 * peso) + (6.25 * altura) - (5 * idade) + 5
    else:
        return (10 * peso) + (6.25 * altura) - (5 * idade) - 161

def aplicar_objetivo(tdee, objetivo):
    if objetivo == "Emagrecimento":
        return tdee * 0.80
    elif objetivo == "Ganho de Massa Muscular":
        return tdee * 1.15
    else: 
        return tdee 

def distribuir_macros(calorias, dieta, peso, objetivo):
    if dieta == "Carnívora":
        carb_pct, prot_pct, gord_pct = 0.0, 0.35, 0.65
    elif dieta == "Cetogênica":
        carb_pct, prot_pct, gord_pct = 0.05, 0.25, 0.70
    elif dieta == "Restrição Severa (Low-Carb)":
        carb_pct, prot_pct, gord_pct = 0.15, 0.40, 0.45
    else: 
        if "Recomposição" in objetivo:
            prot_g = peso * 2.5
            prot_kcal = prot_g * 4
            calorias_restantes = calorias - prot_kcal
            carb_pct = max(0, (calorias_restantes * 0.40) / calorias)
            gord_pct = max(0, (calorias_restantes * 0.60) / calorias)
            prot_pct = prot_kcal / calorias
        else:
            carb_pct, prot_pct, gord_pct = 0.40, 0.30, 0.30

    carb_g = (calorias * carb_pct) / 4
    prot_g = (calorias * prot_pct) / 4
    gord_g = (calorias * gord_pct) / 9
    
    return round(carb_g), round(prot_g), round(gord_g)

# ==========================================
# 5. INTERFACE DO USUÁRIO (STREAMLIT)
# ==========================================
st.title("Sistema de Nutrição de Alta Precisão (USDA + TACO)")

df_master = carregar_taco()

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Parâmetros Individuais")
    idade = st.number_input("Idade", min_value=15, max_value=100, value=43)
    sexo = st.selectbox("Sexo", ["Masculino", "Feminino"])
    peso = st.number_input("Peso (kg)", min_value=40.0, max_value=200.0, value=89.0)
    altura = st.number_input("Altura (cm)", min_value=140, max_value=220, value=183)
    
    atividade_opcoes = {
        "Sedentário (Trabalho de escritório)": 1.2,
        "Levemente Ativo (1-3 dias/sem)": 1.375,
        "Moderadamente Ativo (3-5 dias/sem)": 1.55,
        "Muito Ativo (Treinos intensos)": 1.725,
        "Extremamente Ativo (Atleta)": 1.9
    }
    atividade_nome = st.selectbox("Nível de Atividade Física", list(atividade_opcoes.keys()), index=2)
    fator_atividade = atividade_opcoes[atividade_nome]
    
    tipo_sanguineo = st.selectbox("Tipo Sanguíneo", ["A", "B", "AB", "O"])
    
    st.header("Metas e Protocolo")
    objetivo = st.selectbox("Objetivo Clínico/Físico", [
        "Recomposição Corporal (Emagrecer e Ganhar Massa)",
        "Emagrecimento", 
        "Ganho de Massa Muscular" 
    ])
    
    dieta = st.selectbox("Estratégia Alimentar", [
        "Cetogênica",
        "Carnívora",
        "Restrição Severa (Low-Carb)",
        "Moderada"
    ])
    
    st.markdown("---")
    st.header("Adicionar Alimentos (USDA)")
    termo_busca = st.text_input("Busca Internacional (Em inglês, ex: 'chicken breast', 'salmon'):")
    
    if termo_busca:
        with st.spinner("Buscando no banco de dados do governo americano..."):
            df_usda = buscar_alimento_usda(termo_busca)
            if not df_usda.empty:
                st.success(f"Encontrados {len(df_usda)} resultados!")
                df_master = pd.concat([df_master, df_usda], ignore_index=True)
            else:
                st.info("Nenhum dado retornado da USDA.")

with col2:
    st.header("Diagnóstico Metabólico e Macros")
    
    tmb = calcular_tmb(peso, altura, idade, sexo)
    tdee = tmb * fator_atividade
    calorias_alvo = aplicar_objetivo(tdee, objetivo)
    carb_g, prot_g, gord_g = distribuir_macros(calorias_alvo, dieta, peso, objetivo)
    
    st.markdown(f"**TMB (Basal):** {tmb:.0f} kcal | **Gasto Total:** {tdee:.0f} kcal")
    st.markdown(f"### Meta Diária: {calorias_alvo:.0f} kcal")
    
    col_c, col_p, col_g = st.columns(3)
    col_c.metric("Carboidratos", f"{carb_g}g", f"{(carb_g*4/calorias_alvo)*100:.0f}% kcal")
    col_p.metric("Proteínas", f"{prot_g}g", f"{(prot_g*4/calorias_alvo)*100:.0f}% kcal")
    col_g.metric("Gorduras", f"{gord_g}g", f"{(gord_g*9/calorias_alvo)*100:.0f}% kcal")
    
    st.markdown("---")
    st.header(f"Banco de Alimentos Compatíveis (Base: TACO + USDA)")
    
    if not df_master.empty:
        df_filtrado = df_master.copy()
        
        # Filtros e Limpezas
        df_filtrado = df_filtrado[~df_filtrado['Evitar_Tipo_Sangue'].apply(lambda x: tipo_sanguineo in x if isinstance(x, list) else False)]
        
        if dieta == "Carnívora":
            df_filtrado = df_filtrado[df_filtrado['Carb_100g'] <= 2.0]
        elif dieta == "Cetogênica":
            df_filtrado = df_filtrado[df_filtrado['Carb_100g'] <= 8.0]
            
        df_filtrado = df_filtrado[(df_filtrado['Kcal_100g'] > 0)].sort_values(by='Prot_100g', ascending=False)
        
        st.write(f"Alimentos liberados para **Tipo {tipo_sanguineo}** na dieta **{dieta}**:")
        
        df_view = df_filtrado.drop(columns=['Evitar_Tipo_Sangue']).head(150) 
        st.dataframe(
            df_view.style.format({
                "Kcal_100g": "{:.1f}",
                "Prot_100g": "{:.1f}",
                "Carb_100g": "{:.1f}",
                "Gord_100g": "{:.1f}"
            }),
            use_container_width=True,
            height=300
        )
        
        # ==========================================
        # 6. MONTADOR DE CARDÁPIO E CONFRONTO
        # ==========================================
        st.markdown("---")
        st.header("🍽️ Montador de Cardápio")
        
        with st.form("form_add_alimento"):
            col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
            
            # Limita as opções ao que passou pelo filtro
            opcoes_alimentos = df_filtrado['Alimento'].tolist()
            
            with col_f1:
                alimento_selecionado = st.selectbox("Selecione o Alimento:", opcoes_alimentos)
            with col_f2:
                quantidade = st.number_input("Peso (gramas):", min_value=1.0, max_value=2000.0, value=100.0, step=10.0)
            with col_f3:
                st.markdown("<br>", unsafe_allow_html=True)
                adicionar = st.form_submit_button("➕ Adicionar")
                
            if adicionar and alimento_selecionado:
                linha = df_filtrado[df_filtrado['Alimento'] == alimento_selecionado].iloc[0]
                fator = quantidade / 100.0
                
                novo_item = pd.DataFrame([{
                    "Alimento": alimento_selecionado,
                    "Quantidade (g)": quantidade,
                    "Kcal": linha["Kcal_100g"] * fator,
                    "Carboidratos (g)": linha["Carb_100g"] * fator,
                    "Proteínas (g)": linha["Prot_100g"] * fator,
                    "Gorduras (g)": linha["Gord_100g"] * fator
                }])
                
                st.session_state["cardapio"] = pd.concat([st.session_state["cardapio"], novo_item], ignore_index=True)
                st.rerun() # Atualiza os visuais imediatamente
                
        if not st.session_state["cardapio"].empty:
            st.subheader("📋 Resumo do seu Cardápio")
            st.dataframe(
                st.session_state["cardapio"].style.format({
                    "Quantidade (g)": "{:.0f}",
                    "Kcal": "{:.1f}",
                    "Carboidratos (g)": "{:.1f}",
                    "Proteínas (g)": "{:.1f}",
                    "Gorduras (g)": "{:.1f}"
                }),
                use_container_width=True
            )
            
            if st.button("🗑️ Limpar Cardápio"):
                st.session_state["cardapio"] = pd.DataFrame(columns=[
                    "Alimento", "Quantidade (g)", "Kcal", "Carboidratos (g)", "Proteínas (g)", "Gorduras (g)"
                ])
                st.rerun()
                
            # Cálculos de Confronto
            total_kcal = st.session_state["cardapio"]["Kcal"].sum()
            total_carb = st.session_state["cardapio"]["Carboidratos (g)"].sum()
            total_prot = st.session_state["cardapio"]["Proteínas (g)"].sum()
            total_gord = st.session_state["cardapio"]["Gorduras (g)"].sum()
            
            st.markdown("### ⚖️ Confronto com a Meta Diária")
            
            def saldo_texto(total, alvo, unidade):
                diff = alvo - total
                if diff > 0:
                    return f"Faltam {diff:.0f} {unidade}"
                elif diff < 0:
                    return f"Passou {abs(diff):.0f} {unidade}"
                return "Meta cravada!"
                
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            col_r1.metric("Total Calorias", f"{total_kcal:.0f} kcal", saldo_texto(total_kcal, calorias_alvo, "kcal"), delta_color="off")
            col_r2.metric("Total Carboidratos", f"{total_carb:.0f} g", saldo_texto(total_carb, carb_g, "g"), delta_color="off")
            col_r3.metric("Total Proteínas", f"{total_prot:.0f} g", saldo_texto(total_prot, prot_g, "g"), delta_color="off")
            col_r4.metric("Total Gorduras", f"{total_gord:.0f} g", saldo_texto(total_gord, gord_g, "g"), delta_color="off")
            
            # Gráficos de barra nativos do Streamlit
            st.caption("Progresso de Preenchimento da Meta Diária")
            st.progress(min(total_kcal / calorias_alvo, 1.0) if calorias_alvo > 0 else 0, text="Energia (Kcal)")
            st.progress(min(total_prot / prot_g, 1.0) if prot_g > 0 else 0, text="Proteínas")
            st.progress(min(total_carb / carb_g, 1.0) if carb_g > 0 else 0, text="Carboidratos")
            st.progress(min(total_gord / gord_g, 1.0) if gord_g > 0 else 0, text="Gorduras")

    else:
        st.warning("Banco de dados indisponível no momento.")
