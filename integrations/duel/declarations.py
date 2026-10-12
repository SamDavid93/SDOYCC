"""API 11 card declaration predicates, based on the pinned EDOPro ABI.

Reference: c250b6ab9beb gframe/data_manager.cpp IsCardDeclarable.
Only trusted core predicates reach this evaluator; browser input is a choice ID.
"""
import operator

BASE = 0x4000000000000000
BINARY = {0: operator.add, 1: operator.sub, 2: operator.mul,
    4: lambda a, b: int(bool(a) and bool(b)), 5: lambda a, b: int(bool(a) or bool(b)),
    8: operator.and_, 9: operator.or_, 0x11: operator.xor}
FIELDS = {0x100: 'code', 0x102: 'type', 0x103: 'race', 0x104: 'attribute'}
GETTERS = {0x105: 'code', 0x107: 'type', 0x108: 'race', 0x109: 'attribute'}


def signed(value):
    value &= (1 << 64) - 1
    return value - (1 << 64) if value & (1 << 63) else value


def declarable(code, card, program):
    stack, aliases, tokens = [], False, False
    source = {**card, 'code': code}
    for opcode in program:
        number = (opcode - BASE) >> 32 if opcode >= BASE and (opcode - BASE) & 0xffffffff == 0 else None
        if number in BINARY or number in (3, 0x12, 0x13):
            if len(stack) < 2: return False
            right, left = stack.pop(), stack.pop()
            if number == 3:
                if right == 0: return False
                value = abs(left) // abs(right) * (-1 if (left < 0) != (right < 0) else 1)
            elif number in (0x12, 0x13):
                if not 0 <= right < 64: return False
                value = left << right if number == 0x12 else left >> right
            else: value = BINARY[number](left, right)
            stack.append(signed(value))
        elif number in (6, 7, 0x10) or number in FIELDS or number == 0x101:
            if not stack: return False
            value = stack.pop()
            if number == 6: value = -value
            elif number == 7: value = int(not value)
            elif number == 0x10: value = ~value
            elif number == 0x101:
                packed = source.get('setcode', 0)
                sets = [(packed >> shift) & 65535 for shift in (0, 16, 32, 48)]
                value = int(any(sc and sc & 0xfff == value & 0xfff and sc & value & 0xf000 == value & 0xf000 for sc in sets))
            elif number == 0x100: value = int(code == value)
            else: value = source.get(FIELDS[number], 0) & value
            stack.append(signed(value))
        elif number in GETTERS: stack.append(signed(source.get(GETTERS[number], 0)))
        elif number == 0x14: aliases = True
        elif number == 0x15: tokens = True
        else: stack.append(signed(opcode))
    if len(stack) != 1 or stack[0] == 0: return False
    return code in (78734254, 13857930) or ((aliases or not source.get('alias', 0)) and
        (tokens or source.get('type', 0) & 0x4001 != 0x4001))
