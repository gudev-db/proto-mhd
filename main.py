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

# Configurações globais
st.set_page_config(
    layout="wide",
    page_title="Sistema de Manutenção",
    page_icon="🔧"
)

# ==============================================
# CONFIGURAÇÕES DE BANCO DE DADOS (MongoDB)
# ==============================================
# MongoDB connection with proper encoding for username/password
username = urllib.parse.quote_plus("gustavoromao3345")
password = urllib.parse.quote_plus("RqWFPNOJQfInAW1N")

MONGODB_URI = f"mongodb+srv://{username}:{password}@cluster0.5iilj.mongodb.net/auto_doc?retryWrites=true&w=majority"

try:
    mongo_client = MongoClient(
        MONGODB_URI,
        tls=True,
        tlsAllowInvalidCertificates=True  # Only for development!
    )
    db = mongo_client['auto_doc']
    relatorios_collection = db['relatorios']
    
    # Test the connection
    mongo_client.admin.command('ping')
    st.success("Conexão com MongoDB estabelecida com sucesso!")
except Exception as e:
    st.error(f"Erro ao conectar ao MongoDB: {str(e)}")
    st.stop()

# ==============================================
# CONFIGURAÇÕES DO OPENAI (from .env)
# ==============================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY não encontrada no arquivo .env")
    st.stop()

client_openai = OpenAI(api_key=OPENAI_API_KEY)
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o"

# ==============================================
# CONFIGURAÇÕES DO ASTRA DB (from .env)
# ==============================================
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_COLLECTION = os.getenv("ASTRA_DB_COLLECTION")
ASTRA_DB_NAMESPACE = os.getenv("ASTRA_DB_NAMESPACE", "default_keyspace")

if not all([ASTRA_DB_API_ENDPOINT, ASTRA_DB_APPLICATION_TOKEN, ASTRA_DB_COLLECTION]):
    st.error("Configurações do AstraDB incompletas no arquivo .env")
    st.stop()

class AstraDBClient:
    def __init__(self):
        self.base_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{ASTRA_DB_NAMESPACE}"
        self.headers = {
            "Content-Type": "application/json",
            "x-cassandra-token": ASTRA_DB_APPLICATION_TOKEN,
            "Accept": "application/json"
        }
    
    def vector_search(self, vector: List[float], limit: int = 3) -> List[Dict]:
        """Realiza busca por similaridade vetorial"""
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
# FUNÇÕES DO CHATBOT RAG
# ==============================================
def get_embedding(text: str) -> List[float]:
    """Obtém embedding do texto usando OpenAI"""
    try:
        response = client_openai.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        st.error(f"Erro ao obter embedding: {str(e)}")
        return []

def generate_response(query: str, context: str) -> str:
    """Gera resposta usando o modelo de chat da OpenAI"""
    if not context:
        return "Não encontrei informações relevantes para responder sua pergunta."
    
    prompt = f"""Responda baseado no contexto abaixo:
    
    Contexto:
    {context}
    
    Pergunta: {query}
    Resposta:"""
    
    try:
        response = client_openai.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": '''
                Você é um assistente especializado em manutenção industrial. Responda às perguntas de forma clara e técnica,
                baseando-se sempre nos manuais e documentação disponível.
                '''},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao gerar resposta: {str(e)}"

# ==============================================
# FUNÇÕES PARA RELATÓRIOS DE MANUTENÇÃO
# ==============================================
def criar_relatorio():
    st.subheader("Novo Relatório de Manutenção")
    
    with st.form(key='form_relatorio'):
        # Identificação do técnico
        st.markdown("### Identificação")
        tecnico = st.text_input("Nome do Técnico", max_chars=100, key="tecnico_nome")
        
        # Dados do equipamento
        st.markdown("### Dados do Equipamento")
        equipamento = st.text_input("Equipamento", max_chars=100, key="equipamento_nome")
        horimetro = st.number_input("Horímetro (horas)", min_value=0.0, format="%.1f", key="horimetro_valor")
        
        # Tipo de manutenção
        st.markdown("### Tipo de Manutenção")
        tipo_manutencao = st.selectbox(
            "Tipo de Manutenção",
            ["Preventiva", "Corretiva", "Lubrificação", "Inspeção"],
            index=0,
            key="tipo_manutencao_select"
        )
        
        # Data da manutenção
        data_manutencao = st.date_input("Data da Manutenção", value=datetime.date.today(), key="data_manutencao_input")
        
        # Detalhes da manutenção
        st.markdown("### Detalhes da Manutenção")
        motivo = st.text_area("Motivo da Manutenção", height=100, key="motivo_texto")
        descricao = st.text_area("Descrição do Serviço Realizado", height=150, key="descricao_texto")
        observacoes = st.text_area("Observações Adicionais", height=100, key="observacoes_texto")
        
        # Botão de envio
        submitted = st.form_submit_button("Salvar Relatório")
        
        if submitted:
            if not tecnico or not equipamento or not motivo or not descricao:
                st.error("Preencha todos os campos obrigatórios!")
            else:
                relatorio = {
                    "tecnico": tecnico,
                    "equipamento": equipamento,
                    "horimetro": horimetro,
                    "tipo_manutencao": tipo_manutencao,
                    "data_manutencao": datetime.datetime.combine(data_manutencao, datetime.datetime.min.time()),
                    "motivo": motivo,
                    "descricao": descricao,
                    "observacoes": observacoes,
                    "data_criacao": datetime.datetime.now(),
                    "ultima_atualizacao": datetime.datetime.now()
                }
                
                try:
                    result = relatorios_collection.insert_one(relatorio)
                    st.success("Relatório salvo com sucesso!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erro ao salvar relatório: {str(e)}")

def visualizar_relatorios():
    st.subheader("Relatórios de Manutenção")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_tecnico = st.text_input("Filtrar por técnico", key="filtro_tecnico")
    with col2:
        filtro_equipamento = st.text_input("Filtrar por equipamento", key="filtro_equipamento")
    with col3:
        filtro_tipo = st.selectbox(
            "Filtrar por tipo",
            ["Todos"] + ["Preventiva", "Corretiva", "Lubrificação", "Inspeção"],
            key="filtro_tipo_select"
        )
    
    # Construir query
    query = {}
    if filtro_tecnico:
        query["tecnico"] = {"$regex": filtro_tecnico, "$options": "i"}
    if filtro_equipamento:
        query["equipamento"] = {"$regex": filtro_equipamento, "$options": "i"}
    if filtro_tipo != "Todos":
        query["tipo_manutencao"] = filtro_tipo
    
    try:
        # Buscar relatórios (ordenados por data decrescente)
        relatorios = list(relatorios_collection.find(query).sort("data_manutencao", -1))
        
        if not relatorios:
            st.info("Nenhum relatório encontrado com os filtros selecionados")
        else:
            for relatorio in relatorios:
                with st.expander(f"{relatorio['equipamento']} - {relatorio['tipo_manutencao']} ({relatorio['data_manutencao'].strftime('%d/%m/%Y')})"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**Técnico:** {relatorio['tecnico']}")
                        st.markdown(f"**Equipamento:** {relatorio['equipamento']}")
                        st.markdown(f"**Horímetro:** {relatorio['horimetro']} horas")
                        st.markdown(f"**Tipo de Manutenção:** {relatorio['tipo_manutencao']}")
                        st.markdown(f"**Data da Manutenção:** {relatorio['data_manutencao'].strftime('%d/%m/%Y')}")
                        st.markdown(f"**Motivo:** {relatorio['motivo']}")
                        st.markdown(f"**Descrição:** {relatorio['descricao']}")
                        if relatorio.get('observacoes'):
                            st.markdown(f"**Observações:** {relatorio['observacoes']}")
                    
                    with col2:
                        # Botão para editar
                        if st.button("✏️ Editar", key=f"edit_{relatorio['_id']}"):
                            st.session_state['editar_id'] = str(relatorio['_id'])
                            st.session_state['editar_relatorio'] = relatorio
                            st.rerun()
                        
                        # Botão para deletar
                        if st.button("🗑️ Excluir", key=f"del_{relatorio['_id']}"):
                            relatorios_collection.delete_one({"_id": relatorio['_id']})
                            st.rerun()
    except Exception as e:
        st.error(f"Erro ao buscar relatórios: {str(e)}")

def editar_relatorio():
    if 'editar_id' not in st.session_state:
        st.warning("Nenhum relatório selecionado para edição")
        return
    
    relatorio = st.session_state['editar_relatorio']
    st.subheader(f"Editando Relatório: {relatorio['equipamento']}")
    
    with st.form(key='form_editar_relatorio'):
        # Identificação do técnico
        st.markdown("### Identificação")
        tecnico = st.text_input("Nome do Técnico", value=relatorio['tecnico'], max_chars=100, key="edit_tecnico")
        
        # Dados do equipamento
        st.markdown("### Dados do Equipamento")
        equipamento = st.text_input("Equipamento", value=relatorio['equipamento'], max_chars=100, key="edit_equipamento")
        horimetro = st.number_input("Horímetro (horas)", value=relatorio['horimetro'], min_value=0.0, format="%.1f", key="edit_horimetro")
        
        # Tipo de manutenção
        st.markdown("### Tipo de Manutenção")
        tipo_manutencao = st.selectbox(
            "Tipo de Manutenção",
            ["Preventiva", "Corretiva", "Lubrificação", "Inspeção"],
            index=["Preventiva", "Corretiva", "Lubrificação", "Inspeção"].index(relatorio['tipo_manutencao']),
            key="edit_tipo_manutencao"
        )
        
        # Data da manutenção
        data_manutencao = st.date_input(
            "Data da Manutenção", 
            value=relatorio['data_manutencao'].date(),
            key="edit_data_manutencao"
        )
        
        # Detalhes da manutenção
        st.markdown("### Detalhes da Manutenção")
        motivo = st.text_area("Motivo da Manutenção", value=relatorio['motivo'], height=100, key="edit_motivo")
        descricao = st.text_area("Descrição do Serviço Realizado", value=relatorio['descricao'], height=150, key="edit_descricao")
        observacoes = st.text_area("Observações Adicionais", value=relatorio.get('observacoes', ''), height=100, key="edit_observacoes")
        
        # Botões
        col1, col2, col3 = st.columns(3)
        with col1:
            submitted = st.form_submit_button("Salvar Alterações")
        with col2:
            if st.form_submit_button("Cancelar"):
                del st.session_state['editar_id']
                del st.session_state['editar_relatorio']
                st.rerun()
        
        if submitted:
            if not tecnico or not equipamento or not motivo or not descricao:
                st.error("Preencha todos os campos obrigatórios!")
            else:
                relatorio_atualizado = {
                    "$set": {
                        "tecnico": tecnico,
                        "equipamento": equipamento,
                        "horimetro": horimetro,
                        "tipo_manutencao": tipo_manutencao,
                        "data_manutencao": datetime.datetime.combine(data_manutencao, datetime.datetime.min.time()),
                        "motivo": motivo,
                        "descricao": descricao,
                        "observacoes": observacoes,
                        "ultima_atualizacao": datetime.datetime.now()
                    }
                }
                
                try:
                    relatorios_collection.update_one(
                        {"_id": relatorio['_id']},
                        relatorio_atualizado
                    )
                    st.success("Relatório atualizado com sucesso!")
                    del st.session_state['editar_id']
                    del st.session_state['editar_relatorio']
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar relatório: {str(e)}")

# ==============================================
# CHATBOT RAG
# ==============================================
def chatbot_rag():
    st.title("Assistente de Manutenção")
    st.write("Chatbot especializado em manutenção industrial")
    
    # Inicializa cliente do Astra DB
    astra_client = AstraDBClient()
    
    # Inicializa histórico de conversa
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Exibe mensagens anteriores
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Processa nova entrada
    if prompt := st.chat_input("Digite sua pergunta sobre manutenção..."):
        # Adiciona mensagem do usuário ao histórico
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Obtém embedding e busca no Astra DB
        embedding = get_embedding(prompt)
        if embedding:
            results = astra_client.vector_search(embedding)
            context = "\n".join([str(doc) for doc in results])
            
            # Gera resposta
            response = generate_response(prompt, context)
            
            # Adiciona resposta ao histórico
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)

# ==============================================
# INTERFACE PRINCIPAL
# ==============================================
def main():
    tab1, tab2, tab3 = st.tabs(["Chatbot RAG", "Relatórios de Manutenção", "Visualizar Relatórios"])
    
    with tab1:
        chatbot_rag()
    
    with tab2:
        if 'editar_id' in st.session_state:
            editar_relatorio()
        else:
            criar_relatorio()
    
    with tab3:
        visualizar_relatorios()

if __name__ == "__main__":
    main()
