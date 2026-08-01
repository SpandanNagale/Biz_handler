document.addEventListener("DOMContentLoaded", () => {
  const table = document.getElementById("salesTable");
  if (!table) return;

  function updatePendingCell(row) {
    row.querySelectorAll(".qty-input").forEach((qtyInput) => {
      const cell = qtyInput.closest("td");
      const collectedInput = cell.nextElementSibling.querySelector(".collected-input");
      const pendingCell = collectedInput.closest("td").nextElementSibling;

      const price = parseFloat(qtyInput.dataset.price || "0");
      const qty = parseFloat(qtyInput.value || "0");
      const collected = parseFloat(collectedInput.value || "0");

      if (!qtyInput.value) {
        pendingCell.textContent = "";
        return;
      }
      const amount = qty * price;
      const pending = amount - collected;
      pendingCell.textContent = pending.toFixed(2);
    });
  }

  table.querySelectorAll("tbody tr").forEach((row) => {
    row.querySelectorAll(".qty-input, .collected-input").forEach((input) => {
      input.addEventListener("input", () => updatePendingCell(row));
    });
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const table = document.getElementById("returnsTable");
  if (!table) return;

  function updateReturnRow(row) {
    const returnedInput = row.querySelector(".qty-returned-input");
    const sentCell = row.querySelector(".qty-sent-cell");
    const soldCell = row.querySelector(".qty-sold-cell");
    const valueCell = row.querySelector(".sale-value-cell");

    const sent = parseFloat(sentCell.dataset.qtySent || "0");
    const price = parseFloat(returnedInput.dataset.price || "0");

    if (!returnedInput.value) {
      soldCell.textContent = "";
      valueCell.textContent = "";
      return;
    }
    const returned = parseFloat(returnedInput.value || "0");
    const sold = sent - returned;
    soldCell.textContent = sold;
    valueCell.textContent = (sold * price).toFixed(2);
  }

  table.querySelectorAll("tbody tr").forEach((row) => {
    const returnedInput = row.querySelector(".qty-returned-input");
    if (returnedInput) {
      returnedInput.addEventListener("input", () => updateReturnRow(row));
    }
  });
});
