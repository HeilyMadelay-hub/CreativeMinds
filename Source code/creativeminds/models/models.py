from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date
import re
from dateutil.relativedelta import relativedelta  
from odoo.exceptions import UserError
import requests
import json

class Proyecto(models.Model):
    _name = 'creativeminds.proyecto'
    _description = 'Proyecto'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Campos básicos
    proyecto_id = fields.Integer(string='Id del Proyecto', required=True)
    nombre = fields.Char(string='Nombre del Proyecto', required=True)
    empleado_id = fields.Many2many('creativeminds.empleado', string='Empleado')
    costo_por_hora = fields.Float(string='Costo por Hora')
    horas_asignadas = fields.Float(string='Horas Asignadas') 
    costo_total = fields.Float(string='Costo Total', compute='_calcular_costo_total', store=True) 
    descripcion = fields.Text(string='Descripción del Proyecto')
    cliente = fields.Char(string='Cliente')
    horas_trabajadas_ids = fields.One2many(
        'creativeminds.horas_trabajadas',
        'proyecto_id',
        string="Horas Trabajadas"
    )

    @api.depends('costo_por_hora', 'horas_asignadas')
    def _calcular_costo_total(self):
        self.costo_total = self.costo_por_hora * self.horas_asignadas


    @api.constrains('costo_por_hora', 'horas_asignadas')
    def _verificar_costo_y_horas(self):
        if self.costo_por_hora < 0 or self.horas_asignadas < 0:
            raise ValidationError("El costo por hora y las horas asignadas deben ser valores positivos.")
   
    # Estados y seguimiento
    estado = fields.Selection([
        ('planificacion', 'En planificación'),
        ('en_progreso', 'En progreso'),
        ('finalizado', 'Finalizado'),
        ('detenido', 'Detenido'),
    ], string='Estado del Proyecto', default='planificacion', tracking=True)
    
    porcentaje_progreso = fields.Float(
        string='Porcentaje de Progreso',
        compute='_calcular_progreso',
        store=True,
        tracking=True
    )
    
    # Fechas
    fecha_inicio = fields.Date(string='Fecha de Inicio')
    fecha_fin = fields.Date(string='Fecha de Finalización')
    
    # Prioridad y responsables
    prioridad = fields.Selection([
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
    ], string='Prioridad', default='media')
    responsable_id = fields.Many2one('creativeminds.empleado', string='Responsable')
    
    # Presupuesto y recursos
    presupuesto_estimado = fields.Float(string='Presupuesto Estimado')
    recursos_ids = fields.One2many('creativeminds.recurso', 'proyecto_id', string='Recursos Asignados')
    costo_total_recursos = fields.Float(string='Costo Total de Recursos', 
                                     compute='_calcular_costo_total_recursos', 
                                     store=True)

    @api.depends('recursos_ids.costo_total')
    def _calcular_costo_total_recursos(self):
        self.costo_total_recursos = sum(self.recursos_ids.mapped('costo_total'))

    @api.constrains('presupuesto_estimado', 'costo_total_recursos')
    def _verificar_presupuesto(self):
        if self.costo_total_recursos > self.presupuesto_estimado:
            raise ValidationError(
                f"El costo total de recursos ({self.costo_total_recursos}) "
                f"excede el presupuesto estimado ({self.presupuesto_estimado})"
            )


    # Relaciones
    tareas_ids = fields.One2many('creativeminds.tarea', 'proyecto_id', string='Tareas')
    indicadores_ids = fields.One2many('creativeminds.kpi', 'proyecto_id', string='Indicadores de Desempeño')


    imagen_proyecto = fields.Binary(string='Imagen del Proyecto', attachment=True)
    imagen_filename = fields.Char(string='Nombre del archivo de imagen')

    documentacion_tecnica = fields.Binary(string='Documentación Técnica', attachment=True)
    documentacion_filename = fields.Char(string='Nombre del archivo de documentación')

    archivos_adicionales = fields.Many2many(
        'ir.attachment',
        'creativeminds_attachment_rel',
        'creativeminds_id',
        'attachment_id',
        string='Archivos Adicionales'
    )
    
    # Campos de texto adicionales
    colaboradores = fields.Text(string='Agencias Colaboradoras')
    riesgos = fields.Text(string='Riesgos')
    hitos = fields.Text(string='Hitos/Entregables')
    dependencias = fields.Text(string='Dependencias')
    comentarios = fields.Text(string='Comentarios y Notas')
    
    # Configuración
    recordatorios_automaticos = fields.Boolean(string='Activar Recordatorios Automáticos')

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _verificar_fechas_proyecto(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de finalización.")

    @api.constrains('presupuesto_estimado')
    def _verificar_presupuesto_estimado(self):
        if self.presupuesto_estimado <= 0:
            raise ValidationError("El presupuesto estimado debe ser mayor que cero.")
        num_recursos = len(self.recursos_ids)
        num_tareas = len(self.tareas_ids)
        presupuesto_requerido = (num_recursos * 500) + (num_tareas * 200)
        if (num_recursos > 0 or num_tareas > 0) and self.presupuesto_estimado < presupuesto_requerido:
            raise ValidationError(
                f"El presupuesto ({self.presupuesto_estimado}) es insuficiente. "
                f"Se requieren al menos {round(presupuesto_requerido, 2)} para cubrir recursos y tareas."
            )


    @api.model
    def create(self, valores):
        proyecto = super(Proyecto, self).create(valores)
        if proyecto.recordatorios_automaticos and proyecto.responsable_id:
            self.env['creativeminds.tarea'].create({
                'nombre': f'Tarea inicial de proyecto: {proyecto.nombre}',
                'proyecto_id': proyecto.id,
                'responsable_id': proyecto.responsable_id.id,
                'estado': 'pendiente',
            })
            self._enviar_recordatorio(proyecto)
        return proyecto

    
    def actualizar_progreso_indicador(self):
        indicador = self.env['creativeminds.indicador'].search([
            ('proyecto_id', '=', self.id),
            ('nombre', '=', 'Progreso del Proyecto')
        ], limit=1)
        if indicador:
            indicador.write({'valor': self.porcentaje_progreso})
        return True

    def enviar_notificacion_proyecto(self, tipo_notificacion='estado'):
        if not self.responsable_id:
            return
        asunto = f"Cambio de Estado: Proyecto {self.nombre}" if tipo_notificacion == 'estado' else f"Actualización de Progreso: Proyecto {self.nombre}"
        mensaje = f"<p>Hola {self.responsable_id.name},</p>"
        mensaje += f"<p>El estado del proyecto <b>{self.nombre}</b> ha cambiado a <b>{dict(self._fields['estado'].selection).get(self.estado)}</b>.</p>"
        mensaje += f"<p>Progreso actual: {round(self.porcentaje_progreso, 2)}%</p>"
        self.message_post(
            body=mensaje,
            subject=asunto,
            partner_ids=[self.responsable_id.partner_id.id]
        )

    def _enviar_recordatorio(self, proyecto):
        if not proyecto.responsable_id:
            return
        mensaje = f"""
            <p>Estimado {proyecto.responsable_id.name},</p>
            <p>Este es un recordatorio de que el proyecto <b>{proyecto.nombre}</b> tiene tareas pendientes.</p>
            <p>Por favor, asegúrese de revisar el progreso y continuar con las tareas.</p>
            <p>Saludos,<br>Equipo de gestión de proyectos</p>
        """
        proyecto.message_post(
            body=mensaje,
            subject=f"Recordatorio: Proyecto {proyecto.nombre} - Tareas pendientes",
            partner_ids=[proyecto.responsable_id.partner_id.id]
        )
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

    @api.depends('tareas_ids.estado')
    def _calcular_progreso(self):
        total_tareas = len(self.tareas_ids)
        tareas_completadas = len(self.tareas_ids.filtered(lambda t: t.estado == 'completada'))
        self.porcentaje_progreso = (tareas_completadas / total_tareas * 100) if total_tareas > 0 else 0.0
 
    def obtener_resumen_proyecto(self):
        self.ensure_one()
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

    @api.constrains('descripcion', 'cliente', 'responsable_id')
    def _verificar_campos_importantes(self):
        if self.descripcion and len(self.descripcion.strip()) < 10:
            raise ValidationError("La descripción del proyecto debe tener al menos 10 caracteres.")
        if self.estado in ['en_progreso', 'finalizado'] and not self.cliente:
            raise ValidationError("Debe especificar un cliente antes de cambiar el proyecto a 'En progreso' o 'Finalizado'.")
        if self.estado != 'planificacion' and not self.responsable_id:
            raise ValidationError("Debe asignar un responsable antes de avanzar con el proyecto.")

    @api.constrains('riesgos', 'hitos')
    def _verificar_campos_planificacion(self):
        if self.prioridad == 'alta':
            if not self.riesgos:
                raise ValidationError("Para proyectos de alta prioridad, es obligatorio definir los riesgos.")
            if not self.hitos:
                raise ValidationError("Para proyectos de alta prioridad, es obligatorio definir los hitos/entregables.")

    @api.constrains('recursos_ids')
    def _verificar_recursos_minimos(self):
        if self.estado != 'planificacion' and not self.recursos_ids:
            raise ValidationError("Debe asignar al menos un recurso antes de iniciar el proyecto.")

    @api.constrains('fecha_inicio', 'fecha_fin', 'estado', 'tareas_ids')
    def _verificar_fechas_y_tareas(self):
        if self.estado == 'en_progreso':
            if not self.fecha_inicio:
                raise ValidationError("Debe establecer una fecha de inicio antes de comenzar el proyecto.")
            if not self.fecha_fin:
                raise ValidationError("Debe establecer una fecha de finalización antes de comenzar el proyecto.")
            if not self.tareas_ids:
                raise ValidationError("Debe crear al menos una tarea antes de iniciar el proyecto.")
            for tarea in self.tareas_ids:
                if tarea.fecha_inicio and tarea.fecha_inicio < self.fecha_inicio:
                    raise ValidationError(f"La tarea '{tarea.nombre}' tiene una fecha de inicio anterior a la fecha de inicio del proyecto.")
                if tarea.fecha_fin and tarea.fecha_fin > self.fecha_fin:
                    raise ValidationError(f"La tarea '{tarea.nombre}' tiene una fecha de finalización posterior a la fecha de fin del proyecto.")


     # Para ver tareas del proyecto
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

    # Para ver recursos del proyecto
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

    # Para ver miembros del proyecto
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

    nombre = fields.Char(string='Nombre del Recurso', required=True)
    empleado_id = fields.Many2many('creativeminds.empleado', string='Empleado')
    proyecto_id = fields.Many2one('creativeminds.proyecto', string='Proyecto')
    
    # Costos y presupuesto
    costo_por_hora = fields.Float(string='Costo por Hora')
    horas_asignadas = fields.Float(string='Horas Asignadas')
    costo_total = fields.Float(string='Costo Total', compute='_compute_costo_total', store=True)
    
    @api.depends('costo_por_hora', 'horas_asignadas')
    def _compute_costo_total(self):
        for record in self:
            record.costo_total = record.costo_por_hora * record.horas_asignadas

    # Fechas de asignación
    fecha_inicio = fields.Date(string='Fecha de Inicio')
    fecha_fin = fields.Date(string='Fecha de Fin')
    
    # Estado del recurso
    estado = fields.Selection([
        ('borrador', 'Borrador'),
        ('asignado', 'Asignado'),
        ('en_progreso', 'En Progreso'),
        ('completado', 'Completado')
    ], string='Estado', default='borrador')

    
class Tarea(models.Model):
    _name = 'creativeminds.tarea'
    _description = 'Tareas del Proyecto'

    proyecto_id = fields.Many2one('creativeminds.proyecto', string='Proyecto')
    nombre = fields.Char(string='Nombre de la Tarea', required=True)
    descripcion = fields.Text(string='Descripción')
    responsable_id = fields.Many2one('creativeminds.empleado', string='Responsable')
    fecha_inicio = fields.Date(string='Fecha de Inicio')
    fecha_fin = fields.Date(string='Fecha de Finalización')
    estado = fields.Selection([
        ('pendiente', 'Por hacer'),
        ('en_progreso', 'En progreso'),
        ('completada', 'Completada'),
    ], string='Estado', default='pendiente')

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _verificar_fechas_tarea(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de finalización.")


#Indicadores de Desempeño
class KPI(models.Model):
    _name = 'creativeminds.kpi'
    _description = 'Indicadores Clave de Rendimiento'

    proyecto_id = fields.Many2one('creativeminds.proyecto', string='Proyecto')
    nombre = fields.Char(string='Nombre del KPI', required=True)
    valor = fields.Float(string='Valor')
    objetivo = fields.Float(string='Objetivo')

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

    horas_trabajadas_ids = fields.One2many(
        'creativeminds.horas_trabajadas',
        'empleado_id',
        string="Horas Trabajadas"
    )
    
    @api.constrains('dni')
    def _check_dni(self):
        regex = re.compile(r'[0-9]{8}[A-Z]\Z', re.I)
        for record in self:
            if not regex.match(record.dni):
                raise ValidationError('ERROR. Formato DNI incorrecto. ')

    

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

    _sql_constraints = [
        ('DNI_unico', 'UNIQUE(dni)', "El DNI debe ser único")
    ]
class HorasTrabajadas(models.Model):
    _name = 'creativeminds.horas_trabajadas'
    _description = 'Horas Trabajadas'

    horas = fields.Float("Horas Trabajadas")
    empleado_id = fields.Many2one('creativeminds.empleado', string="Empleado", required=True)
    proyecto_id = fields.Many2one('creativeminds.proyecto', string="Proyecto", required=True)
    fecha = fields.Date("Fecha de Registro")
    
    @api.model
    def create(self, values):
        if values.get('empleado_id') and values.get('proyecto_id'):
            existing_record = self.search([
                ('empleado_id', '=', values['empleado_id']),
                ('proyecto_id', '=', values['proyecto_id']),
            ], limit=1)
            if existing_record:
                raise ValidationError("Ya existe un registro de horas trabajadas para este proyecto y empleado.")

        if not values.get("Fecha"):
            values['fecha'] = fields.Date.today()

        return super(HorasTrabajadas, self).create(values)

class Equipo(models.Model):
    _name = 'creativeminds.equipo'
    _description = 'Equipos de Trabajo'

    equipo_id = fields.Integer(string='ID Grupo', required=True)
    nombre = fields.Char(string='Nombre', required=True)
    empleado_id = fields.Many2many('creativeminds.empleado', string='Empleado')
    responsable_id = fields.Many2one('creativeminds.empleado', string='Responsable')
    descripcion = fields.Text(string='Descripcion del equipo')
    n_miembros = fields.Integer(string='Número de Miembros', compute='_compute_n_miembros')

    def _compute_n_miembros(self):
        for equipo in self:
            equipo.n_miembros = len(equipo.empleado_id)

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
    _name = 'creativeminds.control.panel'
    _description = 'Panel de Control'

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