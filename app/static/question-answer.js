document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-question-answer-form]");
    const timer = document.querySelector("[data-answer-timer]");
    const timeInput = document.getElementById("answerTime");

    if (!form || !timer || !timeInput) {
        return;
    }

    const startedAt = Date.now();
    const formatTime = (seconds) => {
        const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
        const remainder = (seconds % 60).toString().padStart(2, "0");
        return `${minutes}:${remainder}`;
    };

    const updateTimer = () => {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000);
        timer.textContent = formatTime(elapsed);
        timeInput.value = elapsed;
    };

    updateTimer();
    const interval = window.setInterval(updateTimer, 1000);
    form.addEventListener("submit", (event) => {
        // Evita duplo envio sem desabilitar os radios: controles disabled
        // não são incluídos no POST e causavam "Formulário inválido".
        if (form.dataset.submitted === "1") {
            event.preventDefault();
            return;
        }
        form.dataset.submitted = "1";
        updateTimer();
        window.clearInterval(interval);
        // Desabilita apenas o botão de envio (button ou input type=submit).
        form.querySelectorAll("button[type='submit'], input[type='submit']").forEach((element) => {
            element.disabled = true;
        });
    });
});
