# Reactor correcto para Playwright + Scrapy
from scrapy.utils.reactor import install_reactor
install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")

import traceback
import os
import csv
import re
from pathlib import Path
from typing import Dict, List
from datetime import datetime 
from selenium.common.exceptions import TimeoutException
from selenium import webdriver
from collections import defaultdict
import urllib.parse
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote_plus

import scrapy
from scrapy.crawler import CrawlerProcess

# ================= BigSmart (Playwright) =================
from urllib.parse import urljoin
from pathlib import Path

WHATSAPP_PROFILE_DIR = Path.home() / ".whatsapp_web_profile"
BASE_URL_BIG = "https://admin.bigsmart.mx"
LOGIN_URL_BIG = urljoin(BASE_URL_BIG, "/login")
ORDERS_URL_BIG = urljoin(BASE_URL_BIG, "/app/orders/list")

USER_EMAIL_BIG = os.getenv("BIGSMART_EMAIL", "jara.171201@gmail.com")
USER_PASSWORD_BIG = os.getenv("BIGSMART_PASSWORD", "B1g@AyJ4gj")

# ================== PackTrack (Scrapy) ===================
BASE_URL_PQ = os.getenv("PACKTRACK_BASE_URL", "https://packtrack.site")
LOGIN_URL_PQ = f"{BASE_URL_PQ}/users/sign_in"
PAQUETES_URL = f"{BASE_URL_PQ}/paquetes"
MENSAJEROS_URL = f"{BASE_URL_PQ}/mensajeros"

EMAIL_PQ = os.getenv("PACKTRACK_EMAIL", "oriente@ontime.com")
PASSWORD_PQ = os.getenv("PACKTRACK_PASSWORD", "ontime.1712")

# ================= Archivos & misc =======================
if "__file__" in globals():
    HERE = Path(__file__).resolve().parent
else:
    HERE = Path.cwd()

PAQUETES_FILE = HERE / "paquetes.txt"               # un tracking por línea
SALIDA_CSV = HERE / "resultados.csv"                # detalle por guía
MESSAGES_OUT_CSV = HERE / "mensajes_whatsapp.csv"   # salida final por mensajero

HEADLESS = False
NAV_TIMEOUT_MS = 60000
ROW_WAIT_MS = 20000

# ================= WhatsApp (opcional) ===================
# Si quieres que envíe mensajes automáticamente por WhatsApp Web:
#   - instala selenium:   pip install -U selenium
#   - ten Google Chrome instalado
#   - (opcional) exporta SEND_WHATSAPP=1 para que envíe automáticamente
#   - la primera vez te pedirá escanear el QR (se queda esperando)
SEND_WHATSAPP = os.getenv("SEND_WHATSAPP", "0") == "1"
WHATSAPP_COUNTRY_CODE = os.getenv("WHATSAPP_COUNTRY_CODE", "57")  # Colombia por defecto
WHATSAPP_FIRST_LOAD_SEC = int(os.getenv("WHATSAPP_FIRST_LOAD_SEC", "120"))  # tiempo para escanear QR
WHATSAPP_CHAT_READY_SEC = int(os.getenv("WHATSAPP_CHAT_READY_SEC", "35"))   # timeout esperando caja
WHATSAPP_POST_SEND_SEC  = float(os.getenv("WHATSAPP_POST_SEND_SEC", "1.8")) # pausa luego de enviar

# Perfil de Chrome para recordar la sesión (se guarda junto al script)
WHATSAPP_PROFILE_DIR = (HERE / ".whatsapp_web_profile")
WHATSAPP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Selectores (pueden cambiar si WhatsApp actualiza el DOM)
_WA_COMPOSER_SELECTORS = [
    "footer div[contenteditable='true'][data-tab]",
    "div[contenteditable='true'][data-tab]",
    "div[role='textbox'][contenteditable='true']",
    "div[aria-label*='Escribe un mensaje']",
    "div[aria-label*='Type a message']",
    "[data-testid='conversation-compose-input']",
    "[data-testid='conversation-compose-box-input']",
]
_WA_QR_SELECTORS = ["canvas[aria-label]", "div[data-testid='qrcode']", "div[data-ref]"]

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
        
def wa_click_si_existe(driver, xpath, timeout=5):
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            el.click()
            return True
        except:
            return False


def wa_chat_no_disponible(driver):
        textos_error = [
            "El número de teléfono compartido a través de la dirección URL no es válido",
            "Phone number shared via url is invalid",
            "Este número no está en WhatsApp",
            "This number is not on WhatsApp",
        ]
        body = driver.page_source.lower()
        return any(t.lower() in body for t in textos_error)


def wa_esperar_mensaje_enviado(driver, timeout=40):
        """
        Espera el último mensaje saliente y luego verifica si tiene 1 o 2 chulos.
        """
        ultimo_msg_xpath = '(//div[contains(@class,"message-out")])[last()]'
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, ultimo_msg_xpath))
        )

        # Esperar a que al menos aparezca 1 chulo o 2 chulos en el último mensaje enviado
        check_xpath = (
            '(//div[contains(@class,"message-out")])[last()]'
            '//span[@data-icon="msg-check" or @data-icon="msg-dblcheck"]'
        )

        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, check_xpath))
        )

        # Intentar detectar doble check
        dbl_xpath = (
            '(//div[contains(@class,"message-out")])[last()]'
            '//span[@data-icon="msg-dblcheck"]'
        )

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, dbl_xpath))
            )
            return "delivered"
        except:
            return "sent"

def _wa_normalizar_numero(raw: str) -> str:
    """Devuelve SOLO dígitos con país delante (57XXXXXXXXXX)."""
    n = str(raw or "")
    for ch in [" ", "/", "-", "+", "(", ")", ".", "\t", "\n", "\r"]:
        n = n.replace(ch, "")
    n = n.strip()

    # prefijos raros
    if n.startswith("0057"):
        n = n[4:]
    elif n.startswith("057"):
        n = n[3:]

    # si solo viene el número local (10 dígitos)
    if len(n) == 10 and n.isdigit():
        n = WHATSAPP_COUNTRY_CODE + n

    # si viene con país (57 + 10)
    if not n.isdigit():
        return ""
    if len(n) < 12 and n.startswith(WHATSAPP_COUNTRY_CODE) is False and len(n) == 10:
        n = WHATSAPP_COUNTRY_CODE + n
    return n

def _wa_find_first(driver, selectors):
    from selenium.webdriver.common.by import By
    for sel in selectors:
        els = driver.find_elements(By.CSS_SELECTOR, sel)
        for el in els:
            try:
                if el.is_displayed():
                    return el
            except Exception:
                continue
    return None

def _wa_wait_composer_or_qr(driver, timeout: int):
    import time
    end = time.time() + timeout
    while time.time() < end:
        comp = _wa_find_first(driver, _WA_COMPOSER_SELECTORS)
        if comp:
            return "chat", comp
        qr = _wa_find_first(driver, _WA_QR_SELECTORS)
        if qr:
            return "qr", qr
        time.sleep(0.5)
    return None, None

def _wa_build_driver(headless=False):
    from selenium import webdriver
    opts = webdriver.ChromeOptions()
    opts.add_argument("--lang=es-ES")
    opts.add_argument(f"--user-data-dir={WHATSAPP_PROFILE_DIR}")
    opts.add_argument("--window-size=1200,900")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    if headless:
        opts.add_argument("--headless=new")
    return webdriver.Chrome(options=opts)

def _wa_ensure_logged_in(driver, first_load=WHATSAPP_FIRST_LOAD_SEC) -> bool:
    import time
    driver.get("https://web.whatsapp.com")
    state, _ = _wa_wait_composer_or_qr(driver, timeout=15)
    if state == "chat":
        return True
    # si hay QR, esperamos hasta que aparezca el composer
    end = time.time() + first_load
    while time.time() < end:
        comp = _wa_find_first(driver, _WA_COMPOSER_SELECTORS)
        if comp:
            return True
        time.sleep(1)
    return False

def _wa_wait_chat_composer(driver, timeout=WHATSAPP_CHAT_READY_SEC):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    wait = WebDriverWait(driver, timeout)
    for sel in _WA_COMPOSER_SELECTORS:
        try:
            el = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
            if el and el.is_displayed():
                return el
        except Exception:
            continue
    el = _wa_find_first(driver, _WA_COMPOSER_SELECTORS)
    if el:
        return el
    raise TimeoutError("Composer no visible.")

def _wa_has_any(el, selectors):
    from selenium.webdriver.common.by import By
    for sel in selectors:
        try:
            if el.find_elements(By.CSS_SELECTOR, sel):
                return True
        except Exception:
            pass
    return False

def _wa_wait_last_message_delivered(driver, timeout=35):
    import time
    from selenium.webdriver.common.by import By

    ok_selectors = [
        "span[data-testid='msg-check']",
        "span[data-testid='msg-dblcheck']",
        "span[aria-label*='Sent']",
        "span[aria-label*='Enviado']",
        "span[aria-label*='Delivered']",
        "span[aria-label*='Entregado']",
        "span[aria-label*='Read']",
        "span[aria-label*='Leído']",
    ]
    pending_selectors = [
        "span[data-testid='msg-time']",
        "span[aria-label*='Pending']",
        "span[aria-label*='Pendiente']",
    ]
    failed_selectors = [
        "span[data-testid='msg-error']",
        "span[aria-label*='Not sent']",
        "span[aria-label*='No enviado']",
        "span[aria-label*='Error']",
    ]

    end = time.time() + timeout
    while time.time() < end:
        outs = driver.find_elements(By.CSS_SELECTOR, "div.message-out")
        if not outs:
            time.sleep(0.25)
            continue
        last = outs[-1]
        if _wa_has_any(last, failed_selectors):
            return False
        if _wa_has_any(last, ok_selectors):
            return True
        if _wa_has_any(last, pending_selectors):
            time.sleep(0.35)
            continue
        time.sleep(0.35)
    return False


class CargoSpider(scrapy.Spider):
    name = "cargo_spider"

    custom_settings = {
        # Playwright para las requests que lo pidan
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": HEADLESS},

        # Scrapy
        "COOKIES_ENABLED": True,
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.0,
        "LOG_LEVEL": "INFO",
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/122.0.0.0 Safari/537.36"),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    }

    # ---------- Setup ----------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.codigos = self._leer_codigos()

        self.res = {
            c: {
                "tracking": c,
                "fecha": "",
                "cliente_nombre": "",
                "cliente_direccion": "",
                "municipio": "",
                "mensajero": "",
                "estado": "",
                "celular": "",
            }
            for c in self.codigos
        }

        self.pending = len(self.codigos)
        self._finished = False

        # 🔥 AGRUPACIÓN POR MENSAJERO
        self.paquetes_por_mensajero = {}

        # 🔥 CACHE DE CELULARES (ESTO FALTABA)
        self.celular_cache = {}

    # ========== FASE 1: BIGSMART (Playwright) ==========
    def start_requests(self):
        yield scrapy.Request(
            LOGIN_URL_BIG,
            meta={"playwright": True, "playwright_include_page": True},
            callback=self._bigsmart_login_and_scrape_all
        )

    async def _bigsmart_login_and_scrape_all(self, response):
        """(Opcional) Enriquecimiento BigSmart. Si falla, igual seguimos con PackTrack."""
        page = response.meta["playwright_page"]
        page.set_default_timeout(NAV_TIMEOUT_MS)

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_selector("#email")
        await page.fill("#email", USER_EMAIL_BIG)
        await page.fill("#password", USER_PASSWORD_BIG)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(1000)

        # Si falla BigSmart, seguimos a PackTrack
        try:
            if await page.locator(".alert.alert-danger").is_visible():
                await page.close()
                yield scrapy.Request(LOGIN_URL_PQ, callback=self._paquetes_login_page)
                return
        except Exception:
            pass

        # Ir a órdenes
        try:
            if await page.locator('a[data-flag="orders"]').count():
                await page.click('a[data-flag="orders"]')
                await page.wait_for_load_state("networkidle")
            else:
                await page.goto(ORDERS_URL_BIG)
                await page.wait_for_load_state("networkidle")
        except Exception:
            await page.goto(ORDERS_URL_BIG)
            await page.wait_for_load_state("networkidle")

        await self._wait_search_ready(page)

        for i, code in enumerate(self.codigos, start=1):
            self.logger.info("🔎 [BigSmart %d/%d] %s", i, len(self.codigos), code)
            ok = await self._buscar_y_esperar_fila(page, code)
            if not ok:
                continue

            row = page.locator(f'.rt-tr:has-text("{code}")').first
            tds = row.locator(".rt-td")
            td_count = await tds.count()

            status = (await tds.nth(2).inner_text()).strip() if td_count > 2 else ""
            estacion = (await tds.nth(6).inner_text()).strip() if td_count > 6 else ""

            nombre = numero = cliente_direccion = municipio = ""
            try:
                await tds.nth(4).locator("p.list-item-heading").click()
            except Exception:
                try:
                    await tds.nth(4).click()
                except Exception:
                    pass

            entrega_tab = page.locator('a.nav-link:has-text("Delivery")')
            if await entrega_tab.count():
                try:
                    await entrega_tab.click()
                except Exception:
                    pass

            try:
                await page.wait_for_selector("#customer_first_name", timeout=ROW_WAIT_MS)
                nombre = await page.locator("#customer_first_name").input_value()
                numero = await page.locator("#customer_mobile_number").input_value()
                cliente_direccion = await page.locator("#customer_street").input_value()
                municipio = await page.locator("#customer_municipality").input_value()
            except Exception:
                pass

            try:
                if await page.locator("button.close").count():
                    await page.locator("button.close").click()
                else:
                    await page.keyboard.press("Escape")
            except Exception:
                pass

            r = self.res.get(code, {})
            r.update({
                "status": status,
                "estacion_actual": estacion,
                "cliente_nombre": (nombre or "").strip(),
                "cliente_numero": (numero or "").strip(),
                "cliente_direccion": (cliente_direccion or "").strip(),
                "municipio": (municipio or "").strip(),
            })
            self.res[code] = r
            await page.wait_for_timeout(250)

        await page.close()
        yield scrapy.Request(LOGIN_URL_PQ, callback=self._paquetes_login_page)

    async def _wait_search_ready(self, page):
        if await page.locator("#search").count() == 0:
            await page.wait_for_selector("input[name='keyword']")
        else:
            await page.wait_for_selector("#search")
        await page.wait_for_load_state("networkidle")


    def _send_messages_whatsapp_web(self, mensajes):
        if not mensajes:
            self.logger.info("📭 No hay mensajes para enviar por WhatsApp.")
            return

        WHATSAPP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        opts = Options()
        opts.add_argument("--start-maximized")
        opts.add_argument(f"--user-data-dir={WHATSAPP_PROFILE_DIR.resolve()}")
        opts.add_argument("--profile-directory=Default")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=opts)
        wait = WebDriverWait(driver, 60)

        try:
            driver.get("https://web.whatsapp.com")

            try:
                wait.until(EC.presence_of_element_located((By.ID, "pane-side")))
                self.logger.info("✅ Sesión WhatsApp activa.")
            except:
                self.logger.info("🔑 Escanea el QR (solo esta vez)")
                WebDriverWait(driver, 120).until(
                    EC.presence_of_element_located((By.ID, "pane-side"))
                )
                self.logger.info("✅ QR escaneado, sesión guardada.")

            for m in mensajes:
                celular = str(m.get("celular", "")).strip()
                texto = str(m.get("mensaje", "")).strip()

                if not celular or not texto:
                    continue

                try:
                    texto_encoded = urllib.parse.quote(texto)
                    url = f"https://web.whatsapp.com/send?phone={celular}&text={texto_encoded}"
                    driver.get(url)

                    # A veces aparece botón "Continuar al chat"
                    wa_click_si_existe(driver, '//a[contains(@href, "web.whatsapp.com/send")]')
                    wa_click_si_existe(driver, '//button[contains(.,"Continuar al chat")]')
                    wa_click_si_existe(driver, '//button[contains(.,"Continue to chat")]')
                    wa_click_si_existe(driver, '//a[contains(.,"usar WhatsApp Web")]')
                    wa_click_si_existe(driver, '//a[contains(.,"use WhatsApp Web")]')

                    time.sleep(2)

                    if wa_chat_no_disponible(driver):
                        self.logger.warning(f"⚠️ Número inválido o sin WhatsApp: {celular}")
                        continue

                    caja = wa_esperar_caja_mensaje(driver, timeout=WHATSAPP_CHAT_READY_SEC)

                    # Asegurar foco real
                    caja.click()
                    time.sleep(1)
                    caja.send_keys(Keys.ENTER)

                    estado = wa_esperar_mensaje_enviado(driver, timeout=40)

                    if estado == "delivered":
                        self.logger.info(f"✅ Mensaje entregado (2 chulos) → {celular}")
                    else:
                        self.logger.info(f"✅ Mensaje enviado (1 chulo) → {celular}")

                    time.sleep(2)

                except Exception as e:
                    self.logger.error(f"❌ Error enviando a {celular}: {repr(e)}")
                    self.logger.error(traceback.format_exc())
                    time.sleep(3)

            self.logger.info("🏁 Envío de mensajes finalizado.")

        finally:
            driver.quit()
    async def _buscar_y_esperar_fila(self, page, code) -> bool:
        search = page.locator("#search")
        if not await search.count():
            search = page.locator("input[name='keyword']")
        await search.wait_for()
        await search.fill("")
        await search.type(code, delay=15)

        for sel in [".search-sm button", ".search-sm .simple-icon-magnifier",
                    "button:has(.simple-icon-magnifier)", ".search-sm span"]:
            loc = page.locator(sel)
            if await loc.count():
                try:
                    await loc.first.click()
                    break
                except Exception:
                    continue
        else:
            try:
                await search.press("Enter")
            except Exception:
                pass

        row = page.locator(f'.rt-tr:has-text("{code}")').first
        try:
            await row.wait_for(timeout=ROW_WAIT_MS)
            return True
        except Exception:
            return False

    # ========== FASE 2: PACKTRACK (Scrapy) ==========
    def _paquetes_login_page(self, response: scrapy.http.Response):
        token = response.css('form input[name="authenticity_token"]::attr(value)').get()
        if not token:
            self.logger.error("No encontré authenticity_token en PackTrack.")
            self._finish()
            return

        formdata = {
            "user[email]": EMAIL_PQ,
            "user[password]": PASSWORD_PQ,
            "authenticity_token": token,
            "commit": "Log in",
        }
        yield scrapy.FormRequest(url=LOGIN_URL_PQ, formdata=formdata, callback=self._after_paquetes_login)

    def _after_paquetes_login(self, response: scrapy.http.Response):
        if "/users/sign_in" in response.url:
            self.logger.error("❌ Login PackTrack fallido.")
            self._finish()
            return

        self.logger.info("✅ Login PackTrack OK")

        if not self.codigos:
            self.logger.error("No hay códigos en paquetes.txt.")
            self._finish()
            return

        # Pedir paquetes por cada guía
        for code in self.codigos:
            url = f"{PAQUETES_URL}?codigo={code}"
            yield scrapy.Request(url=url, callback=self._parse_paquetes_row, cb_kwargs={"tracking": code})

    # ---- Parsing helpers (PackTrack) ----
    def _map_headers(self, response):
        headers = response.css("table thead tr th::text").getall()
        mapping = {}
        for idx, h in enumerate(headers):
            key = (h or "").strip().lower()
            if key:
                mapping[key] = idx
        return mapping

    def _pick_col(self, tds, headers_map, wanted_names, default_index=None):
        if headers_map:
            for wanted in wanted_names:
                for k, idx in headers_map.items():
                    if wanted in k:
                        return (tds[idx] if idx < len(tds) else "").strip()
        if default_index is not None and default_index < len(tds):
            return tds[default_index].strip()
        return ""

    def _get_row_by_tracking(self, response, tracking):
        headers_map = self._map_headers(response)
        tracking_norm = (tracking or "").strip()

        for tr in response.css("tbody tr"):
            tds = []
            for td in tr.css("td"):
                txt = " ".join(td.css("::text").getall()).strip()
                tds.append(txt)

            # Normaliza el tracking de la tabla
            if tds:
                td0 = (tds[0] or "").strip()
                if td0 == tracking_norm:
                    return tds, headers_map

        return None, headers_map


    def _done_one(self):
        if self.pending > 0:
            self.pending -= 1
        if self.pending == 0:
            self._finish()

    def _parse_paquetes_row(self, response, tracking):
        """
        PackTrack SOLO complementa:
        - mensajero
        - estado
        - celular (luego por /mensajeros)

        Todos los datos del paquete (fecha, cliente, cliente_direccion, municipio)
        ya vienen desde BigSmart y están en self.res[tracking].
        """

        tds, headers_map = self._get_row_by_tracking(response, tracking)

        if tds:
            mensajero = self._pick_col(
                tds,
                headers_map,
                ["mensajero", "courier", "driver", "repartidor"],
                default_index=4,
            )
            estado = self._pick_col(
                tds,
                headers_map,
                ["estado", "status", "situacion", "observacion"],
                default_index=2,
            )
            celular = ""  # NO existe en paquetes
        else:
            mensajero = ""
            estado = "NO ENCONTRADO"
            celular = ""

        # 🔥 BASE DEL ROW: TODO DESDE BIGSMART
        fecha_pack = self._pick_col(tds, headers_map, ["fecha", "date"], default_index=1) if tds else ""

        row = {
        "tracking": str(tracking).strip(),
        "fecha": (fecha_pack or "").strip(),  # ✅ aquí
        "cliente_nombre": self.res[tracking].get("cliente_nombre", ""),
        "cliente_direccion": self.res[tracking].get("cliente_direccion", ""),
        "municipio": self.res[tracking].get("municipio", ""),
        "mensajero": (mensajero or "").strip(),
        "estado": (estado or "SIN ESTADO").strip(),
        "celular": "",
        }


        # Actualizar registro principal
        self.res[tracking].update(row)

        m = row["mensajero"]
        if not m:
            self._done_one()
            return

        # Agrupar por mensajero
        bucket = self.paquetes_por_mensajero.setdefault(
            m, {"celular": "", "rows": []}
        )
        bucket["rows"].append(row)

        # Si ya tenemos el celular cacheado, no volver a consultar
        if m in self.celular_cache and self.celular_cache[m]:
            phone = self.celular_cache[m]
            bucket["celular"] = phone
            row["celular"] = phone
            self.res[tracking]["celular"] = phone
            self._done_one()
            return
        self.logger.info(f"DBG paquete -> {tracking} | mensajero='{mensajero}' | fecha='{row['fecha']}' | celular='{row['celular']}'")


        # Buscar celular en /mensajeros?query=<NOMBRE>
        cached = self.celular_cache.get(mensajero, "")
        if cached:
            bucket["celular"] = cached
            self.res[tracking]["celular"] = cached
            self._done_one()
            return

        # si NO hay cached, NO llames _done_one aquí:
        url = f"{MENSAJEROS_URL}?query={quote_plus(mensajero)}"
        yield scrapy.Request(
            url=url,
            callback=self._parse_mensajero_phone,
            cb_kwargs={"tracking": tracking, "mensajero": mensajero},
            dont_filter=True,
        )

    def _parse_mensajero_phone(self, response, tracking, mensajero):
        celular = ""

        headers = [" ".join(h.split()).strip().lower()
                for h in response.css("table thead tr th::text").getall()]

        idx_cel = None
        for i, h in enumerate(headers):
            if "celular" in h:
                idx_cel = i
                break

        # primera fila
        first_tr = response.css("table tbody tr").get()
        if first_tr and idx_cel is not None:
            tds_text = []
            for td in response.css("table tbody tr")[0].css("td"):
                tds_text.append(" ".join(td.css("::text").getall()).strip())

            if idx_cel < len(tds_text):
                celular = (tds_text[idx_cel] or "").strip()

        celular = self._normalize_phone(celular)

        if celular:
            self.celular_cache[mensajero] = celular
            bucket = self.paquetes_por_mensajero.get(mensajero)
            if bucket is not None:
                bucket["celular"] = celular
            self.res[tracking]["celular"] = celular

        self._done_one()

    # ---------- IO ----------
    def _leer_codigos(self) -> List[str]:
        if PAQUETES_FILE.exists():
            return [l.strip() for l in PAQUETES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        return []

    def _export_resultados_csv(self):
        """Exporta resultados por guía con el orden solicitado."""
        SALIDA_CSV.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "tracking",
            "status",
            "fecha",
            "tracking_2",  # ← segundo tracking (clave interna)
            "cliente_direccion",
            "cliente_nombre",
            "cliente_numero",
            "municipio",
            "mensajero",
            "estado",
        ]

        with open(SALIDA_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # encabezado real (tracking repetido)
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

            for code in self.codigos:
                r = self.res.get(code, {})
                writer.writerow([
                    r.get("tracking", ""),
                    r.get("status", ""),
                    r.get("fecha", ""),
                    r.get("tracking_2", ""),  # tracking repetido
                    r.get("cliente_direccion", ""),
                    r.get("cliente_nombre", ""),
                    r.get("cliente_numero", ""),
                    r.get("municipio", ""),
                    r.get("mensajero", ""),
                    r.get("estado", ""),
                ])

        return str(SALIDA_CSV)





        # ---------- fechas / filtros ----------
    def _days_ago(self, fecha_str: str):
            try:
                fecha_pkg = datetime.strptime((fecha_str or "").strip(), "%d/%m/%Y").date()
                return (datetime.now().date() - fecha_pkg).days
            except Exception:
                return None

    def _normalize_phone(self, raw_phone: str) -> str:
            digits = re.sub(r"\D+", "", raw_phone or "")
            if not digits:
                return ""
            if digits.startswith(WHATSAPP_COUNTRY_CODE):
                return digits
            return WHATSAPP_COUNTRY_CODE + digits

    def _is_pendiente(self, estado: str, status: str = "") -> bool:
            e = (estado or "").strip().lower()
            s = (status or "").strip().lower()
            if not (e or s):
                return False
            # no enviar si incluye entregado o devolucion/devolución
            bloqueadores = [
                "entregado", "delivered", "finalizado", "completado",
                "devolucion", "devolución", "devuelto", "return", "returned", "retorno"
            ]
            return all(b not in e and b not in s for b in bloqueadores)

        # ---------- mensajes ----------
    def _build_whatsapp_messages(self):
            mensajes = []

            for mensajero, bucket in self.paquetes_por_mensajero.items():
                celular = str(bucket.get("celular") or "").strip()
                rows = bucket.get("rows") or []

                # si no tenemos celular o no hay filas, no podemos enviar
                if not celular or not rows:
                    continue

                buckets = defaultdict(list)  # dias -> [rows]

                for r in rows:
                    # filtra entregado / devolución
                    if not self._is_pendiente(r.get("estado", ""), r.get("status", "")):
                        continue

                    dias = self._days_ago(r.get("fecha", ""))
                    if dias is None:
                        continue

                    buckets[dias].append(r)

                if not buckets:
                    continue

                lineas = [
                    f"Hola, {mensajero}, tienes paquetes pendientes:",
                    "",
                    "Formato: Fecha, Guía, Cliente nombre, Dirección, Municipio",
                ]

                for dias in sorted(buckets.keys(), reverse=True):
                    lineas.append(f"\nPendientes de hace {dias} día(s):")

                    for p in buckets[dias]:
                        fecha = (p.get("fecha") or "").strip()
                        guia = (p.get("tracking") or "").strip()
                        cliente = (p.get("cliente_nombre") or "").strip()
                        direccion = (p.get("cliente_direccion") or "").strip()
                        municipio = (p.get("municipio") or "").strip()

                        lineas.append(f"{fecha}, {guia}, {cliente}, {direccion}, {municipio}")

                mensajes.append({
                    "mensajero": mensajero,
                    "celular": celular,
                    "mensaje": "\n".join(lineas).strip(),
                })

            return mensajes

    def _export_messages_csv(self, mensajes: List[Dict[str, str]]) -> str:
            MESSAGES_OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
            with open(MESSAGES_OUT_CSV, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["mensajero", "celular", "mensaje"])
                w.writeheader()
                for m in mensajes:
                    w.writerow(m)
            return str(MESSAGES_OUT_CSV)

    def _finish(self):
            if self._finished:
                return
            self._finished = True

            # ✅ 1. Exportar resultados por paquete (como siempre)
            path_resultados = self._export_resultados_csv()
            self.logger.info(f"📝 Resultados actualizados en: {path_resultados}")

            # ✅ 2. Construir y exportar mensajes
            mensajes = self._build_whatsapp_messages() or []
            self._export_messages_csv(mensajes)
            self.logger.info(f"📨 Mensajes listos en: {MESSAGES_OUT_CSV} ({len(mensajes)})")

            # ✅ 3. Enviar WhatsApp (opcional)
            if SEND_WHATSAPP and mensajes:
                self._send_messages_whatsapp_web(mensajes)


    def closed(self, reason):
                # seguridad: por si algo quedó pendiente
                self._finish()


if __name__ == "__main__":
    process = CrawlerProcess()
    process.crawl(CargoSpider)
    process.start()
