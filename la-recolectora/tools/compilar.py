"""
compilar.py - Compilador de Jack a codigo VM de Nand2Tetris.
  python3 compilar.py [carpeta]   -> escribe un .vm por cada .jack
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jack import Parser, tokenize, JackError

OPS = {'+': 'add', '-': 'sub', '*': 'call Math.multiply 2', '/': 'call Math.divide 2',
       '&': 'and', '|': 'or', '<': 'lt', '>': 'gt', '=': 'eq'}


class Compiler:
    def __init__(self, c, classes):
        self.c, self.classes, self.out, self.n = c, classes, [], 0
        self.cvars = {}
        for i, (t, n) in enumerate(c['fields']): self.cvars[n] = ('this', i, t)
        for i, (t, n) in enumerate(c['statics']): self.cvars[n] = ('static', i, t)

    def w(self, s): self.out.append(s)

    def label(self):
        self.n += 1; return '%s_L%d' % (self.c['name'], self.n)

    def look(self, name):
        if name in self.svars: return self.svars[name]
        if name in self.cvars:
            v = self.cvars[name]
            if v[0] == 'this' and self.kind == 'function': raise JackError('campo %s en function' % name)
            return v
        return None

    def compile(self):
        for sname, s in self.c['subs'].items():
            self.kind = s['kind']; self.svars = {}
            base = 1 if s['kind'] == 'method' else 0
            for i, (t, n) in enumerate(s['params']): self.svars[n] = ('argument', i + base, t)
            for i, (t, n) in enumerate(s['locs']): self.svars[n] = ('local', i, t)
            self.w('function %s.%s %d' % (self.c['name'], sname, len(s['locs'])))
            if s['kind'] == 'constructor':
                self.w('push constant %d' % max(1, len(self.c['fields']))); self.w('call Memory.alloc 1'); self.w('pop pointer 0')
            elif s['kind'] == 'method':
                self.w('push argument 0'); self.w('pop pointer 0')
            self.stmts(s['body'])
        return '\n'.join(self.out) + '\n'

    def stmts(self, ss):
        for st in ss:
            k = st[0]
            if k == 'let':
                seg, i, _ = self.look(st[1]) or self.err(st[1])
                if st[2] is None:
                    self.expr(st[3]); self.w('pop %s %d' % (seg, i))
                else:
                    self.w('push %s %d' % (seg, i)); self.expr(st[2]); self.w('add'); self.expr(st[3])
                    self.w('pop temp 0'); self.w('pop pointer 1'); self.w('push temp 0'); self.w('pop that 0')
            elif k == 'do':
                self.expr(st[1]); self.w('pop temp 0')
            elif k == 'if':
                a, b = self.label(), self.label()
                self.expr(st[1]); self.w('not'); self.w('if-goto ' + a)
                self.stmts(st[2]); self.w('goto ' + b); self.w('label ' + a); self.stmts(st[3]); self.w('label ' + b)
            elif k == 'while':
                a, b = self.label(), self.label()
                self.w('label ' + a); self.expr(st[1]); self.w('not'); self.w('if-goto ' + b)
                self.stmts(st[2]); self.w('goto ' + a); self.w('label ' + b)
            else:
                if st[1] is None: self.w('push constant 0')
                else: self.expr(st[1])
                self.w('return')

    def err(self, n): raise JackError('variable no declarada %s en %s' % (n, self.c['name']))

    def expr(self, e):
        k = e[0]
        if k == 'int': self.w('push constant %d' % e[1])
        elif k == 'str':
            self.w('push constant %d' % len(e[1])); self.w('call String.new 1')
            for ch in e[1]:
                self.w('push constant %d' % ord(ch)); self.w('call String.appendChar 2')
        elif k == 'kw':
            if e[1] == 'true': self.w('push constant 0'); self.w('not')
            elif e[1] == 'this': self.w('push pointer 0')
            else: self.w('push constant 0')
        elif k == 'var':
            seg, i, _ = self.look(e[1]) or self.err(e[1]); self.w('push %s %d' % (seg, i))
        elif k == 'idx':
            seg, i, _ = self.look(e[1]) or self.err(e[1])
            self.w('push %s %d' % (seg, i)); self.expr(e[2]); self.w('add'); self.w('pop pointer 1'); self.w('push that 0')
        elif k == 'un':
            self.expr(e[2]); self.w('neg' if e[1] == '-' else 'not')
        elif k == 'bin':
            self.expr(e[2]); self.expr(e[3]); self.w(OPS[e[1]])
        else:
            _, tgt, name, args = e
            if tgt is None:
                self.w('push pointer 0'); cls, n = self.c['name'], len(args) + 1
            else:
                v = self.look(tgt)
                if v: self.w('push %s %d' % (v[0], v[1])); cls, n = v[2], len(args) + 1
                else: cls, n = tgt, len(args)
            for a in args: self.expr(a)
            self.w('call %s.%s %d' % (cls, name, n))


def compilar(folder):
    classes = {}
    for f in sorted(glob.glob(os.path.join(folder, '*.jack'))):
        c = Parser(tokenize(open(f, encoding='utf-8').read(), f), os.path.basename(f)).klass()
        classes[c['name']] = c
    for name, c in classes.items():
        vm = Compiler(c, classes).compile()
        open(os.path.join(folder, name + '.vm'), 'w').write(vm)
        print('%-8s -> %s.vm (%d lineas)' % (name + '.jack', name, vm.count('\n')))


if __name__ == '__main__':
    compilar(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'LaRecolectora'))
