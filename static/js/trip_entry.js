// Autosave: debounce-submits a form in the background so switching tabs or
// navigating away mid-entry doesn't lose typed-in quantities/collections.
// Backend routes recognize autosave=1 and skip the flash+redirect a real
// button click gets, since a flash message per keystroke would spam the UI.
let pendingAutosaveCount = 0;

function setupAutosave(form) {
  if (!form) return;

  const status = document.createElement("span");
  status.className = "autosave-status text-muted small ms-2";
  const submitBtn = form.querySelector("button[type=submit]");
  if (submitBtn) submitBtn.insertAdjacentElement("afterend", status);

  let timer = null;

  function doSave() {
    const data = new FormData(form);
    data.set("autosave", "1");
    status.textContent = "Saving…";
    fetch(form.action, { method: "POST", body: data, credentials: "same-origin" })
      .then((resp) => {
        status.textContent = resp.ok ? "All changes saved" : "Save failed — use the Save button";
      })
      .catch(() => {
        status.textContent = "Save failed — use the Save button";
      })
      .finally(() => {
        if (pendingAutosaveCount > 0) pendingAutosaveCount -= 1;
      });
  }

  function scheduleSave() {
    status.textContent = "Unsaved changes…";
    pendingAutosaveCount += 1;
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      doSave();
    }, 1000);
  }

  form.addEventListener("input", scheduleSave);
  form.addEventListener("change", scheduleSave);

  // Flush immediately if the tab/window is hidden before the debounce fires
  // (switching tabs, minimizing, or closing) instead of waiting it out.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && timer) {
      clearTimeout(timer);
      timer = null;
      doSave();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupAutosave(document.getElementById("dispatchForm"));
  setupAutosave(document.getElementById("salesForm"));
  setupAutosave(document.getElementById("returnsForm"));

  window.addEventListener("beforeunload", (e) => {
    if (pendingAutosaveCount > 0) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
});

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
    const pending = totalAmount - collected;
    row.querySelector(".row-total-amount").textContent = "₹" + totalAmount.toFixed(2);
    const pendingCell = row.querySelector(".row-total-pending");
    if (pending < 0) {
      pendingCell.textContent = "Paid in full (+₹" + (-pending).toFixed(2) + " credited to balance)";
      pendingCell.classList.remove("balance-positive");
    } else {
      pendingCell.textContent = "₹" + pending.toFixed(2);
      pendingCell.classList.toggle("balance-positive", pending > 0);
    }
  }

  table.querySelectorAll("tbody tr").forEach((row) => {
    row.querySelectorAll(".qty-input, .store-collected-input").forEach((input) => {
      input.addEventListener("input", () => updateRowTotals(row));
    });

    const paidBtn = row.querySelector(".mark-paid-btn");
    const collectedInput = row.querySelector(".store-collected-input");
    if (paidBtn && collectedInput) {
      paidBtn.addEventListener("click", () => {
        let totalAmount = 0;
        row.querySelectorAll(".qty-input").forEach((qtyInput) => {
          const price = parseFloat(qtyInput.dataset.price || "0");
          const qty = parseFloat(qtyInput.value || "0");
          totalAmount += qty * price;
        });
        collectedInput.value = totalAmount.toFixed(2);
        collectedInput.dispatchEvent(new Event("input"));
      });
    }
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
    const damagedInput = row.querySelector(".qty-damaged-input");

    if (returnedInput) {
      returnedInput.addEventListener("input", () => updateReturnRow(row));
    }
    if (returnedInput && damagedInput) {
      const syncDamagedMax = () => {
        damagedInput.max = returnedInput.value || "0";
      };
      syncDamagedMax();
      returnedInput.addEventListener("input", syncDamagedMax);
    }
  });
});
