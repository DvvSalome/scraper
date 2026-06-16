import csv
import os
import re
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
import sys
sys.path.append("..")


# ===================== CONFIG =====================
BASE_URL_PQ = "https://packtrack.site"
LOGIN_URL_PQ = f"{BASE_URL_PQ}/users/sign_in"
PAQUETES_URL = f"{BASE_URL_PQ}/paquetes"
MENSAJEROS_URL = f"{BASE_URL_PQ}/mensajeros"

EMAIL_PQ = os.getenv("PAQUETES_EMAIL", "oriente@ontime.com")
PASSWORD_PQ = os.getenv("PAQUETES_PASSWORD", "ontime.1712")

HEADLESS = False
PAQUETES_TXT = Path(__file__).with_name("paquetes.txt")
RESULTADOS_CSV = Path(__file__).with_name("resultados.csv")
GUIAS_SIN_ASIGNAR_TXT = Path(__file__).with_name("guias_sin_asignar.txt")
TELEGRAM_PROFILE_DIR = Path(__file__).with_name("telegram_profile")
SEND_TELEGRAM = os.getenv("SEND_TELEGRAM", "1").strip().lower() in {"1", "true", "yes", "on"}

TARIFAS_EMPRESA = {
    "pasarex": {
        "plus": 3000,
        "normal": 3000
    },
    "proships": {
        "plus": 2700,
        "normal": 2500
    },
    "x-cargo": {
        "plus": 2000,
        "normal": 2000
    }
}


EMPRESA_NOMBRE = os.getenv("CONTABILIDAD_EMPRESA", "proships").strip().lower()

MENSAJERO_DESCONOCIDO = "sin mensajero"
TELEFONO_DESCONOCIDO = "sin telefono"
# ==================================================

TIPOS_MUNICIPIO = {
    "rionegro": "normal",
    "marinilla": "normal",
    "rionegro - vereda": "rural",
    "marinilla - vereda": "rural",
    "el santuario": "rural",
    "el retiro": "rural",
    "la unión": "rural",
    "la union": "rural",
    "guarne": "rural",
    "guatapé / peñol": "rural",
    "guatape / peñol": "rural",
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
    options.add_argument(f"--user-data-dir={TELEGRAM_PROFILE_DIR.resolve()}")
    options.add_argument("--profile-directory=Default")
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


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        texto = str(value).strip().lower()
        if texto in {"", "sin telefono", "none", "null", "-"}:
            return default
        texto = "".join(ch for ch in str(value) if ch.isdigit() or ch == "-")
        if texto in {"", "-"}:
            return default
        return int(texto)
    except Exception:
        return default
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


def normalizar_nombre_busqueda(nombre: str) -> str:
    nombre = (nombre or "").lower().strip()
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre


def normalizar_telefono(valor: str) -> str:
    import re

    raw = (valor or "").strip()
    if not raw:
        return "sin telefono"

    digits = re.sub(r"\D+", "", raw)

    if len(digits) == 10:
        digits = "57" + digits
    elif digits.startswith("57") and len(digits) > 12:
        digits = digits[:12]
    elif len(digits) > 10 and not digits.startswith("57"):
        digits = digits[-10:]
        digits = "57" + digits

    if len(digits) != 12:
        return "sin telefono"

    return digits

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
            "telefono": TELEFONO_DESCONOCIDO,
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
        return {
            "tracking": tracking,
            "mensajero": MENSAJERO_DESCONOCIDO,
            "telefono": TELEFONO_DESCONOCIDO,
            "municipio": "SIN MUNICIPIO",
            "tipo_municipio": "normal",
        }

    mensajero = _paquetes_pick_col(fila, headers_map, ["mensajero", "courier", "driver", "repartidor"], default_index=4)
    municipio = _paquetes_pick_col(fila, headers_map, ["municipio", "ciudad", "destino"], default_index=5)
    tipo_municipio = _paquetes_pick_col(fila, headers_map, ["tipo", "zona", "plus", "rural"], default_index=6)

    municipio_clean = (municipio or "SIN MUNICIPIO").strip().lower()
    tipo_final = TIPOS_MUNICIPIO.get(municipio_clean, (tipo_municipio or "normal").lower())

    return {
        "tracking": tracking,
        "mensajero": normalizar_mensajero(mensajero),
        "telefono": TELEFONO_DESCONOCIDO,
        "municipio": municipio or "SIN MUNICIPIO",
        "tipo_municipio": tipo_final,
    }


def abrir_directorio_mensajeros(driver):
    robust_get(
        driver,
        MENSAJEROS_URL,
        wait_selector=(By.CSS_SELECTOR, "input#query, input[name='query'], table tbody"),
        timeout=30,
        label="Mensajeros",
    )


def obtener_input_busqueda_mensajero(driver):
    selectors = [
        (By.CSS_SELECTOR, "input#query"),
        (By.CSS_SELECTOR, "input[name='query']"),
        (By.CSS_SELECTOR, "form[action='/mensajeros'] input[type='text']"),
        (By.CSS_SELECTOR, ".search input[type='text']"),
        (By.CSS_SELECTOR, "input[placeholder*='mensajero']"),
    ]
    for by, selector in selectors:
        elementos = driver.find_elements(by, selector)
        for el in elementos:
            try:
                if el.is_displayed() and el.is_enabled():
                    return el
            except Exception:
                continue
    raise NoSuchElementException("No encontré el buscador de mensajeros.")


def buscar_celular_en_packtrack(driver, nombre_mensajero: str) -> str:
    import time
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        abrir_directorio_mensajeros(driver)

        nombre_objetivo = normalizar_nombre_busqueda(nombre_mensajero)

        input_busqueda = WebDriverWait(driver, 20).until(
            lambda d: (
                d.find_element(By.CSS_SELECTOR, "input#query")
                if d.find_elements(By.CSS_SELECTOR, "input#query")
                else d.find_element(By.CSS_SELECTOR, "input[name='query']")
            )
        )

        input_busqueda.click()
        input_busqueda.send_keys(Keys.CONTROL, "a")
        input_busqueda.send_keys(Keys.BACKSPACE)
        time.sleep(0.3)

        input_busqueda.send_keys(nombre_mensajero)
        time.sleep(0.5)

        # ✅ forzar búsqueda
        input_busqueda.send_keys(Keys.ENTER)
        time.sleep(2)

        # ✅ esperar a que carguen filas
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tbody tr"))
        )

        filas = driver.find_elements(By.CSS_SELECTOR, "tbody tr")

        for fila in filas:
            celdas = fila.find_elements(By.CSS_SELECTOR, "td")
            if len(celdas) < 2:
                continue

            nombre_fila = normalizar_nombre_busqueda(celdas[0].text)
            celular_fila = normalizar_telefono(celdas[1].text)

            if nombre_fila == nombre_objetivo:
                return celular_fila

        for fila in filas:
            celdas = fila.find_elements(By.CSS_SELECTOR, "td")
            if len(celdas) < 2:
                continue

            nombre_fila = normalizar_nombre_busqueda(celdas[0].text)
            celular_fila = normalizar_telefono(celdas[1].text)

            if nombre_objetivo in nombre_fila or nombre_fila in nombre_objetivo:
                return celular_fila

        print(f"⚠️ Sin coincidencias de teléfono para mensajero: {nombre_mensajero}")
        return "sin telefono"
    except Exception as exc:
        print(f"⚠️ Error buscando teléfono para '{nombre_mensajero}': {exc}")
        return "sin telefono"
def asignar_telefonos_desde_busqueda(driver, resumen):
    enviados = set()
    enviados_count = 0
    faltantes = 0

    for row in resumen:
        nombre = str(row.get("mensajero", "")).strip()

        if not nombre or nombre.lower() == "sin mensajero":
            print(f"⚠️ Mensajero inválido: {nombre}")
            continue

        telefono = buscar_celular_en_packtrack(driver, nombre)

        if not telefono or telefono == "sin telefono":
            print(f"⚠️ {nombre} no tiene teléfono")
            faltantes += 1
            continue

        clave_envio = (nombre.lower(), str(telefono).strip())

        if clave_envio in enviados:
            print(f"⚠️ Mensaje duplicado evitado para {nombre} - {telefono}")
            continue

        enviados.add(clave_envio)
        enviados_count += 1
        print(f"✅ Mensaje enviado a {nombre} - {telefono}")

    print(f"✅ Mensajes enviados: {enviados_count} | Sin teléfono: {faltantes}")
def es_plus(tipo_municipio: str, municipio: str) -> bool:
    texto = f"{tipo_municipio} {municipio}".lower()
    return any(keyword in texto for keyword in ["plus", "rural", "vereda", "corregimiento"])

def obtener_tarifas_empresa():
    empresa = EMPRESA_NOMBRE.lower()

    if empresa in TARIFAS_EMPRESA:
        return TARIFAS_EMPRESA[empresa]

    return {
        "plus": 2700,
        "normal": 2500
    }
from typing import List, Dict, Any
def consolidar_por_mensajero(registros: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    resumen: Dict[str, Dict[str, Any]] = {}

    for reg in registros:
        mensajero = normalizar_mensajero(reg.get("mensajero", ""))

        if mensajero not in resumen:
            resumen[mensajero] = {
                "mensajero": mensajero,
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

    tarifas = obtener_tarifas_empresa()

    for mensajero, data in resumen.items():
        plus = safe_int(data.get("plus", 0))
        normal = safe_int(data.get("normal", 0))

        data["plus"] = plus
        data["normal"] = normal
        data["total_plus"] = plus * tarifas["plus"]
        data["total_normal"] = normal * tarifas["normal"]
        data["total_general"] = data["total_plus"] + data["total_normal"]

    return sorted(resumen.values(), key=lambda row: row["mensajero"])

def exportar_csv(resumen, ruta_csv):
    import csv

    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "mensajero",
            "plus",
            "total_plus",
            "normal",
            "total_normal",
            "total_general",
        ])

        for row in resumen:
            writer.writerow([
                row["mensajero"],
                row["plus"],
                row["total_plus"],
                row["normal"],
                row["total_normal"],
                row["total_general"],
            ])


def exportar_guias_sin_asignar(registros: List[Dict[str, str]], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    guias = [
        (registro.get("tracking") or "").strip()
        for registro in registros
        if normalizar_mensajero(registro.get("mensajero", "")) == MENSAJERO_DESCONOCIDO
    ]
    output_path.write_text("\n".join(filter(None, guias)), encoding="utf-8")


def formato_pesos(valor: int) -> str:
    return f"{safe_int(valor):,}".replace(",", ".")


def recortar(texto: str, largo: int) -> str:
    texto = (texto or "").strip()
    if len(texto) <= largo:
        return texto
    if largo <= 1:
        return texto[:largo]
    return texto[: largo - 1] + "…"


def armar_mensaje(row):
    mensajero = str(row.get("mensajero", "")).strip()

    plus = int(row.get("plus", 0))
    total_plus = int(row.get("total_plus", 0))

    normal = int(row.get("normal", 0))
    total_normal = int(row.get("total_normal", 0))
    
    general = plus + normal;
    total_general = int(row.get("total_general", 0))

    empresa = (EMPRESA_NOMBRE or "").strip().lower()

    nombre_empresa = {
        "x-cargo": "x cargo",
        "proships": "proships",
        "pasarex": "pasarex",
    }.get(empresa, empresa)

    if nombre_empresa == "pasarex":
        return (
            f"Reporte automático de servicios - {nombre_empresa} \n\n"
            f"Del 16 al 28 de febrero\n"
            f"Nombre: {mensajero}\n"
            f"Detalle:\n"
            f"* Servicios Plus: {general} = ${total_general:,.0f}\n"
            f"Total a pagar: ${total_general:,.0f}\n"
            f"Sistema de liquidación – Mensajería\n"
        )
    else:
        return (
            f"Reporte automático de servicios - {nombre_empresa} \n\n"
            f"Del 16 al 28 de febrero\n"
            f"Nombre: {mensajero}\n"
            f"Detalle:\n"
            f"* Servicios Plus: {plus} = ${total_plus:,.0f}\n"
            f"* Servicios Estándar: {normal} = ${total_normal:,.0f}\n"
            f"Total a pagar: ${total_general:,.0f}\n"
            f"Sistema de liquidación – Mensajería\n"
        )

def esperar_telegram_listo(driver, timeout: int = 180):
    print("➡️ Abriendo Telegram Web")
    robust_get(driver, "https://web.telegram.org/a/", wait_selector=(By.TAG_NAME, "body"), timeout=30, label="Telegram Web")
    limite = time.time() + timeout

    while time.time() < limite:
        body = (driver.page_source or "").lower()

        if any(x in body for x in ["scan from the mobile app", "log in by qr code", "código qr", "escanear"]):
            print("📷 Escanea el QR de Telegram Web...")
            time.sleep(3)
            continue

        if driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'], .chatlist, .ListItem, .tabs-tab"):
            print("✅ Telegram listo")
            return

        time.sleep(2)

    raise TimeoutException("No se pudo iniciar sesión en Telegram Web a tiempo.")


def _click_primero_visible(driver, selectors: List[str], timeout: int = 10) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        for selector in selectors:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    if el.is_displayed() and el.is_enabled():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.2)
                        driver.execute_script("arguments[0].click();", el)
                        return True
                except Exception:
                    continue
        time.sleep(0.5)
    return False


def abrir_chat_telegram(driver, telefono: str) -> bool:
    telefono = normalizar_telefono(telefono)
    if telefono == TELEFONO_DESCONOCIDO:
        print("⚠️ Teléfono inválido, se omite.")
        return False

    robust_get(driver, f"https://t.me/+{telefono}", wait_selector=(By.TAG_NAME, "body"), timeout=20, label=f"Telegram {telefono}")
    time.sleep(2)

    _click_primero_visible(
        driver,
        selectors=[
            "a[href*='web.telegram.org']",
            "a[href*='tg://resolve']",
            ".tgme_action_button_new",
            ".tgme_action_button",
            "button",
        ],
        timeout=10,
    )
    time.sleep(4)

    return "web.telegram.org" in driver.current_url.lower() or bool(
        driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true']")
    )


def obtener_caja_mensaje(driver, timeout: int = 20):
    end = time.time() + timeout
    selectors = [
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true'].input-message-input",
        "div[contenteditable='true']",
    ]
    while time.time() < end:
        for selector in selectors:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    if el.is_displayed() and el.is_enabled():
                        return el
                except Exception:
                    continue
        time.sleep(0.5)
    raise TimeoutException("No encontré la caja de mensaje de Telegram.")


def enviar_mensaje_telegram(driver, telefono: str, mensaje: str) -> bool:
    if not abrir_chat_telegram(driver, telefono):
        print(f"⚠️ No se pudo abrir el chat para {telefono}")
        return False

    try:
        caja = obtener_caja_mensaje(driver, timeout=20)
        driver.execute_script("arguments[0].focus();", caja)
        time.sleep(0.3)

        caja.send_keys(Keys.CONTROL, "a")
        caja.send_keys(Keys.BACKSPACE)

        lineas = mensaje.split("\n")
        for i, linea in enumerate(lineas):
            caja.send_keys(linea)
            if i < len(lineas) - 1:
                caja.send_keys(Keys.SHIFT, Keys.ENTER)

        time.sleep(0.8)
        caja.send_keys(Keys.ENTER)
        print(f"✅ Mensaje enviado a {telefono}")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"❌ Error enviando a {telefono}: {e}")
        return False


def enviar_resumenes_por_telegram(driver, resumen: List[Dict[str, float]]):
    esperar_telegram_listo(driver)

    enviados = 0
    omitidos = 0

    for row in resumen:
        try:
            telefono = buscar_celular_en_packtrack(driver, row["mensajero"])
            if telefono == "sin telefono":
                omitidos += 1
                continue

            mensaje = armar_mensaje(row)

            print("\n" + "=" * 80)
            print(mensaje)
            print("=" * 80 + "\n")

            if enviar_mensaje_telegram(driver, telefono, mensaje):
                enviados += 1
            else:
                omitidos += 1
        except Exception as exc:
            print(f"⚠️ No se pudo procesar mensajero '{row.get('mensajero', '')}': {exc}")
            omitidos += 1
            continue


    print(f"✅ Telegram finalizado. Enviados: {enviados} | Omitidos/Fallidos: {omitidos}")

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
        asignar_telefonos_desde_busqueda(driver, resumen)

        exportar_csv(resumen, RESULTADOS_CSV)
        exportar_guias_sin_asignar(registros, GUIAS_SIN_ASIGNAR_TXT)
        print(f"✅ Reporte exportado en: {RESULTADOS_CSV}")
        if SEND_TELEGRAM:
            enviar_resumenes_por_telegram(driver, resumen)
        else:
            print("ℹ️ Envío por Telegram desactivado (SEND_TELEGRAM=0).")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
