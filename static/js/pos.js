/* Punto de Venta en Mesón — Vivero Leufucades (HU POS). Sin dependencias. */
(function () {
    'use strict';
    const searchInput = document.getElementById('pos-search-input');
    const clearSearchBtn = document.getElementById('pos-search-clear');
    const visibleCountEl = document.getElementById('pos-visible-count');
    const noResultsEl = document.getElementById('pos-no-results');
    const productCards = Array.from(document.querySelectorAll('.pos-product-card'));

    const cartEmptyEl = document.getElementById('pos-cart-empty');
    const cartListEl = document.getElementById('pos-cart-list');
    const clearCartBtn = document.getElementById('pos-clear-cart');
    const clientAlertEl = document.getElementById('pos-client-alert');
    const itemsJsonInput = document.getElementById('pos-items-json');
    const hiddenInputsContainer = document.getElementById('pos-hidden-inputs');
    const checkoutForm = document.getElementById('pos-checkout-form');
    const submitBtn = document.getElementById('pos-submit-btn');

    const totalNetoEl = document.getElementById('pos-total-neto');
    const montoIvaEl = document.getElementById('pos-monto-iva');
    const totalBrutoEl = document.getElementById('pos-total-bruto');

    if (!searchInput || !checkoutForm || !submitBtn) return;

    const catalogMap = new Map();
    productCards.forEach(function (card) {
        const id = parseInt(card.dataset.id, 10);
        catalogMap.set(id, {
            id: id,
            sku: card.dataset.skuDisplay || '',
            nombre: card.dataset.nombreDisplay || '',
            precio: parseInt(card.dataset.precio, 10) || 0,
            stock: parseInt(card.dataset.stock, 10) || 0
        });
    });

    const cart = new Map();

    function formatCLP(amount) {
        const num = Math.round(Number(amount) || 0);
        return '$' + num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    function showAlert(msg) {
        if (!msg) {
            clientAlertEl.textContent = '';
            clientAlertEl.classList.add('hidden');
            return;
        }
        clientAlertEl.textContent = msg;
        clientAlertEl.classList.remove('hidden');
    }

    function filterProducts() {
        const q = (searchInput.value || '').trim().toLowerCase();
        let visibles = 0;

        productCards.forEach(function (card) {
            const sku = card.dataset.sku || '';
            const nombre = card.dataset.nombre || '';
            const match = !q || sku.includes(q) || nombre.includes(q);
            if (match) {
                card.classList.remove('hidden');
                visibles += 1;
            } else {
                card.classList.add('hidden');
            }
        });

        visibleCountEl.textContent = String(visibles);
        if (q) {
            clearSearchBtn.classList.remove('hidden');
        } else {
            clearSearchBtn.classList.add('hidden');
        }

        if (productCards.length > 0 && visibles === 0) {
            noResultsEl.classList.remove('hidden');
        } else {
            noResultsEl.classList.add('hidden');
        }
    }

    function updateCartQuantity(id, delta) {
        const prod = catalogMap.get(id);
        if (!prod || prod.stock <= 0) {
            return;
        }
        const actual = cart.get(id) || 0;
        const nuevo = actual + delta;

        if (nuevo > prod.stock) {
            showAlert('Stock máximo alcanzado para "' + prod.nombre + '" (' + prod.stock + ' un. disponibles).');
            return;
        }
        showAlert('');

        if (nuevo <= 0) {
            cart.delete(id);
        } else {
            cart.set(id, nuevo);
        }
        renderCart();
    }

    function renderCart() {
        cartListEl.innerHTML = '';
        hiddenInputsContainer.innerHTML = '';

        let totalBruto = 0;
        const payload = [];

        cart.forEach(function (cantidad, id) {
            const prod = catalogMap.get(id);
            if (!prod) return;

            const subtotal = prod.precio * cantidad;
            totalBruto += subtotal;
            payload.push({ id_producto: id, cantidad: cantidad });

            const inputId = document.createElement('input');
            inputId.type = 'hidden';
            inputId.name = 'id_producto';
            inputId.value = String(id);
            hiddenInputsContainer.appendChild(inputId);

            const inputCant = document.createElement('input');
            inputCant.type = 'hidden';
            inputCant.name = 'cantidad';
            inputCant.value = String(cantidad);
            hiddenInputsContainer.appendChild(inputCant);

            const li = document.createElement('li');
            li.className = 'py-3 flex items-center justify-between gap-3';
            li.innerHTML =
                '<div class="min-w-0 flex-1">' +
                    '<p class="text-sm font-semibold text-[#1F2933] truncate">' + prod.nombre + '</p>' +
                    '<p class="text-xs text-[#52606D]">' +
                        '<span class="font-mono">' + prod.sku + '</span> &middot; ' +
                        formatCLP(prod.precio) + ' c/u (máx. ' + prod.stock + ')' +
                    '</p>' +
                '</div>' +
                '<div class="flex items-center gap-1.5 shrink-0">' +
                    '<button type="button" data-action="dec" data-id="' + id + '" ' +
                        'class="min-h-[44px] min-w-[44px] rounded-lg border border-[#E2E8E4] bg-[#F9FAF8] hover:bg-[#E2E8E4] text-base font-bold text-[#1F2933] focus:outline-none focus:ring-2 focus:ring-[#1B4332]" ' +
                        'aria-label="Disminuir cantidad">-</button>' +
                    '<span class="w-8 text-center text-sm font-bold text-[#1F2933]">' + cantidad + '</span>' +
                    '<button type="button" data-action="inc" data-id="' + id + '" ' +
                        'class="min-h-[44px] min-w-[44px] rounded-lg border border-[#E2E8E4] bg-[#F9FAF8] hover:bg-[#E2E8E4] text-base font-bold text-[#1F2933] focus:outline-none focus:ring-2 focus:ring-[#1B4332]" ' +
                        'aria-label="Aumentar cantidad">+</button>' +
                '</div>' +
                '<div class="text-right min-w-[82px] shrink-0">' +
                    '<span class="block text-sm font-bold text-[#1B4332]">' + formatCLP(subtotal) + '</span>' +
                    '<button type="button" data-action="del" data-id="' + id + '" ' +
                        'class="text-[11px] font-medium text-[#991B1B] hover:underline focus:outline-none">Quitar</button>' +
                '</div>';
            cartListEl.appendChild(li);
        });

        itemsJsonInput.value = JSON.stringify(payload);

        if (payload.length === 0) {
            cartEmptyEl.classList.remove('hidden');
            cartListEl.classList.add('hidden');
            clearCartBtn.classList.add('hidden');
        } else {
            cartEmptyEl.classList.add('hidden');
            cartListEl.classList.remove('hidden');
            clearCartBtn.classList.remove('hidden');
        }

        const totalNeto = Math.round(totalBruto / 1.19);
        const montoIva = totalBruto - totalNeto;

        totalNetoEl.textContent = formatCLP(totalNeto);
        montoIvaEl.textContent = formatCLP(montoIva);
        totalBrutoEl.textContent = formatCLP(totalBruto);
    }

    document.querySelectorAll('.btn-add-cart').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const id = parseInt(btn.dataset.id, 10);
            updateCartQuantity(id, 1);
        });
    });

    cartListEl.addEventListener('click', function (ev) {
        const target = ev.target.closest('button[data-action]');
        if (!target) return;
        const id = parseInt(target.dataset.id, 10);
        const action = target.dataset.action;
        if (action === 'inc') updateCartQuantity(id, 1);
        if (action === 'dec') updateCartQuantity(id, -1);
        if (action === 'del') {
            cart.delete(id);
            showAlert('');
            renderCart();
        }
    });

    clearCartBtn.addEventListener('click', function () {
        cart.clear();
        showAlert('');
        renderCart();
    });

    searchInput.addEventListener('input', filterProducts);
    clearSearchBtn.addEventListener('click', function () {
        searchInput.value = '';
        filterProducts();
        searchInput.focus();
    });

    checkoutForm.addEventListener('submit', function (ev) {
        if (cart.size === 0) {
            ev.preventDefault();
            showAlert('Agrega al menos un producto al carro antes de confirmar la venta.');
            return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = 'Procesando venta...';
    });

    renderCart();
})();
