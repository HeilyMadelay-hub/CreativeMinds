from odoo import models, fields, api  # Importa los módulos necesarios de Odoo para la creación de modelos y campos.
from odoo.exceptions import ValidationError  # Importa la excepción ValidationError para manejar errores de validación.
from datetime import date  # Importa el módulo date para trabajar con fechas.
import re  # Importa el módulo re para trabajar con expresiones regulares.
from dateutil.relativedelta import relativedelta  
from odoo.exceptions import UserError
import requests
import json

class Proyecto(models.Model):
    _name = 'creativeminds.proyecto'  # Nombre técnico del modelo en Odoo.
    _description = 'Proyecto'  # Descripción del modelo.
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Herencia de funcionalidades de seguimiento de mensajes (para notificaciones y conversaciones).

    # Campos básicos del proyecto
    proyecto_id = fields.Integer(string='Id del Proyecto', required=True)  # Identificador único del proyecto
    nombre = fields.Char(string='Nombre del Proyecto', required=True)  # Nombre del proyecto
    empleado_id = fields.Many2many('creativeminds.empleado', string='Empleado')  # Empleados asignados al proyecto
    costo_por_hora = fields.Float(string='Costo por Hora')  # Costo por hora de trabajo en el proyecto
    horas_asignadas = fields.Float(string='Horas Asignadas')  # Total de horas asignadas al proyecto
    costo_total = fields.Float(string='Costo Total', compute='_calcular_costo_total', store=True)  # Cálculo del costo total basado en las horas y costo por hora
    descripcion = fields.Text(string='Descripción del Proyecto')  # Descripción detallada del proyecto
    cliente = fields.Char(string='Cliente')  # Cliente asociado al proyecto

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
    responsable_id = fields.Many2one('creativeminds.empleado', string='Responsable')  # Responsable principal del proyecto
    
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
            self._enviar_recordatorio(proyecto)  # Enviamos un recordatorio al responsable.
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
            'proyecto_id': self.proyecto_id + 1,  # Incrementamos el ID para la copia
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
        if self.descripcion and len(self.descripcion.strip()) < 10:  # La descripción debe tener al menos 10 caracteres.
            raise ValidationError("La descripción del proyecto debe tener al menos 10 caracteres.")
        if self.estado in ['en_progreso', 'finalizado'] and not self.cliente:  # El cliente es obligatorio si el estado es 'en progreso' o 'finalizado'.
            raise ValidationError("Debe especificar un cliente antes de cambiar el proyecto a 'En progreso' o 'Finalizado'.")
        if self.estado != 'planificacion' and not self.responsable_id:  # El responsable es obligatorio si el proyecto no está en planificación.
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
    _inherit = ['mail.thread']

    empleado_id = fields.Integer(string='ID',required=True)
    partner_id = fields.Many2one('res.partner', string='Contacto Asociado')
    name = fields.Char(string='Nombre', required=True)
    dni = fields.Char(string ='DNI',size = 9, required=True)
    apellido1  = fields.Char(string='Primer apellido')
    apellido2  = fields.Char(string='Segundo apellido')
    fecha_nacimiento = fields.Date(string='Fecha de nacimiento')
    fecha_incorporacion  = fields.Date(string='Fecha incorporacion',default=lambda self: fields.Datetime.now(),readonly = True,)
    foto  = fields.Image(string='Foto',max_width=200,max_height=200,)
    proyecto_id = fields.Many2many('creativeminds.proyecto', string='Proyectos')
    departamento = fields.Char(string='Departamento')
    puesto = fields.Char(string='Puesto')
    equipo_id = fields.Many2many('creativeminds.equipo', string='Equipos')
    disponibilidad = fields.Selection([
        ('disponible', 'Disponible'),
        ('asignado', 'Asignado'),
        ('parcial', 'Parcialmente Disponible'),
        ('no_disponible', 'No Disponible')
    ], string='Disponibilidad', default='disponible')
    
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
    equipo_id = fields.Integer(string='ID Grupo', required=True)  # ID único del equipo, obligatorio.
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

class DashboardMetricas(models.Model):
    _name = 'creativeminds.metrica'
    _description = 'Métricas del Dashboard'

    panel_id = fields.Many2one('creativeminds.control.panel', string='Panel de Control')
    fecha_actualizacion = fields.Datetime(string='Fecha de Actualización')
    
    # Métricas generales
    total_proyectos = fields.Integer(string='Total de Proyectos')
    proyectos_en_progreso = fields.Integer(string='Proyectos en Progreso')
    proyectos_finalizados = fields.Integer(string='Proyectos Finalizados')
    proyectos_retrasados = fields.Integer(string='Proyectos Retrasados')
    progreso_promedio = fields.Float(string='Progreso Promedio (%)')
    presupuesto_total = fields.Float(string='Presupuesto Total')
    costo_actual_total = fields.Float(string='Costo Actual Total')
    eficiencia_presupuestaria = fields.Float(string='Eficiencia Presupuestaria (%)')
    total_tareas = fields.Integer(string='Total de Tareas')
    tareas_completadas = fields.Integer(string='Tareas Completadas')
    tareas_pendientes = fields.Integer(string='Tareas Pendientes')
    empleados_disponibles = fields.Integer(string='Empleados Disponibles')

class Recomendaciones(models.Model):
    _name = 'creativeminds.recomendacion'
    _description = 'Recomendaciones del Sistema'
    _order = 'prioridad asc'

    panel_id = fields.Many2one('creativeminds.control.panel', string='Panel de Control')
    descripcion = fields.Text(string='Descripción')
    prioridad = fields.Integer(string='Prioridad')
    fecha = fields.Date(string='Fecha')
    estado = fields.Selection([
        ('pendiente', 'Pendiente'),
        ('en_proceso', 'En Proceso'),
        ('implementada', 'Implementada'),
        ('descartada', 'Descartada')
    ], string='Estado', default='pendiente')
    notas = fields.Text(string='Notas')
class PanelDeControl(models.Model):
    _name = 'creativeminds.control.panel'  # Nombre técnico del modelo en Odoo.
    _description = 'Panel de Control'  # Descripción del modelo: se usa para gestionar un panel de control de proyectos.

    nombre = fields.Char(string='Nombre', required=True)
    proyectos_ids = fields.Many2many('creativeminds.proyecto', string='Proyectos en el Panel')
    configuracion = fields.Text(string='Configuración del Panel')

    # Campos para el análisis FODA
    fortalezas = fields.Text(string='Fortalezas')
    debilidades = fields.Text(string='Debilidades')
    oportunidades = fields.Text(string='Oportunidades')
    amenazas = fields.Text(string='Amenazas')
    
    # Campo para almacenar la fecha de la última actualización
    ultima_actualizacion = fields.Datetime(string='Última Actualización')
    
    @api.model
    def _ensure_default_record(self):
        """Asegura que exista al menos un registro en el modelo para mostrar el dashboard."""
        if not self.search([], limit=1):
            self.create({'nombre': 'Panel Global'})
        return True
    
    @api.model
    def _init_dashboard(self):
        self._ensure_default_record()
        return True
    
    @api.model
    def load_data_from_api(self):
        """Carga datos desde la API externa y actualiza registros en Odoo."""
        url = "http://127.0.0.1:5000/api/dashboard"  # Endpoint correcto
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                panel_default = self.search([], limit=1)
                
                if not panel_default:
                    panel_default = self.create({'nombre': 'Panel Global'})
                
                # 1. Procesar métricas generales
                if 'metricas' in data and panel_default:
                    metricas = data['metricas']
                    
                    # Crear o actualizar un registro de métricas
                    # Primero, buscar si ya existe un registro de métricas para este panel
                    metrica_existente = self.env['creativeminds.metrica'].search([
                        ('panel_id', '=', panel_default.id)
                    ], limit=1)
                    
                    metrica_values = {
                        'total_proyectos': metricas.get('total_proyectos', 0),
                        'proyectos_en_progreso': metricas.get('proyectos_en_progreso', 0),
                        'proyectos_finalizados': metricas.get('proyectos_finalizados', 0),
                        'proyectos_retrasados': metricas.get('proyectos_retrasados', 0),
                        'progreso_promedio': metricas.get('progreso_promedio', 0),
                        'presupuesto_total': metricas.get('presupuesto_total', 0),
                        'costo_actual_total': metricas.get('costo_actual_total', 0),
                        'eficiencia_presupuestaria': metricas.get('eficiencia_presupuestaria', 0),
                        'total_tareas': metricas.get('total_tareas', 0),
                        'tareas_completadas': metricas.get('tareas_completadas', 0),
                        'tareas_pendientes': metricas.get('tareas_pendientes', 0),
                        'empleados_disponibles': metricas.get('empleados_disponibles', 0),
                        'fecha_actualizacion': fields.Datetime.now(),
                        'panel_id': panel_default.id
                    }
                    
                    if metrica_existente:
                        metrica_existente.write(metrica_values)
                    else:
                        self.env['creativeminds.metrica'].create(metrica_values)
                
                # 2. Procesar proyectos destacados
                if 'proyectos_destacados' in data:
                    # Obtener los IDs de proyectos destacados para actualizar el panel
                    proyectos_destacados_ids = []
                    
                    for proyecto_data in data['proyectos_destacados']:
                        # Buscar si el proyecto ya existe
                        proyecto_existente = self.env['creativeminds.proyecto'].search([
                            ('proyecto_id', '=', proyecto_data.get('proyecto_id'))
                        ], limit=1)
                        
                        proyecto_values = {
                            'nombre': proyecto_data.get('nombre', ''),
                            'estado': proyecto_data.get('estado', 'planificacion'),
                            'fecha_inicio': proyecto_data.get('fecha_inicio', False),
                            'fecha_fin': proyecto_data.get('fecha_fin', False),
                            'presupuesto_estimado': proyecto_data.get('presupuesto_estimado', 0),
                            'costo_total_recursos': proyecto_data.get('costo_total_recursos', 0),
                            'porcentaje_progreso': proyecto_data.get('porcentaje_progreso', 0)
                        }
                        
                        if proyecto_existente:
                            proyecto_existente.write(proyecto_values)
                            proyectos_destacados_ids.append(proyecto_existente.id)
                        else:
                            proyecto_values['proyecto_id'] = proyecto_data.get('proyecto_id')
                            nuevo_proyecto = self.env['creativeminds.proyecto'].create(proyecto_values)
                            proyectos_destacados_ids.append(nuevo_proyecto.id)
                    
                    # Actualizar la relación many2many del panel con los proyectos destacados
                    if panel_default and proyectos_destacados_ids:
                        panel_default.write({
                            'proyectos_ids': [(6, 0, proyectos_destacados_ids)]  # Reemplaza todos los proyectos con los nuevos
                        })
                
                # 3. Procesar y guardar el análisis FODA (como ya te mostré antes)
                if 'analisis' in data and panel_default:
                    analisis = data['analisis']
                    
                    # Convertir listas a texto con formato
                    fortalezas = '\n'.join(['• ' + f for f in analisis.get('fortalezas', [])])
                    debilidades = '\n'.join(['• ' + d for d in analisis.get('debilidades', [])])
                    oportunidades = '\n'.join(['• ' + o for o in analisis.get('oportunidades', [])])
                    amenazas = '\n'.join(['• ' + a for a in analisis.get('amenazas', [])])
                    
                    panel_default.write({
                        'fortalezas': fortalezas,
                        'debilidades': debilidades,
                        'oportunidades': oportunidades,
                        'amenazas': amenazas,
                        'ultima_actualizacion': fields.Datetime.now()
                    })
                
                # 4. Procesar recomendaciones (opcional)
                if 'recomendaciones' in data and panel_default:
                    recomendaciones = data['recomendaciones']
                    
                    # Eliminar recomendaciones anteriores
                    self.env['creativeminds.recomendacion'].search([
                        ('panel_id', '=', panel_default.id)
                    ]).unlink()
                    
                    # Crear nuevas recomendaciones
                    for i, recomendacion_texto in enumerate(recomendaciones):
                        self.env['creativeminds.recomendacion'].create({
                            'panel_id': panel_default.id,
                            'descripcion': recomendacion_texto,
                            'prioridad': i + 1,  # Prioridad basada en el orden
                            'fecha': fields.Date.today()
                        })
                
                return {
                    'status': 'ok',
                    'message': 'Datos del dashboard cargados correctamente'
                }
            else:
                return {
                    'status': 'error',
                    'message': f"Error {response.status_code}: {response.text}"
                }
        except requests.exceptions.RequestException as e:
            raise UserError(f"Error al conectar con la API: {str(e)}")
