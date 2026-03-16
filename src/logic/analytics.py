import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Configuración de Colores Corporativos
COLOR_PRIMARY = '#00A8E8'  # Azul Infinity
COLOR_SECONDARY = '#FF5722' # Naranja Acción
COLOR_WARNING = '#FEB019'
THEME = "plotly_dark"

def generate_pareto_chart(df):
    """Genera el gráfico de Pareto (80/20) de clientes."""
    if df.empty: return None
    
    # Agrupar y ordenar
    pareto_df = df.groupby('client_name').agg({'amount':'sum'}).reset_index()
    pareto_df = pareto_df.sort_values(by='amount', ascending=False)
    
    # Calcular acumulados
    pareto_df['cumulative_sum'] = pareto_df['amount'].cumsum()
    total_sum = pareto_df['amount'].sum()
    pareto_df['cumulative_pct'] = (pareto_df['cumulative_sum'] / total_sum) * 100
    
    # Crear gráfico
    fig = go.Figure()
    
    # Barras
    fig.add_trace(go.Bar(
        x=pareto_df['client_name'].head(20),
        y=pareto_df['amount'].head(20),
        name='Ingresos ($)',
        marker_color=COLOR_PRIMARY
    ))
    
    # Línea
    fig.add_trace(go.Scatter(
        x=pareto_df['client_name'].head(20),
        y=pareto_df['cumulative_pct'].head(20),
        name='% Acumulado',
        yaxis='y2',
        mode='lines+markers',
        marker_color=COLOR_SECONDARY,
        line=dict(width=3)
    ))
    
    fig.update_layout(
        yaxis=dict(title='Monto ($)'),
        yaxis2=dict(
            title='% Acumulado',
            overlaying='y',
            side='right',
            range=[0, 110],
            showgrid=False
        ),
        legend=dict(x=0.6, y=1.1, orientation='h'),
        template=THEME,
        height=450,
        margin=dict(t=50, b=50)
    )
    
    fig.add_hline(y=80, line_dash="dot", line_color="white", annotation_text="80% Vitales", yref="y2")
    return fig

def generate_product_pie_chart(data, value_col, name_col):
    """Genera gráfico de dona para productos con agrupación de pequeños."""
    if data.empty: return None
    
    # Agrupar datos pequeños en "Otros" para que no desaparezcan
    total_val = data[value_col].sum()
    data['pct'] = data[value_col] / total_val
    
    # Si hay un ítem dominante (>90%), mostramos alerta visual en el título
    title_suffix = ""
    if data.iloc[0]['pct'] > 0.90:
        title_suffix = " (Dominio por Volumen)"

    fig = px.pie(
        data, 
        values=value_col, 
        names=name_col, 
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Bold,
        title=f"Distribución{title_suffix}"
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(showlegend=False, margin=dict(t=30, b=10, l=10, r=10), height=300)
    return fig

def generate_product_bar_chart(data, x_col, y_col, title_x):
    """Genera barras horizontales para productos."""
    if data.empty: return None
    
    fig = px.bar(
        data, 
        x=x_col, 
        y=y_col, 
        orientation='h', 
        text_auto='.2s',
        color=y_col, 
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig.update_layout(
        yaxis={'categoryorder':'total ascending', 'title': ''}, 
        xaxis={'title': title_x},
        showlegend=False,
        height=300,
        margin=dict(t=10, b=10, l=0, r=10)
    )
    return fig

def generate_daily_trend_chart(df):
    """Genera el gráfico de área de tendencia diaria."""
    daily = df[df['activity_type'] == 'Venta'].groupby('date_only')['amount'].sum().reset_index()
    
    if daily.empty: return None, 0, 0
    
    fig = px.area(daily, x='date_only', y='amount', markers=True)
    fig.update_traces(line_color=COLOR_WARNING, fillcolor='rgba(254, 176, 25, 0.2)')
    fig.update_layout(height=280, yaxis_title="Venta ($)", xaxis_title=None, margin=dict(t=10))
    
    avg_sales = daily['amount'].mean()
    last_val = daily.iloc[-1]['amount']
    
    return fig, avg_sales, last_val

def generate_activity_charts(df):
    """Genera la torta y las barras de actividades."""
    if df.empty: return None, None

    # Torta
    act_counts = df['activity_type'].value_counts().reset_index()
    act_counts.columns = ['Tipo', 'Cantidad']
    fig_pie = px.pie(act_counts, values='Cantidad', names='Tipo', hole=0.4, color_discrete_sequence=px.colors.qualitative.Prism)
    fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300, showlegend=True)

    # Barras Históricas
    daily_acts = df.groupby(['date_only', 'activity_type']).size().reset_index(name='Conteo')
    fig_bar = px.bar(daily_acts, x='date_only', y='Conteo', color='activity_type', color_discrete_sequence=px.colors.qualitative.Prism)
    fig_bar.update_layout(xaxis_title=None, height=300)

    return fig_pie, fig_bar