"""
RE spits out ticks [-512, 512] which is a full turn of the wheel
I linearly rescale it to [-180, 180]  # wheel degrees
The screen "wants" a positionX from [-1, 1] where 0 is the center of the screen
I I then divide all positions as they are coming by a GainFactor
GainFactor = 1 / (mm_per_deg * UserDefinedGain)
UserDefinedGain = 4.0
mm_per_deg = (2 * Pi * WheelRadius) / 360
where WheelRadius = 31mm

Now that I have the transformation done as if the stimulus would start from the center I need to
offset it by the InitPosition of the stimulus (either -35 or 35)
Then for "safety" I pass an unwrapping function for the cases when the stimulus ight go over the
edge of the screen
I do this in the same go
((InitPosition + out_value) + 180) % 360 - 180 and that is what is sent to the screen...

((-35 + (1 / (1 / ((math.pi * 2 * 31) / 360) * 4))) + 180) % 360 -180
"""
import math
import matplotlib.pyplot as plt


WHEEL_RADIUS = 31
USER_DEFINED_GAIN = 4.0
MM_PER_DEG = (2 * math.pi * WHEEL_RADIUS) / 360
GAIN_FACTOR = 1 / (MM_PER_DEG * USER_DEFINED_GAIN)


def get_scale_shift(from_min, from_max, to_min, to_max):
    scale = (to_max - to_min) / (from_max - from_min)
    shift = -from_min * scale + to_min
    return scale, shift


def rescale(input, from_min, from_max, to_min, to_max):
    scale, shift = get_scale_shift(from_min, from_max, to_min, to_max)
    try:
        iter(input)
    except TypeError:
        input = [input]

    for i in input:
        yield i * scale + shift


RE_TICKS = range(-512, 512)
RE_TICK_DEG_VALUE = list(rescale(RE_TICKS, -512, 512, -180, 180))


def pos_on_screen(pos, init_pos):
    try:
        iter(pos)
    except TypeError:
        pos = [pos]

    for p in pos:
        yield (((p / GAIN_FACTOR) + init_pos) + 180) % 360 - 180


relative_wheel_degrees = range(-20, 21)  # RE_TICK_DEG_VALUE
absolute_screen_deg_form_left_stim = list(pos_on_screen(relative_wheel_degrees, -35))
absolute_screen_deg_form_right_stim = list(pos_on_screen(relative_wheel_degrees, 35))

ax = plt.subplot(111)
ax.plot(
    relative_wheel_degrees,
    absolute_screen_deg_form_left_stim,
    c="b",
    ls="--",
    marker=".",
)
ax.plot(relative_wheel_degrees, absolute_screen_deg_form_right_stim[::-1], "g.--")
ax.axhline()
ax.axhline(-35)
ax.axhline(35)
ax.axhline(70, c="gray")
ax.axhline(-70, c="gray")
ax.set_xlabel(f"Wheel degrees - Gain = {USER_DEFINED_GAIN}")
ax.set_ylabel(f"Screen degrees - Gain = {USER_DEFINED_GAIN}")
# ax.clear()
plt.show()
