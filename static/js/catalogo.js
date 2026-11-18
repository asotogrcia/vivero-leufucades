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
        }
    });

    var modal = document.getElementById('ficha-modal');
    if (!modal) return;

    var titulo = document.getElementById('ficha-modal-titulo');
    var cientifico = document.getElementById('ficha-modal-cientifico');
    var temporada = document.getElementById('ficha-modal-temporada');
    var estado = document.getElementById('ficha-modal-estado');
    var cuidados = document.getElementById('ficha-modal-cuidados');
    var sku = document.getElementById('ficha-modal-sku');
    var precio = document.getElementById('ficha-modal-precio');
    var btnCerrar = document.getElementById('ficha-modal-cerrar');
    var btnAceptar = document.getElementById('ficha-modal-aceptar');

    var BADGE = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ';

    function abrirModal(trigger) {
        var d = trigger.dataset;
        titulo.textContent = d.nombre || '';
        cientifico.textContent = d.cientifico || '';
        cientifico.classList.toggle('hidden', !d.cientifico);
        temporada.textContent = d.temporada || '';
        temporada.className = BADGE + (d.esFijo === '1'
            ? 'bg-[#FEF3C7] text-[#92400E]'
            : 'bg-[#D8F3DC] text-[#1B4332]');

        estado.textContent = d.estado || '';
        estado.className = BADGE + (d.disponible === '1'
            ? 'bg-[#D8F3DC]/70 text-[#1B4332]'
            : 'bg-[#F2F4F2] text-[#52606D] border border-[#E2E8E4]');

        cuidados.textContent = d.cuidados || '';
        sku.textContent = d.sku || '';
        precio.textContent = d.precio || '';

        modal.classList.remove('hidden');
        modal.classList.add('flex');
        btnCerrar.focus();
    }

    function cerrarModal() {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }

    document.querySelectorAll('[data-modal-trigger]').forEach(function (btn) {
        btn.addEventListener('click', function () { abrirModal(btn); });
    });

    btnCerrar.addEventListener('click', cerrarModal);
    btnAceptar.addEventListener('click', cerrarModal);
    modal.addEventListener('click', function (e) {
        if (e.target === modal) cerrarModal();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            cerrarModal();
        }
    });
})();
