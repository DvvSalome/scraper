# Scraper Timex

Proyecto de scraping y automatización para procesamiento de guías de envío, generación de reportes y envío de mensajes por WhatsApp/Telegram.

## Estructura general

- `server.py` - servidor HTTP principal que sirve el frontend estático y expone APIs para ejecutar los scripts.
- `frontend/` - UI del usuario con las páginas:
  - `/` Pendientes por proveedor
  - `/correo/` Generar Excel de novedades SAC
  - `/pasarex_asignar/` Asignar guías en Pasarex / Proships
  - `/contabilidad/` Generar contabilidad por mensajero
- `proships/`, `x-cargo/`, `pasarex/`, `imile/` - scrapers principales para cada proveedor.
- `contabilidad/` - scrapers para contabilidad, con envío opcional a Telegram.
- `proships_correo/` - generación de Excel de novedades SAC.
- `pasarex_asignar/`, `proships/asignar_proships/` e `imile/asignar_imile.py` - scripts de asignación de guías.

## Qué hace

El servidor ejecuta los scrapers desde la UI y devuelve resultados en CSV/Excel. Los scrapers usan:

- Selenium / Chrome para automatizar web
- Scrapy y Scrapy-Playwright para scraping de sitios que requieren JS
- openpyxl para generar/leer Excel
- pandas para lectura de archivos Excel en algunos scripts
- chromedriver-autoinstaller para gestión automática de ChromeDriver

## Requisitos

- Linux / WSL con Python 3.12+ (el proyecto sugiere 3.12.3)
- `python3` disponible
- `pip` para instalar dependencias
- Navegador Chromium / Chrome para Selenium
- Librerías de soporte de Chromium si ejecutas los spiders reales en modo `RUN_SPIDERS=1`

## Dependencias Python recomendadas

```bash
pip install selenium chromedriver-autoinstaller openpyxl requests scrapy pandas undetected-chromedriver scrapy-playwright
```

## Inicio rápido

1. Dentro de la carpeta del proyecto:

```bash
cd /home/user/scraper_timex-main
```

2. Crear y activar un entorno virtual:

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
```

3. Instalar dependencias:

```bash
python3 -m pip install selenium chromedriver-autoinstaller openpyxl requests scrapy pandas undetected-chromedriver scrapy-playwright
```

4. Iniciar el servidor en modo prueba (sin ejecutar los scrapers reales):

```bash
RUN_SPIDERS=0 python3 server.py
```

5. Abrir la UI en el navegador:

- `http://127.0.0.1:8002/`

## Modo real de scraping

Para ejecutar los scrapers reales desde la UI:

```bash
source venv/bin/activate
RUN_SPIDERS=1 python3 server.py
```

> **IMPORTANTE**: `RUN_SPIDERS=1` es necesario para que los scrapers funcionen correctamente. Sin esta variable, los endpoints devolverán respuestas simuladas.

## Páginas de la UI

- `/` - ejecutar scrapers pendientes para `proships`, `x-cargo`, `pasarex` e `imile`
- `/correo/` - generar y descargar el Excel de novedades SAC
- `/pasarex_asignar/` - asignar guías con credenciales de Proships o iMile (Pasarex deshabilitado en UI)
- `/contabilidad/` - generar el consolidado por mensajero y ver guías sin asignar

## Notas útiles

- No es un frontend Node.js: no requiere `npm install` ni compilación adicional.
- El servidor sirve archivos estáticos desde `frontend/`.
- Si necesitas abrir la UI desde Windows con WSL remoto, usa `http://localhost:8002/` si el puerto está accesible.
- Algunos scripts requieren credenciales y configuraciones adicionales mediante variables de entorno.

### Variables de entorno necesarias

#### Credenciales de proveedores
- `PROSHIPS_EMAIL`, `PROSHIPS_PASSWORD` - Para Proships
- `BIGSMART_EMAIL`, `BIGSMART_PASSWORD` - Para X-Cargo (BigSmart)
- `TRACKER_EMAIL`, `TRACKER_PASSWORD` - Para Pasarex
- `IMILE_EMAIL`, `IMILE_PASSWORD` - Para iMile

#### Credenciales de PackTrack (Rails)
- `PAQUETES_EMAIL`, `PAQUETES_PASSWORD` - Para mensajeros y contabilidad
- `PACKTRACK_EMAIL`, `PACKTRACK_PASSWORD` - Alias para PackTrack
- `PACKTRACK_BASE_URL` - URL base de PackTrack (por defecto: https://packtrack.site)

#### WhatsApp
- `SEND_WHATSAPP` - Activar envío por WhatsApp (1 para activar, 0 para desactivar)
- `WHATSAPP_COUNTRY_CODE` - Código de país (por defecto: 57 para Colombia)
- `WHATSAPP_FIRST_LOAD_SEC` - Tiempo para escanear QR (por defecto: 120 segundos)
- `WHATSAPP_CHAT_READY_SEC` - Timeout esperando caja de chat (por defecto: 35 segundos)
- `WHATSAPP_WAIT_TICKS_SEC` - Pausa entre ticks (por defecto: 45 segundos)
- `WHATSAPP_POST_SEND_SEC` - Pausa luego de enviar mensaje (por defecto: 1.8 segundos)
- `WHATSAPP_PROFILE_DIR` - Directorio para perfil de WhatsApp Web (por defecto: .whatsapp_web_profile)

#### Telegram
- `SEND_TELEGRAM` - Activar envío por Telegram (1, true, yes, on para activar)
- `CONTABILIDAD_EMPRESA` - Nombre de empresa para contabilidad (por defecto: proships)

## Errores conocidos

- Si el servidor ejecuta un script hijo con otro Python distinto al virtualenv, puede fallar al importar `selenium`.
  - Solución posible en `server.py`: agregar `import sys`
  - cambiar `['python3', script]` por `[sys.executable, script]` en los llamados de `python3`
- Si el spider falla al descargar ChromeDriver, verás un error que menciona `googlechromelabs.github.io` o `Could not reach host. Are you offline?`.
  - Este problema puede ser causado por falta de red en WSL o porque el gestor de drivers no pudo bajar el driver.
  - Para validar: ejecuta `ping -c 1 googlechromelabs.github.io` en WSL o intenta abrir una URL HTTPS desde WSL.
  - Posibles soluciones:
    - asegúrate de activar el `venv` antes de iniciar `server.py`
    - verifica que WSL tenga acceso a internet
    - instala localmente `chromium`/`chromium-driver` o el navegador compatible en WSL
    - reinicia la ejecución desde el mismo terminal con `source venv/bin/activate` y vuelve a correr `RUN_SPIDERS=1 python3 server.py`

## Cambios recientes

### v1.5 - Asignacion iMile (version inicial)
- Agregado script inicial `imile/asignar_imile.py` con dos credenciales de prueba para iMile.
- Agregada opcion `iMile` en la pagina `/pasarex_asignar/` y despliegue dinamico de credenciales por plataforma.
- Corregido error de validacion "Credencial de iMile invalida" usando `imileCredentialId` en backend.
- Implementado flujo inicial de procesamiento iMile que devuelve estado `OK` desde la UI.
- Mejorado reporte de errores de asignacion en backend mostrando salida completa del proceso en caso de fallo.
- Removida importacion `undetected_chromedriver` en `proships/asignar_proships/asignar_proships.py` para compatibilidad con Python 3.14 (`distutils`).

### v1.4 - Ajustes finales de iMile
- Corregido envío de WhatsApp para estados “Delivered” que son finales
- Añadido manejo seguro cuando PackTrack no encuentra el celular del mensajero
- Mejorada normalización de teléfono para WhatsApp (`00...`, `0XXXXXXXXX`, `57...`) 
- Mejorado formato de guia y número como texto en csv y excel

### v1.3 - Implementación de iMile
- Agregado proveedor iMile a la página principal de pendientes
- Implementado spider de iMile con login y búsqueda de órdenes
- Optimizaciones en carga de páginas y manejo de overlays
- Soporte de envío por WhatsApp desde la pantalla de pendientes por proveedor
- Actualizada estructura del proyecto con carpeta `imile/`

### v1.2 - Desactivación de Pasarex como opción por defecto
- Deshabilitar Pasarex en toda la aplicación
- Cambio de Pasarex a Proships como plataforma por defecto en `/pasarex_asignar/`
- Actualizado estado inicial en `server.py` y fallback en `frontend/app.js`

### v1.1 - Solución de problemas de ChromeDriver
- Reemplazado `webdriver-manager` por `chromedriver-autoinstaller` para mayor confiabilidad
- Actualizadas todas las dependencias en `requirements.txt`
- Solucionado problema de "Could not reach host" en WSL
- Estandarizado uso de `window.location.origin` en frontend para evitar problemas de CORS

## Cómo validar

- Levanta `server.py` con `RUN_SPIDERS=0`.
- Accede a `http://127.0.0.1:8002/`.
- Prueba la navegación entre `/`, `/correo/`, `/pasarex_asignar/` y `/contabilidad/`.
- Si quieres usar scrapers reales, cambia a `RUN_SPIDERS=1` y verifica que el navegador o Chromium esté disponible.
