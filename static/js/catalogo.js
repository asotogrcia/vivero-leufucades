/* Catálogo Público — Vivero Leufucades: Skeleton loaders y modal de ficha técnica. */
(function () {
    'use strict';

    var skeletonGrid = document.getElementById('catalogo-skeleton-grid');
    var contenido = document.getElementById('catalogo-contenido');

    function mostrarSkeletonTransicion() {
        if (skeletonGrid && contenido) {
            contenido.classList.add('hidden');
            skeletonGrid.classList.remove('hidden');
        }
    }

    document.querySelectorAll('form[data-catalogo-search-form]').forEach(function (form) {
        form.addEventListener('submit', mostrarSkeletonTransicion);
    });

    document.querySelectorAll('a[data-catalogo-filter]').forEach(function (link) {
        link.addEventListener('click', mostrarSkeletonTransicion);
    });

    window.addEventListener('pageshow', function (event) {
        if (event.persisted && skeletonGrid && contenido) {
            skeletonGrid.classList.add('hidden');
            contenido.classList.remove('hidden');
        }
    });

    function imagenCargada(img) {
        img.classList.remove('opacity-0');
        img.classList.add('opacity-100');
        if (img.previousElementSibling) {
            img.previousElementSibling.classList.add('hidden');
        }
    }

    document.querySelectorAll('#catalogo-contenido img[loading="lazy"]').forEach(function (img) {
        if (img.complete && img.naturalWidth > 0) {
            imagenCargada(img);
        } else {
            img.addEventListener('load', function () { imagenCargada(img); });
            img.addEventListener('error', function () {
                if (img.previousElementSibling) {
                    img.previousElementSibling.classList.add('hidden');
                }
            });
        }
    });

    var modal = document.getElementById('ficha-modal') || document.getElementById('modal-detalle-producto');
    if (!modal) return;

    var titulo = document.getElementById('ficha-modal-titulo');
    var cientifico = document.getElementById('ficha-modal-cientifico');
    var temporada = document.getElementById('ficha-modal-temporada');
    var estado = document.getElementById('ficha-modal-estado');
    var cuidados = document.getElementById('ficha-modal-cuidados');
    var sku = document.getElementById('ficha-modal-sku');
    var precio = document.getElementById('ficha-modal-precio');
    var btnCerrar = document.getElementById('ficha-modal-cerrar');
    var imagenWrap = document.getElementById('ficha-modal-imagen-wrap');
    var imagenEl = document.getElementById('ficha-modal-imagen');
    var guiaWrap = document.getElementById('ficha-modal-guia');
    var riegoWrap = document.getElementById('ficha-modal-riego-wrap');
    var riegoEl = document.getElementById('ficha-modal-riego');
    var luzWrap = document.getElementById('ficha-modal-luz-wrap');
    var luzEl = document.getElementById('ficha-modal-luz');

    var BADGE = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ';
    var ultimoTrigger = null;

    function abrirModal(trigger) {
        var d = trigger.dataset;
        ultimoTrigger = trigger;

        if (titulo) titulo.textContent = d.nombre || '';
        if (cientifico) {
            cientifico.textContent = d.cientifico || '';
            cientifico.classList.toggle('hidden', !d.cientifico);
        }
        if (temporada) {
            temporada.textContent = d.temporada || '';
            temporada.className = BADGE + (d.esFijo === '1'
                ? 'bg-[#FEF3C7] text-[#92400E]'
                : 'bg-[#D8F3DC] text-[#1B4332]');
        }
        if (estado) {
            estado.textContent = d.estado || '';
            estado.className = BADGE + (d.disponible === '1'
                ? 'bg-[#D8F3DC]/70 text-[#1B4332]'
                : 'bg-[#F2F4F2] text-[#52606D] border border-[#E2E8E4]');
        }

        if (imagenWrap && imagenEl) {
            if (d.imagen) {
                imagenEl.src = d.imagen;
                imagenEl.alt = d.nombre || 'Fotografía de producto';
                imagenWrap.classList.remove('hidden');
            } else {
                imagenEl.removeAttribute('src');
                imagenEl.alt = '';
                imagenWrap.classList.add('hidden');
            }
        }

        var tieneRiego = Boolean(d.riego);
        var tieneLuz = Boolean(d.luz);
        if (riegoWrap && riegoEl) {
            riegoEl.textContent = d.riego || '';
            riegoWrap.classList.toggle('hidden', !tieneRiego);
        }
        if (luzWrap && luzEl) {
            luzEl.textContent = d.luz || '';
            luzWrap.classList.toggle('hidden', !tieneLuz);
        }
        if (guiaWrap) {
            guiaWrap.classList.toggle('hidden', !tieneRiego && !tieneLuz);
        }

        if (cuidados) cuidados.textContent = d.cuidados || '';
        if (sku) sku.textContent = d.sku || '';
        if (precio) precio.textContent = d.precio || '';

        modal.classList.remove('hidden');
        modal.classList.add('flex');
        document.body.classList.add('overflow-hidden');
        if (btnCerrar) btnCerrar.focus();
    }

    function cerrarModal() {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        document.body.classList.remove('overflow-hidden');
        if (ultimoTrigger && typeof ultimoTrigger.focus === 'function') {
            ultimoTrigger.focus();
        }
        ultimoTrigger = null;
    }

    document.addEventListener('click', function (e) {
        if (e.target.closest('[data-close-modal], #ficha-modal-cerrar, #ficha-modal-aceptar')) {
            cerrarModal();
            return;
        }
        if (e.target === modal) {
            cerrarModal();
            return;
        }

        var trigger = e.target.closest('[data-open-modal], [data-modal-trigger]');
        if (!trigger) {
            var card = e.target.closest('[data-product-card]');
            if (card && !e.target.closest('a, button')) {
                trigger = card.querySelector('[data-open-modal], [data-modal-trigger]');
            }
        }
        if (trigger) {
            abrirModal(trigger);
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            cerrarModal();
        }
    });
})();
