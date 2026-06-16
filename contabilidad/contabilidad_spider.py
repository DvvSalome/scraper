import csv
import os
import time
from pathlib import Path
from typing import Dict, List

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import chromedriver_autoinstaller

# ===================== CONFIG =====================
BASE_URL_PQ = "https://packtrack.site"
LOGIN_URL_PQ = f"{BASE_URL_PQ}/users/sign_in"
PAQUETES_URL = f"{BASE_URL_PQ}/paquetes"
EMAIL_PQ = os.getenv("PAQUETES_EMAIL", "oriente@ontime.com")
PASSWORD_PQ = os.getenv("PAQUETES_PASSWORD", "ontime.1712")

HEADLESS = False
PAQUETES_TXT = Path(__file__).with_name("paquetes.txt")
RESULTADOS_CSV = Path(__file__).with_name("resultados.csv")
VALOR_NORMAL = 2500
VALOR_PLUS = 2700
MENSAJERO_DESCONOCIDO = "sin mensajero"
GUIAS_SIN_ASIGNAR_TXT = Path(__file__).with_name("guias_sin_asignar.txt")
# ==================================================
TIPOS_MUNICIPIO = {
    "rionegro": "normal",
    "marinilla": "normal",
    "rionegro - vereda": "rural",
    "marinilla - vereda": "rural",
    "el santuario": "rural",
    "el retiro": "rural",
    "la unión": "rural",
    "guarne": "rural",
    "guatapé / peñol": "rural",
    "el carmen de viboral": "normal",
}

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
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(90)
    driver.set_script_timeout(60)
    return driver


def wait_for(drv, timeout=30):
    return WebDriverWait(drv, timeout)


def robust_get(driver, url: str, wait_selector=None, timeout: int = 45, label: str = ""):
    print(f"➡️ Navegando a {label or url}")
    try:
        driver.get(url)
    except TimeoutException:
        try:
            ready = driver.execute_script("return document.readyState")
        except WebDriverException:
            ready = "unknown"
        if ready not in ("interactive", "complete"):
            time.sleep(2)
            driver.get(url)

    if wait_selector:
        wait_for(driver, timeout).until(EC.presence_of_element_located(wait_selector))


def login_paquetes(driver):
    robust_get(
        driver,
        LOGIN_URL_PQ,
        wait_selector=(By.CSS_SELECTOR, "form input[name='authenticity_token'], input[name='user[email]'], input[name='user[password]']"),
        label="Login Packtrack",
    )
    w = wait_for(driver, 30)

    email_el = w.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='user[email]']")))
    pass_el = w.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='user[password]']")))

    email_el.clear()
    email_el.send_keys(EMAIL_PQ)
    pass_el.clear()
    pass_el.send_keys(PASSWORD_PQ)
    time.sleep(0.3)

    submits = driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
    submit_el = None
    for el in submits:
        try:
            if el.is_displayed() and el.is_enabled():
                submit_el = el
                break
        except Exception:
            continue

    try:
        if submit_el:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", submit_el)
            time.sleep(0.1)
            submit_el.click()
        else:
            raise NoSuchElementException("No hay submit visible habilitado")
    except Exception:
        try:
            if submit_el:
                driver.execute_script("arguments[0].click();", submit_el)
            else:
                raise
        except Exception:
            pass_el.send_keys(Keys.ENTER)

    w.until(lambda d: "/users/sign_in" not in d.current_url)
    print("✅ Login Packtrack OK")




def normalizar_mensajero(valor: str) -> str:
    nombre = (valor or "").strip()
    if not nombre:
        return MENSAJERO_DESCONOCIDO

    nombre_lc = nombre.lower()
    aliases_sin_mensajero = {
        "sin mensajero",
        "sin_mensajero",
        "ninguno",
        "n/a",
        "na",
        "null",
        "none",
        "-",
    }

    if nombre_lc in aliases_sin_mensajero:
        return MENSAJERO_DESCONOCIDO

    return nombre

def _paquetes_map_headers(driver) -> Dict[str, int]:
    headers = driver.find_elements(By.CSS_SELECTOR, "table thead tr th")
    mapping = {}
    for idx, header in enumerate(headers):
        key = (header.text or "").strip().lower()
        if key:
            mapping[key] = idx
    return mapping


def _paquetes_pick_col(tds_texts: List[str], headers_map: Dict[str, int], wanted_names: List[str], default_index=None) -> str:
    if headers_map:
        for wanted in wanted_names:
            for header_name, idx in headers_map.items():
                if wanted in header_name and idx < len(tds_texts):
                    return (tds_texts[idx] or "").strip()
    if default_index is not None and default_index < len(tds_texts):
        return (tds_texts[default_index] or "").strip()
    return ""


def leer_paquetes(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo con paquetes: {path}")

    paquetes = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        codigo = raw.strip()
        if codigo:
            paquetes.append(codigo)
    return paquetes


def paquetes_buscar_y_extraer(driver, tracking: str) -> Dict[str, str]:
    robust_get(
        driver,
        f"{PAQUETES_URL}?codigo={tracking}",
        wait_selector=(By.TAG_NAME, "body"),
        label=f"Paquete {tracking}",
    )

    contenido_pagina = (driver.page_source or "").lower()
    if "no hay paquetes disponibles" in contenido_pagina:
        return {
            "tracking": tracking,
            "mensajero": MENSAJERO_DESCONOCIDO,
            "municipio": "SIN MUNICIPIO",
            "tipo_municipio": "normal",
        }

    headers_map = _paquetes_map_headers(driver)

    fila = None
    for tr in driver.find_elements(By.CSS_SELECTOR, "tbody tr"):
        tds = tr.find_elements(By.CSS_SELECTOR, "td")
        tds_texts = [(td.text or "").strip() for td in tds]
        if not tds_texts:
            continue
        if tracking in tds_texts[0]:
            fila = tds_texts
            break

    if not fila:
        return {"tracking": tracking, "mensajero": MENSAJERO_DESCONOCIDO, "municipio": "SIN MUNICIPIO", "tipo_municipio": "normal"}

    mensajero = _paquetes_pick_col(fila, headers_map, ["mensajero", "courier", "driver", "repartidor"], default_index=4)
    municipio = _paquetes_pick_col(fila, headers_map, ["municipio", "ciudad", "destino"], default_index=5)
    tipo_municipio = _paquetes_pick_col(fila, headers_map, ["tipo", "zona", "plus", "rural"], default_index=6)
    municipio_clean = (municipio or "SIN MUNICIPIO").strip().lower()

    tipo_final = TIPOS_MUNICIPIO.get(municipio_clean, (tipo_municipio or "normal").lower())

    return {
        "tracking": tracking,
        "mensajero": normalizar_mensajero(mensajero),
        "municipio": municipio or "SIN MUNICIPIO",
        "tipo_municipio": tipo_final,
    }

def es_plus(tipo_municipio: str, municipio: str) -> bool:
    texto = f"{tipo_municipio} {municipio}".lower()
    return any(keyword in texto for keyword in ["plus", "rural", "vereda", "corregimiento"])


def consolidar_por_mensajero(registros: List[Dict[str, str]]) -> List[Dict[str, float]]:
    resumen: Dict[str, Dict[str, float]] = {}

    for reg in registros:
        mensajero = normalizar_mensajero(reg.get("mensajero", ""))
        if mensajero not in resumen:
            resumen[mensajero] = {
                "plus": 0,
                "total_plus": 0,
                "normal": 0,
                "total_normal": 0,
                "total_general": 0,
            }

        if es_plus(reg["tipo_municipio"], reg["municipio"]):
            resumen[mensajero]["plus"] += 1
        else:
            resumen[mensajero]["normal"] += 1

    for mensajero, data in resumen.items():
        data["total_plus"] = data["plus"] * VALOR_PLUS
        data["total_normal"] = data["normal"] * VALOR_NORMAL
        data["total_general"] = data["total_plus"] + data["total_normal"]
        data["mensajero"] = mensajero

    return sorted(resumen.values(), key=lambda row: row["mensajero"])


def exportar_csv(resumen: List[Dict[str, float]], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Mensajero", "Plus", "Total plus", "Normal", "Total normal", "Total general"])
        for row in resumen:
            writer.writerow([
                row["mensajero"],
                int(row["plus"]),
                row["total_plus"] / 1000,
                int(row["normal"]),
                row["total_normal"] / 1000,
                row["total_general"] / 1000,
            ])
def exportar_guias_sin_asignar(registros: List[Dict[str, str]], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    guias = [
        (registro.get("tracking") or "").strip()
        for registro in registros
        if normalizar_mensajero(registro.get("mensajero", "")) == MENSAJERO_DESCONOCIDO
    ]
    output_path.write_text("\n".join(filter(None, guias)), encoding="utf-8")


def main():
    paquetes = leer_paquetes(PAQUETES_TXT)
    if not paquetes:
        print(f"⚠️ No hay paquetes en {PAQUETES_TXT}")
        return

    driver = build_driver(headless=HEADLESS)
    try:
        login_paquetes(driver)
        registros = []
        for idx, tracking in enumerate(paquetes, start=1):
            print(f"🔎 [{idx}/{len(paquetes)}] Consultando {tracking}")
            registros.append(paquetes_buscar_y_extraer(driver, tracking))

        resumen = consolidar_por_mensajero(registros)
        exportar_csv(resumen, RESULTADOS_CSV)
        exportar_guias_sin_asignar(registros, GUIAS_SIN_ASIGNAR_TXT)
        print(f"✅ Reporte exportado en: {RESULTADOS_CSV}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
