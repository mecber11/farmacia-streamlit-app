import streamlit as st
import psycopg2
import os
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv # <-- Asegúrate de que esto esté importado

load_dotenv() # <-- ¡Esta línea es CRUCIAL! Debe estar al principio.

# --- CONFIGURACIÓN DE CONEXIÓN A LA DB (Usa las variables de entorno) ---
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    return conn

# --- URL DEL WEBHOOK DE N8N ---
# Esta es la URL de producción de tu primer workflow en n8n
N8N_WEBHOOK_URL = "https://jmecola.app.n8n.cloud/webhook/350bf9fe-e518-4741-bed8-ceb59fd01af9"


# --- INICIALIZACIÓN DEL ESTADO DE LA SESIÓN ---
# session_state es la memoria de Streamlit para cada usuario
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'page' not in st.session_state:
    st.session_state.page = 'login'


# --- PÁGINA DE LOGIN ---
def page_login():
    st.header("Iniciar Sesión")
    telefono = st.text_input("Teléfono")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, telefono, password_hash FROM clientes WHERE telefono = %s", (telefono,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user[3], password):
            st.session_state.logged_in = True
            st.session_state.user_info = {"id": user[0], "nombre": user[1], "telefono": user[2]}
            st.session_state.page = 'catalogo'
            st.rerun() # Vuelve a ejecutar el script para mostrar la nueva página
        else:
            st.error("Teléfono o contraseña incorrectos")

    if st.button("No tengo cuenta, registrarme"):
        st.session_state.page = 'registro'
        st.rerun()

# --- PÁGINA DE REGISTRO ---
def page_registro():
    st.header("Crear Nueva Cuenta")
    with st.form("registro_form"):
        nombre = st.text_input("Nombre Completo")
        telefono = st.text_input("Teléfono (ej: +51987654321)")
        email = st.text_input("Email")
        direccion = st.text_area("Dirección de Envío")
        password = st.text_input("Crea una Contraseña", type="password")
        
        submitted = st.form_submit_button("Registrarme")
        if submitted:
            # Encriptamos la contraseña
            password_hash = generate_password_hash(password)
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO clientes (nombre, telefono, email, direccion, password_hash) VALUES (%s, %s, %s, %s, %s)",
                    (nombre, telefono, email, direccion, password_hash)
                )
                conn.commit()
                cur.close()
                conn.close()
                st.success("¡Registro exitoso! Ahora puedes iniciar sesión.")
                st.session_state.page = 'login'
                st.rerun()
            except Exception as e:
                st.error(f"Error al registrar: {e}")

    if st.button("Ya tengo cuenta, iniciar sesión"):
        st.session_state.page = 'login'
        st.rerun()


# --- PÁGINA DEL CATÁLOGO DE PRODUCTOS ---
def page_catalogo():
    st.title(f"¡Hola, {st.session_state.user_info['nombre']}! 👋")
    st.header("Catálogo de Medicamentos")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, presentacion, precio_unitario, stock FROM medicamentos WHERE activo = TRUE AND stock > 0")
    medicamentos = cur.fetchall()
    cur.close()
    conn.close()

    for med in medicamentos:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.subheader(med[1])
            st.caption(f"{med[2]} | Stock: {med[4]}")
        with col2:
            st.metric("Precio", f"S/ {med[3]:.2f}")
        with col3:
            if st.button("Añadir al Carrito", key=f"add_{med[0]}"):
                # Añadir al carrito en session_state
                st.session_state.cart.append({"id": med[0], "nombre": med[1], "precio": float(med[3]), "cantidad": 1})
                st.toast(f"'{med[1]}' añadido al carrito!")

# --- PÁGINA DEL CARRITO DE COMPRAS ---
def page_carrito():
    st.header("🛒 Tu Carrito de Compras")
    
    if not st.session_state.cart:
        st.warning("Tu carrito está vacío.")
        return

    total = 0
    for item in st.session_state.cart:
        st.write(f"**{item['nombre']}** - S/ {item['precio']:.2f}")
        total += item['precio']
    
    st.metric("Total a Pagar", f"S/ {total:.2f}")

    if st.button("Pagar con PayPal"):
        # ¡AQUÍ SUCEDE LA MAGIA!
        # 1. Preparamos el JSON para n8n
        pedido_json = {
            "cliente": {
                "nombre": st.session_state.user_info['nombre'],
                "telefono": st.session_state.user_info['telefono'],
                "id": st.session_state.user_info['id']
            },
            "items": [
                {"id": item['id'], "cantidad": item['cantidad']} for item in st.session_state.cart
            ]
        }
        
        # 2. Enviamos los datos al webhook de n8n
        st.info("Conectando con nuestro sistema de pagos...")
        try:
            response = requests.post(N8N_WEBHOOK_URL, json=pedido_json)
            response.raise_for_status() # Lanza error si la respuesta no es 200 OK
            
            # 3. Recibimos la URL de pago de PayPal desde n8n
            paypal_url = response.json().get('approve_url')
            if paypal_url:
                st.success("¡Orden creada! Serás redirigido a PayPal para completar el pago.")
                # 4. Mostramos el enlace para que el usuario pague
                st.link_button("Ir a PayPal para Pagar", paypal_url)
                st.session_state.cart = [] # Limpiamos el carrito
            else:
                st.error("Hubo un problema al crear la orden de pago. Intenta de nuevo.")

        except requests.exceptions.RequestException as e:
            st.error(f"Error de comunicación con el servidor: {e}")


# --- LÓGICA PRINCIPAL PARA MOSTRAR PÁGINAS ---
if not st.session_state.logged_in:
    if st.session_state.page == 'login':
        page_login()
    elif st.session_state.page == 'registro':
        page_registro()
else:
    # Si el usuario está logueado, mostramos el menú de navegación
    st.sidebar.header(f"Bienvenido, {st.session_state.user_info['nombre']}")
    opcion = st.sidebar.radio("Menú", ["Catálogo", "Carrito"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.session_state.cart = []
        st.rerun()

    if opcion == "Catálogo":
        page_catalogo()
    elif opcion == "Carrito":
        page_carrito()