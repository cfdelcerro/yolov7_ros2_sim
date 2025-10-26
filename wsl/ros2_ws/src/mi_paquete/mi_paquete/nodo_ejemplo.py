import rclpy
from rclpy.node import Node

class MiNodo(Node):
    def __init__(self):
        super().__init__('mi_nodo')
        self.get_logger().info('¡Hola! Soy tu primer nodo ROS 2 en Python.')

def main(args=None):
    rclpy.init(args=args)
    nodo = MiNodo()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
