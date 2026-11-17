"""
gen_gfx.py - Genera ../LaRecolectora/Gfx.jack: los sprites y las tablas de la pelota.

Los dibujos se definen aqui como texto ('#' = pixel negro) y se convierten
en palabras de 16 bits tal como las espera la memoria de video de Hack:
el bit 0 de cada palabra es el pixel de la IZQUIERDA.
"""
import os

def rows(art):
    a = [r.strip() for r in art.strip().splitlines()]
    assert len(a) == 16 and all(len(r) == 16 for r in a), art
    return a

def fill(f):
    return [''.join('#' if f(x, y) else '.' for x in range(16)) for y in range(16)]

EMPTY = fill(lambda x, y: False)
SOLID = fill(lambda x, y: True)
SOLID_LIT = fill(lambda x, y: ((x // 2) + (y // 2)) % 2 == 0)          # tablero de ajedrez
BOUNCE = fill(lambda x, y: not (4 <= x <= 11 and 4 <= y <= 11))
BOUNCE_LIT = fill(lambda x, y: 4 <= x <= 11 and 4 <= y <= 11)               # BOUNCE invertido
GARBAGE = fill(lambda x, y: (2 <= x <= 13 and 2 <= y <= 13) and not ((4 <= x <= 11 and 4 <= y <= 11) and not (6 <= x <= 9 and 6 <= y <= 9)))
BODY = fill(lambda x, y: 1 <= x <= 14 and 1 <= y <= 14)
DATA = fill(lambda x, y: abs(x - 7.5) + abs(y - 7.5) <= 6.5)               # rombo
EYES = lambda x, y: (3 <= y <= 5) and (3 <= x <= 5 or 10 <= x <= 12)
HEAD = fill(lambda x, y: 1 <= x <= 14 and 1 <= y <= 14 and not EYES(x, y))
HEAD_CHARGED = fill(lambda x, y: 1 <= x <= 14 and 1 <= y <= 14 and not EYES(x, y) and not (4 <= x <= 11 and 9 <= y <= 12))

SPRITES = [  # el indice es el numero de sprite
    ('EMPTY', 'celda libre', EMPTY),
    ('SOLID', 'pared solida (letal)', SOLID),
    ('BOUNCE', 'pared de rebote', BOUNCE),
    ('GARBAGE', 'basura: nodo sin liberar', GARBAGE),
    ('BODY', 'cuerpo de la serpiente', BODY),
    ('DATA', 'dato (rombo)', DATA),
    ('HEAD', 'cabeza', HEAD),
    ('HEAD_CHARGED', 'cabeza cargada (boca abierta)', HEAD_CHARGED),
    ('SOLID_LIT', 'pared solida con pulso del bus', SOLID_LIT),
    ('BOUNCE_LIT', 'pared de rebote con pulso del bus', BOUNCE_LIT),
]

BALL = ['.####.', '######', '######', '######', '######', '.####.']   # 6x6, esquina sup-izq = (x-3, y-3)

def word(r):
    return sum(1 << i for i, ch in enumerate(r) if ch == '#')

def jk(v):
    """Constante de 16 bits como expresion Jack (Jack solo acepta 0..32767)."""
    v &= 0xFFFF
    if v <= 32767: return str(v)
    if v == 0x8000: return '-32767 - 1'
    return '-' + str(65536 - v)

def ball_tables():
    L, R = [], []
    for s in range(16):
        for r in BALL:
            m = word(r) << s
            L.append(m & 0xFFFF); R.append(m >> 16)
    return L, R

def build():
    L, R = ball_tables()
    o = []
    w = o.append
    w('/**')
    w(' * Gfx - dibujo ESCRIBIENDO DIRECTAMENTE en la memoria de video de Hack.')
    w(' *')
    w(' * La pantalla es la RAM 16384..24575: 256 filas x 32 palabras de 16 bits.')
    w(' * El bit 0 de cada palabra es el pixel de la izquierda.')
    w(' *')
    w(' * El campo usa celdas de 16x16 alineadas a palabras, asi que CADA FILA DE UNA')
    w(' * CELDA ES EXACTAMENTE UNA PALABRA de memoria: dibujar una celda = 16 escrituras.')
    w(' *   palabra de la celda (x, y), fila r = 512 + y*512 + r*32 + x')
    w(' *   (512 = las 16 filas de pixeles del marcador; 32 palabras por fila)')
    w(' *')
    w(' * Archivo GENERADO por tools/gen_gfx.py (los dibujos estan alli como texto).')
    w(' */')
    w('class Gfx {')
    w('    static Array screen;     // apunta a la RAM 16384: screen[i] = palabra i de la pantalla')
    w('    static Array sprites;    // %d sprites x 16 palabras' % len(SPRITES))
    w('    static Array ballL;      // pelota desplazada s bits: palabra izquierda  (16 x 6)')
    w('    static Array ballR;      // pelota desplazada s bits: palabra derecha    (16 x 6)')
    w('')
    w('    /** Reserva las tablas y las llena. Se llama una sola vez al iniciar. */')
    w('    function void init() {')
    w('        let screen = 16384;')
    w('        let sprites = Array.new(%d);' % (16 * len(SPRITES)))
    w('        let ballL = Array.new(96);')
    w('        let ballR = Array.new(96);')
    for i, (name, desc, art) in enumerate(SPRITES):
        w('')
        w('        // Sprite %d = %s: %s' % (i, name, desc))
        for r, row in enumerate(art):
            v = word(row)
            if v or name == 'EMPTY':
                w('        let sprites[%d] = %s;%s// %s' % (i * 16 + r, jk(v), ' ' * max(1, 12 - len(jk(v)) - len(str(i * 16 + r))), row))
            else:
                w('        let sprites[%d] = 0;%s// %s' % (i * 16 + r, ' ' * max(1, 11 - len(str(i * 16 + r))), row))
    w('')
    w('        // Pelota de 6x6 pixeles:')
    for r in BALL: w('        //   %s' % r)
    w('        // Hack no tiene instruccion de desplazamiento de bits, asi que la pelota se')
    w('        // guarda ya desplazada para cada una de las 16 posiciones dentro de una palabra.')
    w('        // ballL[s*6 + fila] = parte que cae en la palabra de la izquierda')
    w('        // ballR[s*6 + fila] = parte que se pasa a la palabra de la derecha (solo si s > 10)')
    for i in range(96):
        w('        let ballL[%d] = %s;' % (i, jk(L[i])))
    for i in range(96):
        if R[i]: w('        let ballR[%d] = %s;' % (i, jk(R[i])))
        else: w('        let ballR[%d] = 0;' % i)
    w('        return;')
    w('    }')
    w('''
    /**
     * Dibuja el sprite id en la celda (x, y) del campo.
     * Desenrollado a mano: 16 escrituras seguidas sin bucle, porque un bucle
     * gasta casi el doble de instrucciones VM en el contador y la comparacion.
     */
    function void cell(int x, int y, int id) {
        var int a, b;
        let a = 512 + (y * 512) + x;
        let b = id * 16;''')
    for r in range(16):
        w('        let screen[a + %d] = sprites[b + %d];' % (r * 32, r))
    w('''        return;
    }

    /**
     * Dibuja (on = true) o borra (on = false) la pelota con centro (bx, by) en pixeles.
     * Esquina superior izquierda: (bx - 3, by - 3). Ocupa 6 filas.
     * Solo toca palabras de celdas LIBRES (la fisica de Ball lo garantiza),
     * por eso puede escribir palabras completas sin danar nada.
     */
    function void ball(int bx, int by, boolean on) {
        var int x0, s, a, t, r;
        let x0 = bx - 3;
        let s = x0 & 15;                         // posicion del primer pixel dentro de su palabra
        let a = ((by - 3) * 32) + (x0 / 16);     // palabra de la primera fila
        let t = s * 6;
        let r = 0;
        while (r < 6) {
            if (on) {
                let screen[a] = ballL[t];
                if (s > 10) { let screen[a + 1] = ballR[t]; }
            } else {
                let screen[a] = 0;
                if (s > 10) { let screen[a + 1] = 0; }
            }
            let a = a + 32;
            let t = t + 1;
            let r = r + 1;
        }
        return;
    }

    /** LIMPIEZA DE MEMORIA: libera las tres tablas. */
    function void dispose() {
        do sprites.dispose();
        do ballL.dispose();
        do ballR.dispose();
        return;
    }
}''')
    return '\n'.join(o) + '\n'

if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'LaRecolectora', 'Gfx.jack')
    open(out, 'w').write(build())
    print('Gfx.jack generado')
