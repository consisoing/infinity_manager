import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta

# Servicios y Configuración
from src.services.data_service import (
    log_activity, 
    get_sales_data, 
    get_branch_goal, 
    update_own_record, 
    verify_user_password,
    delete_sales_record # Necesario para borrar
)
from src.services.pdf_service import generate_pdf_report
from src.config.settings import BRANCH_CONFIG

def render_sales(user):
    # Diccionario para capturar gráficos para el PDF
    report_figures = {}
    
    # Datos del usuario y sucursal
    branch_key = user['branch']
    branch_info = BRANCH_CONFIG.get(branch_key, {})
    branch_name = branch_info.get('name', branch_key)
    
    st.title(f"🚀 Panel Operativo: {branch_name}")
    st.caption(f"Bienvenido, {user['full_name']} | Rol: Cazador de Negocios")

    # ==============================================================================
    # 1. FILTROS DE TIEMPO
    # ==============================================================================
    st.sidebar.markdown("### 📅 Filtro de Tiempo")
    today = datetime.now()
    default_start = today.replace(day=1) # Inicio de mes por defecto
    
    date_range = st.sidebar.date_input("Rango de Fecha", value=(default_start, today), format="DD/MM/YYYY")
    
    if not (isinstance(date_range, tuple) and len(date_range) == 2):
        st.sidebar.warning("Selecciona fecha fin.")
        return

    start_d, end_d = date_range
    end_d_str = f"{end_d} 23:59:59"

    # ==============================================================================
    # 2. DATOS Y METAS
    # ==============================================================================
    # Obtener datos SOLO de su sucursal
    df = get_sales_data('sales', branch_key, start_date=start_d, end_date=end_d_str)
    
    # --- LIMPIEZA DE DATOS CRÍTICA ---
    existing_clients = []
    
    if not df.empty:
        # Asegurar tipos numéricos y fechas
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        
        # Corrección de fecha con soporte mixto
        df['created_at'] = pd.to_datetime(df['created_at'], format='mixed', errors='coerce')
        df['date_only'] = df['created_at'].dt.date.fillna(datetime.now().date())
        
        # Limpieza de textos
        df['description'] = df['description'].astype(str).fillna("")
        
        # Lista para el selector de clientes
        raw_clients = df['client_name'].dropna().unique().tolist()
        existing_clients = sorted([c for c in raw_clients if c != "Desconocido" and c.strip() != ""])

    # Obtener Metas de la Base de Datos
    goals = get_branch_goal(branch_key)
    
    # Proyección Temporal (Ajuste de metas por días seleccionados)
    days_in_period = (end_d - start_d).days + 1
    if days_in_period < 1: days_in_period = 1
    time_factor = days_in_period / 30.0

    target_amount = goals['amount'] * time_factor
    target_clients = int(goals['clients'] * time_factor)
    target_meetings = int(goals['meetings'] * time_factor)
    target_products = int(goals['products'] * time_factor)

    # ==============================================================================
    # 3. KPIs OPERATIVOS
    # ==============================================================================
    real_rev = 0.0; real_clients = 0; real_meetings = 0; real_products = 0; pipeline = 0.0

    if not df.empty:
        # 1. Facturación (Solo tipo Venta)
        real_rev = df[df['activity_type'] == 'Venta']['amount'].sum()
        
        # 2. Clientes
        real_clients = df['client_name'].nunique()
        
        # 3. Reuniones
        real_meetings = len(df[df['activity_type'].str.contains("Reunión", case=False, na=False)])
        
        # 4. Productos
        # Filtro: Filas que NO son referencias financieras Y tienen cantidad > 0
        prod_rows = df[
            (~df['description'].str.contains("Ref:|Pedido de venta", case=False, na=False)) &
            (df['quantity'] > 0)
        ]
        real_products = int(prod_rows['quantity'].sum())
        
        # 5. Pipeline
        pipeline = df[df['activity_type'].str.contains("Oportunidad", case=False, na=False)]['amount'].sum()

    # Cálculo de Deltas
    delta_rev = real_rev - target_amount
    delta_clients = real_clients - target_clients
    delta_meetings = real_meetings - target_meetings
    delta_products = real_products - target_products

    # Visualización
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Ventas Cerradas", f"${real_rev:,.2f}", f"{delta_rev:,.2f} vs Meta", delta_color="normal")
    k2.metric("👥 Clientes Atendidos", real_clients, f"{delta_clients} vs Meta ({target_clients})")
    k3.metric("🤝 Reuniones", real_meetings, f"{delta_meetings} vs Meta ({target_meetings})")
    k4.metric("📦 Productos", real_products, f"{delta_products} vs Meta ({target_products})")
    
    prog_pct = min(real_rev / goals['amount'], 1.0) if goals['amount'] > 0 else 0
    st.progress(prog_pct, text=f"Progreso Mensual Global: {prog_pct*100:.1f}%")
    
    if pipeline > 0:
        st.info(f"🔮 Pipeline Activo: **${pipeline:,.2f}** en oportunidades detectadas.")

    st.divider()

    # ==============================================================================
    # 4. PESTAÑAS DE TRABAJO
    # ==============================================================================
    t_reg, t_stats, t_edit, t_pdf = st.tabs(["📝 Registrar Acción", "📊 Mis Estadísticas", "🛠️ Corregir Historial", "📄 Reporte PDF"])

    # ---------------- TAB 1: REGISTRO ----------------
    with t_reg:
        c_left, c_right = st.columns([1, 1])
        
        with c_left:
            with st.container(border=True):
                st.subheader("Nueva Actividad")
                with st.form("sales_activity_form"):
                    act_type = st.selectbox("Tipo de Acción", [
                        "Reunión Presencial", 
                        "Reunión Virtual", 
                        "Capacitación Técnica", 
                        "Oportunidad de Proyecto"
                    ])
                    
                    # Selector Híbrido
                    client_options = ["➕ Nuevo Cliente..."] + existing_clients
                    selected_client_opt = st.selectbox("Seleccionar Cliente / Empresa", client_options)
                    
                    final_client_name = ""
                    new_client_input = ""
                    
                    if selected_client_opt == "➕ Nuevo Cliente...":
                        new_client_input = st.text_input("Escribe el nombre del cliente nuevo:", placeholder="Ej. Procesadora Tío Pollo")
                    
                    # Campos
                    amount = 0.0; quantity = 1; notes = ""
                    
                    if "Reunión" in act_type:
                        notes = st.text_area("Resumen", placeholder="Acuerdos...")
                    elif "Capacitación" in act_type:
                        quantity = st.number_input("Asistentes", 1, 100, 5)
                        notes = st.text_area("Tema", placeholder="Fusión...")
                    elif "Oportunidad" in act_type:
                        amount = st.number_input("Valor Estimado ($)", 0.0)
                        notes = st.text_area("Detalles", placeholder="Descripción...")

                    st.markdown("---")
                    tag = st.radio("Estrategia", ["Mantenimiento", "Cacería", "Recuperación"], horizontal=True)
                    
                    if st.form_submit_button("💾 Registrar Gestión", type="primary"):
                        if selected_client_opt == "➕ Nuevo Cliente...":
                            final_client_name = new_client_input
                        else:
                            final_client_name = selected_client_opt

                        if final_client_name and len(final_client_name.strip()) > 0:
                            log_activity(user['username'], branch_key, final_client_name, amount, notes, act_type, tag, quantity)
                            st.success(f"Registrado para {final_client_name}"); time.sleep(1); st.rerun()
                        else:
                            st.error("⚠️ Nombre de cliente inválido.")

        with c_right:
            st.subheader("⏱️ Últimos Movimientos")
            if not df.empty:
                df['display_info'] = df.apply(
                    lambda x: f"${x['amount']:,.2f}" if "Oportunidad" in str(x['activity_type']) else str(x['description'])[:50], 
                    axis=1
                )
                st.dataframe(
                    df[['created_at', 'activity_type', 'client_name', 'display_info']].head(10),
                    column_config={"created_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YY HH:mm"), "activity_type": "Acción", "client_name": "Cliente", "display_info": "Info"},
                    hide_index=True, use_container_width=True
                )
            else:
                st.info("No has registrado nada en este periodo.")

    # ---------------- TAB 2: ESTADÍSTICAS (IGUAL AL ADMIN) ----------------
    with t_stats:
        if df.empty:
            st.warning("Sin datos para analizar.")
        else:
            c1, c2 = st.columns([1.2, 1.5])
            
            # --- SECCIÓN A: PARETO DE CLIENTES ---
            with c1:
                st.markdown("#### 🏆 Mis Mejores Clientes (Facturación)")
                sales_only = df[df['activity_type'] == 'Venta']
                if not sales_only.empty:
                    pareto = sales_only.groupby('client_name').agg({'amount':'sum'}).reset_index().sort_values('amount', ascending=False).head(10)
                    fig_p = px.bar(pareto, x='amount', y='client_name', orientation='h', text_auto='.2s', title="")
                    fig_p.update_layout(yaxis={'categoryorder':'total ascending', 'title': ''}, xaxis={'title': 'Monto ($)'})
                    st.plotly_chart(fig_p, use_container_width=True)
                    report_figures['pareto'] = fig_p
                else: st.caption("Sin ventas registradas.")

            # --- SECCIÓN B: ANÁLISIS DE PRODUCTOS (SOLUCIÓN DEFINITIVA) ---
            with c2:
                st.markdown("#### 📦 Análisis de Productos")
                
                # 1. Función de limpieza robusta
                def clean_product_name(text):
                    if not isinstance(text, str): return "Desconocido"
                    text = text.split("| SN:")[0]       # Quitar Serial
                    text = text.split("| Estado:")[0]   # Quitar Estado
                    
                    # Quitar códigos tipo [AC8]
                    if "]" in text and "[" in text:
                        try: text = text.split("]", 1)[1]
                        except: pass
                    return text.strip()

                # 2. Filtrar lo que NO es referencia de pedido
                df_prods_raw = df[~df['description'].str.contains("Ref:|Pedido de venta", case=False, na=False)].copy()

                if not df_prods_raw.empty:
                    df_prods_raw['clean_name'] = df_prods_raw['description'].apply(clean_product_name)
                    
                    # 3. SELECTOR DE CRITERIO (CLAVE PARA VER DATOS)
                    # Si no hay cantidades (inventario no cargado), usamos Dinero.
                    metric_opt = st.radio("Analizar por:", ["Facturación ($)", "Volumen (Unidades)"], horizontal=True)
                    
                    if metric_opt == "Facturación ($)":
                        col_val = 'amount'
                        # Solo items con precio > 0
                        data_source = df_prods_raw[df_prods_raw['amount'] > 0]
                        colors = px.colors.qualitative.Bold
                    else:
                        col_val = 'quantity'
                        # Todos los items (incluso si precio es 0)
                        data_source = df_prods_raw
                        colors = px.colors.qualitative.Pastel

                    if not data_source.empty:
                        # Agrupar
                        prods_stats = data_source.groupby('clean_name')[[col_val]].sum().reset_index().sort_values(col_val, ascending=False).head(10)
                        
                        # Gráfico Torta
                        fig_pie = px.pie(
                            prods_stats, 
                            values=col_val, 
                            names='clean_name', 
                            hole=0.4,
                            color_discrete_sequence=colors
                        )
                        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                        fig_pie.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0), height=250)
                        st.plotly_chart(fig_pie, use_container_width=True)
                        report_figures['products_pie'] = fig_pie
                        
                        # Gráfico Barras
                        st.caption("Detalle Top 10")
                        fig_bar = px.bar(prods_stats, x=col_val, y='clean_name', orientation='h', text_auto='.2s', color='clean_name', color_discrete_sequence=colors)
                        fig_bar.update_layout(showlegend=False, yaxis={'title':''}, margin=dict(t=0,b=0,l=0,r=0), height=250)
                        st.plotly_chart(fig_bar, use_container_width=True)
                        
                    else:
                        st.warning(f"No hay datos para el criterio: {metric_opt}")
                else:
                    st.info("No se encontraron productos detallados.")
                    st.caption("Nota: Las ventas de solo 'Pedido' no detallan producto. Se requiere carga de Inventario.")
            
            st.divider()
            
            # Evolución Diaria
            st.markdown("#### 📈 Mi Actividad Diaria")
            daily = df.groupby(['date_only', 'activity_type']).size().reset_index(name='Cant')
            if not daily.empty:
                fig_hist = px.bar(daily, x='date_only', y='Cant', color='activity_type', title="Eventos por Día")
                st.plotly_chart(fig_hist, use_container_width=True)
                report_figures['act_bar'] = fig_hist
            else: st.caption("Sin actividad.")

    # ---------------- TAB 3: CORREGIR (MEJORADA CON TABLA) ----------------
    with t_edit:
        st.subheader("🛠️ Gestión de Historial")
        st.info("Selecciona un registro para editarlo o eliminarlo.")
        
        my_records = df[df['username'] == user['username']].copy()
        
        if not my_records.empty:
            search_term = st.text_input("🔍 Buscar en mis registros:", "")
            if search_term:
                my_records = my_records[my_records['client_name'].str.contains(search_term, case=False) | my_records['activity_type'].str.contains(search_term, case=False)]

            display_df = my_records[['created_at', 'client_name', 'activity_type', 'description', 'amount', 'quantity', 'id']]
            
            selection = st.dataframe(
                display_df,
                column_config={
                    "created_at": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YY HH:mm"),
                    "client_name": "Cliente",
                    "amount": st.column_config.NumberColumn(format="$%.2f"),
                    "id": None
                },
                use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
            )

            if selection.selection.rows:
                idx = selection.selection.rows[0]
                row = my_records.iloc[idx]
                
                st.divider()
                st.markdown(f"#### ✏️ Editando: {row['client_name']}")
                with st.form("edit_row"):
                    c1, c2 = st.columns(2)
                    nc = c1.text_input("Cliente", value=row['client_name'])
                    nm = 0.0; nq = 1; nd = ""
                    
                    if "Oportunidad" in str(row['activity_type']):
                        nm = c2.number_input("Monto ($)", value=float(row['amount']))
                        nd = st.text_area("Detalles", value=row['description'])
                    elif "Capacitación" in str(row['activity_type']):
                        nq = c2.number_input("Asistentes", value=int(row['quantity']))
                        nd = st.text_area("Tema", value=row['description'])
                    else:
                        nd = st.text_area("Notas", value=row['description'])

                    pw = st.text_input("Contraseña:", type="password")
                    
                    col_b1, col_b2 = st.columns([1, 1])
                    if col_b1.form_submit_button("🔄 Actualizar"):
                        if verify_user_password(user['username'], pw):
                            update_own_record(row['id'], {"client_name":nc, "amount":nm, "description":nd, "quantity":nq})
                            st.success("Listo"); time.sleep(1); st.rerun()
                        else: st.error("Clave incorrecta")
                    
                    if col_b2.form_submit_button("🗑️ Eliminar"):
                        if verify_user_password(user['username'], pw):
                            delete_sales_record(row['id'])
                            st.warning("Eliminado"); time.sleep(1); st.rerun()
                        else: st.error("Clave incorrecta")
        else: st.info("No tienes registros propios para editar.")

    # ---------------- TAB 4: PDF ----------------
    with t_pdf:
        st.subheader("📄 Generar Mi Reporte")
        if st.button("🖨️ Generar PDF", type="primary"):
            if df.empty: st.error("Sin datos.")
            else:
                cfg = {'kpi':True, 'pareto':True, 'new_biz':True, 'activities':True}
                try:
                    pdf_bytes = generate_pdf_report(df, branch_name, start_d, end_d, cfg, report_figures)
                    st.success("¡Listo!")
                    st.download_button("Descargar", pdf_bytes, f"Reporte_{branch_key}.pdf", "application/pdf")
                except Exception as e: st.error(f"Error: {e}")