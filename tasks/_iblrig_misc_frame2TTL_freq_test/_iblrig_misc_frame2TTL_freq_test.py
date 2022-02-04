#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: Friday, January 4th 2019, 11:52:41 am
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
import json
import logging
import sys
from pathlib import Path

import dateutil.parser as parser
import iblrig.bonsai as bonsai
import iblrig.frame2TTL
import iblrig.params as params
import iblrig.path_helper as ph
import iblrig.raw_data_loaders as raw
from pybpodapi.protocol import Bpod, StateMachine

import user_settings  # noqa

sys.stdout.flush()

log = logging.getLogger("iblrig")
log.setLevel(logging.INFO)

PARAMS = params.load_params_file()
subj = "_iblrig_test_mouse"
datetime = parser.parse(user_settings.PYBPOD_SESSION).isoformat().replace(":", "_")
folder = Path(ph.get_iblrig_data_folder()) / subj / datetime
folder.mkdir()
bpod_data_file = folder / "bpod_ts_data.jsonable"
bpod_data_lengths_file = folder / "bpod_ts_data_lengths.jsonable"
bonsai_data_file = folder / "bonsai_ts_data.jsonable"
bonsai_data_lengths_file = folder / "bonsai_ts_data_lengths.jsonable"


def softcode_handler(data):
    if data:
        # Launch the workflow
        bonsai.start_frame2ttl_test(bonsai_data_file, bonsai_data_lengths_file)
    return


# Set the thresholds for Frame2TTL
iblrig.frame2TTL.get_and_set_thresholds()
# =============================================================================
# CONNECT TO BPOD
# =============================================================================
bpod = Bpod()
# Soft code handler function can run arbitrary code from within state machine
bpod.softcode_handler_function = softcode_handler

NITER = 500
log.info(f"Starting {NITER} iterations of 1000 sync square pulses @60Hz")
sys.stdout.flush()
# =============================================================================
#     Start state machine definition
# =============================================================================
for i in range(NITER):
    log.info(f"Starting iteration {i+1} of {NITER}")
    sma = StateMachine(bpod)
    sma.add_state(
        state_name="start",
        state_timer=2,
        output_actions=[("SoftCode", 1)],
        state_change_conditions={"Tup": "listen"},
    )
    sma.add_state(
        state_name="listen",
        state_timer=25,
        output_actions=[],
        state_change_conditions={"Tup": "exit"},
    )
    # Send state machine description to Bpod device
    bpod.send_state_machine(sma)
    # Run state machine
    if not bpod.run_state_machine(sma):  # Locks until state machine 'exit' is reached
        break

    data = bpod.session.current_trial.export()

    BNC1 = raw.get_port_events(data["Events timestamps"], name="BNC1")
    # print(BNC1, flush=True)
    # print(BNC1, flush=True)
    # print(len(BNC1), flush=True)
    if len(BNC1) == 1000:
        log.info("PASS 1000 pulses detected")
        sys.stdout.flush()
    else:
        log.error(f"FAILED to detect 1000 pulses: {len(BNC1)} != 1000")
        sys.stdout.flush()
    with open(bpod_data_file, "a") as f:
        f.write(json.dumps(BNC1))
        f.write("\n")
        f.flush()
    with open(bpod_data_lengths_file, "a") as f:
        f.write(json.dumps(len(BNC1)))
        f.write("\n")
        f.flush()

bpod.close()


if __name__ == "__main__":
    print("done", flush=True)
