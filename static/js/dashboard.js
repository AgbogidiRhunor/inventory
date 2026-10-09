function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
}

const csrftoken = getCookie("csrftoken");

let pendingSaleCard = null; // card the open sale dialog belongs to

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".counter-btn").forEach((btn) => {
        btn.addEventListener("click", handleCounterClick);
    });

    const dialog = document.getElementById("sale-dialog");
    const form = document.getElementById("sale-form");
    document.getElementById("sale-cancel").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
        pendingSaleCard = null;
    });
    form.addEventListener("submit", handleSaleSubmit);
});

function endpointFor(card, action) {
    const id = card.dataset.productId;
    return action === "stock" ? `/product/${id}/stock/` : `/product/${id}/sold/`;
}

async function postJSON(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken,
        },
        body: JSON.stringify(payload),
    });
    let data = {};
    try {
        data = await response.json();
    } catch (e) {
        /* non-JSON error page */
    }
    return { ok: response.ok, data };
}

function applyState(card, data) {
    card.querySelector('[data-role="quantity"]').textContent = data.quantity;
    card.querySelector('[data-role="quantity_sold"]').textContent = data.quantity_sold;
    const revenue = card.querySelector('[data-role="revenue"]');
    if (revenue && data.revenue !== undefined) revenue.textContent = data.revenue;
}

async function handleCounterClick(event) {
    const btn = event.currentTarget;
    const card = btn.closest(".product-card");
    const action = btn.dataset.action; // "stock" or "sold"
    const direction = btn.dataset.direction; // "increase" or "decrease"

    // Recording a sale needs a price first, so ask for it.
    if (action === "sold" && direction === "increase") {
        const available = parseInt(card.querySelector('[data-role="quantity"]').textContent, 10);
        if (available <= 0) {
            showInlineError(card, "Cannot record a sale: no stock available.");
            return;
        }
        openSaleDialog(card);
        return;
    }

    setButtonsDisabled(card, true);
    try {
        const { ok, data } = await postJSON(endpointFor(card, action), { direction });
        if (!ok) {
            showInlineError(card, data.error || "Something went wrong.");
            return;
        }
        applyState(card, data);
    } catch (err) {
        showInlineError(card, "Network error. Please try again.");
    } finally {
        setButtonsDisabled(card, false);
    }
}

function openSaleDialog(card) {
    pendingSaleCard = card;
    document.getElementById("sale-dialog-item").textContent = card.dataset.name;
    const input = document.getElementById("sale-price");
    input.value = card.dataset.price; // default to the item's initial price
    setDialogError("");
    document.getElementById("sale-dialog").showModal();
    input.focus();
    input.select();
}

function setDialogError(message) {
    const el = document.getElementById("sale-dialog-error");
    el.textContent = message;
    el.hidden = !message;
}

async function handleSaleSubmit(event) {
    event.preventDefault();
    const card = pendingSaleCard;
    if (!card) return;

    const price = document.getElementById("sale-price").value;
    const confirmBtn = document.getElementById("sale-confirm");
    confirmBtn.disabled = true;
    setDialogError("");

    try {
        const { ok, data } = await postJSON(endpointFor(card, "sold"), {
            direction: "increase",
            price,
        });
        if (!ok) {
            setDialogError(data.error || "Something went wrong.");
            return;
        }
        applyState(card, data);
        document.getElementById("sale-dialog").close();
    } catch (err) {
        setDialogError("Network error. Please try again.");
    } finally {
        confirmBtn.disabled = false;
    }
}

function setButtonsDisabled(card, disabled) {
    card.querySelectorAll(".counter-btn").forEach((b) => (b.disabled = disabled));
}

function showInlineError(card, message) {
    let el = card.querySelector(".card-inline-error");
    if (!el) {
        el = document.createElement("p");
        el.className = "card-inline-error field-error";
        card.querySelector(".product-body").appendChild(el);
    }
    el.textContent = message;
    setTimeout(() => el.remove(), 3000);
}
