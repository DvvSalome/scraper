import os
import time
import json
from selenium.webdriver.support import expected_conditions as EC
import re
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException
import random


options = Options()
options.add_argument("--start-maximized")

# ===================== CONFIG =====================
# --- Proships ---
LOGIN_URL_TRACKER = "https://trackerwin.pasarex.app/sign-in"
STATUS_URL = "https://trackerwin.pasarex.app/status"

SEARCH_INPUT = (By.CSS_SELECTOR, "#top-search, input#search, input[placeholder*='Search'], input[placeholder*='Buscar']")
TIMELINE_CONTAINER = (By.CSS_SELECTOR, ".timeline-items, .shipment-timeline, .timeline")
TABLE_SELECTOR = (By.CSS_SELECTOR, "table.table, table.table-hover, table.table-striped, table.table-condensed")

HEADLESS = False
# ===================================================
# ===================== CREDENCIALES =====================

CREDENCIALES = {
    "user_1": {
        "nombre": "LUZ MARINA DAVID ESCORCIA",
        "usuario": "32609535",
        "password": "pasarex123*",
        "placa": "AAA001"
    },
    "user_2": {
        "nombre": "WILSON DE JESUS PATIÑO CARDONA",
        "usuario": "15354332",
        "password": "pasarex123*",
        "placa": "EZH644"
    },
    "user_3": {
        "nombre": "VICTOR MANUEL ZAPATA MADRID",
        "usuario": "15440135",
        "password": "pasarex123*",
        "placa": "GSR26E"
    },
    "user_4": {
        "nombre": "YHON JAIME QUINTERO CIRO",
        "usuario": "70385015",
        "password": "pasarex123*",
        "placa": "VAQ441"
    },
    "user_5": {
        "nombre": "DALADIER DALADIER ZULUAGA CASTRO",
        "usuario": "70954597",
        "password": "pasarex123*",
        "placa": "MOO734"
    },
    "user_6": {
        "nombre": "SARA CAMILA QUIROZ ARANGO",
        "usuario": "1001479421",
        "password": "pasarex123*",
        "placa": "AKD59H"
    },
    "user_7": {
        "nombre": "ESTEBAN ESTEBAN BUITRAGO SILVA",
        "usuario": "1007461111",
        "password": "pasarex123*",
        "placa": "LUM75F"
    },
    "user_8": {
        "nombre": "JUAN ANTONIO MILLAN PELAEZ",
        "usuario": "1007461272",
        "password": "pasarex123*",
        "placa": "WGX66D"
    },
    "user_9": {
        "nombre": "YEISON YEISON MEJIA MUNERA",
        "usuario": "1013536827",
        "password": "pasarex123*",
        "placa": "DBS94G"
    },
    "user_10": {
        "nombre": "NELSON FERNEY RAMIREZ PEREZ",
        "usuario": "1036927438",
        "password": "pasarex123*",
        "placa": "EPX10E"
    },
    "user_11": {
        "nombre": "JUAN DAVID CASTANEDA CARDONA",
        "usuario": "1036934508",
        "password": "pasarex123*",
        "placa": "HHC61H"

    },
    "user_12": {
        "nombre": "JAVIER ALEJANDRO RENDON VANEGAS",
        "usuario": "1036938064",
        "password": "pasarex123*",
        "placa": "EOB40E"
    },
    "user_13": {
        "nombre": "BRAYAN BRAYAN RENDON RENDON",
        "usuario": "1036951955",
        "password": "pasarex123*",
        "placa": "RAM458"
    },
    "user_14": {
        "nombre": "SAMUEL SAMUEL LONDONO GIRALDO",
        "usuario": "1037886418",
        "password": "pasarex123*",
        "placa": "XKX91E"
    },
    "user_15": {
        "nombre": "JULIAN CAMILO DUQUE LOPEZ",
        "usuario": "1039699122",
        "password": "pasarex123*",
        "placa": "GZI97H"
    },
    "user_16": {
        "nombre": "KEVIN ALEXANDER CARDONA",
        "usuario": "1040033298",
        "password": "pasarex123*",
        "placa": "PKX15D"
    },
    "user_17": {
        "nombre": "ANDRES ANDRES BEDOYA CHICA",
        "usuario": "1040035001",
        "password": "pasarex123*",
        "placa": "GCH23D"
    },
    "user_18": {
        "nombre": "KEVIN ANDRES BERMEJO BACA",
        "usuario": "1042441719",
        "password": "pasarex123*",
        "placa": "REB56E"
    },"user_19": {
        "nombre": "HUMBERTO RAFAEL ROMO GONZALEZ",
        "usuario": "1193153842",
        "password": "pasarex123*",
        "placa": "ARF10D"
    },
    "user_20": {
        "nombre": "JUAN DIEGO JARAMILLO GUTIERREZ",
        "usuario": "15440034",
        "password": "pasarex123*",
        "placa": "VVP09E"
    },
    "user_21": {
        "nombre": "DEINER DAVID BERMUDEZ LEON",
        "usuario": "1065574406",
        "password": "pasarex123*",
        "placa": "GZS19H"
    },
    "user_22": {
        "nombre": "CARLOS MATEO HIGUERA GRAJALES",
        "usuario": "1037654159",
        "password": "pasarex123*",
        "placa": "ITS93G"
    },
    "user_23": {
        "nombre": "DAVID FELIPE DUQUE LOPEZ",
        "usuario": "1001891994",
        "password": "pasarex123*",
        "placa": "EXE91B"
    },
    "user_24": {
        "nombre": "YULIETH ANDREA GAVIRIA VALENCIA",
        "usuario": "1036951826",
        "password": "pasarex123*",
        "placa": "QNW57B"
    }

}



# def obtener_credenciales(credencial_id: str):
#     if credencial_id not in CREDENCIALES:
#         raise ValueError(f"Credencial no válida: {credencial_id}")
#     return CREDENCIALES[credencial_id]

# # 🔥 recibe credencial/guias desde el frontend vía variables de entorno
DEFAULT_CREDENCIAL = "user_9"

# os.environ["PASAREX_GUIAS"] = '["AMZPSR021540578"]'
def _obtener_credencial_desde_entorno() -> str:
    credencial = os.getenv("PASAREX_CREDENCIAL", DEFAULT_CREDENCIAL)
    if credencial in CREDENCIALES:
        return credencial

    print(f"⚠️ Credencial inválida recibida: {credencial}. Usando {DEFAULT_CREDENCIAL}.")
    return DEFAULT_CREDENCIAL


def _obtener_guias_desde_entorno():
    raw_guias = os.getenv("PASAREX_GUIAS", "[]")

    try:
        parsed = json.loads(raw_guias)
    except json.JSONDecodeError:
        parsed = raw_guias.replace(",", "\n").split("\n")

    if not isinstance(parsed, list):
        parsed = [parsed]

    return [str(item).strip() for item in parsed if str(item).strip()]


CREDENCIAL_SELECCIONADA = _obtener_credencial_desde_entorno()
guias = _obtener_guias_desde_entorno()

cred = CREDENCIALES[CREDENCIAL_SELECCIONADA]
EMAIL_PRO = cred["usuario"]
PASSWORD_PRO = cred["password"]


# ---------------- Driver helpers -------------------
def build_driver(headless: bool = False):
    options = Options()

    # ─── PERFIL REAL DE CHROME (CLAVE) ───
    options.add_argument(
        r"--user-data-dir=C:\Users\jhami\AppData\Local\Google\Chrome\User Data"
    )
    options.add_argument("--profile-directory=Profile 3")

    # ─── Flags base seguros ───
    options.add_argument("--start-maximized")
    options.add_argument("--lang=es-ES")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")

    # ─── Anti detección ligera (segura con perfil real) ───
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # ⚠️ NO cambiar el user-agent cuando usas perfil real
    # ⚠️ NO cargar extensiones externas
    # ⚠️ NO usar headless con captcha

    if headless:
        options.add_argument("--headless=new")

    service = Service(chromedriver_autoinstaller.install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.set_page_load_timeout(90)
    driver.set_script_timeout(60)

    # Warm-up
    driver.get("about:blank")
    time.sleep(2)

    return driver

def wait_for(drv, timeout=30):
    return WebDriverWait(drv, timeout)


def robust_get(driver, url: str, wait_selector=None, timeout: int = 45, label: str = ""):
    print(f"➡️  Navegando a {label or url}")
    try:
        driver.get(url)
    except TimeoutException:
        try:
            ready = driver.execute_script("return document.readyState")
        except WebDriverException:
            ready = "unknown"
        if ready not in ("interactive", "complete"):
            ts = int(time.time())
            try:
                driver.save_screenshot(f"/tmp/nav_timeout_{ts}.png")
            except Exception:
                pass
            try:
                with open(f"/tmp/nav_timeout_{ts}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source or "")
            except Exception:
                pass
            time.sleep(2)
            driver.get(url)
    if wait_selector:
        wait_for(driver, timeout).until(EC.presence_of_element_located(wait_selector))


# # ---------------- Proships ------------------------

def safe_type(driver, locator, text, timeout=30, clear_first=True, retries=6):
    """Re-localiza el input cada intento para evitar stale en React/AntD."""
    last_err = None
    for _ in range(retries):
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            el.click()
            time.sleep(0.05)
            if clear_first:
                el.clear()
            el.send_keys(text)
            return el
        except (StaleElementReferenceException,) as e:
            last_err = e
            time.sleep(0.25)
    if last_err:
        raise last_err

def safe_js_set_value(driver, locator, value, timeout=30, retries=6):
    """Para inputs AntD que a veces no reaccionan bien a clear/send_keys."""
    last_err = None
    for _ in range(retries):
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            driver.execute_script("""
                const el = arguments[0];
                const val = arguments[1];
                el.focus();
                el.value = '';
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.value = val;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, el, value)
            return el
        except StaleElementReferenceException as e:
            last_err = e
            time.sleep(0.25)
    if last_err:
        raise last_err

def safe_click_locator(driver, locator, timeout=30, retries=6):
    last_err = None
    for _ in range(retries):
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            driver.execute_script("arguments[0].click();", el)
            return el
        except StaleElementReferenceException as e:
            last_err = e
            time.sleep(0.25)
    if last_err:
        raise last_err

def login_proships(driver):
    robust_get(
        driver,
        LOGIN_URL_TRACKER,
        wait_selector=(By.CSS_SELECTOR, "input[data-testid='user-input']"),
        label="Login Proships"
    )

    w = WebDriverWait(driver, 40)

    # (Opcional) espera a que no haya spinner de AntD
    try:
        w.until_not(EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-spin-spinning")))
    except TimeoutException:
        pass

    # Usuario / Password (relocalizando para evitar stale)
    safe_type(driver, (By.CSS_SELECTOR, "input[data-testid='user-input']"), EMAIL_PRO, timeout=40)

    try:
        pass_locator = (By.CSS_SELECTOR, "input[data-testid='password-input']")
        w.until(EC.presence_of_element_located(pass_locator))
    except TimeoutException:
        pass_locator = (By.CSS_SELECTOR, "input[name='password'], input[type='password']")

    safe_type(driver, pass_locator, PASSWORD_PRO, timeout=40)

    # Submit
    try:
        safe_click_locator(driver, (By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]'), timeout=15)
    except TimeoutException:
        # fallback Enter sobre password
        safe_type(driver, pass_locator, Keys.ENTER, timeout=10, clear_first=False)

    # Confirmación "Si" (si aparece)
    try:
        safe_click_locator(
            driver,
            (By.XPATH, "//button[.//span[normalize-space()='Si'] or normalize-space()='Si']"),
            timeout=10
        )
        print("✅ Confirmación de sesión aceptada (Sí)")
    except TimeoutException:
        pass

    # Modal estación de trabajo (solo 1 bloque, robusto)
    try:
        station_locator = (By.CSS_SELECTOR, "input#station[data-testid='station-input']")
        safe_js_set_value(driver, station_locator, "1", timeout=20)
        # botón submit del modal
        safe_click_locator(driver, (By.CSS_SELECTOR, "div.ant-modal-root button.ant-btn-primary[type='submit']"), timeout=20)
        w.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.ant-modal-wrap")))
        print("✅ Estación de trabajo configurada (1)")
    except TimeoutException:
        pass

    # Espera real: que salga de /sign-in
    w.until(lambda d: "/sign-in" not in d.current_url)
    print("✅ Login tracker OK")

    # Navegación
    safe_click_locator(driver, (By.XPATH, "//button[.//span[normalize-space()='PED']]"), timeout=30)
    safe_click_locator(driver, (By.XPATH, "//button[.//span[normalize-space()='Guía']]"), timeout=30)

    ingresar_guias(driver, guias)

def safe_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.2)
    try:
        el.click()
    except (ElementClickInterceptedException, StaleElementReferenceException):
        driver.execute_script("arguments[0].click();", el)





GUIDE_INPUT_SEL = (By.CSS_SELECTOR, "input[data-testid='guide-input']")

def ingresar_guias(driver, guias):
    w = WebDriverWait(driver, 30)

    for guia in guias:
        intentos = 0
        while True:
            try:
                # 🔥 re-buscar el input CADA VEZ (evita stale)
                guide_input = w.until(EC.element_to_be_clickable(GUIDE_INPUT_SEL))

                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", guide_input)
                time.sleep(0.15)
                guide_input.click()
                time.sleep(0.1)

                # limpiar y escribir
                guide_input.send_keys(Keys.CONTROL, "a")
                guide_input.send_keys(Keys.BACKSPACE)
                guide_input.send_keys(guia)
                guide_input.send_keys(Keys.ENTER)

                print(f"✅ Guía ingresada: {guia}")

                # espera mini para que procese / re-render
                time.sleep(0.4)

                break

            except StaleElementReferenceException:
                intentos += 1
                if intentos >= 5:
                    raise
                time.sleep(0.3)

            except TimeoutException:
                intentos += 1
                if intentos >= 5:
                    raise
                time.sleep(0.5)

    # ✅ Cuando termine TODAS las guías, ahora sí entra a Pasarex
    print("✅ Todas las guías ingresadas. Continuando a Proveedores Pasarex...")
    login_proveedores_pasarex(driver)


def login_proveedores_pasarex(driver, usuario="1002158571", password="1002158571"):
    """
    Login en Proveedores Pasarex.
    - Intenta resolver reCAPTCHA con NopeCHA.
    - Si falla → permite login manual.
    - Detecta acceso exitoso cuando URL contenga /intranet
    """

    print("➡️ Iniciando login en Proveedores Pasarex...")
    driver.get("https://proveedores.pasarex.com/login")

    w = WebDriverWait(driver, 90)

    try:
        # ─────────── INGRESAR CREDENCIALES ───────────
        user_input = w.until(EC.element_to_be_clickable((
            By.XPATH,
            "//label[contains(.,'ID de usuario')]/following::input[1] | "
            "//input[@placeholder='ID de usuario' or @name='usuario' or @id='usuario']"
        )))
        user_input.clear()
        user_input.send_keys(usuario)

        pass_input = w.until(EC.element_to_be_clickable((
            By.XPATH,
            "//label[contains(.,'Clave')]/following::input[1] | "
            "//input[@placeholder='Clave' or @placeholder='Contraseña' or @type='password']"
        )))
        pass_input.clear()
        pass_input.send_keys(password)

        print("✅ Credenciales ingresadas.")

        # ─────────── ESPERAR CAPTCHA AUTOMÁTICO ───────────
        print("🟡 Esperando resolución automática de reCAPTCHA (NopeCHA)...")

        try:
            WebDriverWait(driver, 60).until(
                lambda d: d.execute_script(
                    "return document.getElementById('g-recaptcha-response')?.value?.length > 10 || false"
                )
            )
            print("✅ reCAPTCHA resuelto automáticamente.")
        except TimeoutException:
            print("⚠️ NopeCHA no resolvió el captcha automáticamente.")

        # ─────────── CLICK LOGIN ───────────
        login_button = w.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[@type='submit' and (contains(., 'Ingresar') or contains(., 'Login') or contains(., 'Acceder'))] | "
            "//input[@type='submit' and contains(@value, 'Ingresar')]"
        )))

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_button)
        login_button.click()

        print("✅ Click en 'Ingresar' realizado.")

    except Exception as e:
        print(f"⚠️ Error en login automático: {str(e)}")

    # ─────────── ESPERAR LOGIN (AUTO O MANUAL) ───────────
    print("🟡 Esperando acceso al sistema (auto o manual)...")

    try:
        WebDriverWait(driver, 180).until(
            lambda d: "proveedores.pasarex.com/intranet" in d.current_url
        )
        print("✅ Login exitoso detectado (URL intranet).")

    except TimeoutException:
        print("⚠️ No se detectó acceso automático.")
        print("👉 Si el captcha falló, resuélvelo manualmente en el navegador.")
        print("👉 El sistema continuará cuando detecte la URL /intranet...")

        # Espera indefinida hasta que el usuario entre manualmente
        WebDriverWait(driver, 600).until(
            lambda d: "proveedores.pasarex.com/intranet" in d.current_url
        )

        print("✅ Login manual detectado correctamente.")

    # ─────────── IR A PLANILLA ───────────
    time.sleep(2)
    driver.get("https://proveedores.pasarex.com/planilla_ped_tracker")

    try:
        w.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("✅ Entraste a la planilla ped_tracker")
    except:
        print("⚠️ No cargó la planilla → revisa si el login fue exitoso.")

    # Continúa el flujo
    seleccionar_estacion_resto_antioquia(driver)

def seleccionar_estacion_resto_antioquia(driver):
    w = WebDriverWait(driver, 30)

    # Click en el select (Select2)
    select_span = w.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR, "span#select2-station-container"
    )))
    select_span.click()

    # Espera a que aparezca el dropdown y selecciona "Resto de Antioquia"
    opcion = w.until(EC.element_to_be_clickable((
        By.XPATH,
        "//li[contains(@class,'select2-results__option') and normalize-space()='Resto de Antioquia']"
    )))
    opcion.click()
    seleccionar_courier(driver, CREDENCIAL_SELECCIONADA)

def seleccionar_courier(driver, credencial_id):
    nombre_completo = (CREDENCIALES[credencial_id]["nombre"] or "").strip()
    primera = nombre_completo.split()[0] if nombre_completo else ""

    w = WebDriverWait(driver, 30)

    select_btn_xpath = "//label[contains(.,'Courier Activos')]/following::span[contains(@class,'select2-selection')][1]"
    rendered_xpath   = "//label[contains(.,'Courier Activos')]/following::span[contains(@class,'select2-selection__rendered')][1]"
    option_li_css    = "ul#select2-courier-results li.select2-results__option"

    def norm(s: str) -> str:
        return " ".join((s or "").strip().lower().split())

    def click_select2_option(li_el):
        js = """
        const el = arguments[0];
        if (!el) return false;
        el.scrollIntoView({block:'nearest'});
        ['mousedown','mouseup','click'].forEach(ev=>{
          el.dispatchEvent(new MouseEvent(ev, {bubbles:true, cancelable:true, view:window}));
        });
        return true;
        """
        driver.execute_script(js, li_el)

    def esperar_render_seleccionado():
        def ok(d):
            try:
                txt = (d.find_element(By.XPATH, rendered_xpath).text or "").strip()
                return txt and "buscar courier" not in txt.lower()
            except Exception:
                return False
        w.until(ok)
        return driver.find_element(By.XPATH, rendered_xpath).text.strip()

    def intentar_busqueda(primer_keyword: str, timeout_total=12.0):
        # abrir dropdown (si no está abierto)
        btn = w.until(EC.element_to_be_clickable((By.XPATH, select_btn_xpath)))
        btn.click()

        box = w.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input.select2-search__field")))
        box.clear()
        box.send_keys(primer_keyword)

        target = norm(nombre_completo)
        elegido = None
        t0 = time.time()

        while time.time() - t0 < timeout_total:
            lis = driver.find_elements(By.CSS_SELECTOR, option_li_css)
            for li in lis:
                txt = (li.text or "").strip()
                if txt and norm(txt) == target:
                    elegido = li
                    break
            if elegido:
                break
            time.sleep(0.3)

        if not elegido:
            # cerrar dropdown antes de reintentar
            try:
                box.send_keys(Keys.ESCAPE)
            except Exception:
                pass
            return False

        click_select2_option(elegido)
        esperar_render_seleccionado()
        return True

    # 1er intento (12s)
    ok = intentar_busqueda(primera, timeout_total=12.0)

    # 2do intento (otros 12s) si no encontró exacto
    if not ok:
        ok = intentar_busqueda(primera, timeout_total=12.0)

    if not ok:
        raise Exception(f"No apareció coincidencia exacta en 2 intentos para: '{nombre_completo}' (buscado: '{primera}')")

    seleccionado = driver.find_element(By.XPATH, rendered_xpath).text.strip()
    print(f"✅ Courier seleccionado: {seleccionado} | escrito: {primera} | target: {nombre_completo}")

    # Generar vista
    generar = w.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Generar Vista')]")))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", generar)
    driver.execute_script("arguments[0].click();", generar)

    confirmar = w.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Confirmar vehículo')]")))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", confirmar)
    driver.execute_script("arguments[0].click();", confirmar)

    seleccionar_vehiculo_y_confirmar(driver, credencial_id)

def seleccionar_vehiculo_y_confirmar(driver, texto_busqueda):
    texto_busqueda = CREDENCIALES[texto_busqueda]["placa"]

    w = WebDriverWait(driver, 30)

    # 0) esperar modal visible
    w.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div#confirmContractor.modal.show")))

    # 1) click en el select2 del modal (contractor)
    select_modal = w.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR,
        "div#confirmContractor .select2-selection--single"
    )))
    try:
        select_modal.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", select_modal)

    search_box = w.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR,
        "input.select2-search__field"
    )))
    search_box.clear()
    search_box.send_keys(texto_busqueda)

    # pequeño delay para que filtre
    time.sleep(0.4)

    # 3️⃣ Click a la opción resaltada (highlighted)
    highlighted_option = w.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR,
        "li.select2-results__option--highlighted"
    )))
    highlighted_option.click()

    print(f"✅ Courier seleccionado: {texto_busqueda}")


    time.sleep(0.5)


    print(f"✓ Vehículo '{texto_busqueda}' seleccionado")
    # 4) click en Confirmar dentro del modal
    confirm_button = w.until(EC.element_to_be_clickable((
        By.XPATH, "//button[contains(., 'Confirmar')]"
    )))
    confirm_button.click()
    print("✅ Click en 'Confirmar' realizado.")

  # Esperar a que el botón "Generar Planilla" esté clickeable
    confirmar_planilla = w.until(EC.element_to_be_clickable((
        By.XPATH, "//button[contains(., 'Generar Planilla')]"
    )))
    confirmar_planilla.click()
    print("✅ Click en 'Generar Planilla' realizado.")
    confirmar_simpli = w.until(EC.element_to_be_clickable((
        By.XPATH, "//button[contains(., 'Transmitir Tracker SimpliRoute')]"
    )))
    confirmar_simpli.click()
    print("✅ Click en 'Transmitir Tracker SimpliRoute' realizado.")

      # 4. Ahora, ESPERAR Y MANEJAR LA ALERTA DE ÉXITO DE ESTA ITERACIÓN
    if aceptar_alert_si_aparece(driver, timeout=20):
        driver.quit()
        raise SystemExit

def aceptar_alert_si_aparece(driver, timeout=2):
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        a = driver.switch_to.alert
        txt = a.text
        a.accept()
        print(f"✅ Alert aceptado: {txt}")
        return True
    except TimeoutException:
        return False

def aceptar_alert_si_aparece(driver, timeout=2):
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        a = driver.switch_to.alert
        txt = a.text
        a.accept()
        print(f"✅ Alert aceptado: {txt}")
        return True
    except TimeoutException:
        return False

if __name__ == "__main__":
    driver = build_driver(headless=HEADLESS)  # usa tu config real

    try:
        if not guias:
            raise ValueError("No se recibieron guías para procesar. Envía PASAREX_GUIAS desde el frontend.")
        login_proships(driver)
    finally:
        driver.quit()
