#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import subprocess
import signal

class GzBridge(Node):
    def __init__(self):
        super().__init__('gz_bridge')
        
        # Parámetros
        self.declare_parameter('topic', '/camera')
        self.declare_parameter('ros_type', 'sensor_msgs/msg/Image')
        self.declare_parameter('gz_type', 'gz.msgs.Image')
        
        topic = self.get_parameter('topic').get_parameter_value().string_value
        ros_type = self.get_parameter('ros_type').get_parameter_value().string_value
        gz_type = self.get_parameter('gz_type').get_parameter_value().string_value
        
        bridge_arg = f'{topic}@{ros_type}@{gz_type}'
        
        self.get_logger().info(f'Bridge: {bridge_arg}')
        
        # Lanzar bridge
        try:
            self.bridge_process = subprocess.Popen(
                ['ros2', 'run', 'ros_gz_bridge', 'parameter_bridge', bridge_arg],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.get_logger().info(f'✓ Bridge lanzado (PID: {self.bridge_process.pid})')
            
            self.timer = self.create_timer(2.0, self.check_bridge)
            
        except Exception as e:
            self.get_logger().error(f'Error: {e}')
            raise
    
    def check_bridge(self):
        if self.bridge_process.poll() is not None:
            self.get_logger().error('Bridge cerrado inesperadamente')
            rclpy.shutdown()
    
    def shutdown(self):
        if hasattr(self, 'bridge_process') and self.bridge_process.poll() is None:
            self.get_logger().info('Cerrando bridge...')
            self.bridge_process.terminate()
            try:
                self.bridge_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.bridge_process.kill()

def main(args=None):
    rclpy.init(args=args)
    node = GzBridge()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
