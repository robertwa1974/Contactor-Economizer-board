"""Render econ.kicad_pcb to a PNG via kicad-cli SVG + headless Edge (review aid).

usage: python render.py out.png [layers] [--back]
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

out = os.path.abspath(sys.argv[1])
layers = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "F.Cu,B.Cu,F.SilkS,Edge.Cuts"
svg = out + ".svg"
cmd = [KICAD_CLI, "pcb", "export", "svg", "--mode-single", "-l", layers, "--page-size-mode", "2",
       "--exclude-drawing-sheet", "-o", svg, os.path.join(HERE, "econ.kicad_pcb")]
if "--back" in sys.argv:
    cmd.insert(4, "--mirror")
subprocess.run(cmd, check=True, capture_output=True)
html = out + ".html"
with open(html, "w") as f:
    f.write(f'<html><body style="margin:0;background:#fff"><img src="{os.path.basename(svg)}" style="width:1500px"></body></html>')
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                "--window-size=1500,1310", f"--screenshot={out}", "file:///" + html.replace("\\", "/")],
               check=True, capture_output=True)
print(out)
