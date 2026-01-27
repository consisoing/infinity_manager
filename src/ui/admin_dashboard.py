import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta

# ==============================================================================
# IMPORTACIÓN DE SERVICIOS
# ==============================================================================
from src.services.data_service import (
    get_sales_data, 
    smart_process_excel, 
    update_sales_record, 
    delete_bulk_sales_records, 
    delete_all_data, 
    login_user, 
    get_branch_goal, 
    update_branch_goal, 
    get_inventory_match_data
)
from src.services.pdf_service import generate_pdf_report
from src.config.settings import BRANCH_CONFIG

def render_admin(user):
    # Diccionario para almacenar los gráficos generados y pasarlos al PDF posteriormente
    report_figures = {}

    # ==============================================================================
    # CONFIGURACIÓN DE PÁGINA Y TÍTULO
    # ==============================================================================
    st.title("🗺️ Centro de Comando - Infinity Solutions")
    
    # ==============================================================================
    # 1. FILTROS LATERALES (SIDEBAR)
    # ==============================================================================
    st.sidebar.markdown("### 🔍 Filtros Globales de Auditoría")
    st.sidebar.markdown("---")
    
    # --- A. Selector de Sucursal ---
    # Obtenemos las llaves del archivo de configuración y preparamos la lista
    # Excluimos "Global" de la lista seleccionable directa para evitar confusiones
    branch_options = ["Todas"] + list(BRANCH_CONFIG.keys())
    if "Global" in branch_options: 
        branch_options.remove("Global")
    
    selected_branch = st.sidebar.selectbox("Seleccionar Sucursal:", branch_options)
    
    # --- B. Selector de Fechas ---
    # Por defecto mostramos los últimos 30 días para tener contexto inmediato
    today = datetime.now()
    default_start = today - timedelta(days=30)
    
    date_range = st.sidebar.date_input(
        "Período de Análisis:", 
        value=(default_start, today), 
        format="DD/MM/YYYY"
    )
    
    # Validación: Asegurar que el usuario seleccionó inicio y fin
    if not (isinstance(date_range, tuple) and len(date_range) == 2):
        st.sidebar.warning("⚠️ Por favor selecciona una fecha final en el calendario para cargar los datos.")
        return
    
    # Convertir fechas a formato compatible con base de datos (String ISO al final del día)
    start_d, end_d = date_range
    end_d_str = f"{end_d} 23:59:59"

    # ==============================================================================
    # 2. CÁLCULO DE METAS (TARGETS) DINÁMICAS Y MULTI-KPI
    # ==============================================================================
    # Esta sección obtiene las 4 metas de la BD y las ajusta proporcionalmente al tiempo seleccionado.
    
    # Inicializadores de acumuladores para el caso "Todas"
    base_monthly_goal = 0.0
    base_clients_goal = 0
    base_meetings_goal = 0
    base_products_goal = 0

    # Paso A: Obtener las metas base mensuales desde la Base de Datos
    if selected_branch == "Todas":
        # Si la vista es Global, iteramos y sumamos las metas de todas las sucursales reales
        # Excluimos la llave 'Global' para no duplicar si existiera
        real_branches_list = [b for b in BRANCH_CONFIG.keys() if b != "Global"]
        
        for branch in real_branches_list:
            g_data = get_branch_goal(branch) # Consulta a la DB por sucursal
            base_monthly_goal += g_data.get('amount', 0.0)
            base_clients_goal += g_data.get('clients', 0)
            base_meetings_goal += g_data.get('meetings', 0)
            base_products_goal += g_data.get('products', 0)
    else:
        # Si es una sucursal específica, traemos sus metas puntuales
        g_data = get_branch_goal(selected_branch)
        base_monthly_goal = g_data.get('amount', 0.0)
        base_clients_goal = g_data.get('clients', 0)
        base_meetings_goal = g_data.get('meetings', 0)
        base_products_goal = g_data.get('products', 0)

    # Paso B: Calcular el factor de tiempo (Proyección)
    # Ejemplo: Si la meta mensual es 100 y seleccionamos 15 días, la meta del periodo debería ser 50.
    days_in_period = (end_d - start_d).days + 1
    if days_in_period < 1: 
        days_in_period = 1
    
    # Asumiendo un mes comercial estándar de 30 días para el cálculo proporcional
    time_factor = days_in_period / 30.0 
    
    # Paso C: Calcular las Metas del Periodo (Target)
    target_amount = base_monthly_goal * time_factor
    target_daily = base_monthly_goal / 30.0 # La meta diaria es constante
    target_clients = int(base_clients_goal * time_factor)
    target_meetings = int(base_meetings_goal * time_factor)
    target_products = int(base_products_goal * time_factor)
    
    # Estimación de operaciones de venta (Ticket promedio estimado $200 para calcular cantidad de ventas necesarias)
    # Evitamos división por cero
    if base_monthly_goal > 0:
        target_sales_ops = int((base_monthly_goal / 200) * time_factor) 
    else:
        target_sales_ops = 0

    # ==============================================================================
    # 3. OBTENCIÓN Y LIMPIEZA DE DATOS (DATA FETCHING)
    # ==============================================================================
    # Llamada al servicio de datos principal con los filtros aplicados
    df = get_sales_data(user['role'], user['branch'], selected_branch, start_d, end_d_str)

    # Limpieza Crítica: Asegurar tipos numéricos para evitar errores en gráficos y sumas
    if not df.empty:
        # Convertir monto a float, errores se vuelven 0
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        
        # Convertir cantidad a numero, errores se vuelven 0
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        
        # Crear columna de fecha limpia para agrupaciones gráficas
        # Usamos format='mixed' para soportar formatos con y sin zona horaria
        df['created_at'] = pd.to_datetime(df['created_at'], format='mixed', errors='coerce')
        df['date_only'] = df['created_at'].dt.date.fillna(datetime.now().date())
        
        # Asegurar que descripción sea string para manipulaciones de texto
        df['description'] = df['description'].astype(str).fillna("")

    # ==============================================================================
    # 4. TABLERO DE CONTROL (KPIs) - ENCABEZADO
    # ==============================================================================
    
    # Inicialización de variables en 0
    total_rev = 0.0
    daily_avg = 0.0
    total_clients = 0
    total_meetings = 0
    total_sales_ops = 0
    total_products = 0
    
    # Deltas (Diferencia Real vs Meta)
    delta_rev = 0.0
    delta_daily = 0.0
    delta_clients = 0
    delta_meetings = 0
    delta_sales = 0
    delta_products = 0

    if not df.empty:
        # 1. Facturación Total (Suma de 'amount' donde tipo es 'Venta')
        sales_df = df[df['activity_type'] == 'Venta']
        total_rev = sales_df['amount'].sum()
        delta_rev = total_rev - target_amount
        
        # 2. Venta Promedio Diaria
        daily_avg = total_rev / days_in_period
        delta_daily = daily_avg - target_daily
        
        # 3. N° Clientes Atendidos (Conteo de clientes únicos en el periodo)
        total_clients = df['client_name'].nunique()
        delta_clients = total_clients - target_clients
        
        # 4. Número de Reuniones (Buscamos coincidencias de texto "Reunión")
        meetings_df = df[df['activity_type'].str.contains("Reunión", case=False, na=False)]
        total_meetings = len(meetings_df)
        delta_meetings = total_meetings - target_meetings
        
        # 5. Número de Ventas (Transacciones cerradas)
        total_sales_ops = len(sales_df)
        delta_sales = total_sales_ops - target_sales_ops
        
        # 6. Cantidad de Productos Despachados
        # Filtramos para sumar cantidad solo de productos reales (no referencias financieras)
        prod_filter = df[~df['description'].str.contains("Ref:|Pedido de venta", case=False, na=False)]
        total_products = int(prod_filter['quantity'].sum())
        delta_products = total_products - target_products
    else:
        # Si no hay datos, los deltas son negativos iguales a la meta
        delta_rev = -target_amount
        delta_daily = -target_daily
        delta_clients = -target_clients
        delta_meetings = -target_meetings
        delta_products = -target_products
    
    # --- VISUALIZACIÓN DE KPIs EN GRID DE 2 FILAS ---
    
    # Fila 1: Indicadores Financieros y de Cartera
    k1, k2, k3 = st.columns(3)
    k1.metric(
        label="💰 Facturación Total", 
        value=f"${total_rev:,.2f}", 
        delta=f"{delta_rev:,.2f} vs Meta (${target_amount:,.0f})", 
        delta_color="normal" # Verde si es positivo, Rojo si es negativo
    )
    k2.metric(
        label="📅 Venta Promedio Diaria", 
        value=f"${daily_avg:,.2f}", 
        delta=f"{delta_daily:,.2f} vs Meta (${target_daily:,.0f})"
    )
    k3.metric(
        label="👥 N° Clientes Atendidos", 
        value=total_clients, 
        delta=f"{delta_clients} vs Meta ({target_clients})",
        delta_color="normal"
    )
    
    # Fila 2: Indicadores Operativos
    k4, k5, k6 = st.columns(3)
    k4.metric(
        label="🤝 Número de Reuniones", 
        value=total_meetings, 
        delta=f"{delta_meetings} vs Meta ({target_meetings})"
    )
    k5.metric(
        label="🛒 Número de Ventas", 
        value=total_sales_ops, 
        delta="Cierres Exitosos", # KPI informativo
        delta_color="off"
    )
    k6.metric(
        label="📦 Productos Despachados", 
        value=total_products, 
        delta=f"{delta_products} vs Meta ({target_products})",
        delta_color="normal"
    )
    
    st.divider()

    # ==============================================================================
    # 5. PESTAÑAS DE GESTIÓN INTEGRAL (7 MÓDULOS)
    # ==============================================================================
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Analytics & Pareto", 
        "🆕 Cacería", 
        "📡 Actividades", 
        "🔗 Auditoría Cliente", 
        "📥 Carga Masiva", 
        "⚙️ Gestión",
        "📄 Reportes PDF"
    ])

    # ------------------------------------------------------------------------------
    # TAB 1: ANALYTICS PREMIUM (PARETO + PRODUCTOS + HISTÓRICO)
    # ------------------------------------------------------------------------------
    with tab1:
        if df.empty:
            st.warning("No hay datos cargados en este rango de fechas para generar análisis.")
        else:
            # --- SECCIÓN A: PARETO 80/20 (REAL) ---
            with st.container(border=True):
                st.subheader("🏆 Ley de Pareto (Clientes vs Ingresos)")
                
                # Agrupar solo ventas por cliente
                pareto_df = df[df['activity_type'] == 'Venta'].groupby('client_name').agg({'amount':'sum'}).reset_index()
                
                if not pareto_df.empty:
                    # Ordenar de mayor a menor
                    pareto_df = pareto_df.sort_values(by='amount', ascending=False)
                    
                    # Calcular porcentaje acumulado
                    pareto_df['cumulative_sum'] = pareto_df['amount'].cumsum()
                    total_sum = pareto_df['amount'].sum()
                    pareto_df['cumulative_pct'] = (pareto_df['cumulative_sum'] / total_sum) * 100
                    
                    # Crear gráfico combinado
                    fig_pareto = go.Figure()
                    
                    # Barras (Ingreso $)
                    fig_pareto.add_trace(go.Bar(
                        x=pareto_df['client_name'].head(20), # Top 20 para legibilidad
                        y=pareto_df['amount'].head(20),
                        name='Ingresos ($)',
                        marker_color='#00A8E8' # Azul Corporativo
                    ))
                    
                    # Línea (Acumulado %)
                    fig_pareto.add_trace(go.Scatter(
                        x=pareto_df['client_name'].head(20),
                        y=pareto_df['cumulative_pct'].head(20),
                        name='% Acumulado',
                        yaxis='y2',
                        mode='lines+markers',
                        marker_color='#FF5722',
                        line=dict(width=3)
                    ))
                    
                    # Configuración del Layout (Doble Eje Y)
                    fig_pareto.update_layout(
                        yaxis=dict(title='Monto ($)'),
                        yaxis2=dict(
                            title='% Acumulado',
                            overlaying='y',
                            side='right',
                            range=[0, 110],
                            showgrid=False
                        ),
                        legend=dict(x=0.6, y=1.1, orientation='h'),
                        template="plotly_dark",
                        height=450,
                        margin=dict(t=50, b=50)
                    )
                    
                    # Línea de referencia del 80% (Ley de Pareto)
                    fig_pareto.add_hline(y=80, line_dash="dot", line_color="white", annotation_text="80% Vitales", yref="y2")
                    st.plotly_chart(fig_pareto, use_container_width=True)
                    
                    # Guardar para reporte PDF
                    report_figures['pareto'] = fig_pareto
                else:
                    st.info("Sin ventas registradas para generar Pareto.")

            # --- SECCIÓN B: INTELIGENCIA DE PRODUCTOS ---
            st.markdown("### 📦 Análisis de Productos")
            
            # Función auxiliar para limpiar nombres (quitar seriales únicos para agrupar)
            def clean_prod_name(txt):
                if not isinstance(txt, str): return "Desconocido"
                # Si tiene serial o estado, cortamos el string para quedarnos con el nombre base
                if "| SN:" in txt: txt = txt.split("| SN:")[0]
                if "| Estado:" in txt: return "REF PEDIDO"
                if "Ref:" in txt: return "REF PEDIDO"
                return txt.strip()

            # Crear dataframe copia para no afectar el original
            df_analysis = df.copy()
            df_analysis['clean_name'] = df_analysis['description'].apply(clean_prod_name)
            
            # Excluir las referencias de pedido que no dicen qué producto es
            df_prods = df_analysis[df_analysis['clean_name'] != "REF PEDIDO"]

            if not df_prods.empty:
                # Controles de visualización (Dinero vs Cantidad)
                col_ctrl, _ = st.columns([1, 2])
                with col_ctrl:
                    metric_opt = st.radio("Criterio de Análisis:", ["Facturación ($)", "Volumen (Unidades)"], horizontal=True)
                
                # Lógica de colores y datos según selección
                if metric_opt == "Facturación ($)":
                    col_val = 'amount'
                    # FILTRO IMPORTANTE: Solo mostrar lo que generó dinero (> 0)
                    data_source = df_prods[df_prods['amount'] > 0]
                    colors = px.colors.qualitative.Bold 
                    title_x = "Dinero Generado ($)"
                else:
                    col_val = 'quantity'
                    # Para volumen mostramos todo (incluye inventario interno)
                    data_source = df_prods
                    colors = px.colors.qualitative.Pastel
                    title_x = "Unidades Movidas"

                if not data_source.empty:
                    # Agrupar y ordenar
                    prod_stats = data_source.groupby('clean_name')[[col_val]].sum().reset_index()
                    prod_stats = prod_stats.sort_values(by=col_val, ascending=False).head(10) # Top 10

                    c_pie, c_bar = st.columns([1, 1.5])
                    
                    # Gráfico de Torta (Proporción)
                    with c_pie:
                        fig_pie = px.pie(
                            prod_stats, 
                            values=col_val, 
                            names='clean_name', 
                            hole=0.4,
                            color_discrete_sequence=colors
                        )
                        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                        fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300)
                        st.plotly_chart(fig_pie, use_container_width=True)
                        report_figures['products_pie'] = fig_pie # Guardar para PDF

                    # Histograma Horizontal (Comparación)
                    with c_bar:
                        fig_bar = px.bar(
                            prod_stats, 
                            x=col_val, 
                            y='clean_name', 
                            orientation='h', 
                            text_auto='.2s',
                            color='clean_name', 
                            color_discrete_sequence=colors
                        )
                        fig_bar.update_layout(
                            yaxis={'categoryorder':'total ascending', 'title': ''}, 
                            xaxis={'title': title_x},
                            showlegend=False,
                            height=300,
                            margin=dict(t=10, b=10, l=0, r=10)
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
                        report_figures['products_bar'] = fig_bar # Guardar para PDF
                else:
                    st.warning("⚠️ No hay productos con valor monetario en la selección actual.")
            else:
                st.info("Carga datos con detalle de producto para ver este análisis.")

            st.divider()

            # --- SECCIÓN C: TENDENCIA DIARIA ---
            st.subheader("📈 Tendencia Diaria de Ventas")
            
            # Agrupar ventas por día
            daily = df[df['activity_type'] == 'Venta'].groupby('date_only')['amount'].sum().reset_index()
            
            if not daily.empty:
                fig_hist = px.area(daily, x='date_only', y='amount', markers=True)
                fig_hist.update_traces(line_color='#FEB019', fillcolor='rgba(254, 176, 25, 0.2)')
                fig_hist.update_layout(height=280, yaxis_title="Venta ($)", xaxis_title=None, margin=dict(t=10))
                st.plotly_chart(fig_hist, use_container_width=True)
                report_figures['history'] = fig_hist # Guardar para PDF
                
                # Alertas Inteligentes (Insights)
                avg_sales = daily['amount'].mean()
                last_val = daily.iloc[-1]['amount']
                
                c_a1, c_a2 = st.columns(2)
                c_a1.info(f"📊 Promedio Diario Histórico: **${avg_sales:,.2f}**")
                
                if last_val > avg_sales * 1.5:
                    c_a2.success(f"🚀 ¡Pico de ventas reciente! (${last_val:,.2f})")
                elif last_val < avg_sales * 0.5:
                    c_a2.error(f"📉 Ventas recientes por debajo del promedio (${last_val:,.2f}).")
                else:
                    c_a2.info("✅ Ritmo de ventas estable.")
            else:
                st.caption("Falta data histórica para generar tendencias.")

    # ------------------------------------------------------------------------------
    # TAB 2: CACERÍA (NUEVOS NEGOCIOS)
    # ------------------------------------------------------------------------------
    with tab2:
        st.subheader("🏆 Resultados de Cacería")
        st.markdown("Seguimiento de clientes marcados como **'Cacería'** (Nuevos Negocios).")
        
        if not df.empty:
            new_biz = df[df['strategic_tag'].fillna('').str.contains("Cacería")]
            if not new_biz.empty:
                st.metric("Ingresos Totales por Nuevos Clientes", f"${new_biz['amount'].sum():,.2f}")
                st.dataframe(
                    new_biz[['created_at','client_name','amount','description']], 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Sin registros de clientes nuevos (Cacería) en este periodo.")

    # ------------------------------------------------------------------------------
    # TAB 3: ACTIVIDADES (OPERATIVO)
    # ------------------------------------------------------------------------------
    with tab3:
        st.subheader("📡 Radar de Actividad Operativa")
        
        if not df.empty:
            col_graph1, col_graph2 = st.columns([1, 2])
            
            # A. Distribución por Tipo (Torta)
            with col_graph1:
                st.markdown("##### Distribución")
                activity_counts = df['activity_type'].value_counts().reset_index()
                activity_counts.columns = ['Tipo', 'Cantidad']
                
                fig_pie_act = px.pie(
                    activity_counts, 
                    values='Cantidad', 
                    names='Tipo', 
                    hole=0.4, 
                    color_discrete_sequence=px.colors.qualitative.Prism
                )
                fig_pie_act.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300, showlegend=True)
                st.plotly_chart(fig_pie_act, use_container_width=True)
                report_figures['act_pie'] = fig_pie_act # Guardar para PDF

            # B. Evolución Histórica (Barras Apiladas)
            with col_graph2:
                st.markdown("##### Evolución Diaria")
                daily_acts = df.groupby(['date_only', 'activity_type']).size().reset_index(name='Conteo')
                
                fig_hist_act = px.bar(
                    daily_acts, 
                    x='date_only', 
                    y='Conteo', 
                    color='activity_type', 
                    color_discrete_sequence=px.colors.qualitative.Prism
                )
                fig_hist_act.update_layout(xaxis_title=None, height=300)
                st.plotly_chart(fig_hist_act, use_container_width=True)
                report_figures['act_bar'] = fig_hist_act # Guardar para PDF

            st.divider()
            st.markdown("##### 📋 Bitácora Detallada")
            st.dataframe(
                df[['created_at', 'activity_type', 'client_name', 'description', 'amount', 'username']], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay actividades registradas.")

    # ------------------------------------------------------------------------------
    # TAB 4: AUDITORÍA CLIENTE (360 GRADOS)
    # ------------------------------------------------------------------------------
    with tab4:
        st.subheader("🔗 Auditoría 360º por Cliente")
        st.markdown("Análisis cruzado de **Ventas vs Inventario** para un cliente específico.")
        
        # Obtener datos separados
        ventas, inventario = get_inventory_match_data(start_d, end_d_str)
        
        if ventas.empty and inventario.empty:
            st.warning("No hay datos suficientes (Ventas + Inventario) para realizar cruces.")
        else:
            # Lista unificada de clientes
            all_clients = sorted(list(set(ventas['client_name'].unique()) | set(inventario['client_name'].unique())))
            client_match = st.selectbox("Seleccionar Cliente a Auditar:", all_clients)
            
            if client_match:
                # Filtrar datos específicos
                v_cli = ventas[ventas['client_name'] == client_match].copy()
                i_cli = inventario[inventario['client_name'] == client_match].copy()
                
                # Tablas Detalladas
                c1, c2 = st.columns(2)
                with c1:
                    st.info(f"💰 Facturado: ${v_cli['amount'].sum():,.2f}")
                    st.dataframe(v_cli[['created_at', 'description', 'amount']], hide_index=True, use_container_width=True)
                with c2:
                    st.success(f"📦 Entregado: {int(i_cli['quantity'].sum())} items")
                    st.dataframe(i_cli[['created_at', 'description', 'quantity']], hide_index=True, use_container_width=True)

                st.divider()
                st.markdown(f"#### 📊 Análisis Visual: {client_match}")
                
                g1, g2 = st.columns(2)
                
                # GRÁFICO 1: Mix de Productos del Cliente (Torta)
                with g1:
                    if not i_cli.empty:
                        # Limpiar nombre del producto
                        i_cli['prod_clean'] = i_cli['description'].astype(str).apply(lambda x: x.split("| SN:")[0].strip())
                        
                        mix_prods = i_cli.groupby('prod_clean')['quantity'].sum().reset_index()
                        
                        fig_mix = px.pie(
                            mix_prods, 
                            values='quantity', 
                            names='prod_clean', 
                            title="Productos Comprados (Mix)", 
                            hole=0.4, 
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        st.plotly_chart(fig_mix, use_container_width=True)
                    else:
                        st.caption("Sin datos de productos entregados.")
                
                # GRÁFICO 2: Historial de Facturación (Histograma)
                with g2:
                    if not v_cli.empty:
                        fig_hist = px.histogram(
                            v_cli, 
                            x='created_at', 
                            y='amount', 
                            title="Historial de Pagos ($)", 
                            nbins=20, 
                            color_discrete_sequence=['#00CC96']
                        )
                        st.plotly_chart(fig_hist, use_container_width=True)
                    else:
                        st.caption("Sin pagos registrados.")

    # ------------------------------------------------------------------------------
    # TAB 5: CARGA MASIVA (INTELIGENTE)
    # ------------------------------------------------------------------------------
    with tab5:
        st.subheader("📥 Importar Datos")
        c_up, c_inf = st.columns([2,1])
        
        with c_up:
            # Selector que incluye "Detectar Automático"
            target_opts = ["Detectar Automático"] + [b for b in BRANCH_CONFIG.keys() if b!="Global"]
            target_br = st.selectbox("Destino de Carga", target_opts)
            
            up_file = st.file_uploader("Archivo Excel/CSV", type=['xlsx','csv'])
            
            if up_file and st.button("🚀 Procesar Archivo"):
                try:
                    df_up = pd.read_csv(up_file) if up_file.name.endswith('.csv') else pd.read_excel(up_file)
                    
                    # Lógica para enviar el parámetro correcto
                    branch_param = None if target_br == "Detectar Automático" else target_br
                    
                    success, msg = smart_process_excel(df_up, branch_param)
                    
                    if success: 
                        st.success(msg)
                        st.balloons()
                    else: 
                        st.error(msg)
                except Exception as e: 
                    st.error(f"Error crítico al leer archivo: {str(e)}")
        
        with c_inf:
            st.info("El sistema detecta automáticamente si es:")
            st.markdown("""
            1. **Ventas:** Referencia, Cliente, Total...
            2. **Inventario:** Producto, Realizado, Serie...
            3. **Contactos:** Display Name, Correo...
            """)

    # ------------------------------------------------------------------------------
    # TAB 6: GESTIÓN (METAS COMPLETAS Y BORRADO)
    # ------------------------------------------------------------------------------
    with tab6:
        st.header("🛠️ Gestión del Sistema")
        
        c_gestion_1, c_gestion_2 = st.columns([2, 1])
        
        # 1. CONFIGURACIÓN DE METAS (ROBUSTO)
        with c_gestion_1:
            st.markdown("### 🎯 Configuración de Metas Mensuales")
            st.info("Define los objetivos mensuales para la sucursal seleccionada.")
            
            # Formulario para evitar recargas accidentales
            with st.form("goal_update_form"):
                # Selector de sucursal para la meta
                # Filtrar solo sucursales reales
                real_branches_for_goals = [b for b in BRANCH_CONFIG.keys() if b != "Global"]
                goal_branch = st.selectbox("Seleccionar Sucursal:", real_branches_for_goals)
                
                # Obtener valor actual desde la base de datos
                current_goals = get_branch_goal(goal_branch)
                
                # Inputs para las 4 metas
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    new_amount = st.number_input("Facturación Mensual ($)", value=float(current_goals['amount']), step=1000.0)
                    new_clients = st.number_input("Nuevos Clientes (Cant)", value=int(current_goals['clients']), step=1)
                with col_g2:
                    new_meetings = st.number_input("Reuniones/Visitas (Cant)", value=int(current_goals['meetings']), step=1)
                    new_products = st.number_input("Productos Despachados (Cant)", value=int(current_goals['products']), step=10)
                
                submitted = st.form_submit_button("💾 Guardar Nuevas Metas", type="primary")
                
                if submitted:
                    if update_branch_goal(goal_branch, new_amount, new_clients, new_meetings, new_products):
                        st.success(f"¡Metas de {goal_branch} actualizadas correctamente!")
                        time.sleep(1) # Pausa para lectura
                        st.rerun()    # Recarga para actualizar los KPIs superiores
                    else:
                        st.error("Error al actualizar la base de datos.")
        
        st.divider()
        
        # 2. ZONA DE PELIGRO (BORRADO)
        with st.expander("🚨 ZONA DE PELIGRO (BORRADO DE DATOS)"):
            st.warning(f"⚠️ Estas acciones son irreversibles. Estás trabajando sobre: **{selected_branch}**")
            
            # Opción 1: Borrado Selectivo
            st.markdown("#### Opción A: Selección Manual de Registros")
            if not df.empty:
                df_ed = df.copy()
                df_ed.insert(0, "Eliminar", False)
                edited = st.data_editor(
                    df_ed[["Eliminar", "created_at", "client_name", "amount", "activity_type", "id"]], 
                    hide_index=True, 
                    use_container_width=True
                )
                to_del = edited[edited["Eliminar"]==True]['id'].tolist()
                
                pass_sel = st.text_input("Clave para Selección:", type="password", key="psel")
                
                if st.button("🗑️ Borrar Registros Seleccionados"):
                    if not to_del:
                        st.warning("No has seleccionado nada.")
                    elif login_user(user['username'], pass_sel):
                         delete_bulk_sales_records(to_del)
                         st.success("Registros eliminados correctamente.")
                         time.sleep(1)
                         st.rerun()
                    else:
                        st.error("Contraseña incorrecta.")
            else:
                st.info("No hay datos visibles para seleccionar.")
            
            st.markdown("---")
            
            # Opción 2: Borrado Total
            st.markdown("#### Opción B: Reset Total (Borrado Masivo)")
            st.markdown(f"Borrará TODA la información correspondiente a: **{selected_branch}**")
            
            pwd = st.text_input("Clave de Administrador (Confirmación Total):", type="password", key="pall")
            
            if st.button(f"🔥 DESTRUIR DATOS DE: {selected_branch.upper()}", type="primary"):
                if login_user(user['username'], pwd):
                    delete_all_data(selected_branch)
                    st.success("Base de datos limpiada exitosamente.")
                    time.sleep(1)
                    st.rerun()
                else: 
                    st.error("Contraseña incorrecta. Acción denegada.")

    # ------------------------------------------------------------------------------
    # TAB 7: REPORTES PDF
    # ------------------------------------------------------------------------------
    with tab7:
        st.header("📄 Generador de Informes Corporativos")
        st.markdown("Configura el reporte oficial para descarga en formato PDF.")
        
        c_conf, c_view = st.columns([1, 1])
        
        with c_conf:
            st.markdown("##### Secciones a Incluir")
            inc_kpi = st.checkbox("Incluir Resumen Ejecutivo (KPIs)", value=True)
            inc_pareto = st.checkbox("Incluir Gráfico y Tabla Pareto", value=True)
            inc_new = st.checkbox("Incluir Nuevos Negocios (Cacería)", value=True)
            inc_acts = st.checkbox("Incluir Bitácora Detallada de Actividades", value=False)
            
            st.markdown("---")
            
            if st.button("🖨️ Generar Informe PDF", type="primary"):
                if df.empty:
                    st.error("No hay datos cargados para generar el reporte.")
                else:
                    cfg = {
                        'kpi': inc_kpi, 
                        'pareto': inc_pareto, 
                        'new_biz': inc_new, 
                        'activities': inc_acts
                    }
                    # Pasamos el diccionario report_figures lleno al generador
                    try:
                        pdf_bytes = generate_pdf_report(df, selected_branch, start_d, end_d, cfg, report_figures)
                        st.success("¡Informe Generado Exitosamente!")
                        st.download_button(
                            label="📥 Descargar Documento PDF", 
                            data=pdf_bytes, 
                            file_name=f"Reporte_{selected_branch}_{datetime.now().strftime('%Y%m%d')}.pdf", 
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"Error generando PDF: {e}")
        
        with c_view:
            st.info(f"""
            **Detalles del Reporte:**
            - **Sucursal:** {selected_branch}
            - **Rango:** {start_d} al {end_d}
            - **Total Registros:** {len(df)}
            """)
            st.caption("El PDF incluirá el encabezado corporativo de Infinity Solutions.")