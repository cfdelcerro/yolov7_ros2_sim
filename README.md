# 🚀 YOLOv7 + ROS 2 (Windows & WSL/Gazebo Integration)

Este proyecto integra **YOLOv7** con **ROS 2 Jazzy** tanto en Windows como en WSL 2 (Ubuntu 24.04 + Gazebo Harmonic).  
Permite procesar vídeo en tiempo real (webcam o simulación) y publicar detecciones, coordenadas y métricas operativas.

---

## 📂 Estructura del repositorio

!estructura.PNG

---

## ⚙️ Requisitos

### Windows
- ROS 2 Jazzy para Windows  
- Python 3.12 (pixi env)
- OpenCV + PyTorch + YOLOv7  
- OpenSSL x64 en PATH (`C:\Program Files\OpenSSL-Win64\bin`)

### WSL 2 / Ubuntu
- ROS 2 Jazzy (nativo en Ubuntu 24.04)
- Gazebo Harmonic
- Python + PyTorch + YOLOv7  

---

## 🪟 Ejecución en **Windows**

> Asegúrate de tener los pesos (`yolov7.pt`, `yolov7_dog.pt`) en `C:\ai\yolov7\` y el entorno ROS 2 cargado.

### 1️⃣ Publicar la cámara local
```bat
ros2 run mi_paquete cam_pub
👉 Publica los frames de la webcam en el tópico /camera/image_raw.

### 2️⃣ Ejecutar detección YOLOv7 general (COCO)
bat
Copiar código
ros2 run mi_paquete yolo_v7 --ros-args ^
  -p weights:=C:\ai\yolov7\yolov7.pt ^
  -p names_yaml:=C:\ai\yolov7\data\coco.yaml ^
  -p conf:=0.75 -p img_size:=640
👉 Lanza YOLOv7 en tiempo real con las clases COCO.

### 3️⃣ Detección especializada (ej. perros)
bat
Copiar código
ros2 run mi_paquete yolo_v7 --ros-args ^
  -p weights:=C:\ai\yolov7\yolov7_dog.pt ^
  -p names_yaml:=C:\ai\yolov7\data\dog.yaml ^
  -p conf:=0.75 -p img_size:=320
👉 Modelo entrenado solo para la clase “perro”.

### 4️⃣ Visualizar detecciones
bat
Copiar código
ros2 run mi_paquete image_viewer --ros-args -p image_topic:=/yolo/annotated
👉 Muestra la imagen anotada con las cajas de detección.

### 5️⃣ Nodo de alerta
bat
Copiar código
ros2 run mi_paquete alert_person_node
👉 Publica una alerta cuando se detecta una persona.

### 6️⃣ Inspeccionar tópicos
bat
Copiar código
ros2 topic echo yolo/detections
ros2 topic echo yolo/target_point
ros2 topic echo yolo/metrics
👉 Muestra las detecciones, coordenadas del objetivo y métricas (fps, confianza media, etc.).

### 7️⃣ Deshabilitar detección (servicio)
bat
Copiar código
ros2 service call /yolo/enable std_srvs/srv/SetBool "{data: false}"
👉 Llama al servicio para pausar o reanudar la detección en el nodo YOLOv7.

🐧 Ejecución en WSL 2 + Gazebo
Carga tu entorno (source ~/init.sh) y asegúrate de tener Gazebo y el puente ros_gz_bridge.

🖥️ Terminal 1 — Lanzar el mundo de prueba
bash
Copiar código
source ~/init.sh && gz sim ~/gazebo_worlds/yolo_test_world.sdf
👉 Inicia el mundo de Gazebo con una cámara simulada.

🧩 Terminal 2 — Puente Gazebo ↔ ROS 2
bash
Copiar código
source ~/init.sh && ros2 run ros_gz_bridge parameter_bridge /camera/image_raw@sensor_msgs/msg/Image@gz.msgs.Image
👉 Conecta el flujo de imagen de Gazebo con ROS 2.

🤖 Terminal 3 — Nodo YOLOv7 (detección simulada)
bash
Copiar código
source ~/init.sh && ros2 run mi_paquete yolo_v7 \
  --ros-args -p weights:=/home/usuario/ai/yolov7/yolov7.pt \
  -p device:=cuda -p conf:=0.75 -p input_topic:=/camera/image_raw
👉 Procesa las imágenes simuladas y publica /yolo/annotated.

🪞 Terminal 4 — Visualización
bash
Copiar código
source ~/init.sh && ros2 run mi_paquete image_viewer --ros-args -p image_topic:=/yolo/annotated
👉 Muestra las detecciones de la simulación en tiempo real.

📊 Métricas operativas
El nodo yolo_v7 publica en /yolo/metrics:

FPS promedio

Confianza media por clase

Tiempo de inferencia

Contadores de detecciones

🎬 Ejemplo de ejecución

