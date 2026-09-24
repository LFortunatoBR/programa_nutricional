import streamlit as st
import pandas as pd
import json
import requests

# A configuração da página deve ser obrigatoriamente o primeiro comando Streamlit
st.set_page_config(page_title="Calculadora Metabólica Avançada", layout="wide")

# ==========================================
# SISTEMA DE AUTENTICAÇÃO
# ==========================================
def verificar_senha():
    """Valida a senha usando st.secrets e mantem o estado da sessão ativo"""
    # Inicializa o estado de autenticação se ainda não existir
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    # Se não estiver autenticado, mostra a tela de login
    if not st.session_state["autenticado"]:
        st.markdown("### Acesso Restrito: Sistema Nutricional")
        senha_digitada = st.text_input("Digite a senha de acesso:", type="password")
        
        if st.button("Entrar"):
            # Compara com a senha salva no secrets.toml
            if senha_digitada == st.secrets.get("app_password"):
                st.session_state["autenticado"] = True
                st.rerun() # Recarrega a página para liberar a interface principal
            else:
                st.error("Senha incorreta. Tente novamente.")
        return False
    
    return True

# Trava a execução do restante do código se a função retornar False
if not verificar_senha():
    st.stop()

# ==========================================
# 1. FUNÇÕES DE DADOS E INTEGRAÇÕES DE API
# ==========================================

def inferir_restricoes_sangue(nome):
    """
    Heurística para aplicar as regras de D'Adamo em alimentos carregados dinamicamente
    das APIs (TACO e USDA), já que as bases de dados nutricionais não possuem essa informação.
    """
    nome_lower = str(nome).lower()
    evitar = set()
    
    # Regras do Tipo A (Evitar carne vermelha, porco, tomate, etc)
    if any(x in nome_lower for x in ["beef", "carne", "vaca", "porco", "pork", "bacon", "tomate", "tomato", "batata", "potato"]):
        evitar.add("A")
    
    # Regras do Tipo B (Evitar frango, porco, milho, tomate, amendoim)
    if any(x in nome_lower for x in ["frango", "chicken", "porco", "pork", "bacon", "milho", "corn", "tomate", "tomato", "amendoim", "peanut"]):
        evitar.add("B")
        
    # Regras do Tipo O (Evitar trigo, milho, laticínios, porco)
    if any(x in nome_lower for x in ["trigo", "wheat", "milho", "corn", "leite", "milk", "queijo", "cheese", "porco", "pork"]):
        evitar.add("O")
        
    # Regras do Tipo AB (Evitar frango, milho, carne bovina)
    if any(x in nome_lower for x in ["frango", "chicken", "milho", "corn", "beef", "vaca"]):
        evitar.add("AB")
        
    return list(evitar)

@st.cache_data(ttl=86400)
def carregar_taco():
    """Busca e padroniza a Tabela TACO Brasileira a partir do repositório oficial no GitHub"""
    url_taco = "https://raw.githubusercontent.com/taco-api/taco-api/master/data/taco.json"
    try:
        resposta = requests.get(url_taco)
        if resposta.status_code == 200:
            dados = resposta.json()
            alimentos_taco = []
            
            for item in dados:
                descricao = item.get("description", "")
                if not descricao:
                    continue
                
                # Extração segura de dicionários aninhados da TACO
                energia = item.get("energy", {})
                kcal = float(energia.get("kcal", 0) if energia.get("kcal") else 0)
                
                prot_dict = item.get("protein", {})
                prot = float(prot_dict.get("qty", 0) if isinstance(prot_dict, dict) and prot_dict.get("qty") else 0)
                
                carb_dict = item.get("carbohydrate", {})
                carb = float(carb_dict.get("qty", 0) if isinstance(carb_dict, dict) and carb_dict.get("qty") else 0)
                
                gord_dict = item.get("lipid", {})
                gord = float(gord_dict.get("qty", 0) if isinstance(gord_dict, dict) and gord_dict.get("qty") else 0)
                
                alimentos_taco.append({
                    "Alimento": descricao,
                    "Categoria": "TACO (Brasil)",
                    "Kcal_100g": kcal,
                    "Prot_100g": prot,
                    "Carb_100g": carb,
                    "Gord_100g": gord,
                    "Evitar_Tipo_Sangue": inferir_restricoes_sangue(descricao)
                })
            return pd.DataFrame(alimentos_taco)
    except Exception as e:
        st.error(f"Falha ao carregar a tabela TACO: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=86400)
def buscar_alimento_usda(query, max_resultados=5):
    """Consulta a API do USDA (FoodData Central) focando em ingredientes in natura"""
    # Recupera a chave de forma segura
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
# 2. MOTOR METABÓLICO E DE MACROS
# ==========================================

def calcular_tmb(peso, altura, idade, sexo):
    """Mifflin-St Jeor"""
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
        if objetivo == "Recomposição Corporal (Emagrecer e Ganhar Massa)":
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
# 3. INTERFACE DO USUÁRIO (STREAMLIT)
# ==========================================

st.title("Sistema de Nutrição de Alta Precisão (USDA + TACO)")

# Inicializa o dataframe master (TACO por padrão)
df_master = carregar_taco()

# Cria colunas de layout
col1, col2 = st.columns([1, 2])

with col1:
    st.header("Parâmetros Individuais")
    idade = st.number_input("Idade", min_value=15, max_value=100, value=30)
    sexo = st.selectbox("Sexo", ["Masculino", "Feminino"])
    peso = st.number_input("Peso (kg)", min_value=40.0, max_value=200.0, value=75.0)
    altura = st.number_input("Altura (cm)", min_value=140, max_value=220, value=170)
    
    atividade_opcoes = {
        "Sedentário (Trabalho de escritório)": 1.2,
        "Levemente Ativo (1-3 dias/sem)": 1.375,
        "Moderadamente Ativo (3-5 dias/sem)": 1.55,
        "Muito Ativo (Treinos intensos)": 1.725,
        "Extremamente Ativo (Atleta)": 1.9
    }
    atividade_nome = st.selectbox("Nível de Atividade Física", list(atividade_opcoes.keys()), index=2)
    fator_atividade = atividade_opcoes[atividade_nome]
    
    tipo_sanguineo = st.selectbox("Tipo Sanguíneo", ["O", "A", "B", "AB"])
    
    st.header("Metas e Protocolo")
    objetivo = st.selectbox("Objetivo Clínico/Físico", [
        "Emagrecimento", 
        "Ganho de Massa Muscular", 
        "Recomposição Corporal (Emagrecer e Ganhar Massa)"
    ])
    
    dieta = st.selectbox("Estratégia Alimentar", [
        "Moderada",
        "Restrição Severa (Low-Carb)",
        "Cetogênica",
        "Carnívora"
    ])
    
    st.markdown("---")
    st.header("Adicionar Alimentos (USDA)")
    termo_busca = st.text_input("Busca Internacional (Em inglês, ex: 'chicken breast', 'salmon'):")
    
    if termo_busca:
        with st.spinner("Buscando no banco de dados do governo americano..."):
            df_usda = buscar_alimento_usda(termo_busca)
            if not df_usda.empty:
                st.success(f"Encontrados {len(df_usda)} resultados!")
                # Mescla a base da TACO com o resultado da busca do USDA na memória
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
    
    # Processamento de Filtros Baseado nas Escolhas do Usuário
    if not df_master.empty:
        df_filtrado = df_master.copy()
        
        # 1. Filtro Tipo Sanguíneo
        df_filtrado = df_filtrado[~df_filtrado['Evitar_Tipo_Sangue'].apply(lambda x: tipo_sanguineo in x if isinstance(x, list) else False)]
        
        # 2. Filtro Estrutura da Dieta
        if dieta == "Carnívora":
            # Heurística rigorosa: apenas alimentos sem carboidratos ou com zero/traços
            df_filtrado = df_filtrado[df_filtrado['Carb_100g'] <= 2.0]
        elif dieta == "Cetogênica":
            # Limita opções ricas em carboidratos (ex: acima de 8g a cada 100g)
            df_filtrado = df_filtrado[df_filtrado['Carb_100g'] <= 8.0]
            
        # Remover itens sem dados vitais e ordena por maior densidade proteica e limpeza da lista
        df_filtrado = df_filtrado[(df_filtrado['Kcal_100g'] > 0)].sort_values(by='Prot_100g', ascending=False)
        
        st.write(f"Alimentos liberados para **Tipo {tipo_sanguineo}** na dieta **{dieta}**:")
        
        # Apresentação Limpa
        df_view = df_filtrado.drop(columns=['Evitar_Tipo_Sangue']).head(150) # Exibe top 150 para evitar travamentos
        st.dataframe(
            df_view.style.format({
                "Kcal_100g": "{:.1f}",
                "Prot_100g": "{:.1f}",
                "Carb_100g": "{:.1f}",
                "Gord_100g": "{:.1f}"
            }),
            use_container_width=True,
            height=400
        )
    else:
        st.warning("Banco de dados indisponível no momento.")
