"""Simbologias pessoais: primitivas vetoriais validadas, sem código executável."""
import math
import re


def clean_symbol(data, draft=False):
    if not isinstance(data, dict):
        raise ValueError('Simbologia inválida.')
    ident = str(data.get('id', ''))
    if not re.fullmatch(r'user_[a-f0-9]{32}', ident):
        raise ValueError('Identificador da simbologia inválido.')
    name = str(data.get('name', ''))[:96]
    color = str(data.get('color', '#243c4c'))
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('Cor da simbologia inválida.')
    ops = data.get('ops', [])
    if not isinstance(ops, list) or len(ops) > 200 or (not draft and (not name.strip() or not ops)):
        raise ValueError('Informe um nome e desenhe a simbologia (até 200 elementos).')

    def num(value, low=-100, high=100):
        try:
            result = float(value)
        except (TypeError, ValueError):
            raise ValueError('Medida da simbologia inválida.')
        if not math.isfinite(result) or not low <= result <= high:
            raise ValueError('Medida da simbologia fora do limite.')
        return round(result, 3)

    def fill(value):
        if value is True or value is False or value == 'projetado':
            return value
        raise ValueError('Preenchimento da simbologia inválido.')

    out = []
    vertices = 0
    for op in ops:
        if not isinstance(op, list) or not op or op[0] not in ('line', 'circle', 'rect', 'poly', 'text', 'arc'):
            raise ValueError('Elemento da simbologia inválido.')
        kind = op[0]
        expected = {'line': 5, 'circle': 5, 'rect': 6, 'poly': 3, 'text': 5, 'arc': 6}[kind]
        if len(op) != expected:
            raise ValueError('Elemento incompleto na simbologia.')
        if kind == 'line':
            row = [kind] + [num(v) for v in op[1:]]
        elif kind in ('circle', 'arc'):
            row = [kind, num(op[1]), num(op[2]), num(op[3], .1, 100)]
            row += [fill(op[4])] if kind == 'circle' else [num(op[4], -360, 360), num(op[5], -360, 360)]
        elif kind == 'rect':
            row = [kind, num(op[1]), num(op[2]), num(op[3], .1, 200), num(op[4], .1, 200), fill(op[5])]
        elif kind == 'text':
            row = [kind, num(op[1]), num(op[2]), str(op[3])[:32], num(op[4], 2, 60)]
        else:
            pts = op[1]
            if not isinstance(pts, list) or not 2 <= len(pts) <= 200:
                raise ValueError('Polígono inválido.')
            vertices += len(pts)
            if vertices > 2000 or any(not isinstance(p, list) or len(p) != 2 for p in pts):
                raise ValueError('Pontos da simbologia inválidos.')
            row = [kind, [[num(x), num(y)] for x, y in pts], fill(op[2])]
        out.append(row)
    return {'id': ident, 'name': name, 'tag': str(data.get('tag', ''))[:32], 'color': color,
            'group': 'Minhas simbologias', 'line': data.get('line') is True, 'ops': out}
