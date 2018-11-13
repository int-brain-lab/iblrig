from pythonosc import udp_client
from task_settings import OSC_CLIENT_IP, OSC_CLIENT_PORT

osc_client = udp_client.SimpleUDPClient(OSC_CLIENT_IP, OSC_CLIENT_PORT)

osc_client.send_message("/x", 1)
