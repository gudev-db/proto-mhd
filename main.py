import os
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Dict
from pymongo import MongoClient
import datetime
from bson.objectid import ObjectId
import urllib.parse

# Load environment variables
load_dotenv()

# Global configurations
st.set_page_config(
    layout="wide",
    page_title="Sistema de Manutenção Industrial",
    page_icon="🔧"
)

# ==============================================
# DATABASE CONFIGURATIONS (MongoDB)
# ==============================================
# MongoDB connection with proper encoding
username = urllib.parse.quote_plus("gustavoromao3345")
password = urllib.parse.quote_plus("RqWFPNOJQfInAW1N")
MONGODB_URI = f"mongodb+srv://{username}:{password}@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority"

try:
    mongo_client = MongoClient(
        MONGODB_URI,
        tls=True,
        tlsAllowInvalidCertificates=True  # Only for development!
    )
    db = mongo_client['manutencao_db']
    relatorios_collection = db['relatorios']
    checklists_collection = db['checklists']
    mongo_client.admin.command('ping')
except Exception as e:
    st.error(f"Erro na conexão com o banco de dados: {str(e)}")
    st.stop()

# ==============================================
# OPENAI CONFIGURATION
# ==============================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY não encontrada no arquivo .env")
    st.stop()

client_openai = OpenAI(api_key=OPENAI_API_KEY)
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o"

# ==============================================
# ASTRA DB CONFIGURATION
# ==============================================
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_COLLECTION = os.getenv("ASTRA_DB_COLLECTION")
ASTRA_DB_NAMESPACE = os.getenv("ASTRA_DB_NAMESPACE", "default_keyspace")

if not all([ASTRA_DB_API_ENDPOINT, ASTRA_DB_APPLICATION_TOKEN, ASTRA_DB_COLLECTION]):
    st.error("Configuração incompleta do AstraDB no arquivo .env")
    st.stop()

class AstraDBClient:
    def __init__(self):
        self.base_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{ASTRA_DB_NAMESPACE}"
        self.headers = {
            "Content-Type": "application/json",
            "x-cassandra-token": ASTRA_DB_APPLICATION_TOKEN,
            "Accept": "application/json"
        }
    
    def vector_search(self, vector: List[float], limit: int = 5) -> List[Dict]:
        """Perform vector similarity search"""
        url = f"{self.base_url}/{ASTRA_DB_COLLECTION}"
        payload = {
            "find": {
                "sort": {"$vector": vector},
                "options": {"limit": limit}
            }
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()["data"]["documents"]
        except Exception as e:
            st.error(f"Erro na busca vetorial: {str(e)}")
            return []

# ==============================================
# MAINTENANCE CHECKLISTS SYSTEM
# ==============================================
CHECKLISTS = {
    "10h (Diário)": [
        "Verificar nível de óleo do motor",
        "Verificar nível do fluido hidráulico",
        "Verificar nível do fluido de arrefecimento",
        "Verificar vazamentos visíveis",
        "Inspecionar pneus/rodas",
        "Verificar luzes e buzina",
        "Testar funcionamento geral dos controles",
        "Registrar horímetro inicial e final"
    ],
    "100h": [
        "Substituir filtro de óleo do motor",
        "Verificar tensão da correia",
        "Lubrificar articulações e pinos",
        "Verificar estado do filtro de ar",
        "Inspecionar mangueiras hidráulicas",
        "Verificar conexão da bateria"
    ],
    "250h / 12 meses": [
        "Substituir filtro hidráulico secundário",
        "Verificar fixação de parafusos estruturais",
        "Checar sistema de transmissão",
        "Inspecionar sistema de freios",
        "Verificar alinhamento do braço de elevação"
    ],
    "500h / 12 meses": [
        "Trocar óleo hidráulico",
        "Trocar óleo do motor",
        "Substituir filtro de combustível",
        "Verificar sistema de arrefecimento completo",
        "Limpeza de radiador"
    ],
    "1000h / 12 meses": [
        "Trocar óleo da transmissão",
        "Verificar embuchamentos e pinos",
        "Verificar sistema elétrico completo",
        "Análise de folgas estruturais",
        "Revisão geral de componentes móveis"
    ],
    "24 meses": [
        "Inspeção estrutural completa",
        "Atualização de firmware (se aplicável)",
        "Verificação de corrosão ou desgastes excessivos",
        "Teste de desempenho funcional geral",
        "Auditoria documental de manutenções anteriores"
    ]
}

def save_checklist(checklist_type, hour_meter, responsible, completed_items, observations):
    """Save checklist to database"""
    checklist = {
        "type": checklist_type,
        "hour_meter": hour_meter,
        "execution_date": datetime.datetime.now(),
        "responsible": responsible,
        "completed_items": completed_items,
        "observations": observations,
        "status": "Completo" if all(completed_items.values()) else "Parcial"
    }
    checklists_collection.insert_one(checklist)
    st.success("Checklist salvo com sucesso!")

def checklist_tab():
    """Checklist filling interface"""
    st.title("📋 Checklists de Manutenção")
    
    # Checklist selection
    checklist_type = st.selectbox(
        "Selecione o tipo de checklist:",
        list(CHECKLISTS.keys()),
        key="checklist_type"
    )
    
    # Basic information
    col1, col2, col3 = st.columns(3)
    with col1:
        hour_meter = st.number_input("Horímetro", min_value=0.0, step=1.0, key="hour_meter")
    with col2:
        execution_date = st.date_input("Data de execução", value=datetime.datetime.now(), key="execution_date")
    with col3:
        responsible = st.text_input("Responsável", key="responsible")
    
    st.divider()
    st.subheader("Itens de Verificação")
    
    # Dynamic checklist
    completed_items = {}
    for item in CHECKLISTS[checklist_type]:
        completed_items[item] = st.checkbox(item, key=f"check_{item}")
    
    st.divider()
    observations = st.text_area("Observações", key="observations")
    
    if st.button("Salvar Checklist", type="primary"):
        if not responsible:
            st.error("Por favor informe o responsável")
        else:
            save_checklist(
                checklist_type,
                hour_meter,
                responsible,
                completed_items,
                observations
            )
            st.balloons()

def checklist_history():
    """Checklist history viewer"""
    st.title("📜 Histórico de Checklists")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_type = st.selectbox(
            "Filtrar por tipo",
            ["Todos"] + list(CHECKLISTS.keys()),
            key="filter_type"
        )
    with col2:
        filter_responsible = st.text_input("Filtrar por responsável", key="filter_responsible")
    with col3:
        filter_status = st.selectbox(
            "Filtrar por status",
            ["Todos", "Completo", "Parcial"],
            key="filter_status"
        )
    
    # Build query
    query = {}
    if filter_type != "Todos":
        query["type"] = filter_type
    if filter_responsible:
        query["responsible"] = {"$regex": filter_responsible, "$options": "i"}
    if filter_status != "Todos":
        query["status"] = filter_status
    
    try:
        checklists = list(checklists_collection.find(query).sort("execution_date", -1).limit(50))
        
        if not checklists:
            st.info("Nenhum checklist encontrado com os filtros selecionados")
        else:
            for checklist in checklists:
                with st.expander(f"{checklist['type']} - {checklist['execution_date'].strftime('%d/%m/%Y')} - Horímetro: {checklist['hour_meter']}"):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**Responsável:** {checklist['responsible']}")
                        st.markdown(f"**Status:** {checklist['status']}")
                        
                        st.markdown("**Itens completados:**")
                        for item, completed in checklist['completed_items'].items():
                            st.markdown(f"- {'✅' if completed else '❌'} {item}")
                        
                        if checklist.get('observations'):
                            st.markdown(f"**Observações:** {checklist['observations']}")
                    
                    with col2:
                        if st.button("🗑️ Excluir", key=f"del_{checklist['_id']}"):
                            checklists_collection.delete_one({"_id": checklist['_id']})
                            st.rerun()
    except Exception as e:
        st.error(f"Erro ao buscar checklists: {str(e)}")

# ==============================================
# RAG CHATBOT FUNCTIONS
# ==============================================
def get_embedding(text: str) -> List[float]:
    """Get text embedding using OpenAI"""
    try:
        response = client_openai.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        st.error(f"Erro ao obter embedding: {str(e)}")
        return []

def chatbot_rag():
    """RAG Chatbot interface with specialized tabs for different user levels"""
    st.title("🛠️ Assistente de Manutenção - Torno CNC Turner 180x300")
    
    # Initialize Astra DB client
    astra_client = AstraDBClient()
    
    # Create tabs for different user levels
    tab_novato, tab_experiente, tab_tecnico, tab_personalizado = st.tabs([
        "👶 Para Iniciantes", 
        "👨‍🔧 Para Experientes", 
        "🔧 Técnico Avançado",
        "🎛️ Prompt Personalizado"
    ])
    
    # Initialize conversation history for each tab
    if "messages_novato" not in st.session_state:
        st.session_state.messages_novato = []
    if "messages_experiente" not in st.session_state:
        st.session_state.messages_experiente = []
    if "messages_tecnico" not in st.session_state:
        st.session_state.messages_tecnico = []
    if "messages_personalizado" not in st.session_state:
        st.session_state.messages_personalizado = []
    if "custom_prompt" not in st.session_state:
        st.session_state.custom_prompt = ""
    
    # Common visual description
    visual_description = """
    **DESCRIÇÃO VISUAL DO TORNO CNC TURNER 180x300:**

    Este é um **Torno Mecânico CNC de bancada** compacto, ideal para pequenas oficinas. Corpo branco com detalhes vermelhos e pretos.

    **LADO ESQUERDO - UNIDADE PRINCIPAL:**
    • **Painel de Controle:** Botão de emergência vermelho/amarelo, chave seletora de energia, display digital
    • **Controles:** Botão giratório de velocidade (150-1250 rpm / 300-2500 rpm)
    • **Proteção:** Cobertura branca com janela transparente para segurança
    • **Área de Trabalho:** Torre porta-ferramentas vermelha, volantes prateados para ajuste manual

    **LADO DIREITO - CONTROLE CNC:**
    • **Tela DDCS V.2.1:** Monitor para programação e controle
    • **Pendente de Controle:** Volante branco grande para movimento manual preciso
    • **Botões:** Start, Pause, Stop, Menu e setas direcionais
    • **Porta USB:** Para carregar programas de usinagem

    **SEGURANÇA:** Use sempre óculos de proteção! Leia o manual antes de operar.
    """
    
    def get_system_prompt(user_level, context=""):
        """Get specialized system prompt based on user level"""
        
        base_prompts = {
            "novato": f"""
            Você é um instrutor paciente e detalhista para usuários que estão usando um Torno CNC pela PRIMEIRA VEZ.
            
            {visual_description}
            
            DIRETRIZES PARA INICIANTES:
            - Explique como se estivesse ensinando uma criança - passo a passo, muito claro
            - SEMPRE descreva a localização física dos componentes ("olhe para o lado esquerdo...", "procure o botão vermelho...")
            - Use analogias simples do cotidiano para explicar conceitos técnicos
            - Enfatize a SEGURANÇA acima de tudo
            - Mostre imagens mentais: "imagine que...", "é como se fosse..."
            - Nunca use jargões técnicos sem explicar
            - Dê exemplos práticos e mostre o "passo a passo visual"
            - Repita informações importantes
            - Seja encorajador e reconheça que é normal ter dúvidas
            
            Exemplo de resposta:
            "Vamos começar pelo básico! Olhe para a máquina: no lado ESQUERDO você vê um botão grande VERMELHO com detalhes AMARELOS. Esse é o botão de EMERGÊNCIA - é o mais importante! Antes de ligar a máquina, sempre saiba onde ele está. É como o freio de emergência do carro - só use em caso de perigo!"
            """,
            
            "experiente": f"""
            Você é um técnico especializado para usuários com experiência básica em tornos.
            
            {visual_description}
            
            DIRETRIZES PARA EXPERIENTES:
            - Seja direto e prático, assuma conhecimento básico
            - Foque em procedimentos e soluções rápidas
            - Dê atalhos e dicas de eficiência
            - Explique conceitos técnicos mas sem excesso de detalhes
            - Mostre relações entre componentes e funções
            - Inclua procedimentos de manutenção preventiva
            - Dê referências visuais rápidas: "no painel esquerdo, ajuste a velocidade..."
            - Ofereça soluções para problemas comuns
            
            Exemplo de resposta:
            "Para ajustar a velocidade, use o botão giratório no painel esquerdo. Lembre-se: use a faixa 150-1250 rpm para materiais mais duros e 300-2500 para materiais mais macios. A troca de faixa é manual - verifique o seletor interno."
            """,
            
            "tecnico": f"""
            Você é um engenheiro especialista em Tornos CNC para técnicos avançados.
            
            {visual_description}
            
            DIRETRIZES TÉCNICAS:
            - Use terminologia técnica específica sem explicações básicas
            - Forneça especificações técnicas detalhadas
            - Inclua parâmetros, tolerâncias e valores de referência
            - Discuta arquitetura do sistema CNC e componentes
            - Aborde troubleshooting avançado e diagnóstico
            - Referencie diagramas técnicos e procedimentos de calibração
            - Inclua códigos G e parâmetros de programação quando relevante
            - Discuta integração de sistemas e otimização de processos
            
            Exemplo de resposta:
            "O sistema DDCS V2.1 utiliza controle de malha fechada com encoders de 1000 pulsos/volta. Para recalibração do eixo Z, acesse o menu de parâmetros (P800-815) e execute o procedimento de auto-homing. A precisão nominal é de ±0.01mm com repetibilidade de ±0.005mm."
            """,
            
            "personalizado": f"""
            {visual_description}
            
            INSTRUÇÕES PERSONALIZADAS DO USUÁRIO:
            {st.session_state.custom_prompt}
            
            DIRETRIZES GERAIS:
            - Sempre considere a descrição visual acima
            - Seja prático e objetivo
            - Forneça informações acionáveis
            - Mantenha o foco no contexto de manutenção industrial
            """
        }
        
        return base_prompts.get(user_level, base_prompts["novato"]) + f"\n\nContexto adicional:\n{context}"
    
    def chat_interface(messages_key, user_level, placeholder_text):
        """Reusable chat interface for different tabs"""
        
        # Container for chat messages with custom styling
        chat_container = st.container(height=400)
        
        # Display previous messages
        with chat_container:
            for message in st.session_state[messages_key]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input(placeholder_text):
            # Add user message to history
            st.session_state[messages_key].append({"role": "user", "content": prompt})
            
            # Display user message immediately
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
            
            # Get embedding and search Astra DB
            embedding = get_embedding(prompt)
            context = ""
            if embedding:
                results = astra_client.vector_search(embedding)
                context = "\n".join([str(doc) for doc in results])
            
            # Generate response with specialized prompt
            system_prompt = get_system_prompt(user_level, context)
            
            # Prepare messages for chat completion
            messages_for_api = [
                {"role": "system", "content": system_prompt},
                *st.session_state[messages_key][-6:],
                {"role": "user", "content": prompt}
            ]
            
            try:
                response = client_openai.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=messages_for_api,
                    temperature=0.7
                )
                assistant_response = response.choices[0].message.content
            except Exception as e:
                assistant_response = f"Erro ao gerar resposta: {str(e)}"
            
            # Add response to history
            st.session_state[messages_key].append({"role": "assistant", "content": assistant_response})
            
            # Display assistant response
            with chat_container:
                with st.chat_message("assistant"):
                    st.markdown(assistant_response)
            
            # Rerun to update the display
            st.rerun()
    
    # Tab for Novice Users
    with tab_novato:
        st.header("👶 Assistente para Iniciantes")
        st.markdown("""
        **Bem-vindo ao mundo dos Tornos CNC!** 🎉
        
        Aqui você vai aprender desde o básico:
        - Como identificar cada parte da máquina
        - Procedimentos de segurança ESSENCIAIS  
        - Primeiros passos para operar
        - Conceitos fundamentais explicados de forma SIMPLES
        """)
        
        # Quick safety tips
        with st.expander("🚨 DICAS RÁPIDAS DE SEGURANÇA (LEIA ANTES!)"):
            st.markdown("""
            - **SEMPRE use óculos de proteção**
            - Conheça a localização do botão de EMERGÊNCIA (vermelho/amarelo)
            - Mantenha as mãos longe das partes móveis
            - Não use luvas soltas ou joias
            - Leia o manual antes de qualquer operação
            - Trabalhe em área bem iluminada e ventilada
            """)
        
        chat_interface(
            "messages_novato", 
            "novato", 
            "Pergunte sobre qualquer coisa... não existe pergunta boba! 🤔"
        )
        
        # Clear chat button for novice
        if st.session_state.messages_novato:
            if st.button("🧹 Limpar Conversa", key="clear_novato"):
                st.session_state.messages_novato = []
                st.rerun()
    
    # Tab for Experienced Users
    with tab_experiente:
        st.header("👨‍🔧 Assistente para Experientes")
        st.markdown("""
        **Otimize suas operações!** ⚡
        
        Focado em:
        - Procedimentos eficientes
        - Solução de problemas comuns
        - Manutenção preventiva
        - Dicas de produtividade
        """)
        
        # Quick reference
        with st.expander("📋 REFERÊNCIA RÁPIDA"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                **Velocidades:**
                - Aço: 150-600 rpm
                - Alumínio: 800-2000 rpm  
                - Plástico: 1000-2500 rpm
                """)
            with col2:
                st.markdown("""
                **Manutenção:**
                - Lubrifique a cada 8h
                - Limpe cavacos diariamente
                - Verifique correias semanalmente
                """)
        
        chat_interface(
            "messages_experiente", 
            "experiente", 
            "Qual procedimento ou problema você precisa resolver? 🔧"
        )
        
        # Clear chat button for experienced
        if st.session_state.messages_experiente:
            if st.button("🧹 Limpar Conversa", key="clear_experiente"):
                st.session_state.messages_experiente = []
                st.rerun()
    
    # Tab for Technical Users
    with tab_tecnico:
        st.header("🔧 Assistente Técnico Avançado")
        st.markdown("""
        **Especialização técnica completa** 🎯
        
        Para discussões avançadas sobre:
        - Especificações técnicas detalhadas
        - Programação CNC e códigos G
        - Diagnóstico avançado de falhas
        - Parâmetros de calibração
        - Otimização de processos
        """)
        
        # Technical specs
        with st.expander("📊 ESPECIFICAÇÕES TÉCNICAS"):
            st.markdown("""
            **Torno CNC Turner 180x300:**
            - Capacidade: Ø180mm x 300mm
            - Controle: DDCS V2.1
            - Precisão: ±0.01mm
            - Motor: Passo a passo NEMA 23
            - Alimentação: 220V
            - RPM: 150-2500 (2 faixas)
            - Roscas: Métrica e Imperial
            - Sistema: Controle de malha fechada
            - Encoders: 1000 pulsos/volta
            """)
        
        chat_interface(
            "messages_tecnico", 
            "tecnico", 
            "Consulta técnica, parâmetros ou diagnóstico? 🛠️"
        )
        
        # Clear chat button for technical
        if st.session_state.messages_tecnico:
            if st.button("🧹 Limpar Conversa", key="clear_tecnico"):
                st.session_state.messages_tecnico = []
                st.rerun()
    
    # Tab for Custom Prompt
    with tab_personalizado:
        st.header("🎛️ Prompt Personalizado")
        st.markdown("""
        **Crie seu próprio assistente personalizado!** 🎨
        
        Configure instruções específicas para o chatbot. A descrição visual da máquina será sempre incluída.
        """)
        
        # Custom prompt configuration
        with st.expander("⚙️ CONFIGURAR PROMPT PERSONALIZADO"):
            st.markdown("""
            **Exemplos de uso:**
            - "Responda como um técnico especializado em usinagem de alumínio"
            - "Foque em procedimentos de segurança avançada"
            - "Atue como um instrutor para aprendizes de mecânica"
            - "Especialize-se em manutenção preventiva"
            """)
            
            custom_prompt = st.text_area(
                "Instruções Personalizadas:",
                value=st.session_state.custom_prompt,
                placeholder="Ex: Responda sempre em tom formal, focando em procedimentos de calibração...",
                height=150,
                key="custom_prompt_input"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Salvar Prompt", type="primary"):
                    st.session_state.custom_prompt = custom_prompt
                    st.success("Prompt personalizado salvo!")
            with col2:
                if st.button("🗑️ Limpar Prompt"):
                    st.session_state.custom_prompt = ""
                    st.rerun()
        
        # Show current custom prompt
        if st.session_state.custom_prompt:
            with st.expander("📝 PROMPT ATUAL (Visualização)"):
                st.code(st.session_state.custom_prompt)
        
        # Visual description reminder
        with st.expander("👁️ DESCRIÇÃO VISUAL DA MÁQUINA"):
            st.markdown(visual_description)
        
        chat_interface(
            "messages_personalizado", 
            "personalizado", 
            "Faça sua pergunta com o prompt personalizado... 🎯"
        )
        
        # Clear chat button for custom
        if st.session_state.messages_personalizado:
            if st.button("🧹 Limpar Conversa", key="clear_personalizado"):
                st.session_state.messages_personalizado = []
                st.rerun()
    
    # Enhanced CSS for better visual experience
    st.markdown("""
    <style>
        /* Main chat container styling */
        .stChatInput {
            position: relative !important;
            bottom: 0 !important;
            background: white !important;
        }
        
        /* Tab-specific styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #f0f2f6;
            border-radius: 8px 8px 0px 0px;
            gap: 8px;
            padding: 10px 16px;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #e3f2fd;
            border-bottom: 3px solid #2196f3;
        }
        
        /* Chat message enhancements */
        [data-testid="stChatMessage"] {
            padding: 12px;
            margin: 8px 0;
            border-radius: 15px;
        }
        
        /* User message styling */
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
            padding: 12px 16px;
            border-radius: 18px;
        }
        
        /* Custom prompt tab specific styling */
        .custom-prompt-box {
            border: 2px dashed #4caf50;
            padding: 15px;
            border-radius: 10px;
            background-color: #f8fff8;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)

# ==============================================
# MAINTENANCE REPORTS SYSTEM
# ==============================================
def create_report():
    """Create new maintenance report"""
    st.subheader("Novo Relatório de Manutenção")
    
    with st.form(key='report_form'):
        # Technician identification
        st.markdown("### Identificação")
        technician = st.text_input("Nome do Técnico", max_chars=100, key="technician_name")
        
        # Equipment data
        st.markdown("### Dados do Equipamento")
        equipment = st.text_input("Equipamento", value="S450", max_chars=100, key="equipment_name")
        hour_meter = st.number_input("Horímetro", min_value=0.0, format="%.1f", key="hour_meter_value")
        
        # Maintenance type
        st.markdown("### Tipo de Manutenção")
        maintenance_type = st.selectbox(
            "Tipo de Manutenção",
            ["Preventiva", "Corretiva", "Lubrificação", "Inspeção"],
            index=0,
            key="maintenance_type_select"
        )
        
        # Maintenance date
        maintenance_date = st.date_input("Data da Manutenção", value=datetime.date.today(), key="maintenance_date_input")
        
        # Maintenance details
        st.markdown("### Detalhes da Manutenção")
        reason = st.text_area("Motivo da Manutenção", height=100, key="reason_text")
        description = st.text_area("Descrição do Serviço", height=150, key="description_text")
        observations = st.text_area("Observações Adicionais", height=100, key="observations_text")
        
        # Submit button
        submitted = st.form_submit_button("Salvar Relatório")
        
        if submitted:
            if not technician or not equipment or not reason or not description:
                st.error("Por favor preencha todos os campos obrigatórios!")
            else:
                report = {
                    "technician": technician,
                    "equipment": equipment,
                    "hour_meter": hour_meter,
                    "maintenance_type": maintenance_type,
                    "maintenance_date": datetime.datetime.combine(maintenance_date, datetime.datetime.min.time()),
                    "reason": reason,
                    "description": description,
                    "observations": observations,
                    "creation_date": datetime.datetime.now(),
                    "last_update": datetime.datetime.now()
                }
                
                try:
                    result = relatorios_collection.insert_one(report)
                    st.success("Relatório salvo com sucesso!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erro ao salvar relatório: {str(e)}")

def view_reports():
    """View maintenance reports"""
    st.subheader("Relatórios de Manutenção")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        technician_filter = st.text_input("Filtrar por técnico", key="technician_filter")
    with col2:
        equipment_filter = st.text_input("Filtrar por equipamento", key="equipment_filter")
    with col3:
        type_filter = st.selectbox(
            "Filtrar por tipo",
            ["Todos"] + ["Preventiva", "Corretiva", "Lubrificação", "Inspeção"],
            key="type_filter"
        )
    
    # Build query
    query = {}
    if technician_filter:
        query["technician"] = {"$regex": technician_filter, "$options": "i"}
    if equipment_filter:
        query["equipment"] = {"$regex": equipment_filter, "$options": "i"}
    if type_filter != "Todos":
        query["maintenance_type"] = type_filter
    
    try:
        # Get reports (sorted by date descending)
        reports = list(relatorios_collection.find(query).sort("maintenance_date", -1))
        
        if not reports:
            st.info("Nenhum relatório encontrado com os filtros selecionados")
        else:
            for report in reports:
                with st.expander(f"{report['equipment']} - {report['maintenance_type']} ({report['maintenance_date'].strftime('%d/%m/%Y')})"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**Técnico:** {report['technician']}")
                        st.markdown(f"**Equipamento:** {report['equipment']}")
                        st.markdown(f"**Horímetro:** {report['hour_meter']} horas")
                        st.markdown(f"**Tipo de Manutenção:** {report['maintenance_type']}")
                        st.markdown(f"**Data da Manutenção:** {report['maintenance_date'].strftime('%d/%m/%Y')}")
                        st.markdown(f"**Motivo:** {report['reason']}")
                        st.markdown(f"**Descrição:** {report['description']}")
                        if report.get('observations'):
                            st.markdown(f"**Observações:** {report['observations']}")
                    
                    with col2:
                        # Edit button
                        if st.button("✏️ Editar", key=f"edit_{report['_id']}"):
                            st.session_state['edit_id'] = str(report['_id'])
                            st.session_state['edit_report'] = report
                            st.rerun()
                        
                        # Delete button
                        if st.button("🗑️ Excluir", key=f"del_{report['_id']}"):
                            relatorios_collection.delete_one({"_id": report['_id']})
                            st.rerun()
    except Exception as e:
        st.error(f"Erro ao buscar relatórios: {str(e)}")

def edit_report():
    """Edit existing maintenance report"""
    if 'edit_id' not in st.session_state:
        st.warning("Nenhum relatório selecionado para edição")
        return
    
    report = st.session_state['edit_report']
    st.subheader(f"Editando Relatório: {report['equipment']}")
    
    with st.form(key='edit_report_form'):
        # Technician identification
        st.markdown("### Identificação")
        technician = st.text_input("Nome do Técnico", value=report['technician'], max_chars=100, key="edit_technician")
        
        # Equipment data
        st.markdown("### Dados do Equipamento")
        equipment = st.text_input("Equipamento", value=report['equipment'], max_chars=100, key="edit_equipment")
        hour_meter = st.number_input("Horímetro", value=report['hour_meter'], min_value=0.0, format="%.1f", key="edit_hour_meter")
        
        # Maintenance type
        st.markdown("### Tipo de Manutenção")
        maintenance_type = st.selectbox(
            "Tipo de Manutenção",
            ["Preventiva", "Corretiva", "Lubrificação", "Inspeção"],
            index=["Preventiva", "Corretiva", "Lubrificação", "Inspeção"].index(report['maintenance_type']),
            key="edit_maintenance_type"
        )
        
        # Maintenance date
        maintenance_date = st.date_input(
            "Data da Manutenção", 
            value=report['maintenance_date'].date(),
            key="edit_maintenance_date"
        )
        
        # Maintenance details
        st.markdown("### Detalhes da Manutenção")
        reason = st.text_area("Motivo da Manutenção", value=report['reason'], height=100, key="edit_reason")
        description = st.text_area("Descrição do Serviço", value=report['description'], height=150, key="edit_description")
        observations = st.text_area("Observações Adicionais", value=report.get('observations', ''), height=100, key="edit_observations")
        
        # Buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            submitted = st.form_submit_button("Salvar Alterações")
        with col2:
            if st.form_submit_button("Cancelar"):
                del st.session_state['edit_id']
                del st.session_state['edit_report']
                st.rerun()
        
        if submitted:
            if not technician or not equipment or not reason or not description:
                st.error("Por favor preencha todos os campos obrigatórios!")
            else:
                updated_report = {
                    "$set": {
                        "technician": technician,
                        "equipment": equipment,
                        "hour_meter": hour_meter,
                        "maintenance_type": maintenance_type,
                        "maintenance_date": datetime.datetime.combine(maintenance_date, datetime.datetime.min.time()),
                        "reason": reason,
                        "description": description,
                        "observations": observations,
                        "last_update": datetime.datetime.now()
                    }
                }
                
                try:
                    relatorios_collection.update_one(
                        {"_id": report['_id']},
                        updated_report
                    )
                    st.success("Relatório atualizado com sucesso!")
                    del st.session_state['edit_id']
                    del st.session_state['edit_report']
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar relatório: {str(e)}")

# ==============================================
# MAIN APPLICATION
# ==============================================
def main():
    """Main application with tabs"""
    tab1, tab2, tab3, tab4 = st.tabs([
        "🤖 Assistente", 
        "📝 Relatórios", 
        "✅ Checklists",
        "📊 Histórico"
    ])
    
    with tab1:
        chatbot_rag()
    
    with tab2:
        if 'edit_id' in st.session_state:
            edit_report()
        else:
            create_report()
        st.divider()
        view_reports()
    
    with tab3:
        checklist_tab()
    
    with tab4:
        checklist_history()

if __name__ == "__main__":
    main()
