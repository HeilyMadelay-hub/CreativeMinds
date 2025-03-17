# CreativeMinds - Módulo de Gestión de Proyectos para Odoo

## Descripción General

CreativeMinds es un módulo desarrollado para Odoo que integra herramientas avanzadas para la gestión de proyectos, empleados y equipos, facilitando la organización, seguimiento y control de proyectos creativos. Está diseñado para empresas que buscan optimizar la ejecución de sus proyectos, centralizando la información y mejorando la comunicación entre equipos.

## Componentes Principales

- **Gestión de Proyectos:** Administración de Proyectos con sus respectivas Tareas, Recursos, KPIs, Ideas y Feedback del Cliente.
- **Gestión de Empleados:** Asignación y seguimiento de empleados a proyectos y tareas.
- **Gestión de Equipos:** Agrupación de empleados para favorecer la colaboración y coordinación en los proyectos.

## Problemática que Resuelve

El módulo CreativeMinds aborda diversos desafíos comunes en la gestión de proyectos creativos:

1. **Desorganización en la gestión de proyectos:**
   - Centralización de la información
   - Mejora de la comunicación entre equipos
   - Seguimiento centralizado del progreso

2. **Ineficiencia en la asignación de recursos:**
   - Optimización de la asignación de personal
   - Planificación de capacidades
   - Visibilidad sobre la disponibilidad de recursos

3. **Seguimiento inadecuado del progreso:**
   - Métricas claras para evaluar el avance
   - Identificación de cuellos de botella
   - Transparencia en el estado de los proyectos

## Requisitos

- Odoo versión 17 o superior
- Git (opcional)

## Guía de Instalación

### Usando Git:
```bash
# 1. Abra git bash
# 2. Cambie al directorio para módulos de terceros
cd /ruta/a/su/directorio/addons
# 3. Clone el repositorio
git clone https://github.com/HeilyMadelay-hub/CreativeMinds-AI.git
```

### Sin Git:
1. Entre en el repositorio: HeilyMadelay-hub/CreativeMinds-AI y descargue el .zip
2. Descomprima el repositorio e ir al directorio SourceCode
3. Copie el directorio creativeminds al directorio de módulos de terceros

### Configuración Inicial:
```bash
# 1. Modifique el archivo odoo.conf añadiendo su directorio a addons_paths
# 2. Reinicie el servicio de Odoo
sudo systemctl restart odoo

# 3. En Odoo: Ajustes -> Activar modo desarrollador -> Aplicaciones -> 
# Actualizar lista de aplicaciones -> Activar CreativeMinds
```

## Funcionalidades Principales

### Proyectos
- Gestión completa del ciclo de vida del proyecto
- Seguimiento de costos y presupuestos
- Estados configurables (planificación, en progreso, finalizado, etc.)
- Notificaciones automáticas
- Adjuntos de documentos e imágenes
- Duplicación de proyectos

### Empleados
- Gestión de información personal y profesional
- Control de disponibilidad
- Asignación a proyectos y equipos
- Validación de datos (DNI, edad mínima, etc.)

### Equipos
- Gestión de grupos de trabajo
- Asignación de miembros y responsables
- Cálculo automático del número de miembros

### Tareas
- Asignación a proyectos y responsables
- Control de fechas de inicio y finalización
- Seguimiento del estado (pendiente, en progreso, completada)

### Recursos
- Control de costos y tiempo de asignación
- Fechas de disponibilidad
- Estados de asignación (borrador, asignado, en progreso, completado)

### Ideas
- Evaluación de ideas para proyectos
- Sistema de votación
- Análisis de viabilidad e impacto

### Retroalimentación
- Gestión de feedback de clientes
- Acciones para abordar los comentarios
- Sistema de priorización

### Informes
- Métricas de proyectos
- Análisis de presupuestos y costos
- Seguimiento de tareas y disponibilidad de empleados

## Contacto

Para más información o soporte, contacte a los autores:
- Heily Madelay Ajila Tandazo
- Daniel Gonzalez Esteban

---

© 2024 CreativeMinds - Todos los derechos reservados.
