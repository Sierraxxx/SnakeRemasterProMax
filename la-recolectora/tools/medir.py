"""
medir.py - Mide instrucciones de la maquina virtual (VM) en los .vm compilados.
  - instrucciones por turno de juego (sin contar el tiempo de espera)
  - instrucciones para dibujar una celda: desenrollado vs. con bucle
"""
import sys, os, shutil, tempfile, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv.append('--vm')
import probar
from vm import VMachine
import compilar

# 1) por turno
bot = probar.Bot(7, 'listo', 3)
deltas = []; last = [None, None]
orig = bot.check
def chk(m, s):
    if last[0] is not None and s['phase'] == (last[1] + 1) % 90:
        deltas.append(m.ops - last[0])
    last[0], last[1] = m.ops, s['phase']
    orig(m, s)
bot.check = chk
m = VMachine(probar.FOLDER, bot); m.run()
deltas.sort()
print('turnos medidos: %d' % len(deltas))
print('instrucciones VM por turno: mediana %d, promedio %d, p95 %d, max %d'
      % (statistics.median(deltas), statistics.mean(deltas), deltas[int(len(deltas) * .95)], deltas[-1]))

# 2) una celda: desenrollado vs bucle
tmp = tempfile.mkdtemp()
for f in os.listdir(probar.FOLDER):
    if f.endswith('.jack'): shutil.copy(os.path.join(probar.FOLDER, f), tmp)
open(os.path.join(tmp, 'Main.jack'), 'w').write('''class Main {
    function void main() { do Gfx.init(); do Main.loop(5, 5, 4); do Gfx.cell(5, 5, 4); return; }
    function void loop(int x, int y, int id) {
        var int a, b, r; var Array screen, sprites;
        let screen = 16384; let sprites = Gfx.table();
        let a = 512 + (y * 512) + x; let b = id * 16; let r = 0;
        while (r < 16) { let screen[a] = sprites[b]; let a = a + 32; let b = b + 1; let r = r + 1; }
        return;
    }
}''')
g = open(os.path.join(tmp, 'Gfx.jack')).read().replace('    function void init() {', '    function Array table() { return sprites; }\n\n    function void init() {', 1)
open(os.path.join(tmp, 'Gfx.jack'), 'w').write(g)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()): compilar.compilar(tmp)
v = VMachine(tmp); v.vcall('Gfx.init', [])
o = v.ops; v.vcall('Main.loop', [5, 5, 4]); lp = v.ops - o
o = v.ops; v.vcall('Gfx.cell', [5, 5, 4]); un = v.ops - o
o = v.ops; v.vcall('Gfx.ball', [100, 100, -1]); bl = v.ops - o
print('una celda (16 palabras): con bucle %d instrucciones, desenrollada %d (%d%% menos)' % (lp, un, round(100 * (lp - un) / lp)))
print('pelota (6 filas): %d instrucciones' % bl)
