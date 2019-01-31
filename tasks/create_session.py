# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, January 31st 2019, 1:15:46 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 31-01-2019 01:15:49.4949
from pathlib import Path

import ibllib.io.params as params
import oneibl.params
from alf.one_iblrig import create


if __name__ == "__main__":
    pfile = Path(params.getfile('one_params'))
    if not pfile.exists():
        oneibl.params.setup_alyx_params()

    create()
