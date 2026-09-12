document.addEventListener("DOMContentLoaded", () => {
    const subjectSelect = document.getElementById("aiSubject");
    const topicSelect = document.getElementById("aiTopic");
    const quantitySelect = document.getElementById("aiQuantity");
    const generateButton = document.getElementById("aiGenerateBtn");
    const errorPanel = document.getElementById("aiError");
    const loadingPanel = document.getElementById("aiLoading");
    const resultPanel = document.getElementById("aiResult");
    const resultCount = document.getElementById("aiResultCount");

    document.querySelectorAll("[data-auto-submit]").forEach((select) => {
        select.addEventListener("change", () => select.form.submit());
    });

    if (!subjectSelect || !topicSelect || !quantitySelect || !generateButton) {
        return;
    }

    const setError = (message) => {
        errorPanel.textContent = message;
        errorPanel.classList.remove("d-none");
    };

    const clearMessages = () => {
        errorPanel.textContent = "";
        errorPanel.classList.add("d-none");
        resultPanel.classList.add("d-none");
    };

    const updateTopics = () => {
        const subjectId = subjectSelect.value;
        const options = topicSelect.querySelectorAll("option[data-subject-id]");
        topicSelect.value = "";
        options.forEach((option) => {
            option.hidden = Boolean(subjectId) && option.dataset.subjectId !== subjectId;
        });
    };

    subjectSelect.addEventListener("change", updateTopics);
    updateTopics();

    generateButton.addEventListener("click", async () => {
        const subjectId = Number.parseInt(subjectSelect.value, 10);
        const quantity = Number.parseInt(quantitySelect.value, 10);
        const topicId = topicSelect.value ? Number.parseInt(topicSelect.value, 10) : null;

        if (!Number.isInteger(subjectId) || subjectId <= 0) {
            setError("Selecione uma matéria.");
            return;
        }

        clearMessages();
        loadingPanel.classList.remove("d-none");
        generateButton.disabled = true;

        try {
            const response = await fetch(generateButton.dataset.endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": generateButton.dataset.csrfToken,
                },
                body: JSON.stringify({
                    subject_id: subjectId,
                    topic_id: topicId,
                    quantidade: quantity,
                }),
            });

            let payload;
            try {
                payload = await response.json();
            } catch (error) {
                payload = { success: false, error: "Resposta inválida do servidor." };
            }

            if (!response.ok || !payload.success || !payload.count) {
                setError(payload.error || "Erro ao gerar questões.");
                return;
            }

            resultCount.textContent = payload.count;
            resultPanel.classList.remove("d-none");
            window.setTimeout(() => window.location.reload(), 1500);
        } catch (error) {
            setError("Erro de conexão. Verifique sua conexão e tente novamente.");
        } finally {
            loadingPanel.classList.add("d-none");
            generateButton.disabled = false;
        }
    });
});
