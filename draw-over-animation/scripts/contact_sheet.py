"""Make labeled contact sheets for rendered frame inspection; native crops remain necessary."""
import argparse, math
from pathlib import Path
from PIL import Image, ImageDraw

p=argparse.ArgumentParser()
p.add_argument('directory',type=Path)
p.add_argument('--prefix',default='sheet')
p.add_argument('--columns',type=int,default=3)
p.add_argument('--rows',type=int,default=4)
p.add_argument('--width',type=int,default=480)
a=p.parse_args()
def key(f):
    try:return float(f.stem.removeprefix('t').replace('_','.'))
    except ValueError:return float('inf')
files=sorted(a.directory.glob('t*.png'),key=key)
n=a.columns*a.rows;h=round(a.width*9/16)
for page in range(math.ceil(len(files)/n)):
    board=Image.new('RGB',(a.columns*a.width,a.rows*(h+24)),(18,20,26))
    draw=ImageDraw.Draw(board)
    for i,f in enumerate(files[page*n:(page+1)*n]):
        x=(i%a.columns)*a.width;y=(i//a.columns)*(h+24)
        im=Image.open(f).convert('RGB');im.thumbnail((a.width,h))
        board.paste(im,(x,y+24));draw.text((x+8,y+5),f.stem,fill='white')
    out=a.directory/f'{a.prefix}_{page:02}.jpg';board.save(out,quality=91);print(out)
