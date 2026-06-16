const form = document.getElementById("correo-form");
const codesInput = document.getElementById("codes");
const statusText = document.getElementById("status-text");
const downloadButton = document.getElementById("download-excel");
const submitButton = form.querySelector("button.primary");
const API_BASE = window.location.origin || "http://127.0.0.1:8002";

const setStatus = (message) => {
  statusText.textContent = message;
};

const normalizeCodes = (raw) =>
  raw
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);

const requestExcel = async (codes) => {
  const response = await fetch(`${API_BASE}/api/correo/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ codes }),
  });

  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "No se pudo generar el Excel.");
  return payload;
};

const downloadExcel = async () => {
  const response = await fetch(`${API_BASE}/api/correo/download`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.error || "No se pudo descargar.");
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "FORMATO DE NOVEDADES SAC.xlsx";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const codes = normalizeCodes(codesInput.value);

  if (!codes.length) {
    setStatus("Ingresa al menos un código.");
    return;
  }

  setStatus("Generando Excel...");
  submitButton.disabled = true;

  try {
    await requestExcel(codes);
    setStatus("Excel generado. Ya puedes descargarlo.");
  } catch (error) {
    setStatus(error.message);
  } finally {
    submitButton.disabled = false;
  }
});

downloadButton.addEventListener("click", async () => {
  try {
    await downloadExcel();
  } catch (error) {
    setStatus(error.message);
  }
});