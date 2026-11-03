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

    initSearch();
    initMessages();
});

// ---------- Flash messages ----------
// Success/error messages ("Item updated successfully.") fade out on their own.
const MESSAGE_DISPLAY_MS = 6000;

function initMessages() {
    const container = document.querySelector(".messages");
    if (!container) return;
    container.querySelectorAll(".message").forEach((message) => {
        setTimeout(() => dismissMessage(message, container), MESSAGE_DISPLAY_MS);
    });
}

function dismissMessage(message, container) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const fadeMs = reduceMotion ? 0 : 400;

    // Is this the last message left on screen? Then the container's own
    // bottom margin should collapse too, so the page doesn't jump afterwards.
    message.dataset.dismissing = "1";
    const isLast = Array.from(container.querySelectorAll(".message")).every(
        (m) => m.dataset.dismissing
    );

    // Pin the current height so it can animate down to zero.
    message.style.boxSizing = "border-box";
    message.style.height = `${message.offsetHeight}px`;
    message.style.overflow = "hidden";
    const transition = ["opacity", "height", "margin", "padding", "border-width"]
        .map((prop) => `${prop} ${fadeMs}ms ease`)
        .join(", ");
    message.style.transition = transition;
    if (isLast) {
        container.style.transition = `margin-bottom ${fadeMs}ms ease`;
    }
    void message.offsetHeight; // apply the starting values before animating

    message.style.opacity = "0";
    message.style.height = "0";
    message.style.marginTop = "0";
    message.style.marginBottom = "0";
    message.style.paddingTop = "0";
    message.style.paddingBottom = "0";
    message.style.borderWidth = "0";
    if (isLast) container.style.marginBottom = "0";

    setTimeout(() => {
        message.remove();
        if (!container.querySelector(".message")) container.remove();
    }, fadeMs + 50);
}

// ---------- Search ----------
// Lowercase and strip accents so "creole" also finds "Créole".
function normalizeText(text) {
    return (text || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim();
}

function initSearch() {
    const input = document.getElementById("product-search");
    if (!input) return; // no products yet, so no search bar

    const emptyMessage = document.getElementById("no-results");
    const emptyTerm = document.getElementById("no-results-term");
    const items = Array.from(document.querySelectorAll(".product-card")).map((card) => ({
        card,
        name: normalizeText(card.dataset.name),
    }));

    function applyFilter() {
        const query = normalizeText(input.value);
        let visible = 0;
        items.forEach(({ card, name }) => {
            const match = !query || name.includes(query);
            card.hidden = !match;
            if (match) visible += 1;
        });
        emptyTerm.textContent = input.value.trim();
        emptyMessage.hidden = visible > 0;
    }

    input.addEventListener("input", applyFilter);
    input.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && input.value) {
            input.value = "";
            applyFilter();
        }
    });
}

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