# import iblrig.bonsai as bonsai
# TODO: check if this works!
from pythonosc import udp_client
import sys


if __name__ == "__main__":
    OSC_CLIENT_IP = "127.0.0.1"
    OSC_CLIENT_PORT = int(sys.argv[1])
    osc_client = udp_client.SimpleUDPClient(OSC_CLIENT_IP, OSC_CLIENT_PORT)
    osc_client.send_message("/x", 1)

    # stim = bonsai.osc_client('stim')
    # camera = bonsai.osc_client('camera')
    # mic = bonsai.osc_client('mic')
    # stim.send_message("/x", 1)
    # camera.send_message("/x", 1)
    # mic.send_message("/x", 1)