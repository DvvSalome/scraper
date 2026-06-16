import csv
import io
import ast
import json
import os
import subprocess
import sys
import html
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
BASE_DIR = Path(__file__).resolve().parent

FRONTEND_DIR = BASE_DIR / "frontend"
PROSHIPS_DIR = BASE_DIR / "proships"
XCARGO_DIR = BASE_DIR / "x-cargo"
PASAREX_DIR = BASE_DIR / "pasarex"
CONTABILIDAD_DIR = BASE_DIR / "contabilidad"
IMILE_DIR = BASE_DIR / "imile"
PASAREX_PLUS_MILES = 3.0

CORREO_DIR = BASE_DIR / "proships_correo"
CORREO_TEMPLATE = CORREO_DIR / "FORMATO DE NOVEDADES SAC.xlsx"

PASAREX_ASIGNAR_DIR = BASE_DIR / "pasarex_asignar"
PASAREX_SCRIPT = "asignar_pasarex.py"
PROSHIPS_ASIGNAR_DIR = BASE_DIR / "proships" / "asignar_proships"
PROSHIPS_ASIGNAR_SCRIPT = "asignar_proships.py"
IMILE_ASIGNAR_DIR = BASE_DIR / "imile"
IMILE_ASIGNAR_SCRIPT = "asignar_imile.py"
LAST_RESULTS = []
SCRAPER_CONFIG = {
    "proships": {"workdir": PROSHIPS_DIR, "script": "proships_spider_with_whatsapp_v2.py"},
    "x-cargo": {"workdir": XCARGO_DIR, "script": "cargo_spider_updated_v4.py"},
    "pasarex": {"workdir": PASAREX_DIR, "script": "spider_pasarex.py"},
    "imile": {"workdir": IMILE_DIR, "script": "imile_spider.py"},
}
SCRAPER_STATES = {
    key: {
        "provider": key,
        "running": False,
        "status": "En espera",
        "error": None,
        "results": [],
    }
    for key in SCRAPER_CONFIG
}
PASAREX_ASSIGN_STATE = {
    "mode": "proships",
    "credentials": [],
    "selectedCredential": "",
    "proshipsCredentials": [],
    "selectedProshipsCredential": "",
    "imileCredentials": [],
    "selectedImileCredential": "",
    "guias": [],
}
PASAREX_PENDING_PROCESS = None
PASAREX_ASSIGN_STATE.setdefault("status", "En espera")
PASAREX_ASSIGN_STATE.setdefault("running", False)
PASAREX_ASSIGN_STATE.setdefault("error", None)


def _normalize_packages(raw_packages):
    if isinstance(raw_packages, list):
        items = raw_packages
    elif isinstance(raw_packages, str):
        items = raw_packages.split("\n")
    else:
        return []
    return [item.strip() for item in items if str(item).strip()]


def _normalize_guias(raw_guias):
    if isinstance(raw_guias, list):
        items = raw_guias
    elif isinstance(raw_guias, str):
        items = raw_guias.replace(",", "\n").split("\n")
    else:
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _simulate(packages, provider, whatsapp):
    return [
        {
            "paquete": paquete,
            "estado": "Procesado",
            "detalle": f"Proveedor: {provider} | WhatsApp: {'Activo' if whatsapp else 'Inactivo'}",
        }
        for paquete in packages
    ]

def _watch_pasarex(proc):
    try:
        output, _ = proc.communicate()
        output = (output or "").strip()

        PASAREX_ASSIGN_STATE["running"] = False
        if proc.returncode == 0:
            status_text = "finalizado"
            for line in output.splitlines():
                if "successful assignments" in line.lower():
                    status_text = line.strip().replace("STATUS:", "").strip() or "Successful assignments"
            PASAREX_ASSIGN_STATE["status"] = status_text
            PASAREX_ASSIGN_STATE["error"] = None
        else:
            error_message = output or f"Proceso Pasarex finalizó con código {proc.returncode}."
            PASAREX_ASSIGN_STATE["status"] = "Error"
            PASAREX_ASSIGN_STATE["error"] = error_message
            print(f"[Pasarex] returncode={proc.returncode} output:\n{output}")
    except Exception as e:
        PASAREX_ASSIGN_STATE["running"] = False
        PASAREX_ASSIGN_STATE["status"] = "Error"
        PASAREX_ASSIGN_STATE["error"] = str(e)
        print(f"[Pasarex] excepción al leer el proceso: {e}")


def _run_spider(packages, provider, whatsapp):
    provider_cfg = SCRAPER_CONFIG[provider]
    workdir = provider_cfg["workdir"]
    script = provider_cfg["script"]

    paquetes_file = workdir / "paquetes.txt"
    paquetes_file.write_text("\n".join(packages), encoding="utf-8")

    env = os.environ.copy()
    if whatsapp:
        env["SEND_WHATSAPP"] = "1"
    else:
        env.pop("SEND_WHATSAPP", None)

    result = subprocess.run(
        [sys.executable, script],
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Error ejecutando el spider")

    resultados_csv = workdir / "resultados.csv"
    if not resultados_csv.exists():
        return {"results": [], "guias_sin_asignar": []}

    rows = []
    with resultados_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        _headers = next(reader, [])
        for r in reader:
            if not r:
                continue
            rows.append(
                {
                    "tracking": r[0] if len(r) > 0 else "",
                    "status": r[1] if len(r) > 1 else "",
                    "fecha": r[2] if len(r) > 2 else "",
                    "tracking_2": r[3] if len(r) > 3 else "",
                    "cliente_direccion": r[4] if len(r) > 4 else "",
                    "cliente_nombre": r[5] if len(r) > 5 else "",
                    "cliente_numero": r[6] if len(r) > 6 else "",
                    "municipio": r[7] if len(r) > 7 else "",
                    "mensajero": r[8] if len(r) > 8 else "",
                    "estado": r[9] if len(r) > 9 else "",
                }
            )
    guias_sin_asignar_file = CONTABILIDAD_DIR / "guias_sin_asignar.txt"
    guias_sin_asignar = []
    if guias_sin_asignar_file.exists():
        guias_sin_asignar = [line.strip() for line in guias_sin_asignar_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    return {"results": rows, "guias_sin_asignar": guias_sin_asignar}


def _spider_state(provider):
    return SCRAPER_STATES[provider]


def _build_excel_html(rows):
    header_cells = "".join(
        f"<th>{html.escape(item)}</th>"
        for item in [
            "tracking",
            "status",
            "fecha",
            "tracking_2",
            "cliente_direccion",
            "cliente_nombre",
            "cliente_numero",
            "municipio",
            "mensajero",
            "estado",
        ]
    )

    body_rows = []
    for row in rows:
        columns = [
            row.get("tracking", ""),
            row.get("status", ""),
            row.get("fecha", ""),
            row.get("tracking_2", ""),
            row.get("cliente_direccion", ""),
            row.get("cliente_nombre", ""),
            row.get("cliente_numero", ""),
            row.get("municipio", ""),
            row.get("mensajero", ""),
            row.get("estado", ""),
        ]
        body_rows.append("<tr>" + "".join(f"<td>{html.escape(str(col))}</td>" for col in columns) + "</tr>")

    html_doc = f"""<!doctype html>
<html>
<head><meta charset=\"utf-8\"></head>
<body>
<table border=\"1\">
<thead><tr>{header_cells}</tr></thead>
<tbody>{''.join(body_rows)}</tbody>
</table>
</body>
</html>"""
    return html_doc


def _watch_pending_scraper(provider, process):
    state = _spider_state(provider)
    output = ""
    try:
        out, _ = process.communicate()
        output = (out or "").strip()
        if process.returncode == 0:
            state["results"] = _run_spider_results_from_disk(provider)
            state["status"] = "Finalizado"
            state["error"] = None
        else:
            state["status"] = "Error"
            state["error"] = output or f"El scraper terminó con código {process.returncode}"
    except Exception as exc:
        state["status"] = "Error"
        state["error"] = str(exc)
    finally:
        state["running"] = False


def _run_spider_results_from_disk(provider):
    resultados_csv = SCRAPER_CONFIG[provider]["workdir"] / "resultados.csv"
    if not resultados_csv.exists():
        return []

    rows = []
    with resultados_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        _headers = next(reader, [])
        for r in reader:
            if not r:
                continue
            rows.append(
                {
                    "tracking": r[0] if len(r) > 0 else "",
                    "status": r[1] if len(r) > 1 else "",
                    "fecha": r[2] if len(r) > 2 else "",
                    "tracking_2": r[3] if len(r) > 3 else "",
                    "cliente_direccion": r[4] if len(r) > 4 else "",
                    "cliente_nombre": r[5] if len(r) > 5 else "",
                    "cliente_numero": r[6] if len(r) > 6 else "",
                    "municipio": r[7] if len(r) > 7 else "",
                    "mensajero": r[8] if len(r) > 8 else "",
                    "estado": r[9] if len(r) > 9 else "",
                }
            )
    return rows


def _start_pending_scraper(provider, packages, whatsapp):
    state = _spider_state(provider)
    if state["running"]:
        raise RuntimeError("Ya hay un proceso corriendo para este proveedor.")

    cfg = SCRAPER_CONFIG[provider]
    workdir = cfg["workdir"]
    script = cfg["script"]
    (workdir / "paquetes.txt").write_text("\n".join(packages), encoding="utf-8")

    env = os.environ.copy()
    if whatsapp:
        env["SEND_WHATSAPP"] = "1"
    else:
        env.pop("SEND_WHATSAPP", None)

    process = subprocess.Popen(
        [sys.executable, script],
        cwd=str(workdir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    state["running"] = True
    state["status"] = "Procesando"
    state["error"] = None
    state["results"] = []

    watcher = threading.Thread(target=_watch_pending_scraper, args=(provider, process), daemon=True)
    watcher.start()

def _provider_from_pending_path(path, action):
    parts = path.strip("/").split("/")
    if len(parts) != 4:
        return None
    if parts[0] != "api" or parts[1] != "pending" or parts[3] != action:
        return None
    return parts[2]

def _run_correo_spider(codes):
    paquetes_file = CORREO_DIR / "paquetes.txt"
    paquetes_file.write_text("\n".join(codes), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "proships_spider.py"],
        cwd=str(CORREO_DIR),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Error ejecutando el spider de correo")

    if not CORREO_TEMPLATE.exists():
        raise RuntimeError("No se encontró el Excel de novedades.")
    return CORREO_TEMPLATE

def process_packages(packages, provider, whatsapp):
    if os.getenv("RUN_SPIDERS", "0") == "1":
        try:
            return _run_spider(packages, provider, whatsapp)
        except Exception as exc:
            return _simulate(packages, provider, whatsapp) + [
                {"paquete": "-", "estado": "Advertencia", "detalle": f"Falló el spider: {exc}"}
            ]
    return _simulate(packages, provider, whatsapp)


def _run_pasarex_script(credential_id, guias):
    env = os.environ.copy()
    env["PASAREX_CREDENCIAL"] = credential_id
    env["PASAREX_GUIAS"] = json.dumps(guias)

    return subprocess.Popen(
        [sys.executable, PASAREX_SCRIPT],
        cwd=str(PASAREX_ASIGNAR_DIR),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

def _run_proships_assign_script(credential_id, guias):
    env = os.environ.copy()
    env["PROSHIPS_CREDENTIAL"] = credential_id
    env["PROSHIPS_GUIAS"] = json.dumps(guias)

    return subprocess.Popen(
        [sys.executable, PROSHIPS_ASIGNAR_SCRIPT],
        cwd=str(PROSHIPS_ASIGNAR_DIR),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def _run_imile_assign_script(credential_id, guias):
    env = os.environ.copy()
    env["IMILE_CREDENCIAL"] = credential_id
    env["IMILE_GUIAS"] = json.dumps(guias)

    return subprocess.Popen(
        [sys.executable, IMILE_ASIGNAR_SCRIPT],
        cwd=str(IMILE_ASIGNAR_DIR),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

def _load_pasarex_assign_data():
    pasarex_path = PASAREX_ASIGNAR_DIR / PASAREX_SCRIPT
    pasarex_source = pasarex_path.read_text(encoding="utf-8")
    credentials = []
    selected = ""
    parsed_guias = []

    pasarex_tree = ast.parse(pasarex_source)
    creds_dict = {}

    for node in pasarex_tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CREDENCIALES":
                    creds_dict = ast.literal_eval(node.value)
                if isinstance(target, ast.Name) and target.id == "CREDENCIAL_SELECCIONADA":
                    try:
                        selected = ast.literal_eval(node.value)
                    except Exception:
                        selected = ""
                if isinstance(target, ast.Name) and target.id == "guias":
                    try:
                        parsed_guias = [str(item) for item in ast.literal_eval(node.value)]
                    except Exception:
                        parsed_guias = []

    for credential_id, data in creds_dict.items():
        display_name = data.get("nombre") or data.get("label") or credential_id
        credentials.append({"id": credential_id, "displayName": display_name})

    if not selected and credentials:
        selected = credentials[0]["id"]

    proships_credentials = []
    selected_proships = ""
    proships_path = PROSHIPS_ASIGNAR_DIR / PROSHIPS_ASIGNAR_SCRIPT
    proships_source = proships_path.read_text(encoding="utf-8")
    proships_tree = ast.parse(proships_source)
    proships_dict = {}

    for node in proships_tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "credenciales":
                    proships_dict = ast.literal_eval(node.value)

    for credential_id, data in proships_dict.items():
        display_name = data.get("nombre") or credential_id
        email = (data.get("email") or "").strip()
        proships_credentials.append({"id": credential_id, "displayName": f"{display_name} ({email})" if email else display_name})

    if proships_credentials:
        selected_proships = proships_credentials[0]["id"]

    imile_credentials = []
    selected_imile = ""
    imile_path = IMILE_DIR / "asignar_imile.py"
    if imile_path.exists():
        imile_source = imile_path.read_text(encoding="utf-8")
        imile_tree = ast.parse(imile_source)
        imile_dict = {}
        for node in imile_tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "CREDENCIALES":
                        imile_dict = ast.literal_eval(node.value)
                    if isinstance(target, ast.Name) and target.id == "CREDENCIAL_SELECCIONADA":
                        try:
                            selected_imile = ast.literal_eval(node.value)
                        except Exception:
                            selected_imile = ""

        for credential_id, data in imile_dict.items():
            display_name = data.get("nombre") or data.get("label") or credential_id
            email = (data.get("email") or "").strip()
            imile_credentials.append({"id": credential_id, "displayName": f"{display_name} ({email})" if email else display_name})

    if not selected_imile and imile_credentials:
        selected_imile = imile_credentials[0]["id"]

    PASAREX_ASSIGN_STATE["credentials"] = credentials
    PASAREX_ASSIGN_STATE["selectedCredential"] = selected
    PASAREX_ASSIGN_STATE["proshipsCredentials"] = proships_credentials
    PASAREX_ASSIGN_STATE["selectedProshipsCredential"] = selected_proships
    PASAREX_ASSIGN_STATE["imileCredentials"] = imile_credentials
    PASAREX_ASSIGN_STATE["selectedImileCredential"] = selected_imile
    PASAREX_ASSIGN_STATE["guias"] = parsed_guias

def _run_contabilidad_spider(packages, provider="proships", send_telegram=False):
    provider = str(provider or "proships").strip().lower()

    paquetes_file = CONTABILIDAD_DIR / "paquetes.txt"
    paquetes_file.write_text("\n".join(packages), encoding="utf-8")

    env = os.environ.copy()
    env["SEND_TELEGRAM"] = "1" if send_telegram else "0"
    env["CONTABILIDAD_EMPRESA"] = provider

    script_name = "contabilidad_spider_con_telegram_v3.py" if send_telegram else "contabilidad_spider.py"

    result = subprocess.run(
        [sys.executable, script_name],
        cwd=str(CONTABILIDAD_DIR),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "Error ejecutando spider de contabilidad"
        )

    resultados_csv = CONTABILIDAD_DIR / "resultados.csv"
    guias_txt = CONTABILIDAD_DIR / "guias_sin_asignar.txt"

    rows = []
    if resultados_csv.exists():
        with resultados_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            _headers = next(reader, [])
            for r in reader:
                if not r:
                    continue

                rows.append(
                    {
                        "mensajero": (r[0] if len(r) > 0 else "").strip(),
                        "plus": int(float(r[1])) if len(r) > 1 and str(r[1]).strip() else 0,
                        "total_plus": float(r[2]) if len(r) > 2 and str(r[2]).strip() else 0.0,
                        "normal": int(float(r[3])) if len(r) > 3 and str(r[3]).strip() else 0,
                        "total_normal": float(r[4]) if len(r) > 4 and str(r[4]).strip() else 0.0,
                        "total_general": float(r[5]) if len(r) > 5 and str(r[5]).strip() else 0.0,
                    }
                )

    if provider == "pasarex":
        for row in rows:
            total_pasarex = row["plus"] + row["normal"]
            row["plus"] = total_pasarex
            row["normal"] = 0
            row["total_normal"] = 0.0
            row["total_plus"] = total_pasarex * PASAREX_PLUS_MILES
            row["total_general"] = row["total_plus"]

    guias_sin_asignar = []
    if guias_txt.exists():
        contenido = guias_txt.read_text(encoding="utf-8").strip()
        if contenido:
            guias_sin_asignar = [
                linea.strip()
                for linea in contenido.splitlines()
                if linea.strip()
            ]

    return {
        "results": rows,
        "guias_sin_asignar": guias_sin_asignar,
    }
class RequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def _send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_csv(self, csv_text, filename="resultados.csv"):
        data = csv_text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path, content_type, filename=None):
        data = path.read_bytes()
        self._send_bytes(data, content_type, filename=filename)

    def _send_bytes(self, data, content_type, filename=None):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        provider = _provider_from_pending_path(self.path, "status")
        if provider is not None:
            if provider not in SCRAPER_CONFIG:
                self._send_json({"error": "Proveedor inválido."}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(_spider_state(provider))
            return

        provider = _provider_from_pending_path(self.path, "download.csv")
        if provider is not None:
            if provider not in SCRAPER_CONFIG:
                self._send_json({"error": "Proveedor inválido."}, status=HTTPStatus.BAD_REQUEST)
                return
            csv_path = SCRAPER_CONFIG[provider]["workdir"] / "resultados.csv"
            if not csv_path.exists():
                self._send_json({"error": "No existe resultados.csv para descargar."}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_csv(csv_path.read_text(encoding="utf-8", errors="replace"), filename=f"resultados-{provider}.csv")
            return

        provider = _provider_from_pending_path(self.path, "download.xlsx")
        if provider is not None:
            if provider not in SCRAPER_CONFIG:
                self._send_json({"error": "Proveedor inválido."}, status=HTTPStatus.BAD_REQUEST)
                return
            rows = _spider_state(provider).get("results") or _run_spider_results_from_disk(provider)
            if not rows:
                self._send_json({"error": "No hay resultados para exportar."}, status=HTTPStatus.BAD_REQUEST)
                return
            excel_data = _build_excel_html(rows).encode("utf-8")
            self._send_bytes(
                excel_data,
                "application/vnd.ms-excel; charset=utf-8",
                filename=f"resultados-{provider}.xls",
            )
            return

        if self.path == "/api/download":
            # descarga resultados.csv real si existe (proships / x-cargo)
            posibles = [PROSHIPS_DIR / "resultados.csv", XCARGO_DIR / "resultados.csv", PASAREX_DIR / "resultados.csv"]
            csv_path = next((p for p in posibles if p.exists()), None)
            if not csv_path:
                self._send_json({"error": "No existe resultados.csv para descargar."}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_csv(csv_path.read_text(encoding="utf-8", errors="replace"), filename="resultados.csv")
            return

        if self.path == "/api/correo/download":
            if not CORREO_TEMPLATE.exists():
                self._send_json({"error": "No hay Excel de novedades disponible."}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_file(
                CORREO_TEMPLATE,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=CORREO_TEMPLATE.name,
            )
            return
        if self.path == "/api/pasarex/asignar":
            self._send_json(PASAREX_ASSIGN_STATE)
            return

        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):  # noqa: N802
        global LAST_RESULTS
        global PASAREX_PENDING_PROCESS

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": "JSON inválido"}, status=HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/process":
            packages = _normalize_packages(payload.get("packages", []))
            provider = payload.get("provider", "proships")
            whatsapp = bool(payload.get("whatsapp", False))

            if not packages:
                self._send_json({"error": "Debes ingresar al menos un paquete."}, status=HTTPStatus.BAD_REQUEST)
                return

            if provider not in {"proships", "x-cargo", "pasarex"}:
                self._send_json({"error": "Proveedor inválido."}, status=HTTPStatus.BAD_REQUEST)
                return

            results = process_packages(packages, provider, whatsapp)
            LAST_RESULTS = results
            if isinstance(results, dict):
                self._send_json({"status": "ok", "results": results.get("results", []), "guias_sin_asignar": results.get("guias_sin_asignar", [])})
            else:
                self._send_json({"status": "ok", "results": results, "guias_sin_asignar": []})
            return

        provider = _provider_from_pending_path(self.path, "start")
        if provider is not None:
            whatsapp = bool(payload.get("whatsapp", False))
            packages = _normalize_packages(payload.get("packages", []))

            if provider not in SCRAPER_CONFIG:
                self._send_json({"error": "Proveedor inválido."}, status=HTTPStatus.BAD_REQUEST)
                return

            if not packages:
                self._send_json({"error": "Debes ingresar al menos un paquete."}, status=HTTPStatus.BAD_REQUEST)
                return

            run_real_spider = os.getenv("RUN_SPIDERS", "0") == "1"
            if run_real_spider:
                try:
                    _start_pending_scraper(provider, packages, whatsapp)
                except Exception as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
            else:
                state = _spider_state(provider)
                state["results"] = _simulate(packages, provider, whatsapp)
                state["running"] = False
                state["status"] = "Finalizado (simulado)"
                state["error"] = None

            self._send_json({"status": "ok", "message": "Proceso iniciado", "provider": provider})
            return

        if self.path == "/api/correo/process":
            codes = _normalize_packages(payload.get("codes", []))
            if not codes:
                self._send_json({"error": "Debes ingresar al menos un código."}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                _run_correo_spider(codes)
            except Exception as exc:
                self._send_json({"error": str(exc) or "Error generando el Excel."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"status": "ok"})
            return
        if self.path == "/api/contabilidad/process":
            packages = _normalize_packages(payload.get("packages", []))
            company = payload.get("company") or payload.get("provider", "proships")
            send_telegram = bool(payload.get("send_telegram", False))
            global EMPRESA_NOMBRE
            EMPRESA_NOMBRE = company

            if not packages:
                self._send_json({"error": "Debes ingresar al menos un paquete."}, status=HTTPStatus.BAD_REQUEST)
                return

            if company not in {"x-cargo", "proships", "pasarex"}:
                self._send_json({"error": "Proveedor inválido."}, status=HTTPStatus.BAD_REQUEST)
                return

            try:
                contabilidad_data = _run_contabilidad_spider(packages, company, send_telegram)
                if isinstance(contabilidad_data, list):
                    results = contabilidad_data
                    guias_sin_asignar = []
                elif isinstance(contabilidad_data, dict):
                    results = contabilidad_data.get("results", [])
                    guias_sin_asignar = contabilidad_data.get("guias_sin_asignar", [])
                else:
                    results = []
                    guias_sin_asignar = []

                provider_label = {
                    "x-cargo": "X Cargo",
                    "proships": "Proships",
                    "pasarex": "Pasarex",
                }.get(company, company)

                for row in results:
                    row["empresa"] = provider_label

                self._send_json({
                    "status": "ok",
                    "results": results,
                    "guias_sin_asignar": guias_sin_asignar,
                })
                return

            except Exception as exc:
                self._send_json(
                    {"error": str(exc) or "Error ejecutando contabilidad."},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR
                )
                return
        if self.path == "/api/pasarex/asignar/procesar":
            mode = str(payload.get("mode", "proships")).strip().lower()
            credential_id = payload.get("credentialId", "")
            imile_credential_id = payload.get("imileCredentialId", credential_id)
            proships_credential_id = payload.get("proshipsCredentialId", "")
            guias = _normalize_guias(payload.get("guias", []))

            if mode not in {"pasarex", "proships", "imile"}:
                self._send_json({"error": "Modo inválido."}, status=HTTPStatus.BAD_REQUEST)
                return

            if not guias:
                self._send_json({"error": "Debes ingresar al menos una guía."}, status=HTTPStatus.BAD_REQUEST)
                return

            if PASAREX_ASSIGN_STATE.get("running"):
                self._send_json({"error": "Ya hay un proceso de asignación en ejecución."}, status=HTTPStatus.BAD_REQUEST)
                return
            if mode == "pasarex":
                valid_ids = {item["id"] for item in PASAREX_ASSIGN_STATE["credentials"]}
                if credential_id not in valid_ids:
                    self._send_json({"error": "Credencial de Pasarex inválida."}, status=HTTPStatus.BAD_REQUEST)
                    return
                PASAREX_PENDING_PROCESS = _run_pasarex_script(credential_id, guias)
                PASAREX_ASSIGN_STATE["mode"] = mode
                PASAREX_ASSIGN_STATE["running"] = True
                PASAREX_ASSIGN_STATE["status"] = "Procesando"
                PASAREX_ASSIGN_STATE["error"] = None
            elif mode == "proships":
                valid_ids = {item["id"] for item in PASAREX_ASSIGN_STATE["proshipsCredentials"]}
                if proships_credential_id not in valid_ids:
                    self._send_json({"error": "Credencial de Proships inválida."}, status=HTTPStatus.BAD_REQUEST)
                    return
                PASAREX_PENDING_PROCESS = _run_proships_assign_script(proships_credential_id, guias)
                PASAREX_ASSIGN_STATE["mode"] = mode
                PASAREX_ASSIGN_STATE["running"] = True
                PASAREX_ASSIGN_STATE["status"] = "Procesando"
                PASAREX_ASSIGN_STATE["error"] = None
            else:
                valid_ids = {item["id"] for item in PASAREX_ASSIGN_STATE["imileCredentials"]}
                if imile_credential_id not in valid_ids:
                    self._send_json({"error": "Credencial de iMile inválida."}, status=HTTPStatus.BAD_REQUEST)
                    return
                PASAREX_ASSIGN_STATE["mode"] = mode
                PASAREX_ASSIGN_STATE["selectedImileCredential"] = imile_credential_id
                PASAREX_PENDING_PROCESS = _run_imile_assign_script(imile_credential_id, guias)
                PASAREX_ASSIGN_STATE["running"] = True
                PASAREX_ASSIGN_STATE["status"] = "Procesando"
                PASAREX_ASSIGN_STATE["error"] = None

            if mode in {"pasarex", "proships", "imile"}:
                watcher = threading.Thread(target=_watch_pasarex, args=(PASAREX_PENDING_PROCESS,), daemon=True)
                watcher.start()
            self._send_json({"status": "ok", "message": "Proceso iniciado."})
            return


        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint no encontrado")


def main():
    _load_pasarex_assign_data()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8002"))
    server = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"Servidor iniciado en http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
