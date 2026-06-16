/******************** ELEMENTOS GENERALES ********************/
const form = document.getElementById("process-form");
const packagesInput = document.getElementById("packages");
const providerSelect = document.getElementById("provider");
const whatsappCheckbox = document.getElementById("whatsapp");
const statusText = document.getElementById("status-text");
const resultsBody = document.getElementById("results-body");
const downloadButton = document.getElementById("download");
const submitButton = form?.querySelector("button.primary");

/******************** CONTABILIDAD ********************/
const contabilidadForm = document.getElementById("contabilidad-form");
const contabilidadCompanySelect = document.getElementById("contabilidad-company");
const contabilidadPackagesInput = document.getElementById("contabilidad-packages");
const contabilidadStatusText = document.getElementById("contabilidad-status-text");
const contabilidadHeaders = document.getElementById("contabilidad-headers");
const contabilidadResultsBody = document.getElementById("contabilidad-results-body");
const contabilidadSubmit = document.getElementById("contabilidad-submit");


const API_BASE = window.location.origin || "http://127.0.0.1:8002";

/******************** HELPERS ********************/

const pendingCards = document.querySelectorAll(".pending-card");

const parseItems = (raw) =>
  raw
    .split(/\n|,/) 
    .map((x) => x.trim())
    .filter(Boolean);

const renderPendingResults = (tbody, rows) => {
  tbody.innerHTML = "";

  if (!rows.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="3" class="empty">Sin resultados aún.</td>';   
    tbody.appendChild(row);
    return;
  }
const excludedStatusKeywords = [
  "entregado",
  "entregado al cliente",
  "pod",
  "delivered",
  "ecc",
  "fuera de zona",
  "devolucion",
  "devolución",
  "devuelto",
];

const pendientes = rows.filter((r) => {
  const status = (r.status || "")
    .toLowerCase()
    .normalize("NFD") // elimina tildes
    .replace(/[\u0300-\u036f]/g, "")
    .trim();

  if (!status) return true;

  return !excludedStatusKeywords.some((word) =>
    status.includes(word)
  );
});
  const grouped = new Map();

  pendientes.forEach((r) => {
    const mensajero = (r.mensajero || "Sin mensajero").trim() || "Sin mensajero";
    const fecha = (r.fecha || "Sin fecha").trim() || "Sin fecha";
    const key = `${mensajero}__${fecha}`;

    if (!grouped.has(key)) {
      grouped.set(key, { mensajero, fecha, pendientes: 0 });
    }

    grouped.get(key).pendientes += 1;
  });

  const aggregatedRows = Array.from(grouped.values()).sort((a, b) => {
    if (a.mensajero !== b.mensajero) return a.mensajero.localeCompare(b.mensajero, "es");
    return a.fecha.localeCompare(b.fecha, "es");
  });

  aggregatedRows.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.mensajero}</td>
      <td>${item.fecha}</td>
      <td>${item.pendientes}</td>
    `;
    tbody.appendChild(row);
  });
};



/******************** PROCESO NORMAL (PENDIENTES) ********************/
const downloadFile = async (url, fallbackName) => {
  const res = await fetch(url);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "No fue posible descargar el archivo");
  }

  const blob = await res.blob();
  const header = res.headers.get("Content-Disposition") || "";
  const match = header.match(/filename="([^"]+)"/);
  const fileName = match?.[1] || fallbackName;
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(objectUrl);
};

const initPendingCard = (card) => {
  const provider = card.dataset.provider;
  const form = card.querySelector(".pending-form");
  const packagesInput = card.querySelector(".pending-packages");
  const whatsappInput = card.querySelector(".pending-whatsapp");
  const statusText = card.querySelector(".pending-status");
  const resultsBody = card.querySelector(".pending-results-body");
  const submitButton = form.querySelector("button.primary");
  const downloadCsvButton = card.querySelector(".pending-download-csv");
  const downloadExcelButton = card.querySelector(".pending-download-xlsx");

  let pollInterval = null;

  const setStatus = (message) => {
    statusText.textContent = message;
  };

  const pollStatus = async () => {
    const res = await fetch(`${API_BASE}/api/pending/${provider}/status`);
    const data = await res.json();

    if (!res.ok) {
      setStatus(data.error || "Error consultando estado");
      submitButton.disabled = false;
      return;
    }

    setStatus(data.error ? `Error: ${data.error}` : data.status || "En espera");
    renderPendingResults(resultsBody, data.results || []);

    if (data.running) {
      submitButton.disabled = true;
      if (!pollInterval) {
        pollInterval = setInterval(() => {
          pollStatus().catch(() => {});
        }, 2000);
      }
    } else {
      submitButton.disabled = false;
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    }
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const packages = parseItems(packagesInput.value);

    if (!packages.length) {
      setStatus("Ingresa al menos un paquete.");
      return;
    }

    submitButton.disabled = true;
    setStatus("Encolando trabajo...");

    const res = await fetch(`${API_BASE}/api/pending/${provider}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ packages, whatsapp: whatsappInput.checked }),
    });

    const data = await res.json();
    if (!res.ok) {
      setStatus(data.error || "No fue posible iniciar el scraper");
      submitButton.disabled = false;
      return;
    }

    setStatus("Procesando");
    await pollStatus();
  });

  downloadCsvButton.addEventListener("click", async () => {
    try {
      await downloadFile(`${API_BASE}/api/pending/${provider}/download.csv`, `resultados-${provider}.csv`);
    } catch (err) {
      setStatus(err.message);
    }
  });

  downloadExcelButton.addEventListener("click", async () => {
    try {
      await downloadFile(`${API_BASE}/api/pending/${provider}/download.xlsx`, `resultados-${provider}.xls`);
    } catch (err) {
      setStatus(err.message);
    }
  });

  pollStatus().catch(() => setStatus("No se pudo consultar el estado inicial"));
};

if (pendingCards.length) {
  pendingCards.forEach((card) => initPendingCard(card));
}

/******************** PASAREX ASIGNAR ********************/
const pasarexForm = document.getElementById("pasarex-form");
const pasarexModeSelect = document.getElementById("pasarex-mode");
const pasarexCredentialField = document.getElementById("pasarex-credential-field");
const pasarexCredentialSelect = document.getElementById("pasarex-credenciales");
const imileCredentialField = document.getElementById("imile-credential-field");
const imileCredentialSelect = document.getElementById("imile-credenciales");
const pasarexGuiasInput = document.getElementById("pasarex-guias");
const proshipsCredentialField = document.getElementById("proships-credential-field");
const proshipsCredentialSelect = document.getElementById("proships-credenciales");
const pasarexStatusText = document.getElementById("pasarex-status-text");
const pasarexProcesarButton = document.getElementById("pasarex-procesar");

let pasarexPollInterval = null;

const setPasarexStatus = (message) => {
  if (pasarexStatusText) pasarexStatusText.textContent = message;
};

const renderContabilidadTable = ({ headers = [], rows = [] }) => {
  if (!contabilidadHeaders || !contabilidadResultsBody) return;

  contabilidadHeaders.innerHTML = "";
  contabilidadResultsBody.innerHTML = "";

  if (!headers.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td class="empty">Sin resultados aún.</td>';
    contabilidadResultsBody.appendChild(row);
    return;
  }

  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    contabilidadHeaders.appendChild(th);
  });

  if (!rows.length) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="${headers.length}" class="empty">Sin filas para la empresa seleccionada.</td>`;
    contabilidadResultsBody.appendChild(row);
    return;
  }

  rows.forEach((item) => {
    const row = document.createElement("tr");
    headers.forEach((header) => {
      const td = document.createElement("td");
      td.textContent = item[header] ?? "";
      row.appendChild(td);
    });
    contabilidadResultsBody.appendChild(row);
  });
};

const loadContabilidadCompanies = async () => {
  if (!contabilidadForm) return;

  const res = await fetch(`${API_BASE}/api/contabilidad/empresas`);
  const data = await res.json();

  contabilidadCompanySelect.innerHTML = "";
  (data.companies || []).forEach((company) => {
    const opt = document.createElement("option");
    opt.value = company.id;
    opt.textContent = company.name;
    contabilidadCompanySelect.appendChild(opt);
  });
};

const loadContabilidadResults = async () => {
  if (!contabilidadForm) return;
  const company = contabilidadCompanySelect.value;
  if (!company) return;

  setContabilidadStatus("Cargando tabla...");
  const res = await fetch(`${API_BASE}/api/contabilidad/results?company=${encodeURIComponent(company)}`);
  const data = await res.json();

  if (!res.ok) throw new Error(data.error || "Error cargando la tabla de contabilidad");

  renderContabilidadTable(data);
  setContabilidadStatus(`Mostrando tabla de ${company}.`);
};

const processContabilidad = async () => {
  const company = contabilidadCompanySelect.value;
  const packages = parseItems(contabilidadPackagesInput.value);
  if (!packages.length) {
    throw new Error("Ingresa al menos un paquete para contabilidad.");
  }

  const res = await fetch(`${API_BASE}/api/contabilidad/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company, packages }),
  });
  const data = await res.json();

  if (!res.ok) throw new Error(data.error || "Error procesando contabilidad");

  renderContabilidadTable(data);
  setContabilidadStatus(`Proceso finalizado para ${company}.`);
};

if (contabilidadForm) {
  loadContabilidadCompanies()
    .then(loadContabilidadResults)
    .catch((err) => setContabilidadStatus(err.message));

  contabilidadCompanySelect.addEventListener("change", () => {
    loadContabilidadResults().catch((err) => setContabilidadStatus(err.message));
  });

  contabilidadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    contabilidadSubmit.disabled = true;
    setContabilidadStatus("Procesando...");
    try {
      await processContabilidad();
    } catch (err) {
      setContabilidadStatus(err.message);
    } finally {
      contabilidadSubmit.disabled = false;
    }
  });
}

/******************** PASAREX ********************/
const parseGuias = (raw) =>
  raw.split(/\n|,/).map((x) => x.trim()).filter(Boolean);

const loadPasarexData = async () => {
  if (!pasarexForm) return null;

  setPasarexStatus("Cargando configuración...");
  const res = await fetch(`${API_BASE}/api/pasarex/asignar`);
  const data = await res.json();

  pasarexCredentialSelect.innerHTML = "";
  (data.credentials || []).forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.displayName;
    pasarexCredentialSelect.appendChild(opt);
  });

  imileCredentialSelect.innerHTML = "";
  (data.imileCredentials || []).forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.displayName;
    imileCredentialSelect.appendChild(opt);
  });

  proshipsCredentialSelect.innerHTML = "";
  (data.proshipsCredentials || []).forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.displayName;
    proshipsCredentialSelect.appendChild(opt);
  });

  pasarexCredentialSelect.value = data.selectedCredential || "";
  imileCredentialSelect.value = data.selectedImileCredential || "";
  proshipsCredentialSelect.value = data.selectedProshipsCredential || "";
  pasarexModeSelect.value = data.mode || "proships";

  toggleCredentialFields();
  pasarexGuiasInput.value = (data.guias || []).join("\n");

  if (data.status) {
    setPasarexStatus(data.status);
  } else {
    setPasarexStatus("Listo.");
  }

  return data;
};
const toggleCredentialFields = () => {
  const mode = pasarexModeSelect.value;
  const isProships = mode === "proships";
  const isPasarex = mode === "pasarex";
  const isImile = mode === "imile";

  pasarexCredentialField.style.display = isPasarex ? "block" : "none";
  imileCredentialField.style.display = isImile ? "block" : "none";
  proshipsCredentialField.style.display = isProships ? "block" : "none";
};
// --- PASAREX: polling correcto (sin return suelto) ---
const pollPasarexStatus = async () => {
  if (!pasarexForm) return;

  try {
    const res = await fetch(`${API_BASE}/api/pasarex/asignar`);
    const data = await res.json();

    if (data.error) setPasarexStatus(`Error: ${data.error}`);
    else if (data.status) setPasarexStatus(data.status);

    // cuando termina, paramos polling
    if (data.running === false) {
      if (pasarexProcesarButton) pasarexProcesarButton.disabled = false;
      if (pasarexPollInterval) {
        clearInterval(pasarexPollInterval);
        pasarexPollInterval = null;
      }
    }
  } catch (_err) {
    // noop
  }
};

const startPasarexPolling = () => {
  if (!pasarexForm || pasarexPollInterval) return;
  pasarexPollInterval = setInterval(() => {
    pollPasarexStatus();
  }, 1500);
};

const pasarexProcesar = async () => {
  const mode = pasarexModeSelect.value;
  const credentialId = pasarexCredentialSelect.value;
  const imileCredentialId = imileCredentialSelect.value;
  const proshipsCredentialId = proshipsCredentialSelect.value;
  const guias = parseItems(pasarexGuiasInput.value);

  setPasarexStatus("Iniciando proceso...");
  pasarexProcesarButton.disabled = true;
  const res = await fetch(`${API_BASE}/api/pasarex/asignar/procesar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, credentialId, imileCredentialId, proshipsCredentialId, guias }),
  });

  const data = await res.json();
  if (!res.ok) {
    pasarexProcesarButton.disabled = false;
    throw new Error(data.error);
  }

  setPasarexStatus("Procesando");
  startPasarexPolling();

};



if (pasarexForm) {
  loadPasarexData().then((data) => {
    if (data?.running) {
      pasarexProcesarButton.disabled = true;
      startPasarexPolling();
    }
  });
  pasarexModeSelect.addEventListener("change", () => {
    toggleCredentialFields();
  });

  pasarexForm.addEventListener("submit", (e) => {
    e.preventDefault();
    pasarexProcesar().catch((err) => setPasarexStatus(err.message));
  });

  pasarexProcesarButton.addEventListener("click", (e) => {
    e.preventDefault();
    pasarexProcesar().catch((err) => setPasarexStatus(err.message));
  });
}