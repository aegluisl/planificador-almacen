import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, time as time_module
import time
import plotly.express as px
import uuid 
import json 

# --- FIREBASE & AUTH IMPORTS ---
try:
    # Intenta importar firebase_admin
    from firebase_admin import initialize_app, credentials, firestore, auth

    if not st.session_state.get('firebase_initialized', False):
        try:
            # 1. Intentar cargar las credenciales de Firebase desde los secretos de Streamlit
            if "FIREBASE_KEY" in st.secrets:
                
                # --- Lógica CRUCIAL para leer el secreto en formato TOML de campo por campo ---
                creds_dict = {
                    "type": st.secrets.FIREBASE_KEY.type,
                    "project_id": st.secrets.FIREBASE_KEY.project_id,
                    "private_key_id": st.secrets.FIREBASE_KEY.private_key_id,
                    "private_key": st.secrets.FIREBASE_KEY.private_key, # El TOML maneja bien los saltos de línea aquí
                    "client_email": st.secrets.FIREBASE_KEY.client_email,
                    "client_id": st.secrets.FIREBASE_KEY.client_id,
                    "auth_uri": st.secrets.FIREBASE_KEY.auth_uri,
                    "token_uri": st.secrets.FIREBASE_KEY.token_uri,
                    "auth_provider_x509_cert_url": st.secrets.FIREBASE_KEY.auth_provider_x509_cert_url,
                    "client_x509_cert_url": st.secrets.FIREBASE_KEY.client_x509_cert_url,
                    "universe_domain": st.secrets.FIREBASE_KEY.universe_domain
                }
                
                # Crear las credenciales de Firebase a partir del diccionario
                cred = credentials.Certificate(creds_dict)
                initialize_app(cred)
                db = firestore.client()
                st.session_state.db_online = True
                st.session_state.firebase_initialized = True
            
            else:
                 # Si los secretos no están configurados (Entorno de Canvas o local sin secretos)
                try:
                    # Intentar usar la inicialización global de Canvas
                    db = firestore.client()
                    st.session_state.db_online = True
                except:
                    # Fallback si Firebase no está disponible.
                    st.warning("Firebase no detectado. La aplicación funcionará, pero los datos NO serán persistentes ni compartidos.")
                    class MockDB:
                        def collection(self, path): return self
                        def document(self, doc_id): return self
                        def get(self): return type('', (object,), {'exists': False})() 
                        def set(self, data): pass
                        def on_snapshot(self, callback): pass
                    db = MockDB()
                    st.session_state.db_online = False

        except Exception as e:
            st.error(f"Error al inicializar Firebase con Secretos: {e}. ¿El formato TOML es correcto?")
            st.session_state.db_online = False

    else:
        # Ya inicializado, obtener la referencia
        db = firestore.client() if st.session_state.get('db_online', False) else None
        
except ImportError:
    st.warning("La librería `firebase_admin` no está instalada o disponible. La aplicación funcionará, pero los datos NO serán persistentes ni compartidos.")
    st.session_state.db_online = False

# --- Configuración de la Página ---
st.set_page_config(page_title="Planificador de Almacén", layout="wide", page_icon="📦")

# --- Constantes de Firestore ---
COLLECTION_PATH = "planificacion_almacen_tareas" 
DOCUMENT_ID_PREFIX = "plan_"

# --- Datos Maestros ---
LISTA_TAREAS = [
    "Carga de Transportistas",
    "Recepción de Importación",
    "Recepción de Primax",
    "Cambio de aceite",
    "Proveedores",
    "Asignación de ubicaciones",
    "Inventario de Ubicaciones",
    "Inventario de Lubricantes",
    "Ordenamiento",
    "Picking Taller",
    "Picking Mostrador",
    "Picking Sucursales",
    "Embalaje Sucursales",
    "Desembalaje Importaciones",
    "Ubicación Importaciones",
    "Devoluciones Sucursales",
    "Ubicación Devoluciones Sucursales",
    "Devoluciones Taller",
    "Inventario Cíclico",
    "Inventario Repuestos Controlados",
    "Atención Cores"
]

# Nombres reales de los técnicos
LISTA_TECNICOS = [
    "GEORGE GAMARRA",
    "LEIDY YUPANQUI",
    "ALDO SULCA",
    "LUIS DELGADO",
    "JHONY CONDE",
    "GIANCARLO BEGAZOS",
    "MANUEL AYACHI",
    "ALEXANDRA MILLA",
    "LEONEL RODRIGUEZ"
]

# --- Gestión del Estado (Streamlit & Firestore) ---
if 'asignaciones' not in st.session_state:
    st.session_state.asignaciones = []

if 'fecha_plan' not in st.session_state:
    st.session_state.fecha_plan = date.today()

# --- Funciones de Firestore ---
def get_doc_id(target_date):
    """Genera el ID del documento basado en la fecha."""
    return f"{DOCUMENT_ID_PREFIX}{target_date.strftime('%Y%m%d')}"

@st.cache_data(show_spinner="Cargando plan desde la nube...")
def load_plan_from_firestore(target_date):
    """Carga las asignaciones para la fecha dada desde Firestore."""
    if not st.session_state.get('db_online', False) or db is None:
        return []

    doc_id = get_doc_id(target_date)
    doc_ref = db.collection(COLLECTION_PATH).document(doc_id)
    doc = doc_ref.get()

    if doc.exists:
        data = doc.to_dict()
        loaded_asignaciones = []
        for entry in data.get('tasks', []):
            # Convertir string de hora a datetime.time y agregar el ID
            try:
                entry["Inicio"] = datetime.strptime(entry["Inicio"], "%H:%M:%S").time()
                entry["Fin"] = datetime.strptime(entry["Fin"], "%H:%M:%S").time()
                # Asegurar que siempre haya un ID (para compatibilidad con datos viejos)
                if 'ID' not in entry:
                    entry['ID'] = str(uuid.uuid4()) 
                
                if "Fecha" in entry: # Limpiar si existe, no queremos error de clave
                    del entry["Fecha"] 
                loaded_asignaciones.append(entry)
            except Exception as e:
                # Omitir entradas con formato de hora incorrecto
                st.warning(f"Error al cargar tarea con ID {entry.get('ID', 'N/A')}: {e}")
                continue
        
        return loaded_asignaciones
    return []

def save_plan_to_firestore(asignaciones, target_date):
    """Guarda las asignaciones actuales en Firestore."""
    if not st.session_state.get('db_online', False) or db is None:
        return

    doc_id = get_doc_id(target_date)
    doc_ref = db.collection(COLLECTION_PATH).document(doc_id)

    # Convertir objetos datetime.time a strings para serialización JSON en Firestore
    saveable_tasks = []
    for entry in asignaciones:
        saveable_tasks.append({
            "ID": entry.get("ID"), # Guardar el ID
            "Técnico": entry["Técnico"],
            "Tarea": entry["Tarea"],
            "Inicio": entry["Inicio"].strftime("%H:%M:%S"),
            "Fin": entry["Fin"].strftime("%H:%M:%S"),
            "Notas": entry["Notas"],
            "Fecha": target_date.isoformat() 
        })

    try:
        doc_ref.set({"tasks": saveable_tasks, "updated_at": datetime.now()})
        st.toast("✅ Plan guardado en la nube.")
    except Exception as e:
        st.error(f"Error al guardar en Firestore: {e}")


# --- Funciones de Lógica de la Aplicación ---
def agregar_tarea(tecnico, tarea, hora_inicio, hora_fin, notas):
    if hora_inicio >= hora_fin:
        st.error("⚠️ La hora de inicio debe ser anterior a la hora de fin.")
        return

    entrada = {
        "ID": str(uuid.uuid4()), # Nuevo ID único
        "Técnico": tecnico,
        "Tarea": tarea,
        "Inicio": hora_inicio, 
        "Fin": hora_fin,
        "Notas": notas
    }
    
    st.session_state.asignaciones.append(entrada)
    
    # Guardar en la nube inmediatamente después de agregar
    save_plan_to_firestore(st.session_state.asignaciones, st.session_state.fecha_plan)

    st.success(f"Asignado: {tarea} a {tecnico}")
    st.cache_data.clear() # Limpia el caché para la próxima carga
    st.rerun()

def limpiar_dia():
    st.session_state.asignaciones = []
    save_plan_to_firestore(st.session_state.asignaciones, st.session_state.fecha_plan)
    st.cache_data.clear() 
    st.rerun()

def eliminar_ultima_asignacion():
    if st.session_state.asignaciones:
        st.session_state.asignaciones.pop()
        save_plan_to_firestore(st.session_state.asignaciones, st.session_state.fecha_plan)
        st.cache_data.clear() 
        st.rerun()

def handle_date_change(new_date):
    """Maneja la carga del plan al cambiar la fecha."""
    st.session_state.fecha_plan = new_date
    st.session_state.asignaciones = load_plan_from_firestore(new_date)
    st.session_state.data_loaded_for_date = new_date
    st.cache_data.clear()
    st.rerun()

# --- Inicialización/Recarga del Estado ---
if 'data_loaded_for_date' not in st.session_state or st.session_state.data_loaded_for_date != st.session_state.fecha_plan:
    st.session_state.asignaciones = load_plan_from_firestore(st.session_state.fecha_plan)
    st.session_state.data_loaded_for_date = st.session_state.fecha_plan

# --- Interfaz Gráfica ---

st.title("🏭 Planificador Visual de Almacén (NUBE)")
if st.session_state.get('db_online', False):
    st.markdown("**(Conectado a Firestore: Datos persistentes y compartidos)**")
else:
    st.warning("**(Almacenamiento LOCAL: Los datos se perderán al cerrar la aplicación)**")


# Selector de fecha
col_fecha, col_blank = st.columns([1, 4])
with col_fecha:
    nueva_fecha = st.date_input("Fecha de Planificación", value=st.session_state.fecha_plan)
    if nueva_fecha != st.session_state.fecha_plan:
        handle_date_change(nueva_fecha)

# Layout Principal
col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("1️⃣ Asignar Trabajo")
    st.info("Horario Regular: 07:45 - 16:45\nHoras Extra: Hasta 20:30")
    
    with st.form("formulario_asignacion"):
        seleccion_tecnico = st.selectbox("Técnico", LISTA_TECNICOS)
        seleccion_tarea = st.selectbox("Tarea", LISTA_TAREAS)
        
        c1, c2 = st.columns(2)
        with c1:
            h_inicio = st.time_input("Inicio", value=time_module(7, 45))
        with c2:
            h_fin = st.time_input("Fin", value=time_module(16, 45))
            
        notas_adicionales = st.text_input("Notas", placeholder="Ej: Prioridad alta")
        
        boton_asignar = st.form_submit_button("➕ Añadir Bloque", type="primary")
        
        if boton_asignar:
            agregar_tarea(seleccion_tecnico, seleccion_tarea, h_inicio, h_fin, notas_adicionales)

    st.markdown("### Acciones")
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("↩️ Deshacer"):
            eliminar_ultima_asignacion()
    with col_act2:
        if st.button("🗑️ Limpiar Todo"):
            limpiar_dia()

with col2:
    st.subheader("2️⃣ Cronograma de Operaciones")

    # Preparar el DataFrame para Plotly
    if not st.session_state.asignaciones:
        df = pd.DataFrame(columns=["ID", "Técnico", "Tarea", "Inicio", "Fin", "Notas"])
        st.info("Comienza asignando tareas desde el panel izquierdo.")
    else:
        # Convertir objetos time de la sesión a objetos datetime para Plotly
        df = pd.DataFrame([{
            "ID": entry["ID"],
            "Técnico": entry["Técnico"],
            "Tarea": entry["Tarea"],
            "Inicio": datetime.combine(st.session_state.fecha_plan, entry["Inicio"]),
            "Fin": datetime.combine(st.session_state.fecha_plan, entry["Fin"]),
            "Notas": entry["Notas"],
        } for entry in st.session_state.asignaciones])
        
    # Configuración del Gráfico
    fig = px.timeline(
        df, 
        x_start="Inicio", 
        x_end="Fin", 
        y="Técnico", 
        color="Tarea",
        text="Tarea",
        hover_data=["Notas"],
        height=500,
        title=f"Programación: {st.session_state.fecha_plan.strftime('%d/%m/%Y')}"
    )
    
    # Definir límites del eje X
    inicio_dia = datetime.combine(st.session_state.fecha_plan, time_module(7, 0)) # 7:00 AM
    fin_dia = datetime.combine(st.session_state.fecha_plan, time_module(21, 0)) # 9:00 PM (21:00)

    fig.update_layout(
        xaxis_range=[inicio_dia, fin_dia],
        xaxis=dict(
            title="Horario (07:45 AM - 08:30 PM)",
            tickformat="%H:%M",
            dtick=3600000.0,
            side="top"
        ),
        yaxis=dict(
            title="",
            categoryorder="array", 
            categoryarray=LISTA_TECNICOS[::-1]
        ),
        showlegend=True,
        bargap=0.1
    )
    
    fig.update_traces(textposition='inside', insidetextanchor='middle')

    fig.update_yaxes(type='category')

    st.plotly_chart(fig, use_container_width=True)

    # --- Tabla Detallada y Edición (Sección clave para tu solicitud) ---
    if not df.empty:
        with st.expander("📝 Editar y Exportar Plan"):
            st.markdown("---")
            st.markdown("**Para editar o eliminar:** Haz doble clic en una celda para modificarla, o haz clic en el número de fila y luego en el icono de la papelera (🗑️) para eliminar la tarea. Los cambios se guardarán automáticamente.")
            
            # 1. Crear un DataFrame con IDs y tiempos en formato string para el editor
            df_editable = pd.DataFrame(st.session_state.asignaciones)
            df_editable['Inicio'] = df_editable['Inicio'].apply(lambda t: t.strftime("%H:%M"))
            df_editable['Fin'] = df_editable['Fin'].apply(lambda t: t.strftime("%H:%M"))
            
            # Reordenar columnas para mejor vista
            df_editable = df_editable[['ID', 'Técnico', 'Tarea', 'Inicio', 'Fin', 'Notas']]
            
            # Configuración para hacer el ID invisible al usuario y establecer selectbox
            column_config = {
                "ID": st.column_config.Column("ID", disabled=True, width="extra-small", help="Identificador único de la tarea (no editable)"),
                "Técnico": st.column_config.SelectboxColumn("Técnico", options=LISTA_TECNICOS),
                "Tarea": st.column_config.SelectboxColumn("Tarea", options=LISTA_TAREAS),
                "Inicio": st.column_config.TextColumn("Inicio (HH:MM)", help="Formato de 24 horas (ej. 14:30)"),
                "Fin": st.column_config.TextColumn("Fin (HH:MM)", help="Formato de 24 horas (ej. 16:45)"),
            }

            # 2. El editor de datos
            edited_df = st.data_editor(
                df_editable,
                column_config=column_config,
                hide_index=False, # Necesario para la eliminación (se hace clic en el índice)
                key="data_editor_tareas",
                use_container_width=True
            )
            
            # 3. Detectar cambios y guardar
            # Comparar el DataFrame editado con el que se mostró originalmente (df_editable)
            if not edited_df.equals(df_editable):
                
                # Proceso para reconstruir la lista de asignaciones
                new_asignaciones = []
                valid_change = True

                for index, row in edited_df.iterrows():
                    # st.data_editor permite añadir filas vacías, las ignoramos.
                    if pd.isna(row['Técnico']) or pd.isna(row['Tarea']):
                        continue
                        
                    try:
                        # Convertir strings de hora de vuelta a datetime.time
                        inicio_time = datetime.strptime(row['Inicio'], "%H:%M").time()
                        fin_time = datetime.strptime(row['Fin'], "%H:%M").time()

                        if inicio_time >= fin_time:
                            st.warning(f"Error de horario en la fila {index+1} ({row['Técnico']}): La hora de fin debe ser posterior a la de inicio. NO GUARDADO.")
                            valid_change = False
                            continue 
                        
                        new_asignaciones.append({
                            "ID": row["ID"],
                            "Técnico": row["Técnico"],
                            "Tarea": row["Tarea"],
                            "Inicio": inicio_time,
                            "Fin": fin_time,
                            "Notas": row["Notas"]
                        })

                    except ValueError:
                         st.warning(f"Error de formato de hora en la fila {index+1} ({row['Técnico']}). Usa el formato HH:MM (ej. 15:30). NO GUARDADO.")
                         valid_change = False
                         continue

                # Si no hubo errores de validación, guardar y recargar
                if valid_change:
                    st.session_state.asignaciones = new_asignaciones
                    save_plan_to_firestore(st.session_state.asignaciones, st.session_state.fecha_plan)
                    st.cache_data.clear() 
                    st.rerun() # Forzar la recarga del gráfico

            # Botón descargar (usa el DataFrame ya generado `df`)
            st.markdown("---")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar Reporte Diario (CSV)", data=csv, file_name=f"plan_{st.session_state.fecha_plan}.csv", mime='text/csv')