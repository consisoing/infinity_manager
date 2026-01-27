from fpdf import FPDF
from datetime import datetime
import pandas as pd
import tempfile
import os
import plotly.io as pio

# Configuración para renderizado de imágenes
pio.templates.default = "plotly_white"

class PDFReport(FPDF):
    def __init__(self, branch, date_range):
        super().__init__()
        self.branch = branch
        self.date_range = date_range
        self.set_auto_page_break(auto=True, margin=15)
        
    def header(self):
        # Fondo del encabezado (Azul Corporativo Infinity)
        self.set_fill_color(10, 25, 48) 
        self.rect(0, 0, 210, 30, 'F')
        
        # Nombre de Empresa
        self.set_font('Arial', 'B', 20)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 8)
        self.cell(0, 10, 'INFINITY SOLUTIONS', 0, 1, 'L')
        
        # Título del Reporte
        self.set_font('Arial', '', 10)
        self.set_text_color(255, 87, 34) # Naranja
        self.set_xy(10, 18)
        self.cell(0, 5, 'REPORTE DE GESTION COMERCIAL & OPERATIVA', 0, 1, 'L')
        
        # Datos de Contexto (Derecha)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(255, 255, 255)
        self.set_xy(100, 8)
        
        # Limpieza de caracteres para el encabezado
        clean_branch = self.branch.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 5, f"SUCURSAL: {clean_branch.upper()}", 0, 1, 'R')
        
        self.set_font('Arial', '', 9)
        self.set_xy(100, 14)
        self.cell(0, 5, f"Periodo: {self.date_range}", 0, 1, 'R')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Pagina {self.page_no()} | Confidencial - Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 0, 'C')

    def chapter_title(self, label):
        self.ln(5)
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(245, 245, 245) # Gris muy claro
        self.set_text_color(10, 25, 48) # Azul oscuro
        # Limpieza de caracteres para el título
        clean_label = label.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, f"  {clean_label}", 0, 1, 'L', 1)
        self.ln(5)

    def add_kpi_row(self, kpis):
        """Dibuja tarjetas de KPI estilizadas"""
        self.set_font('Arial', 'B', 10)
        start_y = self.get_y()
        margin = 10
        # Ancho disponible
        page_width = 190
        box_width = (page_width - (margin * (len(kpis) - 1))) / len(kpis)
        
        current_x = 10
        for title, value in kpis.items():
            # Caja
            self.set_fill_color(255, 255, 255)
            self.set_draw_color(200, 200, 200)
            self.rect(current_x, start_y, box_width, 20)
            
            # Título KPI
            self.set_xy(current_x, start_y + 2)
            self.set_font('Arial', '', 9)
            self.set_text_color(100, 100, 100)
            clean_title = title.encode('latin-1', 'replace').decode('latin-1')
            self.cell(box_width, 5, clean_title, 0, 1, 'C')
            
            # Valor KPI
            self.set_xy(current_x, start_y + 9)
            self.set_font('Arial', 'B', 14)
            if "$" in str(value): self.set_text_color(0, 128, 0) # Verde
            else: self.set_text_color(10, 25, 48) # Azul
            
            clean_value = str(value).encode('latin-1', 'replace').decode('latin-1')
            self.cell(box_width, 8, clean_value, 0, 1, 'C')
            
            current_x += box_width + margin
            
        self.set_y(start_y + 25)

    def add_chart(self, fig):
        """Renderiza gráficos Plotly con manejo de errores y alta calidad"""
        if fig:
            try:
                # Comprobar espacio en página
                if self.get_y() > 200: self.add_page()
                
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                    # Kaleido engine es necesario
                    fig.write_image(tmpfile.name, format="png", width=800, height=450, scale=1.5, engine="kaleido")
                    
                    # Centrar imagen
                    x_pos = (210 - 180) / 2
                    self.image(tmpfile.name, x=x_pos, w=180)
                    self.ln(5)
                try: os.unlink(tmpfile.name)
                except: pass
            except Exception as e:
                self.set_font('Arial', 'I', 9)
                self.set_text_color(255, 0, 0)
                self.cell(0, 10, f"[Error al generar grafico: {str(e)}]", 0, 1)

    def add_smart_table(self, df, columns, title, col_widths=None):
        """
        Tabla inteligente con ajuste de texto (Word Wrap) y anchos dinámicos.
        """
        # Título de la tabla
        self.set_font('Arial', 'B', 11)
        self.set_text_color(10, 25, 48)
        clean_title = title.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, clean_title, 0, 1)
        
        # Configuración de anchos por defecto si no se pasan
        if not col_widths:
            col_widths = [190 / len(columns)] * len(columns)
        
        # --- ENCABEZADOS ---
        self.set_font('Arial', 'B', 8)
        self.set_fill_color(230, 230, 230)
        self.set_text_color(0)
        self.set_draw_color(180, 180, 180)
        
        for i, col in enumerate(columns):
            # Limpiar nombre columna (ej: client_name -> CLIENTE)
            header_text = col.replace("_", " ").upper()
            header_text = header_text.encode('latin-1', 'replace').decode('latin-1')
            self.cell(col_widths[i], 8, header_text, 1, 0, 'C', 1)
        self.ln()
        
        # --- FILAS ---
        self.set_font('Arial', '', 8)
        self.set_fill_color(255)
        
        for _, row in df.iterrows():
            # 1. Calcular la altura máxima de la fila
            max_lines = 1
            row_data = []
            
            for i, col in enumerate(columns):
                # Limpieza de texto estricta
                text = str(row[col])
                text = text.replace('€', 'Eur').replace('’', "'").replace('“', '"').replace('”', '"')
                text = text.encode('latin-1', 'replace').decode('latin-1')
                
                text_len = self.get_string_width(text)
                width = col_widths[i]
                
                lines = int(text_len / (width - 2)) + 1 
                if lines > max_lines: max_lines = lines
                row_data.append(text)
            
            # Altura de la fila (5mm por línea)
            row_height = max_lines * 5
            
            # Salto de página inteligente si la fila no cabe
            if self.get_y() + row_height > 270:
                self.add_page()
                # Repetir headers
                self.set_font('Arial', 'B', 8)
                self.set_fill_color(230, 230, 230)
                for i, col in enumerate(columns):
                    header_text = col.replace("_", " ").upper().encode('latin-1', 'replace').decode('latin-1')
                    self.cell(col_widths[i], 8, header_text, 1, 0, 'C', 1)
                self.ln()
                self.set_font('Arial', '', 8)

            # 2. Imprimir celdas
            x_start = self.get_x()
            y_start = self.get_y()
            
            for i, text in enumerate(row_data):
                current_x = self.get_x()
                self.multi_cell(col_widths[i], 5, text, border=1, align='L')
                self.set_xy(current_x + col_widths[i], y_start)
            
            self.ln(row_height)

# ----------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE GENERACIÓN
# ----------------------------------------------------------------------
def generate_pdf_report(df, branch_name, start_d, end_d, config, figures):
    """
    Genera el PDF completo.
    """
    pdf = PDFReport(branch_name, f"{start_d} al {end_d}")
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- LÓGICA FINANCIERA CORREGIDA ---
    # 1. Normalizar clientes para evitar duplicados (Cable Center == CABLE CENTER)
    df['client_name'] = df['client_name'].astype(str).str.strip().str.upper()
    
    # 2. Filtrar solo las ventas reales (Facturación)
    sales_data = df[df['activity_type'] == 'Venta']
    
    # 3. Cálculos Correctos
    total_sales = sales_data['amount'].sum()
    
    # Clientes Únicos: Contamos solo clientes que han comprado (Facturados)
    # Si quieres clientes de TODA actividad, usa df. Pero lo usual es Clientes Activos = Facturados
    total_clients = sales_data['client_name'].nunique()
    
    # Transacciones DE VENTA (para el ticket promedio)
    sales_tx_count = len(sales_data)
    
    # Ticket Promedio = Ventas Totales / Cantidad de Ventas (No de registros totales)
    avg_ticket = total_sales / sales_tx_count if sales_tx_count > 0 else 0.0

    # Total de registros (Volumen de datos procesados, para referencia operativa)
    total_records = len(df)
    
    # Productos Movidos (Suma de quantity de todo el dataframe, incluye logística)
    prod_q = int(pd.to_numeric(df['quantity'], errors='coerce').sum())

    # --- 1. RESUMEN EJECUTIVO (KPIs) ---
    if config.get('kpi'):
        pdf.chapter_title("1. RESUMEN EJECUTIVO")
        
        # Fila 1
        kpis_1 = {
            "FACTURACION": f"${total_sales:,.2f}",
            "CLIENTES ACTIVOS": str(total_clients),
            "TICKET PROMEDIO": f"${avg_ticket:,.2f}" # ¡Corregido!
        }
        pdf.add_kpi_row(kpis_1)

        # Fila 2
        kpis_2 = {
            "PRODUCTOS MOVIDOS": str(prod_q),
            "VENTAS CERRADAS": str(sales_tx_count),
            "REGISTROS TOTALES": str(total_records)
        }
        pdf.add_kpi_row(kpis_2)

        if 'history' in figures:
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 6, "Comportamiento Diario de Ventas:", 0, 1)
            pdf.add_chart(figures['history'])

    # --- 2. ANÁLISIS DE MERCADO ---
    if config.get('pareto'):
        pdf.add_page()
        pdf.chapter_title("2. ANALISIS DE MERCADO Y PARETO")
        
        if 'pareto' in figures:
            pdf.cell(0, 8, "Concentracion de Facturacion (80/20):", 0, 1)
            pdf.add_chart(figures['pareto'])
            pdf.ln(5)
        
        # Tabla Pareto usando los datos filtrados de ventas
        pareto_table = sales_data.groupby('client_name').agg({'amount':'sum'}).reset_index().sort_values('amount', ascending=False).head(10)
        
        if not pareto_table.empty:
            pareto_table['amount'] = pareto_table['amount'].apply(lambda x: f"${x:,.2f}")
            pdf.add_smart_table(pareto_table, ['client_name', 'amount'], "Top 10 Clientes VIP", [140, 50])

    # --- 3. ANÁLISIS DE PRODUCTOS ---
    if 'products_pie' in figures or 'products_bar' in figures:
        pdf.add_page()
        pdf.chapter_title("3. MOVIMIENTO DE INVENTARIO")
        
        if 'products_pie' in figures:
            pdf.cell(0, 8, "Distribucion del Mix de Productos:", 0, 1)
            pdf.add_chart(figures['products_pie'])
        
        if 'products_bar' in figures:
            pdf.ln(5)
            pdf.cell(0, 8, "Top Productos por Volumen:", 0, 1)
            pdf.add_chart(figures['products_bar'])

    # --- 4. DETALLE OPERATIVO ---
    if config.get('activities'):
        pdf.add_page()
        pdf.chapter_title("4. BITACORA DE OPERACIONES")
        
        # Usamos el DF completo para la bitácora
        log_table = df[['created_at', 'activity_type', 'client_name', 'description', 'amount']].head(50).copy()
        
        log_table['created_at'] = pd.to_datetime(log_table['created_at']).dt.strftime('%d/%m %H:%M')
        # Mostrar monto solo si es positivo
        log_table['amount'] = log_table['amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
        
        pdf.add_smart_table(
            log_table, 
            ['created_at', 'activity_type', 'client_name', 'description', 'amount'], 
            "Ultimos 50 Movimientos Registrados",
            [25, 30, 50, 65, 20]
        )

    return pdf.output(dest='S').encode('latin-1', 'replace')