import speech_recognition as sr 
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_nonsilent
import subprocess
import os
import sys
import tempfile
import multiprocessing as mp
import wave
import math
import audioop
from progressbar import ProgressBar, Percentage, Bar, ETA

import pysrt
import six

DEFAULT_CURRENCY = 10

class SpeechRecognizer(object): # pylint: disable=too-few-public-methods
    """
    Class for performing speech-to-text for an input FLAC file.
    """
    def __init__(self):
        # Initialize recognizer
        self.r = sr.Recognizer()

    def __call__(self, data):
        with sr.AudioFile(data) as source:
            audio = self.r.record(source)

            # generate translation
            try:
                text = self.r.recognize_google(audio)
                return text   

            except sr.RequestError as e: 
                pass                
            except sr.UnknownValueError: 
                pass

        return None
    
class FLACConverter(object): # pylint: disable=too-few-public-methods
    """
    Class for converting a region of an input audio or video file into a FLAC audio file
    """
    def __init__(self, source_path, include_before=0.25, include_after=0.25):
        self.source_path = source_path
        self.include_before = include_before
        self.include_after = include_after

    def __call__(self, region):
        try:
            start, end = region
            start = max(0, start - self.include_before)
            end += self.include_after
            temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            command = ["ffmpeg", "-ss", str(start), "-t", str(end - start),
                       "-y", "-i", self.source_path,
                       "-vn", temp.name]
            use_shell = True if os.name == "nt" else False
            subprocess.check_output(command, stdin=open(os.devnull), shell=use_shell)
            return temp.name

        except KeyboardInterrupt:
            return None

def percentile(arr, percent):
    """
    Calculate the given percentile of arr.
    """
    arr = sorted(arr)
    index = (len(arr) - 1) * percent
    floor = math.floor(index)
    ceil = math.ceil(index)
    if floor == ceil:
        return arr[int(index)]
    low_value = arr[int(floor)] * (ceil - index)
    high_value = arr[int(ceil)] * (index - floor)
    return low_value + high_value

def extractRegions(filename, frame_width=4096, min_region_size=0.5, max_region_size=10):
    """
    Perform voice activity detection on a given audio file.
    """
    reader = wave.open(filename)
    sample_width = reader.getsampwidth()
    rate = reader.getframerate()
    n_channels = reader.getnchannels()
    chunk_duration = float(frame_width) / rate

    n_chunks = int(math.ceil(reader.getnframes()*1.0 / frame_width))
    energies = []

    for _ in range(n_chunks):
        chunk = reader.readframes(frame_width)
        energies.append(audioop.rms(chunk, sample_width * n_channels))


    threshold = percentile(energies, 0.25)

    elapsed_time = 0

    regions = []
    region_start = None

    max_silence_time = 0.5 # [s] Minimun silence time to divide a region
    silence_time = 0

    for energy in energies:

        is_silence = (energy <= threshold)
        if is_silence and region_start:
            silence_time += chunk_duration
            if ((silence_time >= max_silence_time) or (region_start - elapsed_time >= max_region_size)) and ((elapsed_time - region_start) >= min_region_size):
                regions.append((region_start, elapsed_time))
                region_start = None
                silence_time = 0
        elif (not region_start):
            region_start = elapsed_time
        elif (not is_silence):
            silence_time = 0
        elapsed_time += chunk_duration
    return regions

    # audio = AudioSegment.from_wav(filename)

    # chunks = split_on_silence(audio, min_silence_len = 500, silence_thresh = -16)
    # chunk_silence = AudioSegment.silent(duration = 250)

    # filenames = []

    # for chunk in chunks:
    #     audio_chunk = chunk_silence + chunk + chunk_silence

    #     temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)

    #     audio_chunk.export(temp.name, bitrate ='192k', format ="wav")

    #     filenames.append(temp.name)

    # return filenames



    # return detect_nonsilent(audio, min_silence_len = 500, silence_thresh = -10)


def genSubtitles(filename):

    audio_filename = extractAudio(filename)
    
    pool = mp.Pool(DEFAULT_CURRENCY)
    audio_regions = extractRegions(audio_filename)
    converter = FLACConverter(audio_filename)
    recognizer = SpeechRecognizer()

    transcripts = []
    # print(audio_regions)
    if audio_regions:
        try:
            widgets = ["Converting speech regions to FLAC files: ", Percentage(), ' ', Bar(), ' ',
                       ETA()]
            pbar = ProgressBar(widgets=widgets, maxval=len(audio_regions)).start()
            extracted_regions = []
            for i, extracted_region in enumerate(pool.imap(converter, audio_regions)):
                extracted_regions.append(extracted_region)
                pbar.update(i)
            pbar.finish()

            # extracted_regions = extractRegions(audio_filename)

            widgets = ["Performing speech recognition: ", Percentage(), ' ', Bar(), ' ', ETA()]
            pbar = ProgressBar(widgets=widgets, maxval=len(audio_regions)).start()

            for i, transcript in enumerate(pool.imap(recognizer, extracted_regions)):
                transcripts.append(transcript)
                pbar.update(i)
            pbar.finish()

            for file in extracted_regions:
                os.remove(file)
        
            # print("Translation")
            # for i in transcripts:
            #     print(i)

        except KeyboardInterrupt:
            pbar.finish()
            pool.terminate()
            pool.join()
            print("Cancelling transcription")
            raise

    timed_subtitles = [(r, t) for r, t in zip(audio_regions, transcripts) if t]
    formatted_subtitles = srtFormatter(timed_subtitles)

    base = os.path.splitext(filename)[0]
    dest = "{base}.srt".format(base=base)

    with open(dest, 'wb') as output_file:
        output_file.write(formatted_subtitles.encode("utf-8"))

    os.remove(audio_filename)

def extractAudio(filename, channels = 2, rate = 44100):

    temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    command = [ffmpeg_check(), "-y", "-i", filename,
               "-ac", str(channels), "-ar", str(rate),
               "-vn", temp.name]

    subprocess.check_output(command, shell=True)
    
    temp.close()
    return temp.name

def srtFormatter(subtitles, padding_before=0, padding_after=0):
    """
    Serialize a list of subtitles according to the SRT format, with optional time padding.
    """
    sub_rip_file = pysrt.SubRipFile()
    for i, ((start, end), text) in enumerate(subtitles, start=1):
        item = pysrt.SubRipItem()
        item.index = i
        item.text = six.text_type(text)
        item.start.seconds = max(0, start - padding_before)
        item.end.seconds = end + padding_after
        sub_rip_file.append(item)
    return '\n'.join(six.text_type(item) for item in sub_rip_file)

def ffmpeg_check():
    """
    Return the ffmpeg executable name. "null" returned when no executable exsits.
    """
    if which("ffmpeg"):
        return "ffmpeg"
    elif which("ffmpeg.exe"):
        return "ffmpeg.exe"
    else:
        return None

def which(program):
    """
    Return the path for a given executable.
    """
    def is_exe(file_path):
        """
        Checks whether a file is executable.
        """
        return os.path.isfile(file_path) and os.access(file_path, os.X_OK)

    fpath, _ = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None