/* Panel operacional — Vivero Leufucades: sidebar móvil, modal de ajuste de stock,
   confirmaciones de acciones críticas e impresión de comprobante. Sin dependencias. */
(function () {
    'use strict';

    // --- Sidebar móvil (drawer) ---
    var sidebar = document.getElementById('panel-sidebar');
    var backdrop = document.getElementById('sidebar-backdrop');
    var openBtn = document.getElementById('sidebar-open-btn');
    var closeBtn = document.getElementById('sidebar-close-btn');

    if (sidebar && backdrop && openBtn) {
        var abrirDrawer = function () {
            sidebar.classList.remove('-translate-x-full');
            sidebar.classList.add('translate-x-0');
            backdrop.classList.remove('hidden');
            openBtn.setAttribute('aria-expanded', 'true');
        };
        var cerrarDrawer = function () {
            sidebar.classList.add('-translate-x-full');
            sidebar.classList.remove('translate-x-0');
            backdrop.classList.add('hidden');
            openBtn.setAttribute('aria-expanded', 'false');
        };
        openBtn.addEventListener('click', abrirDrawer);
        if (closeBtn) closeBtn.addEventListener('click', cerrarDrawer);
        backdrop.addEventListener('click', cerrarDrawer);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !backdrop.classList.contains('hidden')) {
                cerrarDrawer();
            }
        });
    }

    // --- Modal de ajuste rápido de stock / merma (inventario) ---
    var modal = document.getElementById('modal-ajuste-stock');
    if (modal) {
        var form = document.getElementById('form-ajuste-stock');
        var subtitulo = document.getElementById('modal-ajuste-subtitulo');
        var cerrarModal = function () { modal.classList.add('hidden'); };

        document.querySelectorAll('.btn-abrir-ajuste').forEach(function (btn) {
            btn.addEventListener('click', function () {
                form.action = '/inventario/ajustar/' + btn.dataset.ajusteId + '/';
                subtitulo.textContent = btn.dataset.ajusteNombre +
                    ' (Stock actual: ' + btn.dataset.ajusteStock + ' un.)';
                modal.classList.remove('hidden');
                var qty = document.getElementById('id_cantidad');
                if (qty) qty.focus();
            });
        });

        var btnCerrar = document.getElementById('btn-cerrar-ajuste');
        var btnCancelar = document.getElementById('btn-cancelar-ajuste');
        if (btnCerrar) btnCerrar.addEventListener('click', cerrarModal);
        if (btnCancelar) btnCancelar.addEventListener('click', cerrarModal);
        modal.addEventListener('click', function (e) {
            if (e.target === modal) cerrarModal();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modal.classList.contains('hidden')) cerrarModal();
        });
    }

    // --- Confirmación de acciones críticas: <form data-confirm="..."> ---
    document.querySelectorAll('form[data-confirm]').forEach(function (f) {
        f.addEventListener('submit', function (e) {
            if (!window.confirm(f.dataset.confirm)) e.preventDefault();
        });
    });

    // --- Imprimir comprobante: <button data-print> ---
    document.querySelectorAll('[data-print]').forEach(function (b) {
        b.addEventListener('click', function () { window.print(); });
    });
})();