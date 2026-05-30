import streamlit as st
from langchain_groq import ChatGroq
from buscador import buscar_datos_componente
from streamlit_javascript import st_javascript
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController
import json

# ======================================================================
# 1. CONFIGURACIÓN INICIAL Y COOKIES
# ======================================================================
st.set_page_config(page_title="ElectroIA", page_icon="🎓", layout="centered")

if "cookies_inicializadas" not in st.session_state:
    st.session_state.cookies_controller = CookieController()
    st.session_state.cookies_inicializadas = True

cookies = st.session_state.cookies_controller

# 🔌 Conexión Supabase
SUPABASE_URL = "https://jyxlfttrbynepdwhxlom.supabase.co"
SUPABASE_KEY = "sb_publishable_XbbivjLYo2KEZm8d_KemMw_yJMMOnn1"

@st.cache_resource
def iniciar_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase: Client = iniciar_supabase()
except Exception:
    st.error("Error de conexión con el servidor de autenticación.")

# Inicializar estados de sesión esenciales
if "vista_auth" not in st.session_state:
    st.session_state.vista_auth = "login"
if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "historial_conversaciones" not in st.session_state:
    st.session_state.historial_conversaciones = {}
if "chat_actual" not in st.session_state:
    st.session_state.chat_actual = None

# ======================================================================
# 🚀 2. DETECTOR DE REDIRECCIONES DE CORREO (PRIORIDAD ABSOLUTA)
# ======================================================================
query_params = st.query_params

# CASO A: Viene desde el mail de recuperación de contraseña (tipo Facebook)
if "access_token" in query_params and query_params.get("type") == "recovery":
    try:
        res_recovery = supabase.auth.set_session(query_params["access_token"], query_params.get("refresh_token", ""))
        st.session_state.usuario_recupero = res_recovery.user
        st.session_state.vista_auth = "cambiar_clave"
    except Exception as e:
        st.error(f"El enlace de recuperación expiró o es inválido: {e}")

# CASO B: Viene desde el mail de confirmación de cuenta nueva
elif "access_token" in query_params and "refresh_token" in query_params:
    try:
        supabase.auth.set_session(query_params["access_token"], query_params["refresh_token"])
        st.success("¡Cuenta confirmada con éxito! Ya podés iniciar sesión.")
        st.session_state.vista_auth = "login"
        st.query_params.clear()
    except Exception:
        pass

# ======================================================================
# 🔄 3. PERSISTENCIA POR COOKIES (AUTOLOGIN)
# ======================================================================
if st.session_state.usuario is None and st.session_state.vista_auth != "cambiar_clave":
    session_guardada = cookies.get("electroia_session")
    if session_guardada:
        try:
            res_cookie = supabase.auth.set_session(session_guardada.get("access_token"), session_guardada.get("refresh_token"))
            st.session_state.usuario = res_cookie.user
        except Exception:
            cookies.remove("electroia_session")

# ======================================================================
# 🌐 4. IDIOMA Y CONFIGURACIÓN DE MODELOS IA
# ======================================================================
codigo_idioma = st_javascript("window.navigator.language")
idioma_usuario = "español"
t = {
    "subtitulo": "Escribí el modelo de un componente para generar su ficha o consultale tus dudas de taller.",
    "input_placeholder": "Diga qué componente electrónico querés buscar...",
    "spinner": "Analizando parámetros en la nube...",
    "nuevo_chat": "Nuevo Chat",
    "titulo_auth": "Acceso a ElectroIA",
    "btn_login": "Iniciar Sesión",
    "btn_register": "Registrarse",
    "msg_welcome": "Sesión iniciada como: ",
    "btn_logout": "Cerrar Sesión"
}

if codigo_idioma and codigo_idioma.startswith("en"):
    idioma_usuario = "inglés (English)"
    t.update({
        "subtitulo": "Enter a component model to generate its datasheet or consult workshop doubts.",
        "input_placeholder": "Say which electronic component you want to search for...",
        "spinner": "Analyzing parameters in the cloud...",
        "nuevo_chat": "New Chat",
        "titulo_auth": "Access to ElectroIA",
        "btn_login": "Log In",
        "btn_register": "Sign Up",
        "msg_welcome": "Logged in as: ",
        "btn_logout": "Log Out"
    })

# Cargar API Key e inicializar Groq
api_key = st.secrets["GROQ_API_KEY"]
llm = ChatGroq(groq_api_key=api_key, model_name="llama-3.1-8b-instant", temperature=0.5)

# Funciones de base de datos para el historial persistente
def cargar_historial_desde_db(user_id):
    try:
        res = supabase.table("chats").select("*").eq("user_id", user_id).order("updated_at", desc=False).execute()
        historial = {}
        for fila in res.data:
            historial[fila["chat_id"]] = json.loads(fila["conversacion"])
        return historial
    except Exception:
        return {}

def guardar_chat_en_db(user_id, chat_id, conversacion):
    try:
        json_conversacion = json.dumps(conversacion)
        supabase.table("chats").upsert({
            "user_id": user_id,
            "chat_id": chat_id,
            "conversacion": json_conversacion
        }, on_conflict="user_id, chat_id").execute()
    except Exception:
        pass

# Sincronizar historial al entrar
if st.session_state.usuario and not st.session_state.historial_conversaciones:
    st.session_state.historial_conversaciones = cargar_historial_desde_db(st.session_state.usuario.id)

# ======================================================================
# 🔑 PANTALLA 1: CONTROL DE ACCESO
# ======================================================================
if st.session_state.usuario is None:
    
    # --- VISTA A: CAMBIAR CONTRASEÑA (VINCULADA AL CORREO DE RECUPERACIÓN) ---
    if st.session_state.vista_auth == "cambiar_clave":
        st.title("🔑 Restablecer Contraseña")
        st.write("Ingresá los nuevos datos de acceso para tu cuenta de ElectroIA.")
        
        if "usuario_recupero" in st.session_state and st.session_state.usuario_recupero:
            st.info(f"Modificando la contraseña para: **{st.session_state.usuario_recupero.email}**")
        
        nueva_pass = st.text_input("Contraseña Nueva", type="password", key="new_password_input")
        confirmar_pass = st.text_input("Vuelve a escribir la contraseña nueva", type="password", key="confirm_password_input")
        
        if st.button("Confirmar Nueva Contraseña", use_container_width=True):
            if nueva_pass and confirmar_pass:
                if nueva_pass == confirmar_pass:
                    if len(nueva_pass) >= 6:
                        try:
                            supabase.auth.update_user({"password": nueva_pass})
                            st.success("¡Tu contraseña fue actualizada con éxito! Ya podés ingresar.")
                            
                            if "usuario_recupero" in st.session_state:
                                del st.session_state.usuario_recupero
                            st.session_state.vista_auth = "login"
                            st.query_params.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo guardar la contraseña: {e}")
                    else:
                        st.error("La contraseña debe tener al menos 6 caracteres.")
                else:
                    st.error("❌ Las contraseñas no coinciden. Verificá la escritura.")
            else:
                st.warning("⚠️ Completá ambos campos.")

    # --- VISTA B: INICIAR SESIÓN COMÚN ---
    elif st.session_state.vista_auth == "login":
        st.title(t["titulo_auth"])
        
        email = st.text_input("Correo Electrónico", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        recordar = st.checkbox("Recordar mi sesión en este equipo", value=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t["btn_login"], use_container_width=True):
                if email and password:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state.usuario = res.user
                        
                        if recordar and res.session:
                            cookies.set("electroia_session", {
                                "access_token": res.session.access_token,
                                "refresh_token": res.session.refresh_token
                            })
                        
                        st.session_state.historial_conversaciones = cargar_historial_desde_db(res.user.id)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error de credenciales: {e}")
                else:
                    st.warning("⚠️ Completa los campos para iniciar sesión.")
        with col2:
            if st.button("Crear una cuenta nueva", use_container_width=True):
                st.session_state.vista_auth = "registro"
                st.rerun()
        
        st.write("---")
        with st.expander("¿Olvidaste tu contraseña?"):
            email_recupero = st.text_input("Ingresá tu correo para recuperar acceso:")
            if st.button("Enviar correo de restablecimiento"):
                if email_recupero:
                    try:
                        supabase.auth.reset_password_email(email_recupero)
                        st.success("📩 Enlace enviado. Revisá tu casilla de correo o spam.")
                    except Exception as ex:
                        st.error(f"Error: {ex}")
                else:
                    st.warning("Escribí un correo válido.")

    # --- VISTA C: FORMULARIO DE REGISTRO SEGURO ---
    elif st.session_state.vista_auth == "registro":
        st.title("📝 Formulario de Registro")
        st.write("Completa tus datos para crear tu cuenta de acceso.")
        
        with st.form("form_registro_mobile"):
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            email_reg = st.text_input("Correo Electrónico")
            pass_reg = st.text_input("Crear Contraseña", type="password")
            pass_conf = st.text_input("Confirmar Contraseña", type="password")
            btn_confirmar = st.form_submit_button("Confirmar Registro", use_container_width=True)
            
        if btn_confirmar:
            if nombre.strip() and apellido.strip() and email_reg.strip() and pass_reg and pass_conf:
                if pass_reg == pass_conf:
                    try:
                        res = supabase.auth.sign_up({
                            "email": email_reg.strip(), 
                            "password": pass_reg,
                            "options": {
                                "data": {
                                    "first_name": nombre.strip(),
                                    "last_name": apellido.strip()
                                }
                            }
                        })
                        if res.user:
                            st.session_state.usuario = res.user
                            st.success("¡Cuenta creada con éxito!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar: {e}")
                else:
                    st.error("❌ Las contraseñas no coinciden. Verificalas.")
            else:
                st.warning("⚠️ Por favor, completa todos los campos del formulario.")
        
        if st.button("Volver al Login", use_container_width=True):
            st.session_state.vista_auth = "login"
            st.rerun()

# ======================================================================
# 🤖 PANTALLA 2: APLICACIÓN PRINCIPAL (SI EL USUARIO ESTÁ LOGUEADO)
# ======================================================================
else:
    with st.sidebar:
        metadatos = st.session_state.usuario.user_metadata if st.session_state.usuario.user_metadata else {}
        nombre_usuario = metadatos.get("first_name", st.session_state.usuario.email)
        
        st.write(f"👤 {t['msg_welcome']}\n`{nombre_usuario}`")
        
        if st.button(f"➕ {t['nuevo_chat']}", use_container_width=True):
            nuevo_id = f"Chat {len(st.session_state.historial_conversaciones) + 1}"
            st.session_state.historial_conversaciones[nuevo_id] = []
            st.session_state.chat_actual = nuevo_id
            st.rerun()

        st.write("---")
        st.write("📁 Historial de Chats:")
        for chat_id in list(st.session_state.historial_conversaciones.keys()):
            mensajes_chat = st.session_state.historial_conversaciones[chat_id]
            label_boton = mensajes_chat[0]["contenido"] if mensajes_chat else chat_id
            label_boton = label_boton[:20] + "..." if len(label_boton) > 20 else label_boton
            if st.button(label_boton, key=chat_id, use_container_width=True):
                st.session_state.chat_actual = chat_id
                st.rerun()
                
        st.write("---")
        if st.button(t["btn_logout"], use_container_width=True):
            try: supabase.auth.sign_out()
            except Exception: pass
            
            cookies.remove("electroia_session")
            st.session_state.usuario = None
            st.session_state.historial_conversaciones = {}
            st.session_state.chat_actual = None
            st.session_state.vista_auth = "login"
            st.rerun()

    # Manejo del chat actual por defecto
    if st.session_state.chat_actual is None:
        st.session_state.chat_actual = "Chat 1"
        if "Chat 1" not in st.session_state.historial_conversaciones:
            st.session_state.historial_conversaciones["Chat 1"] = []

    mensajes_actuales = st.session_state.historial_conversaciones[st.session_state.chat_actual]

    st.title("ElectroIA")
    st.write(t["subtitulo"])

    # Renderizar mensajes históricos en la interfaz
    for msj in mensajes_actuales:
        with st.chat_message(msj["rol"]):
            st.markdown(msj["contenido"])

    # Entrada del chat del usuario
    if pregunta_usuario := st.chat_input(t["input_placeholder"]):
        with st.chat_message("user"):
            st.markdown(pregunta_usuario)
        mensajes_actuales.append({"rol": "user", "contenido": pregunta_usuario})

        with st.chat_message("assistant"):
            with st.spinner(t["spinner"]):
                try:
                    palabras = pregunta_usuario.strip().split()
                    
                    # Si es una sola palabra, asumimos búsqueda de componente en buscador.py
                    if len(palabras) == 1 and len(mensajes_actuales) <= 2:
                        datos_mouser = buscar_datos_componente(pregunta_usuario)
                        if datos_mouser:
                            atributos_str = "\n".join(datos_mouser["atributos"])
                            prompt = f"""
                            Actúa como un Profesor de Electrónica de nivel superior y especialista en Mecatrónica.
                            Generá una Ficha Didáctica Técnica para el componente '{datos_mouser['modelo']}'.
                            Responder en: {idioma_usuario}.
                            Estructura: 1. Especificaciones de Ingeniería, 2. Parámetros Críticos, 3. Aplicación en Control.
                            Datos Mouser: Fabricante: {datos_mouser['fabricante']} | Descripción: {datos_mouser['descripcion']} | Atributos: {atributos_str}
                            """
                        else:
                            prompt = f"Actúa como un ingeniero especialista. Respondé de forma técnica sobre el componente: {pregunta_usuario}. Idioma: {idioma_usuario}."
                    else:
                        historial_texto = "".join([f"{'Técnico' if m['rol']=='user' else 'Especialista'}: {m['contenido']}\n" for m in mensajes_actuales[:-1]])
                        prompt = f"Profesor de Electrónica. Responde considerando el historial.\nHistorial:\n{historial_texto}\nConsulta: {pregunta_usuario}\nIdioma: {idioma_usuario}."

                    respuesta = llm.invoke(prompt)
                    st.markdown(respuesta.content)
                    mensajes_actuales.append({"rol": "assistant", "contenido": respuesta.content})
                    
                    # Guardar automáticamente la conversación actualizada en Supabase
                    guardar_chat_en_db(st.session_state.usuario.id, st.session_state.chat_actual, mensajes_actuales)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")