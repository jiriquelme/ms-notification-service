# ========================================================================
#                                Imports
# ========================================================================

import requests
from twilio.rest import Client
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
import os
import qrcode
from google.cloud import storage

# ========================================================================
#                                Configuración
# ========================================================================

# Obtener las credenciales y el número de Twilio desde el archivo .env
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

client = Client(account_sid, auth_token)

# ========================================================================
#                                Funciones
# ========================================================================

def generar_y_subir_qr(id_encomienda):
    # Generar el QR
    nombre_archivo = f"QR_CODE_{id_encomienda}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=20,
        border=6,
    )

    contenido = {f"id_encomienda": id_encomienda}

    qr.add_data(contenido)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.convert("RGB")

    nombre_local = f"{nombre_archivo}.png"
    img.save(nombre_local)
    
    # Subir a GCS
    client = storage.Client()
    bucket = client.bucket(os.getenv('GCS_BUCKET_NAME'))  # Configura el bucket en tu archivo .env
    blob = bucket.blob(f"qr_codes/{nombre_archivo}.png")
    blob.upload_from_filename(nombre_local)
    
    # Obtener URL pública
    os.remove(nombre_local)  # Elimina el archivo local después de subirlo
    return blob.public_url

def subir_imagen_a_bucket(imagen, id_encomienda):
    """
    Sube una imagen (en memoria o desde un archivo local) a Google Cloud Storage y devuelve la URL pública de la imagen.
    
    Args:
        imagen: Ruta local de la imagen o archivo en memoria (de request.FILES).
        id_encomienda (str): ID de la encomienda para nombrar el archivo.

    Returns:
        str: URL pública de la imagen en el bucket.
    """
    # Configura el cliente de Google Cloud Storage
    client = storage.Client()
    bucket_name = os.getenv('GCS_BUCKET_NAME')
    bucket = client.bucket(bucket_name)
    
    # Define el nombre del archivo en el bucket
    nombre_archivo = f"ENCOMIENDA_{id_encomienda}"
    blob = bucket.blob(f"encomiendas/{nombre_archivo}.png")
    
    # Verifica si `imagen` es una ruta de archivo o un archivo en memoria
    if isinstance(imagen, str):
        # Si es una ruta de archivo, usa upload_from_filename
        blob.upload_from_filename(imagen)
    else:
        # Si es un archivo en memoria (por ejemplo, request.FILES), usa upload_from_file
        blob.upload_from_file(imagen, content_type=imagen.content_type)

    # Haz pública la imagen y obtén la URL
    return blob.public_url


# ========================================================================
#                                Endpoints
# ========================================================================

class SendNotificationView(APIView):
    def post(self, request):
        codigo_departamento = request.data.get("codigo_departamento")
        imagen_encomienda = request.FILES['image']
        try:
            if not codigo_departamento or not imagen_encomienda:
                return Response({"error": "El código de departamento y la imagen de la encomienda son requeridos"}, status=400)

            # Obtener información del residente desde el management-service
            url = f"{settings.MANAGEMENT_SERVICE_URL}/residente/?codigo_departamento={codigo_departamento}"
            response = requests.get(url)

            if response.status_code != 200:
                error_data = response.json()
                error_respuesta = error_data["error"]
                return Response({"error": error_respuesta}, status=404)
            
            residente_data = response.json()
            nombre_completo = residente_data["nombre_completo"]
            telefono = residente_data["telefono"]

            # Crear registro de encomienda después de notificar
            encomienda_data = {
                "departamento_id": codigo_departamento,
                "residente_id": residente_data["id"],
            }
            response = requests.post(f"{settings.MANAGEMENT_SERVICE_URL}/registrar-encomienda/", data=encomienda_data)

            if response.status_code != 200:
                return Response({"error": "Error al registrar encomienda"}, status=500)
            
            # Obtener el ID de la encomienda registrada
            encomienda_id = response.json().get("id")
            
            # Generar el QR con el ID de la encomienda
            url_qr = generar_y_subir_qr(encomienda_id)  # Esta función devuelve la URL pública del QR
            url_img_encomienda = subir_imagen_a_bucket(imagen_encomienda, encomienda_id)

            print(f"Codigo Departamento: {codigo_departamento}\nNombre Residente: {nombre_completo}")
            """"
            # Enviar mensaje de Inicio de Contacto
            message = client.messages.create(
            from_=whatsapp_number,
            to=f'whatsapp:+56{telefono}',
            content_sid='HXb4eacc3414799fa8b067886de0e0324d',  # Reemplaza con el Template SID de tu plantilla aprobada
            content_variables=f'{{"1":"{nombre_completo}", "2":"{codigo_departamento}"}}', 
            )



            """
            # Enviar mensaje vía Twilio con la URL del QR
            message = client.messages.create(
                from_=whatsapp_number,
                to=f'whatsapp:+56{telefono}',
                body=f"Hola {nombre_completo}, residente del departamento {codigo_departamento}. Tiene un paquete disponible en conserjería.",
                media_url=[url_qr]  # Incluye la URL del QR como media en el mensaje de WhatsApp
            )

            message_encomienda = client.messages.create(
                from_=whatsapp_number,
                to=f'whatsapp:+56{telefono}',
                body=f"Evidencia de su pedido.",
                media_url=[url_img_encomienda]  # Incluye la URL del QR como media en el mensaje de WhatsApp
            )
            
            return Response({"status": "Notificación enviada y encomienda registrada",
                              "sid": message.sid,
                              "sid_encomienda": message_encomienda.sid
                                })
        except Exception as e:
            print(e)
            return Response({"error": "Error interno del servidor"}, status=500)

class GenerarQRView(APIView):
    def post(self, request):
        id_encomienda = request.data.get("id_encomienda")
        
        if not id_encomienda:
            return Response({"error": "ID de encomienda es requerido"}, status=400)
        
        try:
            url_qr = generar_y_subir_qr(id_encomienda)
            return Response({"status": "QR generado", "url_qr": url_qr})
        except Exception as e:
            return Response({"error": str(e)}, status=500)