import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import time
import plotly.express as px

# --- Configuración de la Página ---
st.set_page_config(page_title="Planificador de Almacén", layout="wide", page_icon="📦")

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

# --- Gestión del Estado ---
if 'asignaciones' not in st.session_state:
    st.session_state.asignaciones = []

if 'fecha_plan' not in st.session_state:
    st.session_state.fecha_plan = date.today()

# --- Funciones ---
def agregar_tarea(tecnico, tarea, hora_inicio, hora_fin, notas):
    if hora_inicio >= hora_fin:
        st.error("⚠️ La hora de inicio debe ser anterior a la hora de fin.")
        return

    inicio_dt = datetime.combine(st.session_state.fecha_plan, hora_inicio)
    fin_dt = datetime.combine(st.session_state.fecha_plan, hora_fin)

    entrada = {
        "Técnico": tecnico,
        "Tarea": tarea,
        "Inicio": inicio_dt,
        "Fin": fin_dt,
        "Notas": notas
    }
    
    st.session_state.asignaciones.append(entrada)
    st.success(f"Asignado: {tarea} a {tecnico}")
    time.sleep(0.5)
    st.rerun()

def limpiar_dia():
    st.session_state.asignaciones = []
    st.rerun()

def eliminar_ultima_asignacion():
    if st.session_state.asignaciones:
        st.session_state.asignaciones.pop()
        st.rerun()

# --- Interfaz Gráfica ---

st.title("🏭 Planificador Visual de Almacén")

# Selector de fecha
col_fecha, col_blank = st.columns([1, 4])
with col_fecha:
    nueva_fecha = st.date_input("Fecha de Planificación", value=st.session_state.fecha_plan)
    if nueva_fecha != st.session_state.fecha_plan:
        st.session_state.fecha_plan = nueva_fecha
        # limpiar_dia() # Descomentar si se quiere limpiar al cambiar fecha

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
            # Hora inicio por defecto: 07:45 AM
            h_inicio = st.time_input("Inicio", value=datetime.strptime("07:45", "%H:%M").time())
        with c2:
            # Hora fin por defecto: 04:45 PM (16:45)
            h_fin = st.time_input("Fin", value=datetime.strptime("16:45", "%H:%M").time())
            
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

    # Preparamos el DataFrame. Si está vacío, creamos uno con la estructura correcta pero sin datos
    # para que el gráfico se renderice con los nombres vacíos.
    if not st.session_state.asignaciones:
        df = pd.DataFrame(columns=["Técnico", "Tarea", "Inicio", "Fin", "Notas"])
        st.info("Comienza asignando tareas desde el panel izquierdo.")
    else:
        df = pd.DataFrame(st.session_state.asignaciones)

    # Configuración del Gráfico
    # Truco: Si no hay datos, agregamos una fila "invisible" para inicializar el gráfico si fuera necesario,
    # pero Plotly maneja DataFrames vacíos si definimos los ejes.
    
    fig = px.timeline(
        df, 
        x_start="Inicio", 
        x_end="Fin", 
        y="Técnico", 
        color="Tarea",
        text="Tarea",
        hover_data=["Notas"],
        height=500, # Altura fija para que se vean bien los 9 técnicos
        title=f"Programación: {st.session_state.fecha_plan.strftime('%d/%m/%Y')}"
    )
    
    # Definir límites del eje X (De 7:00 AM a 9:00 PM para ver todo el rango posible)
    inicio_dia = datetime.combine(st.session_state.fecha_plan, datetime.strptime("07:00", "%H:%M").time())
    fin_dia = datetime.combine(st.session_state.fecha_plan, datetime.strptime("21:00", "%H:%M").time())

    fig.update_layout(
        xaxis_range=[inicio_dia, fin_dia], # Fija el rango visual
        xaxis=dict(
            title="Horario (07:45 AM - 08:30 PM)",
            tickformat="%H:%M",
            dtick=3600000.0, # Grid cada hora
            side="top" # Poner las horas arriba como en la imagen de referencia
        ),
        yaxis=dict(
            title="",
            categoryorder="array", 
            categoryarray=LISTA_TECNICOS[::-1] # Invertimos lista para que el 1ro salga arriba
        ),
        showlegend=True,
        bargap=0.1
    )
    
    fig.update_traces(textposition='inside', insidetextanchor='middle')

    # Forzar que aparezcan todos los nombres en el eje Y incluso si no tienen tareas
    # (Plotly a veces oculta categorías vacías, esto ayuda a mantener la estructura)
    fig.update_yaxes(type='category')

    st.plotly_chart(fig, use_container_width=True)

    # --- Tabla Detallada ---
    if not df.empty:
        with st.expander("Ver Detalle y Exportar"):
            st.dataframe(df.assign(
                Inicio=df["Inicio"].dt.strftime("%H:%M"),
                Fin=df["Fin"].dt.strftime("%H:%M")
            ), use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar Reporte Diario (CSV)", data=csv, file_name=f"plan_{st.session_state.fecha_plan}.csv", mime='text/csv')