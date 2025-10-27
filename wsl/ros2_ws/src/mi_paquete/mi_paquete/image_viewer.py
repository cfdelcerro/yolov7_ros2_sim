#!/home/usuario/yolo_ws/bin/python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
import cv2
import numpy as np

class ImageViewerNode(Node):
    def __init__(self):
        super().__init__('image_viewer_node')

        # Parámetro para el topic a visualizar
        self.declare_parameter('image_topic', '/yolo/annotated')
        image_topic = self.get_parameter('image_topic').get_parameter_value().string_value

        self.get_logger().info(f'Suscribiéndose a: {image_topic}')

        # Suscriptor con QoS de sensor (match con publicador típico de cámaras)
        self.subscription = self.create_subscription(
            Image,
            image_topic,
            self.image_callback,
            qos_profile_sensor_data
        )

        # Ventana OpenCV
        self.window_name = f'Viewer: {image_topic}'
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)

        self.frame_count = 0
        self.get_logger().info('Image Viewer listo')

    def _to_numpy_respecting_step(self, msg: Image):
        """
        Convierte sensor_msgs/Image -> np.ndarray respetando msg.step (stride por fila).
        Devuelve (frame_bgr, ok)
        """
        H, W, ROW_STEP = msg.height, msg.width, msg.step
        buf = np.frombuffer(msg.data, dtype=np.uint8)

        # Validación rápida de tamaño de buffer
        if buf.size < ROW_STEP * H:
            self.get_logger().warn(
                f'Buffer más pequeño que step*height: {buf.size} < {ROW_STEP}*{H}'
            )

        try:
            if msg.encoding == 'bgr8' or msg.encoding == 'rgb8':
                C = 3
                row = buf.reshape(H, ROW_STEP)[:, :W * C]
                img = row.reshape(H, W, C)
                if msg.encoding == 'rgb8':
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                return np.ascontiguousarray(img), True

            elif msg.encoding == 'bgra8' or msg.encoding == 'rgba8':
                C = 4
                row = buf.reshape(H, ROW_STEP)[:, :W * C]
                img = row.reshape(H, W, C)
                if msg.encoding == 'rgba8':
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                else:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return np.ascontiguousarray(img), True

            elif msg.encoding == 'mono8':
                row = buf.reshape(H, ROW_STEP)[:, :W]
                gray = row.reshape(H, W)
                bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                return np.ascontiguousarray(bgr), True

            else:
                self.get_logger().warn(f'Encoding no soportado: {msg.encoding}')
                return None, False
        except Exception as e:
            self.get_logger().error(f'Error reconstruyendo imagen: {e}')
            return None, False

    def image_callback(self, msg: Image):
        self.frame_count += 1

        frame, ok = self._to_numpy_respecting_step(msg)
        if not ok or frame is None:
            return

        # Overlay informativo
        try:
            cv2.putText(frame, f'Frame: {self.frame_count}', (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f'{msg.width}x{msg.height} {msg.encoding}', (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        except Exception as e:
            # Si por lo que sea frame no es uint8 contiguo (no debería pasar), lo forzamos:
            frame = np.ascontiguousarray(np.clip(frame, 0, 255).astype(np.uint8))
            cv2.putText(frame, f'Frame: {self.frame_count}', (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Mostrar
        cv2.imshow(self.window_name, frame)
        # ESC para cerrar
        if cv2.waitKey(1) & 0xFF == 27:
            self.get_logger().info('ESC pulsado. Cerrando visor.')
            rclpy.shutdown()

        # Log cada 30 frames
        if self.frame_count % 30 == 0:
            self.get_logger().info(f'Frames recibidos: {self.frame_count}')

    def destroy_node(self):
        try:
            cv2.destroyAllWindows()
        finally:
            super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = ImageViewerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

if __name__ == '__main__':
    main()
