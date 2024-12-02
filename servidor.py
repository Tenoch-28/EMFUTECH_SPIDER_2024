#ESTE ES EL SERVIDOR QUE DEBERAS CORRER EN TU COMPUTADORA
#SI TIENES DUDAS PREGUNTALE A CHATGPT :) O A MI CORREO enocmtz0521@gmail.com

import socket
import struct
import cv2
import torch
import pickle
import threading
import warnings
import time

# Suprimir advertencias de deprecación
warnings.filterwarnings("ignore", category=FutureWarning)

# Configuración de reconexión
REINTENTOS = 5
TIEMPO_ESPERA = 15  # Tiempo de espera en segundos entre reintentos

# Cargar el modelo de detección
model = torch.hub.load('ultralytics/yolov5', 'custom', path='/home/tenoclogy28/Documents/CLIENTE/best.pt')

def conectar_cliente(socket_servidor, cliente_tipo):
    for intento in range(REINTENTOS):
        try:
            cliente_socket, addr = socket_servidor.accept()
            print(f"Conectado al {cliente_tipo} en {addr}")
            return cliente_socket
        except socket.error:
            print(f"Error al conectar con {cliente_tipo}. Reintentando en {TIEMPO_ESPERA} segundos... (Intento {intento + 1}/{REINTENTOS})")
            time.sleep(TIEMPO_ESPERA)
    return None

# Crear sockets para el robot (video), Oculus (dirección) y mensajes
server_robot_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_robot_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Permitir reutilización de la dirección
server_robot_socket.bind(('0.0.0.0', 8083))
server_robot_socket.listen(1)

server_oculus_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_robot_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Permitir reutilización de la dirección
server_oculus_socket.bind(('0.0.0.0', 8085))
server_oculus_socket.listen(1)

server_mensaje_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_robot_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Permitir reutilización de la dirección
server_mensaje_socket.bind(('0.0.0.0', 8086))
server_mensaje_socket.listen(1)

# Función para recibir y procesar datos de video
def manejar_video(robot_socket, oculus_socket):
    while True:
        try:
            # Recibir el tamaño de la imagen
            data_size = b''
            while len(data_size) < 4:
                packet = robot_socket.recv(4 - len(data_size))
                if not packet:
                    raise ConnectionResetError("Conexión perdida con el robot.")
                data_size += packet

            # Desempaquetar el tamaño
            size = struct.unpack("I", data_size)[0]

            # Recibir datos de la imagen
            data = b""
            while len(data) < size:
                packet = robot_socket.recv(size - len(data))
                if not packet:
                    raise ConnectionResetError("Conexión perdida con el robot.")
                data += packet

            # Procesar la imagen y detección
            frame = cv2.imdecode(pickle.loads(data), cv2.IMREAD_COLOR)
            results = model(frame)
            for _, row in results.pandas().xyxy[0].iterrows():
                if row['name'] == 'person':
                    x1, y1, x2, y2 = int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax'])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, "Persona detectada", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Enviar la imagen procesada al Oculus
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            oculus_socket.sendall(struct.pack("l", len(buffer)) + buffer.tobytes())
        
        except (BrokenPipeError, ConnectionResetError):
            print("Conexión perdida con el robot. Intentando reconectar...")
            robot_socket = conectar_cliente(server_robot_socket, "robot")

# Función para recibir la dirección de Oculus y enviar los valores al cliente de video
def manejar_direccion(oculus_socket, mensaje_socket):
    while True:
        try:
            # Recibir la dirección desde el Oculus
            direccion = oculus_socket.recv(1024).decode('utf-8')
            if direccion == "Mirada al frente":
                mensaje_socket.sendall(b'0')
                print("Enviado 0 al cliente de video (frontal)")
            elif direccion == "Giro a la derecha":
                mensaje_socket.sendall(b'1')
                print("Enviado 1 al cliente de video (derecha)")
            elif direccion == "Giro a la izquierda":
                mensaje_socket.sendall(b'2')
                print("Enviado 2 al cliente de video (izquierda)")
        except (BrokenPipeError, ConnectionResetError):
            print("Conexión perdida con el Oculus.")
            oculus_socket = conectar_cliente(server_oculus_socket, "Oculus")

# Conectar los clientes
robot_socket = conectar_cliente(server_robot_socket, "robot")
oculus_socket = conectar_cliente(server_oculus_socket, "Oculus")
mensaje_socket = conectar_cliente(server_mensaje_socket, "cliente de mensajes")

# Iniciar hilos independientes para el manejo de video y el manejo de dirección
video_thread = threading.Thread(target=manejar_video, args=(robot_socket, oculus_socket))
direccion_thread = threading.Thread(target=manejar_direccion, args=(oculus_socket, mensaje_socket))
video_thread.start()
direccion_thread.start()

# Esperar a que ambos hilos terminen
video_thread.join()
direccion_thread.join()

# Cerrar conexiones
server_robot_socket.close()
server_oculus_socket.close()
server_mensaje_socket.close()