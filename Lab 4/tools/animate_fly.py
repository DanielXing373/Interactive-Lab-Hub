"""Create a clearly labeled simulated-fly version; preserve original video/audio.
Run with a Python environment containing Pillow and imageio-ffmpeg.
"""
from pathlib import Path
import math
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/prototype_2.mp4'
OUTPUT = ROOT / 'assets/prototype_2_animated.mp4'
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 720, 1280, 30
font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 25)

def position(t):
    # Hover near the snack, then leave when the recorded OLED changes to SHOO.
    for start, trigger, x, y in [(0, 4.2, 175, 790), (11.6, 13.65, 220, 820)]:
        if start <= t < trigger:
            elapsed = t-start
            hx = x + 17*math.sin(elapsed*5)
            hy = y + 11*math.sin(elapsed*7)
            if start > 0 and elapsed < .6:
                u=elapsed/.6
                hx=(-65)*(1-u)+hx*u
                hy=650*(1-u)+hy*u
            return hx, hy, -15 + 12*math.sin(t*4)
        if trigger <= t < trigger+.8:
            u=(t-trigger)/.8
            hx=x+17*math.sin((trigger-start)*5)
            hy=y+11*math.sin((trigger-start)*7)
            return hx+(W+140-hx)*u, hy-550*u-80*math.sin(math.pi*u), -55
    return None

def fly(t, angle):
    # Draw a stylized animation, deliberately distinguishable from real footage.
    im=Image.new('RGBA',(120,120))
    d=ImageDraw.Draw(im)
    for side in (-1,1):
        for offset in (-12,0,12):
            d.line([(60+side*7,62+offset),(60+side*23,69+offset),(60+side*29,65+offset)],fill=(20,22,26,255),width=3)
    flap=8+int(9*(1+math.sin(t*2*math.pi*12))/2)
    d.ellipse((24,34-flap,59,64),fill=(211,237,247,215),outline=(55,67,75,255),width=2)
    d.ellipse((61,34-flap,96,64),fill=(211,237,247,215),outline=(55,67,75,255),width=2)
    d.ellipse((49,52,71,84),fill=(34,37,44,255),outline=(240,240,240,230),width=1)
    d.ellipse((48,38,72,60),fill=(26,28,33,255))
    d.ellipse((47,38,57,49),fill=(171,62,45,255))
    d.ellipse((63,38,73,49),fill=(171,62,45,255))
    d.line((55,38,50,30),fill=(25,25,25,255),width=2)
    d.line((65,38,70,30),fill=(25,25,25,255),width=2)
    return im.rotate(angle,resample=Image.Resampling.BICUBIC)

reader=subprocess.Popen([FFMPEG,'-v','error','-i',str(SOURCE),'-vf',f'fps={FPS}', '-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
writer=subprocess.Popen([FFMPEG,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-', '-i',str(SOURCE),'-map','0:v:0','-map','1:a:0?', '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','copy','-shortest','-movflags','+faststart',str(OUTPUT)],stdin=subprocess.PIPE)
n=0
try:
    while True:
        raw=reader.stdout.read(W*H*3)
        if not raw: break
        if len(raw)!=W*H*3: raise RuntimeError('Incomplete decoded frame')
        frame=Image.frombytes('RGB',(W,H),raw).convert('RGBA')
        t=n/FPS
        p=position(t)
        if p:
            x,y,angle=p
            frame.alpha_composite(fly(t,angle),(round(x-60),round(y-60)))
        label=Image.new('RGBA',(W,H))
        d=ImageDraw.Draw(label)
        d.rounded_rectangle((20,22,391,68),radius=10,fill=(12,18,25,220))
        d.text((34,31),'SIMULATED FLY OVERLAY',font=font,fill='white')
        frame=Image.alpha_composite(frame,label).convert('RGB')
        writer.stdin.write(frame.tobytes())
        if n in (60,126,138,390,420): frame.save(f'/tmp/fly-preview-{n}.jpg')
        n+=1
finally:
    reader.stdout.close()
    writer.stdin.close()
assert reader.wait()==0, 'Video decode failed'
assert writer.wait()==0, 'Video encode failed'
print(f'Created {OUTPUT}: {n} frames at {FPS} fps')
