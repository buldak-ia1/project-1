const statusChip = document.getElementById("statusChip");
const statusDetail = document.getElementById("statusDetail");
const runForm = document.getElementById("runForm");
const runButton = document.getElementById("runButton");
const reloadButton = document.getElementById("reloadButton");
const metricGrid = document.getElementById("metricGrid");
const classificationSummary = document.getElementById("classificationSummary");
const groupingSummary = document.getElementById("groupingSummary");
const manifestPreview = document.getElementById("manifestPreview");
const runLogPreview = document.getElementById("runLogPreview");
const reportTable = document.getElementById("reportTable");
const reportHead = reportTable.querySelector("thead");
const reportBody = reportTable.querySelector("tbody");
const reportEmpty = document.getElementById("reportEmpty");

const sourceRootInput = document.getElementById("sourceRoot");
const outputRootInput = document.getElementById("outputRoot");
const policyPathInput = document.getElementById("policyPath");
const executionModeInput = document.getElementById("executionMode");
const useDemoInputToggle = document.getElementById("useDemoInput");
const demoHint = document.getElementById("demoHint");
const modeDetail = document.getElementById("modeDetail");

sourceRootInput.value = "";
outputRootInput.value = "demo_output";
policyPathInput.value = "config/classification_policy.json";
executionModeInput.value = "analyze_only";

useDemoInputToggle.addEventListener("change", syncDemoState);
executionModeInput.addEventListener("change", () => {
  modeDetail.textContent = `현재 모드: ${labelExecutionMode(executionModeInput.value)}`;
});
syncDemoState();

runForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Running", "MetaSort 파이프라인을 실행하고 있습니다.");
  runButton.disabled = true;

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_root: sourceRootInput.value.trim(),
        output_root: outputRootInput.value.trim(),
        policy_path: policyPathInput.value.trim(),
        execution_mode: executionModeInput.value,
        use_demo_input: useDemoInputToggle.checked,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.message || "실행 중 오류가 발생했습니다.");
    }
    renderPayload(payload);
    setStatus("Completed", "실행이 끝났습니다. 결과와 리포트를 확인하세요.");
  } catch (error) {
    setStatus("Error", error.message);
  } finally {
    runButton.disabled = false;
  }
});

reloadButton.addEventListener("click", async () => {
  setStatus("Loading", "최근 결과를 불러오고 있습니다.");
  try {
    await loadState();
    setStatus("Ready", "최근 결과를 새로 불러왔습니다.");
  } catch (error) {
    setStatus("Error", error.message);
  }
});

async function loadState() {
  const response = await fetch("/api/state");
  const payload = await response.json();
  renderPayload(payload);
}

function renderPayload(payload) {
  const projectRun = payload.project_run;
  const summaryFile = payload.summary_file;
  const manifest = payload.manifest;
  const reportPreview = payload.report_preview || [];
  const runLogLines = payload.run_log_preview || [];

  const summary = projectRun?.summary || summaryFile?.summary || {};
  renderMetrics(summary, summaryFile);
  renderClassification(summary.classification?.by_criterion || {});
  renderGrouping(summary.grouping || {});
  manifestPreview.textContent = JSON.stringify(manifest || {}, null, 2);
  runLogPreview.textContent = runLogLines.length ? runLogLines.join("\n") : "run.log가 아직 없습니다.";
  renderReportTable(reportPreview);
  const activeMode = summary.organization?.execution_mode || projectRun?.policy?.execution_mode || executionModeInput.value;
  modeDetail.textContent = `현재 모드: ${labelExecutionMode(activeMode)}`;
}

function renderMetrics(summary, summaryFile) {
  const metrics = [
    { label: "Images", value: summaryFile?.image_count ?? summary.image_count ?? 0 },
    { label: "Groups", value: summaryFile?.group_count ?? summary.grouping?.group_count ?? 0 },
    { label: "Copied", value: summary.organization?.copied_files ?? 0 },
    { label: "Embeddings", value: summary.features?.extracted_embeddings ?? 0 },
  ];

  metricGrid.innerHTML = metrics.map((metric) => `
    <article class="metric-card">
      <span class="metric-label">${escapeHtml(metric.label)}</span>
      <strong class="metric-value">${escapeHtml(String(metric.value))}</strong>
    </article>
  `).join("");
}

function renderClassification(byCriterion) {
  const entries = Object.entries(byCriterion);
  if (!entries.length) {
    classificationSummary.innerHTML = "실행 후 표시됩니다.";
    classificationSummary.classList.add("empty-state");
    return;
  }
  classificationSummary.classList.remove("empty-state");
  classificationSummary.innerHTML = entries.map(([criterion, values]) => {
    const inline = Object.entries(values).map(([label, count]) => `${label}: ${count}`).join(" / ");
    return `<div><strong>${escapeHtml(criterion)}</strong><br>${escapeHtml(inline)}</div>`;
  }).join("");
}

function renderGrouping(grouping) {
  const entries = Object.entries(grouping).filter(([key]) => key !== "by_group_type");
  if (!entries.length) {
    groupingSummary.innerHTML = "실행 후 표시됩니다.";
    groupingSummary.classList.add("empty-state");
    return;
  }
  groupingSummary.classList.remove("empty-state");
  groupingSummary.innerHTML = entries.map(([label, value]) =>
    `<div><strong>${escapeHtml(label)}</strong><br>${escapeHtml(String(value))}</div>`
  ).join("");
}

function renderReportTable(rows) {
  if (!rows.length) {
    reportHead.innerHTML = "";
    reportBody.innerHTML = "";
    reportEmpty.style.display = "block";
    return;
  }

  reportEmpty.style.display = "none";
  const columns = Object.keys(rows[0]);
  reportHead.innerHTML = `<tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>`;
  reportBody.innerHTML = rows.map((row) => `
    <tr>${columns.map((column) => `<td>${escapeHtml(row[column] ?? "")}</td>`).join("")}</tr>
  `).join("");
}

function setStatus(state, detail) {
  statusChip.textContent = state;
  statusDetail.textContent = detail;
}

function syncDemoState() {
  const isDemoMode = useDemoInputToggle.checked;
  sourceRootInput.disabled = isDemoMode;
  sourceRootInput.placeholder = isDemoMode ? "demo_input 고정 사용" : "예: D:\\Images";
  demoHint.textContent = isDemoMode
    ? "데모 모드에서는 프로젝트 내부 demo_input만 재생성합니다. 입력한 Source Root는 사용하지 않습니다."
    : "실제 폴더를 사용할 때는 Source Root와 Output Root를 서로 다른 위치로 지정하세요.";
}

function labelExecutionMode(mode) {
  if (mode === "copy") {
    return "복사";
  }
  return "분석 전용";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

loadState().then(() => {
  setStatus("Ready", "최근 결과를 불러왔습니다.");
}).catch(() => {
  setStatus("Idle", "아직 실행되지 않았습니다.");
});
