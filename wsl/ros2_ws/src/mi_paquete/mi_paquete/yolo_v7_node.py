#!/usr/bin/env python3
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
from cv_bridge import CvBridge


class YoloV7Node(Node):
    def __init__(self):
        super().__init__('yolo_v7_node')

        # ---------------- Parámetros ----------------
        self.declare_parameter('weights', os.path.expanduser('~/ai/yolov7/yolov7.pt'))
        self.declare_parameter('img_size', 640)
        self.declare_parameter('conf', 0.25)
        self.declare_parameter('device', 'cuda')
        self.declare_parameter('names_yaml', os.path.expanduser('~/ai/yolov7/data/coco.yaml'))
        self.declare_parameter('save_csv', True)
        self.declare_parameter('csv_path', os.path.expanduser('~/ros2_ws/detections.csv'))
        self.declare_parameter('target_label', 'person')
        self.declare_parameter('metrics_period', 5.0)
        self.declare_parameter('input_topic', '/camera/image_raw')

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
        input_topic = self.get_parameter('input_topic').get_parameter_value().string_value

        # ---------------- Dispositivo ----------------
        self.device = 'cuda' if (device_pref == 'cuda' and torch.cuda.is_available()) else 'cpu'

        # ---------------- IO ROS ----------------
        self.bridge = CvBridge()
        self.sub = self.create_subscription(Image, input_topic, self.cb_image, qos_profile_sensor_data)

        # PUBLICA EN RUTA ABSOLUTA PARA EVITAR CONFUSIONES DE NAMESPACE
        self.pub_img = self.create_publisher(Image, '/yolo/annotated', qos_profile_sensor_data)
        self.pub_txt = self.create_publisher(String, '/yolo/detections', 10)
        self.pub_point = self.create_publisher(Point, '/yolo/target_point', 10)
        self.pub_metrics = self.create_publisher(String, '/yolo/metrics', 10)

        self.enabled = True
        self.srv = self.create_service(SetBool, '/yolo/enable', self.srv_enable_cb)

        # ---------------- Modelo ----------------
        self.get_logger().info('Cargando YOLOv7...')
        yolo_repo_path = os.path.expanduser('~/ai/yolov7')
        # source='local' requiere que exista el repo local de yolov7
        self.model = torch.hub.load(yolo_repo_path, 'custom', weights, source='local', trust_repo=True)
        self.model.conf = conf
        self.model.to(self.device).eval()
        self.get_logger().info(f'Modelo listo en {self.device} | conf={conf} | size={self.img_size} | topic={input_topic}')

        # ---------------- Nombres ----------------
        self.names = self._load_names(names_yaml)

        # ---------------- CSV ----------------
        if self.save_csv:
            self._ensure_csv_header()

        # ---------------- Métricas ----------------
        self._metrics_t0 = time.time()
        self._metrics_frames = 0
        self._metrics_det_count = 0
        self._metrics_infer_ms_sum = 0.0
        self._metrics_infer_frames = 0
        self._metrics_timer = self.create_timer(self.metrics_period, self._publish_metrics)

    def srv_enable_cb(self, req, res):
        self.enabled = bool(req.data)
        estado = 'habilitada' if self.enabled else 'deshabilitada'
        msg = f'Detección {estado} vía servicio.'
        self.get_logger().warn(msg)
        res.success = True
        res.message = msg
        return res

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
                # ordenar por clave si es dict
                keys_sorted = sorted(names.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x))
                names = [names[k] for k in keys_sorted]
            if isinstance(names, list) and all(isinstance(x, str) for x in names):
                self.get_logger().info(f'Usando nombres del modelo ({len(names)} clases).')
                return names
        except Exception:
            pass
        self.get_logger().warn('Sin YAML válido ni nombres en el modelo; usaré índices numéricos.')
        return [str(i) for i in range(1000)]

    def _ensure_csv_header(self):
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

    @torch.inference_mode()
    def cb_image(self, msg: Image):
        # DEBUG
        self.get_logger().info(f'🔵 CALLBACK! {msg.width}x{msg.height} | {msg.encoding} | enabled={self.enabled}')

        # Reconstruir frame según encoding → SIEMPRE A BGR (OpenCV)
        try:
            if msg.encoding == 'rgb8':
                arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
                frame_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            elif msg.encoding == 'bgr8':
                frame_bgr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
            elif msg.encoding == 'mono8':
                arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width))
                frame_bgr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            else:
                self.get_logger().warn(f'Encoding no soportado: {msg.encoding}')
                return
        except Exception as e:
            self.get_logger().error(f'Error convirtiendo imagen: {e}')
            return

        # DEBUG
        self.get_logger().info(f'📸 Frame convertido: shape={frame_bgr.shape}, range=[{frame_bgr.min()}, {frame_bgr.max()}]')

        # Métricas
        self._metrics_frames += 1

        # Si está deshabilitado, reenvía la imagen cruda como anotada (BGR)
        if not self.enabled:
            annotated = frame_bgr
            annotated = np.clip(annotated, 0, 255).astype(np.uint8)
            annotated = np.ascontiguousarray(annotated)
            out_msg = self.bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
            out_msg.header.stamp = msg.header.stamp
            out_msg.header.frame_id = msg.header.frame_id if msg.header.frame_id else 'camera_frame'
            self.pub_img.publish(out_msg)
            return

        # --- Detección habilitada ---
        t0 = time.time()
        results = self.model(frame_bgr, size=self.img_size)
        infer_ms = (time.time() - t0) * 1000.0
        self._metrics_infer_ms_sum += infer_ms
        self._metrics_infer_frames += 1

        det = results.xyxy[0]  # tensor Nx6

        # DEBUG
        self.get_logger().info(f'🤖 YOLO procesó: {len(det) if det is not None else 0} detecciones en {infer_ms:.1f}ms')

        annotated = frame_bgr.copy()
        self.get_logger().info(f'📝 Annotated antes de dibujar: range=[{annotated.min()}, {annotated.max()}]')

        lines = []
        best_target = None

        if det is not None and len(det) > 0:
            for *xyxy, conf, cls in det.tolist():
                x1, y1, x2, y2 = map(float, xyxy)
                cls_id = int(cls)
                label = self.names[cls_id] if 0 <= cls_id < len(self.names) else str(cls_id)
                score = float(conf)

                cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(annotated, f'{label} {score:.2f}', (int(x1), max(0, int(y1) - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

                lines.append(f'{label} {score:.2f}')
                self._append_csv(msg.header.stamp, label, score, x1, y1, x2, y2)

                if label.lower() == self.target_label.lower():
                    if (best_target is None) or (score > best_target[0]):
                        best_target = (score, x1, y1, x2, y2, label)

        self.get_logger().info(f'🎨 Annotated después de dibujar: range=[{annotated.min()}, {annotated.max()}]')

        if lines:
            self.pub_txt.publish(String(data=', '.join(lines)))
            self._metrics_det_count += len(lines)

        if best_target is not None:
            _, x1, y1, x2, y2, _ = best_target
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            p = Point()
            p.x = float(cx)
            p.y = float(cy)
            p.z = 0.0
            self.pub_point.publish(p)

        # --- Publicación segura: BGR8 + contiguidad ---
        annotated = np.clip(annotated, 0, 255).astype(np.uint8)
        annotated = np.ascontiguousarray(annotated)
        out_msg = self.bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
        out_msg.header.stamp = msg.header.stamp
        out_msg.header.frame_id = msg.header.frame_id if msg.header.frame_id else 'camera_frame'
        self.get_logger().info('📤 Publicando imagen anotada (bgr8, contigua)')
        self.pub_img.publish(out_msg)

    def _publish_metrics(self):
        elapsed = max(time.time() - self._metrics_t0, 1e-6)
        fps = self._metrics_frames / elapsed
        dets_per_frame = (self._metrics_det_count / self._metrics_frames) if self._metrics_frames > 0 else 0.0
        avg_infer_ms = (self._metrics_infer_ms_sum / self._metrics_infer_frames) if self._metrics_infer_frames > 0 else 0.0

        msg = f'fps={fps:.1f}, detections_per_frame={dets_per_frame:.2f}, avg_inference_ms={avg_infer_ms:.1f}'
        self.pub_metrics.publish(String(data=msg))

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
