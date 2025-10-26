from setuptools import find_packages, setup

package_name = 'mi_paquete'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Usuario',
    maintainer_email='Usuario@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'nodo_ejemplo = mi_paquete.nodo_ejemplo:main',
            'cam_pub = mi_paquete.cam_publisher:main',
            'img_pub = mi_paquete.img_publisher:main',
            'video_pub = mi_paquete.video_publisher:main',
            'image_viewer = mi_paquete.image_viewer:main',
            'yolo_v7 = mi_paquete.yolo_v7_node:main',
            'alert_person_node = mi_paquete.alert_person_node:main',

        ],
    },
)
