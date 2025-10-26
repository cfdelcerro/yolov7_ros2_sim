import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    
    world_file = os.path.expanduser('~/gazebo_worlds/yolo_test_world.sdf')
    
    # Gazebo
    gazebo = ExecuteProcess(
        cmd=['gz', 'sim', world_file],
        output='screen'
    )
    
    # Bridge
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/camera@sensor_msgs/msg/Image@gz.msgs.Image'],
        output='screen'
    )
    
    return LaunchDescription([
        gazebo,
        bridge
    ])
