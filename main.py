def chatbot_rag():
    """RAG Chatbot interface with specialized tabs for different user levels"""
    st.title("🛠️ Assistente de Manutenção - Torno CNC Turner 180x300")
    
    # Initialize Astra DB client
    astra_client = AstraDBClient()
    
    # Create tabs for different user levels
    tab_novato, tab_experiente, tab_tecnico = st.tabs([
        "👶 Para Iniciantes", 
        "👨‍🔧 Para Experientes", 
        "🔧 Técnico Avançado"
    ])
    
    # Initialize conversation history for each tab
    if "messages_novato" not in st.session_state:
        st.session_state.messages_novato = []
    if "messages_experiente" not in st.session_state:
        st.session_state.messages_experiente = []
    if "messages_tecnico" not in st.session_state:
        st.session_state.messages_tecnico = []
    
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
        
        /* Visual indicators for different tabs */
        .novice-chat {
            border-left: 4px solid #4caf50;
        }
        
        .experienced-chat {
            border-left: 4px solid #ff9800;
        }
        
        .technical-chat {
            border-left: 4px solid #f44336;
        }
    </style>
    """, unsafe_allow_html=True)

# Update the main function to only show the chatbot tab for testing
def main():
    """Main application focusing only on chatbot"""
    st.set_page_config(
        layout="wide",
        page_title="Assistente Torno CNC Turner 180x300",
        page_icon="🛠️"
    )
    
    chatbot_rag()

if __name__ == "__main__":
    main()
