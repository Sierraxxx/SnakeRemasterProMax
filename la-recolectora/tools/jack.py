"""
jack.py - Interprete de Jack para verificar LA RECOLECTORA sin el emulador.

Lee los .jack, los analiza con la gramatica de Jack y los ejecuta con
aritmetica de 16 bits. Incluye un sistema operativo simulado (Screen, Output,
Keyboard, Memory, Array, String, Math, Sys) que es ESTRICTO:
  - coordenadas de pantalla ilegales            -> error
  - llamar un metodo sobre null                 -> error
  - leer/escribir memoria ya liberada o ajena   -> error
  - liberar dos veces el mismo bloque           -> error
y lleva la cuenta de cada bloque vivo del heap, para demostrar que no hay fugas.
"""
import re, os, glob

TOK = re.compile(r'\s+|//[^\n]*|/\*.*?\*/|(?P<int>\d+)|(?P<str>"[^"\n]*")|(?P<id>[A-Za-z_]\w*)|(?P<sym>[{}()\[\].,;+\-*/&|<>=~])', re.S)
KW = {'class', 'constructor', 'function', 'method', 'field', 'static', 'var', 'int', 'char', 'boolean', 'void',
      'true', 'false', 'null', 'this', 'let', 'do', 'if', 'else', 'while', 'return'}


class JackError(Exception):
    pass


def tokenize(src, fname):
    out, pos = [], 0
    while pos < len(src):
        m = TOK.match(src, pos)
        if not m:
            raise JackError('%s: caracter inesperado %r' % (fname, src[pos:pos + 20]))
        pos = m.end()
        if m.lastgroup == 'int':
            v = int(m.group())
            if v > 32767: raise JackError('%s: entero > 32767' % fname)
            out.append(('int', v))
        elif m.lastgroup == 'str':
            out.append(('str', m.group()[1:-1]))
        elif m.lastgroup == 'id':
            out.append(('kw' if m.group() in KW else 'id', m.group()))
        elif m.lastgroup == 'sym':
            out.append(('sym', m.group()))
    return out


class Parser:
    def __init__(self, toks, fname):
        self.t, self.i, self.f = toks, 0, fname

    def peek(self, k=0): return self.t[self.i + k] if self.i + k < len(self.t) else ('eof', '')
    def next(self): self.i += 1; return self.t[self.i - 1]

    def eat(self, val=None, kind=None):
        k, v = self.next()
        if (val is not None and v != val) or (kind is not None and k != kind):
            raise JackError('%s: se esperaba %s y llego %r (token %d)' % (self.f, val or kind, v, self.i))
        return v

    def type_(self):
        k, v = self.next()
        if k == 'id' or v in ('int', 'char', 'boolean'): return v
        raise JackError('%s: tipo invalido %r' % (self.f, v))

    def klass(self):
        self.eat('class'); name = self.eat(kind='id'); self.eat('{')
        fields, statics, subs = [], [], {}
        while self.peek()[1] in ('field', 'static'):
            kind = self.next()[1]; ty = self.type_()
            names = [self.eat(kind='id')]
            while self.peek()[1] == ',': self.next(); names.append(self.eat(kind='id'))
            self.eat(';')
            (fields if kind == 'field' else statics).extend((ty, n) for n in names)
        while self.peek()[1] in ('constructor', 'function', 'method'):
            kind = self.next()[1]
            ret = self.next()[1]; sname = self.eat(kind='id'); self.eat('(')
            params = []
            if self.peek()[1] != ')':
                while True:
                    ty = self.type_(); params.append((ty, self.eat(kind='id')))
                    if self.peek()[1] != ',': break
                    self.next()
            self.eat(')'); self.eat('{')
            locs = []
            while self.peek()[1] == 'var':
                self.next(); ty = self.type_(); locs.append((ty, self.eat(kind='id')))
                while self.peek()[1] == ',': self.next(); locs.append((ty, self.eat(kind='id')))
                self.eat(';')
            body = self.stmts(); self.eat('}')
            if sname in subs: raise JackError('%s: subrutina duplicada %s' % (self.f, sname))
            if not body or body[-1][0] != 'return':
                raise JackError('%s.%s: no termina en return' % (name, sname))
            subs[sname] = dict(kind=kind, ret=ret, params=params, locs=locs, body=body)
        self.eat('}')
        if self.peek()[0] != 'eof': raise JackError('%s: texto despues de la clase' % self.f)
        return dict(name=name, fields=fields, statics=statics, subs=subs)

    def stmts(self):
        out = []
        while self.peek()[1] in ('let', 'do', 'if', 'while', 'return'):
            v = self.next()[1]
            if v == 'let':
                n = self.eat(kind='id'); idx = None
                if self.peek()[1] == '[': self.next(); idx = self.expr(); self.eat(']')
                self.eat('='); e = self.expr(); self.eat(';'); out.append(('let', n, idx, e))
            elif v == 'do':
                c = self.term()
                if c[0] != 'call': raise JackError('%s: do sin llamada' % self.f)
                self.eat(';'); out.append(('do', c))
            elif v == 'if':
                self.eat('('); c = self.expr(); self.eat(')'); self.eat('{'); a = self.stmts(); self.eat('}')
                b = []
                if self.peek()[1] == 'else': self.next(); self.eat('{'); b = self.stmts(); self.eat('}')
                out.append(('if', c, a, b))
            elif v == 'while':
                self.eat('('); c = self.expr(); self.eat(')'); self.eat('{'); a = self.stmts(); self.eat('}')
                out.append(('while', c, a))
            else:
                e = None
                if self.peek()[1] != ';': e = self.expr()
                self.eat(';'); out.append(('return', e))
        return out

    def expr(self):
        l = self.term()
        while self.peek()[0] == 'sym' and self.peek()[1] in '+-*/&|<>=':
            op = self.next()[1]; l = ('bin', op, l, self.term())
        return l

    def args(self):
        a = []
        if self.peek()[1] != ')':
            a.append(self.expr())
            while self.peek()[1] == ',': self.next(); a.append(self.expr())
        self.eat(')'); return a

    def term(self):
        k, v = self.next()
        if k == 'int': return ('int', v)
        if k == 'str': return ('str', v)
        if v in ('true', 'false', 'null', 'this'): return ('kw', v)
        if v == '(':
            e = self.expr(); self.eat(')'); return e
        if v in ('-', '~'): return ('un', v, self.term())
        if k == 'id':
            p = self.peek()[1]
            if p == '[': self.next(); e = self.expr(); self.eat(']'); return ('idx', v, e)
            if p == '(': self.next(); return ('call', None, v, self.args())
            if p == '.':
                self.next(); m = self.eat(kind='id'); self.eat('('); return ('call', v, m, self.args())
            return ('var', v)
        raise JackError('%s: termino invalido %r' % (self.f, v))


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class Return(Exception):
    def __init__(self, v): self.v = v


class Halt(Exception):
    pass


class Machine:
    HEAP_WORDS = 14336          # heap real de Hack: RAM 2048..16383
    STACK_WORDS = 1792          # pila real: RAM 256..2047

    def __init__(self, folder, keyfn=None):
        self.cls = {}
        for f in sorted(glob.glob(os.path.join(folder, '*.jack'))):
            c = Parser(tokenize(open(f, encoding='utf-8').read(), os.path.basename(f)), os.path.basename(f)).klass()
            if c['name'] + '.jack' != os.path.basename(f):
                raise JackError('la clase %s no coincide con el archivo %s' % (c['name'], f))
            self.cls[c['name']] = c
        self.statics = {}
        self.mem = {}               # direccion -> valor (solo bloques vivos)
        self.blocks = {}            # base -> tamano
        self.kind = {}              # base -> 'obj:Clase' | 'array' | 'string'
        self.strs = {}              # base -> texto
        self.nextaddr = 2048
        self.scrwrites = 0
        self.freed = {}
        self.live_words = self.peak_words = 0
        self.allocs = self.frees = 0
        self.screen = [bytearray(512) for _ in range(256)]
        self.color = 1
        self.text = {}              # (fila, col) -> caracter
        self.cur = [0, 0]
        self.time = 0
        self.keyfn = keyfn or (lambda m: 0)
        self.depth = self.maxdepth = 0
        self.stack = self.maxstack = 0
        self.callcount = {}
        self.maxrec = {}
        self.active = {}
        self.ops = 0

    # ------------------------------ heap ------------------------------
    def alloc(self, n, kind):
        if n < 1: raise JackError('Memory.alloc con tamano %d' % n)
        # Las direcciones se reutilizan lo mas tarde posible (cuarentena),
        # para detectar cualquier uso de memoria despues de liberarla.
        a = None
        for start in (self.nextaddr, 2048):               # siguiente hueco libre, dando la vuelta
            pos = start
            for base in sorted(x for x in self.blocks if x + self.blocks[x] >= start):
                if base - pos >= n + 1: break
                pos = max(pos, base + self.blocks[base] + 1)
            if pos + n + 1 <= 16384:            # heap real de Hack: RAM 2048..16383
                a = pos; break
        if a is None: raise JackError('simulador sin direcciones')
        self.nextaddr = a + n + 1
        self.blocks[a] = n; self.kind[a] = kind
        for i in range(n): self.mem[a + i] = 0
        self.live_words += n + 1; self.peak_words = max(self.peak_words, self.live_words); self.allocs += 1
        if self.live_words > self.HEAP_WORDS: raise JackError('heap agotado')
        return a

    def free(self, a):
        if a not in self.blocks: raise JackError('liberacion invalida o doble de la direccion %d' % a)
        n = self.blocks.pop(a); self.kind.pop(a)
        self.freed.setdefault(n, []).append(a)
        for i in range(n): del self.mem[a + i]
        self.strs.pop(a, None)
        self.live_words -= n + 1; self.frees += 1

    # --- memoria de video: RAM 16384..24575 se traduce a pixeles ---
    def scr_rd(self, a):
        o = a - 16384; row = self.screen[o // 32]; x0 = (o % 32) * 16
        return s16(sum(1 << i for i in range(16) if row[x0 + i]))

    def scr_wr(self, a, v):
        o = a - 16384; row = self.screen[o // 32]; x0 = (o % 32) * 16; v &= 0xFFFF
        for i in range(16): row[x0 + i] = (v >> i) & 1
        self.scrwrites += 1

    def rd(self, a):
        if 16384 <= a < 24576: return self.scr_rd(a)
        if a not in self.mem: raise JackError('lectura de memoria no reservada o ya liberada (%d)' % a)
        return self.mem[a]

    def wr(self, a, v):
        if 16384 <= a < 24576: return self.scr_wr(a, v)
        if a not in self.mem: raise JackError('escritura en memoria no reservada o ya liberada (%d)' % a)
        self.mem[a] = s16(v)

    # ------------------------------ ejecucion ------------------------------
    def run(self):
        try:
            self.call('Main', 'main', [], None)
        except Halt:
            pass

    def call(self, cname, sname, args, this):
        c = self.cls[cname]
        if sname not in c['subs']: raise JackError('no existe %s.%s' % (cname, sname))
        s = c['subs'][sname]
        if len(args) != len(s['params']): raise JackError('%s.%s: numero de argumentos' % (cname, sname))
        if s['kind'] == 'constructor':
            this = self.alloc(max(1, len(c['fields'])), 'obj:' + cname)
        fr = dict(cls=c, sub=s, this=this, vars={n: 0 for _, n in s['locs']})
        fr['types'] = {n: t for t, n in s['locs']}
        for (t, n), v in zip(s['params'], args):
            fr['vars'][n] = v; fr['types'][n] = t
        key = cname + '.' + sname
        words = 5 + len(args) + (1 if s['kind'] == 'method' else 0) + len(s['locs']) + 6
        self.depth += 1; self.stack += words
        self.maxdepth = max(self.maxdepth, self.depth); self.maxstack = max(self.maxstack, self.stack)
        if self.stack > self.STACK_WORDS: raise JackError('desbordamiento de pila en ' + key)
        self.active[key] = self.active.get(key, 0) + 1
        self.maxrec[key] = max(self.maxrec.get(key, 0), self.active[key])
        self.callcount[key] = self.callcount.get(key, 0) + 1
        try:
            self.block(s['body'], fr); ret = 0
        except Return as r:
            ret = r.v
        self.active[key] -= 1; self.depth -= 1; self.stack -= words
        return ret

    def block(self, stmts, fr):
        for st in stmts:
            self.ops += 1
            k = st[0]
            if k == 'let':
                v = self.ev(st[3], fr)
                if st[2] is None: self.setvar(st[1], v, fr)
                else: self.wr(self.elem(st[1], st[2], fr), v)
            elif k == 'do': self.ev(st[1], fr)
            elif k == 'if':
                self.block(st[2] if self.ev(st[1], fr) != 0 else st[3], fr)
            elif k == 'while':
                while self.ev(st[1], fr) != 0: self.block(st[2], fr)
            else:
                if st[1] is None:
                    if fr['sub']['ret'] != 'void': raise JackError('return sin valor en subrutina no void')
                    raise Return(0)
                raise Return(self.ev(st[1], fr))

    def where(self, name, fr):
        if name in fr['vars']: return 'l'
        c = fr['cls']
        for i, (t, n) in enumerate(c['fields']):
            if n == name:
                if fr['sub']['kind'] == 'function': raise JackError('campo %s usado en function' % name)
                return ('f', i, t)
        for t, n in c['statics']:
            if n == name: return ('s', t)
        return None

    def vtype(self, name, fr):
        w = self.where(name, fr)
        if w is None: return None
        if w == 'l': return fr['types'][name]
        return w[2] if w[0] == 'f' else w[1]

    def getvar(self, name, fr):
        w = self.where(name, fr)
        if w is None: raise JackError('variable no declarada: %s en %s' % (name, fr['cls']['name']))
        if w == 'l': return fr['vars'][name]
        if w[0] == 'f': return self.rd(fr['this'] + w[1])
        return self.statics.get((fr['cls']['name'], name), 0)

    def setvar(self, name, v, fr):
        v = s16(v); w = self.where(name, fr)
        if w is None: raise JackError('variable no declarada: %s' % name)
        if w == 'l': fr['vars'][name] = v
        elif w[0] == 'f': self.wr(fr['this'] + w[1], v)
        else: self.statics[(fr['cls']['name'], name)] = v

    def elem(self, name, idx, fr):
        base = self.getvar(name, fr); i = self.ev(idx, fr)
        if base == 16384:
            if not 0 <= i < 8192: raise JackError('escritura fuera de la pantalla: %s[%d]' % (name, i))
            return base + i
        if self.kind.get(base) != 'array': raise JackError('%s[...] no es un arreglo vivo' % name)
        if not 0 <= i < self.blocks[base]: raise JackError('indice %d fuera del arreglo %s (tamano %d)' % (i, name, self.blocks[base]))
        return base + i

    def ev(self, e, fr):
        k = e[0]
        if k == 'int': return e[1]
        if k == 'var': return self.getvar(e[1], fr)
        if k == 'kw':
            if e[1] == 'true': return -1
            if e[1] == 'this':
                if fr['sub']['kind'] == 'function': raise JackError('this en function')
                return fr['this']
            return 0
        if k == 'str':
            a = self.alloc(len(e[1]) + 3, 'string'); self.strs[a] = e[1]; return a
        if k == 'idx': return self.rd(self.elem(e[1], e[2], fr))
        if k == 'un':
            v = self.ev(e[2], fr); return s16(-v) if e[1] == '-' else s16(~v)
        if k == 'bin':
            a = self.ev(e[2], fr); b = self.ev(e[3], fr); op = e[1]
            if op == '+': return s16(a + b)
            if op == '-': return s16(a - b)
            if op == '*': return s16(a * b)
            if op == '/':
                if b == 0: raise JackError('division por cero')
                q = abs(a) // abs(b); return s16(q if (a < 0) == (b < 0) else -q)
            if op == '&': return s16(a & b)
            if op == '|': return s16(a | b)
            if op == '<': return -1 if a < b else 0
            if op == '>': return -1 if a > b else 0
            return -1 if a == b else 0
        # llamada
        _, tgt, name, argex = e
        if tgt is None:
            if fr['sub']['kind'] == 'function': raise JackError('llamada a metodo %s sin objeto dentro de una function' % name)
            if fr['cls']['subs'].get(name, {}).get('kind') != 'method': raise JackError('%s no es un metodo de %s' % (name, fr['cls']['name']))
            return self.call(fr['cls']['name'], name, [self.ev(a, fr) for a in argex], fr['this'])
        ty = self.vtype(tgt, fr)
        if ty is not None:                                    # metodo sobre un objeto
            obj = self.getvar(tgt, fr)
            args = [self.ev(a, fr) for a in argex]
            if obj == 0: raise JackError('llamada a %s.%s sobre null (en %s)' % (tgt, name, fr['cls']['name']))
            if ty in self.cls:
                if self.kind.get(obj) != 'obj:' + ty: raise JackError('%s.%s: el objeto ya fue liberado o no es %s' % (tgt, name, ty))
                if self.cls[ty]['subs'].get(name, {}).get('kind') != 'method': raise JackError('%s.%s no es metodo' % (ty, name))
                return self.call(ty, name, args, obj)
            return self.os_method(ty, name, obj, args)
        args = [self.ev(a, fr) for a in argex]
        if tgt in self.cls:
            if self.cls[tgt]['subs'].get(name, {}).get('kind') not in ('function', 'constructor'):
                raise JackError('%s.%s no es function/constructor' % (tgt, name))
            return self.call(tgt, name, args, None)
        return self.os_func(tgt, name, args)

    # ------------------------------ sistema operativo ------------------------------
    def os_method(self, ty, name, obj, a):
        if ty == 'Array' and name == 'dispose':
            if self.kind.get(obj) != 'array': raise JackError('Array.dispose sobre algo que no es un arreglo vivo')
            self.free(obj); return 0
        if ty == 'String':
            if self.kind.get(obj) != 'string': raise JackError('String.%s sobre un String ya liberado' % name)
            if name == 'dispose': self.free(obj); return 0
            if name == 'length': return len(self.strs[obj])
        raise JackError('metodo del SO no soportado: %s.%s' % (ty, name))

    def px(self, x, y):
        if not (0 <= x <= 511 and 0 <= y <= 255): raise JackError('coordenada de pantalla ilegal (%d,%d)' % (x, y))
        self.screen[y][x] = self.color

    def os_func(self, c, n, a):
        if c == 'Memory' and n == 'deAlloc': self.free(a[0]); return 0
        if c == 'Memory' and n == 'alloc': return self.alloc(a[0], 'array')
        if c == 'Array' and n == 'new': return self.alloc(a[0], 'array')
        if c == 'Math':
            if n == 'multiply': return s16(a[0] * a[1])
            if n == 'abs': return abs(a[0])
            if n == 'min': return min(a);
            if n == 'max': return max(a)
        if c == 'Sys':
            if n == 'wait':
                if a[0] <= 0: raise JackError('Sys.wait con duracion <= 0')
                self.time += a[0]; return 0
            if n == 'halt': raise Halt()
        if c == 'Keyboard' and n == 'keyPressed':
            self.time += 1
            return self.keyfn(self)
        if c == 'Screen':
            if n == 'clearScreen':
                for r in self.screen: r[:] = bytes(512)
                self.text.clear(); return 0
            if n == 'setColor': self.color = 1 if a[0] != 0 else 0; return 0
            if n == 'drawPixel': self.px(a[0], a[1]); return 0
            if n == 'drawRectangle':
                x1, y1, x2, y2 = a
                if not (0 <= x1 <= x2 <= 511 and 0 <= y1 <= y2 <= 255): raise JackError('drawRectangle ilegal %s' % a)
                for y in range(y1, y2 + 1):
                    self.screen[y][x1:x2 + 1] = bytes([self.color]) * (x2 - x1 + 1)
                for (r, cc) in [k for k in self.text if y1 <= k[0] * 11 + 5 <= y2 and x1 <= k[1] * 8 + 4 <= x2]:
                    del self.text[(r, cc)]
                return 0
            if n == 'drawLine':
                x1, y1, x2, y2 = a
                for (x, y) in ((x1, y1), (x2, y2)):
                    if not (0 <= x <= 511 and 0 <= y <= 255): raise JackError('drawLine ilegal %s' % a)
                steps = max(abs(x2 - x1), abs(y2 - y1), 1)
                for i in range(steps + 1):
                    self.px(round(x1 + (x2 - x1) * i / steps), round(y1 + (y2 - y1) * i / steps))
                return 0
            if n == 'drawCircle':
                x, y, r = a
                if not (0 <= r <= 181 and x - r >= 0 and x + r <= 511 and y - r >= 0 and y + r <= 255):
                    raise JackError('drawCircle ilegal %s' % a)
                for dy in range(-r, r + 1):
                    w = int((r * r - dy * dy) ** 0.5)
                    self.screen[y + dy][x - w:x + w + 1] = bytes([self.color]) * (2 * w + 1)
                return 0
        if c == 'Output':
            if n == 'moveCursor':
                if not (0 <= a[0] <= 22 and 0 <= a[1] <= 63): raise JackError('moveCursor ilegal %s' % a)
                self.cur = [a[0], a[1]]; return 0
            if n in ('printString', 'printInt'):
                if n == 'printString':
                    if self.kind.get(a[0]) != 'string': raise JackError('printString de un String liberado o null')
                    s = self.strs[a[0]]
                else:
                    s = str(a[0])
                for ch in s:
                    if self.cur[1] > 63: raise JackError('el texto %r se sale de la fila %d' % (s, self.cur[0]))
                    self.text[(self.cur[0], self.cur[1])] = ch; self.cur[1] += 1
                return 0
        raise JackError('funcion del SO no soportada: %s.%s' % (c, n))

    # ------------------------------ utilidades de prueba ------------------------------
    def field(self, obj, cname, fname):
        for i, (t, n) in enumerate(self.cls[cname]['fields']):
            if n == fname: return self.rd(obj + i)
        raise KeyError(fname)

    def objects(self, cname):
        return [a for a, k in self.kind.items() if k == 'obj:' + cname]

    def png(self, path, scale=2):
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('L', (512, 256), 255)
        img.putdata([0 if p else 255 for row in self.screen for p in row])
        d = ImageDraw.Draw(img)
        try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 9)
        except Exception: font = ImageFont.load_default()
        for (r, cc), ch in self.text.items():
            d.text((cc * 8, r * 11), ch, fill=0, font=font)
        img.resize((512 * scale, 256 * scale), Image.NEAREST).save(path)
