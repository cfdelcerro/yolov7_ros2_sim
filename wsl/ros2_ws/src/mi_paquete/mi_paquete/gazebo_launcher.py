#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import subprocess
import os
import signal
import sys

class GazeboLauncher(Node):
    def __init__(self):
        super().__init__('gazebo_launcher')
        
        # Parámetros
        self.declare_parameter('world_file', os.path.expanduser('~/gazebo_worlds/yolo_test_world.sdf'))
        self.declare_parameter('run_mode', True)  # True = -r (sin pausa)
        self.declare_parameter('verbose', False)  # Logs detallados
        self.declare_parameter('headless', False)  # Sin GUI
        
        world_file = self.get_parameter('world_file').get_parameter_value().string_value
        run_mode = self.get_parameter('run_mode').get_parameter_value().bool_value
        verbose = self.get_parameter('verbose').get_parameter_value().bool_value
        headless = self.get_parameter('headless').get_parameter_value().bool_value
        
        # Verificar que el mundo existe
        if not os.path.exists(world_file):
            self.get_logger().error(f'Mundo no encontrado: {world_file}')
            raise FileNotFoundError(f'Mundo no encontrado: {world_file}')
        
        self.get_logger().info(f'Lanzando Gazebo con mundo: {world_file}')
        
        # Construir comando
        cmd = ['gz', 'sim', world_file]
        
        if run_mode:
            cmd.append('-r')
            self.get_logger().info('Modo: Run (sin pausa)')
        
        if verbose:
            cmd.extend(['-v', '4'])
            self.get_logger().info('Modo: Verbose')
        
        if headless:
            cmd.append('-s')
            self.get_logger().info('Modo: Headless (sin GUI)')
        
        # Lanzar Gazebo como subproceso
        try:
            self.gazebo_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            self.get_logger().info(f'✓ Gazebo lanzado (PID: {self.gazebo_process.pid})')
            
            # Timer para verificar si Gazebo sigue corriendo
            self.timer = self.create_timer(2.0, self.check_gazebo)
            
        except Exception as e:
            self.get_logger().error(f'Error lanzando Gazebo: {e}')
            raise
    
    def check_gazebo(self):
        """Verifica si Gazebo sigue corriendo"""
        if self.gazebo_process.poll() is not None:
            self.get_logger().error('Gazebo se cerró inesperadamente')
            rclpy.shutdown()
    
    def shutdown(self):
        """Cierra Gazebo al terminar el nodo"""
        if hasattr(self, 'gazebo_process') and self.gazebo_process.poll() is None:
            self.get_logger().info('Cerrando Gazebo...')
            self.gazebo_process.terminate()
            try:
                self.gazebo_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.get_logger().warn('Gazebo no respondió, forzando cierre...')
                self.gazebo_process.kill()
            self.get_logger().info('✓ Gazebo cerrado')

def signal_handler(sig, frame):
    """Maneja Ctrl+C"""
    rclpy.shutdown()

def main(args=None):
    rclpy.init(args=args)
    
    # Configurar handler de señales
    signal.signal(signal.SIGINT, signal_handler)
    
    node = GazeboLauncher()
    
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
