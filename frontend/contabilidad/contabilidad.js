const form = document.getElementById("contabilidad-form");
const providerSelect = document.getElementById("contabilidad-provider");
const packagesInput = document.getElementById("contabilidad-packages");
const statusText = document.getElementById("contabilidad-status-text");
const resultsHead = document.getElementById("contabilidad-results-head");
const resultsBody = document.getElementById("contabilidad-results-body");
const resultsFoot = document.getElementById("contabilidad-results-foot");
const submitButton = document.getElementById("contabilidad-procesar");
const sendTelegramCheckbox = document.getElementById("contabilidad-send-telegram");
const unassignedGuides = document.getElementById("contabilidad-unassigned-guides");
const totalPlusCount = document.getElementById("total-plus-count");
const totalPlusValue = document.getElementById("total-plus-value");
const totalNormalCount = document.getElementById("total-normal-count");
const totalNormalValue = document.getElementById("total-normal-value");
const totalGeneralValue = document.getElementById("total-general-value");

const API_BASE = window.location.origin || "http://127.0.0.1:8002";

const setStatus = (message) => {
  if (statusText) statusText.textContent = message;
};

const normalizePackages = (raw) =>
  raw
    .split(/\n|,|;/)
    .map((item) => item.trim())
    .filter(Boolean);

const parseNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
};
const normalizeMoneyValue = (value) => {
  const numeric = Number(value) || 0;
  if (numeric !== 0 && Math.abs(numeric) < 1000) {
    return numeric * 1000;
  }
  return numeric;
};

const formatCurrency = (value) => {
  const numberValue = normalizeMoneyValue(value);
  if (numberValue === 0) return "0";
  return numberValue.toLocaleString("es-CO");
};

const getColumns = (provider) => {
  if (provider === "pasarex") {
    return ["EMPRESA","Mensajero", "Plus", "Total plus", "Total general"];
  }
  return ["EMPRESA","Mensajero", "Plus", "Total plus", "Normal", "Total normal", "Total general"];
};

const renderHeader = (provider) => {
  const columns = getColumns(provider);
  resultsHead.innerHTML = `<tr>${columns.map((col) => `<th>${col}</th>`).join("")}</tr>`;
};

const renderFooter = (provider, totals) => {
  if (provider === "pasarex") {
    resultsFoot.innerHTML = `
      <tr class="totals-row">
        <td></td>
        <td><strong>TOTAL GENERAL</strong></td>
        <td>${totals.plusCount}</td>
        <td>${formatCurrency(totals.plusValue)}</td>
        <td>${formatCurrency(totals.generalValue)}</td>
      </tr>
    `;
    return;
  }

  resultsFoot.innerHTML = `
    <tr class="totals-row">
      <td></td>
      <td><strong>TOTAL GENERAL</strong></td>
      <td>${totals.plusCount}</td>
      <td>${formatCurrency(totals.plusValue)}</td>
      <td>${totals.normalCount}</td>
      <td>${formatCurrency(totals.normalValue)}</td>
      <td>${formatCurrency(totals.generalValue)}</td>
    </tr>
  `;
};

const computeTotals = (rows) => {
  const totals = {
    plusCount: 0,
    plusValue: 0,
    normalCount: 0,
    normalValue: 0,
    generalValue: 0,
  };

  rows.forEach((row) => {
    totals.plusCount += parseNumber(row.plus);
    totals.plusValue += normalizeMoneyValue(row.total_plus);
    totals.normalCount += parseNumber(row.normal);
    totals.normalValue += normalizeMoneyValue(row.total_normal);
    totals.generalValue += normalizeMoneyValue(row.total_general);
  });

  return totals;
};


const renderResults = (rows, provider) => {
  renderHeader(provider);
  resultsBody.innerHTML = "";

  const colCount = getColumns(provider).length;
  if (!rows.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="${colCount}" class="empty">Sin resultados aún.</td>`;
    resultsBody.appendChild(tr);
    renderFooter(provider, computeTotals([]));
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    if (provider === "pasarex") {
      tr.innerHTML = `
        <td>${row.empresa || ""}</td>
        <td>${row.mensajero ?? ""}</td>
        <td>${row.plus ?? 0}</td>
        <td>${formatCurrency(row.total_plus ?? 0)}</td>
        <td>${formatCurrency(row.total_general ?? 0)}</td>
      `;
    } else {
      tr.innerHTML = `
        <td>${row.empresa || ""}</td>
        <td>${row.mensajero ?? ""}</td>
        <td>${row.plus ?? 0}</td>
        <td>${formatCurrency(row.total_plus ?? 0)}</td>
        <td>${row.normal ?? 0}</td>
        <td>${formatCurrency(row.total_normal ?? 0)}</td>
        <td>${formatCurrency(row.total_general ?? 0)}</td>
      `;
    }
    resultsBody.appendChild(tr);
  });

  renderFooter(provider, computeTotals(rows));
};
const renderUnassignedGuides = (guides = []) => {
  if (!unassignedGuides) return;

  if (!guides.length) {
    unassignedGuides.textContent = "Sin guías sin asignar.";
    unassignedGuides.classList.add("empty");
    return;
  }

  unassignedGuides.textContent = guides.join(", ");
  unassignedGuides.classList.remove("empty");
};
const processContabilidad = async (packages, provider, sendTelegram) => {
  const response = await fetch(`${API_BASE}/api/contabilidad/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    
    body: JSON.stringify({ packages, provider, company: provider, send_telegram: sendTelegram }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "No se pudo procesar contabilidad.");
  }
  return {
    results: payload.results || [],
    guiasSinAsignar: payload.guias_sin_asignar || [],
  };
};

providerSelect.addEventListener("change", () => {
  renderResults([], providerSelect.value);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const packages = normalizePackages(packagesInput.value);
  const provider = providerSelect.value;
  const sendTelegram = Boolean(sendTelegramCheckbox?.checked);

  if (!packages.length) {
    setStatus("Debes ingresar al menos un paquete.");
    return;
  }

  submitButton.disabled = true;
  setStatus("Procesando contabilidad...");

  try {
    const { results, guiasSinAsignar } = await processContabilidad(packages, provider, sendTelegram);
    renderResults(results, provider);
    renderUnassignedGuides(guiasSinAsignar);
    setStatus("Proceso finalizado.");
  } catch (error) {
    setStatus(error.message);
  } finally {
    submitButton.disabled = false;
  }
});

renderResults([], providerSelect.value);
renderUnassignedGuides([]);