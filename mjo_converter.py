#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mjo_converter.py
================

Двунаправленный конвертер файлов Majiro engine (.mjo ↔ .txt).

Формат .mjo (Majiro Object Script):
    Header (16 bytes): "MajiroObjV1.000" (расшифрован) или
                        "MajiroObjX1.000" (зашифрован)
    uint32  MainOffset      -- смещение до функции $main в байткоде
    uint32  LineCount       -- количество строк в исходном скрипте
    uint32  FunctionCount   -- количество функций
    Function[Count]:
        uint32 Hash         -- CRC32-хеш имени функции
        uint32 Offset       -- смещение в байткоде
    uint32  BytecodeSize    -- размер байткода
    byte[Size] Bytecode     -- зашифрованный/расшифрованный байткод

Шифрование байткода:
    XOR-шифр с 1024-байтным ключом, который является побайтовым
    представлением (little-endian) CRC32-таблицы (256 uint32 значений,
    вычисленных с полиномом 0xEDB88320).

Использование:
    # .mjo -> .txt (дизассемблирование)
    python mjo_converter.py script.mjo -o script.txt
    # .txt -> .mjo (ассемблирование и шифрование)
    python mjo_converter.py script.txt -o script.mjo
    # авто-определение по расширению
    python mjo_converter.py script.mjo           # -> script.txt
    python mjo_converter.py script.txt           # -> script.mjo

Автор: abral syndicate
"""

from __future__ import annotations

import argparse
import io
import os
import struct
import sys
from dataclasses import dataclass, field
from typing import BinaryIO, Iterable, List, Optional, Tuple


# ============================================================================
# КРИПТОГРАФИЯ (XOR-шифр с ключом CRC32-таблицы)
# ============================================================================

def _crc32_table_uint32() -> Tuple[int, ...]:
    """Возвращает 256 значений uint32 стандартной CRC32-таблицы (poly 0xEDB88320)."""
    poly = 0xEDB88320
    table = []
    for i in range(256):
        num = i
        for _ in range(8):
            if num & 1:
                num = (num >> 1) ^ poly
            else:
                num >>= 1
        table.append(num & 0xFFFFFFFF)
    return tuple(table)


def _build_xor_key() -> bytes:
    """Строит 1024-байтный XOR-ключ из CRC32-таблицы (little-endian)."""
    return b"".join(struct.pack("<I", v) for v in _crc32_table_uint32())


XOR_KEY: bytes = _build_xor_key()
XOR_KEY_LEN: int = len(XOR_KEY)  # 1024


def xor_crypt(data: bytearray | bytes, key_offset: int = 0) -> None:
    """Шифрует/дешифрует массив байт in-place с помощью XOR-ключа Majiro."""
    if isinstance(data, bytes):
        data = bytearray(data)
    for i in range(len(data)):
        data[i] ^= XOR_KEY[(key_offset + i) % XOR_KEY_LEN]


# ============================================================================
# КОНСТАНТЫ ЗАГОЛОВКА .MJO
# ============================================================================

MAGIC_SIZE = 16
SIGNATURE_DECRYPTED = b"MajiroObjV1.000\x00"  # 'V' = расшифрован
SIGNATURE_ENCRYPTED = b"MajiroObjX1.000\x00"  # 'X' = зашифрован


# ============================================================================
# ТАБЛИЦА ОПКОДОВ MAJIRO IL
# ============================================================================
#
# Типы:
#   0=int (.i), 1=float (.r), 2=string (.s),
#   3=int[] (.iarr), 4=float[] (.rarr), 5=string[] (.sarr)
#
# Операнды:
#   (пусто)      — нет операндов
#   int32        — 4 байта, int
#   float32      — 4 байта, float
#   string       — uint16 N + N байт (включая '\0')
#   field        — uint16 flags + uint32 hash + int16 offset
#   method       — uint32 hash
#   call         — uint32 hash + int32 placeholder + uint16 argc
#   syscall      — uint32 hash + uint16 argc
#   typelist     — uint16 N + N байт (типы)
#   case         — uint16 N + int32[N] относительных смещений
#   jump         — int32 относительное смещение
#   lineno       — uint16


@dataclass(frozen=True)
class OpInfo:
    name: str
    operand_kind: str = ""  # пусто = нет операндов


# Все опкоды < 0x100 — короткие опкоды 1 байт, но Majiro использует uint16
# В таблице используются только реально встречающиеся опкоды.
OPCODE_TABLE: dict[int, OpInfo] = {
    # --- Арифметика / побитовые / логические (без операндов) ---
    0x100: OpInfo("mul.i"),
    0x101: OpInfo("mul.r"),
    0x108: OpInfo("div.i"),
    0x109: OpInfo("div.r"),
    0x110: OpInfo("rem"),
    0x118: OpInfo("add.i"),
    0x119: OpInfo("add.r"),
    0x11A: OpInfo("add.s"),
    0x120: OpInfo("sub.i"),
    0x121: OpInfo("sub.r"),
    0x128: OpInfo("shr"),
    0x130: OpInfo("shl"),
    0x138: OpInfo("cle.i"),
    0x139: OpInfo("cle.r"),
    0x13A: OpInfo("cle.s"),
    0x140: OpInfo("clt.i"),
    0x141: OpInfo("clt.r"),
    0x142: OpInfo("clt.s"),
    0x148: OpInfo("cge.i"),
    0x149: OpInfo("cge.r"),
    0x14A: OpInfo("cge.s"),
    0x150: OpInfo("cgt.i"),
    0x151: OpInfo("cgt.r"),
    0x152: OpInfo("cgt.s"),
    0x158: OpInfo("ceq.i"),
    0x159: OpInfo("ceq.r"),
    0x15A: OpInfo("ceq.s"),
    0x15B: OpInfo("ceq.iarr"),
    0x15C: OpInfo("ceq.rarr"),
    0x15D: OpInfo("ceq.sarr"),
    0x160: OpInfo("cne.i"),
    0x161: OpInfo("cne.r"),
    0x162: OpInfo("cne.s"),
    0x163: OpInfo("cne.iarr"),
    0x164: OpInfo("cne.rarr"),
    0x165: OpInfo("cne.sarr"),
    0x168: OpInfo("xor"),
    0x170: OpInfo("andl"),
    0x178: OpInfo("orl"),
    0x180: OpInfo("and"),
    0x188: OpInfo("or"),
    0x190: OpInfo("notl"),
    0x191: OpInfo("nop.191"),
    0x198: OpInfo("not"),
    0x1A0: OpInfo("neg.i"),
    0x1A1: OpInfo("neg.r"),
    0x1A8: OpInfo("nop.1a8"),
    0x1A9: OpInfo("nop.1a9"),

    # --- Сохранение в переменную <field> ---
    0x1B0: OpInfo("st.i",   "field"),
    0x1B1: OpInfo("st.f",   "field"),
    0x1B2: OpInfo("st.s",   "field"),
    0x1B3: OpInfo("st.iarr", "field"),
    0x1B4: OpInfo("st.rarr", "field"),
    0x1B5: OpInfo("st.sarr", "field"),
    0x1B8: OpInfo("st.mul.i", "field"),
    0x1B9: OpInfo("st.mul.r", "field"),
    0x1C0: OpInfo("st.div.i", "field"),
    0x1C1: OpInfo("st.div.r", "field"),
    0x1C8: OpInfo("st.rem",   "field"),
    0x1D0: OpInfo("st.add.i", "field"),
    0x1D1: OpInfo("st.add.r", "field"),
    0x1D2: OpInfo("st.add.s", "field"),
    0x1D8: OpInfo("st.sub.i", "field"),
    0x1D9: OpInfo("st.sub.r", "field"),
    0x1E0: OpInfo("st.shl",   "field"),
    0x1E8: OpInfo("st.shr",   "field"),
    0x1F0: OpInfo("st.and",   "field"),
    0x1F8: OpInfo("st.xor",   "field"),
    0x200: OpInfo("st.or",    "field"),

    # --- Сохранение через указатель p <field> ---
    0x210: OpInfo("stp.i",   "field"),
    0x211: OpInfo("stp.f",   "field"),
    0x212: OpInfo("stp.s",   "field"),
    0x213: OpInfo("stp.iarr", "field"),
    0x214: OpInfo("stp.rarr", "field"),
    0x215: OpInfo("stp.sarr", "field"),
    0x218: OpInfo("stp.mul.i", "field"),
    0x219: OpInfo("stp.mul.r", "field"),
    0x220: OpInfo("stp.div.i", "field"),
    0x221: OpInfo("stp.div.r", "field"),
    0x228: OpInfo("stp.rem",   "field"),
    0x230: OpInfo("stp.add.i", "field"),
    0x231: OpInfo("stp.add.r", "field"),
    0x232: OpInfo("stp.add.s", "field"),
    0x238: OpInfo("stp.sub.i", "field"),
    0x239: OpInfo("stp.sub.r", "field"),
    0x240: OpInfo("stp.shl",   "field"),
    0x248: OpInfo("stp.shr",   "field"),
    0x250: OpInfo("stp.and",   "field"),
    0x258: OpInfo("stp.xor",   "field"),
    0x260: OpInfo("stp.or",    "field"),

    # --- Сохранение в элемент массива <field> ---
    0x270: OpInfo("stelem.i", "field"),
    0x271: OpInfo("stelem.f", "field"),
    0x272: OpInfo("stelem.s", "field"),
    0x278: OpInfo("stelem.mul.i", "field"),
    0x279: OpInfo("stelem.mul.r", "field"),
    0x280: OpInfo("stelem.div.i", "field"),
    0x281: OpInfo("stelem.div.r", "field"),
    0x288: OpInfo("stelem.rem",   "field"),
    0x290: OpInfo("stelem.add.i", "field"),
    0x291: OpInfo("stelem.add.r", "field"),
    0x292: OpInfo("stelem.add.s", "field"),
    0x298: OpInfo("stelem.sub.i", "field"),
    0x299: OpInfo("stelem.sub.r", "field"),
    0x2A0: OpInfo("stelem.shl",   "field"),
    0x2A8: OpInfo("stelem.shr",   "field"),
    0x2B0: OpInfo("stelem.and",   "field"),
    0x2B8: OpInfo("stelem.xor",   "field"),
    0x2C0: OpInfo("stelem.or",    "field"),

    # --- Сохранение в элемент массива через указатель <field> ---
    0x2D0: OpInfo("stelemp.i", "field"),
    0x2D1: OpInfo("stelemp.f", "field"),
    0x2D2: OpInfo("stelemp.s", "field"),
    0x2D8: OpInfo("stelemp.mul.i", "field"),
    0x2D9: OpInfo("stelemp.mul.r", "field"),
    0x2E0: OpInfo("stelemp.div.i", "field"),
    0x2E1: OpInfo("stelemp.div.r", "field"),
    0x2E8: OpInfo("stelemp.rem",   "field"),
    0x2F0: OpInfo("stelemp.add.i", "field"),
    0x2F1: OpInfo("stelemp.add.r", "field"),
    0x2F2: OpInfo("stelemp.add.s", "field"),
    0x2F8: OpInfo("stelemp.sub.i", "field"),
    0x2F9: OpInfo("stelemp.sub.r", "field"),
    0x300: OpInfo("stelemp.shl",   "field"),
    0x308: OpInfo("stelemp.shr",   "field"),
    0x310: OpInfo("stelemp.and",   "field"),
    0x318: OpInfo("stelemp.xor",   "field"),
    0x320: OpInfo("stelemp.or",    "field"),

    # --- Литералы / загрузка ---
    0x800: OpInfo("ldc.i",  "int32"),
    0x801: OpInfo("ldstr",  "string"),
    0x802: OpInfo("ld",     "field"),
    0x803: OpInfo("ldc.r",  "float32"),

    # --- Вызовы / управление ---
    0x80F: OpInfo("call",    "call"),
    0x810: OpInfo("callp",   "call"),
    0x829: OpInfo("alloca",  "typelist"),
    0x82B: OpInfo("ret"),
    0x82C: OpInfo("br",      "jump"),
    0x82D: OpInfo("brtrue",  "jump"),
    0x82E: OpInfo("brfalse", "jump"),
    0x82F: OpInfo("pop"),
    0x830: OpInfo("br.case",  "jump"),
    0x831: OpInfo("bne.case", "jump"),
    0x832: OpInfo("bge.case", "jump"),
    0x833: OpInfo("ble.case", "jump"),
    0x834: OpInfo("syscall",  "syscall"),
    0x835: OpInfo("syscallp", "syscall"),
    0x836: OpInfo("argcheck", "typelist"),
    0x837: OpInfo("ldelem",   "field"),
    0x838: OpInfo("blt.case", "jump"),
    0x839: OpInfo("bgt.case", "jump"),
    0x83A: OpInfo("line",     "lineno"),
    0x83B: OpInfo("bsel.1",   "jump"),
    0x83C: OpInfo("bsel.3",   "jump"),
    0x83D: OpInfo("bsel.2",   "jump"),
    0x83E: OpInfo("conv.i"),
    0x83F: OpInfo("conv.r"),
    0x840: OpInfo("text",     "string"),
    0x841: OpInfo("proc"),
    0x842: OpInfo("ctrl",     "string"),
    0x843: OpInfo("bsel.x",   "jump"),
    0x844: OpInfo("bsel.clr"),
    0x845: OpInfo("bsel.4",   "jump"),
    0x846: OpInfo("bsel.jmp.4"),
    0x847: OpInfo("bsel.5"),
    0x850: OpInfo("switch",   "case"),
}


# Кодирование строк Majiro: использует SHIFT-JIS (CP932)
def sjis_decode(data: bytes) -> str:
    """Декодирует строку Majiro (Shift-JIS/CP932) в unicode."""
    try:
        return data.decode("cp932")
    except UnicodeDecodeError:
        # Фоллбэк — latin1, чтобы хотя бы не терять байты
        return data.decode("latin1", errors="replace")


def sjis_encode(text: str) -> bytes:
    """Кодирует unicode-строку обратно в Shift-JIS (CP932)."""
    return text.encode("cp932", errors="replace")


# ============================================================================
# ЧТЕНИЕ / ПАРСИНГ .MJO
# ============================================================================


@dataclass
class MjoFunction:
    hash: int
    offset: int


@dataclass
class Instruction:
    offset: int
    opcode: int
    mnemonic: str
    operands: list  # список значений операндов в нормализованном виде
    raw_bytes: bytes  # сырые байты инструкции (включая опкод)

    def render(self) -> str:
        """Возвращает человеко-читаемое представление инструкции."""
        parts = [self.mnemonic]
        for op in self.operands:
            if isinstance(op, str):
                # строка -- обрамляем кавычками, экранируем \ и "
                esc = op.replace("\\", "\\\\").replace('"', '\\"')
                parts.append(f'"{esc}"')
            else:
                parts.append(str(op))
        return " ".join(parts)


@dataclass
class MjoFile:
    signature: bytes           # 16-байтовая сигнатура
    main_offset: int          # uint32
    line_count: int           # uint32
    functions: List[MjoFunction]
    bytecode_size: int        # uint32
    bytecode: bytearray       # расшифрованный байткод
    encrypted: bool           # была ли сигнатура 'X' (зашифровано)

    @property
    def is_encrypted(self) -> bool:
        return self.signature.startswith(b"MajiroObjX")


def read_mjo(path: str) -> MjoFile:
    with open(path, "rb") as f:
        data = f.read()

    if len(data) < MAGIC_SIZE:
        raise ValueError(f"Файл слишком мал: {len(data)} байт")

    sig = data[:MAGIC_SIZE]
    if sig not in (SIGNATURE_DECRYPTED, SIGNATURE_ENCRYPTED):
        raise ValueError(
            f"Неверная сигнатура файла: {sig!r}. "
            f"Ожидается {SIGNATURE_DECRYPTED!r} или {SIGNATURE_ENCRYPTED!r}"
        )
    encrypted = sig.startswith(b"MajiroObjX")

    pos = MAGIC_SIZE
    main_offset, line_count, func_count = struct.unpack_from("<III", data, pos)
    pos += 12

    functions: List[MjoFunction] = []
    for _ in range(func_count):
        h, off = struct.unpack_from("<II", data, pos)
        functions.append(MjoFunction(hash=h, offset=off))
        pos += 8

    (bytecode_size,) = struct.unpack_from("<I", data, pos)
    pos += 4

    if pos + bytecode_size > len(data):
        raise ValueError(
            f"Заявленный размер байткода ({bytecode_size}) превышает "
            f"размер оставшихся данных ({len(data) - pos})"
        )

    bytecode = bytearray(data[pos:pos + bytecode_size])
    if encrypted:
        xor_crypt(bytecode, key_offset=0)

    return MjoFile(
        signature=sig,
        main_offset=main_offset,
        line_count=line_count,
        functions=functions,
        bytecode_size=bytecode_size,
        bytecode=bytecode,
        encrypted=encrypted,
    )


# ============================================================================
# ДИЗАССЕМБЛЕР
# ============================================================================


class _Reader:
    def __init__(self, data: bytes | bytearray):
        self.data = bytes(data)
        self.pos = 0

    def read(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError("Неожиданный конец байткода")
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def u8(self) -> int:
        return self.read(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.read(2))[0]

    def i16(self) -> int:
        return struct.unpack("<h", self.read(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.read(4))[0]


def disassemble(mjo: MjoFile) -> List[Instruction]:
    """Дизассемблирует байткод в список инструкций."""
    r = _Reader(mjo.bytecode)
    instructions: List[Instruction] = []
    end = len(mjo.bytecode)

    while r.pos < end:
        start = r.pos
        opcode = r.u16()

        info = OPCODE_TABLE.get(opcode)
        if info is None:
            raise ValueError(
                f"Неизвестный опкод 0x{opcode:04X} по смещению 0x{start:08X}"
            )

        operands: list = []
        kind = info.operand_kind

        if kind == "":
            pass
        elif kind == "int32":
            operands.append(r.i32())
        elif kind == "float32":
            v = r.f32()
            # Сохраняем как hex float (детерминированно)
            operands.append(struct.unpack("<I", struct.pack("<f", v))[0])
            operands[-1] = ("f32", v)  # type: ignore
        elif kind == "string":
            slen = r.u16()
            sdata = r.read(slen)
            # Отбрасываем завершающий '\0', если он есть
            s = sjis_decode(sdata)
            if s.endswith("\0"):
                s = s[:-1]
            operands.append(s)
        elif kind == "field":
            flags = r.u16()
            h = r.u32()
            off = r.i16()
            operands.append(("field", flags, h, off))
        elif kind == "call":
            h = r.u32()
            placeholder = r.i32()
            argc = r.u16()
            operands.append(("call", h, placeholder, argc))
        elif kind == "syscall":
            h = r.u32()
            argc = r.u16()
            operands.append(("syscall", h, argc))
        elif kind == "typelist":
            n = r.u16()
            types = [r.u8() for _ in range(n)]
            operands.append(("typelist", types))
        elif kind == "case":
            n = r.u16()
            # case[n] хранит ОТНОСИТЕЛЬНОЕ смещение; абсолютное = case + OperandOffset + 2 + (n+1)*4
            case_data_pos = r.pos
            base = case_data_pos + 4 * n
            cases = []
            for _ in range(n):
                rel = r.i32()
                cases.append(rel + base)
            operands.append(("case", cases))
        elif kind == "jump":
            rel = r.i32()
            target = rel + r.pos  # абсолютное смещение
            operands.append(target)
        elif kind == "lineno":
            operands.append(r.u16())
        else:
            raise ValueError(f"Неизвестный тип операнда: {kind!r}")

        instr_bytes = bytes(mjo.bytecode[start:r.pos])
        instructions.append(Instruction(
            offset=start,
            opcode=opcode,
            mnemonic=info.name,
            operands=operands,
            raw_bytes=instr_bytes,
        ))

    return instructions


# ============================================================================
# АССЕМБЛЕР (обратная операция)
# ============================================================================


def _encode_operands(opcode: int, operands: list, current_offset: int = 0) -> bytes:
    """Кодирует список операндов в байты для данного опкода.

    current_offset -- позиция опкода в финальном байткоде (нужна для jump/case
    относительных смещений, чтобы они ссылались на абсолютные смещения).
    """
    info = OPCODE_TABLE[opcode]
    kind = info.operand_kind
    buf = io.BytesIO()

    if kind == "":
        if operands:
            raise ValueError(
                f"Опкод 0x{opcode:04X} ({info.name}) не имеет операндов, "
                f"но передано: {operands!r}"
            )
    elif kind == "int32":
        if len(operands) != 1:
            raise ValueError(f"{info.name}: ожидается 1 операнд int32")
        buf.write(struct.pack("<i", int(operands[0])))
    elif kind == "float32":
        if len(operands) != 1:
            raise ValueError(f"{info.name}: ожидается 1 операнд float32")
        if isinstance(operands[0], tuple) and operands[0][0] == "f32":
            v = operands[0][1]
        else:
            v = float(operands[0])
        buf.write(struct.pack("<f", v))
    elif kind == "string":
        if len(operands) != 1:
            raise ValueError(f"{info.name}: ожидается 1 строковый операнд")
        s = operands[0]
        if not isinstance(s, str):
            raise ValueError(f"{info.name}: строковый операнд должен быть str")
        enc = sjis_encode(s + "\0")
        buf.write(struct.pack("<H", len(enc)))
        buf.write(enc)
    elif kind == "field":
        if len(operands) != 1 or not (isinstance(operands[0], tuple)
                                       and operands[0][0] == "field"):
            raise ValueError(f"{info.name}: ожидается ('field', flags, hash, offset)")
        _, flags, h, off = operands[0]
        buf.write(struct.pack("<HIh", int(flags), int(h) & 0xFFFFFFFF, int(off)))
    elif kind == "call":
        if len(operands) != 1 or not (isinstance(operands[0], tuple)
                                       and operands[0][0] == "call"):
            raise ValueError(f"{info.name}: ожидается ('call', hash, placeholder, argc)")
        _, h, ph, argc = operands[0]
        buf.write(struct.pack("<IiH", int(h) & 0xFFFFFFFF, int(ph), int(argc)))
    elif kind == "syscall":
        if len(operands) != 1 or not (isinstance(operands[0], tuple)
                                       and operands[0][0] == "syscall"):
            raise ValueError(f"{info.name}: ожидается ('syscall', hash, argc)")
        _, h, argc = operands[0]
        buf.write(struct.pack("<IH", int(h) & 0xFFFFFFFF, int(argc)))
    elif kind == "typelist":
        if len(operands) != 1 or not (isinstance(operands[0], tuple)
                                       and operands[0][0] == "typelist"):
            raise ValueError(f"{info.name}: ожидается ('typelist', [types])")
        _, types = operands[0]
        buf.write(struct.pack("<H", len(types)))
        for t in types:
            buf.write(struct.pack("<B", int(t) & 0xFF))
    elif kind == "case":
        if len(operands) != 1 or not (isinstance(operands[0], tuple)
                                       and operands[0][0] == "case"):
            raise ValueError(f"{info.name}: ожидается ('case', [targets])")
        _, targets = operands[0]
        buf.write(struct.pack("<H", len(targets)))
        # Абсолютная позиция в финальном байткоде, с которой начнутся int32 смещения:
        # current_offset + 2 (опкод) + 2 (N) + 4*N (предыдущие смещения) = позиция первого смещения
        # но база для каждого смещения = позиция ПОСЛЕ всего списка смещений
        # Формула: rel = target - (current_offset + 2 (опкод) + 2 (N) + 4*N)
        base = current_offset + 2 + 2 + 4 * len(targets)
        for t in targets:
            rel = int(t) - base
            buf.write(struct.pack("<i", rel))
    elif kind == "jump":
        if len(operands) != 1:
            raise ValueError(f"{info.name}: ожидается 1 целевое смещение")
        target = int(operands[0])
        # Абсолютная позиция в финальном байткоде, в которой будет расположен этот int32,
        # и позиция ПОСЛЕ него:
        #   rel_pos = current_offset + 2 (опкод) -- в финальном байткоде
        #   rel = target - (rel_pos + 4) = target - (current_offset + 6)
        rel = target - (current_offset + 6)
        buf.write(struct.pack("<i", rel))
    elif kind == "lineno":
        if len(operands) != 1:
            raise ValueError(f"{info.name}: ожидается номер строки")
        buf.write(struct.pack("<H", int(operands[0])))
    else:
        raise ValueError(f"Неизвестный тип операнда: {kind!r}")

    return buf.getvalue()


def assemble_bytecode(instructions: List[Instruction]) -> bytes:
    """Собирает список инструкций в бинарный байткод.

    Предполагается, что инструкции уже отсортированы по offset и
    их смещения соответствуют их позициям в финальном байткоде.
    """
    parts: list[bytes] = []
    for instr in instructions:
        parts.append(struct.pack("<H", instr.opcode))
        parts.append(_encode_operands(instr.opcode, instr.operands, instr.offset))
    return b"".join(parts)


# ============================================================================
# ФОРМАТ ТЕКСТОВОГО ПРЕДСТАВЛЕНИЯ (.TXT)
# ============================================================================
#
# Формат (построчно):
#   ; Majiro Disassembly                          <- заголовок
#   ; signature = MajiroObjX1.000                <- сигнатура
#   ; main_offset = 0
#   ; line_count = 4168
#   ; function_count = 1
#   ; functions:                                 <- таблица функций
#   ;   func hash=0x1D128F30 offset=0
#   ; bytecode_size = 159059
#   ; encrypted = yes
#   [header end]                                 <- разделитель секций
#   [FUNC hash offset]                           <- декларация функции
#   [offset] opcode=mnemonic args...             <- инструкция
#   ...
#
# Аргументы:
#   int32    : 123
#   float32  : float:1.5  (или  hex:0x3FC00000)
#   string   : "text..."  (с экранированием \ и ")
#   field    : field(flags=0, hash=0x..., offset=0)
#   call     : call(hash=0x..., placeholder=0, argc=0)
#   syscall  : syscall(hash=0x..., argc=0)
#   typelist : typelist(t1,t2,...)
#   case     : case(t1,t2,...)
#   jump     : целое (абсолютное смещение)
#   lineno   : 123


def render_operand(op) -> str:
    if isinstance(op, str):
        esc = op.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{esc}"'
    if isinstance(op, tuple):
        tag = op[0]
        if tag == "f32":
            _, v = op
            # Сначала пытаемся «красиво», иначе hex
            return f"float:{v}"
        if tag == "field":
            _, flags, h, off = op
            return f"field(flags=0x{flags:04X}, hash=0x{h:08X}, offset={off})"
        if tag == "call":
            _, h, ph, argc = op
            return f"call(hash=0x{h:08X}, placeholder={ph}, argc={argc})"
        if tag == "syscall":
            _, h, argc = op
            return f"syscall(hash=0x{h:08X}, argc={argc})"
        if tag == "typelist":
            _, types = op
            return "typelist(" + ",".join(str(t) for t in types) + ")"
        if tag == "case":
            _, targets = op
            return "case(" + ",".join(str(t) for t in targets) + ")"
    return str(op)


def mjo_to_text(mjo: MjoFile) -> str:
    """Преобразует распарсенный .mjo в текстовое представление."""
    lines: list[str] = []
    lines.append("; Majiro Disassembly")
    # Обрезаем завершающий '\0' для красоты
    sig = mjo.signature.rstrip(b"\x00").decode("ascii", errors="replace")
    lines.append(f"; signature = {sig}")
    lines.append(f"; main_offset = {mjo.main_offset}")
    lines.append(f"; line_count = {mjo.line_count}")
    lines.append(f"; function_count = {len(mjo.functions)}")
    lines.append("; functions:")
    for i, fn in enumerate(mjo.functions):
        lines.append(f";   func[{i}] hash=0x{fn.hash:08X} offset={fn.offset}")
    lines.append(f"; bytecode_size = {mjo.bytecode_size}")
    lines.append(f"; encrypted = {'yes' if mjo.is_encrypted else 'no'}")
    lines.append("; ===END HEADER===")

    instrs = disassemble(mjo)
    for instr in instrs:
        op_str = " ".join(render_operand(o) for o in instr.operands)
        if op_str:
            lines.append(f"0x{instr.offset:08X} {instr.mnemonic} {op_str}")
        else:
            lines.append(f"0x{instr.offset:08X} {instr.mnemonic}")

    return "\n".join(lines) + "\n"


# ============================================================================
# ПАРСЕР ТЕКСТОВОГО ПРЕДСТАВЛЕНИЯ (.TXT)
# ============================================================================


_HEX_PREFIX = ("0x", "0X", "$")


def _strip_name(s: str) -> str:
    """Отрезает префикс name= если он есть."""
    s = s.strip()
    if "=" in s:
        return s.split("=", 1)[1].strip()
    return s


def _parse_int(s: str) -> int:
    s = s.strip()
    if s.startswith(_HEX_PREFIX):
        return int(s[2:] if s[1] in "xX" else s[1:], 16)
    return int(s)


def _parse_string_literal(s: str) -> str:
    """Парсит строковой литерал в кавычках с экранированием \\ и \"."""
    s = s.strip()
    if len(s) < 2 or s[0] != '"' or s[-1] != '"':
        raise ValueError(f"Ожидается строковой литерал в кавычках: {s!r}")
    body = s[1:-1]
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            elif nxt == "0":
                out.append("\0")
            elif nxt == "\\":
                out.append("\\")
            elif nxt == '"':
                out.append('"')
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _parse_tuple(s: str) -> Tuple[str, list]:
    """Парсит конструкцию name(a,b,c) в (name, [args])."""
    s = s.strip()
    if "(" not in s or not s.endswith(")"):
        raise ValueError(f"Ожидается конструкция name(...): {s!r}")
    name, rest = s.split("(", 1)
    name = name.strip()
    body = rest[:-1]  # отрезаем ')'
    # Разделяем по запятой на верхнем уровне
    args: list[str] = []
    depth = 0
    cur = []
    for ch in body:
        if ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            cur.append(ch)
    if cur:
        args.append("".join(cur).strip())
    return name, args


def _parse_operands(opcode: int, args: list[str]) -> list:
    """Парсит список строк-аргументов в нормализованные операнды."""
    info = OPCODE_TABLE[opcode]
    kind = info.operand_kind

    if kind == "":
        if args:
            raise ValueError(
                f"{info.name}: неожиданные аргументы: {args!r}"
            )
        return []

    if kind == "int32":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается 1 аргумент int32")
        return [_parse_int(args[0])]

    if kind == "float32":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается 1 аргумент float32")
        s = args[0].strip()
        if s.startswith("float:"):
            v = float(s[6:])
        elif s.startswith("hex:") or s.startswith("0x") or s.startswith("0X") or s.startswith("$"):
            v = struct.unpack("<f", struct.pack("<I", _parse_int(s)))[0]
        else:
            v = float(s)
        return [("f32", v)]

    if kind == "string":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается 1 строковой аргумент")
        return [_parse_string_literal(args[0])]

    if kind == "field":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается field(...)")
        name, sub = _parse_tuple(args[0])
        if name != "field" or len(sub) != 3:
            raise ValueError(f"{info.name}: ожидается field(flags,hash,offset)")
        return [("field", _parse_int(_strip_name(sub[0])), _parse_int(_strip_name(sub[1])), _parse_int(_strip_name(sub[2])))]

    if kind == "call":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается call(...)")
        name, sub = _parse_tuple(args[0])
        if name != "call" or len(sub) != 3:
            raise ValueError(f"{info.name}: ожидается call(hash,placeholder,argc)")
        return [("call", _parse_int(_strip_name(sub[0])), _parse_int(_strip_name(sub[1])), _parse_int(_strip_name(sub[2])))]

    if kind == "syscall":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается syscall(...)")
        name, sub = _parse_tuple(args[0])
        if name != "syscall" or len(sub) != 2:
            raise ValueError(f"{info.name}: ожидается syscall(hash,argc)")
        return [("syscall", _parse_int(_strip_name(sub[0])), _parse_int(_strip_name(sub[1])))]

    if kind == "typelist":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается typelist(...)")
        name, sub = _parse_tuple(args[0])
        if name != "typelist":
            raise ValueError(f"{info.name}: ожидается typelist(...)")
        return [("typelist", [_parse_int(x) for x in sub])]

    if kind == "case":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается case(...)")
        name, sub = _parse_tuple(args[0])
        if name != "case":
            raise ValueError(f"{info.name}: ожидается case(...)")
        return [("case", [_parse_int(x) for x in sub])]

    if kind == "jump":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается 1 целевое смещение")
        return [_parse_int(args[0])]

    if kind == "lineno":
        if len(args) != 1:
            raise ValueError(f"{info.name}: ожидается номер строки")
        return [_parse_int(args[0])]

    raise ValueError(f"Неизвестный тип операнда: {kind!r}")


# Строим обратное отображение мнемоника -> опкод для дизассемблера
_MNEMONIC_TO_OPCODE: dict[str, int] = {
    info.name: op for op, info in OPCODE_TABLE.items()
}


def _split_args(s: str) -> list[str]:
    """Разделяет строку аргументов на отдельные аргументы с учётом кавычек и скобок."""
    args = []
    cur = []
    depth = 0
    in_str = False
    esc = False
    for ch in s:
        if esc:
            cur.append(ch)
            esc = False
            continue
        if ch == "\\" and in_str:
            cur.append(ch)
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            cur.append(ch)
            continue
        if not in_str:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch.isspace() and depth == 0:
                if cur:
                    args.append("".join(cur))
                    cur = []
                continue
        cur.append(ch)
    if cur:
        args.append("".join(cur))
    return args


# ============================================================================
# СБОРКА .MJO ИЗ РАСПАРСЕННОГО ТЕКСТА
# ============================================================================


def build_mjo_from_text(text: str) -> MjoFile:
    """Парсит текст, ассемблирует байткод и возвращает MjoFile."""
    lines = text.splitlines()

    sig = SIGNATURE_ENCRYPTED
    main_offset = 0
    line_count = 0
    functions: List[MjoFunction] = []
    encrypted = True
    instructions: List[Instruction] = []

    i = 0
    in_header = True
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line:
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        if line.startswith(";"):
            if "===END HEADER===" in line:
                in_header = False
                continue
            if not in_header:
                continue
            low = line.lower()
            if "signature" in low and "=" in line:
                sig = line.split("=", 1)[1].strip().encode("ascii")
                # Дополняем сигнатуру до 16 байт (содержит завершающий \x00)
                if len(sig) < MAGIC_SIZE:
                    sig = sig + b"\x00" * (MAGIC_SIZE - len(sig))
            elif "main_offset" in low and "=" in line:
                main_offset = _parse_int(line.split("=", 1)[1])
            elif "line_count" in low and "=" in line:
                line_count = _parse_int(line.split("=", 1)[1])
            elif "encrypted" in low and "=" in line:
                v = line.split("=", 1)[1].strip().lower()
                encrypted = v in ("yes", "true", "1", "y")
            elif "func[" in low and "=" in line:
                head, rest = line.split("]", 1)
                idx = _parse_int(head.split("[", 1)[1])
                parts = rest.strip().split()
                h, off = 0, 0
                for p in parts:
                    if p.startswith("hash="):
                        h = _parse_int(p[5:])
                    elif p.startswith("offset="):
                        off = _parse_int(p[7:])
                if idx >= len(functions):
                    while len(functions) <= idx:
                        functions.append(MjoFunction(hash=0, offset=0))
                functions[idx] = MjoFunction(hash=h, offset=off)
            continue

        if in_header:
            in_header = False

        parts = line.split(None, 1)
        if not parts:
            continue
        head = parts[0].lower()
        if head == "func":
            if len(parts) < 2:
                continue
            fparts = parts[1].split()
            h = _parse_int(fparts[0])
            off = _parse_int(fparts[1])
            replaced = False
            for j, fn in enumerate(functions):
                if fn.offset == off:
                    functions[j] = MjoFunction(hash=h, offset=off)
                    replaced = True
                    break
            if not replaced:
                functions.append(MjoFunction(hash=h, offset=off))
            continue
        if head in ("endfunc", "end"):
            continue

        if len(parts) < 2:
            continue
        offset = _parse_int(parts[0])
        rest = parts[1]
        sub_parts = rest.split(None, 1)
        mnemonic = sub_parts[0]
        args_str = sub_parts[1] if len(sub_parts) > 1 else ""
        if mnemonic not in _MNEMONIC_TO_OPCODE:
            raise ValueError(f"Строка {i}: неизвестная мнемоника {mnemonic!r}")
        opcode = _MNEMONIC_TO_OPCODE[mnemonic]
        args = _split_args(args_str)
        operands = _parse_operands(opcode, args)
        body = struct.pack("<H", opcode) + _encode_operands(opcode, operands)
        instructions.append(Instruction(
            offset=offset,
            opcode=opcode,
            mnemonic=mnemonic,
            operands=operands,
            raw_bytes=body,
        ))

    # Сортируем инструкции по offset и ассемблируем
    instructions.sort(key=lambda i: i.offset)
    bytecode = assemble_bytecode(instructions)

    return MjoFile(
        signature=sig,
        main_offset=main_offset,
        line_count=line_count,
        functions=functions,
        bytecode_size=len(bytecode),
        bytecode=bytearray(bytecode),
        encrypted=encrypted,
    )


def write_mjo(path: str, mjo: MjoFile) -> None:
    """Записывает MjoFile в бинарный .mjo (с шифрованием при необходимости)."""
    with open(path, "wb") as f:
        f.write(mjo.signature)
        f.write(struct.pack("<III",
                            mjo.main_offset,
                            mjo.line_count,
                            len(mjo.functions)))
        for fn in mjo.functions:
            f.write(struct.pack("<II", fn.hash & 0xFFFFFFFF, fn.offset))
        f.write(struct.pack("<I", len(mjo.bytecode)))
        # Шифруем копию, не трогая исходный массив
        data = bytearray(mjo.bytecode)
        if mjo.is_encrypted:
            xor_crypt(data, key_offset=0)
        f.write(data)


# ============================================================================
# CLI
# ============================================================================


def _auto_out_path(in_path: str) -> str:
    root, ext = os.path.splitext(in_path)
    if ext.lower() == ".mjo":
        return root + ".txt"
    if ext.lower() == ".txt":
        return root + ".mjo"
    return in_path + ".out"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Двунаправленный конвертер Majiro .mjo ↔ .txt",
    )
    parser.add_argument("input", help="Входной файл (.mjo или .txt)")
    parser.add_argument("-o", "--output", help="Выходной файл (по умолчанию авто)")
    parser.add_argument(
        "--force-plain",
        action="store_true",
        help="При записи .mjo сохранять сигнатуру 'V' (без шифрования)",
    )
    parser.add_argument(
        "--force-encrypted",
        action="store_true",
        help="При записи .mjo сохранять сигнатуру 'X' (с шифрованием) [по умолчанию]",
    )
    args = parser.parse_args(argv)

    in_path = args.input
    out_path = args.output or _auto_out_path(in_path)
    in_ext = os.path.splitext(in_path)[1].lower()

    try:
        if in_ext == ".mjo":
            mjo = read_mjo(in_path)
            text = mjo_to_text(mjo)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"[OK] .mjo -> .txt: {in_path} -> {out_path}")
        elif in_ext == ".txt":
            with open(in_path, "r", encoding="utf-8") as f:
                text = f.read()
            mjo = build_mjo_from_text(text)
            if args.force_plain and mjo.is_encrypted:
                mjo.signature = SIGNATURE_DECRYPTED
            elif args.force_encrypted and not mjo.is_encrypted:
                mjo.signature = SIGNATURE_ENCRYPTED
            write_mjo(out_path, mjo)
            print(f"[OK] .txt -> .mjo: {in_path} -> {out_path} "
                  f"(encrypted={mjo.is_encrypted}, "
                  f"bytecode_size={mjo.bytecode_size})")
        else:
            print(f"[ERR] Неподдерживаемое расширение: {in_ext}", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"[ERR] {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
