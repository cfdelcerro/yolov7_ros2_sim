import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
import time

class ImageViewer(Node):
    def __init__(self):
        super().__init__('image_viewer')

        # Parámetros
        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('window_name', 'ROS2 Image Viewer')
        self.declare_parameter('display_width', 0)  # 0 = sin redimensionar

        self.image_topic = self.get_parameter('image_topic').get_parameter_value().string_value
        self.window_name = self.get_parameter('window_name').get_parameter_value().string_value
        self.display_width = int(self.get_parameter('display_width').value)

        self.sub = self.create_subscription(
            Image,
            self.image_topic,
            self.callback,
            qos_profile_sensor_data
        )
        self.get_logger().info(f'Image Viewer iniciado. Suscrito a {self.image_topic}')

        self._last_time = None
        self._first_log = True

        cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)

    def _to_bgr8(self, msg: Image) -> np.ndarray:
        """
        Convierte sensor_msgs/Image a ndarray BGR8 para mostrar en OpenCV.
        Soporta: rgb8, bgr8, rgba8, bgra8, mono8, mono16, 16UC1.
        """
        enc = msg.encoding.lower()
        h, w = msg.height, msg.width
        # msg.step = bytes por fila
        # Para uint8 3 canales, step suele ser w*3. No asumimos: usamos reshape con step.
        buf = np.frombuffer(msg.data, dtype=np.uint8)

        try:
            if enc in ('rgb8', 'bgr8', 'rgba8', 'bgra8'):
                # deduce canales por encoding
                ch = 3 if enc in ('rgb8', 'bgr8') else 4
                # reshape usando step para robustez
                row_stride = msg.step
                # bytes esperados mínimo
                expected = row_stride * h
                if buf.size < expected:
                    raise ValueError(f'Buffer menor que step*h ({buf.size} < {expected})')
                arr = np.ndarray(shape=(h, row_stride), dtype=np.uint8, buffer=buf)
                # recorta a w*ch y re-reshape a (h,w,ch)
                arr = arr[:, :w * ch].reshape(h, w, ch)

                if enc == 'rgb8':
                    frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                elif enc == 'bgr8':
                    frame = arr
                elif enc == 'rgba8':
                    frame = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                elif enc == 'bgra8':
                    frame = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

                return frame

            elif enc in ('mono8',):
                row_stride = msg.step
                expected = row_stride * h
                if buf.size < expected:
                    raise ValueError(f'Buffer menor que step*h ({buf.size} < {expected})')
                arr = np.ndarray(shape=(h, row_stride), dtype=np.uint8, buffer=buf)
                arr = arr[:, :w]  # 1 canal
                return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)

            elif enc in ('mono16', '16uc1'):
                # reinterpretar como uint16
                buf16 = np.frombuffer(msg.data, dtype=np.uint16)
                # step aquí es en bytes; por fila hay msg.step/2 elementos uint16
                elems_per_row = msg.step // 2
                expected = elems_per_row * h
                if buf16.size < expected:
                    raise ValueError(f'Buffer16 menor que (step/2)*h ({buf16.size} < {expected})')
                arr16 = np.ndarray(shape=(h, elems_per_row), dtype=np.uint16, buffer=buf16)
                arr16 = arr16[:, :w]  # 1 canal

                # Escalado a 8 bits para visualizar
                # normaliza al rango 0..255 de forma robusta
                min_val, max_val = np.min(arr16), np.max(arr16)
                if max_val == min_val:
                    img8 = np.zeros_like(arr16, dtype=np.uint8)
                else:
                    img8 = ((arr16 - min_val) * (255.0 / (max_val - min_val))).astype(np.uint8)
                return cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)

            else:
                # Fallback heurístico: intenta deducir canales por step
                self.get_logger().warn(f'Encoding no soportado: {msg.encoding}. Intento heurístico.')
                ch_guess = msg.step // w if (w > 0) else 3
                if ch_guess not in (1, 3, 4):
                    ch_guess = 3
                arr = np.frombuffer(msg.data, dtype=np.uint8)
                if arr.size < h * w * ch_guess:
                    raise ValueError('Buffer insuficiente para heurística')
                arr = arr.reshape((h, w, ch_guess)) if ch_guess > 1 else arr.reshape((h, w))
                if ch_guess == 1:
                    return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                elif ch_guess == 3:
                    return arr  # suponemos BGR
                else:
                    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

        except Exception as e:
            self.get_logger().error(f'Error convirtiendo imagen: {e}')
            return None

    def _overlay_info(self, frame: np.ndarray, enc: str, fps: float):
        text = f'{enc} | {frame.shape[1]}x{frame.shape[0]} | {fps:.1f} FPS'
        cv2.putText(frame, text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

    def callback(self, msg: Image):
        t = time.time()
        fps = 0.0
        if self._last_time is not None:
            dt = t - self._last_time
            if dt > 0:
                fps = 1.0 / dt
        self._last_time = t

        frame = self._to_bgr8(msg)
        if frame is None:
            return

        if self._first_log:
            self.get_logger().info(f'Primer frame: encoding={msg.encoding}, size={frame.shape[1]}x{frame.shape[0]}')
            self._first_log = False

        # Redimensionar si se pidió display_width
        if self.display_width > 0 and frame.shape[1] != self.display_width:
            scale = self.display_width / float(frame.shape[1])
            new_h = int(round(frame.shape[0] * scale))
            frame = cv2.resize(frame, (self.display_width, new_h), interpolation=cv2.INTER_AREA)

        self._overlay_info(frame, msg.encoding, fps)

        cv2.imshow(self.window_name, frame)
        # Importante para refrescar ventana (no bloquear el spin)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC para cerrar
            self.get_logger().info('ESC pulsado: cerrando visor.')
            rclpy.shutdown()

def main():
    rclpy.init()
    node = ImageViewer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        cv2.destroyAllWindows()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
