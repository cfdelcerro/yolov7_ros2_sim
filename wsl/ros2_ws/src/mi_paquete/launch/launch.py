import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    
    # Ruta al mundo de Gazebo
    world_file = os.path.expanduser('~/gazebo_worlds/yolo_test.world')
    
    # Lanzar Gazebo
    gazebo_launch = ExecuteProcess(
        cmd=['gazebo', '--verbose', world_file, '-s', 'libgazebo_ros_factory.so'],
        output='screen'
    )
    
    # Esperar a que Gazebo inicie antes de lanzar YOLOv7
    yolo_node = TimerAction(
        period=5.0,  # Espera 5 segundos
        actions=[
            Node(
                package='mi_paquete',
                executable='yolo_v7',
                name='yolo_v7_node',
                parameters=[{
                    'weights': os.path.expanduser('~/ai/yolov7/yolov7.pt'),
                    'names_yaml': os.path.expanduser('~/ai/yolov7/data/coco.yaml'),
                    'conf': 0.75,
                    'img_size': 640,
                    'input_topic': '/camera/image_raw',
                    'device': 'cuda'
                }],
                output='screen'
            )
        ]
    )
    
    # Viewer
    viewer_node = TimerAction(
        period=6.0,  # Espera 6 segundos
        actions=[
            Node(
                package='mi_paquete',
                executable='image_viewer',
                name='image_viewer_node',
                parameters=[{
                    'image_topic': '/yolo/annotated'
                }],
                output='screen'
            )
        ]
    )
    
    return LaunchDescription([
        gazebo_launch,
        yolo_node,
        viewer_node
    ])