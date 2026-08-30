document.addEventListener("DOMContentLoaded", () => {
    const chartsDataNode = document.getElementById("dashboard-charts-data");
    if (!chartsDataNode || !window.Chart) {
        return;
    }

    const charts = JSON.parse(chartsDataNode.textContent || "{}");
    const styles = getComputedStyle(document.body);
    const textColor = styles.getPropertyValue("--muted-strong").trim() || "#c3d2ea";
    const gridColor = styles.getPropertyValue("--grid").trim() || "rgba(148, 163, 184, 0.12)";
    const primary = styles.getPropertyValue("--primary").trim() || "#5ba4ff";
    const success = styles.getPropertyValue("--success").trim() || "#3dd68c";

    Chart.defaults.color = textColor;
    Chart.defaults.borderColor = gridColor;
    Chart.defaults.font.family = '"Segoe UI", Tahoma, Arial, sans-serif';

    const makeBar = (canvasId, labels, datasets, maxY) => {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !labels || !labels.length) {
            return;
        }
        new Chart(canvas, {
            type: "bar",
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: datasets.length > 1 } },
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        beginAtZero: true,
                        max: maxY,
                        grid: { color: gridColor },
                    },
                },
            },
        });
    };

    const hours = charts.hoursPerWeek || {};
    makeBar("chartHoursWeek", hours.labels, [
        { label: "Planejado", data: hours.planned || [], backgroundColor: primary, borderRadius: 6 },
        { label: "Concluído", data: hours.completed || [], backgroundColor: success, borderRadius: 6 },
    ]);

    const bySubject = charts.timeBySubject || {};
    const subjectCanvas = document.getElementById("chartTimeSubject");
    if (subjectCanvas && (bySubject.labels || []).length) {
        new Chart(subjectCanvas, {
            type: "doughnut",
            data: {
                labels: bySubject.labels,
                datasets: [{
                    data: bySubject.minutes,
                    backgroundColor: bySubject.colors,
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
            },
        });
    }

    const area = charts.progressByArea || {};
    makeBar("chartAreaProgress", area.labels, [
        { label: "Conclusão (%)", data: area.percent || [], backgroundColor: primary, borderRadius: 6 },
    ], 100);

    const evolution = charts.evolution || {};
    const evolutionCanvas = document.getElementById("chartEvolution");
    if (evolutionCanvas && (evolution.labels || []).length) {
        new Chart(evolutionCanvas, {
            type: "line",
            data: {
                labels: evolution.labels,
                datasets: [{
                    label: "Conclusão (%)",
                    data: evolution.values || [],
                    borderColor: primary,
                    backgroundColor: "rgba(91, 164, 255, 0.18)",
                    fill: true,
                    tension: 0.35,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, max: 100, grid: { color: gridColor } },
                    x: { grid: { display: false } },
                },
            },
        });
    }
});
