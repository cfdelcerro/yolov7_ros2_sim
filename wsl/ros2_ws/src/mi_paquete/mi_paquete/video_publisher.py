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


class VideoPublisher(Node):
    def __init__(self, video_path, fps=None):
        super().__init__('video_publisher')
        
        print(f'\n=== INICIANDO VIDEO PUBLISHER ===')
        print(f'Ruta: {video_path}')
        
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            print(f'❌ ERROR: No se pudo abrir el vídeo')
            raise RuntimeError(f'No se pudo abrir: {video_path}')
        
        self.pub = self.create_publisher(Image, '/camera/image_raw', 10)
        print('✓ Publicador creado')
        
        # Esperar DDS
        print('Esperando descubrimiento DDS...')
        time.sleep(2)

        # FPS del video o especificado
        self.fps = fps or self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f'✓ Vídeo: {width}x{height}, {total_frames} frames')
        print(f'✓ Publicando a {self.fps:.2f} FPS')
        print(f'Topic: /camera/image_raw\n')
        
        self.timer = self.create_timer(1.0/self.fps, self.loop)
        self.frame_count = 0

    def loop(self):
        ok, frame = self.cap.read()
        if not ok:
            # Reiniciar video (loop)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            print('↻ Reiniciando vídeo')
            return
        
        msg = cv2_to_imgmsg(frame)
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera_frame'
        self.pub.publish(msg)
        
        self.frame_count += 1
        if self.frame_count == 1:
            print('✓ Publicando vídeo...')
        elif self.frame_count % 100 == 0:
            print(f'Frames: {self.frame_count}')

    def destroy_node(self):
        if hasattr(self, 'cap') and self.cap:
            self.cap.release()
            print('✓ Vídeo liberado')
        super().destroy_node()

def main():
    rclpy.init()
    # 🔧 CAMBIA ESTA RUTA a tu video
    video_path = r'C:\ai\sample.mp4'
    
    try:
        node = VideoPublisher(video_path=video_path, fps=None)
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