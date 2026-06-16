import os
import time
from pathlib import Path
from typing import List
import pandas as pd
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
# ===================== CONFIG =====================
# --- Proships ---
LOGIN_URL_PROSHIPS = "https://correos-app-backend.mailamericas.com/auth/login"
CREATE_ORDER_URL = "https://correos-app-backend.mailamericas.com/create_order"

EMAIL_PRO = os.getenv("PROSHIPS_EMAIL", "jara.171201@gmail.com")
PASSWORD_PRO = os.getenv("PROSHIPS_PASSWORD", "Ontime01")

SEARCH_INPUT = (By.CSS_SELECTOR, "#top-search, input#search, input[placeholder*='Search'], input[placeholder*='Buscar']")
TIMELINE_CONTAINER = (By.CSS_SELECTOR, ".timeline-items, .shipment-timeline, .timeline")
TABLE_SELECTOR = (By.CSS_SELECTOR, "table.table, table.table-hover, table.table-striped, table.table-condensed")

# Archivos
PAQUETES_FILE = "paquetes.xlsx"
SALIDA_CSV = "resultados.csv"
ARCHIVO_GENERADO = "archivo_create_order.xlsx"
EMAIL_DUMMY = "prueba@correo.com"

HEADLESS = False
# ===================================================

credenciales = {
    "usuario1": {
        "nombre": "Kevin Andres Bermejo Baca",
        "email": "kevinbermejo830@gmail.com"
    },
    "usuario2": {
        "nombre": "Maria Lucelly Gomez Gomez",
        "email": "glorluyean.81@gmail.com"
    },
    "usuario3": {
        "nombre": "Luis Camilo Velasquez Betancur",
        "email": "camilobeta58@gmail.com"
    },
    "usuario4": {
        "nombre": "Victor Manuel Zapata Madrid",
        "email": "zapatavictor7819@gmail.com"
    },
    "usuario5": {
        "nombre": "Sara Camila Quiroz Arango",
        "email": "sara456766@gmail.com"
    },
    "usuario6": {
        "nombre": "Juan Diego Jaramillo Gutierrez",
        "email": "jara.7827@gmail.com"
    },
    "usuario7": {
        "nombre": "Juan Antonio Millan Pelaez",
        "email": "millan1107pelaez@gmail.com"
    },
    "usuario8": {
        "nombre": "Juan Esteban Jaramillo David",
        "email": "jara.171201@gmail.com"
    },
        "usuario9": {
        "nombre": "Javier Alejandro Rendon Vanegas",
        "email": "alejo-lds90@hotmail.es"
    },
    "usuario10": {
        "nombre": "Yeison Mejia Munera",
        "email": "yeikmejias@gmail.com"
    },
        "usuario11": {
        "nombre": "Nelson Ferney Ramirez Perez",
        "email": "nelsonferneyramirezperez@gmail.com"
    },
    "usuario12": {
        "nombre": "Daladier Zuluaga Castro",
        "email": "daladierzuluaga5@gmail.com"
    },
    "usuario13": {
        "nombre": "Edgar Alexander Vargas Rios",
        "email": "genesiscastillo88.cg@gmail.com"
    },
        "usuario14": {
        "nombre": "Wilson de Jesus Patiño Cardona",
        "email": "wilsonp.c794@gmail.com"
    },
    "usuario15": {
        "nombre": "Esteban Buitrago Silva",
        "email": "buitragoesteban123@gmail.com"
    },
    "usuario16": {
        "nombre": "Willian Arley Gomez Garcia",
        "email": "willaregomez01@gmail.com"
    },
    "usuario17": {
        "nombre": "Mauricio Castañeda Cifuentes",
        "email": "taisaxxx127@gmail.com"
    },
        "usuario18": {
        "nombre": "Julian Camilo Duque Lopez",
        "email": "juliancamiloduquelopez@gmail.com"
    },
    "usuario19": {
        "nombre": "Yohan Sebastian Zuluaga Saldarriaga",
        "email": "caramelozuluaga599@gmail.com"
    },
    "usuario20": {
        "nombre": "Carlos Mateo Higuera Grajales",
        "email": "mateohiguera64@gmail.com"
    },
    "usuario21": {
        "nombre": "David Felipe Duque López",
        "email": "ciroangie684@gmail.com"
    },
        "usuario22": {
        "nombre": "Brayan Rendon Rendon",
        "email": "brayanren95@gmail.com"
    },
        "usuario23": {
        "nombre": "Juan David Castañeda",
        "email": "juandavidcc17@gmail.com"
    }
}
DEFAULT_CREDENTIAL = next(iter(credenciales.keys()))


def _obtener_email_dummy_desde_entorno() -> str:
    credential_id = os.getenv("PROSHIPS_CREDENTIAL", "").strip()
    if credential_id and credential_id in credenciales:
        return (credenciales[credential_id].get("email") or EMAIL_DUMMY).strip()

    raw_email = os.getenv("PROSHIPS_EMAIL_DUMMY", "").strip()
    if raw_email:
        return raw_email

    return EMAIL_DUMMY


def _obtener_paquetes_desde_entorno() -> List[str]:
    raw = os.getenv("PROSHIPS_GUIAS", "")
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw.replace(",", "\n").split("\n")

    if not isinstance(parsed, list):
        parsed = [parsed]

    return [str(item).strip() for item in parsed if str(item).strip()]
# ---------------- Driver helpers -------------------
def build_driver(headless: bool = False):
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=es-ES,es;q=0.9")
    options.add_argument("--window-size=1366,900")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if headless:
        options.add_argument("--headless=new")

    service = Service(chromedriver_autoinstaller.install())

    driver = webdriver.Chrome(
        service=service,
        options=options
    )
    
    driver.set_page_load_timeout(90)
    driver.set_script_timeout(60)
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


# ---------------- Proships ------------------------
# ---------------- Excel -------------------
def leer_paquetes_desde_excel(path_excel):
    ruta = Path(path_excel)

    if not ruta.exists():
        raise RuntimeError(f"No se encontró el archivo: {ruta}")

    df = None
    ultimo_error = None

    try:
        df = pd.read_excel(str(ruta), dtype=str, engine="openpyxl", header=None)
    except Exception as e:
        ultimo_error = e

    if df is None:
        try:
            df = pd.read_excel(str(ruta), dtype=str, engine="xlrd", header=None)
        except Exception as e:
            ultimo_error = e

    if df is None:
        try:
            df = pd.read_csv(str(ruta), dtype=str, header=None)
        except Exception as e:
            ultimo_error = e

    if df is None:
        raise RuntimeError(f"No se pudo leer el archivo {ruta}. Error: {ultimo_error}")

    df = df.fillna("")

    if df.empty:
        raise RuntimeError("El archivo está vacío")

    paquetes = list(dict.fromkeys(str(x).strip() for x in df.iloc[:, 0].tolist() if str(x).strip()))

    if not paquetes:
        raise RuntimeError("No se encontraron paquetes en la primera columna")

    return paquetes

def generar_excel_create_order(paquetes: List[str], email_dummy: str = EMAIL_DUMMY) -> str:
    df = pd.DataFrame({
        "tracking_number": paquetes,
        "email": [email_dummy] * len(paquetes)
    })

    salida = Path(ARCHIVO_GENERADO).resolve()
    df.to_excel(salida, index=False)

    print(f"✅ Archivo generado: {salida}")
    print(f"📦 Total paquetes: {len(paquetes)}")
    return str(salida)


# ---------------- Login -------------------
def set_react_input_value(driver, element, value):
    driver.execute_script("""
        const el = arguments[0];
        const value = arguments[1];
        const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeSetter.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
    """, element, value)


def login_proships(driver):
    robust_get(
        driver,
        LOGIN_URL_PROSHIPS,
        wait_selector=(By.CSS_SELECTOR, "input[placeholder='Email'], input[type='email'], input[type='text']"),
        label="Login Proships"
    )

    w = wait_for(driver, 40)

    email_el = w.until(EC.presence_of_element_located((
        By.CSS_SELECTOR,
        "input[placeholder='Email'], input[type='email'], input[type='text']"
    )))
    pass_el = w.until(EC.presence_of_element_located((
        By.CSS_SELECTOR,
        "input[placeholder='Password'], input[type='password']"
    )))

    email_el.click()
    time.sleep(0.3)
    set_react_input_value(driver, email_el, EMAIL_PRO)

    pass_el.click()
    time.sleep(0.3)
    set_react_input_value(driver, pass_el, PASSWORD_PRO)

    time.sleep(1)

    login_btn = w.until(EC.presence_of_element_located((
        By.XPATH, "//button[contains(., 'Login') or @type='submit']"
    )))

    if login_btn.is_enabled():
        try:
            login_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", login_btn)
    else:
        pass_el.send_keys(Keys.ENTER)

    # espera a salir del login o al menos a cambiar de página
    for _ in range(15):
        if "/auth/login" not in driver.current_url.lower():
            print("✅ Login Proships OK")
            return
        time.sleep(1)

    raise Exception("No se pudo iniciar sesión en Proships")


# ---------------- Upload file -------------------
def subir_archivo_create_order(driver, ruta_archivo: str):
    robust_get(
        driver,
        CREATE_ORDER_URL,
        wait_selector=(By.TAG_NAME, "body"),
        label="Create Order"
    )

    w = wait_for(driver, 30)
    time.sleep(3)

    file_input = None
    selectores = [
        (By.CSS_SELECTOR, "input[type='file']"),
        (By.XPATH, "//input[@type='file']"),
    ]

    for by, sel in selectores:
        try:
            file_input = w.until(EC.presence_of_element_located((by, sel)))
            if file_input:
                break
        except Exception:
            continue

    if not file_input:
        raise Exception("No se encontró el input file en create_order")

    # por si está oculto
    driver.execute_script("""
        arguments[0].style.display = 'block';
        arguments[0].style.visibility = 'visible';
        arguments[0].style.opacity = 1;
    """, file_input)

    file_input.send_keys(str(Path(ruta_archivo).resolve()))
    print(f"✅ Archivo cargado en create_order: {ruta_archivo}")
    attach_selectores = [
        (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'attach packages')]"),
        (By.CSS_SELECTOR, "button.btn.btn-primary"),
    ]

    attach_btn = None
    for by, selector in attach_selectores:
        try:
            attach_btn = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((by, selector)))
            if attach_btn:
                break
        except Exception:
            continue

    if attach_btn:
        try:
            attach_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", attach_btn)
        print("✅ Botón 'Attach packages' presionado")
    else:
        print("⚠️ No se encontró el botón 'Attach packages'")
    estado = esperar_successful_assignments(driver, timeout=120)
    print(f"✅ Estado final detectado: {estado}")
    return estado


def esperar_successful_assignments(driver, timeout=120):
    selectores = [
        (By.XPATH, "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'successful assignments')]"),
        (By.CSS_SELECTOR, "h2.text-white.font-semibold"),
    ]

    fin = time.time() + timeout
    while time.time() < fin:
        for by, selector in selectores:
            try:
                elementos = driver.find_elements(by, selector)
            except Exception:
                elementos = []

            for el in elementos:
                texto = (el.text or "").strip()
                if texto and "successful assignments" in texto.lower():
                    print(f"STATUS: {texto}")
                    return texto

        time.sleep(1)

    raise TimeoutException("No apareció el mensaje 'Successful assignments'")

# ---------------- Main -------------------
def main():
    paquetes = _obtener_paquetes_desde_entorno() or leer_paquetes_desde_excel(PAQUETES_FILE)
    (PAQUETES_FILE)
    email_dummy = _obtener_email_dummy_desde_entorno()
    archivo_generado = generar_excel_create_order(paquetes, email_dummy)
    driver = build_driver(headless=HEADLESS)

    try:
        login_proships(driver)
        estado_final = subir_archivo_create_order(driver, archivo_generado)
        print(f"✅ Flujo completado: {estado_final}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()