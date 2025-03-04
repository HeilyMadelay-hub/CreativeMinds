from flask import Flask, jsonify, request, Blueprint
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from sqlalchemy import create_engine
import logging
import os
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurar blueprints para organizar la API
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Configuración de conexión a Odoo
def get_odoo_connection():
    try:
        db_user = os.getenv('DB_USER', 'admin')
        db_password = os.getenv('DB_PASSWORD', 'admin')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'odoo')
        
        connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        engine = create_engine(connection_string)
        return engine
    except Exception as e:
        logger.error(f"Error al conectar con la base de datos: {str(e)}")
        return None

# Rutas de la API
@api_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar que la API está funcionando"""
    return jsonify({"status": "OK", "message": "Creative Minds Analytics API está funcionando correctamente"})

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Obtiene un resumen general del estado de todos los proyectos"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        # Consulta para proyectos
        proyectos_df = pd.read_sql("""
            SELECT 
                proyecto_id, nombre, estado, fecha_inicio, fecha_fin, 
                presupuesto_estimado, costo_total_recursos, porcentaje_progreso
            FROM 
                creativeminds_proyecto
        """, engine)
        
        # Consulta para tareas
        tareas_df = pd.read_sql("""
            SELECT 
                t.id, t.nombre, t.estado, t.fecha_comienzo, t.fecha_final, 
                t.proyecto_id, p.nombre as nombre_proyecto
            FROM 
                creativeminds_tarea t
            JOIN 
                creativeminds_proyecto p ON t.proyecto_id = p.id
        """, engine)
        
        # Consulta para empleados
        empleados_df = pd.read_sql("""
            SELECT 
                e.empleado_id, e.nombre, e.disponibilidad, e.departamento, e.puesto
            FROM 
                creativeminds_empleado e
        """, engine)
        
        # Métricas generales
        metricas = {
            "total_proyectos": len(proyectos_df),
            "proyectos_en_progreso": len(proyectos_df[proyectos_df['estado'] == 'en_progreso']),
            "proyectos_finalizados": len(proyectos_df[proyectos_df['estado'] == 'finalizado']),
            "proyectos_retrasados": _calcular_proyectos_retrasados(proyectos_df, tareas_df),
            "progreso_promedio": proyectos_df['porcentaje_progreso'].mean(),
            "presupuesto_total": proyectos_df['presupuesto_estimado'].sum(),
            "costo_actual_total": proyectos_df['costo_total_recursos'].sum(),
            "eficiencia_presupuestaria": _calcular_eficiencia_presupuestaria(proyectos_df),
            "total_tareas": len(tareas_df),
            "tareas_completadas": len(tareas_df[tareas_df['estado'] == 'completada']),
            "tareas_pendientes": len(tareas_df[tareas_df['estado'] == 'pendiente']),
            "empleados_disponibles": len(empleados_df[empleados_df['disponibilidad'] == 'disponible'])
        }
        
        # Proyectos principales (top 5 por progreso)
        top_proyectos = proyectos_df.sort_values('porcentaje_progreso', ascending=False).head(5)
        
        # Análisis de fortalezas y debilidades
        analisis = _analizar_fortalezas_debilidades(proyectos_df, tareas_df, empleados_df)
        
        # Recomendaciones para mejora
        recomendaciones = _generar_recomendaciones(proyectos_df, tareas_df, empleados_df, analisis)
        
        return jsonify({
            "metricas": metricas,
            "proyectos_destacados": top_proyectos.to_dict(orient='records'),
            "analisis": analisis,
            "recomendaciones": recomendaciones
        })
        
    except Exception as e:
        logger.error(f"Error en el dashboard: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/proyectos', methods=['GET'])
def get_proyectos():
    """Obtiene todos los proyectos con métricas detalladas"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        proyectos_df = pd.read_sql("""
            SELECT 
                p.*, 
                COUNT(DISTINCT t.id) as total_tareas,
                SUM(CASE WHEN t.estado = 'completada' THEN 1 ELSE 0 END) as tareas_completadas,
                COUNT(DISTINCT r.id) as total_recursos
            FROM 
                creativeminds_proyecto p
            LEFT JOIN 
                creativeminds_tarea t ON p.id = t.proyecto_id
            LEFT JOIN 
                creativeminds_recurso r ON p.id = r.proyecto_id
            GROUP BY 
                p.id
        """, engine)
        
        # Calcular métricas adicionales para cada proyecto
        proyectos_metricas = []
        for _, proyecto in proyectos_df.iterrows():
            # Calcular eficiencia y estado general
            eficiencia = _calcular_eficiencia_proyecto(proyecto)
            estado_salud = _determinar_estado_salud_proyecto(proyecto)
            
            # Añadir métricas específicas
            proyecto_data = proyecto.to_dict()
            proyecto_data["eficiencia"] = eficiencia
            proyecto_data["estado_salud"] = estado_salud
            proyecto_data["dias_restantes"] = _calcular_dias_restantes(proyecto)
            
            proyectos_metricas.append(proyecto_data)
        
        return jsonify({"proyectos": proyectos_metricas})
        
    except Exception as e:
        logger.error(f"Error al obtener proyectos: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/proyectos/<int:proyecto_id>', methods=['GET'])
def get_proyecto_detalle(proyecto_id):
    """Obtiene detalles completos de un proyecto específico con análisis profundo"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        # Obtener datos del proyecto
        proyecto_df = pd.read_sql(f"""
            SELECT * FROM creativeminds_proyecto WHERE id = {proyecto_id}
        """, engine)
        
        if proyecto_df.empty:
            return jsonify({"error": "Proyecto no encontrado"}), 404
        
        # Obtener tareas relacionadas
        tareas_df = pd.read_sql(f"""
            SELECT * FROM creativeminds_tarea WHERE proyecto_id = {proyecto_id}
        """, engine)
        
        # Obtener recursos relacionados
        recursos_df = pd.read_sql(f"""
            SELECT * FROM creativeminds_recurso WHERE proyecto_id = {proyecto_id}
        """, engine)
        
        # Obtener KPIs relacionados
        kpis_df = pd.read_sql(f"""
            SELECT * FROM creativeminds_kpi WHERE proyecto_id = {proyecto_id}
        """, engine)
        
        # Calcular métricas específicas del proyecto
        metricas_proyecto = _calcular_metricas_proyecto(proyecto_df.iloc[0], tareas_df, recursos_df, kpis_df)
        
        # Generar análisis personalizado
        analisis_proyecto = _analizar_proyecto(proyecto_df.iloc[0], tareas_df, recursos_df, kpis_df)
        
        # Generar recomendaciones específicas
        recomendaciones_proyecto = _generar_recomendaciones_proyecto(proyecto_df.iloc[0], tareas_df, recursos_df)
        
        return jsonify({
            "proyecto": proyecto_df.iloc[0].to_dict(),
            "tareas": tareas_df.to_dict(orient='records'),
            "recursos": recursos_df.to_dict(orient='records'),
            "kpis": kpis_df.to_dict(orient='records'),
            "metricas": metricas_proyecto,
            "analisis": analisis_proyecto,
            "recomendaciones": recomendaciones_proyecto
        })
        
    except Exception as e:
        logger.error(f"Error al obtener detalles del proyecto: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/empleados', methods=['GET'])
def get_empleados():
    """Obtiene datos de empleados con análisis de carga de trabajo y rendimiento"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        # Obtener datos de empleados
        empleados_df = pd.read_sql("""
            SELECT 
                e.*, 
                COUNT(DISTINCT pt.id) as total_proyectos,
                COUNT(DISTINCT t.id) as total_tareas,
                SUM(CASE WHEN t.estado = 'completada' THEN 1 ELSE 0 END) as tareas_completadas
            FROM 
                creativeminds_empleado e
            LEFT JOIN 
                creativeminds_proyecto_empleado_rel pe ON e.id = pe.empleado_id
            LEFT JOIN 
                creativeminds_proyecto pt ON pe.proyecto_id = pt.id
            LEFT JOIN 
                creativeminds_tarea t ON t.responsable_id = e.id
            GROUP BY 
                e.id
        """, engine)
        
        # Calcular métricas por empleado
        empleados_metricas = []
        for _, empleado in empleados_df.iterrows():
            empleado_data = empleado.to_dict()
            
            # Calcular tasa de completitud
            if empleado_data["total_tareas"] > 0:
                empleado_data["tasa_completitud"] = empleado_data["tareas_completadas"] / empleado_data["total_tareas"]
            else:
                empleado_data["tasa_completitud"] = 0
            
            # Calcular carga de trabajo
            empleado_data["carga_trabajo"] = _calcular_carga_trabajo(empleado_data)
            
            empleados_metricas.append(empleado_data)
        
        return jsonify({"empleados": empleados_metricas})
        
    except Exception as e:
        logger.error(f"Error al obtener datos de empleados: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/metricas/rendimiento', methods=['GET'])
def get_metricas_rendimiento():
    """Obtiene métricas de rendimiento general por departamento y equipo"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
            
        # Métricas por departamento
        departamentos_df = pd.read_sql("""
            SELECT 
                e.departamento,
                COUNT(DISTINCT e.id) as total_empleados,
                COUNT(DISTINCT p.id) as total_proyectos,
                AVG(p.porcentaje_progreso) as progreso_promedio,
                SUM(p.costo_total_recursos) as costo_total,
                SUM(p.presupuesto_estimado) as presupuesto_total
            FROM 
                creativeminds_empleado e
            LEFT JOIN 
                creativeminds_proyecto_empleado_rel pe ON e.id = pe.empleado_id
            LEFT JOIN 
                creativeminds_proyecto p ON pe.proyecto_id = p.id
            WHERE 
                e.departamento IS NOT NULL
            GROUP BY 
                e.departamento
        """, engine)
        
        # Métricas por equipo
        equipos_df = pd.read_sql("""
            SELECT 
                eq.id, eq.nombre,
                COUNT(DISTINCT em.id) as total_miembros,
                COUNT(DISTINCT p.id) as total_proyectos,
                AVG(p.porcentaje_progreso) as progreso_promedio
            FROM 
                creativeminds_equipo eq
            LEFT JOIN 
                creativeminds_equipo_empleado_rel ee ON eq.id = ee.equipo_id
            LEFT JOIN 
                creativeminds_empleado em ON ee.empleado_id = em.id
            LEFT JOIN 
                creativeminds_proyecto_empleado_rel pe ON em.id = pe.empleado_id
            LEFT JOIN 
                creativeminds_proyecto p ON pe.proyecto_id = p.id
            GROUP BY 
                eq.id, eq.nombre
        """, engine)
        
        # Añadir eficiencia por departamento
        for i, dept in departamentos_df.iterrows():
            if dept['presupuesto_total'] > 0:
                departamentos_df.at[i, 'eficiencia_presupuestaria'] = (
                    1 - (dept['costo_total'] / dept['presupuesto_total'])
                ) * 100
            else:
                departamentos_df.at[i, 'eficiencia_presupuestaria'] = 0
        
        return jsonify({
            "departamentos": departamentos_df.to_dict(orient='records'),
            "equipos": equipos_df.to_dict(orient='records')
        })
        
    except Exception as e:
        logger.error(f"Error al obtener métricas de rendimiento: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/metricas/historicas', methods=['GET'])
def get_metricas_historicas():
    """Obtiene métricas históricas para análisis de tendencias"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        # Obtener proyectos con fechas
        proyectos_df = pd.read_sql("""
            SELECT 
                id, nombre, estado, fecha_inicio, fecha_fin, 
                presupuesto_estimado, costo_total_recursos, porcentaje_progreso
            FROM 
                creativeminds_proyecto
            WHERE 
                fecha_inicio IS NOT NULL
        """, engine)
        
        # Convertir fechas a formato datetime
        proyectos_df['fecha_inicio'] = pd.to_datetime(proyectos_df['fecha_inicio'])
        proyectos_df['fecha_fin'] = pd.to_datetime(proyectos_df['fecha_fin'])
        
        # Obtener el rango de tiempo (último año)
        hoy = datetime.now()
        inicio_periodo = hoy - timedelta(days=365)
        
        # Filtrar proyectos del último año
        proyectos_periodo = proyectos_df[proyectos_df['fecha_inicio'] >= inicio_periodo]
        
        # Crear series temporales por mes
        proyectos_periodo['mes_inicio'] = proyectos_periodo['fecha_inicio'].dt.to_period('M')
        
        # Agrupar por mes y calcular métricas
        metricas_mensuales = []
        
        for mes in pd.period_range(start=inicio_periodo, end=hoy, freq='M'):
            proyectos_mes = proyectos_periodo[proyectos_periodo['mes_inicio'] == mes]
            
            if not proyectos_mes.empty:
                metricas_mes = {
                    "mes": mes.strftime('%Y-%m'),
                    "proyectos_iniciados": len(proyectos_mes),
                    "presupuesto_total": proyectos_mes['presupuesto_estimado'].sum(),
                    "costo_total": proyectos_mes['costo_total_recursos'].sum(),
                    "progreso_promedio": proyectos_mes['porcentaje_progreso'].mean()
                }
                
                # Calcular eficiencia presupuestaria
                if metricas_mes["presupuesto_total"] > 0:
                    metricas_mes["eficiencia_presupuestaria"] = (
                        1 - (metricas_mes["costo_total"] / metricas_mes["presupuesto_total"])
                    ) * 100
                else:
                    metricas_mes["eficiencia_presupuestaria"] = 0
                
                metricas_mensuales.append(metricas_mes)
        
        # Tendencias y predicciones
        tendencias = _calcular_tendencias(metricas_mensuales)
        
        return jsonify({
            "metricas_mensuales": metricas_mensuales,
            "tendencias": tendencias
        })
        
    except Exception as e:
        logger.error(f"Error al obtener métricas históricas: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Funciones auxiliares para cálculos y análisis
def _calcular_proyectos_retrasados(proyectos_df, tareas_df):
    """Calcula el número de proyectos que están retrasados"""
    hoy = datetime.now().date()
    count = 0
    
    for _, proyecto in proyectos_df.iterrows():
        if proyecto['estado'] != 'finalizado' and proyecto['fecha_fin'] and pd.to_datetime(proyecto['fecha_fin']).date() < hoy:
            count += 1
            continue
            
        # Verificar tareas retrasadas
        tareas_proyecto = tareas_df[tareas_df['proyecto_id'] == proyecto['id']]
        for _, tarea in tareas_proyecto.iterrows():
            if tarea['estado'] != 'completada' and tarea['fecha_final'] and pd.to_datetime(tarea['fecha_final']).date() < hoy:
                count += 1
                break
                
    return count

def _calcular_eficiencia_presupuestaria(proyectos_df):
    """Calcula la eficiencia presupuestaria en porcentaje"""
    presupuesto_total = proyectos_df['presupuesto_estimado'].sum()
    costo_actual = proyectos_df['costo_total_recursos'].sum()
    
    if presupuesto_total > 0:
        return ((presupuesto_total - costo_actual) / presupuesto_total) * 100
    return 0

def _calcular_eficiencia_proyecto(proyecto):
    """Calcula la eficiencia de un proyecto específico"""
    if proyecto['presupuesto_estimado'] > 0:
        eficiencia_presupuesto = (1 - (proyecto['costo_total_recursos'] / proyecto['presupuesto_estimado'])) * 100
    else:
        eficiencia_presupuesto = 0
        
    if proyecto['total_tareas'] > 0:
        eficiencia_tareas = (proyecto['tareas_completadas'] / proyecto['total_tareas']) * 100
    else:
        eficiencia_tareas = 0
        
    # Ponderación: 60% presupuesto, 40% tareas
    return (eficiencia_presupuesto * 0.6) + (eficiencia_tareas * 0.4)

def _determinar_estado_salud_proyecto(proyecto):
    """Determina el estado de salud de un proyecto: Bueno, Regular, En riesgo, Crítico"""
    try:
        # Verificar si hay fecha de fin establecida y si está vencida
        hoy = datetime.now().date()
        fecha_fin = pd.to_datetime(proyecto['fecha_fin']).date() if pd.notna(proyecto['fecha_fin']) else None
        vencido = fecha_fin and fecha_fin < hoy and proyecto['estado'] != 'finalizado'
        
        # Calcular progreso esperado basado en fechas
        if fecha_fin and pd.notna(proyecto['fecha_inicio']):
            fecha_inicio = pd.to_datetime(proyecto['fecha_inicio']).date()
            duracion_total = (fecha_fin - fecha_inicio).days
            if duracion_total > 0:
                tiempo_transcurrido = (min(hoy, fecha_fin) - fecha_inicio).days
                progreso_esperado = (tiempo_transcurrido / duracion_total) * 100
                desviacion_progreso = proyecto['porcentaje_progreso'] - progreso_esperado
            else:
                desviacion_progreso = 0
        else:
            desviacion_progreso = 0
        
        # Calcular desviación presupuestaria
        if proyecto['presupuesto_estimado'] > 0:
            desviacion_presupuesto = (proyecto['costo_total_recursos'] / proyecto['presupuesto_estimado']) * 100 - 100
        else:
            desviacion_presupuesto = 0
        
        # Determinar estado de salud
        if vencido:
            return "Crítico"
        elif desviacion_progreso < -20 or desviacion_presupuesto > 20:
            return "En riesgo"
        elif desviacion_progreso < -10 or desviacion_presupuesto > 10:
            return "Regular"
        else:
            return "Bueno"
    except:
        return "No determinado"

def _calcular_dias_restantes(proyecto):
    """Calcula los días restantes para la finalización del proyecto"""
    hoy = datetime.now().date()
    
    if pd.notna(proyecto['fecha_fin']):
        fecha_fin = pd.to_datetime(proyecto['fecha_fin']).date()
        dias_restantes = (fecha_fin - hoy).days
        return max(0, dias_restantes)
    
    return None

def _calcular_metricas_proyecto(proyecto, tareas_df, recursos_df, kpis_df):
    """Calcula métricas detalladas para un proyecto específico"""
    hoy = datetime.now().date()
    
    # Cálculos básicos
    total_tareas = len(tareas_df)
    tareas_completadas = len(tareas_df[tareas_df['estado'] == 'completada'])
    tareas_pendientes = len(tareas_df[tareas_df['estado'] == 'pendiente'])
    tareas_en_progreso = len(tareas_df[tareas_df['estado'] == 'en_progreso'])
    
    # Cálculos de tiempo
    fecha_inicio = pd.to_datetime(proyecto['fecha_inicio']).date() if pd.notna(proyecto['fecha_inicio']) else None
    fecha_fin = pd.to_datetime(proyecto['fecha_fin']).date() if pd.notna(proyecto['fecha_fin']) else None
    
    if fecha_inicio and fecha_fin:
        duracion_total = (fecha_fin - fecha_inicio).days
        duracion_transcurrida = (hoy - fecha_inicio).days if hoy > fecha_inicio else 0
        porcentaje_tiempo_transcurrido = (duracion_transcurrida / duracion_total) * 100 if duracion_total > 0 else 0
        desviacion_tiempo = porcentaje_tiempo_transcurrido - proyecto['porcentaje_progreso']
    else:
        duracion_total = None
        duracion_transcurrida = None
        porcentaje_tiempo_transcurrido = None
        desviacion_tiempo = None
    
    # Cálculos de presupuesto
    if proyecto['presupuesto_estimado'] > 0:
        porcentaje_presupuesto_usado = (proyecto['costo_total_recursos'] / proyecto['presupuesto_estimado']) * 100
        presupuesto_restante = proyecto['presupuesto_estimado'] - proyecto['costo_total_recursos']
    else:
        porcentaje_presupuesto_usado = 0
        presupuesto_restante = 0
    
    # Valor ganado (EV) - método de gestión de proyectos
    valor_planificado = proyecto['presupuesto_estimado'] * (porcentaje_tiempo_transcurrido / 100) if porcentaje_tiempo_transcurrido else 0
    valor_ganado = proyecto['presupuesto_estimado'] * (proyecto['porcentaje_progreso'] / 100)
    costo_actual = proyecto['costo_total_recursos']
    
    indice_rendimiento_cronograma = valor_ganado / valor_planificado if valor_planificado > 0 else 0
    indice_rendimiento_costo = valor_ganado / costo_actual if costo_actual > 0 else 0
    
    return {
        "total_tareas": total_tareas,
        "tareas_completadas": tareas_completadas, 
        "tareas_pendientes": tareas_pendientes,
        "tareas_en_progreso": tareas_en_progreso,
        "tasa_completitud": (tareas_completadas / total_tareas * 100) if total_tareas > 0 else 0,
        "duracion_total_dias": duracion_total,
        "dias_transcurridos": duracion_transcurrida,
        "porcentaje_tiempo_transcurrido": porcentaje_tiempo_transcurrido,
        "desviacion_tiempo_progreso": desviacion_tiempo,
        "presupuesto_estimado": proyecto['presupuesto_estimado'],
        "costo_actual": proyecto['costo_total_recursos'],
        "porcentaje_presupuesto_usado": porcentaje_presupuesto_usado,
        "presupuesto_restante": presupuesto_restante,
        "valor_planificado": valor_planificado,
        "valor_ganado": valor_ganado,
        "indice_rendimiento_cronograma": indice_rendimiento_cronograma,
        "indice_rendimiento_costo": indice_rendimiento_costo,
        "total_recursos": len(recursos_df),
        "total_kpis": len(kpis_df)
    }

def _analizar_proyecto(proyecto, tareas_df, recursos_df, kpis_df):
    """Genera un análisis detallado de un proyecto específico"""
    metricas = _calcular_metricas_proyecto(proyecto, tareas_df, recursos_df, kpis_df)
    
    analisis = {
        "puntos_fuertes": [],
        "puntos_debiles": [],
        "riesgos": [],
        "oportunidades": []
    }
    
    # Analizar puntos fuertes
    if metricas["indice_rendimiento_costo"] > 1.05:
        analisis["puntos_fuertes"].append("Excelente rendimiento de costos")
    
    if metricas["indice_rendimiento_cronograma"] > 1.05:
        analisis["puntos_fuertes"].append("Progreso por encima del cronograma planificado")
    
    if metricas["tasa_completitud"] > 75:
        analisis["puntos_fuertes"].append("Alta tasa de completitud de tareas")
    
    if metricas["porcentaje_presupuesto_usado"] < 85 and metricas["porcentaje_tiempo_transcurrido"] > 80:
        analisis["puntos_fuertes"].append("Eficiencia presupuestaria")
    
    # Analizar puntos débiles
    if metricas["indice_rendimiento_cronograma"] < 0.9:
        analisis["puntos_debiles"].append("Retraso en el cronograma")
    
    if metricas["indice_rendimiento_costo"] < 0.9:
        analisis["puntos_debiles"].append("Sobrecosto del proyecto")
    
    if metricas["porcentaje_tiempo_transcurrido"] > 70 and metricas["tasa_completitud"] < 50:
        analisis["puntos_debiles"].append("Baja tasa de completitud en relación al tiempo transcurrido")
    
    # Analizar riesgos
    if metricas["desviacion_tiempo_progreso"] > 20:
        analisis["riesgos"].append("Riesgo de retraso significativo en la entrega")
    
    if metricas["porcentaje_presupuesto_usado"] > 90 and metricas["porcentaje_tiempo_transcurrido"] < 80:
        analisis["riesgos"].append("Riesgo de sobrecosto del proyecto")
    
    tareas_sin_progreso = tareas_df[(tareas_df['estado'] == 'pendiente') & (pd.to_datetime(tareas_df['fecha_comienzo']) < pd.Timestamp.now())]
    if len(tareas_sin_progreso) > 3:
        analisis["riesgos"].append(f"Hay {len(tareas_sin_progreso)} tareas que debieron iniciarse pero siguen pendientes")
    
    # Analizar oportunidades
    if len(kpis_df) < 3:
        analisis["oportunidades"].append("Definir más KPIs para un mejor seguimiento del proyecto")
    
    if metricas["total_recursos"] < 2:
        analisis["oportunidades"].append("Considerar asignar más recursos al proyecto")
    
    if metricas["tasa_completitud"] > 95 and proyecto['estado'] != 'finalizado':
        analisis["oportunidades"].append("El proyecto está casi completado, considerar finalizarlo formalmente")
        
    # Si no hay nada, agregar mensajes predeterminados
    if not analisis["puntos_fuertes"]:
        analisis["puntos_fuertes"].append("No se identificaron puntos fuertes destacables")
    if not analisis["puntos_debiles"]:
        analisis["puntos_debiles"].append("No se identificaron puntos débiles significativos")
    if not analisis["riesgos"]:
        analisis["riesgos"].append("No se identificaron riesgos críticos en este momento")
    if not analisis["oportunidades"]:
        analisis["oportunidades"].append("Considerar realizar una revisión detallada para identificar oportunidades de mejora")
        
    return analisis

def _generar_recomendaciones_proyecto(proyecto, tareas_df, recursos_df):
    """Genera recomendaciones específicas para mejorar un proyecto"""
    recomendaciones = []
    
    # Análisis de estado
    if proyecto['estado'] == 'en_progreso':
        # Verificar si hay tareas sin asignar
        tareas_sin_responsable = tareas_df[tareas_df['responsable_id'].isna()]
        if not tareas_sin_responsable.empty:
            recomendaciones.append(f"Asignar responsables a las {len(tareas_sin_responsable)} tareas sin asignar")
        
        # Verificar si hay tareas retrasadas
        hoy = datetime.now().date()
        tareas_retrasadas = tareas_df[(tareas_df['estado'] != 'completada') & 
                                      (pd.notnull(tareas_df['fecha_final'])) & 
                                      (pd.to_datetime(tareas_df['fecha_final']).dt.date < hoy)]
        if not tareas_retrasadas.empty:
            recomendaciones.append(f"Priorizar las {len(tareas_retrasadas)} tareas retrasadas")
    
    # Análisis de recursos
    if len(recursos_df) == 0:
        recomendaciones.append("Asignar recursos al proyecto para un mejor seguimiento y control")
    
    # Verificar presupuesto
    if proyecto['costo_total_recursos'] > proyecto['presupuesto_estimado'] * 0.9:
        recomendaciones.append("Reevaluar el presupuesto del proyecto, ya que está cerca o por encima del límite")
    
    # Analizar progreso y fechas
    if pd.notnull(proyecto['fecha_fin']):
        fecha_fin = pd.to_datetime(proyecto['fecha_fin']).date()
        hoy = datetime.now().date()
        dias_restantes = (fecha_fin - hoy).days
        
        if dias_restantes < 30 and proyecto['porcentaje_progreso'] < 70:
            recomendaciones.append("Considerar extender la fecha de finalización o reasignar más recursos debido al bajo progreso")
    
    # Recomendaciones por estado
    if proyecto['estado'] == 'planificacion':
        recomendaciones.append("Definir hitos claros y KPIs medibles antes de iniciar el proyecto")
        recomendaciones.append("Realizar una evaluación de riesgos detallada")
    
    # Si el progreso es bajo
    if proyecto['porcentaje_progreso'] < 25 and pd.notnull(proyecto['fecha_inicio']):
        fecha_inicio = pd.to_datetime(proyecto['fecha_inicio']).date()
        hoy = datetime.now().date()
        dias_transcurridos = (hoy - fecha_inicio).days
        
        if dias_transcurridos > 30:
            recomendaciones.append("Evaluar los obstáculos que impiden el progreso del proyecto")
    
    # Si el proyecto tiene más de 10 tareas
    if len(tareas_df) > 10:
        recomendaciones.append("Considerar dividir el proyecto en fases o subproyectos para un mejor seguimiento")
    
    # Si no hay recomendaciones, agregar una genérica
    if not recomendaciones:
        recomendaciones.append("El proyecto parece estar avanzando adecuadamente. Mantener el monitoreo regular")
    
    return recomendaciones

def _analizar_fortalezas_debilidades(proyectos_df, tareas_df, empleados_df):
    """Analiza fortalezas y debilidades globales de la gestión de proyectos"""
    analisis = {
        "fortalezas": [],
        "debilidades": [],
        "oportunidades": [],
        "amenazas": []
    }
    
    # Analizar proyectos
    proyectos_en_progreso = proyectos_df[proyectos_df['estado'] == 'en_progreso']
    proyectos_finalizados = proyectos_df[proyectos_df['estado'] == 'finalizado']
    
    # 1. Eficiencia presupuestaria
    if len(proyectos_finalizados) > 0:
        eficiencia_media = _calcular_eficiencia_presupuestaria(proyectos_finalizados)
        if eficiencia_media > 10:
            analisis["fortalezas"].append(f"Buena eficiencia presupuestaria global ({eficiencia_media:.2f}% de ahorro promedio)")
        elif eficiencia_media < -5:
            analisis["debilidades"].append(f"Tendencia a superar presupuestos ({-eficiencia_media:.2f}% de sobrecosto promedio)")
    
    # 2. Cumplimiento de plazos
    hoy = datetime.now().date()
    proyectos_retrasados = sum(1 for _, p in proyectos_en_progreso.iterrows() 
                              if pd.notna(p['fecha_fin']) and pd.to_datetime(p['fecha_fin']).date() < hoy)
    
    porcentaje_retrasados = (proyectos_retrasados / len(proyectos_en_progreso)) * 100 if len(proyectos_en_progreso) > 0 else 0
    
    if porcentaje_retrasados > 30:
        analisis["debilidades"].append(f"Alto porcentaje de proyectos retrasados ({porcentaje_retrasados:.2f}%)")
    elif porcentaje_retrasados < 10 and len(proyectos_en_progreso) > 3:
        analisis["fortalezas"].append(f"Excelente cumplimiento de plazos (solo {porcentaje_retrasados:.2f}% de proyectos retrasados)")
    
    # 3. Disponibilidad de personal
    empleados_disponibles = len(empleados_df[empleados_df['disponibilidad'] == 'disponible'])
    porcentaje_disponibles = (empleados_disponibles / len(empleados_df)) * 100 if len(empleados_df) > 0 else 0
    
    if porcentaje_disponibles < 15:
        analisis["amenazas"].append(f"Baja disponibilidad de personal ({porcentaje_disponibles:.2f}%)")
    elif porcentaje_disponibles > 40:
        analisis["oportunidades"].append(f"Alta disponibilidad de personal ({porcentaje_disponibles:.2f}%) para nuevos proyectos")
    
    # 4. Progreso global
    progreso_promedio = proyectos_en_progreso['porcentaje_progreso'].mean() if len(proyectos_en_progreso) > 0 else 0
    
    if progreso_promedio < 30:
        analisis["debilidades"].append(f"Bajo progreso promedio en los proyectos activos ({progreso_promedio:.2f}%)")
    elif progreso_promedio > 70:
        analisis["fortalezas"].append(f"Buen progreso promedio en los proyectos activos ({progreso_promedio:.2f}%)")
    
    # 5. Diversidad de departamentos y equipos involucrados
    if 'departamento' in empleados_df.columns:
        departamentos_unicos = empleados_df['departamento'].nunique()
        if departamentos_unicos > 3:
            analisis["fortalezas"].append(f"Buena colaboración interdepartamental ({departamentos_unicos} departamentos)")
    
    # 6. Evaluar la carga de trabajo
    tareas_por_empleado = []
    for _, empleado in empleados_df.iterrows():
        if 'id' in empleado:
            tareas = tareas_df[tareas_df['responsable_id'] == empleado['id']]
            tareas_por_empleado.append(len(tareas))
    
    if tareas_por_empleado:
        max_tareas = max(tareas_por_empleado) if tareas_por_empleado else 0
        desviacion_tareas = np.std(tareas_por_empleado) if len(tareas_por_empleado) > 1 else 0
        
        if max_tareas > 10:
            analisis["amenazas"].append(f"Posible sobrecarga de trabajo en algunos empleados (máx. {max_tareas} tareas)")
        
        if desviacion_tareas > 5:
            analisis["debilidades"].append("Distribución desigual de la carga de trabajo entre empleados")
    
    # Verificar que haya al menos un elemento en cada categoría
    if not analisis["fortalezas"]:
        analisis["fortalezas"].append("La organización mantiene operaciones estables")
    
    if not analisis["debilidades"]:
        analisis["debilidades"].append("No se identificaron debilidades críticas en este momento")
    
    if not analisis["oportunidades"]:
        analisis["oportunidades"].append("Considerar implementar más KPIs para medir el rendimiento de los proyectos")
    
    if not analisis["amenazas"]:
        analisis["amenazas"].append("Vigilar la asignación de recursos para evitar cuellos de botella")
    
    return analisis

def _generar_recomendaciones(proyectos_df, tareas_df, empleados_df, analisis):
    """Genera recomendaciones para mejorar la gestión de proyectos basadas en el análisis"""
    recomendaciones = []
    
    # 1. Recomendaciones basadas en debilidades
    for debilidad in analisis.get("debilidades", []):
        if "presupuestos" in debilidad.lower():
            recomendaciones.append("Implementar un proceso más riguroso de estimación de presupuestos")
            recomendaciones.append("Establecer revisiones periódicas de gastos durante la ejecución de proyectos")
        
        elif "retrasados" in debilidad.lower():
            recomendaciones.append("Revisar y ajustar el proceso de planificación de plazos")
            recomendaciones.append("Implementar alertas tempranas para proyectos en riesgo de retraso")
        
        elif "progreso" in debilidad.lower():
            recomendaciones.append("Realizar revisiones semanales del progreso de proyectos críticos")
            recomendaciones.append("Considerar la implementación de metodologías ágiles para mejorar la velocidad de entrega")
        
        elif "distribución" in debilidad.lower() and "carga" in debilidad.lower():
            recomendaciones.append("Revisar la asignación de tareas para equilibrar la carga de trabajo")
            recomendaciones.append("Implementar un sistema de rotación para tareas repetitivas")
    
    # 2. Recomendaciones basadas en amenazas
    for amenaza in analisis.get("amenazas", []):
        if "disponibilidad" in amenaza.lower() and "personal" in amenaza.lower():
            recomendaciones.append("Evaluar la necesidad de contratar personal adicional o freelancers")
            recomendaciones.append("Priorizar proyectos y posiblemente posponer los menos críticos")
        
        elif "sobrecarga" in amenaza.lower():
            recomendaciones.append("Redistribuir tareas entre el equipo para evitar el agotamiento")
            recomendaciones.append("Considerar herramientas de automatización para tareas repetitivas")
    
    # 3. Recomendaciones basadas en oportunidades
    for oportunidad in analisis.get("oportunidades", []):
        if "disponibilidad" in oportunidad.lower() and "personal" in oportunidad.lower():
            recomendaciones.append("Aprovechar la disponibilidad para capacitar al personal en nuevas habilidades")
            recomendaciones.append("Considerar iniciar proyectos estratégicos planificados para el futuro")
    
    # 4. Recomendaciones específicas basadas en métricas
    
    # Verificar eficiencia presupuestaria global
    eficiencia_global = _calcular_eficiencia_presupuestaria(proyectos_df)
    if eficiencia_global < 0:
        recomendaciones.append("Realizar un análisis detallado de costos para identificar áreas de optimización")
    
    # Verificar proyectos sin KPIs definidos
    if 'indicadores_ids' in proyectos_df.columns:
        proyectos_sin_kpis = proyectos_df[proyectos_df['indicadores_ids'].isna() | (proyectos_df['indicadores_ids'] == '[]')]
        if len(proyectos_sin_kpis) > 0:
            recomendaciones.append(f"Definir KPIs para los {len(proyectos_sin_kpis)} proyectos que carecen de indicadores")
    
    # Verificar proyectos casi finalizados
    proyectos_casi_terminados = proyectos_df[(proyectos_df['estado'] == 'en_progreso') & 
                                            (proyectos_df['porcentaje_progreso'] > 90)]
    if len(proyectos_casi_terminados) > 0:
        recomendaciones.append(f"Verificar criterios de finalización para {len(proyectos_casi_terminados)} proyectos con más del 90% de progreso")
    
    # Recomendaciones de mejores prácticas generales
    recomendaciones.append("Implementar reuniones retrospectivas al finalizar cada proyecto para identificar mejoras")
    recomendaciones.append("Mantener una base de conocimientos documentando lecciones aprendidas de cada proyecto")
    
    # Limitar a 10 recomendaciones máximo para no abrumar
    if len(recomendaciones) > 10:
        # Priorizar recomendaciones específicas sobre las generales
        recomendaciones = [r for r in recomendaciones if not r.startswith("Implementar") and not r.startswith("Mantener")][:8]
        recomendaciones.append("Implementar reuniones retrospectivas al finalizar cada proyecto")
        recomendaciones.append("Mantener una base de conocimientos con lecciones aprendidas")
    
    return recomendaciones

def _calcular_carga_trabajo(empleado_data):
    """Calcula el nivel de carga de trabajo de un empleado"""
    # Factores para considerar:
    # 1. Número de tareas asignadas
    # 2. Número de proyectos en los que participa
    # 3. Disponibilidad declarada
    
    nivel_carga = 0
    
    # Factor de tareas
    if empleado_data["total_tareas"] > 15:
        nivel_carga += 5
    elif empleado_data["total_tareas"] > 10:
        nivel_carga += 4
    elif empleado_data["total_tareas"] > 7:
        nivel_carga += 3
    elif empleado_data["total_tareas"] > 4:
        nivel_carga += 2
    elif empleado_data["total_tareas"] > 1:
        nivel_carga += 1
    
    # Factor de proyectos
    if empleado_data["total_proyectos"] > 5:
        nivel_carga += 5
    elif empleado_data["total_proyectos"] > 3:
        nivel_carga += 3
    elif empleado_data["total_proyectos"] > 1:
        nivel_carga += 1
    
    # Factor de disponibilidad
    if empleado_data["disponibilidad"] == "no_disponible":
        nivel_carga += 5
    elif empleado_data["disponibilidad"] == "parcial":
        nivel_carga += 3
    elif empleado_data["disponibilidad"] == "asignado":
        nivel_carga += 2
    
    # Normalizar a escala 0-10
    nivel_carga = min(nivel_carga, 10)
    
    # Determinar categoría de carga
    if nivel_carga >= 8:
        return {"nivel": nivel_carga, "categoria": "Alta"}
    elif nivel_carga >= 5:
        return {"nivel": nivel_carga, "categoria": "Media"}
    else:
        return {"nivel": nivel_carga, "categoria": "Baja"}

def _calcular_tendencias(metricas_mensuales):
    """Calcula tendencias a partir de las métricas históricas"""
    if not metricas_mensuales or len(metricas_mensuales) < 3:
        return {
            "tendencia_proyectos": None,
            "tendencia_presupuesto": None,
            "tendencia_eficiencia": None,
            "prediccion_proximos_meses": None
        }
    
    # Extraer series temporales
    meses = [m["mes"] for m in metricas_mensuales]
    proyectos_por_mes = [m["proyectos_iniciados"] for m in metricas_mensuales]
    presupuesto_por_mes = [m["presupuesto_total"] for m in metricas_mensuales]
    eficiencia_por_mes = [m.get("eficiencia_presupuestaria", 0) for m in metricas_mensuales]
    
    # Calcular tendencias (pendiente de la línea de regresión)
    x = np.arange(len(meses))
    
    # Tendencia de proyectos iniciados
    if len(set(proyectos_por_mes)) > 1:  # Verificar que hay variación
        slope_proyectos = np.polyfit(x, proyectos_por_mes, 1)[0]
        tendencia_proyectos = "creciente" if slope_proyectos > 0.1 else "decreciente" if slope_proyectos < -0.1 else "estable"
    else:
        tendencia_proyectos = "estable"
    
    # Tendencia de presupuesto
    if len(set(presupuesto_por_mes)) > 1:  # Verificar que hay variación
        slope_presupuesto = np.polyfit(x, presupuesto_por_mes, 1)[0]
        tendencia_presupuesto = "creciente" if slope_presupuesto > 100 else "decreciente" if slope_presupuesto < -100 else "estable"
    else:
        tendencia_presupuesto = "estable"
    
    # Tendencia de eficiencia
    if len(set(eficiencia_por_mes)) > 1:  # Verificar que hay variación
        slope_eficiencia = np.polyfit(x, eficiencia_por_mes, 1)[0]
        tendencia_eficiencia = "mejorando" if slope_eficiencia > 0.5 else "empeorando" if slope_eficiencia < -0.5 else "estable"
    else:
        tendencia_eficiencia = "estable"
    
    # Predicción simple para próximos 3 meses (promedio móvil)
    ultimos_proyectos = proyectos_por_mes[-3:] if len(proyectos_por_mes) >= 3 else proyectos_por_mes
    prediccion_proyectos = round(sum(ultimos_proyectos) / len(ultimos_proyectos))
    
    ultimos_presupuestos = presupuesto_por_mes[-3:] if len(presupuesto_por_mes) >= 3 else presupuesto_por_mes
    prediccion_presupuesto = sum(ultimos_presupuestos) / len(ultimos_presupuestos)
    
    return {
        "tendencia_proyectos": {
            "direccion": tendencia_proyectos,
            "valores_recientes": proyectos_por_mes[-3:] if len(proyectos_por_mes) >= 3 else proyectos_por_mes
        },
        "tendencia_presupuesto": {
            "direccion": tendencia_presupuesto,
            "valores_recientes": [round(p, 2) for p in (presupuesto_por_mes[-3:] if len(presupuesto_por_mes) >= 3 else presupuesto_por_mes)]
        },
        "tendencia_eficiencia": {
            "direccion": tendencia_eficiencia,
            "valores_recientes": [round(e, 2) for e in (eficiencia_por_mes[-3:] if len(eficiencia_por_mes) >= 3 else eficiencia_por_mes)]
        },
        "prediccion_proximos_meses": {
            "proyectos_mensuales": prediccion_proyectos,
            "presupuesto_mensual": round(prediccion_presupuesto, 2)
        }
    }
    


# Añadir endpoints personalizados

@api_bp.route('/equipos', methods=['GET'])
def get_equipos():
    """Obtiene información sobre los equipos de trabajo y su rendimiento"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        # Obtener datos de equipos
        equipos_df = pd.read_sql("""
            SELECT 
                e.id, e.nombre, e.descripcion, e.responsable_id,
                COUNT(DISTINCT ee.empleado_id) as num_miembros
            FROM 
                creativeminds_equipo e
            LEFT JOIN 
                creativeminds_equipo_empleado_rel ee ON e.id = ee.equipo_id
            GROUP BY 
                e.id, e.nombre, e.descripcion, e.responsable_id
        """, engine)
        
        # Obtener datos de miembros por equipo
        miembros_df = pd.read_sql("""
            SELECT 
                ee.equipo_id, 
                e.empleado_id, 
                e.nombre, 
                e.disponibilidad,
                e.departamento,
                e.puesto
            FROM 
                creativeminds_equipo_empleado_rel ee
            JOIN 
                creativeminds_empleado e ON ee.empleado_id = e.id
        """, engine)
        
        # Obtener datos de proyectos por equipo
        proyectos_equipo_df = pd.read_sql("""
            SELECT 
                ee.equipo_id,
                COUNT(DISTINCT pe.proyecto_id) as total_proyectos,
                AVG(p.porcentaje_progreso) as progreso_promedio
            FROM 
                creativeminds_equipo_empleado_rel ee
            JOIN 
                creativeminds_empleado e ON ee.empleado_id = e.id
            JOIN 
                creativeminds_proyecto_empleado_rel pe ON e.id = pe.empleado_id
            JOIN 
                creativeminds_proyecto p ON pe.proyecto_id = p.id
            GROUP BY 
                ee.equipo_id
        """, engine)
        
        # Combinar datos
        equipos_completos = []
        for _, equipo in equipos_df.iterrows():
            equipo_data = equipo.to_dict()
            
            # Obtener miembros del equipo
            miembros = miembros_df[miembros_df['equipo_id'] == equipo['id']].to_dict(orient='records')
            equipo_data['miembros'] = miembros
            
            # Obtener datos de proyectos
            proyectos_data = proyectos_equipo_df[proyectos_equipo_df['equipo_id'] == equipo['id']]
            if not proyectos_data.empty:
                equipo_data['total_proyectos'] = int(proyectos_data['total_proyectos'].iloc[0])
                equipo_data['progreso_promedio'] = float(proyectos_data['progreso_promedio'].iloc[0]) if pd.notna(proyectos_data['progreso_promedio'].iloc[0]) else 0
            else:
                equipo_data['total_proyectos'] = 0
                equipo_data['progreso_promedio'] = 0
                
            # Calcular rendimiento del equipo
            equipo_data['rendimiento'] = _calcular_rendimiento_equipo(equipo_data, miembros)
            
            equipos_completos.append(equipo_data)
            
        return jsonify({"equipos": equipos_completos})
        
    except Exception as e:
        logger.error(f"Error al obtener datos de equipos: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/recursos', methods=['GET'])
def get_recursos():
    """Obtiene información sobre los recursos asignados a los proyectos"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        recursos_df = pd.read_sql("""
            SELECT 
                r.*, 
                p.nombre as nombre_proyecto
            FROM 
                creativeminds_recurso r
            LEFT JOIN 
                creativeminds_proyecto p ON r.proyecto_id = p.id
        """, engine)
        
        # Calcular métricas adicionales
        recursos_df['eficiencia_costo'] = recursos_df.apply(
            lambda r: (r['horas_asignadas'] * r['costo_por_hora']) / r['costo_total'] 
            if r['costo_total'] > 0 else 0, 
            axis=1
        )
        
        return jsonify({"recursos": recursos_df.to_dict(orient='records')})
        
    except Exception as e:
        logger.error(f"Error al obtener datos de recursos: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/predicciones', methods=['GET'])
def get_predicciones():
    """Genera predicciones para la planificación futura"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        # Obtener datos históricos
        proyectos_df = pd.read_sql("""
            SELECT 
                id, nombre, estado, fecha_inicio, fecha_fin, 
                presupuesto_estimado, costo_total_recursos, porcentaje_progreso,
                horas_asignadas
            FROM 
                creativeminds_proyecto
            WHERE 
                fecha_inicio IS NOT NULL AND fecha_fin IS NOT NULL
        """, engine)
        
        # Si no hay suficientes datos para predicciones
        if len(proyectos_df) < 5:
            return jsonify({
                "error": "Datos insuficientes para generar predicciones confiables",
                "recomendacion": "Se necesitan al menos 5 proyectos completados para generar predicciones"
            })
        
        # Calcular promedios y tendencias
        proyectos_finalizados = proyectos_df[proyectos_df['estado'] == 'finalizado']
        
        # Duración promedio de proyectos
        proyectos_finalizados['fecha_inicio'] = pd.to_datetime(proyectos_finalizados['fecha_inicio'])
        proyectos_finalizados['fecha_fin'] = pd.to_datetime(proyectos_finalizados['fecha_fin'])
        proyectos_finalizados['duracion_dias'] = (proyectos_finalizados['fecha_fin'] - proyectos_finalizados['fecha_inicio']).dt.days
        
        duracion_promedio = proyectos_finalizados['duracion_dias'].mean()
        
        # Costo promedio por hora y por proyecto
        costo_promedio_hora = proyectos_finalizados['costo_por_hora'].mean() if 'costo_por_hora' in proyectos_finalizados.columns else None
        
        if costo_promedio_hora is None:
            costo_promedio_por_proyecto = proyectos_finalizados['costo_total_recursos'].mean()
        else:
            costo_promedio_por_proyecto = None
        
        # Horas promedio por proyecto
        horas_promedio = proyectos_finalizados['horas_asignadas'].mean() if 'horas_asignadas' in proyectos_finalizados.columns else None
        
        # Generar predicciones para nuevos proyectos
        predicciones = {
            "duracion_estimada": {
                "promedio_dias": round(duracion_promedio, 1) if not pd.isna(duracion_promedio) else None,
                "minima_dias": round(proyectos_finalizados['duracion_dias'].min(), 1) if not proyectos_finalizados.empty else None,
                "maxima_dias": round(proyectos_finalizados['duracion_dias'].max(), 1) if not proyectos_finalizados.empty else None
            },
            "costo_estimado": {
                "promedio_por_proyecto": round(costo_promedio_por_proyecto, 2) if costo_promedio_por_proyecto is not None else None,
                "promedio_por_hora": round(costo_promedio_hora, 2) if costo_promedio_hora is not None else None,
                "horas_promedio": round(horas_promedio, 2) if horas_promedio is not None else None
            },
            "capacidad_optima": {
                "proyectos_simultáneos": _estimar_capacidad_optima(proyectos_df),
                "recursos_recomendados": _estimar_recursos_recomendados(proyectos_finalizados)
            }
        }
        
        return jsonify({"predicciones": predicciones})
        
    except Exception as e:
        logger.error(f"Error al generar predicciones: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Funciones auxiliares adicionales

def _calcular_rendimiento_equipo(equipo_data, miembros):
    """Calcula una puntuación de rendimiento para un equipo basada en diversos factores"""
    if not miembros:
        return {"puntuacion": 0, "nivel": "No evaluable", "factores": []}
    
    factores = []
    puntuacion_total = 0
    
    # Factor 1: Tamaño adecuado del equipo (óptimo entre 3-7 miembros)
    num_miembros = len(miembros)
    if 3 <= num_miembros <= 7:
        puntuacion_total += 3
        factores.append({"nombre": "Tamaño óptimo", "puntuacion": 3})
    elif 2 <= num_miembros < 3 or 7 < num_miembros <= 10:
        puntuacion_total += 2
        factores.append({"nombre": "Tamaño aceptable", "puntuacion": 2})
    else:
        puntuacion_total += 1
        factores.append({"nombre": "Tamaño no óptimo", "puntuacion": 1})
    
    # Factor 2: Diversidad de habilidades (basado en departamentos/puestos)
    departamentos = set()
    puestos = set()
    
    for miembro in miembros:
        if 'departamento' in miembro and miembro['departamento']:
            departamentos.add(miembro['departamento'])
        if 'puesto' in miembro and miembro['puesto']:
            puestos.add(miembro['puesto'])
    
    diversidad = len(departamentos) + len(puestos)
    if diversidad >= 5:
        puntuacion_total += 3
        factores.append({"nombre": "Alta diversidad", "puntuacion": 3})
    elif 3 <= diversidad < 5:
        puntuacion_total += 2
        factores.append({"nombre": "Diversidad media", "puntuacion": 2})
    else:
        puntuacion_total += 1
        factores.append({"nombre": "Baja diversidad", "puntuacion": 1})
    
    # Factor 3: Disponibilidad de los miembros
    disponibilidad_puntos = 0
    for miembro in miembros:
        if 'disponibilidad' in miembro:
            if miembro['disponibilidad'] == 'disponible':
                disponibilidad_puntos += 3
            elif miembro['disponibilidad'] == 'parcial':
                disponibilidad_puntos += 2
            elif miembro['disponibilidad'] == 'asignado':
                disponibilidad_puntos += 1
    
    disponibilidad_promedio = disponibilidad_puntos / num_miembros if num_miembros > 0 else 0
    
    if disponibilidad_promedio > 2.5:
        puntuacion_total += 3
        factores.append({"nombre": "Alta disponibilidad", "puntuacion": 3})
    elif disponibilidad_promedio > 1.5:
        puntuacion_total += 2
        factores.append({"nombre": "Disponibilidad media", "puntuacion": 2})
    else:
        puntuacion_total += 1
        factores.append({"nombre": "Baja disponibilidad", "puntuacion": 1})
    
    # Factor 4: Productividad (basada en progreso de proyectos)
    if 'progreso_promedio' in equipo_data and equipo_data['progreso_promedio'] > 0:
        if equipo_data['progreso_promedio'] > 75:
            puntuacion_total += 3
            factores.append({"nombre": "Alta productividad", "puntuacion": 3})
        elif equipo_data['progreso_promedio'] > 50:
            puntuacion_total += 2
            factores.append({"nombre": "Productividad media", "puntuacion": 2})
        else:
            puntuacion_total += 1
            factores.append({"nombre": "Productividad baja", "puntuacion": 1})
    else:
        # No hay datos de progreso
        puntuacion_total += 1
        factores.append({"nombre": "Sin datos de productividad", "puntuacion": 1})
    
    # Calcular puntuación final (sobre 10)
    puntuacion_max_posible = 12  # 4 factores * 3 puntos máx
    puntuacion_final = (puntuacion_total / puntuacion_max_posible) * 10
    
    # Determinar nivel de rendimiento
    if puntuacion_final >= 8:
        nivel = "Excelente"
    elif puntuacion_final >= 6:
        nivel = "Bueno"
    elif puntuacion_final >= 4:
        nivel = "Regular"
    else:
        nivel = "Bajo"
    
    return {
        "puntuacion": round(puntuacion_final, 1),
        "nivel": nivel,
        "factores": factores
    }

def _estimar_capacidad_optima(proyectos_df):
    """Estima la capacidad óptima de proyectos simultáneos basada en datos históricos"""
    try:
        # Convertir fechas a datetime
        proyectos_df['fecha_inicio'] = pd.to_datetime(proyectos_df['fecha_inicio'])
        proyectos_df['fecha_fin'] = pd.to_datetime(proyectos_df['fecha_fin'])
        
        # Crear un rango de fechas para análisis
        if len(proyectos_df) > 0:
            fecha_min = proyectos_df['fecha_inicio'].min()
            fecha_max = proyectos_df['fecha_fin'].max()
            
            if pd.notna(fecha_min) and pd.notna(fecha_max):
                # Crear serie temporal de proyectos activos por día
                dias = pd.date_range(start=fecha_min, end=fecha_max)
                proyectos_por_dia = []
                
                for dia in dias:
                    # Contar proyectos activos en este día
                    activos = sum(1 for _, p in proyectos_df.iterrows() 
                               if pd.notna(p['fecha_inicio']) and pd.notna(p['fecha_fin']) 
                               and p['fecha_inicio'] <= dia <= p['fecha_fin'])
                    proyectos_por_dia.append(activos)
                
                if proyectos_por_dia:
                    # Calcular estadísticas
                    max_proyectos = max(proyectos_por_dia)
                    promedio_proyectos = sum(proyectos_por_dia) / len(proyectos_por_dia)
                    percentil_75 = np.percentile(proyectos_por_dia, 75)
                    
                    return {
                        "maximo_historico": max_proyectos,
                        "promedio_historico": round(promedio_proyectos, 1),
                        "recomendado": max(round(percentil_75, 0), 1)  # Al menos 1 proyecto
                    }
        
        # Si no hay datos suficientes
        return {
            "maximo_historico": None,
            "promedio_historico": None,
            "recomendado": 2  # Valor predeterminado
        }
    except:
        return {
            "maximo_historico": None,
            "promedio_historico": None,
            "recomendado": 2  # Valor predeterminado
        }

def _estimar_recursos_recomendados(proyectos_df):
    """Estima la cantidad de recursos recomendados por proyecto basado en históricos"""
    if 'recursos_ids' in proyectos_df.columns:
        # Si tenemos datos directos de recursos
        try:
            recursos_por_proyecto = []
            for _, proyecto in proyectos_df.iterrows():
                if isinstance(proyecto['recursos_ids'], list):
                    recursos_por_proyecto.append(len(proyecto['recursos_ids']))
                elif isinstance(proyecto['recursos_ids'], str) and proyecto['recursos_ids'].startswith('['):
                    # Es un string que representa una lista
                    recursos_por_proyecto.append(len(json.loads(proyecto['recursos_ids'])))
            
            if recursos_por_proyecto:
                promedio = sum(recursos_por_proyecto) / len(recursos_por_proyecto)
                return round(promedio, 1)
        except:
            pass
    
    # Si no hay datos o hay error, usar heurística basada en duración y presupuesto
    try:
        duracion_promedio = proyectos_df['duracion_dias'].mean() if 'duracion_dias' in proyectos_df.columns else None
        presupuesto_promedio = proyectos_df['presupuesto_estimado'].mean()
        
        if duracion_promedio is not None and presupuesto_promedio is not None:
            # Heurística simple: 1 recurso por cada 15 días de proyecto o por cada X presupuesto
            recursos_por_tiempo = duracion_promedio / 15
            recursos_por_presupuesto = presupuesto_promedio / 5000  # Ajustar según escala de presupuesto
            
            return round(max(recursos_por_tiempo, recursos_por_presupuesto), 1)
    except:
        pass
    
    # Valor predeterminado si no hay datos
    return 2

@api_bp.route('/recomendaciones', methods=['GET'])
def get_recomendaciones_generales():
    """Genera recomendaciones generales para mejorar la gestión de proyectos"""
    try:
        engine = get_odoo_connection()
        if not engine:
            return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
        
        # Obtener datos de proyectos
        proyectos_df = pd.read_sql("""
            SELECT 
                proyecto_id, nombre, estado, fecha_inicio, fecha_fin, 
                presupuesto_estimado, costo_total_recursos, porcentaje_progreso
            FROM 
                creativeminds_proyecto
        """, engine)
        
        # Obtener tareas
        tareas_df = pd.read_sql("""
            SELECT 
                t.id, t.nombre, t.estado, t.fecha_comienzo, t.fecha_final, 
                t.proyecto_id, p.nombre as nombre_proyecto
            FROM 
                creativeminds_tarea t
            JOIN 
                creativeminds_proyecto p ON t.proyecto_id = p.id
        """, engine)
        
        # Obtener empleados
        empleados_df = pd.read_sql("""
            SELECT 
                e.empleado_id, e.nombre, e.disponibilidad, e.departamento, e.puesto
            FROM 
                creativeminds_empleado e
        """, engine)
        
        # Análisis de fortalezas y debilidades
        analisis = _analizar_fortalezas_debilidades(proyectos_df, tareas_df, empleados_df)
        
        # Generar recomendaciones
        recomendaciones = _generar_recomendaciones(proyectos_df, tareas_df, empleados_df, analisis)
        
        # Identificar áreas de mejora críticas
        areas_mejora = _identificar_areas_mejora(proyectos_df, tareas_df, empleados_df)
        
        return jsonify({
            "analisis_foda": analisis,
            "recomendaciones": recomendaciones,
            "areas_mejora_prioritarias": areas_mejora
        })
        
    except Exception as e:
        logger.error(f"Error al generar recomendaciones: {str(e)}")
        return jsonify({"error": str(e)}), 500


def _identificar_areas_mejora(proyectos_df, tareas_df, empleados_df):
    """Identifica áreas críticas que necesitan mejora inmediata"""
    areas_mejora = []
    
    # 1. Verificar proyectos críticos retrasados
    hoy = datetime.now().date()
    proyectos_retrasados = []
    
    for _, proyecto in proyectos_df.iterrows():
        if proyecto['estado'] != 'finalizado' and pd.notna(proyecto['fecha_fin']):
            fecha_fin = pd.to_datetime(proyecto['fecha_fin']).date()
            if fecha_fin < hoy:
                dias_retraso = (hoy - fecha_fin).days
                proyectos_retrasados.append({
                    "id": proyecto['proyecto_id'],
                    "nombre": proyecto['nombre'],
                    "dias_retraso": dias_retraso,
                    "progreso": proyecto['porcentaje_progreso']
                })
    
    if proyectos_retrasados:
        # Ordenar por días de retraso
        proyectos_retrasados = sorted(proyectos_retrasados, key=lambda x: x['dias_retraso'], reverse=True)
        areas_mejora.append({
            "area": "Proyectos retrasados",
            "descripcion": f"Hay {len(proyectos_retrasados)} proyectos que han superado su fecha de finalización",
            "gravedad": "Alta" if len(proyectos_retrasados) > 3 or (proyectos_retrasados and proyectos_retrasados[0]['dias_retraso'] > 30) else "Media",
            "ejemplos": proyectos_retrasados[:3],  # Top 3 más retrasados
            "accion_recomendada": "Realizar reunión de revisión urgente con los responsables de estos proyectos"
        })
    
    # 2. Verificar sobrecarga de recursos
    if 'id' in empleados_df.columns:
        empleados_con_tareas = {}
        for _, tarea in tareas_df.iterrows():
            if pd.notna(tarea['responsable_id']):
                empleado_id = tarea['responsable_id']
                if empleado_id not in empleados_con_tareas:
                    empleados_con_tareas[empleado_id] = []
                empleados_con_tareas[empleado_id].append(tarea)
        
        empleados_sobrecargados = []
        for empleado_id, tareas in empleados_con_tareas.items():
            if len(tareas) > 8:  # Umbral de sobrecarga
                # Buscar nombre del empleado
                nombre = "Desconocido"
                empleado_info = empleados_df[empleados_df['id'] == empleado_id]
                if not empleado_info.empty:
                    nombre = empleado_info['nombre'].iloc[0]
                
                empleados_sobrecargados.append({
                    "id": empleado_id,
                    "nombre": nombre,
                    "num_tareas": len(tareas),
                    "tareas_pendientes": sum(1 for t in tareas if t['estado'] == 'pendiente')
                })
        
        if empleados_sobrecargados:
            areas_mejora.append({
                "area": "Sobrecarga de recursos humanos",
                "descripcion": f"Hay {len(empleados_sobrecargados)} empleados con excesiva carga de trabajo",
                "gravedad": "Alta" if len(empleados_sobrecargados) > 3 else "Media",
                "ejemplos": sorted(empleados_sobrecargados, key=lambda x: x['num_tareas'], reverse=True)[:3],
                "accion_recomendada": "Redistribuir tareas y considerar la asignación de más recursos"
            })
    
    # 3. Verificar proyectos con presupuesto excedido
    proyectos_sobrecosto = []
    for _, proyecto in proyectos_df.iterrows():
        if proyecto['presupuesto_estimado'] > 0 and proyecto['costo_total_recursos'] > proyecto['presupuesto_estimado']:
            exceso = (proyecto['costo_total_recursos'] - proyecto['presupuesto_estimado']) / proyecto['presupuesto_estimado'] * 100
            proyectos_sobrecosto.append({
                "id": proyecto['proyecto_id'],
                "nombre": proyecto['nombre'],
                "presupuesto": proyecto['presupuesto_estimado'],
                "costo_actual": proyecto['costo_total_recursos'],
                "exceso_porcentaje": round(exceso, 1)
            })
    
    if proyectos_sobrecosto:
        areas_mejora.append({
            "area": "Control presupuestario",
            "descripcion": f"Hay {len(proyectos_sobrecosto)} proyectos que han excedido su presupuesto",
            "gravedad": "Alta" if len(proyectos_sobrecosto) > 2 else "Media",
            "ejemplos": sorted(proyectos_sobrecosto, key=lambda x: x['exceso_porcentaje'], reverse=True)[:3],
            "accion_recomendada": "Realizar auditoría de costos y revisar procesos de estimación presupuestaria"
        })
    
    # 4. Verificar tareas bloqueadas o sin avance
    hoy = datetime.now().date()
    tareas_estancadas = []
    
    for _, tarea in tareas_df.iterrows():
        if tarea['estado'] == 'en_progreso' and pd.notna(tarea['fecha_comienzo']):
            fecha_inicio = pd.to_datetime(tarea['fecha_comienzo']).date()
            dias_activa = (hoy - fecha_inicio).days
            
            if dias_activa > 14:  # Más de 2 semanas sin completarse
                tareas_estancadas.append({
                    "id": tarea['id'],
                    "nombre": tarea['nombre'],
                    "proyecto": tarea['nombre_proyecto'],
                    "dias_activa": dias_activa
                })
    
    if tareas_estancadas:
        areas_mejora.append({
            "area": "Progreso de tareas",
            "descripcion": f"Hay {len(tareas_estancadas)} tareas en progreso por más de 2 semanas",
            "gravedad": "Media",
            "ejemplos": sorted(tareas_estancadas, key=lambda x: x['dias_activa'], reverse=True)[:3],
            "accion_recomendada": "Revisar bloqueos y dependencias que impiden el avance de las tareas"
        })
    
    return areas_mejora

# Registrar los blueprints
app.register_blueprint(api_bp)

# Ejecutar la aplicación 
if __name__ == '__main__':
    # Configurar logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Configurar manejador para la consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Configurar manejador para archivo de log
    try:
        file_handler = logging.FileHandler('creativeminds_api.log')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except:
        logger.warning("No se pudo crear el archivo de log")
    
    logger.info("Iniciando Creative Minds Analytics API...")
    
    # Ejecutar en modo debug y permitir acceso desde cualquier host
    app.run(debug=True, host='0.0.0.0', port=5000)