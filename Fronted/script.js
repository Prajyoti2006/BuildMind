const errorLog = document.getElementById("errorLog");
const analyzeBtn = document.getElementById("analyzeBtn");
const clearBtn = document.getElementById("clearBtn");
const result = document.getElementById("result");

let analysisCount = 0;
const HISTORY_KEY = "buildmind_analysis_history_v1";

function getHistory() {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); }
    catch (_) { return []; }
}

function saveHistory(item) {
    const history = getHistory();
    history.unshift(item);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 30)));
    renderHistory();
}

function renderHistory() {
    const history = getHistory();
    const rows = document.getElementById("historyRows");
    if (!rows) return;
    document.getElementById("historyCount").textContent = history.length;
    document.getElementById("successCount").textContent = history.filter(x => /success|passed|complete/i.test(x.cause + " " + x.logs)).length;
    document.getElementById("failureCount").textContent = history.filter(x => /fail|error|exception/i.test(x.cause + " " + x.logs)).length;
    rows.innerHTML = "";
    if (!history.length) {
        rows.innerHTML = '<tr><td colspan="3">No reports yet. Analyze a log first.</td></tr>';
        return;
    }
    history.forEach(item => {
        const tr = document.createElement("tr");
        [item.date, item.cause, item.fix].forEach(value => {
            const td = document.createElement("td");
            td.textContent = value || "—";
            tr.appendChild(td);
        });
        rows.appendChild(tr);
    });
}


async function analyzeBuild() {
    const logs = errorLog.value.trim();

    if (!logs) {
        errorLog.focus();
        errorLog.placeholder = "Please paste your Jenkins error logs first.";
        return;
    }

    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Analyzing logs...";
    result.hidden = true;

    try {
        const response = await fetch("http://127.0.0.1:5000/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ logs })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Analysis failed.");
        }

        document.getElementById("causeText").textContent =
            data.cause || "The root cause could not be identified.";

        document.getElementById("fixText").textContent =
            data.suggested_fix || data.fix ||
            "Review the original Jenkins console output.";

        const evidence = Array.isArray(data.evidence)
            ? data.evidence
            : [];

        document.getElementById("evidenceText").textContent =
            evidence.length
                ? evidence.join("\n")
                : "No specific error lines were identified. Review the original Jenkins log.";

        document.getElementById("modeText").textContent =
            data.mode === "ai"
                ? "AI-powered analysis"
                : "Rule-based analysis · Demo mode";

        analysisCount++;
        document.getElementById("analysisCount").textContent = analysisCount;

        result.hidden = false;
        saveHistory({
            date: new Date().toLocaleString(),
            cause: data.cause || "Cause not identified",
            fix: data.suggested_fix || data.fix || "Review the original log",
            logs: logs.slice(0, 1200)
        });

        result.scrollIntoView({
            behavior: "smooth",
            block: "nearest"
        });

    } catch (error) {
        alert(
            "Could not connect to BuildMind backend.\n\n" +
            "Check that the Python server is running at " +
            "http://127.0.0.1:5000\n\n" +
            "Details: " + error.message
        );
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "✦  Analyze Logs  →";
    }
}

analyzeBtn.addEventListener("click", analyzeBuild);

clearBtn.addEventListener("click", () => {
    errorLog.value = "";
    result.hidden = true;
    errorLog.focus();
});

document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
        document.querySelectorAll(".nav-item").forEach(nav => nav.classList.remove("active"));
        item.classList.add("active");
    });
});

const clearHistoryBtn = document.getElementById("clearHistoryBtn");
if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener("click", () => {
        localStorage.removeItem(HISTORY_KEY);
        renderHistory();
    });
}

const knowledgeSearch = document.getElementById("knowledgeSearch");
if (knowledgeSearch) {
    knowledgeSearch.addEventListener("input", () => {
        const query = knowledgeSearch.value.toLowerCase();
        document.querySelectorAll(".knowledge-card").forEach(card => {
            card.hidden = !card.textContent.toLowerCase().includes(query);
        });
    });
}

renderHistory();
