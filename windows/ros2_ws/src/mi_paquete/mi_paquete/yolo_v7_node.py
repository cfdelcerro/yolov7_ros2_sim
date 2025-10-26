import os
import csv
import time
import cv2
import torch
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String
from geometry_msgs.msg import Point
from std_srvs.srv import SetBool

def cv2_to_imgmsg_rgb(frame_rgb: np.ndarray) -> Image:
    """Convierte un array RGB (H,W,3 uint8) a sensor_msgs/Image (rgb8)."""
    msg = Image()
    h, w = frame_rgb.shape[:2]
    msg.height = h
    msg.width = w
    msg.encoding = 'rgb8'
    msg.is_bigendian = 0
    msg.step = w * 3
    msg.data = frame_rgb.tobytes()
    return msg

class YoloV7Node(Node):
    def __init__(self):
        super().__init__('yolo_v7_node')

        # ---------------- Parámetros ----------------
        self.declare_parameter('weights', r'C:\ai\yolov7\yolov7.pt')
        self.declare_parameter('img_size', 640)
        self.declare_parameter('conf', 0.25)
        self.declare_parameter('device', 'cuda')  # 'cuda' o 'cpu'
        self.declare_parameter('names_yaml', r'C:\ai\yolov7\data\coco.yaml')

        # CSV de detecciones
        self.declare_parameter('save_csv', True)
        self.declare_parameter('csv_path', r'C:\ros2_ws\detections.csv')

        # Publicación de Point: mejor bbox de esta etiqueta
        self.declare_parameter('target_label', 'person')

        # Métricas operativas
        self.declare_parameter('metrics_period', 5.0)  # segundos entre publicaciones de métricas

        # ---------------- Leer parámetros ----------------
        weights = self.get_parameter('weights').get_parameter_value().string_value
        self.img_size = int(self.get_parameter('img_size').value)
        conf = float(self.get_parameter('conf').value)
        device_pref = self.get_parameter('device').get_parameter_value().string_value
        names_yaml = self.get_parameter('names_yaml').get_parameter_value().string_value

        self.save_csv = bool(self.get_parameter('save_csv').value)
        self.csv_path = self.get_parameter('csv_path').get_parameter_value().string_value
        self.target_label = self.get_parameter('target_label').get_parameter_value().string_value
        self.metrics_period = float(self.get_parameter('metrics_period').value)

        # ---------------- Dispositivo ----------------
        self.device = 'cuda' if (device_pref == 'cuda' and torch.cuda.is_available()) else 'cpu'

        # ---------------- IO ROS ----------------
        self.sub = self.create_subscription(Image, '/camera/image_raw', self.cb_image, qos_profile_sensor_data)
        self.pub_img = self.create_publisher(Image, 'yolo/annotated', qos_profile_sensor_data)
        self.pub_txt = self.create_publisher(String, 'yolo/detections', 10)
        self.pub_point = self.create_publisher(Point, 'yolo/target_point', 10)
        self.pub_metrics = self.create_publisher(String, 'yolo/metrics', 10)

        # Servicio enable/disable
        self.enabled = True
        self.srv = self.create_service(SetBool, 'yolo/enable', self.srv_enable_cb)

        # ---------------- Modelo ----------------
        self.get_logger().info('Cargando YOLOv7...')

        # Detectar ruta según sistema operativo
        if os.name == 'nt':  # Windows
            yolo_repo_path = 'C:/ai/yolov7'
        else:  # Linux/WSL
            yolo_repo_path = os.path.expanduser('~/ai/yolov7')

        self.model = torch.hub.load(yolo_repo_path, 'custom', weights, source='local', trust_repo=True)
        self.model.conf = conf
        self.model.to(self.device).eval()
        self.get_logger().info(f'Modelo listo en {self.device} | conf={conf} | size={self.img_size}')
        self.model = torch.hub.load('C:/ai/yolov7', 'custom', weights, source='local', trust_repo=True)
        self.model.conf = conf
        self.model.to(self.device).eval()
        self.get_logger().info(f'Modelo listo en {self.device} | conf={conf} | size={self.img_size}')

        # ---------------- Nombres ----------------
        self.names = self._load_names(names_yaml)

        # ---------------- CSV ----------------
        if self.save_csv:
            self._ensure_csv_header()

        # ---------------- Métricas (ventana) ----------------
        self._metrics_t0 = time.time()
        self._metrics_frames = 0
        self._metrics_det_count = 0
        self._metrics_infer_ms_sum = 0.0
        self._metrics_infer_frames = 0  # solo cuenta frames con detección habilitada
        self._metrics_timer = self.create_timer(self.metrics_period, self._publish_metrics)

    # ---------------- Servicio on/off ----------------
    def srv_enable_cb(self, req, res):
        self.enabled = bool(req.data)
        estado = 'habilitada' if self.enabled else 'deshabilitada'
        msg = f'Detección {estado} vía servicio.'
        self.get_logger().warn(msg)
        res.success = True
        res.message = msg
        return res

    # ---------------- Names YAML o fallback ----------------
    def _load_names(self, yaml_path: str):
        if yaml_path and os.path.exists(yaml_path):
            try:
                import yaml
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                names = data.get('names', None)
                if isinstance(names, dict):
                    names = [names[k] for k in sorted(names.keys(), key=lambda x: int(x))]
                if isinstance(names, list) and all(isinstance(x, str) for x in names):
                    self.get_logger().info(f'Cargados {len(names)} nombres desde {yaml_path}')
                    return names
                else:
                    self.get_logger().warn(f'Formato "names" no reconocido en {yaml_path}. Intento fallback.')
            except Exception as e:
                self.get_logger().warn(f'Fallo leyendo YAML de nombres: {e}. Intento fallback.')
        try:
            names = getattr(self.model, 'names', None)
            if isinstance(names, dict):
                names = [names[k] for k in sorted(names.keys())]
            if isinstance(names, list) and all(isinstance(x, str) for x in names):
                self.get_logger().info(f'Usando nombres del modelo ({len(names)} clases).')
                return names
        except Exception:
            pass
        self.get_logger().warn('Sin YAML válido ni nombres en el modelo; usaré índices numéricos.')
        return [str(i) for i in range(1000)]

    # ---------------- CSV helpers ----------------
    def _ensure_csv_header(self):
        """Crea directorio/archivo y escribe cabecera si el CSV no existe o está vacío."""
        path_dir = os.path.dirname(self.csv_path)
        if path_dir:
            os.makedirs(path_dir, exist_ok=True)
        header = ['stamp_sec', 'stamp_nanosec', 'label', 'score',
                  'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'width', 'height']
        need_header = (not os.path.exists(self.csv_path)) or (os.path.getsize(self.csv_path) == 0)
        if need_header:
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(header)
            self.get_logger().info(f'CSV creado con cabecera: {self.csv_path}')

    def _append_csv(self, stamp, label, score, x1, y1, x2, y2):
        """Añade una detección como nueva fila al CSV."""
        if not self.save_csv:
            return
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        w = (x2 - x1)
        h = (y2 - y1)
        try:
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow([
                    getattr(stamp, 'sec', 0), getattr(stamp, 'nanosec', 0),
                    label, f'{float(score):.4f}',
                    f'{x1:.1f}', f'{y1:.1f}', f'{x2:.1f}', f'{y2:.1f}',
                    f'{cx:.1f}', f'{cy:.1f}', f'{w:.1f}', f'{h:.1f}'
                ])
        except Exception as e:
            self.get_logger().error(f'Error escribiendo CSV: {e}')

    # ---------------- Callback principal ----------------
    @torch.inference_mode()
    def cb_image(self, msg: Image):
        """
        - Si enabled=True: corre YOLO, publica detecciones/CSV/Point e imagen anotada.
        - Si enabled=False: NO corre YOLO ni publica detecciones/CSV/Point; solo reenvía la imagen.
        En ambos casos, se contabilizan frames para FPS (métrica operativa).
        """
        # Reconstruir frame (se asume rgb8) → BGR
        arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
        frame_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        # Contador de frames (para FPS)
        self._metrics_frames += 1

        if not self.enabled:
            # Solo reenviar imagen sin anotaciones
            out_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            out_msg = cv2_to_imgmsg_rgb(out_rgb)
            out_msg.header.stamp = msg.header.stamp
            out_msg.header.frame_id = msg.header.frame_id if msg.header.frame_id else 'camera_frame'
            self.pub_img.publish(out_msg)
            return

        # --- Detección habilitada ---
        t0 = time.time()
        results = self.model(frame_bgr, size=self.img_size)  # x1,y1,x2,y2,conf,cls
        infer_ms = (time.time() - t0) * 1000.0
        self._metrics_infer_ms_sum += infer_ms
        self._metrics_infer_frames += 1

        det = results.xyxy[0]

        annotated = frame_bgr.copy()
        lines = []
        best_target = None  # (score, x1, y1, x2, y2, label)

        if det is not None and len(det) > 0:
            for *xyxy, conf, cls in det.tolist():
                x1, y1, x2, y2 = map(float, xyxy)
                cls_id = int(cls)
                label = self.names[cls_id] if 0 <= cls_id < len(self.names) else str(cls_id)
                score = float(conf)

                # Dibujo
                cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(annotated, f'{label} {score:.2f}', (int(x1), max(0, int(y1) - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

                # Texto y CSV
                lines.append(f'{label} {score:.2f}')
                self._append_csv(msg.header.stamp, label, score, x1, y1, x2, y2)

                # Mejor bbox para target_label
                if label.lower() == self.target_label.lower():
                    if (best_target is None) or (score > best_target[0]):
                        best_target = (score, x1, y1, x2, y2, label)

        # Publicar detecciones (texto) y contabilizar para métricas
        if lines:
            self.pub_txt.publish(String(data=', '.join(lines)))
            self._metrics_det_count += len(lines)

        # Publicar Point del mejor target (si existe)
        if best_target is not None:
            _, x1, y1, x2, y2, _ = best_target
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            p = Point()
            p.x = float(cx)
            p.y = float(cy)
            p.z = 0.0
            self.pub_point.publish(p)

        # Publicar imagen anotada
        out = cv2_to_imgmsg_rgb(annotated)
        out.header.stamp = msg.header.stamp
        out.header.frame_id = msg.header.frame_id if msg.header.frame_id else 'camera_frame'
        self.pub_img.publish(out)

    # ---------------- Métricas operativas ----------------
    def _publish_metrics(self):
        elapsed = max(time.time() - self._metrics_t0, 1e-6)
        fps = self._metrics_frames / elapsed
        dets_per_frame = (self._metrics_det_count / self._metrics_frames) if self._metrics_frames > 0 else 0.0
        avg_infer_ms = (self._metrics_infer_ms_sum / self._metrics_infer_frames) if self._metrics_infer_frames > 0 else 0.0

        msg = f'fps={fps:.1f}, detections_per_frame={dets_per_frame:.2f}, avg_inference_ms={avg_infer_ms:.1f}'
        self.pub_metrics.publish(String(data=msg))

        # Reset ventana
        self._metrics_t0 = time.time()
        self._metrics_frames = 0
        self._metrics_det_count = 0
        self._metrics_infer_ms_sum = 0.0
        self._metrics_infer_frames = 0

def main():
    rclpy.init()
    node = YoloV7Node()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
