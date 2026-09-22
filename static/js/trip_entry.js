document.addEventListener("DOMContentLoaded", () => {
  const table = document.getElementById("salesTable");
  if (!table) return;

  function updateRowTotals(row) {
    let totalAmount = 0;
    row.querySelectorAll(".qty-input").forEach((qtyInput) => {
      const price = parseFloat(qtyInput.dataset.price || "0");
      const qty = parseFloat(qtyInput.value || "0");
      totalAmount += qty * price;
    });

    const collected = parseFloat(row.querySelector(".store-collected-input").value || "0");
    row.querySelector(".row-total-amount").textContent = "₹" + totalAmount.toFixed(2);
    row.querySelector(".row-total-pending").textContent = "₹" + (totalAmount - collected).toFixed(2);
  }

  table.querySelectorAll("tbody tr").forEach((row) => {
    row.querySelectorAll(".qty-input, .store-collected-input").forEach((input) => {
      input.addEventListener("input", () => updateRowTotals(row));
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
