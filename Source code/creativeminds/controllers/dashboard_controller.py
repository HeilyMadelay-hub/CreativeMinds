from odoo import http
from odoo.http import request
import requests
import json

class DashboardController(http.Controller):
    @http.route('/creativeminds/dashboard', type='json', auth='user')
    def get_dashboard_data(self):
        """Obtiene datos del dashboard desde la API externa"""
        try:
            # URL de la API externa
            api_url = "http://localhost:5000/api/dashboard"
            
            # Realizar la petición a la API externa
            response = requests.get(api_url, timeout=10)
            
            # Verificar si la petición fue exitosa
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"Error en la API: {response.status_code}",
                    "message": "No se pudieron obtener los datos del dashboard"
                }
        except Exception as e:
            return {
                "error": str(e),
                "message": "Error al conectar con la API externa"
            }