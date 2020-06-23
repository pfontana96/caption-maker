import sys
from tkinter import Tk
from view import Screen
import pkg_resources.py2_warn
import multiprocessing


class GUI():

    def __init__(self, parent):
        self.parent = parent
        self.view = Screen(parent)
        self.view.packing()

def main():
    root = Tk()
    root.title("Julius caption-maker")

    app = GUI(root)
    root.mainloop()

if __name__ == "__main__":
    # Pyinstaller fix
    multiprocessing.freeze_support()

    main()