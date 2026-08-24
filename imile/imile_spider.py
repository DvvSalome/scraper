import os
import time
import csv
import urllib.parse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
import chromedriver_autoinstaller

BASE_URL = "https://ds.imile.com"
LOGIN_URL = "https://ds-login.imile.com/"
IMILE_WAYBILL_URL = BASE_URL + "/#/DSOperation/WaybillManagement/dsTrackQuery?waybillNo={}"
IMILE_EMAIL = os.getenv("IMILE_EMAIL", "2106639001")
IMILE_PASSWORD = os.getenv("IMILE_PASSWORD", "Mile.2026")
SEARCH_INPUT = (By.CSS_SELECTOR, ".search-header input")
RESULTS_CSV = Path("resultados.csv")
MENSAJES_OUT_CSV = Path("mensajes_whatsapp.csv")

BASE_URL_PQ = "https://packtrack.site"
LOGIN_URL_PQ = f"{BASE_URL_PQ}/users/sign_in"
MENSAJEROS_URL = f"{BASE_URL_PQ}/mensajeros"
EMAIL_PQ = os.getenv("PACKTRACK_EMAIL", "oriente@ontime.com")
PASSWORD_PQ = os.getenv("PACKTRACK_PASSWORD", "ontime.1712")

SEND_WHATSAPP = os.getenv("SEND_WHATSAPP", "0") == "1"
WHATSAPP_COUNTRY_CODE = os.getenv("WHATSAPP_COUNTRY_CODE", "57")
WHATSAPP_FIRST_LOAD_SEC = int(os.getenv("WHATSAPP_FIRST_LOAD_SEC", "120"))
WHATSAPP_CHAT_READY_SEC = int(os.getenv("WHATSAPP_CHAT_READY_SEC", "60"))
WHATSAPP_WAIT_TICKS_SEC = int(os.getenv("WHATSAPP_WAIT_TICKS_SEC", "45"))
WHATSAPP_PROFILE_DIR = Path(os.getenv("WHATSAPP_PROFILE_DIR", str(Path.cwd() / ".whatsapp_web_profile")))
WHATSAPP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


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


def robust_get(driver, url: str, wait_selector=None, timeout: int = 45, label: str = ""):
    print(f"➡️  Navegando a {label or url}")
    try:
        driver.get(url)
    except Exception:
        try:
            ready = driver.execute_script("return document.readyState")
        except Exception:
            ready = "unknown"
        if ready not in ("interactive", "complete"):
            time.sleep(2)
            driver.get(url)
    if wait_selector:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located(wait_selector))


def navigate_to_waybill(driver, waybill: str):
    url = IMILE_WAYBILL_URL.format(waybill)
    # Force a true page reload instead of a hash-change (SPA client-side nav).
    # Without this, React re-uses the old render tree and the bottom detail
    # panel never renders when the tab was in background during PackTrack login.
    driver.get("about:blank")
    time.sleep(0.3)
    driver.get(url)
    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located(SEARCH_INPUT))
    _wait_for_no_loading(driver)
    # Wait for the full detail panel (bottom section) to render.
    # React lazy-renders it; a longer wait is required on multi-tab sessions.
    time.sleep(3)


def search_waybill(driver, waybill: str):
    wait = WebDriverWait(driver, 30)
    _click_if_visible(driver, ".close-icon")
    search_input = wait.until(EC.element_to_be_clickable(SEARCH_INPUT))
    try:
        search_input.click()
    except ElementClickInterceptedException:
        _click_if_visible(driver, ".close-icon")
        time.sleep(0.5)
        try:
            search_input.click()
        except Exception:
            driver.execute_script("arguments[0].click();", search_input)

    search_input.send_keys(Keys.CONTROL, "a")
    search_input.send_keys(Keys.BACKSPACE)
    time.sleep(0.2)
    search_input.send_keys(waybill)
    search_input.send_keys(Keys.ENTER)
    _wait_for_no_loading(driver)
    time.sleep(1)


def query_waybill(driver, waybill: str, first: bool = False):
    if first:
        navigate_to_waybill(driver, waybill)
    else:
        search_waybill(driver, waybill)
    wait = WebDriverWait(driver, 30)
    wait.until(lambda d: d.current_url.startswith(BASE_URL) or "waybillNo" in d.current_url)
    # A veces aparece un overlay justo al cargar la página; cerrarlo si existe
    _click_if_visible(driver, ".close-icon")
    time.sleep(0.5)
    driver.save_screenshot(f"/tmp/imile_spider_{waybill}.png")
    print(f"➡️  iMile cargó la orden {waybill}")
    return extract_waybill_info(driver, waybill)


def _safe_text(driver, selector, by=By.CSS_SELECTOR, timeout=8):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, selector))
        ).text.strip()
    except Exception:
        return ""


def _click_tab(driver, selector):
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
        for button in buttons:
            if button.is_displayed() and button.is_enabled():
                button.click()
                time.sleep(0.8)
                return True
    except Exception:
        pass
    return False


def _click_tab_by_text(driver, tab_text: str) -> bool:
    """Click a tab button matching tab_text (case-insensitive)."""
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR,
            ".tab-content button, .tabs button, [class*='tab'] button")
        for btn in buttons:
            if tab_text.lower() in btn.text.lower():
                btn.click()
                time.sleep(1.2)
                _wait_for_no_loading(driver, timeout=8)
                return True
    except Exception:
        pass
    return False


def _find_detail_by_label(driver, label_text: str) -> str:
    """Find a .detail-item by label and return value.
    textContent concatenates label+value without separator, so we extract
    the value by stripping the label prefix from the full string.
    """
    try:
        items = driver.find_elements(By.CSS_SELECTOR, ".detail-item")
        for item in items:
            tc = _js_text(driver, item)
            if not tc:
                continue
            lower_tc = tc.lower()
            lower_label = label_text.lower()
            if lower_tc.startswith(lower_label):
                value = tc[len(label_text):].strip()
                return "" if value in ("-", "—", "N/A", "0057") else value
    except Exception:
        pass
    return ""


def _click_if_visible(driver, selector):
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for el in elements:
            if el.is_displayed() and el.is_enabled():
                el.click()
                time.sleep(0.5)
                return True
    except Exception:
        pass
    return False


def _wait_for_no_loading(driver, timeout=30):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: not any(
                el.is_displayed()
                for el in d.find_elements(By.CSS_SELECTOR, ".loading, .ImileSpin-loadingMask")
            )
        )
    except Exception:
        pass


def is_pendiente(estado: str = "", detalle: str = "") -> bool:
    """Determina si una guía está pendiente (no entregada ni devuelta)."""
    txt = f"{estado or ''} {detalle or ''}".strip().lower()
    if not txt:
        return True
    bloque = [
        "entregado", "delivered",
        "devolucion", "devolución", "devuelto",
        "return", "returned", "retorno"
    ]
    return all(b not in txt for b in bloque)


def login_paquetes(driver):
    robust_get(
        driver,
        LOGIN_URL_PQ,
        wait_selector=(By.CSS_SELECTOR, "form input[name='authenticity_token'], input[name='user[email]'], input[name='user[password]']"),
        label="Login PackTrack"
    )
    w = WebDriverWait(driver, 30)
    email_input = w.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='user[email]']")))
    password_input = w.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='user[password]']")))
    email_input.clear(); email_input.send_keys(EMAIL_PQ)
    password_input.clear(); password_input.send_keys(PASSWORD_PQ)
    password_input.send_keys(Keys.ENTER)
    w.until(lambda d: "/users/sign_in" not in d.current_url)
    print("✅ Login PackTrack OK")


def _paquetes_map_headers(driver):
    headers = driver.find_elements(By.CSS_SELECTOR, "table thead tr th")
    mapping = {}
    for idx, h in enumerate(headers):
        key = (h.text or "").strip().lower()
        if key:
            mapping[key] = idx
    return mapping


def _paquetes_pick_col(values, headers_map, wanted_names, default_index=None):
    if headers_map:
        for wanted in wanted_names:
            for header, idx in headers_map.items():
                if wanted in header and idx < len(values):
                    return (values[idx] or "").strip()
    if default_index is not None and default_index < len(values):
        return (values[default_index] or "").strip()
    return ""


def paquetes_buscar_y_extraer(driver, tracking: str):
    url = f"{BASE_URL_PQ}/paquetes?codigo={urllib.parse.quote(tracking)}"
    try:
        robust_get(driver, url, wait_selector=(By.CSS_SELECTOR, "table"), timeout=25, label=f"Paquetes {tracking}")
    except Exception as exc:
        print(f"⚠️ Error consultando PackTrack /paquetes para {tracking}: {exc}")
        return {"fecha": "", "mensajero": "", "estado": ""}

    headers_map = _paquetes_map_headers(driver)
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    if not rows:
        return {"fecha": "", "mensajero": "", "estado": ""}

    fila = None
    for row in rows:
        values = [(td.text or "").strip() for td in row.find_elements(By.CSS_SELECTOR, "td")]
        if values and values[0] == tracking:
            fila = values
            break

    if not fila:
        return {"fecha": "", "mensajero": "", "estado": ""}

    fecha = _paquetes_pick_col(fila, headers_map, ["fecha", "date"], default_index=1)
    mensajero = _paquetes_pick_col(fila, headers_map, ["mensajero", "courier", "driver", "repartidor"], default_index=4)
    estado = _paquetes_pick_col(fila, headers_map, ["estado", "status", "situacion", "observacion"], default_index=2)

    return {
        "fecha": fecha.strip(),
        "mensajero": mensajero.strip(),
        "estado": estado.strip(),
    }


def mensajero_buscar_celular(driver, mensajero_nombre: str) -> str:
    nombre = (mensajero_nombre or "").strip()
    if not nombre:
        return ""

    url = f"{MENSAJEROS_URL}?query={urllib.parse.quote(nombre)}"
    try:
        robust_get(driver, url, wait_selector=(By.CSS_SELECTOR, "table"), timeout=25, label=f"Mensajeros {nombre}")
    except TimeoutException:
        print(f"⚠️ No encontré el mensajero en PackTrack: {nombre}")
        return ""
    except Exception as exc:
        print(f"⚠️ Error buscando mensajero {nombre}: {exc}")
        return ""

    headers_map = _paquetes_map_headers(driver)
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    if not rows:
        return ""

    first_row = rows[0].find_elements(By.CSS_SELECTOR, "td")
    values = [(td.text or "").strip() for td in first_row]
    celular = _paquetes_pick_col(values, headers_map, ["celular", "cell", "phone"], default_index=None)
    if not celular:
        return ""

    digits = "".join(ch for ch in celular if ch.isdigit())
    if len(digits) == 10:
        digits = WHATSAPP_COUNTRY_CODE + digits
    if not digits.startswith(WHATSAPP_COUNTRY_CODE) and len(digits) == 10:
        digits = WHATSAPP_COUNTRY_CODE + digits
    return digits


def _js_text(driver, element) -> str:
    """Get element text via JS textContent — works even off-viewport."""
    try:
        return (driver.execute_script("return arguments[0].textContent", element) or "").strip()
    except Exception:
        return ""


def _scroll_into_view(driver, element):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", element)
        time.sleep(0.3)
    except Exception:
        pass


def _dismiss_overlay(driver):
    """Dismiss any overlay/modal blocking interactions."""
    for sel in [".close-icon", "div.overlay .close", "[class*='overlay'] button", "div.overlay"]:
        _click_if_visible(driver, sel)
    # Also dismiss via Escape key
    try:
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    time.sleep(0.5)


def extract_waybill_info(driver, waybill: str):
    status_text = _safe_text(driver, ".status.active")

    # Dismiss any overlay that may block tab clicks
    _dismiss_overlay(driver)

    # Find Customer Info tab among all MUI tab buttons (by position or textContent).
    # In multi-tab Chrome sessions, .text may be empty but textContent via JS works.
    # Customer Info is consistently at index 5: [Waybill tracks, Undefined, Container,
    # Basic Info, Shipping Info, Customer Info, ...]
    customer_clicked = False
    try:
        mui_tabs = driver.find_elements(
            By.CSS_SELECTOR, "button.MuiTab-root, button[class*='MuiTab-root']"
        )
        print(f"  [DBG extract] mui_tabs found: {len(mui_tabs)}")
        for i, b in enumerate(mui_tabs[:7]):
            tc = _js_text(driver, b)
            print(f"    [{i}] textContent={repr(tc[:30])}")
        target = None
        # Try by textContent first
        for btn in mui_tabs:
            tc = _js_text(driver, btn).upper()
            if "CUSTOMER" in tc and "INFO" in tc:
                target = btn
                break
        # Fall back to fixed index 5 if text-based lookup fails
        if target is None and len(mui_tabs) > 5:
            target = mui_tabs[5]
            print(f"  [DBG extract] using index-5 fallback")

        if target:
            _scroll_into_view(driver, target)
            # Use JS click to bypass any overlay that intercepts native clicks
            driver.execute_script("arguments[0].click()", target)
            time.sleep(1.5)
            _wait_for_no_loading(driver, timeout=8)
            customer_clicked = True
            print(f"  [DBG extract] tab clicked, customer_clicked=True")
    except Exception as e:
        print(f"  [DBG extract] EXCEPTION: {e}")
        pass

    if customer_clicked:
        # Debug: show what detail-items are present after tab click
        items = driver.find_elements(By.CSS_SELECTOR, ".detail-item")
        print(f"  [DBG] detail-items after click: {len(items)}")
        for i, it in enumerate(items[:6]):
            tc = _js_text(driver, it)
            print(f"    [{i}] {repr(tc[:60])}")
        cliente_nombre    = _find_detail_by_label(driver, "Customer Name")
        cliente_numero    = _find_detail_by_label(driver, "Customer phone")
        cliente_direccion = _find_detail_by_label(driver, "Address")
        print(f"  [DBG] nombre={repr(cliente_nombre)} numero={repr(cliente_numero)}")
    else:
        cliente_nombre = cliente_numero = cliente_direccion = ""

    return {
        "tracking": waybill,
        "status": status_text,
        "fecha": "",
        "tracking_2": waybill,
        "cliente_direccion": cliente_direccion,
        "cliente_nombre": cliente_nombre,
        "cliente_numero": cliente_numero,
        "municipio": "",
        "mensajero": "",
        "estado": "",
    }


def _wa_normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits.lstrip("0")
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        digits = WHATSAPP_COUNTRY_CODE + digits
    if len(digits) == 11 and digits.startswith(WHATSAPP_COUNTRY_CODE[1:]):
        digits = WHATSAPP_COUNTRY_CODE + digits[1:]
    if not digits.startswith(WHATSAPP_COUNTRY_CODE) and len(digits) == 10:
        digits = WHATSAPP_COUNTRY_CODE + digits
    return digits


def build_whatsapp_driver(headless: bool = False):
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
        for sel in failed_selectors:
            try:
                if last.find_elements(By.CSS_SELECTOR, sel):
                    return False
            except Exception:
                pass

        for sel in ok_selectors:
            try:
                if last.find_elements(By.CSS_SELECTOR, sel):
                    return True
            except Exception:
                pass

        time.sleep(0.35)

    return False


def _wa_click_continue_button(driver):
    """Click 'Continue to chat' / 'Continuar al chat' if present."""
    for xpath in [
        "//button[contains(., 'Continue to chat')]",
        "//button[contains(., 'Continuar al chat')]",
        "//a[contains(., 'Continue to chat')]",
        "//span[contains(., 'Continue to chat')]/..",
    ]:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                if el.is_displayed():
                    el.click()
                    time.sleep(1.5)
                    return True
        except Exception:
            pass
    return False


class WhatsAppNumeroInvalido(Exception):
    """El número no está en WhatsApp o la URL /send es inválida."""
    pass


def _wa_numero_invalido(driver) -> bool:
    """Detecta el popup de 'número inválido / no está en WhatsApp'."""
    frases = [
        "no es válido", "not valid", "isn't on whatsapp", "is not on whatsapp",
        "no está en whatsapp", "phone number shared via url is invalid",
        "url que compartiste no es válid", "número de teléfono compartido",
    ]
    try:
        for xp in ("//div[@role='dialog']", "//*[@data-animate-modal-body='true']"):
            for el in driver.find_elements(By.XPATH, xp):
                try:
                    if el.is_displayed():
                        t = (el.text or "").lower()
                        if any(f in t for f in frases):
                            return True
                except Exception:
                    pass
    except Exception:
        pass
    return False


def wa_esperar_caja_mensaje(driver, timeout=45):
    selectores = [
        # WhatsApp Web 2024/2025 selectors
        "div[aria-placeholder='Type a message']",
        "div[aria-placeholder='Escribe un mensaje']",
        "div[data-testid='conversation-compose-box-input']",
        "footer div[contenteditable='true']",
        "div[contenteditable='true'][data-tab]",
        "div[title='Escribe un mensaje']",
        "div[aria-label='Escribe un mensaje']",
        "div[aria-label='Type a message']",
        # generic fallback
        "div[contenteditable='true']",
    ]

    end = time.time() + timeout
    ultimo_error = None
    continue_clicked = False

    while time.time() < end:
        # Handle "Continue to chat" popup
        if not continue_clicked:
            if _wa_click_continue_button(driver):
                continue_clicked = True

        # Si el número no está en WhatsApp, cortar rápido (no esperar todo el timeout)
        if _wa_numero_invalido(driver):
            raise WhatsAppNumeroInvalido("el número no está en WhatsApp / URL inválida")

        for sel in selectores:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elementos:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except Exception as e:
                ultimo_error = e
        time.sleep(0.4)

    raise Exception(f"No apareció la caja de mensaje. Último error: {ultimo_error}")


def _wa_contar_mensajes(driver) -> int:
    """Cuenta burbujas de mensaje (selector robusto a versiones de WhatsApp Web)."""
    try:
        return len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='msg-container'], div.message-out"))
    except Exception:
        return 0


def _wa_confirmar_envio(driver, caja, antes: int, timeout: float) -> bool:
    """Enviado si aparece una burbuja nueva O si la caja quedó vacía tras el ENTER."""
    end = time.time() + timeout
    while time.time() < end:
        if _wa_contar_mensajes(driver) > antes:
            return True
        try:
            if not (caja.text or "").strip():
                return True          # la caja tenía texto y se vació => se envió
        except Exception:
            return True              # la caja se re-renderizó => se envió
        time.sleep(0.25)
    return False


def _wa_enviar_uno(driver, phone: str, text: str) -> bool:
    """Abre el chat y envía un mensaje. Lanza WhatsAppNumeroInvalido si el número no está en WhatsApp."""
    url = f"https://web.whatsapp.com/send?phone={phone}&text={urllib.parse.quote(text)}"
    driver.get(url)

    caja = wa_esperar_caja_mensaje(driver, timeout=WHATSAPP_CHAT_READY_SEC)
    try:
        caja.click()
    except Exception:
        pass
    try:
        if not (caja.text or "").strip():
            caja.send_keys(text)
    except Exception:
        pass

    antes = _wa_contar_mensajes(driver)
    caja.send_keys(Keys.ENTER)
    return _wa_confirmar_envio(driver, caja, antes, WHATSAPP_CHAT_READY_SEC)


def send_whatsapp_messages(mensajes):
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
        fallidos = []

        for m in mensajes:
            phone = _wa_normalize_phone((m.get("celular") or "").strip())
            text = (m.get("mensaje") or "").strip()
            if not phone or not text or phone in enviados:
                continue

            # Aislar cada envío: un fallo NO debe abortar el resto del lote.
            try:
                ok = _wa_enviar_uno(driver, phone, text)
            except WhatsAppNumeroInvalido:
                print(f"⛔ No está en WhatsApp, se omite -> {phone}")
                fallidos.append(phone)
                continue
            except Exception as e:
                print(f"⚠️ Error enviando a {phone}, se omite: {e}")
                fallidos.append(phone)
                continue

            if ok:
                enviados.add(phone)
                print(f"✅ Enviado -> {phone}")
            else:
                fallidos.append(phone)
                print(f"❌ No se pudo confirmar envío -> {phone}")
            time.sleep(1.2)

        print(f"📊 WhatsApp: {len(enviados)} enviados, {len(fallidos)} fallidos de {len(mensajes)}.")
        if fallidos:
            print("   Fallidos:", ", ".join(fallidos))

    finally:
        try:
            driver.quit()
        except Exception:
            pass


def export_mensajes_csv(mensajes, path_out: Path = MENSAJES_OUT_CSV):
    with path_out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["mensajero", "celular", "mensaje"])
        w.writeheader()
        for m in mensajes:
            w.writerow(m)
    return path_out


def _days_ago(fecha_str: str):
    try:
        d = datetime.strptime((fecha_str or "").strip(), "%d/%m/%Y").date()
        return (datetime.now().date() - d).days
    except Exception:
        return None


def build_whatsapp_messages(rows):
    por = {}
    for r in rows:
        if not is_pendiente(r.get("status", ""), r.get("estado", "")):
            continue
        telefono = (r.get("mensajero_celular") or "").strip()
        mensajero = (r.get("mensajero") or "").strip()
        if not telefono or not mensajero:
            if mensajero and not telefono:
                print(f"⚠️ Mensajero sin celular para {mensajero} / {r.get('tracking', '')}")
            continue
        key = (telefono, mensajero)
        por.setdefault(key, []).append(r)

    mensajes = []
    for (telefono, mensajero), items in por.items():
        buckets = defaultdict(list)
        for it in items:
            da = _days_ago(it.get("fecha", ""))
            if da is None:
                continue
            buckets[da].append(it)

        if not buckets:
            continue

        lineas = [
            f"Hola, {mensajero}, tienes los siguientes paquetes pendientes en iMile:",
            "Formato: Fecha, Guía, Cliente nombre, Dirección",
        ]
        for da in sorted(buckets.keys(), reverse=True):
            lineas.append(f"\nPendientes de hace {da} día(s):")
            for it in buckets[da]:
                fecha = (it.get("fecha") or "").strip()
                guia = (it.get("tracking") or "").strip()
                cliente = (it.get("cliente_nombre") or "").strip()
                direccion = (it.get("cliente_direccion") or "").strip()
                lineas.append(f"{fecha}, {guia}, {cliente}, {direccion}".strip())

        mensajes.append({
            "mensajero": mensajero,
            "celular": telefono,
            "mensaje": "\n".join(lineas).strip(),
        })
    return mensajes


def main():
    driver = build_driver(headless=False)
    try:
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 30)

        email_input = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='userCode']"))
        )
        password_input = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
        )

        email_input.clear()
        email_input.send_keys(IMILE_EMAIL)
        password_input.clear()
        password_input.send_keys(IMILE_PASSWORD)

        submit_button = driver.find_element(By.CSS_SELECTOR, "button.ImileButton-root")
        submit_button.click()

        wait.until(lambda d: d.current_url.startswith(BASE_URL))
        _wait_for_no_loading(driver)
        _click_if_visible(driver, ".close-icon")
        print("✅ Login iMile realizado")

        codes = []
        paquetes_file = Path("paquetes.txt")
        if paquetes_file.exists():
            codes = [line.strip() for line in paquetes_file.read_text(encoding="utf-8").splitlines() if line.strip()]

        results = []
        handle_imile = driver.current_window_handle
        handle_packtrack = None
        if codes:
            driver.switch_to.new_window('tab')
            login_paquetes(driver)
            handle_packtrack = driver.current_window_handle
            driver.switch_to.window(handle_imile)

        for index, code in enumerate(codes):
            data = query_waybill(driver, code, first=(index == 0))
            if handle_packtrack:
                driver.switch_to.window(handle_packtrack)
                packtrack_info = paquetes_buscar_y_extraer(driver, code)
                mensajero_celular_raw = ""
                if packtrack_info.get("mensajero"):
                    mensajero_celular_raw = mensajero_buscar_celular(driver, packtrack_info.get("mensajero"))
                driver.switch_to.window(handle_imile)
            else:
                packtrack_info = {"fecha": "", "mensajero": "", "estado": ""}
                mensajero_celular_raw = ""

            data["fecha"] = packtrack_info.get("fecha", "")
            data["mensajero"] = packtrack_info.get("mensajero", "")
            data["estado"] = data.get("estado") or packtrack_info.get("estado", "")
            data["mensajero_celular"] = mensajero_celular_raw
            results.append(data)
            time.sleep(1)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    RESULTS_CSV.write_text(
        "tracking,status,fecha,tracking_2,cliente_direccion,cliente_nombre,cliente_numero,municipio,mensajero,estado\n",
        encoding="utf-8",
    )
    with RESULTS_CSV.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for row in results:
            writer.writerow([
                # Forzar texto en Excel para tracking y teléfono usando fórmula ="..."
                f"=\"{row.get('tracking', '')}\"",
                row.get("status", ""),
                row.get("fecha", ""),
                f"=\"{row.get('tracking_2', '')}\"",
                row.get("cliente_direccion", ""),
                row.get("cliente_nombre", ""),
                f"=\"{row.get('cliente_numero', '')}\"",
                row.get("municipio", ""),
                row.get("mensajero", ""),
                row.get("estado", ""),
            ])

    mensajes = build_whatsapp_messages(results)
    export_mensajes_csv(mensajes, MENSAJES_OUT_CSV)
    print(f"📨 Mensajes WhatsApp listos en: {MENSAJES_OUT_CSV} ({len(mensajes)})")

    if SEND_WHATSAPP:
        send_whatsapp_messages(mensajes)


if __name__ == "__main__":
    main()
