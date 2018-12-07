from pythonosc import udp_client
import sys

if __name__ == "__main__":
    OSC_CLIENT_IP = '127.0.0.1'
    OSC_CLIENT_PORT = int(sys.argv[1])
    osc_client = udp_client.SimpleUDPClient(OSC_CLIENT_IP, OSC_CLIENT_PORT)
    osc_client.send_message("/x", 1)
