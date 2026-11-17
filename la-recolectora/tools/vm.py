"""
vm.py - Ejecuta los .vm compilados (maquina de pila de Nand2Tetris) con el
mismo sistema operativo estricto de jack.py. Sirve para probar exactamente
los archivos que se cargan en el VM Emulator.
"""
import os, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jack import Machine, JackError, Halt, s16


class VMachine(Machine):
    def __init__(self, folder, keyfn=None):
        super().__init__(folder, keyfn)
        self.funcs = {}
        for f in sorted(glob.glob(os.path.join(folder, '*.vm'))):
            cur = None
            for line in open(f):
                p = line.split('//')[0].split()
                if not p: continue
                if p[0] == 'function':
                    cur = dict(name=p[1], nloc=int(p[2]), code=[], labels={}); self.funcs[p[1]] = cur
                elif p[0] == 'label': cur['labels'][p[1]] = len(cur['code'])
                else: cur['code'].append(p)
        self.vstat = {}
        self.ctor = []

    def run(self):
        try: self.vcall('Main.main', [])
        except Halt: pass

    def vcall(self, name, args):
        cls, sub = name.split('.')
        if name not in self.funcs:
            return self.oscall(cls, sub, args)
        f = self.funcs[name]
        words = 5 + len(args) + f['nloc'] + 6
        self.stack += words; self.maxstack = max(self.maxstack, self.stack)
        if self.stack > self.STACK_WORDS: raise JackError('desbordamiento de pila en ' + name)
        self.active[name] = self.active.get(name, 0) + 1
        self.maxrec[name] = max(self.maxrec.get(name, 0), self.active[name])
        self.ctor.append(cls if sub == 'new' else None)
        loc = [0] * f['nloc']; st = []; this = that = 0; pc = 0; code = f['code']; labels = f['labels']
        while True:
            c = code[pc]; pc += 1; op = c[0]; self.ops += 1
            if op == 'push':
                seg, i = c[1], int(c[2])
                if seg == 'constant': st.append(i)
                elif seg == 'local': st.append(loc[i])
                elif seg == 'argument': st.append(args[i])
                elif seg == 'this': st.append(self.rd(this + i))
                elif seg == 'that': st.append(self.rd(that + i))
                elif seg == 'pointer': st.append(this if i == 0 else that)
                elif seg == 'temp': st.append(self.temp[i])
                elif seg == 'static': st.append(self.vstat.get((cls, i), 0))
            elif op == 'pop':
                seg, i = c[1], int(c[2]); v = st.pop()
                if seg == 'local': loc[i] = v
                elif seg == 'argument': args[i] = v
                elif seg == 'this': self.wr(this + i, v)
                elif seg == 'that':
                    if 16384 <= that + i < 24576 or (that + i) in self.mem: self.wr(that + i, v)
                    else: raise JackError('escritura invalida en %d' % (that + i))
                elif seg == 'pointer':
                    if i == 0: this = v
                    else: that = v
                elif seg == 'temp': self.temp[i] = v
                elif seg == 'static':
                    self.vstat[(cls, i)] = v
                    self.statics[(cls, self.cls[cls]['statics'][i][1])] = v
            elif op == 'add': b = st.pop(); st[-1] = s16(st[-1] + b)
            elif op == 'sub': b = st.pop(); st[-1] = s16(st[-1] - b)
            elif op == 'and': b = st.pop(); st[-1] = s16(st[-1] & b)
            elif op == 'or': b = st.pop(); st[-1] = s16(st[-1] | b)
            elif op == 'eq': b = st.pop(); st[-1] = -1 if st[-1] == b else 0
            elif op == 'lt': b = st.pop(); st[-1] = -1 if st[-1] < b else 0
            elif op == 'gt': b = st.pop(); st[-1] = -1 if st[-1] > b else 0
            elif op == 'neg': st[-1] = s16(-st[-1])
            elif op == 'not': st[-1] = s16(~st[-1])
            elif op == 'goto': pc = labels[c[1]]
            elif op == 'if-goto':
                if st.pop() != 0: pc = labels[c[1]]
            elif op == 'call':
                n = int(c[2]); a = st[len(st) - n:] if n else []
                if n: del st[len(st) - n:]
                st.append(self.vcall(c[1], a))
            elif op == 'return':
                self.ctor.pop(); self.active[name] -= 1; self.stack -= words
                return st.pop()
            else: raise JackError('comando VM desconocido: ' + ' '.join(c))

    temp = [0] * 8

    def oscall(self, c, n, a):
        if c == 'Memory' and n == 'alloc':
            owner = self.ctor[-1] if self.ctor else None
            return self.alloc(a[0], 'obj:' + owner if owner else 'array')
        if c == 'Math' and n == 'divide':
            if a[1] == 0: raise JackError('division por cero')
            q = abs(a[0]) // abs(a[1]); return s16(q if (a[0] < 0) == (a[1] < 0) else -q)
        if c == 'String':
            if n == 'new':
                p = self.alloc(a[0] + 3, 'string'); self.strs[p] = ''; return p
            if self.kind.get(a[0]) != 'string': raise JackError('String.%s sobre un String liberado' % n)
            if n == 'appendChar':
                if len(self.strs[a[0]]) >= self.blocks[a[0]] - 3: raise JackError('String lleno')
                self.strs[a[0]] += chr(a[1]); return a[0]
            if n == 'dispose': self.free(a[0]); return 0
        if c == 'Array' and n == 'dispose':
            if self.kind.get(a[0]) != 'array': raise JackError('Array.dispose invalido')
            self.free(a[0]); return 0
        return self.os_func(c, n, a)
