---
name: ui-botanica-rbac
description: Construye plantillas DTL responsivas en paleta Verde Bosque minimalista y aplica control de acceso estricto RBAC en vistas Django.
---
# Skill: Interfaz Botánica Minimalista y Control de Acceso RBAC

## Cuándo aplicar
Al crear o editar plantillas HTML (`templates/`), estilos CSS o controladores de vistas (`views/`).

## 1. Control de Acceso RBAC (`core/decorators.py`)
- Implementar dos decoradores explícitos:
  - `@requiere_administradora`: Verifica `request.user.is_authenticated` y `(request.user.is_superuser or request.user.groups.filter(name='Administradora General').exists())`. Si no cumple, retorna `HttpResponseForbidden("Acceso denegado: Se requiere perfil de Administradora General.")`.
  - `@requiere_operador_o_admin`: Permite tanto a `Administradora General` como a `Operador de Mesón`.
- **Nunca** confiar en ocultar enlaces en el HTML; toda ruta protegida debe llevar su decorador en Python.

## 2. Reglas de Plantillas DTL (`templates/`)
- `base_publico.html`: Header limpio blanco con logo "Vivero Leufucades", buscador y botón discreto "Acceso Vivero" a la derecha. Fondo `#F9FAF8`.
- `base_panel.html`: Layout flex con Sidebar fijo izquierdo de `250px` en color `#1B4332`, texto blanco/menta suave, badge superior indicando la temporada comercial activa (ej. `Ciclo Activo: Primavera`) y botón "Cerrar Sesión".
- **Tarjetas de KPI y Alertas:**
  - En el Dashboard (`/panel/`), mostrar tarjetas blancas con borde `#E2E8E4` para: Ventas de Hoy ($CLP), Especies Activas y **Stock Crítico (`<= 5` un.)**.
  - Si existen productos con `stock_actual <= stock_minimo`, renderizar un banner superior y una tabla destacada en rojo suave (`bg-[#FEF2F2] border-[#FECACA] text-[#991B1B]`) con botón directo para reponer stock.