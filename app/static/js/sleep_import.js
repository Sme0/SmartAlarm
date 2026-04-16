const parseBtn = document.getElementById("parseBtn");
const fileInput = document.getElementById("xmlFile");
const statusEl = document.getElementById("status");
const loadingWrapEl = document.getElementById("loadingWrap");
const loadingTitleEl = document.getElementById("loadingTitle");
const progressTrackEl = document.getElementById("progressTrack");
const progressBarEl = document.getElementById("progressBar");
const progressLabelEl = document.getElementById("progressLabel");
const importedRangeLabelEl = document.getElementById("importedRangeLabel");

let isImporting = false;

function setStatus(message, isError = false) {
    statusEl.textContent = message;
    statusEl.className = isError
        ? "mt-4 rounded-lg border px-3 py-2 text-sm bg-red-50 border-red-200 text-red-800"
        : "mt-4 rounded-lg border px-3 py-2 text-sm bg-slate-50 border-slate-200 text-slate-800";
    statusEl.classList.remove("hidden");
}

function setLoadingMessage(title) {
    if (loadingTitleEl) loadingTitleEl.textContent = title;
}

function setProgress(percent, label = null) {
    const safePercent = Math.max(0, Math.min(100, Math.round(percent)));
    if (progressBarEl) progressBarEl.style.width = `${safePercent}%`;
    if (progressTrackEl) {
        progressTrackEl.setAttribute("aria-valuenow", String(safePercent));
        progressTrackEl.setAttribute("aria-valuetext", `${safePercent}%`);
    }
    if (progressLabelEl) {
        progressLabelEl.textContent = label || `${safePercent}% complete`;
    }
}

function setParsingState(isParsing, title = "Processing upload...") {
    isImporting = isParsing;
    loadingWrapEl.classList.toggle("hidden", !isParsing);
    if (isParsing) {
        // Keep a single active message source during import.
        statusEl.classList.add("hidden");
    }
    parseBtn.disabled = isParsing;
    fileInput.disabled = isParsing;
    if (isParsing) {
        setLoadingMessage(title);
    } else {
        setProgress(0, "0% complete");
    }
}

function formatImportedRangeValue(value) {
    if (!value) return null;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed.toLocaleString();
}

window.addEventListener("beforeunload", (event) => {
    if (!isImporting) return;
    event.preventDefault();
    event.returnValue = "Upload in progress. Leaving now may cancel the import.";
});

if (!parseBtn || !fileInput || !statusEl || !loadingWrapEl) {
    console.error("App init failed: expected DOM elements were not found.");
} else {
parseBtn.addEventListener("click", async () => {
    const file = fileInput.files?.[0];


    if (!file) {
        setStatus("Please choose an XML file first.", true);
        return;
    }

    try {
        statusEl.classList.add("hidden");
        setParsingState(true, "Parsing XML file...");
        setProgress(10, "Preparing import");

        const rows = await parseSleepXML(file);
        setProgress(45, `Parsed ${rows.length} record(s)`);
        setLoadingMessage("Uploading sleep data...");

        const response = await fetch('/sleep-data/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                sleep_data: rows
            })
        });

        setProgress(80, "Upload finished");

        setLoadingMessage("Finalizing import...");

        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.response !== 'ok') {
            const message = data.message || `Upload failed (${response.status})`;
            throw new Error(message);
        }

        setProgress(100, "Import successful");
        setStatus('Sleep data uploaded successfully.');

        if (importedRangeLabelEl) {
            const start = formatImportedRangeValue(data.imported_range_start);
            const end = formatImportedRangeValue(data.imported_range_end);
            importedRangeLabelEl.textContent = (start && end)
                ? `${start} to ${end}`
                : 'No sleep data imported yet.';
        }

    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setStatus(`Failed to import sleep data: ${message}`, true);
    } finally {
        setParsingState(false);
    }
});
}
