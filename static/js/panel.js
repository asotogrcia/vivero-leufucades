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

    // --- Modal de confirmación reutilizable (delegación de eventos) ---
    var modalConfirm = document.getElementById('modal-confirmacion');
    var modalConfirmTitulo = document.getElementById('modal-confirmacion-titulo');
    var modalConfirmMensaje = document.getElementById('modal-confirmacion-mensaje');
    var modalConfirmBtnOk = document.getElementById('modal-confirmacion-confirmar');
    var modalConfirmBtnCancel = document.getElementById('modal-confirmacion-cancelar');
    var modalConfirmBtnClose = document.getElementById('modal-confirmacion-cerrar');
    var accionPendiente = null;

    var cerrarModalConfirm = function () {
        if (!modalConfirm) return;
        modalConfirm.classList.add('hidden');
        accionPendiente = null;
    };

    var abrirModalConfirm = function (titulo, mensaje, textoBoton, onConfirm) {
        if (!modalConfirm) {
            if (window.confirm(mensaje || titulo)) onConfirm();
            return;
        }
        if (modalConfirmTitulo) {
            modalConfirmTitulo.textContent = titulo || 'Confirmar acción';
        }
        if (modalConfirmMensaje) {
            modalConfirmMensaje.textContent =
                mensaje ||
                'El registro pasará a "Dados de Baja" y podrá reactivarse en cualquier momento sin perder su historial.';
        }
        if (modalConfirmBtnOk) {
            modalConfirmBtnOk.textContent = textoBoton || 'Confirmar';
        }
        accionPendiente = onConfirm;
        modalConfirm.classList.remove('hidden');
        if (modalConfirmBtnCancel) modalConfirmBtnCancel.focus();
    };

    if (modalConfirm) {
        if (modalConfirmBtnCancel) {
            modalConfirmBtnCancel.addEventListener('click', cerrarModalConfirm);
        }
        if (modalConfirmBtnClose) {
            modalConfirmBtnClose.addEventListener('click', cerrarModalConfirm);
        }
        if (modalConfirmBtnOk) {
            modalConfirmBtnOk.addEventListener('click', function () {
                var cb = accionPendiente;
                cerrarModalConfirm();
                if (typeof cb === 'function') cb();
            });
        }
        modalConfirm.addEventListener('click', function (e) {
            if (e.target === modalConfirm) cerrarModalConfirm();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modalConfirm.classList.contains('hidden')) {
                cerrarModalConfirm();
            }
        });
    }

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (
            !form ||
            form.tagName !== 'FORM' ||
            (!form.hasAttribute('data-confirm-title') &&
                !form.hasAttribute('data-confirm-message') &&
                !form.hasAttribute('data-confirm'))
        ) {
            return;
        }
        if (form.dataset.confirmed === 'true') {
            delete form.dataset.confirmed;
            return;
        }
        e.preventDefault();
        abrirModalConfirm(
            form.dataset.confirmTitle || 'Confirmar acción',
            form.dataset.confirmMessage || form.dataset.confirm || '',
            form.dataset.confirmButton || 'Confirmar',
            function () {
                form.dataset.confirmed = 'true';
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            }
        );
    });

    document.addEventListener('click', function (e) {
        var trigger = e.target.closest(
            'button[data-confirm-title], button[data-confirm-message], ' +
                'a[data-confirm-title], a[data-confirm-message]'
        );
        if (!trigger) return;
        if (trigger.dataset.confirmed === 'true') {
            delete trigger.dataset.confirmed;
            return;
        }
        e.preventDefault();
        abrirModalConfirm(
            trigger.dataset.confirmTitle || 'Confirmar acción',
            trigger.dataset.confirmMessage || '',
            trigger.dataset.confirmButton || 'Confirmar',
            function () {
                if (trigger.tagName === 'A' && trigger.href) {
                    window.location.href = trigger.href;
                    return;
                }
                if (trigger.form) {
                    trigger.dataset.confirmed = 'true';
                    trigger.form.dataset.confirmed = 'true';
                    if (typeof trigger.form.requestSubmit === 'function') {
                        trigger.form.requestSubmit(trigger);
                    } else {
                        trigger.form.submit();
                    }
                }
            }
        );
    });

    // --- Notificaciones Toast flotantes ---
    var cerrarToast = function (toast) {
        if (!toast || toast.dataset.closing === 'true') return;
        toast.dataset.closing = 'true';
        toast.classList.add('is-closing');
        window.setTimeout(function () {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 250);
    };

    document.addEventListener('click', function (e) {
        var closeBtn = e.target.closest('[data-toast-close]');
        if (!closeBtn) return;
        var toast = closeBtn.closest('[data-toast]');
        if (toast) cerrarToast(toast);
    });

    document.querySelectorAll('[data-toast]').forEach(function (toast) {
        var timeoutMs = parseInt(toast.dataset.toastTimeout, 10) || 4500;
        window.setTimeout(function () {
            cerrarToast(toast);
        }, timeoutMs);
    });

    // --- Imprimir comprobante: <button data-print> ---
    document.querySelectorAll('[data-print]').forEach(function (b) {
        b.addEventListener('click', function () { window.print(); });
    });
})();