import os
import json
import time
from datetime import date
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import chromedriver_autoinstaller

PACKTRACK_LOGIN_URL = "https://packtrack.site/users/sign_in"
PACKTRACK_NEW_URL = "https://packtrack.site/paquetes/new"
PACKTRACK_EMAIL = os.getenv("PACKTRACK_EMAIL", "oriente@ontime.com")
PACKTRACK_PASSWORD = os.getenv("PACKTRACK_PASSWORD", "ontime.1712")
IMILE_CLIENTE_ID = "36"

# ---------------- CREDENCIALES -------------------
CREDENCIALES = {
    "usuario1": {
        "nombre": "Jose Manuel Vargas Pastrana",
        "municipio_id": "5",
    },
    "usuario2": {
        "nombre": "Kevin Andres Bermejo Baca",
        "municipio_id": "5",
    },
}

DEFAULT_CREDENCIAL = "usuario1"


def _obtener_credencial_desde_entorno() -> str:
    credencial = os.getenv("IMILE_CREDENCIAL", DEFAULT_CREDENCIAL).strip()
    if credencial in CREDENCIALES:
        return credencial
    print(f"⚠️ Credencial inválida: {credencial}. Usando {DEFAULT_CREDENCIAL}.")
    return DEFAULT_CREDENCIAL


def _obtener_guias_desde_entorno():
    raw_guias = os.getenv("IMILE_GUIAS", "[]")
    try:
        parsed = json.loads(raw_guias)
    except json.JSONDecodeError:
        parsed = raw_guias.replace(",", "\n").split("\n")
    if not isinstance(parsed, list):
        parsed = [parsed]
    return [str(item).strip() for item in parsed if str(item).strip()]


def build_driver(headless: bool = False):
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    if headless:
        opts.add_argument("--headless=new")
    service = Service(chromedriver_autoinstaller.install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(90)
    return driver


def login_packtrack(driver):
    driver.get(PACKTRACK_LOGIN_URL)
    w = WebDriverWait(driver, 30)
    w.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='user[email]']")))
    driver.find_element(By.CSS_SELECTOR, "input[name='user[email]']").send_keys(PACKTRACK_EMAIL)
    driver.find_element(By.CSS_SELECTOR, "input[name='user[password]']").send_keys(PACKTRACK_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "input[name='user[password]']").send_keys(Keys.ENTER)
    WebDriverWait(driver, 20).until(lambda d: "/users/sign_in" not in d.current_url)
    print("✅ Login PackTrack OK")


def _find_mensajero_id(driver, nombre: str) -> str:
    opts = driver.find_elements(By.CSS_SELECTOR, "select[name='paquete[mensajero_id]'] option")
    nombre_lower = nombre.strip().lower()
    for o in opts:
        text = driver.execute_script("return arguments[0].textContent", o).strip().lower()
        val = o.get_attribute("value") or ""
        if not val:
            continue
        if text == nombre_lower:
            return val
        # partial match: all words of nombre present in text
        words = nombre_lower.split()
        if all(w in text for w in words):
            return val
    available = [
        driver.execute_script("return arguments[0].textContent", o).strip()
        for o in opts if o.get_attribute("value")
    ]
    raise RuntimeError(
        f"Mensajero '{nombre}' no encontrado en PackTrack.\n"
        f"Disponibles: {available}"
    )


def asignar_en_packtrack(driver, guias: list, nombre_mensajero: str, municipio_id: str):
    driver.get(PACKTRACK_NEW_URL)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[name='paquete[codigo]']"))
    )
    time.sleep(2)

    # Open the modal
    driver.execute_script("document.getElementById('modal-paquete').classList.remove('hidden')")
    time.sleep(1)

    # Fill codes
    textarea = driver.find_element(By.CSS_SELECTOR, "textarea[name='paquete[codigo]']")
    driver.execute_script("arguments[0].value = arguments[1]", textarea, "\n".join(guias))

    # Cliente = I Mile (36)
    Select(driver.find_element(By.CSS_SELECTOR, "select[name='paquete[cliente_id]']")).select_by_value(IMILE_CLIENTE_ID)

    # Mensajero
    mensajero_id = _find_mensajero_id(driver, nombre_mensajero)
    Select(driver.find_element(By.CSS_SELECTOR, "select[name='paquete[mensajero_id]']")).select_by_value(mensajero_id)
    print(f"  Mensajero seleccionado: {nombre_mensajero} (id={mensajero_id})")

    # Municipio
    Select(driver.find_element(By.CSS_SELECTOR, "select[name='paquete[municipio_id]']")).select_by_value(municipio_id)

    # Date = today
    today = date.today().strftime("%Y-%m-%d")
    date_input = driver.find_element(By.CSS_SELECTOR, "input[name='paquete[date]']")
    driver.execute_script("arguments[0].value = arguments[1]", date_input, today)

    # Submit
    submit = driver.find_element(By.CSS_SELECTOR, "input[name='commit']")
    driver.execute_script("arguments[0].click()", submit)

    # Wait for redirect (success = redirect away from /new, or success message)
    try:
        WebDriverWait(driver, 30).until(
            lambda d: "paquetes/new" not in d.current_url or
            "exitosamente" in d.find_element(By.TAG_NAME, "body").text.lower() or
            "creado" in d.find_element(By.TAG_NAME, "body").text.lower() or
            "asignado" in d.find_element(By.TAG_NAME, "body").text.lower()
        )
        print(f"✅ {len(guias)} guía(s) asignadas en PackTrack.")
    except TimeoutException:
        body = driver.find_element(By.TAG_NAME, "body").text[:300]
        print(f"⚠️ No se confirmó redirección. Estado: {body}")

    print(f"URL final: {driver.current_url}")


def main():
    credencial_id = _obtener_credencial_desde_entorno()
    guias = _obtener_guias_desde_entorno()
    cred = CREDENCIALES[credencial_id]

    if not guias:
        print("⚠️ No hay guías para asignar.")
        print("STATUS: OK")
        return

    print(f"Asignando {len(guias)} guía(s) a {cred['nombre']}...")
    driver = build_driver(headless=False)
    try:
        login_packtrack(driver)
        asignar_en_packtrack(driver, guias, cred["nombre"], cred["municipio_id"])
    finally:
        driver.quit()

    print("STATUS: OK")


if __name__ == "__main__":
    main()
