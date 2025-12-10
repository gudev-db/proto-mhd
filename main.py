import os
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Dict
import base64
from io import BytesIO
from PIL import Image
import tempfile

# Load environment variables
load_dotenv()

# Global configurations
st.set_page_config(
    layout="wide",
    page_title="Assistente de Torno CNC",
    page_icon="🔧"
)

# ==============================================
# OPENAI CONFIGURATION
# ==============================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY não encontrada no arquivo .env")
    st.stop()

client_openai = OpenAI(api_key=OPENAI_API_KEY)
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"  # Usando modelo que suporta visão
VISION_MODEL = "gpt-4o-mini"

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
# IMAGE PROCESSING FUNCTIONS
# ==============================================
def encode_image_to_base64(image_file) -> str:
    """Convert uploaded image to base64 string"""
    try:
        # Read image file
        image_bytes = image_file.read()
        
        # Convert to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Determine MIME type
        mime_type = image_file.type
        if not mime_type:
            # Guess from filename
            if image_file.name.lower().endswith('.png'):
                mime_type = 'image/png'
            elif image_file.name.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif image_file.name.lower().endswith('.webp'):
                mime_type = 'image/webp'
            elif image_file.name.lower().endswith('.gif'):
                mime_type = 'image/gif'
            else:
                mime_type = 'image/jpeg'  # default
        
        return f"data:{mime_type};base64,{base64_image}"
    except Exception as e:
        st.error(f"Erro ao processar imagem: {str(e)}")
        return ""

def analyze_image_with_gpt(image_base64: str, question: str = "O que você vê nesta imagem?") -> str:
    """Analyze image content using GPT vision capabilities"""
    try:
        response = client_openai.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64,
                                "detail": "high"  # Use "low" para economizar tokens se necessário
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro ao analisar imagem: {str(e)}")
        return ""

def get_embedding_from_image_analysis(analysis_text: str) -> List[float]:
    """Get embedding from image analysis text"""
    return get_embedding(analysis_text)

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

# ==============================================
# RAG CHATBOT FUNCTIONS WITH IMAGE SUPPORT
# ==============================================
def chatbot_rag():
    """RAG Chatbot interface with image upload support"""
    st.title("🛠️ Assistente de Torno CNC Turner 180x300")
    
    # Initialize Astra DB client
    astra_client = AstraDBClient()
    
    # Initialize session state for images
    if "uploaded_images" not in st.session_state:
        st.session_state.uploaded_images = []
    if "current_image_analysis" not in st.session_state:
        st.session_state.current_image_analysis = ""
    
    # Create tabs for different user levels
    tab_novato, tab_experiente, tab_tecnico, tab_personalizado, tab_imagem = st.tabs([
        "👶 Iniciantes", 
        "👨‍🔧 Experientes", 
        "🔧 Técnico",
        "🎛️ Personalizado",
        "🖼️ Com Imagem"
    ])
    
    # Initialize conversation history for each tab
    tab_messages_keys = {
        "novato": "messages_novato",
        "experiente": "messages_experiente", 
        "tecnico": "messages_tecnico",
        "personalizado": "messages_personalizado",
        "imagem": "messages_imagem"
    }
    
    for key in tab_messages_keys.values():
        if key not in st.session_state:
            st.session_state[key] = []
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
            """,
            
            "imagem": f"""
            Você é um especialista em análise de imagens de equipamentos industriais, especialmente tornos CNC.
            
            {visual_description}
            
            DIRETRIZES PARA ANÁLISE DE IMAGENS:
            - Analise a imagem fornecida pelo usuário detalhadamente
            - Compare com a descrição padrão do Torno CNC Turner 180x300
            - Identifique componentes, peças, ferramentas ou problemas visíveis
            - Dê recomendações específicas baseadas no que você vê
            - Se a imagem não for clara, peça mais detalhes ou outra imagem
            - Relacione o que você vê com procedimentos de manutenção ou operação
            - Se identificar problemas, sugere ações corretivas
            - Se for uma foto de um manual ou diagrama, explique o conteúdo
            """
        }
        
        return base_prompts.get(user_level, base_prompts["novato"]) + f"\n\nContexto adicional:\n{context}"
    
    def chat_interface(messages_key, user_level, placeholder_text, with_image=False):
        """Reusable chat interface for different tabs"""
        
        # For image tab, show upload section
        if with_image:
            st.header("📤 Envie uma Imagem do Torno")
            
            col1, col2 = st.columns([2, 3])
            
            with col1:
                # Image upload section
                uploaded_file = st.file_uploader(
                    "Escolha uma imagem",
                    type=['jpg', 'jpeg', 'png', 'webp', 'gif'],
                    key=f"upload_{user_level}"
                )
                
                if uploaded_file is not None:
                    # Display uploaded image
                    st.image(uploaded_file, caption="Imagem enviada", use_column_width=True)
                    
                    # Store in session state
                    st.session_state.uploaded_images.append(uploaded_file)
                    
                    # Analyze button
                    if st.button("🔍 Analisar Imagem", type="primary", key=f"analyze_{user_level}"):
                        with st.spinner("Analisando imagem..."):
                            # Convert to base64
                            image_base64 = encode_image_to_base64(uploaded_file)
                            
                            if image_base64:
                                # Analyze image content
                                analysis = analyze_image_with_gpt(
                                    image_base64, 
                                    "Analise esta imagem de um torno CNC. Descreva o que você vê, identifique componentes e dê recomendações relevantes."
                                )
                                
                                if analysis:
                                    st.session_state.current_image_analysis = analysis
                                    st.success("Imagem analisada com sucesso!")
                                    
                                    # Show analysis summary
                                    with st.expander("📋 Resumo da Análise", expanded=True):
                                        st.write(analysis[:500] + "..." if len(analysis) > 500 else analysis)
            
            with col2:
                # Show chat container
                chat_container = st.container(height=500)
        
        else:
            # Regular chat container for other tabs
            chat_container = st.container(height=400)
        
        # Display previous messages
        with chat_container:
            for message in st.session_state[messages_key]:
                with st.chat_message(message["role"]):
                    if message.get("type") == "image":
                        st.image(message["content"], caption="Imagem enviada", use_column_width=True)
                    else:
                        st.markdown(message["content"])
        
        # Chat input
        chat_input_col1, chat_input_col2 = st.columns([4, 1]) if with_image else (None, None)
        
        if with_image:
            with chat_input_col1:
                prompt = st.chat_input(placeholder_text)
        else:
            prompt = st.chat_input(placeholder_text)
        
        if prompt:
            # Add user message to history
            st.session_state[messages_key].append({"role": "user", "content": prompt})
            
            # Display user message immediately
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
            
            # Get context based on user level
            context = ""
            
            if with_image and st.session_state.current_image_analysis:
                # Use image analysis as context for RAG
                context = f"Análise da imagem enviada: {st.session_state.current_image_analysis}\n\n"
                
                # Get embedding from image analysis and search Astra DB
                embedding = get_embedding_from_image_analysis(st.session_state.current_image_analysis)
                if embedding:
                    results = astra_client.vector_search(embedding)
                    rag_context = "\n".join([str(doc) for doc in results])
                    context += f"Informações relevantes do banco de conhecimento: {rag_context}"
            else:
                # Regular text-based RAG
                embedding = get_embedding(prompt)
                if embedding:
                    results = astra_client.vector_search(embedding)
                    context = "\n".join([str(doc) for doc in results])
            
            # Generate response with specialized prompt
            system_prompt = get_system_prompt(user_level, context)
            
            # Prepare messages for chat completion
            messages_for_api = [
                {"role": "system", "content": system_prompt},
                *[
                    {"role": msg["role"], "content": msg["content"]} 
                    for msg in st.session_state[messages_key][-6:] 
                    if msg.get("type") != "image"
                ],
                {"role": "user", "content": prompt}
            ]
            
            # For image tab, include image analysis in context
            if with_image and st.session_state.current_image_analysis:
                messages_for_api[-1]["content"] = f"Análise da imagem: {st.session_state.current_image_analysis}\n\nPergunta do usuário: {prompt}"
            
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
            "Pergunte sobre qualquer coisa... não existe pergunta boba! 🤔",
            with_image=False
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
            "Qual procedimento ou problema você precisa resolver? 🔧",
            with_image=False
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
            "Consulta técnica, parâmetros ou diagnóstico? 🛠️",
            with_image=False
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
            "Faça sua pergunta com o prompt personalizado... 🎯",
            with_image=False
        )
        
        # Clear chat button for custom
        if st.session_state.messages_personalizado:
            if st.button("🧹 Limpar Conversa", key="clear_personalizado"):
                st.session_state.messages_personalizado = []
                st.rerun()
    
    # Tab for Image Analysis
    with tab_imagem:
        st.header("🖼️ Análise com Imagem")
        st.markdown("""
        **Envie uma imagem do torno para análise especializada!** 📸
        
        Como usar:
        1. 📤 Faça upload de uma imagem do torno ou de seus componentes
        2. 🔍 Clique em "Analisar Imagem" para processamento
        3. 💬 Faça perguntas específicas sobre o que você vê
        4. 🛠️ Receba recomendações personalizadas
        
        **Tipos de imagens úteis:**
        - Foto geral do torno
        - Componentes específicos (painel, ferramentas, etc.)
        - Problemas ou desgastes visíveis
        - Diagramas ou manuais
        - Peças que precisam de identificação
        """)
        
        # Image analysis chat interface
        chat_interface(
            "messages_imagem", 
            "imagem", 
            "Faça uma pergunta sobre a imagem analisada... 📝",
            with_image=True
        )
        
        # Clear chat and image button
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.messages_imagem:
                if st.button("🧹 Limpar Conversa", key="clear_imagem"):
                    st.session_state.messages_imagem = []
                    st.rerun()
        
        with col2:
            if st.session_state.uploaded_images or st.session_state.current_image_analysis:
                if st.button("🗑️ Limpar Imagem", key="clear_image_data"):
                    st.session_state.uploaded_images = []
                    st.session_state.current_image_analysis = ""
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
            gap: 4px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            white-space: nowrap;
            background-color: #f0f2f6;
            border-radius: 6px 6px 0px 0px;
            padding: 8px 12px;
            font-size: 14px;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #e3f2fd;
            border-bottom: 3px solid #2196f3;
            font-weight: bold;
        }
        
        /* Image upload styling */
        .uploadedImage {
            border: 2px solid #4caf50;
            border-radius: 10px;
            padding: 10px;
            margin: 10px 0;
        }
        
        /* Chat message enhancements */
        [data-testid="stChatMessage"] {
            padding: 10px;
            margin: 6px 0;
            border-radius: 12px;
        }
        
        /* User message styling */
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
            padding: 10px 14px;
            border-radius: 15px;
        }
        
        /* Image tab specific */
        .image-analysis-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)

# ==============================================
# MAIN APPLICATION
# ==============================================
def main():
    """Main application"""
    chatbot_rag()

if __name__ == "__main__":
    main()
