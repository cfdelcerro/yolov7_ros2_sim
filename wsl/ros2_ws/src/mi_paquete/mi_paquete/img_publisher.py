import os
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import time

def cv2_to_imgmsg(frame_bgr):
    msg = Image()
    msg.height, msg.width = frame_bgr.shape[:2]
    msg.encoding = 'bgr8'
    msg.is_bigendian = 0
    msg.step = msg.width * 3
    msg.data = frame_bgr.tobytes()
    return msg


class ImagePublisher(Node):
    def __init__(self, image_path, fps=10):
        super().__init__('image_publisher')
        
        print(f'\n=== INICIANDO IMAGE PUBLISHER ===')
        print(f'Ruta: {image_path}')
        
        if not os.path.isfile(image_path):
            print(f'❌ ERROR: Archivo no encontrado')
            raise FileNotFoundError(image_path)
        
        self.frame = cv2.imread(image_path)
        if self.frame is None:
            print(f'❌ ERROR: No se pudo leer la imagen')
            raise RuntimeError('No se pudo leer la imagen')
        
        h, w = self.frame.shape[:2]
        print(f'✓ Imagen cargada: {w}x{h} píxeles')
        
        self.pub = self.create_publisher(Image, '/camera/image_raw', 10)
        print('✓ Publicador creado')
        
        # Esperar DDS
        print('Esperando descubrimiento DDS...')
        time.sleep(2)
        
        self.timer = self.create_timer(1.0/fps, self.loop)
        print(f'✓ Publicando a {fps} FPS')
        print(f'Topic: /camera/image_raw\n')
        
        self.frame_count = 0

    def loop(self):
        msg = cv2_to_imgmsg(self.frame)
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_frame'
        self.pub.publish(msg)
        
        self.frame_count += 1
        if self.frame_count == 1:
            print('✓ Publicando imagen...')
        elif self.frame_count % 100 == 0:
            print(f'Frames: {self.frame_count}')

def main():
    rclpy.init()
    # 🔧 CAMBIA ESTA RUTA a tu imagen
    image_path = r'C:\ai\yolov7\inference\images\bus.jpg'
    
    try:
        node = ImagePublisher(image_path=image_path, fps=10)
        print('Nodo activo. Ctrl+C para detener\n')
        rclpy.spin(node)
    except KeyboardInterrupt:
        print('\nDeteniendo...')
    except Exception as e:
        print(f'\n❌ ERROR: {e}')
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()