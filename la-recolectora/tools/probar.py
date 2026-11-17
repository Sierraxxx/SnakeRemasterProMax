"""
probar.py - Juega LA RECOLECTORA con jugadores automaticos y verifica todo.

  python3 probar.py            -> ejecuta el codigo Jack (interprete de Jack)
  python3 probar.py --vm       -> ejecuta los .vm compilados (interprete de VM)
  python3 probar.py --capturas -> ademas guarda imagenes en ../docs/capturas

En CADA turno se comprueba:
  - la lista enlazada de la serpiente, la cuadricula y el arreglo de basura
  - que el contador de nodos coincida con los objetos vivos reales
  - que no quede ningun String sin liberar
  - la pantalla del campo PALABRA POR PALABRA contra lo esperado
    (sprites, pulsos del bus y la pelota)
  - que la pelota solo este sobre celdas libres
Al salir: que no quede ningun bloque reservado en el heap.
"""
import sys, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jack import Machine, JackError
import gen_gfx

FOLDER = os.path.join(HERE, '..', 'LaRecolectora')
if '--vm' in sys.argv:
    from vm import VMachine as Machine

DXY = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
KEYOF = {1: 131, 2: 133, 3: 130, 4: 132}
OPP = {1: 2, 2: 1, 3: 4, 4: 3}
SPR = [[gen_gfx.word(r) for r in art] for _, _, art in gen_gfx.SPRITES]
BALL = [gen_gfx.word(r) for r in gen_gfx.BALL]


class Bot:
    def __init__(self, seed, estilo, partidas, salir='gameover', shots=None):
        self.r = random.Random(seed); self.estilo = estilo; self.partidas = partidas; self.salir = salir
        self.want = 4; self.deaths = 0; self.checks = 0; self.lastphase = None; self.prev = None
        self.stats = dict(turnos=0, limpiezas=0, combo_max=0, basura_max=0, mem_max=0, atrapadas=0,
                          rebotes_pelota=0, muertes={}, pausas=0)
        self.special = []; self.shots = shots or {}; self.lastcombo = 0; self.lastcharged = False; self.lastv = None

    # ---------------- lectura del estado interno ----------------
    def state(self, m):
        g = m.objects('Game')[0]
        F = lambda o, c, f: m.field(o, c, f)
        sn, w, b = F(g, 'Game', 'snake'), F(g, 'Game', 'world'), F(g, 'Game', 'ball')
        grid = F(w, 'World', 'grid'); ring = F(w, 'World', 'ring')
        head, tail = F(sn, 'Snake', 'head'), F(sn, 'Snake', 'tail')
        return dict(m=m, g=g, G=[m.rd(grid + i) for i in range(480)], objs=F(w, 'World', 'objs'),
                    ring=[m.rd(ring + i) for i in range(90)], phase=F(w, 'World', 'phase'),
                    head=head, tail=tail, len=F(sn, 'Snake', 'len'), dir=F(sn, 'Snake', 'dir'),
                    hx=F(head, 'Node', 'x'), hy=F(head, 'Node', 'y'),
                    charged=F(g, 'Game', 'charged') != 0, combo=F(g, 'Game', 'combo'),
                    ball=(F(b, 'Ball', 'active') != 0, F(b, 'Ball', 'x'), F(b, 'Ball', 'y'), F(b, 'Ball', 'vx'), F(b, 'Ball', 'vy')))

    # ---------------- verificacion completa ----------------
    def check(self, m, s):
        self.checks += 1
        G = s['G']
        n = s['tail']; cells = []
        while n != 0:
            cells.append((m.field(n, 'Node', 'x'), m.field(n, 'Node', 'y'))); last = n; n = m.field(n, 'Node', 'next')
            assert len(cells) <= 40, 'lista con ciclo'
        assert last == s['head'] and len(cells) == s['len'], 'lista de la serpiente inconsistente'
        assert len(set(cells)) == len(cells), 'dos segmentos en la misma celda'
        assert all(G[y * 32 + x] == 4 for x, y in cells) and G.count(4) == s['len'], 'grid != serpiente'
        nb = G.count(3)
        for i in range(480):
            o = m.rd(s['objs'] + i)
            assert (o != 0) == (G[i] == 3), 'objs/grid inconsistentes'
        live = m.statics[('Node', 'live')]
        assert live == len(m.objects('Node')) == s['len'] + nb, 'contador de nodos'
        assert live <= 40, 'limite de memoria superado'
        assert G.count(5) <= 1
        assert not any(k == 'string' for k in m.kind.values()), 'FUGA: String vivo'
        # pantalla esperada, palabra por palabra
        exp = {}
        for i in range(480):
            x, y = i % 32, i // 32
            sid = G[i]
            if (x, y) == (s['hx'], s['hy']): sid = 7 if s['charged'] else 6
            for r in range(16): exp[(16 + y * 16 + r) * 32 + x] = SPR[sid][r]
        act, bx, by, vx, vy = s['ball']
        if act:
            x0 = bx - 3; sh = x0 & 15
            for r in range(6):
                a = (by - 3 + r) * 32 + x0 // 16
                exp[a] |= (BALL[r] << sh) & 0xFFFF
                if sh > 10: exp[a + 1] |= BALL[r] << sh >> 16
            for cx in range((bx - 3) // 16, (bx + 2) // 16 + 1):
                for cy in range((by - 19) // 16, (by - 14) // 16 + 1):
                    assert G[cy * 32 + cx] == 0, 'la pelota esta sobre una celda ocupada'
        ring = s['ring']; ph = s['phase']
        lit = [ring[(ph + 30 * k) % 90] for k in range(3)]
        bad = []
        for a, v in exp.items():
            got = m.rd(16384 + a) & 0xFFFF
            if got != v:
                c = ((a // 32 - 16) // 16) * 32 + a % 32
                if c in lit and got == SPR[G[c] + 7][(a // 32 - 16) % 16]: continue
                bad.append((a, c % 32, c // 32, got, v))
        assert not bad, 'pantalla distinta en %d palabras, p.ej. celda (%d,%d)' % (len(bad), bad[0][1], bad[0][2])
        st = self.stats
        st['basura_max'] = max(st['basura_max'], nb); st['mem_max'] = max(st['mem_max'], live)
        if act and self.lastv and (vx, vy) != self.lastv: st['rebotes_pelota'] += 1
        self.lastv = (vx, vy) if act else None

    # ---------------- jugador automatico ----------------
    def choose(self, s):
        G, r = s['G'], self.r
        def t(d):
            x, y = s['hx'] + DXY[d][0], s['hy'] + DXY[d][1]
            return G[y * 32 + x] if 0 <= x < 32 and 0 <= y < 15 else 1
        opts = [d for d in (1, 2, 3, 4) if d != OPP[s['dir']]]
        if self.estilo == 'loco': return r.choice(opts)
        live = s['len'] + G.count(3)
        def safe(d):
            c = t(d)
            if self.estilo == 'acaparador': return c in (0, 2, 5)
            return c in (0, 2) or (c == 3 and s['charged']) or (c == 5 and live < 40)
        ok = [d for d in opts if safe(d)] or opts
        if r.random() < 0.06: return r.choice(ok)
        target = None
        act, bx, by = s['ball'][:3]
        if self.estilo == 'acaparador':
            if 5 in G and not (s['len'] >= 8 and r.random() < 0.5): target = G.index(5)
            else: ok = [d for d in ok if t(d) == 2] or ok
        elif s['charged'] and 3 in G:
            idx = [i for i in range(480) if G[i] == 3]
            target = min(idx, key=lambda i: abs(i % 32 - s['hx']) + abs(i // 32 - s['hy']))
        elif act and G.count(3) > 0:
            target = ((by - 16) // 16) * 32 + bx // 16
        elif 5 in G and live < 40:
            target = G.index(5)
        if target is None:
            nob = [d for d in ok if t(d) != 2]
            return s['dir'] if s['dir'] in nob else r.choice(nob or ok)
        tx, ty = target % 32, target // 32
        return min(ok, key=lambda d: (t(d) == 2 and r.random() < 0.7,
                                      abs(s['hx'] + DXY[d][0] - tx) + abs(s['hy'] + DXY[d][1] - ty), r.random()))

    def __call__(self, m):
        tx = m.text
        hold = (m.time // 40) % 2 == 0
        if tx.get((1, 24)) == 'L' and tx.get((20, 16)) == 'P':                    # titulo
            if 'titulo' in self.shots: m.png(self.shots.pop('titulo'))
            return 32 if hold else 0
        if tx.get((8, 25)) == 'F':                                                 # fin de partida
            if self.prev != 'over':
                self.prev = 'over'; self.deaths += 1; self.lastphase = None
                motivo = ''.join(tx.get((10, c), '') for c in range(17, 50)).strip()
                self.stats['muertes'][motivo] = self.stats['muertes'].get(motivo, 0) + 1
                if 'fin' in self.shots: m.png(self.shots.pop('fin'))
            return (82 if self.deaths < self.partidas else 81) if hold else 0
        if ''.join(tx.get((0, c), '') for c in range(52, 57)) == 'PAUSA':          # pausa
            return 80 if hold else 0
        if not m.objects('Game') or not m.objects('Ball'): return 0
        self.prev = 'play'
        s = self.state(m)
        if s['phase'] != self.lastphase:                                           # turno nuevo
            self.lastphase = s['phase']
            self.check(m, s)
            st = self.stats; st['turnos'] += 1
            if s['combo'] != self.lastcombo and s['combo'] > 0:
                st['limpiezas'] += 1; st['combo_max'] = max(st['combo_max'], s['combo'])
            self.lastcombo = s['combo']
            if s['charged'] and not self.lastcharged: st['atrapadas'] += 1
            self.lastcharged = s['charged']
            for name, cond in (('juego', st['turnos'] == 30 and s['ball'][0]),
                               ('basura', s['G'].count(3) >= 6 and s['ball'][0]),
                               ('cargada', s['charged'] and s['G'].count(3) >= 5)):
                if name in self.shots and cond: m.png(self.shots.pop(name))
            self.want = self.choose(s)
            x = self.r.random()
            if x < 0.004: self.special = [80, 0]; st['pausas'] += 1
            elif self.salir == 'jugando' and st['turnos'] > 500: self.special = [81]
        if self.special: return self.special.pop(0)
        return KEYOF[self.want]


def partida(seed, estilo, partidas, salir='gameover', shots=None):
    bot = Bot(seed, estilo, partidas, salir, shots)
    m = Machine(FOLDER, bot)
    m.run()
    assert not m.blocks, 'FUGA al salir: %d bloques vivos %s' % (len(m.blocks), sorted(set(m.kind.values())))
    fin = ''.join(m.text.get((11, c), '') for c in range(18, 40)).strip()
    assert fin == 'Nodos vivos: 0', 'pantalla final: %r' % fin
    return m, bot


if __name__ == '__main__':
    shots = {}
    if '--capturas' in sys.argv:
        d = os.path.join(HERE, '..', 'docs', 'capturas'); os.makedirs(d, exist_ok=True)
        shots = {k: os.path.join(d, '%d_%s.png' % (i, k)) for i, k in enumerate(['titulo', 'juego', 'basura', 'cargada', 'fin'])}
    rapido = '--vm' in sys.argv
    plan = ([(s, 'listo', 4, 'gameover') for s in range(3 if rapido else 10)] +
            [(s, 'loco', 10, 'gameover') for s in range(100, 102 if rapido else 105)] +
            [(s, 'listo', 99, 'jugando') for s in range(200, 201 if rapido else 203)] +
            [(s, 'acaparador', 5, 'gameover') for s in range(300, 302 if rapido else 305)])
    T = dict(turnos=0, checks=0, limpiezas=0, atrapadas=0, rebotes=0, pausas=0, combo=0, basura=0, mem=0, allocs=0, peak=0, stack=0)
    muertes, rec = {}, {}
    for seed, estilo, n, salir in plan:
        m, b = partida(seed, estilo, n, salir, shots if seed in (0, 1) else None)
        st = b.stats
        T['turnos'] += st['turnos']; T['checks'] += b.checks; T['limpiezas'] += st['limpiezas']
        T['atrapadas'] += st['atrapadas']; T['rebotes'] += st['rebotes_pelota']; T['pausas'] += st['pausas']
        T['combo'] = max(T['combo'], st['combo_max']); T['basura'] = max(T['basura'], st['basura_max']); T['mem'] = max(T['mem'], st['mem_max'])
        T['allocs'] += m.allocs; T['peak'] = max(T['peak'], m.peak_words); T['stack'] = max(T['stack'], m.maxstack)
        for k, v in st['muertes'].items(): muertes[k] = muertes.get(k, 0) + v
        for k, v in m.maxrec.items():
            if v > 1: rec[k] = max(rec.get(k, 0), v)
    print('modo:', 'VM compilada' if rapido else 'codigo Jack')
    print('sesiones %d | turnos %d | verificaciones completas %d' % (len(plan), T['turnos'], T['checks']))
    print('pelota: %d veces atrapada, %d rebotes | limpiezas %d (combo max %d) | basura max %d | memoria max %d/40 | pausas %d'
          % (T['atrapadas'], T['rebotes'], T['limpiezas'], T['combo'], T['basura'], T['mem'], T['pausas']))
    print('muertes:', muertes)
    print('recursion maxima:', rec)
    print('heap: %d reservas, todas liberadas, pico %d/14336 palabras | pila: pico %d/1792' % (T['allocs'], T['peak'], T['stack']))
    print('TODO OK')
