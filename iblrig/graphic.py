#!/usr/bin/env python
# @Author: Niccolò Bonacchi
# @Creation_Date: 2022-01-24
# @Editor: Michele Fabbri
# @Edit_Date: 2022-02-01
"""
Popup and string input prompts
"""
import tkinter as tk
from tkinter import simpledialog


def numinput(title, prompt, default=None, minval=None, maxval=None, nullable=False, askint=False):
    root = tk.Tk()
    root.withdraw()
    ask = simpledialog.askinteger if askint else simpledialog.askfloat
    ans = ask(title, prompt, initialvalue=default, minvalue=minval, maxvalue=maxval)
    if ans == 0:
        return ans
    elif not ans and not nullable:
        return numinput(
            title,
            prompt,
            default=default,
            minval=minval,
            maxval=maxval,
            nullable=nullable,
            askint=askint,
        )
    return ans
