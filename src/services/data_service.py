import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
from src.config.connection import init_connection

# Inicializar conexión con Supabase
supabase = init_connection()

# ==============================================================================
# 1. AUTENTICACIÓN
# ==============================================================================

def login_user(username, password):
    try:
        response = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"❌ Error Critical en Login: {e}")
        return None

def verify_user_password(username, password):
    return login_user(username, password) is not None

def verify_admin_password(input_password, current_user_password):
    return input_password == current_user_password

# ==============================================================================
# 2. LECTURA DE DATOS (CON AUTOCORRECCIÓN DE SUCURSAL)
# ==============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def get_sales_data(user_role, user_branch, filter_branch=None, start_date=None, end_date=None):
    """
    Obtiene datos de ventas con corrección automática de sucursal basada en Referencia.
    """
    query = supabase.table("sales_log").select("*")
    
    # Filtro de fecha en SQL (Eficiente)
    if start_date and end_date:
        query = query.gte('created_at', start_date).lte('created_at', end_date)
    
    # Rango amplio
    query = query.order('created_at', desc=True).range(0, 100000)
    
    response = query.execute()
    df = pd.DataFrame(response.data)
    
    if df.empty: return df

    # --- AUTOCORRECCIÓN DE SUCURSAL ---
    # Si la sucursal está mal, usamos el ID de referencia para corregirla en memoria
    # Ej: BARIN/OUT/03533 -> Barinas
    
    def fix_branch(row):
        current_branch = str(row['branch']).lower()
        ref_id = str(row['reference_id']).upper()
        
        # Si ya coincide, dejarlo
        if user_role == 'sales' and str(user_branch).lower() in current_branch:
            return row['branch']
        
        # Rescate por Código
        if "BARIN" in ref_id: return "Barinas"
        if "MERID" in ref_id: return "Merida"
        if "VIGIA" in ref_id: return "Vigia"
        if "CARAC" in ref_id: return "Caracas"
        if "VALEN" in ref_id: return "Valencia"
        
        return row['branch']

    # Aplicar corrección solo si hay referencias
    if 'reference_id' in df.columns:
        df['branch'] = df.apply(fix_branch, axis=1)

    # Convertir a minúsculas para filtrado seguro
    df['branch_norm'] = df['branch'].astype(str).str.strip().str.lower()

    # --- FILTRADO FINAL ---
    if user_role == 'sales':
        target = str(user_branch).strip().lower()
        df = df[df['branch_norm'].str.contains(target, na=False)]
        
    elif user_role == 'admin':
        if filter_branch and filter_branch != "Todas":
            target = str(filter_branch).strip().lower()
            df = df[df['branch_norm'].str.contains(target, na=False)]
            
    return df

@st.cache_data(ttl=300, show_spinner=False)
def get_branch_goal(branch):
    try:
        response = supabase.table("goals").select("*").eq("branch", branch).execute()
        if response.data:
            data = response.data[0]
            return {
                "amount": float(data.get('amount', 10000)),
                "clients": int(data.get('clients_goal', 20)),
                "meetings": int(data.get('meetings_goal', 40)),
                "products": int(data.get('products_goal', 100))
            }
        return {"amount": 10000.0, "clients": 20, "meetings": 40, "products": 100}
    except Exception as e:
        return {"amount": 10000.0, "clients": 20, "meetings": 40, "products": 100}

def get_inventory_match_data(start_date, end_date):
    try:
        query = supabase.table("sales_log").select("*").gte('created_at', start_date).lte('created_at', end_date).range(0, 100000)
        response = query.execute()
        df = pd.DataFrame(response.data)
        if df.empty: return pd.DataFrame(), pd.DataFrame()
        ventas = df[df['activity_type'] == 'Venta'].copy()
        inventario = df[df['activity_type'].str.contains("Logística|Inventario|Entrega", na=False) | (df['username'] == 'Almacén')].copy()
        return ventas, inventario
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

# ==============================================================================
# 3. ESCRITURA
# ==============================================================================

def log_activity(username, branch, client, amount, desc, activity_type, tag, quantity=1):
    data = {
        "username": username, "branch": branch, "client_name": client,
        "amount": amount, "description": desc, "activity_type": activity_type,
        "strategic_tag": tag, "quantity": quantity, "created_at": datetime.now().isoformat()
    }
    supabase.table("sales_log").insert(data).execute()
    st.cache_data.clear()

def update_branch_goal(branch, amount, clients, meetings, products):
    try:
        data = {"branch": branch, "amount": amount, "clients_goal": clients, "meetings_goal": meetings, "products_goal": products}
        supabase.table("goals").upsert(data).execute()
        st.cache_data.clear()
        return True
    except Exception as e: return False

def update_sales_record(record_id, updates):
    try:
        supabase.table("sales_log").update(updates).eq("id", record_id).execute()
        st.cache_data.clear()
        return True, "Registro actualizado."
    except Exception as e: return False, f"Error: {str(e)}"

def update_own_record(record_id, updates):
    return update_sales_record(record_id, updates)

def delete_sales_record(record_id):
    try:
        supabase.table("sales_log").delete().eq("id", record_id).execute()
        st.cache_data.clear()
        return True, "Registro eliminado."
    except Exception as e: return False, str(e)

def delete_bulk_sales_records(list_ids):
    try:
        if not list_ids: return False, "Nada seleccionado."
        supabase.table("sales_log").delete().in_("id", list_ids).execute()
        st.cache_data.clear()
        return True, f"Se eliminaron {len(list_ids)} registros."
    except Exception as e: return False, str(e)

def delete_all_data(target_branch=None):
    try:
        query = supabase.table("sales_log").delete()
        if target_branch and target_branch != "Todas":
            query = query.eq("branch", target_branch)
        else:
            query = query.neq("id", -1)
        query.execute()
        st.cache_data.clear()
        return True, "Datos eliminados masivamente."
    except Exception as e: return False, str(e)

# ==============================================================================
# 5. CARGA MASIVA
# ==============================================================================

def smart_process_excel(df, default_branch):
    records = []
    if len(df.columns) == 1 and ";" in str(df.iloc[0,0]):
        try:
            col_name = df.columns[0]
            new_cols = col_name.split(";")
            df = df[col_name].str.split(";", expand=True)
            df.columns = new_cols
        except: pass

    df = df.astype(str)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.replace({'nan': None, 'NaN': None, '': None})
    headers = list(df.columns)
    
    contact_keywords = ["translated display name", "job position", "nombre a mostrar", "etiquetas/nombre de etiqueta"]
    headers_lower = [h.lower() for h in headers]
    if any(k in headers_lower for k in contact_keywords):
        return False, "⚠️ ERROR: Estás subiendo CONTACTOS en la pestaña de VENTAS. Por favor ve a la pestaña '👥 Fichas Clientes'."

    branch_map = {
        "El Vigía": "Vigia", "El Vigia": "Vigia", "Vigia": "Vigia",
        "Barinas": "Barinas", "Caracas": "Caracas", "Distrito Capital": "Caracas",
        "Valencia": "Valencia", "Carabobo": "Valencia",
        "Merida": "Merida", "Mérida": "Merida", "Ejido": "Merida",
        "Anzoategui": "Anzoategui", "Anzoátegui": "Anzoategui", "Barcelona": "Anzoategui", "Puerto La Cruz": "Anzoategui"
    }

    def get_row_branch(row_val):
        if not row_val: return None
        val_str = str(row_val).strip()
        for key, code in branch_map.items():
            if key.lower() in val_str.lower(): return code
        return None

    def clean_money(val):
        if val is None or str(val).strip() == '' or str(val).lower() == 'none': return 0.0
        s_val = str(val).replace('$', '').replace('Bs', '').strip()
        if ',' in s_val:
            if '.' in s_val: s_val = s_val.replace('.', '') 
            s_val = s_val.replace(',', '.') 
        try: return float(s_val)
        except: return 0.0

    last_valid_branch = default_branch

    # Lógica VENTAS
    if "Referencia del pedido" in headers and "Total" in headers:
        for _, row in df.iterrows():
            detected = None
            if 'Almacén' in headers and row.get('Almacén'):
                 detected = get_row_branch(row.get('Almacén'))
            
            if detected: last_valid_branch = detected; actual_branch = detected
            elif last_valid_branch: actual_branch = last_valid_branch
            else: actual_branch = "Vigia"

            try: 
                raw_date = row.get('Fecha de creación')
                fecha = pd.to_datetime(raw_date).isoformat()
            except: fecha = datetime.now().isoformat()

            records.append({
                "branch": actual_branch, "created_at": fecha,
                "client_name": str(row.get('Cliente') or 'Desconocido'),
                "activity_type": "Venta", 
                "amount": clean_money(row.get('Total')),
                "quantity": 1, 
                "description": f"Ref: {row.get('Referencia del pedido')} | Estado: {row.get('Estado')}",
                "reference_id": str(row.get('Referencia del pedido')), 
                "strategic_tag": "Mantenimiento", 
                "username": str(row.get('Comercial', 'Carga Masiva'))
            })
        mode_msg = "Ventas"
    
    # Lógica INVENTARIO
    elif "Producto" in headers and "Realizado" in headers:
        for _, row in df.iterrows():
            detected = None
            hints = str(row.get('Referencia', '')) + " " + str(row.get('Desde', ''))
            detected = get_row_branch(hints)
            
            if detected: last_valid_branch = detected; actual_branch = detected
            elif last_valid_branch: actual_branch = last_valid_branch
            else: actual_branch = "Vigia"
            
            try: fecha = pd.to_datetime(row.get('Fecha')).isoformat()
            except: fecha = datetime.now().isoformat()
            
            prod_name = str(row.get('Producto', 'Sin Nombre'))
            if "]" in prod_name: prod_name = prod_name.split("]", 1)[1].strip()
            
            records.append({
                "branch": actual_branch, "created_at": fecha,
                "client_name": str(row.get('Contacto/Nombre') or 'Stock Interno'),
                "activity_type": "Logística/Entrega", "amount": 0.0,
                "quantity": int(clean_money(row.get('Realizado'))),
                "description": f"{prod_name} | SN: {row.get('Lote/Nº de serie')}",
                "reference_id": str(row.get('Referencia')), "strategic_tag": "Operativo", "username": "Almacén"
            })
        mode_msg = "Inventario"
    
    else:
        return False, f"⚠️ Formato no reconocido. Columnas: {headers[:3]}..."

    if records:
        try:
            chunk_size = 100
            for i in range(0, len(records), chunk_size):
                supabase.table("sales_log").insert(records[i:i + chunk_size]).execute()
            st.cache_data.clear() 
            return True, f"✅ Carga de {mode_msg} Exitosa: {len(records)} registros."
        except Exception as e: return False, f"Error DB: {str(e)}"
    
    return False, "Archivo vacío."

# ==============================================================================
# 6. CRM
# ==============================================================================

def get_all_customer_profiles(branch=None):
    all_records = []
    chunk_size = 1000
    offset = 0
    query = supabase.table("customer_profiles").select("*")
    if branch and branch != "Todas": query = query.eq("branch", branch)
    while True:
        response = query.range(offset, offset + chunk_size - 1).execute()
        data_chunk = response.data
        if not data_chunk: break
        all_records.extend(data_chunk)
        if len(data_chunk) < chunk_size: break
        offset += chunk_size
    return pd.DataFrame(all_records)

def smart_import_profiles(df, branch_default):
    stats = {"nuevos": 0, "actualizados": 0, "sin_cambios": 0}
    df = df.astype(str)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    col_map = {'nombre': ['nombre a mostrar', 'translated display name', 'display name', 'compañía', 'nombre', 'cliente'], 'email': ['correo electrónico', 'email', 'correo', 'mail'], 'phone': ['teléfono', 'phone', 'telefono', 'móvil', 'celular'], 'city': ['ciudad', 'city', 'población', 'estado'], 'category': ['etiquetas', 'tags', 'categoría', 'category']}

    def find_col(options):
        for opt in options:
            if opt in df.columns: return opt
        return None

    c_name = find_col(col_map['nombre'])
    c_email = find_col(col_map['email'])
    c_phone = find_col(col_map['phone'])
    c_city = find_col(col_map['city'])
    c_cat = find_col(col_map['category'])

    if not c_name: return False, f"Error: No encontré columna de Nombre."

    existing_db = get_all_customer_profiles(branch_default)
    existing_map = {}
    if not existing_db.empty:
        existing_db['norm_name'] = existing_db['name'].astype(str).str.strip().str.upper()
        existing_map = existing_db.set_index('norm_name').to_dict('index')

    inserts = []
    
    for _, row in df.iterrows():
        raw_name = str(row[c_name]).strip()
        if not raw_name or raw_name.lower() in ['nan', 'none', '', 'false']: continue
        norm_name = raw_name.upper().replace("  ", " ")
        
        def get_clean(col_name):
            if not col_name: return None
            val = str(row[col_name]).strip()
            return None if val.lower() in ['nan', 'none', '', 'false'] else val

        new_email = get_clean(c_email); new_phone = get_clean(c_phone); new_city = get_clean(c_city); new_cat = get_clean(c_cat) or "General"

        if norm_name in existing_map:
            current = existing_map[norm_name]
            record_id = current.get('id', -1)
            if record_id == -1: continue
            changes = {}
            if not current.get('email') and new_email: changes['email'] = new_email
            if not current.get('phone') and new_phone: changes['phone'] = new_phone
            if not current.get('city') and new_city: changes['city'] = new_city
            if not current.get('category') and new_cat: changes['category'] = new_cat
            if changes:
                has_e = changes.get('email', current.get('email')); has_p = changes.get('phone', current.get('phone')); has_c = changes.get('city', current.get('city'))
                changes['is_complete'] = bool(has_e and has_p and has_c)
                try:
                    supabase.table("customer_profiles").update(changes).eq("id", record_id).execute()
                    stats["actualizados"] += 1
                except: pass
            else: stats["sin_cambios"] += 1
        else:
            is_comp = bool(new_email and new_phone and new_city)
            inserts.append({"name": norm_name, "email": new_email, "phone": new_phone, "city": new_city, "category": new_cat, "branch": branch_default, "is_complete": is_comp, "first_seen_at": datetime.now().isoformat()})
            existing_map[norm_name] = {"id": -1}

    if inserts:
        try:
            chunk_size = 1000
            for i in range(0, len(inserts), chunk_size):
                supabase.table("customer_profiles").insert(inserts[i:i + chunk_size]).execute()
            stats["nuevos"] += len(inserts)
        except Exception as e: return False, f"Error insertando: {str(e)}"
            
    st.cache_data.clear()
    return True, f"Proceso CRM Terminado: {stats['nuevos']} Nuevos | {stats['actualizados']} Fichas Mejoradas"

def delete_bulk_profiles(list_ids):
    try:
        if not list_ids: return False, "No seleccionaste nada."
        supabase.table("customer_profiles").delete().in_("id", list_ids).execute()
        st.cache_data.clear()
        return True, f"Se eliminaron {len(list_ids)} contactos."
    except Exception as e: return False, str(e)

def delete_all_profiles(target_branch=None):
    try:
        query = supabase.table("customer_profiles").delete()
        if target_branch and target_branch != "Todas": query = query.eq("branch", target_branch)
        else: query = query.neq("id", -1)
        query.execute()
        st.cache_data.clear()
        return True, "Base de contactos limpiada."
    except Exception as e: return False, str(e)