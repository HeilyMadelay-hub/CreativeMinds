from odoo import models, fields, api  # Importa los módulos necesarios de Odoo para la creación de modelos y campos.
from odoo.exceptions import ValidationError  # Importa la excepción ValidationError para manejar errores de validación.
from datetime import date  # Importa el módulo date para trabajar con fechas.
import re  # Importa el módulo re para trabajar con expresiones regulares.
from dateutil.relativedelta import relativedelta  # Para realizar operaciones con fechas, como sumar o restar periodos.
from odoo.exceptions import UserError  # Para generar errores personalizados en Odoo.
import logging # Para registrar información y errores en el log de Odoo.

# Configuramos el logger para poder registrar información y errores

_logger = logging.getLogger(__name__)

class Proyecto(models.Model):
    _name = 'creativeminds.proyecto'  # Nombre técnico del modelo en Odoo.
    _description = 'Proyecto'  # Descripción del modelo.
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Herencia de funcionalidades de seguimiento de mensajes (para notificaciones y conversaciones).

    # Campos básicos del proyecto
    nombre = fields.Char(string='Nombre del Proyecto', required=True)  # Nombre del proyecto
    empleado_id = fields.Many2many('creativeminds.empleado', string='Empleados')  # Empleados asignados al proyecto
    idea_ids = fields.One2many('creativeminds.idea', 'proyecto_id', string='Ideas')  # Ideas para el proyecto
    costo_por_hora = fields.Float(string='Costo por Hora')  # Costo por hora de trabajo en el proyecto
    horas_asignadas = fields.Float(string='Horas Asignadas')  # Total de horas asignadas al proyecto
    costo_total = fields.Float(string='Costo Total', compute='_calcular_costo_total', store=True)  # Cálculo del costo total basado en las horas y costo por hora
    descripcion = fields.Text(string='Descripción del Proyecto')  # Descripción detallada del proyecto
    cliente = fields.Char(string='Cliente')  # Cliente asociado al proyecto
    feedback_ids = fields.One2many('creativeminds.feedback', 'proyecto_id', string='Retroalimentación')  #Feedback del cliente 

    @api.depends('costo_por_hora', 'horas_asignadas')
    def _calcular_costo_total(self):
        # Calcula el costo total del proyecto como el producto de costo por hora y horas asignadas
        self.costo_total = self.costo_por_hora * self.horas_asignadas

    @api.constrains('costo_por_hora', 'horas_asignadas')
    def _verificar_costo_y_horas(self):
        # Verifica que el costo por hora y las horas asignadas sean valores positivos
        if self.costo_por_hora < 0 or self.horas_asignadas < 0:
            raise ValidationError("El costo por hora y las horas asignadas deben ser valores positivos.")
   
    # Campos relacionados con el estado y seguimiento del proyecto
    estado = fields.Selection([  # Estado del proyecto
        ('planificacion', 'En planificación'),
        ('en_progreso', 'En progreso'),
        ('finalizado', 'Finalizado'),
        ('detenido', 'Detenido'),
    ], string='Estado del Proyecto', default='planificacion', tracking=True)
    
    porcentaje_progreso = fields.Float(  # Porcentaje de progreso calculado
        string='Porcentaje de Progreso',
        compute='_calcular_progreso',
        store=True,
        tracking=True
    )
    
    # Fechas del proyecto
    fecha_inicio = fields.Date(string='Fecha de Inicio')  # Fecha de inicio del proyecto
    fecha_fin = fields.Date(string='Fecha de Finalización')  # Fecha de finalización del proyecto
    
    # Prioridad y responsables
    prioridad = fields.Selection([  # Nivel de prioridad del proyecto
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
    ], string='Prioridad', default='media')

    responsable_id = fields.Many2one(
        'creativeminds.empleado',
        string='Responsable',
        domain="[('disponibilidad', '=', 'disponible')]",  # Filtra solo empleados disponibles
        tracking=True
    )

    @api.constrains('responsable_id')
    def _verificar_responsable(self):
        for record in self:
            if record.estado not in ['planificacion'] and not record.responsable_id:
                raise ValidationError("Debe asignar un responsable antes de cambiar el estado del proyecto.")

    
   
    # Presupuesto y recursos
    presupuesto_estimado = fields.Float(string='Presupuesto Estimado')  # Presupuesto estimado del proyecto
    recursos_ids = fields.One2many('creativeminds.recurso', 'proyecto_id', string='Recursos Asignados')  # Recursos asignados al proyecto
    costo_total_recursos = fields.Float(string='Costo Total de Recursos', 
                                     compute='_calcular_costo_total_recursos', 
                                     store=True)  # Costo total de los recursos asignados

    @api.depends('recursos_ids.costo_total')
    def _calcular_costo_total_recursos(self):
        # Calcula el costo total de los recursos asignados al proyecto
        self.costo_total_recursos = sum(self.recursos_ids.mapped('costo_total'))

    @api.constrains('presupuesto_estimado', 'costo_total_recursos')
    def _verificar_presupuesto(self):
        # Verifica que el costo total de los recursos no exceda el presupuesto estimado
        if self.costo_total_recursos > self.presupuesto_estimado:
            raise ValidationError(
                f"El costo total de recursos ({self.costo_total_recursos}) "
                f"excede el presupuesto estimado ({self.presupuesto_estimado})"
            )

    # Relaciones con tareas e indicadores
    tareas_ids = fields.One2many('creativeminds.tarea', 'proyecto_id', string='Tareas')  # Tareas asociadas al proyecto
    indicadores_ids = fields.One2many('creativeminds.kpi', 'proyecto_id', string='Indicadores de Desempeño')  # Indicadores de desempeño asociados al proyecto

    # Archivos y documentación
    imagen_proyecto = fields.Binary(string='Imagen del Proyecto', attachment=True)  # Imagen del proyecto
    imagen_filename = fields.Char(string='Nombre del archivo de imagen')  # Nombre del archivo de imagen
    documentacion_tecnica = fields.Binary(string='Documentación Técnica', attachment=True)  # Documentación técnica del proyecto
    documentacion_filename = fields.Char(string='Nombre del archivo de documentación')  # Nombre del archivo de documentación

    # Archivos adicionales
    archivos_adicionales = fields.Many2many(
        'ir.attachment',
        'creativeminds_attachment_rel',
        'creativeminds_id',
        'attachment_id',
        string='Archivos Adicionales'
    )  # Archivos adicionales que se pueden asociar al proyecto
   
    # Campos de texto para detalles adicionales
    colaboradores = fields.Text(string='Agencias Colaboradoras')  # Agencias colaboradoras en el proyecto
    riesgos = fields.Text(string='Riesgos')  # Riesgos asociados al proyecto
    hitos = fields.Text(string='Hitos/Entregables')  # Hitos o entregables importantes del proyecto
    dependencias = fields.Text(string='Dependencias')  # Dependencias entre el proyecto y otros
    comentarios = fields.Text(string='Comentarios y Notas')  # Notas o comentarios sobre el proyecto
    
    # Configuración para recordatorios automáticos
    recordatorios_automaticos = fields.Boolean(string='Activar Recordatorios Automáticos')

    # Verificación de fechas del proyecto
    @api.constrains('fecha_inicio', 'fecha_fin')
    def _verificar_fechas_proyecto(self):
        # Asegura que la fecha de inicio no sea posterior a la fecha de finalización
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de finalización.")

    @api.constrains('presupuesto_estimado')
    def _verificar_presupuesto_estimado(self):
        # Verifica que el presupuesto estimado sea válido y suficiente para los recursos y tareas
        if self.presupuesto_estimado <= 0:
            raise ValidationError("El presupuesto estimado debe ser mayor que cero.")
        num_recursos = len(self.recursos_ids)
        num_tareas = len(self.tareas_ids)
        presupuesto_requerido = (num_recursos * 500) + (num_tareas * 200)  # Estimación de presupuesto requerido
        if (num_recursos > 0 or num_tareas > 0) and self.presupuesto_estimado < presupuesto_requerido:
            raise ValidationError(
                f"El presupuesto ({self.presupuesto_estimado}) es insuficiente. "
                f"Se requieren al menos {round(presupuesto_requerido, 2)} para cubrir recursos y tareas."
            )

    # Sobrescribimos el método 'create' para agregar lógica adicional al crear un proyecto.
    @api.model
    def create(self, valores):
        if 'responsable_id' not in valores or not valores['responsable_id']:
            raise ValidationError("Es necesario asignar un responsable al proyecto.")
        
        proyecto = super(Proyecto, self).create(valores) # Crear el proyecto como se haría normalmente.
        # Si los recordatorios automáticos están activados y el proyecto tiene un responsable asignado,
        # se crea una tarea inicial y se envía un recordatorio.
        if proyecto.recordatorios_automaticos and proyecto.responsable_id:
            self.env['creativeminds.tarea'].create({
                'nombre': f'Tarea inicial de proyecto: {proyecto.nombre}',# Nombre de la tarea inicial.
                'proyecto_id': proyecto.id,  # Asociamos la tarea al proyecto.
                'responsable_id': proyecto.responsable_id.id,  # Asignamos al responsable del proyecto.
                'estado': 'pendiente',  # La tarea está pendiente al principio.
            })
            self.enviar_recordatorio(proyecto)  # Enviamos un recordatorio al responsable.
        return proyecto  # Devolvemos el proyecto creado.
    
    # Método que actualiza el indicador de progreso del proyecto.
    def actualizar_progreso_indicador(self):
        # Buscamos el indicador específico relacionado con el progreso del proyecto.
        indicador = self.env['creativeminds.indicador'].search([
            ('proyecto_id', '=', self.id),
            ('nombre', '=', 'Progreso del Proyecto')
        ], limit=1)
        if indicador:  # Si el indicador existe, actualizamos su valor.
            indicador.write({'valor': self.porcentaje_progreso})
        return True

    # Método que envía una notificación al responsable del proyecto sobre el cambio de estado o progreso.
    def enviar_notificacion_proyecto(self, tipo_notificacion='estado'):
        if not self.responsable_id:  # Si no hay responsable, no se envía notificación.
            return
        # Determinamos el asunto de la notificación según el tipo.
        asunto = f"Cambio de Estado: Proyecto {self.nombre}" if tipo_notificacion == 'estado' else f"Actualización de Progreso: Proyecto {self.nombre}"
        # Construimos el mensaje de notificación en formato HTML.
        mensaje = f"<p>Hola {self.responsable_id.name},</p>"
        mensaje += f"<p>El estado del proyecto <b>{self.nombre}</b> ha cambiado a <b>{dict(self._fields['estado'].selection).get(self.estado)}</b>.</p>"
        mensaje += f"<p>Progreso actual: {round(self.porcentaje_progreso, 2)}%</p>"
        # Enviamos el mensaje por correo utilizando el sistema de mensajes de Odoo.
        self.message_post(
            body=mensaje,
            subject=asunto,
            partner_ids=[self.responsable_id.partner_id.id]  # Enviamos el mensaje al partner del responsable.
        )

    # Método que envía un recordatorio al responsable del proyecto sobre las tareas pendientes.
    def enviar_recordatorio(self, proyecto):
        if not proyecto.responsable_id:  # Si no hay responsable asignado, no se envía el recordatorio.
            return
        # Construimos el mensaje de recordatorio en formato HTML.
        mensaje = f"""
            <p>Estimado {proyecto.responsable_id.name},</p>
            <p>Este es un recordatorio de que el proyecto <b>{proyecto.nombre}</b> tiene tareas pendientes.</p>
            <p>Por favor, asegúrese de revisar el progreso y continuar con las tareas.</p>
            <p>Saludos,<br>Equipo de gestión de proyectos</p>
        """
        # Enviamos el recordatorio por mensaje en Odoo.
        proyecto.message_post(
            body=mensaje,
            subject=f"Recordatorio: Proyecto {proyecto.nombre} - Tareas pendientes",
            partner_ids=[proyecto.responsable_id.partner_id.id]  # Enviamos el mensaje al partner del responsable.
        )
        # Creamos una actividad para el responsable para asegurarnos de que se realice el seguimiento de las tareas pendientes.
        actividad_tipo = self.env.ref('mail.mail_activity_data_todo')
        modelo_id = self.env['ir.model']._get_id('creativeminds.proyecto')
        self.env['mail.activity'].create({
            'activity_type_id': actividad_tipo.id,
            'res_model_id': modelo_id,
            'res_id': proyecto.id,
            'user_id': proyecto.responsable_id.id,
            'summary': f"Recordatorio: {proyecto.nombre} - Tareas pendientes",
            'note': f"Este es un recordatorio para que revises las tareas pendientes del proyecto {proyecto.nombre}.",
        })

    # Método que calcula el porcentaje de progreso del proyecto basado en las tareas completadas.
    @api.depends('tareas_ids.estado')
    def _calcular_progreso(self):
        total_tareas = len(self.tareas_ids)  # Contamos el total de tareas.
        tareas_completadas = len(self.tareas_ids.filtered(lambda t: t.estado == 'completada'))
        # Calculamos el progreso como el porcentaje de tareas completadas.
        self.porcentaje_progreso = (tareas_completadas / total_tareas * 100) if total_tareas > 0 else 0.0
 
    # Método que obtiene un resumen detallado del proyecto.
    def obtener_resumen_proyecto(self):
        self.ensure_one()  # Aseguramos que solo haya un registro.
        return {
            'nombre': self.nombre,
            'estado': self.estado,
            'progreso': self.porcentaje_progreso,
            'presupuesto': {
                'estimado': self.presupuesto_estimado,
                'actual': self.costo_total_recursos,
                'disponible': self.presupuesto_estimado - self.costo_total_recursos
            },
            'tareas': {
                'total': len(self.tareas_ids),
                'completadas': len(self.tareas_ids.filtered(lambda t: t.estado == 'completada')),
                'en_progreso': len(self.tareas_ids.filtered(lambda t: t.estado == 'en_progreso')),
                'pendientes': len(self.tareas_ids.filtered(lambda t: t.estado == 'pendiente'))
            }
        }

    def duplicar_proyecto(self):
        """
        Función para duplicar un proyecto existente.
        No requiere argumentos adicionales ya que opera sobre el registro actual (self).
        """
        self.ensure_one()
        
        # Crear una copia del proyecto actual
        valores = {
            'nombre': self.nombre + ' (Copia)',
            'estado': 'planificacion',
            'empleado_id': [(6, 0, self.empleado_id.ids)],  # Preservar relaciones many2many
            'costo_por_hora': self.costo_por_hora,
            'horas_asignadas': self.horas_asignadas,
            'descripcion': self.descripcion,
            'cliente': self.cliente,
            'fecha_inicio': self.fecha_inicio,
            'fecha_fin': self.fecha_fin,
            'prioridad': self.prioridad,
            'responsable_id': self.responsable_id.id if self.responsable_id else False,
            'presupuesto_estimado': self.presupuesto_estimado,
            'riesgos': self.riesgos,
            'hitos': self.hitos,
            'dependencias': self.dependencias,
            'comentarios': self.comentarios,
            'recordatorios_automaticos': self.recordatorios_automaticos,
            'imagen_proyecto': self.imagen_proyecto,
            'documentacion_tecnica': self.documentacion_tecnica,
            'archivos_adicionales': [(6, 0, self.archivos_adicionales.ids)],  # Copiar archivos adicionales
        }
        
        # Crear nuevo proyecto con los valores copiados
        nuevo_proyecto = self.create(valores)
        
        # Duplicar las tareas asociadas
        for tarea in self.tareas_ids:
            tarea_valores = {
                'proyecto_id': nuevo_proyecto.id,
                'nombre': tarea.nombre,
                'descripcion': tarea.descripcion,
                'responsable_id': tarea.responsable_id.id if tarea.responsable_id else False,
                'fecha_inicio': tarea.fecha_inicio,
                'fecha_fin': tarea.fecha_fin,
                'estado': 'pendiente',  # Las tareas duplicadas comienzan como pendientes
            }
            self.env['creativeminds.tarea'].create(tarea_valores)
        
        # Duplicar los recursos asignados
        for recurso in self.recursos_ids:
            recurso_valores = {
                'proyecto_id': nuevo_proyecto.id,
                'nombre': recurso.nombre,
                'empleado_id': [(6, 0, recurso.empleado_id.ids)] if recurso.empleado_id else [],
                'costo_por_hora': recurso.costo_por_hora,
                'horas_asignadas': recurso.horas_asignadas,
                'fecha_inicio': recurso.fecha_inicio,
                'fecha_fin': recurso.fecha_fin,
                'estado': 'borrador',  # Los recursos duplicados comienzan como borrador
            }
            self.env['creativeminds.recurso'].create(recurso_valores)
    
        # Duplicar las ideas asociadas al proyecto
        for idea in self.idea_ids:
            nueva_idea = idea.copy({'proyecto_id': nuevo_proyecto.id})
            
            # Duplicar los votos asociados a cada idea
            for voto in idea.vote_ids:
                voto.copy({'idea_id': nueva_idea.id})

        # Duplicar los feedbacks asociados al proyecto
        for feedback in self.feedback_ids:
            nuevo_feedback = feedback.copy({'proyecto_id': nuevo_proyecto.id})
            
            # Duplicar las acciones de feedback asociadas
            for accion in feedback.action_items:
                accion.copy({'feedback_id': nuevo_feedback.id})
            
            # Duplicar los archivos adjuntos asociados a la retroalimentación
            for archivo in feedback.attachment_ids:
                archivo.copy({'res_id': nuevo_feedback.id})
        
        # Mostrar el formulario del nuevo proyecto
        return {
            'name': 'Proyecto Duplicado',
            'type': 'ir.actions.act_window',
            'res_model': 'creativeminds.proyecto',
            'view_mode': 'form',
            'res_id': nuevo_proyecto.id,
            'target': 'current',
        }

    # Método para verificar que la descripción, cliente y responsable sean válidos antes de hacer cambios.
    @api.constrains('descripcion', 'cliente', 'responsable_id')
    def _verificar_campos_importantes(self):
        if self.descripcion and len(self.descripcion.strip()) < 10:
            raise ValidationError("La descripción del proyecto debe tener al menos 10 caracteres.")
        if self.estado in ['en_progreso', 'finalizado'] and not self.cliente:
            raise ValidationError("Debe especificar un cliente antes de cambiar el proyecto a 'En progreso' o 'Finalizado'.")
        if self.estado not in ['planificacion'] and not self.responsable_id:
            raise ValidationError("Debe asignar un responsable antes de avanzar con el proyecto.")

    # Método para verificar que los campos de planificación son correctos para proyectos de alta prioridad.
    @api.constrains('riesgos', 'hitos')
    def _verificar_campos_planificacion(self):
        if self.prioridad == 'alta':  # Si el proyecto es de alta prioridad.
            if not self.riesgos:  # Los riesgos deben estar definidos.
                raise ValidationError("Para proyectos de alta prioridad, es obligatorio definir los riesgos.")
            if not self.hitos:  # Los hitos deben estar definidos.
                raise ValidationError("Para proyectos de alta prioridad, es obligatorio definir los hitos/entregables.")

    # Método para verificar que haya al menos un recurso asignado antes de cambiar el estado a 'en progreso'.
    @api.constrains('recursos_ids')
    def _verificar_recursos_minimos(self):
        if self.estado != 'planificacion' and not self.recursos_ids:  # Si el proyecto no está en planificación y no tiene recursos asignados.
            raise ValidationError("Debe asignar al menos un recurso antes de iniciar el proyecto.")

    # Método para verificar que las fechas de inicio y fin, así como las tareas, sean coherentes.
    @api.constrains('fecha_inicio', 'fecha_fin', 'estado', 'tareas_ids')
    def _verificar_fechas_y_tareas(self):
        if self.estado == 'en_progreso':  # Si el proyecto está en progreso.
            if not self.fecha_inicio:  # La fecha de inicio debe estar definida.
                raise ValidationError("Debe establecer una fecha de inicio antes de comenzar el proyecto.")
            if not self.fecha_fin:  # La fecha de fin debe estar definida.
                raise ValidationError("Debe establecer una fecha de finalización antes de comenzar el proyecto.")
            if not self.tareas_ids:  # Deben existir al menos una tarea asociada.
                raise ValidationError("Debe crear al menos una tarea antes de iniciar el proyecto.")
            for tarea in self.tareas_ids:
                if tarea.fecha_inicio and tarea.fecha_inicio < self.fecha_inicio:  # La tarea no puede empezar antes de la fecha de inicio del proyecto.
                    raise ValidationError(f"La tarea '{tarea.nombre}' tiene una fecha de inicio anterior a la fecha de inicio del proyecto.")
                if tarea.fecha_fin and tarea.fecha_fin > self.fecha_fin:  # La tarea no puede terminar después de la fecha de finalización del proyecto.
                    raise ValidationError(f"La tarea '{tarea.nombre}' tiene una fecha de finalización posterior a la fecha de fin del proyecto.")

    # Función para ver las tareas del proyecto
    def ver_tareas(self):
        return {
            'name': 'Tareas del Proyecto',
            'type': 'ir.actions.act_window',
            'res_model': 'creativeminds.tarea',
            'view_mode': 'tree,form',
            'domain': [('proyecto_id', '=', self.id)],
            'context': {'default_proyecto_id': self.id},
            'target': 'current',
        }

    # Función para ver los recursos del proyecto
    def ver_recursos(self):
        return {
            'name': 'Recursos del Proyecto',
            'type': 'ir.actions.act_window',
            'res_model': 'creativeminds.recurso',
            'view_mode': 'tree,form',
            'domain': [('proyecto_id', '=', self.id)],
            'context': {'default_proyecto_id': self.id},
            'target': 'current',
        }

    # Función para ver los miembros del proyecto
    def ver_miembros(self):
        return {
            'name': 'Miembros del Proyecto',
            'type': 'ir.actions.act_window',
            'res_model': 'creativeminds.empleado',
            'view_mode': 'tree,form',
            'domain': [('proyecto_id', '=', self.id)],
            'context': {'default_proyecto_id': self.id},
            'target': 'current',
        }

    # Método para obtener las métricas
    def obtener_metricas(self):
        proyectos = self.env['creativeminds.proyecto'].search([])  # Obtener todos los proyectos
        tareas = self.env['creativeminds.tarea'].search([])  # Obtener todas las tareas
        empleados = self.env['creativeminds.empleado'].search([])  # Obtener todos los empleados
        
        # Métricas de proyectos
        total_proyectos = len(proyectos)
        proyectos_en_progreso = len(proyectos.filtered(lambda p: p.estado == 'en_progreso'))
        proyectos_finalizados = len(proyectos.filtered(lambda p: p.estado == 'finalizado'))
        proyectos_retrasados = len(proyectos.filtered(lambda p: p.fecha_fin and p.fecha_fin < fields.Date.today() and p.estado != 'finalizado'))
        
        # Métricas de progreso
        progreso_promedio = sum(proyecto.porcentaje_progreso for proyecto in proyectos) / total_proyectos if total_proyectos > 0 else 0
        
        # Cálculo de presupuestos
        presupuesto_total = sum(proyecto.presupuesto_estimado for proyecto in proyectos)
        costo_actual_total = sum(proyecto.costo_total_recursos for proyecto in proyectos)
        eficiencia_presupuestaria = (costo_actual_total / presupuesto_total * 100) if presupuesto_total > 0 else 0
        
        # Métricas de tareas
        total_tareas = len(tareas)
        tareas_completadas = len(tareas.filtered(lambda t: t.estado == 'completada'))
        tareas_pendientes = len(tareas.filtered(lambda t: t.estado == 'pendiente'))
        
        # Métricas de empleados disponibles
        empleados_disponibles = len(empleados.filtered(lambda e: e.disponibilidad == 'disponible'))

        # Retornar todas las métricas calculadas
        return {
            'total_proyectos': total_proyectos,
            'proyectos_en_progreso': proyectos_en_progreso,
            'proyectos_finalizados': proyectos_finalizados,
            'proyectos_retrasados': proyectos_retrasados,
            'progreso_promedio': progreso_promedio,
            'presupuesto_total': presupuesto_total,
            'costo_actual_total': costo_actual_total,
            'eficiencia_presupuestaria': eficiencia_presupuestaria,
            'total_tareas': total_tareas,
            'tareas_completadas': tareas_completadas,
            'tareas_pendientes': tareas_pendientes,
            'empleados_disponibles': empleados_disponibles
        }
    
    # Método para generar el informe
    def generar_informe_metricas(self):
        # Obtener las métricas
        metrics = self.obtener_metricas()

        # Usar el informe de QWeb
        return self.env.ref('creativeminds.action_report_metricas').report_action(self, data={'metrics': metrics})

class Recurso(models.Model):
    _name = 'creativeminds.recurso'
    _description = 'Recursos del Proyecto'

    # Campos básicos
    nombre = fields.Char(string='Nombre del Recurso', required=True)  # Nombre del recurso (obligatorio).
    empleado_id = fields.Many2many('creativeminds.empleado', string='Empleado')  # Relación con los empleados asignados al recurso.
    proyecto_id = fields.Many2one('creativeminds.proyecto', string='Proyecto')  # Relación con el proyecto al que pertenece el recurso.

    # Costos y presupuesto
    costo_por_hora = fields.Float(string='Costo por Hora')  # Costo por hora del recurso.
    horas_asignadas = fields.Float(string='Horas Asignadas')  # Número de horas asignadas al recurso.
    costo_total = fields.Float(string='Costo Total', compute='_compute_costo_total', store=True)  # Cálculo automático del costo total basado en el costo por hora y las horas asignadas.

    @api.depends('costo_por_hora', 'horas_asignadas')  # Cuando cambian el costo o las horas, se recalcula el costo total.
    def _compute_costo_total(self):
        for record in self:
            record.costo_total = record.costo_por_hora * record.horas_asignadas  # El costo total es el costo por hora multiplicado por las horas asignadas.

    # Fechas de asignación
    fecha_inicio = fields.Date(string='Fecha de Inicio')  # Fecha de inicio de la asignación del recurso.
    fecha_fin = fields.Date(string='Fecha de Fin')  # Fecha de finalización de la asignación del recurso.

    # Estado del recurso
    estado = fields.Selection([  # Definimos los posibles estados del recurso.
        ('borrador', 'Borrador'),  # Estado inicial.
        ('asignado', 'Asignado'),  # Cuando el recurso ya está asignado al proyecto.
        ('en_progreso', 'En Progreso'),  # Cuando el recurso está trabajando activamente en el proyecto.
        ('completado', 'Completado')  # Cuando el recurso ha finalizado su tarea.
    ], string='Estado', default='borrador')  # El estado por defecto es 'borrador'.
    
class Tarea(models.Model):
    _name = 'creativeminds.tarea'
    _description = 'Tareas del Proyecto'

    # Campos básicos
    proyecto_id = fields.Many2one('creativeminds.proyecto', string='Proyecto')  # Relación con el proyecto al que pertenece la tarea.
    nombre = fields.Char(string='Nombre de la Tarea', required=True)  # Nombre de la tarea (obligatorio).
    descripcion = fields.Text(string='Descripción')  # Descripción opcional de la tarea.
    responsable_id = fields.Many2one('creativeminds.empleado', string='Responsable')  # Relación con el empleado que es responsable de la tarea.
    fecha_inicio = fields.Date(string='Fecha de Inicio')  # Fecha en la que la tarea debería comenzar.
    fecha_fin = fields.Date(string='Fecha de Finalización')  # Fecha en la que la tarea debe finalizar.
    estado = fields.Selection([  # Selección de estados de la tarea.
        ('pendiente', 'Por hacer'),  # Estado cuando la tarea aún no se ha comenzado.
        ('en_progreso', 'En progreso'),  # Estado cuando la tarea está siendo trabajada.
        ('completada', 'Completada'),  # Estado cuando la tarea ha sido finalizada.
    ], string='Estado', default='pendiente')  # El estado inicial es "pendiente" por defecto.

    # Método de validación de fechas
    @api.constrains('fecha_inicio', 'fecha_fin')  # Este decorador valida las fechas de inicio y fin.
    def _verificar_fechas_tarea(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:  # Si la fecha de inicio es mayor que la de fin, lanza un error.
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de finalización.")  # Lanza un error de validación si las fechas no son correctas.

#Indicadores de Desempeño
class KPI(models.Model):
    _name = 'creativeminds.kpi'
    _description = 'Indicadores Clave de Rendimiento'

    # Campos de datos
    proyecto_id = fields.Many2one('creativeminds.proyecto', string='Proyecto')  # Relación con el proyecto al que pertenece el KPI.
    nombre = fields.Char(string='Nombre del KPI', required=True)  # Nombre del KPI, que es obligatorio.
    valor = fields.Float(string='Valor')  # Valor actual del KPI, que puede ser un número decimal.
    objetivo = fields.Float(string='Objetivo')  # Objetivo o meta del KPI, también como número decimal.

class Empleado(models.Model):
    _name = 'creativeminds.empleado'
    _description = 'Empleados del Proyecto'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    partner_id = fields.Many2one('res.partner', string='Contacto Asociado', required=True)  # Relación Many2one con el modelo 'res.partner' para asociar un contacto.
    name = fields.Char(string='Nombre', required=True)  # Campo de texto para almacenar el nombre del empleado (requerido).
    dni = fields.Char(string='DNI', size=9, required=True)  # Campo de texto para almacenar el DNI del empleado (requerido, con un tamaño máximo de 9 caracteres).
    apellido1 = fields.Char(string='Primer apellido')  # Campo de texto para almacenar el primer apellido del empleado.
    apellido2 = fields.Char(string='Segundo apellido')  # Campo de texto para almacenar el segundo apellido del empleado.
    fecha_nacimiento = fields.Date(string='Fecha de nacimiento')  # Campo de fecha para almacenar la fecha de nacimiento del empleado.
    fecha_incorporacion = fields.Date(string='Fecha incorporacion', default=lambda self: fields.Datetime.now(), readonly=True)  # Fecha de incorporación con valor por defecto de la fecha y hora actual, solo lectura.
    foto = fields.Image(string='Foto', max_width=200, max_height=200)  # Campo de imagen para almacenar la foto del empleado con un tamaño máximo de 200x200 píxeles.
    proyecto_id = fields.Many2many('creativeminds.proyecto', string='Proyectos')  # Relación Many2many con el modelo 'creativeminds.proyecto' para asociar proyectos al empleado.
    departamento = fields.Char(string='Departamento')  # Campo de texto para almacenar el departamento del empleado.
    puesto = fields.Char(string='Puesto')  # Campo de texto para almacenar el puesto del empleado.
    equipo_id = fields.Many2many('creativeminds.equipo', string='Equipos')  # Relación Many2many con el modelo 'creativeminds.equipo' para asociar equipos al empleado.
    phone = fields.Char(string='Teléfono')
    email = fields.Char(string='Correo Electrónico')
    tareas_ids = fields.One2many('creativeminds.tarea', 'responsable_id',string='Tareas')  # Tareas asociadas al empleado
    
    
    
    
    # Estado de disponibilidad
    disponibilidad = fields.Selection([  # Campo para gestionar la disponibilidad del empleado.
        ('disponible', 'Disponible'),  # El empleado está disponible para trabajar.
        ('asignado', 'Asignado'),  # El empleado está asignado a un proyecto.
        ('parcial', 'Parcialmente Disponible'),  # El empleado está parcialmente disponible.
        ('no_disponible', 'No Disponible')  # El empleado no está disponible.
    ], string='Disponibilidad', default='disponible')  # Valor por defecto es "disponible".

    # Restricción en el campo DNI: formato válido
    @api.constrains('dni')
    def _check_dni(self):
        regex = re.compile(r'[0-9]{8}[A-Z]\Z', re.I)  # Expresión regular para verificar el formato correcto del DNI (8 dígitos seguidos de una letra).
        for record in self:
            if not regex.match(record.dni):  # Si el formato no es válido, lanza una excepción.
                raise ValidationError('ERROR. Formato DNI incorrecto.')

    @api.constrains('fecha_nacimiento')
    def _check_edad_minima(self):
        for record in self:
            if record.fecha_nacimiento:
                # Calcular la edad actual basada en la fecha de nacimiento
                edad = relativedelta(date.today(), record.fecha_nacimiento).years
                if edad < 16:
                    raise ValidationError("El empleado debe tener al menos 16 años para poder trabajar.")
                if record.fecha_nacimiento > date.today():
                    raise ValidationError("La fecha de nacimiento no puede estar en el futuro.")


    # Restricción SQL: asegura que el DNI sea único en la base de datos.
    _sql_constraints = [
        ('DNI_unico', 'UNIQUE(dni)', "El DNI debe ser único")  # Restricción de unicidad en el campo DNI.
    ]

    @api.model
    def create(self, vals):
        record = super(Empleado, self).create(vals)
        
        # Enviar una notificación al crear el empleado
        record.message_post(
            body=f"Se ha creado un nuevo empleado: {record.name}.",
            subject="Nuevo Empleado",
            partner_ids=[record.partner_id.id]  # Enviamos el mensaje al partner (empleado) creado
        )
        return record
    
class Equipo(models.Model):
    _name = 'creativeminds.equipo'
    _description = 'Equipos de Trabajo'

    # Campos básicos de información del equipo
    nombre = fields.Char(string='Nombre', required=True)  # Nombre del equipo, obligatorio.
    empleado_id = fields.Many2many('creativeminds.empleado', string='Empleado')  # Relación de muchos a muchos con los empleados del equipo.
    responsable_id = fields.Many2one('creativeminds.empleado', string='Responsable')  # Relación con un solo responsable del equipo.
    descripcion = fields.Text(string='Descripcion del equipo')  # Descripción del equipo, opcional.
    
    # Campo calculado: número de miembros en el equipo
    n_miembros = fields.Integer(string='Número de Miembros', compute='_compute_n_miembros')  # Número de miembros calculado dinámicamente.

    # Método para calcular el número de miembros en el equipo
    def _compute_n_miembros(self):
        for equipo in self:
            equipo.n_miembros = len(equipo.empleado_id)  # Asigna el número de miembros en función de la cantidad de empleados asociados al equipo.

class IdeaEvaluation(models.Model):
    _name = 'creativeminds.idea'
    _description = 'Evaluación de Ideas'
    
    name = fields.Char('Nombre de la Idea', required=True)
    proyecto_id = fields.Many2one('creativeminds.proyecto', string='Proyecto')  # Relación con el proyecto al que pertenece.
    creator_id = fields.Many2one('creativeminds.empleado', string='Empleado')
    description = fields.Html('Descripción')
    pros = fields.Text('Pros')
    cons = fields.Text('Contras')
    vote_ids = fields.One2many('creativeminds.idea.vote', 'idea_id', 'Votos')
    score = fields.Float('Puntuación', compute='_compute_score')
    feasibility = fields.Selection([
        ('1', 'Muy difícil'),
        ('2', 'Difícil'),
        ('3', 'Moderado'),
        ('4', 'Factible'),
        ('5', 'Muy factible')
    ], string='Viabilidad')
    impact = fields.Selection([
        ('1', 'Muy bajo'),
        ('2', 'Bajo'),
        ('3', 'Moderado'),
        ('4', 'Alto'),
        ('5', 'Muy alto')
    ], string='Impacto')

    @api.depends('vote_ids.score')
    def _compute_score(self):
        for record in self:
            # Get all the votes related to the current IdeaEvaluation record
            votes = record.vote_ids
            if votes:
                # Calculate the average score
                total_score = sum(vote.score for vote in votes)
                num_votes = len(votes)
                record.score = total_score / num_votes if num_votes > 0 else 0
            else:
                # No votes yet, score is 0
                record.score = 0

class IdeaVote(models.Model):
    _name = 'creativeminds.idea.vote'
    _description = 'Votos para Evaluación de Ideas'
    
    idea_id = fields.Many2one('creativeminds.idea', string='Idea', required=True)
    empleado_id = fields.Many2one('creativeminds.empleado', string='Empleado', required=True)
    score = fields.Float('Puntuación', required=True)
    comment = fields.Text('Comentario')

class ClientFeedback(models.Model):
    _name = 'creativeminds.feedback'
    _description = 'Retroalimentación del Cliente'
    
    proyecto_id = fields.Many2one('creativeminds.proyecto', string='Proyecto', required=True)  # Relación con el proyecto al que pertenece.
    date = fields.Date('Fecha', default=fields.Date.today)
    cliente = fields.Char(string='Cliente')  # Cliente asociado al feedback
    feedback_text = fields.Html('Comentarios')
    positive_points = fields.Text('Puntos Positivos')
    improvement_points = fields.Text('Puntos de Mejora')
    action_items = fields.One2many('creativeminds.feedback.action', 'feedback_id', 'Acciones a Realizar')
    attachment_ids = fields.Many2many('ir.attachment', string='Archivos Adjuntos')
    priority = fields.Selection([
        ('0', 'Sugerencia'),
        ('1', 'Baja'),
        ('2', 'Media'),
        ('3', 'Alta'),
        ('4', 'Crítica')
    ], string='Prioridad', default='1')

class FeedbackAction(models.Model):
    _name = 'creativeminds.feedback.action'
    _description = 'Acción a Realizar para Feedback'

    feedback_id = fields.Many2one('creativeminds.feedback', string='Retroalimentación', readonly=False,required=True)
    action_text = fields.Text('Descripción de la Acción')
    assigned_to = fields.Many2one('creativeminds.empleado', string='Asignado a')
    due_date = fields.Date(string="Fecha Límite")
    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('in_progress', 'En Progreso'),
        ('done', 'Hecho')
    ], string='Estado', default='pending')
    
    @api.model
    def create(self, vals):
        if 'default_feedback_id' in self.env.context:
            vals['feedback_id'] = self.env.context['default_feedback_id']
        return super(FeedbackAction, self).create(vals)
    
    @api.constrains('due_date')
    def _check_due_date(self):
        for record in self:
            if record.due_date and record.due_date < date.today():
                raise ValidationError("La fecha límite no puede ser anterior a la fecha actual.")
