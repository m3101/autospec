""" Automatic speaker frequency response calibration tool
    Copyright (c) 2020 - Amélia O. F. da S.
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>."""
import sys
import sounddevice as sd
import wave
import numpy as np
import time
import matplotlib.pyplot as plt
import math

#Sampling rate
sr = 44100

print("Autospec")
print("Copyright (c) 2020 Amélia O. F. da S.")
print("")

def smoothC(curve,ww):
    cumsum_vec = np.cumsum(np.insert(curve, 0, 0))
    return (cumsum_vec[ww:] - cumsum_vec[:-ww]) / ww

#We're reading and filtering a file
if len(sys.argv)>1:
    if len(sys.argv)<3:
        print("Usage: python autospec.py <.wav file> <.filter file>")
        print("       or python autospec.py")
    else:
        with open(sys.argv[2],'rb') as f:
            fcurve = np.load(f)
        precord = False
        fname = sys.argv[1]
        if fname[-1]=="X":
            precord=True
            fname=fname[:-1]
        f = wave.open(fname)
        audio = np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/2**15
        audio = audio[np.arange(len(audio))%2==0]
        audio = audio/audio.max()
        plt.plot(np.fft.rfftfreq(fcurve.size*2,1/sr)[:-1],fcurve)
        plt.title("Compensation curve")
        plt.xlabel("Frequency (hz)")
        plt.show()
        bsize=fcurve.size*2
        l=math.floor(audio.size/bsize)
        filtered = np.zeros(((l+1)*bsize))
        extra = audio.size-l*bsize
        for i in range(l):
            filtered[bsize*i:bsize*(i+1)]=np.fft.irfft(
                                        np.fft.rfft(
                                            audio[bsize*i:bsize*(i+1)]
                                        )*np.insert(fcurve,-1,1)
                                        )
        filtered[bsize*l:bsize*l+extra]=audio[-extra:]
        filtered[bsize*l:]=np.fft.irfft(
                                      np.fft.rfft(
                                            filtered[bsize*l:]
                                        )*np.insert(fcurve,-1,1)
                                    )
        filtered=filtered/filtered.max()
        if not precord:
            sd.play(audio,sr,blocking=True)
            sd.play(filtered,sr,blocking=True)
        else:
            rawpure = sd.playrec(audio[:sr*3],sr,1,blocking=True)
            rawpure = rawpure/rawpure.max()
            rawfilt = sd.playrec(filtered[:sr*3],sr,1,blocking=True)
            rawfilt = rawfilt/rawfilt.max()
            input("Press enter to play the recorded results")
            sd.play(rawpure,sr,blocking=True)
            sd.play(rawfilt,sr,blocking=True)

#We're generating a new filter
else:
    print("Please position your speakers/audio output as near as possible to your microphone and raise your volume to a moderately high level.")
    print("(Warning: this step will play a loud white noise sound for a short time on your speakers)")
    a = input(" <press enter to calculate the calibration curve>\r")
    noise = np.random.rand(sr)
    if not a:
        raw = sd.playrec(noise,sr,1,blocking=True)
        raw = raw/raw.max()
        raw = raw[:,0]
        print("Recorded")
        with open("rec.npdump",'wb') as f:
            np.save(f,raw)
    else:
        with open("rec.npdump",'rb') as f:
            raw=np.load(f)
    fft = np.fft.rfft(raw*np.blackman(raw.shape[0]))
    windoww = 200
    smooth = smoothC(np.log(fft),windoww)
    plt.title("Log(fft(recording))")
    plt.xlabel("Frequency (hz)")
    plt.plot(np.fft.rfftfreq(raw.size,d=1/sr),np.log(fft))
    plt.plot(np.fft.rfftfreq(raw.size,d=1/sr)[:-(windoww-1)],smooth)
    plt.figure()
    smthfft = np.exp(smooth)
    fcurve = np.ones(fft.shape)
    fcurve[:smthfft.size][smthfft!=0] = smthfft.max()/smthfft
    w = 300
    fcurve[:-(w-1)] = smoothC(fcurve,w)
    fcurve=fcurve/fcurve.max()
    plt.title("Compensation curve")
    plt.xlabel("Frequency (hz)")
    plt.plot(np.fft.rfftfreq(raw.size,d=1/sr),fcurve)
    plt.figure()
    fcurve[0:10]=1
    filtered = np.fft.irfft(np.fft.rfft(raw)*fcurve)

    fft = np.fft.rfft(filtered*np.blackman(raw.shape[0]))
    smooth = smoothC(np.log(fft),windoww)
    plt.title("Log(fft(compensated recording))")
    plt.xlabel("Frequency (hz)")
    plt.plot(np.fft.rfftfreq(raw.size,d=1/sr),np.log(fft))
    plt.plot(np.fft.rfftfreq(raw.size,d=1/sr)[:-(windoww-1)],smooth)
    smthfft = np.insert(np.exp(smooth),-1,np.ones((windoww-1)))
    plt.show()

    sd.play(noise,sr,blocking=True)
    sd.play(raw,sr,blocking=True)
    sd.play(filtered/filtered.max(),sr,blocking=True)

    fn=input("Filter curve file name: ")
    with open(fn,'wb') as f:
        np.save(f,fcurve)