# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Thursday, March 28th 2019, 7:19:15 pm
import blocks
import numpy as np
import misc

positions = np.array([-35, 35])
contrasts = np.array([1., 0.25, 0.125, 0.0625, 0.0])
# sig_contrast_mat = np.matmul(
#     np.sign(positions).reshape(2, 1), contrasts.reshape(1, 5))

probs_positions = np.array([0.5, 0.5])
probs_contrasts = np.array(misc.get_biased_probs(5))
prob_mat = np.matmul(probs_positions.reshape(2, 1),
                     probs_contrasts.reshape(1, 5))


# def make_contrasts():
len_block = [90]
pos = [-35] * int(len_block[0] / 2) + [35] * int(len_block[0] / 2)
cont = np.sort(contrasts.tolist() * 10)[::-1][:-5].tolist() * 2
cont = np.sort(contrasts.tolist() * 10)[::-1][:-5].tolist()

pc = np.array([pos, cont+cont]).T

np.random.shuffle(pc)  # only shuffles on the first dimension

prob_left = 0.8 if blocks.draw_position([-35, 35], 0.5) < 0 else 0.2

while len(pos) < 2001:
    len_block.append(blocks.get_block_len(60, min_=20, max_=100))
    for x in range(len_block[-1]):
        pos.append(blocks.draw_position([-35, 35], prob_left))
        cont.append(misc.draw_contrast())
        # do this in PC space
    prob_left = np.round(np.abs(1 - prob_left), 1)

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from ibllib.dsp.smooth import smooth
    plt.plot(pos, 'o')
    plt.plot(smooth(pos, window_len=20, window='flat'))
    [plt.axvline(x) for x in np.cumsum(len_block)]
    plt.show()

    print('.')
