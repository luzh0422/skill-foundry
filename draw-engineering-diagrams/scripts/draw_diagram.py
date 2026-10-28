#!/usr/bin/env python3
"""Render the skill's bounded lanes/state/timeline layouts from JSON to SVG."""
import argparse
from html import escape
import json
import re
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STYLE = json.loads((ROOT / 'assets/style.json').read_text())


def length(text, size):
    """Conservative CJK/Latin width estimate; final PNG inspection is mandatory."""
    return sum(size * (1 if ord(c) > 255 else 0.64) for c in text)


def wrap(text, size, width):
    lines = []
    for paragraph in str(text).split('\n'):
        current = ''
        for token in re.findall(r'[A-Za-z0-9_./:<>-]+|[^\n]', paragraph):
            if length(token, size) > width:
                raise ValueError(f'Unbroken identifier exceeds text width: {token}; widen the card or use a shorter display label')
            if current and length(current + token, size) > width:
                lines.append(current.rstrip())
                current = ''
            current += token
        lines.append(current.rstrip())
    return lines


class Canvas:
    def __init__(self, width, height, title, subtitle=''):
        self.width, self.height = width, height
        self.title = title
        self.parts = []
        self.bounds = []
        self.panel(0, 0, width, height, STYLE['background'], 'none', 0)
        self.text(title, 48, 44, width-96, 38, STYLE['text'], True)
        if subtitle:
            self.text(subtitle, 48, 96, width-96, 21, STYLE['secondary'])

    def add(self, xml, bounds=None):
        self.parts.append(xml)
        if bounds:
            self.bounds.append(bounds)

    def panel(self, x, y, w, h, fill, stroke, radius=14, dashed=False):
        dash = ' stroke-dasharray="7 5"' if dashed else ''
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>', (x,y,x+w,y+h))

    def text(self, value, x, y, width, size=20, color=None, bold=False, align='left'):
        lines = wrap(value, size, width)
        line_height = size*1.45
        anchor = 'middle' if align == 'center' else 'start'
        at_x = x+width/2 if align == 'center' else x
        spans = ''.join(f'<tspan x="{at_x}" y="{y+size+i*line_height}">{escape(line)}</tspan>' for i,line in enumerate(lines))
        self.add(f'<text font-family="{STYLE["font_family"]}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color or STYLE["text"]}" text-anchor="{anchor}">{spans}</text>', (x,y,x+width,y+len(lines)*line_height))
        return len(lines)*line_height

    def circle(self,x,y,r,fill,stroke='none'):
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',(x-r,y-r,x+r,y+r))

    def edge(self, points, role='neutral', arrow=True, dashed=False):
        assert all(a[0]==b[0] or a[1]==b[1] for a,b in zip(points,points[1:])), 'Use orthogonal connector segments'
        color=STYLE['roles'][role]['stroke']
        path=' '.join(f'{x},{y}' for x,y in points)
        end=f' marker-end="url(#arrow-{role})"' if arrow else ''
        dash=' stroke-dasharray="7 5"' if dashed else ''
        self.add(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"{end}{dash}/>')

    def card(self,x,y,w,h,node):
        role=STYLE['roles'][node.get('role','structure')]
        self.panel(x,y,w,h,role['fill'],role['stroke'])
        consumed=self.text(node['title'],x+20,y+18,w-40,node.get('title_size',23),role['text'],True,'center')
        body=node.get('body','')
        if body:
            consumed += 14 + self.text(body,x+20,y+18+consumed+14,w-40,20,STYLE['secondary'],False,'center')
        if consumed>h-32:
            raise ValueError(f'Card overflow: {node["title"]}; shorten text, split the diagram, or increase card height')

    def legend(self, y, roles):
        self.edge([(48,y-12),(self.width-48,y-12)],arrow=False)
        for i,(role,label) in enumerate(roles):
            x=48+i*220
            self.edge([(x,y+14),(x+34,y+14)],role,False)
            self.text(label,x+46,y,160,18,STYLE['roles'][role]['text'])

    def save(self,path):
        for x1,y1,x2,y2 in self.bounds:
            if min(x1,y1)<0 or x2>self.width or y2>self.height:
                raise ValueError(f'Content out of canvas: {(x1,y1,x2,y2)}')
        defs=''.join(f'<marker id="arrow-{role}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9" fill="none" stroke="{v["stroke"]}" stroke-width="1.8"/></marker>' for role,v in STYLE['roles'].items())
        xml=f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" role="img"><title>{escape(self.title)}</title><defs>{defs}</defs>'+''.join(self.parts)+'</svg>'
        ET.fromstring(xml)
        Path(path).write_text(xml)


def lanes(spec):
    rows=spec['lanes']
    if not 1<=len(rows)<=5:
        raise ValueError('Use 1–5 lanes; split larger diagrams')
    width=1600; height=180+len(rows)*244+90
    c=Canvas(width,height,spec['title'],spec.get('subtitle',''))
    c.title=spec['title']
    for i,row in enumerate(rows):
        y=154+i*244; role=row.get('role','structure'); palette=STYLE['roles'][role]
        c.panel(48,y,1504,220,STYLE['panel'],STYLE['border'])
        c.panel(48,y,6,220,palette['stroke'],'none',3)
        c.circle(84,y+28,16,palette['stroke'])
        c.text(str(i+1),68,y+12,32,19,'#ffffff',True,'center')
        c.text(row['title'],112,y+9,1390,25,STYLE['text'],True)
        nodes=row['nodes']
        if not 1<=len(nodes)<=4:
            raise ValueError('Use 1–4 cards per lane')
        gap=68; x=80; available=1440; card_width=(available-gap*(len(nodes)-1))/len(nodes)
        node_y=y+64; card_height=132
        for j,node in enumerate(nodes):
            node=dict(node);node.setdefault('role',role)
            nx=x+j*(card_width+gap)
            c.card(nx,node_y,card_width,card_height,node)
            if j<len(nodes)-1:
                c.edge([(nx+card_width+10,node_y+66),(nx+card_width+gap-12,node_y+66)],role)
        if row.get('note'):
            raise ValueError('Put long lane notes in subtitle/body, or use a custom SVG layout')
    c.legend(height-42,[('structure','结构 / 主路径'),('layer','独立分支'),('resource','内存 / 资源'),('command','命令 / 提交')])
    return c


def state(spec):
    nodes=spec['states']
    if len(nodes)!=3:
        raise ValueError('State template supports 3 states; customize SVG for other graphs')
    c=Canvas(1600,850,spec['title'],spec.get('subtitle',''));c.title=spec['title']
    c.panel(48,152,1504,610,STYLE['panel'],STYLE['border'])
    c.panel(48,152,6,610,STYLE['roles']['structure']['stroke'],'none',3)
    xs=[100,620,1140];y=310;w=360;h=240
    for x,node in zip(xs,nodes):c.card(x,y,w,h,{**node,'title_size':40})
    positions={node['id']:x for node,x in zip(nodes,xs)}
    counters={'upper':0,'lower':0}
    for edge in spec['transitions']:
        src=positions[edge['from']];dst=positions[edge['to']];route=edge.get('route','direct');role=edge.get('role','structure')
        if route=='direct':
            if dst<=src or dst-src>520:raise ValueError('Direct transitions must go to next state on the right')
            c.edge([(src+w+12,y+120),(dst-14,y+120)],role)
            c.text(edge['label'],src+w+8,y+65,dst-src-w-16,18,STYLE['roles'][role]['text'],False,'center')
        elif route in counters:
            k=counters[route];counters[route]+=1
            if k>=2:raise ValueError('Use at most two connectors per outer band')
            band=228-k*60 if route=='upper' else 625+k*65
            attach=y-8 if route=='upper' else y+h+8
            # Separate ports for return/upgrade paths so their vertical segments stay distinct.
            port_shift = 40 if k == 0 else -40
            sx=src+w/2+port_shift;dx=dst+w/2+port_shift
            c.edge([(sx,attach),(sx,band),(dx,band),(dx,attach)],role)
            left=min(sx,dx);right=max(sx,dx)
            if left==right:
                raise ValueError('Draw self-loops manually with Canvas.edge()')
            c.text(edge['label'],left,band-35,right-left,18,STYLE['roles'][role]['text'],True,'center')
        else:raise ValueError('route must be direct, upper or lower')
    c.text(spec.get('note',''),64,784,1472,18,STYLE['secondary'])
    return c


def timeline(spec):
    nodes=spec['milestones'];n=len(nodes)
    if not 2<=n<=5:raise ValueError('Use 2–5 milestones; split larger timelines')
    c=Canvas(1600,410,spec['title'],spec.get('subtitle',''));c.title=spec['title']
    c.edge([(80,208),(1520,208)],arrow=True)
    for i,node in enumerate(nodes):
        x=180+i*1240/(n-1);role=STYLE['roles'][node.get('role','structure')]
        c.text(node['date'],x-130,147,260,26,STYLE['text'],True,'center')
        c.circle(x,208,12,role['fill'],role['stroke'])
        c.edge([(x,224),(x,248)],node.get('role','structure'),False)
        c.card(x-132,252,264,100,{'title':node['title'],'role':node.get('role','structure')})
    return c


def preview(svg, png, chrome):
    import shutil
    chrome=chrome or shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:raise RuntimeError('Chrome/Chromium required for PNG; SVG has been saved')
    root=ET.parse(svg).getroot();w=int(root.get('width'));h=int(root.get('height'))
    with tempfile.TemporaryDirectory(prefix='engineering-diagram-') as tmp:
        html=Path(tmp)/'preview.html'
        html.write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;padding:0;overflow:hidden;background:white}svg{display:block}</style>'+Path(svg).read_text())
        cmd=[chrome,'--headless','--disable-gpu','--no-sandbox','--hide-scrollbars','--no-first-run',
             '--no-default-browser-check','--force-device-scale-factor=1','--run-all-compositor-stages-before-draw',
             '--user-data-dir='+str(Path(tmp)/'profile'),'--window-size='+f'{w},{h+140}',
             '--screenshot='+str(Path(png).resolve()),html.as_uri()]
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError('Pillow required to crop PNG to exact SVG dimensions')
        im=Image.open(png);im.crop((0,0,w,h)).save(png)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--svg',type=Path,required=True)
    parser.add_argument('--png',type=Path)
    parser.add_argument('--chrome')
    args=parser.parse_args()
    spec=json.loads(args.spec.read_text())
    builders={'lanes':lanes,'state':state,'timeline':timeline}
    if spec.get('kind') not in builders:raise ValueError('kind must be lanes, state, timeline')
    canvas=builders[spec['kind']](spec);canvas.save(args.svg)
    if args.png:preview(args.svg,args.png,args.chrome)
    print(json.dumps({'svg':str(args.svg),'png':str(args.png) if args.png else None,'width':canvas.width,'height':canvas.height},ensure_ascii=False))


if __name__=='__main__':main()
