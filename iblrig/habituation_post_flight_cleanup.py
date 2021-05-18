import iblrig.bonsai as bonsai
import iblrig.path_helper as ph
from iblrig.bpod_helper import bpod_lights
from iblrig.poop_count import poop


# Close stimulus and camera workflows
bonsai.osc_client('stim').send_message("/x", 1)
bonsai.osc_client('camera').send_message("/x", 1)  # Camera workflow has mic recording also
# Turn bpod lights back on
bpod_lights(None, 0)
# Log poop count (for latest session on rig)
poop()
# cleanup pybpod data
ph.get_iblrig_params_folder()

# Finally if Alyx is present try to register session and update the params in lab_location

