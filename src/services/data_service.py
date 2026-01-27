import pandas as pd
import numpy as np
from datetime import datetime
from src.config.connection import init_connection

# Inicializar conexión con Supabase
supabase = init_connection()

# ==============================================================================
# 1. AUTENTICACIÓN Y SEGURIDAD
# ==============================================================================

def login_user(username, password):
    """
    Verifica las credenciales del usuario en la base de datos.
    Retorna el objeto de usuario si es exitoso, o None si falla.
    """
    try:
        response = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"❌ Error Critical en Login: {e}")
        return None

def verify_user_password(username, password):
    """
    Función auxiliar para re-verificar la contraseña antes de una acción crítica
    (como editar o borrar un registro).
    """
    return login_user(username, password) is not None

def verify_admin_password(input_password, current_user_password):
    """
    Verifica si la contraseña ingresada coincide con la del administrador actual.
    """
    return input_password == current_user_password

# ==============================================================================
# 2. LECTURA DE DATOS (READ)
# ==============================================================================

def get_sales_data(user_role, user_branch, filter_branch=None, start_date=None, end_date=None):
    """
    Obtiene el historial de ventas y actividades aplicando filtros de seguridad.
    - Si es Vendedor: Solo ve su sucursal.
    - Si es Admin: Puede ver todo o filtrar por sucursal.
    """
    query = supabase.table("sales_log").select("*")
    
    # 1. Filtro de Rol (Seguridad)
    if user_role == 'sales':
        query = query.eq('branch', user_branch)
    elif user_role == 'admin':
        if filter_branch and filter_branch != "Todas":
            query = query.eq('branch', filter_branch)
            
    # 2. Filtro de Fechas (Rango)
    if start_date and end_date:
        query = query.gte('created_at', start_date).lte('created_at', end_date)
    
    # Ordenar: Más reciente primero
    query = query.order('created_at', desc=True)
    
    response = query.execute()
    return pd.DataFrame(response.data)

def get_branch_goal(branch):
    """
    Obtiene TODAS las metas configuradas para una sucursal específica.
    Retorna un diccionario con valores por defecto si no existen.
    """
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
        # Valores por defecto (Fallback)
        return {
            "amount": 10000.0, 
            "clients": 20, 
            "meetings": 40, 
            "products": 100
        }
    except Exception as e:
        print(f"Error fetching goals: {e}")
        return {"amount": 10000.0, "clients": 20, "meetings": 40, "products": 100}

def get_inventory_match_data(start_date, end_date):
    """
    Función especializada para la Auditoría.
    Descarga toda la data del periodo y separa en dos DataFrames:
    1. Ventas (Facturación)
    2. Inventario (Logística)
    """
    try:
        query = supabase.table("sales_log").select("*").gte('created_at', start_date).lte('created_at', end_date)
        response = query.execute()
        df = pd.DataFrame(response.data)
        
        if df.empty: 
            return pd.DataFrame(), pd.DataFrame()
        
        # Separar por tipo de actividad
        ventas = df[df['activity_type'] == 'Venta'].copy()
        
        # Para inventario, buscamos todo lo que sea logística o movimientos de almacén
        # (Usamos str.contains para ser flexibles)
        inventario = df[
            df['activity_type'].str.contains("Logística|Inventario|Entrega", na=False) |
            (df['username'] == 'Almacén')
        ].copy()
        
        return ventas, inventario
    except Exception as e:
        print(f"Error en Match: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ==============================================================================
# 3. ESCRITURA Y ACTUALIZACIÓN (CREATE / UPDATE)
# ==============================================================================

def log_activity(username, branch, client, amount, desc, activity_type, tag, quantity=1):
    """
    Registra una nueva actividad desde el dashboard del vendedor.
    """
    data = {
        "username": username,
        "branch": branch,
        "client_name": client,
        "amount": amount,
        "description": desc,
        "activity_type": activity_type,
        "strategic_tag": tag,
        "quantity": quantity,
        "created_at": datetime.now().isoformat()
    }
    supabase.table("sales_log").insert(data).execute()

def update_branch_goal(branch, amount, clients, meetings, products):
    """
    Actualiza o Crea las 4 metas para una sucursal.
    """
    try:
        data = {
            "branch": branch, 
            "amount": amount,
            "clients_goal": clients,
            "meetings_goal": meetings,
            "products_goal": products
        }
        # Upsert: Si existe actualiza, si no existe crea
        supabase.table("goals").upsert(data).execute()
        return True
    except Exception as e:
        print(f"Error actualizando metas: {e}")
        return False

def update_sales_record(record_id, updates):
    """
    Actualiza campos específicos de un registro existente.
    """
    try:
        supabase.table("sales_log").update(updates).eq("id", record_id).execute()
        return True, "Registro actualizado correctamente."
    except Exception as e:
        return False, f"Error al actualizar: {str(e)}"

def update_own_record(record_id, updates):
    """Wrapper para que el vendedor actualice sus propios registros"""
    return update_sales_record(record_id, updates)

# ==============================================================================
# 4. BORRADO DE DATOS (DELETE - ZONA DE PELIGRO)
# ==============================================================================

def delete_sales_record(record_id):
    """Elimina un solo registro por ID"""
    try:
        supabase.table("sales_log").delete().eq("id", record_id).execute()
        return True, "Registro eliminado."
    except Exception as e: return False, str(e)

def delete_bulk_sales_records(list_ids):
    """
    Elimina múltiples registros a la vez.
    Recibe una lista de IDs [1, 2, 5, ...]
    """
    try:
        if not list_ids: return False, "No seleccionaste nada."
        # Usamos el filtro 'in_' de Supabase
        supabase.table("sales_log").delete().in_("id", list_ids).execute()
        return True, f"Se eliminaron {len(list_ids)} registros."
    except Exception as e: return False, str(e)

def delete_all_data(target_branch=None):
    """
    BOTÓN NUCLEAR: Elimina todos los datos.
    Si target_branch es 'Todas', borra la tabla completa.
    Si es una sucursal, borra solo esa sucursal.
    """
    try:
        query = supabase.table("sales_log").delete()
        
        if target_branch and target_branch != "Todas":
            query = query.eq("branch", target_branch)
        else:
            # Truco para borrar todo (where id is not null)
            query = query.neq("id", -1) 
            
        query.execute()
        return True, "Datos eliminados masivamente."
    except Exception as e: return False, str(e)

# ==============================================================================
# 5. CARGA MASIVA INTELIGENTE (LOGICA DE NEGOCIO ERP)
# ==============================================================================

def smart_process_excel(df, default_branch):
    """
    Procesa archivos Excel/CSV detectando automáticamente el formato.
    Soporta: Ventas, Inventario, Contactos.
    Reconoce sucursales: Vigia, Barinas, Caracas, Valencia, Merida, Anzoategui.
    """
    records = []
    
    # 1. Limpieza inicial de cabeceras
    df.columns = [str(c).strip() for c in df.columns]
    # Reemplazar NaN con None para JSON
    df = df.replace({np.nan: None})
    headers = list(df.columns)
    
    print(f"🔍 Analizando columnas: {headers}")

    # --- MAPEO DE SUCURSALES (DICCIONARIO EXTENDIDO) ---
    branch_map = {
        # El Vigía
        "El Vigía": "Vigia", "El Vigia": "Vigia", "Vigia": "Vigia",
        # Barinas
        "Barinas": "Barinas", 
        # Caracas
        "Caracas": "Caracas", "Distrito Capital": "Caracas",
        # Valencia
        "Valencia": "Valencia", "Carabobo": "Valencia",
        # Mérida
        "Merida": "Merida", "Mérida": "Merida", "Ejido": "Merida", "Andes": "Merida",
        # Anzoátegui
        "Anzoategui": "Anzoategui", "Anzoátegui": "Anzoategui", 
        "Barcelona": "Anzoategui", "Puerto La Cruz": "Anzoategui", "Lecheria": "Anzoategui", "Oriente": "Anzoategui"
    }

    def get_row_branch(row_val):
        """Busca palabras clave en el texto para asignar la sucursal"""
        if not row_val: return default_branch
        val_str = str(row_val).strip()
        
        for key, code in branch_map.items():
            if key.lower() in val_str.lower():
                return code
        return default_branch

    def clean_money(val):
        """Convierte texto de moneda ($ 1.200,00) a float (1200.00)"""
        if val is None or str(val).strip() == '': return 0.0
        
        # Si ya es número
        if isinstance(val, (int, float)): return float(val)
        
        s_val = str(val).replace('$', '').replace('Bs', '').strip()
        
        # Formato europeo/latino: 1.500,50
        if ',' in s_val and '.' in s_val:
            s_val = s_val.replace('.', '')  # Quitar miles
            s_val = s_val.replace(',', '.') # Poner punto decimal
        elif ',' in s_val:
            s_val = s_val.replace(',', '.')
        
        try: return float(s_val)
        except: return 0.0

    # ---------------------------------------------------------
    # ESCENARIO A: ARCHIVO DE VENTAS (PEDIDOS)
    # ---------------------------------------------------------
    if "Referencia del pedido" in headers and "Total" in headers:
        print("✅ MODO: Carga de Ventas (Facturación)")
        for _, row in df.iterrows():
            # Detectar Sucursal
            actual_branch = default_branch
            if 'Almacén' in headers:
                # Si el usuario eligió "Detectar Automático" (None), usamos la columna
                if default_branch is None:
                    actual_branch = get_row_branch(row.get('Almacén'))
                else:
                    actual_branch = default_branch

            monto = clean_money(row.get('Total'))
            ref_id = str(row.get('Referencia del pedido', '')).strip()
            
            # Fecha
            try: fecha = pd.to_datetime(row.get('Fecha de creación')).isoformat()
            except: fecha = datetime.now().isoformat()

            records.append({
                "branch": actual_branch,
                "created_at": fecha,
                "client_name": str(row.get('Cliente') or 'Desconocido'),
                "activity_type": "Venta",
                "amount": monto,
                "quantity": 1,
                "description": f"Ref: {ref_id} | Estado: {row.get('Estado')}",
                "reference_id": ref_id,
                "strategic_tag": "Mantenimiento",
                "username": str(row.get('Comercial', 'Carga Masiva'))
            })

    # ---------------------------------------------------------
    # ESCENARIO B: ARCHIVO DE INVENTARIO (PRODUCTOS)
    # ---------------------------------------------------------
    elif "Producto" in headers and "Realizado" in headers:
        print("✅ MODO: Carga de Inventario")
        for _, row in df.iterrows():
            qty = clean_money(row.get('Realizado'))
            
            # Detectar Sucursal
            actual_branch = default_branch
            if default_branch is None:
                # Concatenamos varios campos para buscar pistas de la ciudad
                pistas = str(row.get('Referencia', '')) + " " + str(row.get('Desde', ''))
                actual_branch = get_row_branch(pistas)

            try: fecha = pd.to_datetime(row.get('Fecha')).isoformat()
            except: fecha = datetime.now().isoformat()
            
            # Limpieza del nombre del producto
            prod_name = str(row.get('Producto', 'Sin Nombre'))
            # Quitar corchetes iniciales si existen ej: [AC8]
            if "]" in prod_name:
                prod_name = prod_name.split("]", 1)[1].strip()

            records.append({
                "branch": actual_branch,
                "created_at": fecha,
                "client_name": str(row.get('Contacto/Nombre') or 'Stock Interno'),
                "activity_type": "Logística/Entrega",
                "amount": 0.0, # Inventario no suma dinero aquí
                "quantity": int(qty),
                "description": f"{prod_name} | SN: {row.get('Lote/Nº de serie')}",
                "reference_id": str(row.get('Referencia', '')),
                "strategic_tag": "Operativo",
                "username": "Almacén"
            })

    # ---------------------------------------------------------
    # ESCENARIO C: BASE DE CONTACTOS
    # ---------------------------------------------------------
    elif "Translated Display Name" in headers or "Compañía" in headers:
        print("✅ MODO: Carga de Contactos")
        for _, row in df.iterrows():
            cli = row.get('Translated Display Name') or row.get('Compañía')
            
            actual_branch = default_branch
            if default_branch is None:
                pistas = str(row.get('Estado', '')) + " " + str(row.get('Ciudad', ''))
                actual_branch = get_row_branch(pistas)

            records.append({
                "branch": actual_branch,
                "created_at": datetime.now().isoformat(),
                "client_name": str(cli),
                "activity_type": "Registro Cliente",
                "amount": 0.0,
                "quantity": 0,
                "description": f"Email: {row.get('Correo electrónico')}",
                "strategic_tag": "Prospección",
                "username": "Admin"
            })
    
    # ---------------------------------------------------------
    # ESCENARIO D: GENÉRICO
    # ---------------------------------------------------------
    else:
        print("⚠️ MODO: Genérico (Fallback)")
        for _, row in df.iterrows():
            records.append({
                "branch": default_branch if default_branch else "Vigia",
                "created_at": datetime.now().isoformat(),
                "client_name": str(row.get(df.columns[0]) or 'Sin Nombre'),
                "activity_type": "Carga Genérica",
                "amount": 0.0,
                "quantity": 1,
                "description": "Carga manual sin formato reconocido",
                "strategic_tag": "General",
                "username": "Admin"
            })

    # =========================================================
    # INSERCIÓN FINAL EN BASE DE DATOS
    # =========================================================
    if records:
        try:
            # Insertar en lotes de 100 para estabilidad
            chunk_size = 100
            for i in range(0, len(records), chunk_size):
                chunk = records[i:i + chunk_size]
                supabase.table("sales_log").insert(chunk).execute()
            
            return True, f"Proceso Exitoso: {len(records)} registros cargados."
        except Exception as e:
            return False, f"Error de Base de Datos: {str(e)}"
    
    return False, "El archivo está vacío o no se reconocieron datos."