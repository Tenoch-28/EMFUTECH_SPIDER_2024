#ESTE CODIGO VA DENTRO DEL ROBOT JETHEXA SPIDER EN UN ARCHIVO PYTHON3


import socket
import cv2
import pickle
import struct
import time
import threading
import pygame as pg  # Importar pygame para leer el joystick
from jethexa_sdk import pwm_servo  # Importar SDK para el control de servos en Jetson Nano

# Configuración del servidor
IP_SERVIDOR = '192.168.10.152'
PUERTO_VIDEO = 8083
PUERTO_MENSAJE = 8086
REINTENTOS = 5
TIEMPO_ESPERA = 15

# Inicializar pygame y el servo
pg.init()
pwm_servo.pwm_servo1.start()

# Función para intentar reconectar el joystick si no está conectado
def check_joystick():
    if pg.joystick.get_count() == 0:
        print("Joystick desconectado. Intentando reconectar...")
        pg.joystick.quit()  # Reset pygame joystick module
        pg.joystick.init()
    if pg.joystick.get_count() > 0:
        joystick = pg.joystick.Joystick(0)
        joystick.init()
        print("Joystick reconectado.")
        return joystick
    return None

# Inicializar el joystick si está conectado
joystick = check_joystick()

# Intentar acceder a la cámara en múltiples índices
def conectar_camara():
    for i in range(4):  # Intentar del índice 0 al 3
        camara = cv2.VideoCapture(i)
        if camara.isOpened():
            camara.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            camara.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            print(f"Cámara conectada en el índice {i}")
            return camara
        else:
            print(f"No se encontró cámara en el índice {i}")
    print("No se pudo conectar ninguna cámara.")
    return None

# Función para recibir valores numéricos y controlar el servomotor en un hilo separado
def recibir_mensajes(mensaje_socket):
    global joystick
    while True:
        try:
            mensaje = mensaje_socket.recv(1024).decode('utf-8')

            # Control de servomotor basado en mensajes del servidor
            if mensaje == '0':
                pwm_servo.pwm_servo1.set_position(1500, 1000)
            elif mensaje == '1':
                pwm_servo.pwm_servo1.set_position(2000, 1000)
            elif mensaje == '2':
                pwm_servo.pwm_servo1.set_position(1000, 1000)

        except (BrokenPipeError, ConnectionResetError):
            print("Conexión perdida con el servidor de mensajes.")
            break

# Función para verificar y procesar el botón del joystick
def verificar_boton_joystick():
    global joystick
    while True:
        if joystick:
            # Procesar eventos para detectar si se presiona el botón 'triangle'
            for event in pg.event.get():
                if event.type == pg.JOYBUTTONDOWN and joystick.get_button(4):  # 4 es el índice de `triangle`
                    pwm_servo.pwm_servo1.set_position(1500, 1000)  # 0 grados (frontal)
                    print("Servo ajustado a 0 grados (frontal) por el botón triangle")
        else:
            # Intentar reconectar el joystick si está desconectado
            joystick = check_joystick()
        time.sleep(0.1)  # Reducir la carga en la CPU

# Conectar el socket de video y el socket de mensajes
def conectar_servidor(ip, puerto):
    cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for intento in range(REINTENTOS):
        try:
            cliente_socket.connect((ip, puerto))
            print(f"Conectado al servidor en el puerto {puerto}.")
            return cliente_socket
        except socket.error:
            time.sleep(TIEMPO_ESPERA)
    return None

video_socket = conectar_servidor(IP_SERVIDOR, PUERTO_VIDEO)
mensaje_socket = conectar_servidor(IP_SERVIDOR, PUERTO_MENSAJE)

# Iniciar hilos separados para recibir mensajes y verificar el joystick
mensaje_thread = threading.Thread(target=recibir_mensajes, args=(mensaje_socket,))
joystick_thread = threading.Thread(target=verificar_boton_joystick)
mensaje_thread.start()
joystick_thread.start()

# Intentar conectar la cámara
camara = conectar_camara()
if not camara:
    print("Error: No se pudo establecer conexión con la cámara.")
    exit()

# Enviar imágenes al servidor
while True:
    try:
        ret, frame = camara.read()
        if not ret:
            print("No se puede capturar la imagen.")
            break

        # Comprimir y enviar la imagen
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        data = pickle.dumps(buffer)
        message_size = struct.pack("l", len(data))
        video_socket.sendall(message_size + data)

        # Verificar el joystick en cada iteración para reconectar si es necesario
        joystick = check_joystick()

    except (BrokenPipeError, ConnectionResetError):
        print("Conexión perdida. Intentando reconectar el video...")
        video_socket = conectar_servidor(IP_SERVIDOR, PUERTO_VIDEO)
        if video_socket is None:
            break

# Liberar recursos
camara.release()
video_socket.close()
mensaje_socket.close()
pg.quit()
