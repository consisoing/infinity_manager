from fpdf import FPDF
from datetime import datetime
import pandas as pd
import tempfile
import os
import re
import plotly.io as pio

pio.templates.default = "plotly_white"

# NORMALIZACIÓN
def normalize_client_name(text):
    if not isinstance(text, str): return "DESCONOCIDO"
    text = text.upper()
    replacements = (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ñ", "N"))
    for a, b in replacements:
        text = text.replace(a, b)
    text = re.sub(r'[^A-Z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    blacklist = ["STOCK", "ALMACEN", "INVENTARIO", "AJUSTE", "DESCONOCIDO", "CARGA MASIVA", "ADMIN", "NAN", "NONE"]
    for bad_word in blacklist:
        if bad_word in text: return "DESCONOCIDO"
    if len(text) < 2: return "DESCONOCIDO"
    return text

class PDFReport(FPDF):
    def __init__(self, branch, date_range):
        super().__init__()
        self.branch = branch
        self.date_range = date_range
        self.set_auto_page_break(auto=True, margin=15)
        
    def header(self):
        self.set_fill_color(10, 25, 48) 
        self.rect(0, 0, 210, 30, 'F')
        self.set_font('Arial', 'B', 20)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 8)
        self.cell(0, 10, 'INFINITY SOLUTIONS', 0, 1, 'L')
        self.set_font('Arial', '', 10)
        self.set_text_color(255, 87, 34)
        self.set_xy(10, 18)
        self.cell(0, 5, 'REPORTE DE GESTION COMERCIAL & OPERATIVA', 0, 1, 'L')
        self.set_font('Arial', 'B', 9)
        self.set_text_color(255, 255, 255)
        self.set_xy(100, 8)
        clean_branch = str(self.branch).encode('latin-1', 'replace').decode('latin-1')
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
        self.set_fill_color(245, 245, 245)
        self.set_text_color(10, 25, 48)
        clean_label = label.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, f"  {clean_label}", 0, 1, 'L', 1)
        self.ln(5)

    def add_kpi_row(self, kpis):
        self.set_font('Arial', 'B', 10)
        start_y = self.get_y()
        margin = 10
        page_width = 190
        box_width = (page_width - (margin * (len(kpis) - 1))) / len(kpis)
        current_x = 10
        for title, value in kpis.items():
            self.set_fill_color(255, 255, 255)
            self.set_draw_color(200, 200, 200)
            self.rect(current_x, start_y, box_width, 20)
            self.set_xy(current_x, start_y + 2)
            self.set_font('Arial', '', 9)
            self.set_text_color(100, 100, 100)
            clean_title = title.encode('latin-1', 'replace').decode('latin-1')
            self.cell(box_width, 5, clean_title, 0, 1, 'C')
            self.set_xy(current_x, start_y + 9)
            self.set_font('Arial', 'B', 14)
            if "$" in str(value): self.set_text_color(0, 128, 0)
            else: self.set_text_color(10, 25, 48)
            clean_value = str(value).encode('latin-1', 'replace').decode('latin-1')
            self.cell(box_width, 8, clean_value, 0, 1, 'C')
            current_x += box_width + margin
        self.set_y(start_y + 25)

    def add_chart(self, fig):
        if fig:
            try:
                if self.get_y() > 200: self.add_page()
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                    fig.write_image(tmpfile.name, format="png", width=800, height=450, scale=1.5, engine="kaleido")
                    x_pos = (210 - 180) / 2
                    self.image(tmpfile.name, x=x_pos, w=180)
                    self.ln(5)
                try: os.unlink(tmpfile.name)
                except: pass
            except Exception as e:
                self.set_font('Arial', 'I', 9)
                self.set_text_color(255, 0, 0)
                error_msg = str(e).encode('latin-1', 'replace').decode('latin-1')
                self.cell(0, 10, f"[Error grafico: {error_msg}]", 0, 1)
        else:
            self.set_font('Arial', 'I', 9)
            self.set_text_color(128)
            self.cell(0, 10, "[Grafico no disponible]", 0, 1)

    def add_smart_table(self, df, columns, title, col_widths=None):
        if df.empty:
            self.ln(5); self.set_font('Arial', 'I', 10); self.cell(0, 10, "Sin datos.", 0, 1); return
        self.ln(5)
        self.set_font('Arial', 'B', 11)
        self.set_text_color(10, 25, 48)
        clean_title = title.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, clean_title, 0, 1)
        if not col_widths: col_widths = [190 / len(columns)] * len(columns)
        self.set_font('Arial', 'B', 8)
        self.set_fill_color(230, 230, 230)
        self.set_text_color(0)
        self.set_draw_color(180, 180, 180)
        for i, col in enumerate(columns):
            header_text = col.replace("_", " ").upper().encode('latin-1', 'replace').decode('latin-1')
            self.cell(col_widths[i], 8, header_text, 1, 0, 'C', 1)
        self.ln()
        self.set_font('Arial', '', 8)
        self.set_fill_color(255)
        for _, row in df.iterrows():
            max_lines = 1
            row_data = []
            for i, col in enumerate(columns):
                text = str(row[col]) if pd.notna(row[col]) else "-"
                text = text.replace('€', 'Eur').replace('’', "'").replace('“', '"').replace('”', '"')
                text = text.encode('latin-1', 'replace').decode('latin-1')
                width = col_widths[i]
                lines = int(self.get_string_width(text) / (width - 2)) + 1 if width > 5 else 1
                if lines > max_lines: max_lines = lines
                row_data.append(text)
            row_height = max_lines * 5
            if self.get_y() + row_height > 270:
                self.add_page()
                self.set_font('Arial', 'B', 8)
                self.set_fill_color(230, 230, 230)
                for i, col in enumerate(columns):
                    header_text = col.replace("_", " ").upper().encode('latin-1', 'replace').decode('latin-1')
                    self.cell(col_widths[i], 8, header_text, 1, 0, 'C', 1)
                self.ln()
                self.set_font('Arial', '', 8)
            y_start = self.get_y()
            for i, text in enumerate(row_data):
                current_x = self.get_x()
                self.multi_cell(col_widths[i], 5, text, border=1, align='L')
                self.set_xy(current_x + col_widths[i], y_start)
            self.ln(row_height)

def generate_pdf_report(df, branch_name, start_d, end_d, config, figures):
    pdf = PDFReport(branch_name, f"{start_d} al {end_d}")
    pdf.alias_nb_pages()
    pdf.add_page()

    if df.empty:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Sin datos.", 0, 1)
        return pdf.output(dest='S').encode('latin-1', 'replace')

    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    
    # NORMALIZAR
    if 'client_name' in df.columns:
        df['client_name_norm'] = df['client_name'].astype(str).apply(normalize_client_name)
    else:
        df['client_name_norm'] = "DESCONOCIDO"

    sales_data = df[df['activity_type'] == 'Venta']
    total_sales = sales_data['amount'].sum()
    
    # --- CLIENTES ACTIVOS (SOLO VENTAS) ---
    valid_clients = sales_data[sales_data['client_name_norm'] != 'DESCONOCIDO']
    total_clients = valid_clients['client_name_norm'].nunique()
    
    sales_tx_count = len(sales_data)
    avg_ticket = total_sales / sales_tx_count if sales_tx_count > 0 else 0.0
    total_records = len(df)
    prod_filter = df[~df['description'].astype(str).str.contains("Ref:|Pedido de venta", case=False, na=False)]
    prod_q = int(prod_filter['quantity'].sum())

    if config.get('kpi'):
        pdf.chapter_title("1. RESUMEN EJECUTIVO")
        kpis_1 = {
            "FACTURACION": f"${total_sales:,.2f}",
            "CLIENTES ACTIVOS": str(total_clients),
            "TICKET PROMEDIO": f"${avg_ticket:,.2f}"
        }
        pdf.add_kpi_row(kpis_1)
        kpis_2 = {
            "PRODUCTOS MOVIDOS": str(prod_q),
            "VENTAS CERRADAS": str(sales_tx_count),
            "REGISTROS TOTALES": str(total_records)
        }
        pdf.add_kpi_row(kpis_2)
        if 'history' in figures and figures['history'] is not None:
            pdf.ln(5); pdf.set_font('Arial', 'B', 10); pdf.cell(0, 6, "Tendencia:", 0, 1)
            pdf.add_chart(figures['history'])

    if config.get('pareto'):
        pdf.add_page(); pdf.chapter_title("2. MERCADO")
        if 'pareto' in figures and figures['pareto'] is not None:
            pdf.cell(0, 8, "80/20:", 0, 1); pdf.add_chart(figures['pareto']); pdf.ln(5)
        # Usar nombre normalizado
        pareto_table = sales_data.groupby('client_name_norm').agg({'amount':'sum'}).reset_index().sort_values('amount', ascending=False).head(10)
        if not pareto_table.empty:
            pareto_table['amount'] = pareto_table['amount'].apply(lambda x: f"${x:,.2f}")
            pdf.add_smart_table(pareto_table, ['client_name_norm', 'amount'], "Top 10 VIP", [140, 50])

    if ('products_pie' in figures and figures['products_pie']) or ('products_bar' in figures and figures['products_bar']):
        pdf.add_page(); pdf.chapter_title("3. INVENTARIO")
        if 'products_pie' in figures and figures['products_pie']:
            pdf.cell(0, 8, "Mix:", 0, 1); pdf.add_chart(figures['products_pie'])
        if 'products_bar' in figures and figures['products_bar']:
            pdf.ln(5); pdf.cell(0, 8, "Top Volumen:", 0, 1); pdf.add_chart(figures['products_bar'])

    if config.get('activities'):
        pdf.add_page(); pdf.chapter_title("4. BITACORA")
        log_table = df[['created_at', 'activity_type', 'client_name', 'description', 'amount']].head(50).copy()
        log_table['created_at'] = pd.to_datetime(log_table['created_at']).dt.strftime('%d/%m %H:%M')
        log_table['amount'] = log_table['amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
        log_table['description'] = log_table['description'].astype(str).str.slice(0, 100)
        pdf.add_smart_table(log_table, ['created_at', 'activity_type', 'client_name', 'description', 'amount'], "Recientes", [25, 30, 50, 65, 20])

    return pdf.output(dest='S').encode('latin-1', 'replace')