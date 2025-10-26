from setuptools import setup, find_packages
from setuptools.command.install import install
import os
from glob import glob
import sys

package_name = 'mi_paquete'

# Detectar el Python del virtualenv
VENV_PYTHON = '/home/usuario/yolo_ws/bin/python3'

class CustomInstall(install):
    def run(self):
        install.run(self)
        # Fix shebangs después de instalar
        install_dir = os.path.join(self.install_scripts)
        if os.path.exists(install_dir):
            for script in os.listdir(install_dir):
                script_path = os.path.join(install_dir, script)
                if os.path.isfile(script_path):
                    with open(script_path, 'r') as f:
                        content = f.read()
                    if content.startswith('#!') and 'python' in content.split('\n')[0]:
                        lines = content.split('\n')
                        lines[0] = f'#!{VENV_PYTHON}'
                        with open(script_path, 'w') as f:
                            f.write('\n'.join(lines))
                        print(f"Fixed shebang in {script}")

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='usuario',
    maintainer_email='usuario@todo.com',
    description='YOLOv7 con ROS2 y Gazebo',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'yolo_v7 = mi_paquete.yolo_v7_node:main',
            'image_viewer = mi_paquete.image_viewer:main',
            'gazebo_launcher = mi_paquete.gazebo_launcher:main',
            'gz_bridge = mi_paquete.gz_bridge:main',
        ],
    },
    cmdclass={
        'install': CustomInstall,
    },
)

