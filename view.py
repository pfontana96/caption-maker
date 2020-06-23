from tkinter import filedialog, Frame, Button, Toplevel, Label
from subgen import genSubtitles
import speech_recognition as sr 
import subprocess
import os

class Screen(object):
    def __init__(self, parent, bg="white"):

        self.parent = parent

        # Frame 
        self.frame = Frame(parent, width=768, height=576, bg=bg)
        
        # Range widgets
        self.cap_gen_but = Button(self.frame, text="Generar Subtitulos", command=self.generate_captions)
       
        # Quit button
        self.quit_but = Button(self.frame, text="Salir", command=self.exit)


    def exit(self):
		
        self.tempWin = Toplevel(self.parent)
        self.tempWin.title("Atencion")
        text = Label(self.tempWin, text = "De verdad quiere salir?")
        button_yes = Button(self.tempWin, text = "Si", command = self.parent.destroy)
        button_no = Button(self.tempWin, text = "No", command = self.tempWin.destroy)
        text.pack()
        button_yes.pack(side = "bottom")
        button_no.pack(side = "bottom")

    def generate_captions(self):
        
        # Get filename
        video_filename = filedialog.askopenfilename(initialdir = "/",title = "Select file",filetypes = (("mpeg files","*.mp4"),("all files","*.*")))
        genSubtitles(video_filename)


    def packing(self):

        # Frame
        self.cap_gen_but.pack(fill="both", expand=1, side="left")
        self.quit_but.pack(fill="both", expand=1, side="left")

        #Tk window
        self.frame.pack(fill="both", expand=1)
