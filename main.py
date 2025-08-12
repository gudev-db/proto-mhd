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

def generate_response(query: str, context: str, conversation_history: List[Dict]) -> str:
    """Generate response using OpenAI chat model"""
    if not context:
        context = "Não encontrei informações relevantes no banco de dados."
    
    # Get maintenance reports and checklists from MongoDB
    reports = list(relatorios_collection.find().sort("maintenance_date", -1).limit(5))
    checklists = list(checklists_collection.find().sort("execution_date", -1).limit(5))
    
    # Format reports and checklists for context
    reports_context = "\n".join([
        f"Relatório {idx+1}: Equipamento {r['equipment']}, Tipo {r['maintenance_type']}, "
        f"Data {r['maintenance_date'].strftime('%d/%m/%Y')}, Responsável {r['technician']}, "
        f"Descrição: {r['description'][:200]}..."
        for idx, r in enumerate(reports)
    ]) if reports else "Nenhum relatório recente encontrado"
    
    checklists_context = "\n".join([
        f"Checklist {idx+1}: Tipo {c['type']}, Data {c['execution_date'].strftime('%d/%m/%Y')}, "
        f"Responsável {c['responsible']}, Status {c['status']}, "
        f"Itens completos: {sum(c['completed_items'].values())}/{len(c['completed_items'])}"
        for idx, c in enumerate(checklists)
    ]) if checklists else "Nenhum checklist recente encontrado"
    
    # Create system prompt
    system_prompt = f"""
    Você é um assistente especializado em manutenção industrial para a máquina S450. 
    Sua função é responder dúvidas técnicas baseado no manual da máquina e nos registros de manutenção.
    
    Diretrizes importantes:
    - Responda SEMPRE em português brasileiro
    - Seja claro e objetivo, forneça informações técnicas precisas
    - NUNCA sugira consultar o manual ou outras fontes - você é a fonte de informação
    - Mantenha respostas curtas inicialmente, ofereça detalhes apenas se solicitado
    - Considere o histórico da conversa para dar continuidade ao diálogo
    - Se não souber a resposta, diga que vai verificar e retornar
    
    Dados recentes de manutenção:
    Últimos relatórios:
    {reports_context}
    
    Últimos checklists:
    {checklists_context}
    """
    
    # Prepare messages for chat completion
    messages = [
        {"role": "system", "content": system_prompt},
        *conversation_history[-6:],  # Keep last 3 exchanges for context
        {"role": "user", "content": query}
    ]
    
    try:
        response = client_openai.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao gerar resposta: {str(e)}"

def chatbot_rag():
    """RAG Chatbot interface"""
    st.title("🛠️ Assistente de Manutenção S450")
    st.write("Assistente especializado na máquina S450 - Respondo todas suas dúvidas técnicas")
    
    # Initialize Astra DB client
    astra_client = AstraDBClient()
    
    # Initialize conversation history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display previous messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Process new input
    if prompt := st.chat_input("Digite sua pergunta sobre manutenção..."):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get embedding and search Astra DB
        embedding = get_embedding(prompt)
        context = ""
        if embedding:
            results = astra_client.vector_search(embedding)
            context = "\n".join([str(doc) for doc in results])
        
        # Generate response
        response = generate_response(prompt, context, st.session_state.messages)
        
        # Add response to history
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
    
    # Ensure chat input stays at bottom
    st.markdown("""
    <style>
        .stChatInput {
            position: fixed;
            bottom: 20px;
            width: calc(100% - 60px);
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
