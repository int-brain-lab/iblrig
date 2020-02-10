#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Monday, February 18th 2019, 1:46:37 pm
import sys

from iblrig.bpod_helper import bpod_lights


if __name__ == "__main__":
    if len(sys.argv) == 2:
        comport = params.get_board_comport()
        command = sys.argv[1]
    else:
        comport = sys.argv[1]
        command = sys.argv[2]

    bpod_lights(comport, int(command))
