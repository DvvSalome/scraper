import os
import time
import csv
import urllib.parse
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller

options = Options()
options.add_argument("--start-maximized")

# ===================== CONFIG =====================
# --- Proships ---
LOGIN_URL_PROSHIPS = "https://tracking.proships.com/login"
SHIPMENTS_URL = "https://tracking.proships.com/shipments"
EMAIL_PRO = os.getenv("PROSHIPS_EMAIL", "jara.171201@gmail.com")
PASSWORD_PRO = os.getenv("PROSHIPS_PASSWORD", "Ontime01")

SEARCH_INPUT = (By.CSS_SELECTOR, "#top-search, input#search, input[placeholder*='Search'], input[placeholder*='Buscar']")
TIMELINE_CONTAINER = (By.CSS_SELECTOR, ".timeline-items, .shipment-timeline, .timeline")
TABLE_SELECTOR = (By.CSS_SELECTOR, "table.table, table.table-hover, table.table-striped, table.table-condensed")

# --- Paquetes (Rails) ---
BASE_URL_PQ = "https://packtrack.site"
LOGIN_URL_PQ = f"{BASE_URL_PQ}/users/sign_in"
PAQUETES_URL = f"{BASE_URL_PQ}/paquetes"
DEVOLUCIONES_URL = f"{BASE_URL_PQ}/devolucions"
EMAIL_PQ = os.getenv("PAQUETES_EMAIL", "oriente@ontime.com")
PASSWORD_PQ = os.getenv("PAQUETES_PASSWORD", "ontime.1712")


MENSAJEROS_URL = f"{BASE_URL_PQ}/mensajeros"

# --- WhatsApp Web (envío a mensajeros) ---
SEND_WHATSAPP = os.getenv("SEND_WHATSAPP", "0") == "1"   # export SEND_WHATSAPP=1 para enviar
WHATSAPP_COUNTRY_CODE = os.getenv("WHATSAPP_COUNTRY_CODE", "57")  # Colombia por defecto
WHATSAPP_FIRST_LOAD_SEC = int(os.getenv("WHATSAPP_FIRST_LOAD_SEC", "120"))  # tiempo para escanear QR la 1ra vez
WHATSAPP_CHAT_READY_SEC = int(os.getenv("WHATSAPP_CHAT_READY_SEC", "35"))
WHATSAPP_WAIT_TICKS_SEC = int(os.getenv("WHATSAPP_WAIT_TICKS_SEC", "45"))
WHATSAPP_PROFILE_DIR = Path(os.getenv("WHATSAPP_PROFILE_DIR", str(Path.cwd() / ".whatsapp_web_profile")))
WHATSAPP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

MENSAJES_OUT_CSV = "mensajes_whatsapp.csv"
# Archivos
PAQUETES_FILE = "paquetes.txt"
SALIDA_CSV = "resultados.csv"

HEADLESS = False
# ===================================================


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
def login_proships(driver):
    robust_get(driver, LOGIN_URL_PROSHIPS, wait_selector=(By.CSS_SELECTOR, "input[name='email'], input[type='email']"), label="Login Proships")
    w = wait_for(driver, 40)

    email_el = w.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='email'], input[type='email']")))
    email_el.clear(); email_el.send_keys(EMAIL_PRO)

    pass_el = w.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password'], input[type='password']")))
    pass_el.clear(); pass_el.send_keys(PASSWORD_PRO)

    try:
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]').click()
    except NoSuchElementException:
        pass_el.send_keys(Keys.ENTER)

    w.until(lambda d: "/login" not in d.current_url)
    print("✅ Login Proships OK")


def _find_search_input(driver):
    inputs = driver.find_elements(*SEARCH_INPUT)
    for el in inputs:
        if el.is_displayed() and el.is_enabled():
            return el
    for sel in ["input[name='search']", "input[name='q']"]:
        found = driver.find_elements(By.CSS_SELECTOR, sel)
        for el in found:
            if el.is_displayed() and el.is_enabled():
                return el
    raise NoSuchElementException("No se encontró el campo de búsqueda en Proships.")


def proships_buscar(driver, tracking: str):
    try:
        inp = _find_search_input(driver)
    except Exception:
        robust_get(driver, SHIPMENTS_URL, wait_selector=SEARCH_INPUT, timeout=45, label="Shipments Proships")
        inp = _find_search_input(driver)

    inp.clear()
    inp.send_keys(tracking)
    inp.send_keys(Keys.ENTER)

    # Espera la sección de timeline o algo que indique resultados
    try:
        wait_for(driver, 25).until(EC.presence_of_element_located(TIMELINE_CONTAINER))
    except TimeoutException:
        time.sleep(1.0)


def proships_extraer_timeline(driver) -> Dict[str, str]:
    data = {"checkpoint_code": ""}
    try:
        first_item = driver.find_element(By.CSS_SELECTOR, ".timeline-items .row .timeline-item, .timeline-items .timeline-item, .timeline .timeline-item")
    except Exception:
        return data

    for sel in ["address.checkpoint-code", ".checkpoint-code", ".checkpoint, address"]:
        try:
            chk = first_item.find_element(By.CSS_SELECTOR, sel)
            text = chk.text.strip()
            if text:
                data["checkpoint_code"] = text
                break
        except Exception:
            continue
    return data


def proships_extraer_contacto(driver) -> Dict[str, str]:
    out = {"buyer": "", "phone": "", "address": ""}
    try:
        wait_for(driver, 12).until(EC.presence_of_element_located(TABLE_SELECTOR))
    except Exception:
        return out

    etiquetas = ["buyer", "phone", "tel", "teléfono", "address", "dirección"]
    tablas = driver.find_elements(By.CSS_SELECTOR, "table")

    tabla_objetivo = None
    for tbl in tablas:
        try:
            html = (tbl.get_attribute("innerText") or "").lower()
        except Exception:
            continue
        if any(lbl in html for lbl in etiquetas):
            tabla_objetivo = tbl
            break

    if tabla_objetivo is None:
        return out

    filas = tabla_objetivo.find_elements(By.CSS_SELECTOR, "tr")
    for tr in filas:
        celdas = tr.find_elements(By.CSS_SELECTOR, "th,td")
        if len(celdas) < 2:
            continue
        label = (celdas[0].text or "").strip().lower()
        valor_td = (celdas[1].text or "").strip()

        if not out["buyer"] and "buyer" in label:
            out["buyer"] = valor_td
        elif not out["phone"] and ("phone" in label or "tel" in label or "teléfono" in label):
            out["phone"] = valor_td
        elif not out["address"] and ("address" in label or "dirección" in label):
            out["address"] = valor_td

    return out


def proships_procesar(driver, tracking: str) -> Dict[str, str]:
    proships_buscar(driver, tracking)
    timeline = proships_extraer_timeline(driver)
    contacto = proships_extraer_contacto(driver)
    return {"tracking": tracking, **timeline, **contacto}


# ---------------- Paquetes (Rails) -----------------
def login_paquetes(driver):
    robust_get(
        driver,
        LOGIN_URL_PQ,
        wait_selector=(By.CSS_SELECTOR, "form input[name='authenticity_token'], input[name='user[email]'], input[name='user[password]']"),
        label="Login Paquetes"
    )
    w = wait_for(driver, 30)

    # Campos
    email_el = w.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='user[email]']")))
    pass_el  = w.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='user[password]']")))

    # Llenar
    email_el.clear(); email_el.send_keys(EMAIL_PQ)
    pass_el.clear();  pass_el.send_keys(PASSWORD_PQ)

    time.sleep(0.3)  # deja que la UI habilite el botón

    # Buscar el primer submit visible y habilitado
    submits = driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
    submit_el = None
    for el in submits:
        try:
            if el.is_displayed() and el.is_enabled():
                submit_el = el
                break
        except Exception:
            continue

    # 1) Click normal
    try:
        if submit_el:
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", submit_el)
            time.sleep(0.1)
            submit_el.click()
        else:
            raise NoSuchElementException("No hay submit visible habilitado")
    except Exception:
        # 2) Click por JS
        try:
            if submit_el:
                driver.execute_script("arguments[0].click();", submit_el)
            else:
                raise
        except Exception:
            # 3) ENTER en el password
            try:
                pass_el.send_keys(Keys.ENTER)
            except Exception:
                # 4) Submit explícito del form (último recurso)
                try:
                    form = driver.find_element(By.CSS_SELECTOR, "form")
                    driver.execute_script("arguments[0].submit();", form)
                except Exception:
                    # Guardar evidencia y relanzar
                    ts = int(time.time())
                    try: driver.save_screenshot(f"/tmp/login_paquetes_click_{ts}.png")
                    except: pass
                    raise

    # Esperar que salga del login
    w.until(lambda d: "/users/sign_in" not in d.current_url)
    print("✅ Login Paquetes OK")

def _paquetes_map_headers(driver) -> Dict[str, int]:
    headers = driver.find_elements(By.CSS_SELECTOR, "table thead tr th")
    mapping = {}
    for idx, h in enumerate(headers):
        key = (h.text or "").strip().lower()
        if key:
            mapping[key] = idx
    return mapping


def _paquetes_pick_col(tds_texts: List[str], headers_map: Dict[str, int], wanted_names: List[str], default_index=None) -> str:
    if headers_map:
        for wanted in wanted_names:
            for k, idx in headers_map.items():
                if wanted in k:
                    if idx < len(tds_texts):
                        return (tds_texts[idx] or "").strip()
    if default_index is not None and default_index < len(tds_texts):
        return (tds_texts[default_index] or "").strip()
    return ""


def paquetes_buscar_y_extraer(driver, tracking: str) -> Dict[str, str]:
    # 1) /paquetes
    robust_get(driver, f"{PAQUETES_URL}?codigo={tracking}", label=f"Paquetes {tracking}")
    headers_map = _paquetes_map_headers(driver)

    fila = None
    for tr in driver.find_elements(By.CSS_SELECTOR, "tbody tr"):
        tds = tr.find_elements(By.CSS_SELECTOR, "td")
        tds_texts = [(td.text or "").strip() for td in tds]
        if not tds_texts:
            continue
        if tds_texts[0] == tracking:
            fila = tds_texts
            break

    fecha = ""
    mensajero = ""
    estado = ""

    if fila:
        fecha = _paquetes_pick_col(fila, headers_map, ["fecha", "date"], default_index=1)
        mensajero = _paquetes_pick_col(fila, headers_map, ["mensajero", "courier", "driver", "repartidor"], default_index=4)
        estado = _paquetes_pick_col(fila, headers_map, ["estado", "status", "situacion", "observacion"], default_index=2)

    return {
        "fecha": (fecha or "").strip(),
        "mensajero": (mensajero or "").strip(),
        "estado": (estado or "SIN ESTADO").strip()
    }



# ---------------- Mensajeros (Rails) -----------------
def _normalize_mensajero_phone(raw_phone: str) -> str:
    digits = "".join(ch for ch in str(raw_phone or "") if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith(WHATSAPP_COUNTRY_CODE):
        return digits
    # si viene sin país, asumimos Colombia
    if len(digits) == 10:
        return WHATSAPP_COUNTRY_CODE + digits
    return digits

def mensajero_buscar_celular(driver, mensajero_nombre: str) -> str:
    """Busca el celular del mensajero en /mensajeros?query=<NOMBRE>.

    La tabla tiene una columna llamada 'Celular' (puede venir como Celular, celular, etc).
    """
    nombre = (mensajero_nombre or "").strip()
    if not nombre:
        return ""

    url = f"{MENSAJEROS_URL}?query={urllib.parse.quote(nombre)}"
    robust_get(driver, url, wait_selector=(By.CSS_SELECTOR, "table"), timeout=25, label=f"Mensajeros {nombre}")

    # map headers
    headers = driver.find_elements(By.CSS_SELECTOR, "table thead tr th")
    headers_norm = [(h.text or "").strip().lower() for h in headers]
    idx_cel = None
    for i, h in enumerate(headers_norm):
        if "celular" in h:
            idx_cel = i
            break
    if idx_cel is None:
        return ""

    # primera fila del resultado filtrado
    trs = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    if not trs:
        return ""

    tds = trs[0].find_elements(By.CSS_SELECTOR, "td")
    if idx_cel >= len(tds):
        return ""

    celular_raw = (tds[idx_cel].text or "").strip()
    return _normalize_mensajero_phone(celular_raw)

# ---------------- WhatsApp Web (Selenium) -----------------
def _wa_normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if not digits:
        return ""
    # si viene sin país y es 10 dígitos, asumimos Colombia
    if len(digits) == 10:
        digits = WHATSAPP_COUNTRY_CODE + digits
    if not digits.startswith(WHATSAPP_COUNTRY_CODE) and len(digits) == 10:
        digits = WHATSAPP_COUNTRY_CODE + digits
    return digits

def build_whatsapp_driver(headless: bool = False):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--lang=es-ES")
    opts.add_argument("--start-maximized")
    opts.add_argument(f"--user-data-dir={WHATSAPP_PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    if headless:
        opts.add_argument("--headless=new")
    return webdriver.Chrome(options=opts)

def wa_wait_logged_in(driver):
    """Espera a que WhatsApp Web esté listo. Si hay QR, espera hasta WHATSAPP_FIRST_LOAD_SEC."""
    driver.get("https://web.whatsapp.com/")
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pane-side")))
        return True
    except Exception:
        print("🔑 Escanea el QR de WhatsApp (solo la primera vez)...")
        try:
            WebDriverWait(driver, WHATSAPP_FIRST_LOAD_SEC).until(EC.presence_of_element_located((By.ID, "pane-side")))
            return True
        except Exception:
            return False

def wa_wait_two_ticks(driver, timeout=WHATSAPP_WAIT_TICKS_SEC) -> bool:
    """
    Espera a que el último mensaje SALIENTE tenga doble chulo (entregado/leído).
    Importante: esto asume que el mensaje ya fue creado (message-out existe).
    """
    end = time.time() + timeout

    ok_selectors = [
        "span[data-testid='msg-dblcheck']",
        "span[aria-label*='Delivered']",
        "span[aria-label*='Entregado']",
        "span[aria-label*='Read']",
        "span[aria-label*='Leído']",
    ]
    failed_selectors = [
        "span[data-testid='msg-error']",
        "span[aria-label*='Not sent']",
        "span[aria-label*='No enviado']",
        "span[aria-label*='Error']",
    ]

    while time.time() < end:
        outs = driver.find_elements(By.CSS_SELECTOR, "div.message-out")
        if not outs:
            time.sleep(0.25)
            continue

        last = outs[-1]

        # Si falló el envío, corta de una
        for sel in failed_selectors:
            try:
                if last.find_elements(By.CSS_SELECTOR, sel):
                    return False
            except Exception:
                pass

        # Doble chulo / entregado / leído
        for sel in ok_selectors:
            try:
                if last.find_elements(By.CSS_SELECTOR, sel):
                    return True
            except Exception:
                pass

        time.sleep(0.35)

    return False

def wa_esperar_caja_mensaje(driver, timeout=45):
    selectores = [
        "footer div[contenteditable='true']",
        "div[contenteditable='true'][data-tab]",
        "div[title='Escribe un mensaje']",
        "div[aria-label='Escribe un mensaje']",
        "div[aria-label='Type a message']",
    ]

    end = time.time() + timeout
    ultimo_error = None

    while time.time() < end:
        for sel in selectores:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elementos:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except Exception as e:
                ultimo_error = e
        time.sleep(0.4)

    raise TimeoutException(f"No apareció la caja de mensaje. Último error: {ultimo_error}")


def send_whatsapp_messages(mensajes: List[Dict[str, str]]):
    if not mensajes:
        print("📭 No hay mensajes para enviar por WhatsApp.")
        return

    driver = build_whatsapp_driver(headless=False)
    try:
        if not wa_wait_logged_in(driver):
            print("❌ No pude confirmar sesión de WhatsApp.")
            return
        print("✅ Sesión WhatsApp activa (se guarda en el perfil).")

        enviados = set()

        for m in mensajes:
            phone = _wa_normalize_phone((m.get("celular") or "").strip())
            text  = (m.get("mensaje") or "").strip()

            if not phone or not text:
                continue
            if phone in enviados:
                continue

            # abrir chat con texto precargado
            url = f"https://web.whatsapp.com/send?phone={phone}&text={urllib.parse.quote(text)}"
            driver.get(url)

            # esperar composer
            caja = wa_esperar_caja_mensaje(driver, timeout=WHATSAPP_CHAT_READY_SEC)
            try:
                caja.click()
            except Exception:
                pass

            # si por algún motivo NO quedó el texto precargado, lo escribimos
            try:
                current = (caja.text or "").strip()
                if not current:
                    caja.send_keys(text)
            except Exception:
                pass

            # ✅ 1) contar mensajes salientes antes de enviar
            before_count = len(driver.find_elements(By.CSS_SELECTOR, "div.message-out"))

            # ✅ 2) ENTER para enviar
            caja.send_keys(Keys.ENTER)

            # ✅ 3) esperar a que aparezca un NUEVO mensaje-out (confirmación de envío)
            end_send = time.time() + WHATSAPP_CHAT_READY_SEC
            sent_created = False
            while time.time() < end_send:
                now_count = len(driver.find_elements(By.CSS_SELECTOR, "div.message-out"))
                if now_count > before_count:
                    sent_created = True
                    break
                time.sleep(0.25)

            if not sent_created:
                print(f"⚠️ No vi salir el mensaje (message-out) -> {phone}")
                # intenta una vez más (a veces WhatsApp no toma el primer Enter)
                try:
                    caja.send_keys(Keys.ENTER)
                except Exception:
                    pass

                # re-intenta esperar creación
                end_send2 = time.time() + 10
                while time.time() < end_send2:
                    now_count = len(driver.find_elements(By.CSS_SELECTOR, "div.message-out"))
                    if now_count > before_count:
                        sent_created = True
                        break
                    time.sleep(0.25)

            if not sent_created:
                print(f"❌ No se pudo confirmar envío -> {phone}")
                continue

            # ✅ 4) esperar 2 chulos (entregado/leído)
            ok = wa_wait_two_ticks(driver, timeout=WHATSAPP_WAIT_TICKS_SEC)
            if ok:
                print(f"✅ Entregado (2 chulos) -> {phone}")
            else:
                print(f"⚠️ No confirmé 2 chulos -> {phone}")

            enviados.add(phone)
            time.sleep(1.2)

    finally:
        try:
            driver.quit()
        except Exception:
            pass


            # 3) esperar que aparezca el botón de enviar (flecha)
            #    (si no aparece, es porque WhatsApp aún no reconoce el texto, así que damos Enter una vez)
            def _find_send():
                # WhatsApp cambia: usamos varios selectores
                sels = [
                    "span[data-icon='send']",
                    "button span[data-icon='send']",
                    "button[aria-label*='Enviar']",
                    "button[aria-label*='Send']",
                    "button[data-testid='compose-btn-send']",
                    "span[data-testid='send']",
                ]
                for sel in sels:
                    els = driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        try:
                            if el.is_displayed() and el.is_enabled():
                                return el
                        except Exception:
                            continue
                return None

            send_btn = _find_send()
            if not send_btn:
                # fuerza a que WhatsApp “active” el botón (a veces queda como borrador)
                try:
                    caja.send_keys(Keys.ENTER)
                except Exception:
                    pass
                time.sleep(0.6)
                send_btn = WebDriverWait(driver, 20).until(lambda d: _find_send())

            # 4) click enviar
            send_btn.click()

            # 5) esperar DOBLE CHULO en el último mensaje enviado
            ok = wa_wait_two_ticks(driver, timeout=WHATSAPP_WAIT_TICKS_SEC)
            if ok:
                print(f"✅ Entregado (2 chulitos) -> {phone}")
            else:
                print(f"⚠️ No confirmé 2 chulitos -> {phone}")

            enviados.add(phone)
            time.sleep(1.0)

        finally:
            try:
                driver.quit()
            except Exception:
                pass

def export_mensajes_csv(mensajes: List[Dict[str, str]], path_out: str = MENSAJES_OUT_CSV):
    with open(path_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["mensajero", "celular", "mensaje"])
        w.writeheader()
        for m in mensajes:
            w.writerow(m)
    return path_out

def is_pendiente(estado: str = "", checkpoint_code: str = "") -> bool:
    """Pendiente si NO incluye entregado ni devolución en estado o checkpoint_code."""
    txt = f"{estado or ''} {checkpoint_code or ''}".strip().lower()
    if not txt:
        return False
    bloque = [
        "entregado", "delivered",
        "devolucion", "devolución", "devuelto",
        "return", "returned", "retorno"
    ]
    return all(b not in txt for b in bloque)

def days_ago(fecha_str: str):
    try:
        d = datetime.strptime((fecha_str or "").strip(), "%d/%m/%Y").date()
        return (datetime.now().date() - d).days
    except Exception:
        return None

def build_pendientes_por_mensajero(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Arma mensajes por mensajero con formato:
    Formato: Fecha, Guía, Cliente nombre, Dirección

    Pendientes de hace X día(s):
    fecha, tracking, buyer, address
    """
    por = {}
    for r in rows:
        mens = (r.get("mensajero") or "").strip()
        cel  = (r.get("mensajero_celular") or "").strip()
        if not mens or not cel:
            continue
        por.setdefault((mens, cel), []).append(r)

    mensajes = []
    from collections import defaultdict

    for (mensajero, celular), items in por.items():
        buckets = defaultdict(list)
        for it in items:
            if not is_pendiente(it.get("estado", ""), it.get("checkpoint_code", "")):
                continue
            da = days_ago(it.get("fecha", ""))
            if da is None:
                continue
            buckets[da].append(it)

        if not buckets:
            continue

        lineas = [f"Hola, {mensajero}, tienes pendientes los siguientes paquetes de proships:",
                  "Formato: Fecha, Guía, Cliente nombre, Dirección"]

        for da in sorted(buckets.keys(), reverse=True):
            lineas.append(f"\nPendientes de hace {da} día(s):")
            for it in buckets[da]:
                fecha = (it.get("fecha") or "").strip()
                guia  = (it.get("tracking") or "").strip()
                cliente = (it.get("buyer") or "").strip()
                direccion = (it.get("address") or "").strip()
                lineas.append(f"{fecha}, {guia}, {cliente}, {direccion}".strip())

        mensajes.append({
            "mensajero": mensajero,
            "celular": celular,
            "mensaje": "\n".join(lineas).strip()
        })

    return mensajes

# ---------------- Main flow -----------------------
def leer_paquetes() -> List[str]:
    if Path(PAQUETES_FILE).exists():
        with open(PAQUETES_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    raise RuntimeError(f"No se encontró el archivo {PAQUETES_FILE}")


def main():
    trackings = leer_paquetes()
    driver = build_driver(headless=HEADLESS)

    try:
        # Pestaña 1: Proships
        login_proships(driver)
        handle_pro = driver.current_window_handle

        # Pestaña 2: Paquetes
        driver.switch_to.new_window('tab')
        login_paquetes(driver)
        handle_paq = driver.current_window_handle

        results: List[Dict[str, str]] = []

        for i, trk in enumerate(trackings, start=1):
            print(f"\n=========== [{i}/{len(trackings)}] {trk} ===========")

            # PROSHIPS (pestaña 1)
            driver.switch_to.window(handle_pro)
            pro = proships_procesar(driver, trk)

            # PAQUETES (pestaña 2)
            driver.switch_to.window(handle_paq)
            pq = paquetes_buscar_y_extraer(driver, trk)

            # Mensajero celular (PackTrack /mensajeros)
            mensajero_nombre = pq.get('mensajero', '')
            mensajero_celular = ''
            if mensajero_nombre:
                try:
                    mensajero_celular = mensajero_buscar_celular(driver, mensajero_nombre)
                except Exception:
                    mensajero_celular = ''

            # Ensamble con columnas solicitadas (tracking aparece 2 veces) (tracking aparece 2 veces)
            row = {
                "tracking": pro.get("tracking", trk),
                "checkpoint_code": pro.get("checkpoint_code", ""),
                "phone": pro.get("phone", ""),
                "fecha": pq.get("fecha", ""),
                "tracking_2": pro.get("tracking", trk),  # duplicado
                "buyer": pro.get("buyer", ""),
                "address": pro.get("address", ""),
                "mensajero": pq.get("mensajero", ""),
                "mensajero_celular": mensajero_celular,
                "estado": pq.get("estado", ""),  # ← reemplazo
            }

            results.append(row)
            time.sleep(1.0)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # Guardar CSV con cabeceras EXACTAS (tracking repetido)
    columnas = [
        "tracking", "checkpoint_code", "phone", "fecha",
        "tracking", "buyer", "address", "mensajero", "estado"
    ]

    with open(SALIDA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # ✅ Encabezados EXACTOS (con espacios y orden solicitado)
        writer.writerow([
            "tracking",
            "status",
            "fecha",
            "tracking",
            "cliente_direccion",
            "cliente_nombre",
            "cliente_numero",
            "municipio",
            "mensajero",
            "estado",
        ])

        for r in results:
            writer.writerow([
                r.get("tracking", ""),
                r.get("checkpoint_code", ""),        # status
                r.get("fecha", ""),
                r.get("tracking", ""),               # tracking duplicado
                r.get("address", ""),                # cliente_direccion
                r.get("buyer", ""),                  # cliente_nombre
                r.get("phone", ""),                  # cliente_numero
                r.get("municipio", ""),              # municipio (si viene vacío, queda vacío)
                r.get("mensajero", ""),
                r.get("estado", ""),
            ])

    print(f"📁 Listo: {SALIDA_CSV} generado.")

    # ---- Mensajes por mensajero (WhatsApp) ----
    mensajes = build_pendientes_por_mensajero(results)
    out_msg = export_mensajes_csv(mensajes, MENSAJES_OUT_CSV)
    print(f"📨 Mensajes listos en: {out_msg} ({len(mensajes)})")

    if SEND_WHATSAPP:
        send_whatsapp_messages(mensajes)



if __name__ == "__main__":
    main()
