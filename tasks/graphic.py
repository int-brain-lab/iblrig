# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Sunday, February 3rd 2019, 11:59:56 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 3-02-2019 11:59:58.5858
import tkinter as tk
from tkinter import simpledialog

from ibllib.misc.login import login


def numinput(title, prompt, default=None, minval=None, maxval=None,
             nullable=False, askint=False):
    root = tk.Tk()
    root.withdraw()
    ask = simpledialog.askinteger if askint else simpledialog.askfloat
    ans = ask(
        title, prompt, initialvalue=default, minvalue=minval, maxvalue=maxval)
    if ans == 0:
        return ans
    elif not ans and not nullable:
        return numinput(
            title, prompt, default=default, minval=minval, maxval=maxval,
            nullable=nullable, askint=askint)
    return ans


def strinput(title, prompt, default='COM', nullable=False):
        """
        Example:
        >>> strinput("RIG CONFIG", "Insert RE com port:", default="COM")
        """
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        ans = simpledialog.askstring(title, prompt, initialvalue=default)
        if (ans is None or ans == '' or ans == default) and not nullable:
            return strinput(title, prompt, default=default, nullable=nullable)
        else:
            return ans
