//ESTE CLIENTE DEBE DE ESTAR EN TU SCRIPT DE UNITY

using UnityEngine;
using UnityEngine.UI;
using UnityEngine.XR;
using System.Net.Sockets;
using System.IO;
using System.Text;
using System.Threading;

public class VideoReceiver : MonoBehaviour
{
    public RawImage rawImage;
    private Texture2D texture;
    private TcpClient client;
    private NetworkStream stream;
    private int reintentos = 5;
    private float tiempoEspera = 15f;  // Segundos entre intentos

    // Variable para almacenar la última dirección enviada
    private string ultimaDireccionEnviada = "";
    private float tiempoUltimoEnvio = 0f; // Para controlar la frecuencia de envío
    private float intervaloEnvio = 1f;    // Enviar datos máximo una vez por segundo

    void Start()
    {
        texture = new Texture2D(320, 240);
        rawImage.texture = texture;
        ConectarServidor();
    }

    void ConectarServidor()
    {
        for (int intento = 0; intento < reintentos; intento++)
        {
            try
            {
                client = new TcpClient("192.168.10.152", 8085);
                stream = client.GetStream();
                Debug.Log("Conexión establecida con el servidor.");
                return;
            }
            catch (SocketException)
            {
                Debug.LogError($"Error al conectar con el servidor. Reintentando en {tiempoEspera} segundos... (Intento {intento + 1}/{reintentos})");
                Thread.Sleep((int)(tiempoEspera * 1000));
            }
        }
        Debug.LogError("No se pudo conectar al servidor.");
    }

    void Update()
    {
        try
        {
            if (stream != null && stream.DataAvailable)
            {
                byte[] dataLength = new byte[4];
                stream.Read(dataLength, 0, dataLength.Length);
                int length = System.BitConverter.ToInt32(dataLength, 0);

                if (length > 0 && length < 10 * 1024 * 1024)
                {
                    byte[] imageData = new byte[length];
                    int bytesRead = 0;
                    while (bytesRead < length)
                    {
                        int read = stream.Read(imageData, bytesRead, length - bytesRead);
                        if (read == 0) throw new IOException("Conexión cerrada.");
                        bytesRead += read;
                    }

                    if (texture.LoadImage(imageData))
                    {
                        texture.Apply();
                        Debug.Log("Imagen mostrada correctamente.");
                    }
                }
            }

            // Lógica para detectar y enviar la dirección de giro
            if (client != null && stream != null)
            {
                // Controlar frecuencia de envío para evitar spam de mensajes
                if (Time.time - tiempoUltimoEnvio > intervaloEnvio)
                {
                    string message = DetectarDireccion();
                    // Enviar mensaje solo si es diferente al último enviado
                    if (!string.IsNullOrEmpty(message) && message != ultimaDireccionEnviada)
                    {
                        byte[] data = Encoding.ASCII.GetBytes(message);
                        stream.Write(data, 0, data.Length);
                        Debug.Log($"Mensaje enviado al servidor: {message}");

                        // Actualizar la última dirección enviada y el tiempo de envío
                        ultimaDireccionEnviada = message;
                        tiempoUltimoEnvio = Time.time;
                    }
                }
            }
        }
        catch (IOException)
        {
            Debug.LogError("Conexión perdida. Intentando reconectar...");
            ConectarServidor();
        }
    }

    string DetectarDireccion()
    {
        InputDevice headDevice = InputDevices.GetDeviceAtXRNode(XRNode.Head);
        Quaternion headRotation;
        if (headDevice.TryGetFeatureValue(CommonUsages.deviceRotation, out headRotation))
        {
            // Obtener el ángulo de rotación en el eje Y (Yaw)
            float yaw = headRotation.eulerAngles.y;

            // Convertir el rango de 0 a 360 grados en uno de -180 a 180 grados
            if (yaw > 180) yaw -= 360;

            // Determinar la dirección en función de los rangos especificados
            if (yaw >= 80 && yaw <= 100)
                return "Giro a la derecha";
            else if (yaw <= -80 && yaw >= -100)
                return "Giro a la izquierda";
            else if (yaw >= -20 && yaw <= 20)
                return "Mirada al frente";
        }
        
        return null;  // Sin cambio significativo en la posición
    }

    void OnDestroy()
    {
        stream?.Close();
        client?.Close();
    }
}