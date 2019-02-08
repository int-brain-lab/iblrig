# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, February 8th 2019, 11:39:30 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 8-02-2019 11:39:33.3333
import iotasks


def block_len():
    return iotasks.texp(factor=50, min_=20, max_=100)


print(block_len())
