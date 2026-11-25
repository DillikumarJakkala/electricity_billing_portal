document.addEventListener("DOMContentLoaded", function () {
    const fromInput = document.getElementById("id_period_from");
    const toInput = document.getElementById("id_period_to");
    const daysInput = document.getElementById("id_no_of_days");

    if (!fromInput || !toInput || !daysInput) return;

    function updateDays() {
        if (!fromInput.value || !toInput.value) {
            daysInput.value = 0;
            return;
        }
        const start = new Date(fromInput.value + "T00:00:00");
        const end = new Date(toInput.value + "T00:00:00");
        if (isNaN(start.getTime()) || isNaN(end.getTime()) || end < start) {
            daysInput.value = 0;
            return;
        }
        const diffDays = Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
        daysInput.value = diffDays;
    }

    fromInput.addEventListener("change", updateDays);
    toInput.addEventListener("change", updateDays);
    updateDays();
});