import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import time  # <-- Añadir

def cv2_to_imgmsg(frame_bgr):
    msg = Image()
    msg.height, msg.width = frame_bgr.shape[:2]
    msg.encoding = 'bgr8'
    msg.is_bigendian = 0
    msg.step = msg.width * 3
    msg.data = frame_bgr.tobytes()
    return msg

class CamPublisher(Node):
    def __init__(self, device_index=0, fps=20):
        super().__init__('cam_publisher')
        
        print(f'\n=== INICIANDO NODO CAM_PUBLISHER ===')
        
        self.pub = self.create_publisher(Image, '/camera/image_raw', 10)  # depth=10
        print('✓ Publicador creado')
        
        # ESPERAR para que DDS se estabilice
        print('Esperando descubrimiento DDS...')
        time.sleep(2)
        print('✓ Listo')
        
        print(f'Abriendo cámara {device_index}...')
        self.cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
        
        if not self.cap.isOpened():
            print(f'❌ ERROR: No se pudo abrir la cámara {device_index}')
            raise RuntimeError('Camera open failed')
        
        print('✓ Cámara abierta')

        self.cap.set(cv2.CAP_PROP_FPS, fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f'Resolución: {width}x{height} @ {fps} FPS')
        print(f'Topic: /camera/image_raw\n')

        period = 1.0 / fps
        self.timer = self.create_timer(period, self.loop)
        
        self.frame_count = 0

    def loop(self):
        ok, frame = self.cap.read()
        if not ok:
            return
        
        msg = cv2_to_imgmsg(frame)
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_frame'
        self.pub.publish(msg)
        
        self.frame_count += 1
        if self.frame_count == 1:
            print('✓ Publicando frames...')
        elif self.frame_count % 100 == 0:
            print(f'Frames: {self.frame_count}')

    def destroy_node(self):
        if hasattr(self, 'cap') and self.cap:
            self.cap.release()
        super().destroy_node()

def main():
    rclpy.init()
    try:
        node = CamPublisher(device_index=0, fps=20)
        print('Nodo activo. Ctrl+C para detener\n')
        rclpy.spin(node)
    except KeyboardInterrupt:
        print('\nDeteniendo...')
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()