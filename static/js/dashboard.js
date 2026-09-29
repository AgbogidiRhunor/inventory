function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
}

const csrftoken = getCookie("csrftoken");

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".counter-btn").forEach((btn) => {
        btn.addEventListener("click", handleCounterClick);
    });
});

async function handleCounterClick(event) {
    const btn = event.currentTarget;
    const card = btn.closest(".product-card");
    const productId = card.dataset.productId;
    const action = btn.dataset.action; // "stock" or "sold"
    const direction = btn.dataset.direction; // "increase" or "decrease"

    const url = action === "stock"
        ? `/product/${productId}/stock/`
        : `/product/${productId}/sold/`;

    setButtonsDisabled(card, true);

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrftoken,
            },
            body: JSON.stringify({ direction }),
        });

        const data = await response.json();

        if (!response.ok) {
            showInlineError(card, data.error || "Something went wrong.");
            return;
        }

        card.querySelector('[data-role="quantity"]').textContent = data.quantity;
        card.querySelector('[data-role="quantity_sold"]').textContent = data.quantity_sold;
    } catch (err) {
        showInlineError(card, "Network error. Please try again.");
    } finally {
        setButtonsDisabled(card, false);
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
