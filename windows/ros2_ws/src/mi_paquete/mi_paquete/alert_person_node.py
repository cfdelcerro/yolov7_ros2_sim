import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class AlertPersonNode(Node):
    """
    Nodo ROS 2 que escucha /yolo/detections (String)
    y publica una alerta en /alerts/person si detecta la palabra 'person'.
    """
    def __init__(self):
        super().__init__('alert_person_node')

        # Parámetros configurables
        self.declare_parameter('detections_topic', 'yolo/detections')
        self.declare_parameter('alert_topic', 'alerts/person')
        self.declare_parameter('label', 'person')   # palabra clave a vigilar

        self.detections_topic = (
            self.get_parameter('detections_topic').get_parameter_value().string_value
        )
        self.alert_topic = (
            self.get_parameter('alert_topic').get_parameter_value().string_value
        )
        self.label = (
            self.get_parameter('label').get_parameter_value().string_value.lower()
        )

        # Suscriptor y publicador
        self.sub = self.create_subscription(
            String, self.detections_topic, self.cb_detections, 10
        )
        self.pub_alert = self.create_publisher(String, self.alert_topic, 10)

        self.get_logger().info(
            f'AlertPersonNode escuchando "{self.detections_topic}" buscando "{self.label}"'
        )

    def cb_detections(self, msg: String):
        """
        Callback del tópico de detecciones.
        msg.data contiene un texto tipo "person 0.94, car 0.81"
        """
        text = msg.data.lower()
        if self.label in text:
            alert = f'ALERTA: {self.label} detectada'
            self.get_logger().warn(alert)
            self.pub_alert.publish(String(data=alert))

def main():
    rclpy.init()
    node = AlertPersonNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

