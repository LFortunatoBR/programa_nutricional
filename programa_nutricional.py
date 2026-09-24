import streamlit as st
import pandas as pd
import requests
import json
import os

# ==========================================
# 1. CONFIGURAÇÃO INICIAL DA PÁGINA
# ==========================================
st.set_page_config(page_title="Calculadora Metabólica Avançada", layout="wide")

if "cardapio" not in st.session_state:
    st.session_state["cardapio"] = pd.DataFrame(columns=[
        "Alimento", "Quantidade (g)", "Kcal", "Carboidratos (g)", "Proteínas (g)", "Gorduras (g)"
    ])

# ==========================================
# 2. SISTEMA DE AUTENTICAÇÃO
# ==========================================
def verificar_senha():
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
    if any(x in nome_lower for x in ["beef", "carne", "vaca", "porco", "pork", "bacon", "tomate", "tomato", "batata", "potato", "acém", "picanha", "patinho"]):
        evitar.add("A")
    if any(x in nome_lower for x in ["frango", "chicken", "porco", "pork", "bacon", "milho", "corn", "tomate", "tomato", "amendoim", "peanut"]):
        evitar.add("B")
    if any(x in nome_lower for x in ["trigo", "wheat", "milho", "corn", "leite", "milk", "queijo", "cheese", "porco", "pork"]):
        evitar.add("O")
    if any(x in nome_lower for x in ["frango", "chicken", "milho", "corn", "beef", "vaca"]):
        evitar.add("AB")
    return list(evitar)

def converter_para_float(valor):
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

def salvar_novo_alimento(nome, categoria, kcal, prot, carb, gord):
    """Abre o TACO.json, anexa o novo alimento e salva permanentemente."""
    try:
        if not os.path.exists("TACO.json"):
            dados = []
        else:
            with open("TACO.json", "r", encoding="utf-8") as f:
                dados = json.load(f)
        
        # Cria a estrutura exata exigida pelo seu TACO.json atual
        novo_id = max([item.get("id", 0) for item in dados]) + 1 if dados else 1
        
        novo_item = {
            "id": novo_id,
            "description": nome,
            "category": categoria,
            "humidity_percents": "NA",
            "energy_kcal": kcal,
            "energy_kj": kcal * 4.184, # Conversão básica
            "protein_g": prot,
            "lipid_g": gord,
            "cholesterol_mg": "NA",
            "carbohydrate_g": carb,
            "fiber_g": "NA",
            "ashes_g": "NA",
            "calcium_mg": "NA",
            "magnesium_mg": "NA",
            "manganese_mg": "NA",
            "phosphorus_mg": "NA",
            "iron_mg": "NA",
            "sodium_mg": "NA",
            "potassium_mg": "NA",
            "copper_mg": "NA",
            "zinc_mg": "NA",
            "retinol_mcg": "NA",
            "re_mcg": "NA",
            "rae_mcg": "NA",
            "thiamine_mg": "NA",
            "riboflavin_mg": "NA",
            "pyridoxine_mg": "NA",
            "niacin_mg": "NA",
            "vitaminC_mg": "NA",
            "saturated_g": "NA",
            "monounsaturated_g": "NA",
            "polyunsaturated_g": "NA",
            "12:0_g": "NA",
            "14:0_g": "NA",
            "16:0_g": "NA",
            "18:0_g": "NA",
            "20:0_g": "NA",
            "22:0_g": "NA",
            "24:0_g": "NA",
            "14:1_g": "NA",
            "16:1_g": "NA",
            "18:1_g": "NA",
            "20:1_g": "NA",
            "18:2 n-6_g": "NA",
            "18:3 n-3_g": "NA",
            "20:4_g": "NA",
            "20:5_g": "NA",
            "22:5_g": "NA",
            "22:6_g": "NA",
            "18:1t_g": "NA",
            "18:2t_g": "NA",
            "tryptophan_g": "NA",
            "threonine_g": "NA",
            "isoleucine_g": "NA",
            "leucine_g": "NA",
            "lysine_g": "NA",
            "methionine_g": "NA",
            "cystine_g": "NA",
            "phenylalanine_g": "NA",
            "tyrosine_g": "NA",
            "valine_g": "NA",
            "arginine_g": "NA",
            "histidine_g": "NA",
            "alanine_g": "NA",
            "aspartic_g": "NA",
            "glutamic_g": "NA",
            "glycine_g": "NA",
            "proline_g": "NA",
            "serine_g": "NA"
        }
        
        dados.append(novo_item)
        
        with open("TACO.json", "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            
        # Força o Streamlit a ler o arquivo novamente apagando o cache antigo
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar arquivo: {e}")
        return False

# ==========================================
# 4. MOTOR METABÓLICO
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
# 5. INTERFACE DO USUÁRIO
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
    
    with st.expander("🛠️ Cadastrar Novo Alimento Local"):
        with st.form("form_cadastrar_alimento"):
            st.info("Os valores devem ser baseados em 100g do produto.")
            novo_nome = st.text_input("Nome do Alimento (Ex: Acém, cozido):")
            nova_cat = st.selectbox("Categoria:", ["Carnes e derivados", "Pescados e frutos do mar", "Leite e derivados", "Verduras, hortaliças e derivados", "Frutas e derivados", "Outros"])
            n_kcal = st.number_input("Calorias (kcal):", min_value=0.0, value=212.0)
            n_prot = st.number_input("Proteínas (g):", min_value=0.0, value=26.7)
            n_carb = st.number_input("Carboidratos (g):", min_value=0.0, value=0.0)
            n_gord = st.number_input("Gorduras (g):", min_value=0.0, value=10.9)
            
            if st.form_submit_button("Salvar no Banco de Dados"):
                if novo_nome:
                    if salvar_novo_alimento(novo_nome, nova_cat, n_kcal, n_prot, n_carb, n_gord):
                        st.success(f"'{novo_nome}' salvo com sucesso! O sistema foi atualizado.")
                        st.rerun()
                else:
                    st.error("O nome do alimento é obrigatório.")

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
        
        st.markdown("---")
        st.header("🍽️ Montador de Cardápio Diário")
        
        with st.form("form_add_alimento"):
            col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
            opcoes_alimentos = df_filtrado['Alimento'].tolist()
            
            with col_f1:
                alimento_selecionado = st.selectbox("Selecione o Alimento:", opcoes_alimentos)
            with col_f2:
                quantidade = st.number_input("Peso (g):", min_value=1.0, max_value=2000.0, value=100.0, step=10.0)
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
                st.rerun()
                
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
                
            total_kcal = st.session_state["cardapio"]["Kcal"].sum()
            total_carb = st.session_state["cardapio"]["Carboidratos (g)"].sum()
            total_prot = st.session_state["cardapio"]["Proteínas (g)"].sum()
            total_gord = st.session_state["cardapio"]["Gorduras (g)"].sum()
            
            st.markdown("### ⚖️ Saldo Restante")
            
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
            
            st.caption("Progresso de Preenchimento da Meta Diária")
            st.progress(min(total_kcal / calorias_alvo, 1.0) if calorias_alvo > 0 else 0, text="Energia (Kcal)")
            st.progress(min(total_prot / prot_g, 1.0) if prot_g > 0 else 0, text="Proteínas")
            st.progress(min(total_carb / carb_g, 1.0) if carb_g > 0 else 0, text="Carboidratos")
            st.progress(min(total_gord / gord_g, 1.0) if gord_g > 0 else 0, text="Gorduras")

    else:
        st.warning("Banco de dados indisponível no momento.")
