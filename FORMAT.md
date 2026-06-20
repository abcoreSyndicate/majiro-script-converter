# Majiro .mjo Binary Format Specification

This document describes the binary format of `.mjo` script files used by the Majiro visual novel engine.

## File Layout

```
+---------------------------+
| Header (16 bytes)         |  Magic signature
+---------------------------+
| MainOffset   (uint32 LE)  |  Offset of $main function in bytecode
+---------------------------+
| LineCount    (uint32 LE)  |  Number of source lines in original script
+---------------------------+
| FunctionCount(uint32 LE)  |  Number of functions
+---------------------------+
| Function[0]               |  (Hash uint32 LE, Offset uint32 LE)
| Function[1]               |
| ...                       |
| Function[N-1]             |
+---------------------------+
| BytecodeSize  (uint32 LE) |  Size of bytecode in bytes
+---------------------------+
| Bytecode[...]             |  Encrypted or plain bytecode
+---------------------------+
```

All multi-byte integers are stored in **little-endian** byte order.

## Header Signature

The first 16 bytes are a fixed signature:

| Signature              | Meaning                                |
|------------------------|----------------------------------------|
| `MajiroObjV1.000\0`    | **Plain / decrypted** bytecode         |
| `MajiroObjX1.000\0`    | **Encrypted** bytecode (XOR cipher)    |

The `V`/`X` character distinguishes plain from encrypted variants. The trailing `\0` byte is part of the signature (16 bytes total).

## Function Table

Each function is described by two `uint32` values:

- **Hash**: CRC32 hash of the function name. Used as a lookup key.
- **Offset**: Byte offset of the function's first instruction in the bytecode.

Functions are sorted by offset in ascending order. The first function is typically `$main`, but not guaranteed.

## Bytecode

The bytecode is a stream of instructions for the Majiro IL (Intermediate Language) virtual machine. Each instruction has:

- A 2-byte opcode
- Zero or more operands (variable size)

### Operand Types

| Code | Type     | Description                              |
|------|----------|------------------------------------------|
| `.i` | int32    | 32-bit signed integer                    |
| `.r` | float64  | 64-bit IEEE 754 double                   |
| `.s` | string   | Length-prefixed (uint32 LE) UTF-8 string |
| `.iarr` | int[]  | Length-prefixed array of int32           |
| `.rarr` | float[]| Length-prefixed array of float64         |
| `.sarr` | string[] | Length-prefixed array of strings       |

### Branch and Call Instructions

Branch instructions (`br`, `br.case`, etc.) encode their target as a **relative offset** from the position immediately after the instruction. The assembler automatically computes these offsets from absolute addresses.

Call instructions reference functions by their CRC32 hash, not by name or offset.

## XOR Cipher (Encryption)

The bytecode section is XOR-encrypted using a 1024-byte key.

### Key Derivation

The key is the byte representation (little-endian) of the standard CRC-32 lookup table — 256 `uint32` values computed with polynomial `0xEDB88320`:

```python
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
key = b"".join(struct.pack("<I", v) for v in table)  # 1024 bytes
```

### Encryption

```python
for i in range(len(bytecode)):
    bytecode[i] ^= key[i % 1024]
```

The cipher is **reciprocal**: applying XOR twice returns the original data.

## Text Format (.txt)

The disassembled text representation has a header section followed by an instruction listing:

```
; Majiro Disassembly
; signature = MajiroObjX1.000
; main_offset = 0
; line_count = 4168
; function_count = 1
; functions:
;   func[0] hash=0x121D8F30 offset=0
; bytecode_size = 159059
; encrypted = yes
; ===END HEADER===

0x00000000 ldstr "BG01"
0x00000009 call hash=0xA4EB1E4C args=2
0x00000011 ldc.i 0
...
```

### Header Fields

| Field           | Description                              |
|-----------------|------------------------------------------|
| `signature`     | File signature (without trailing `\0`)   |
| `main_offset`   | Offset of `$main` function               |
| `line_count`    | Number of source lines                   |
| `function_count`| Number of functions                      |
| `func[N]`       | N-th function (hash and offset)          |
| `bytecode_size` | Size of bytecode section                 |
| `encrypted`     | `yes` if bytecode is XOR-encrypted       |

### Instruction Format

```
0xOFFSET MNEMONIC [OPERAND1] [OPERAND2] ...
```

- **OFFSET**: 8-character hex offset (e.g., `0x00000009`)
- **MNEMONIC**: instruction name (e.g., `ldstr`, `call`, `br`)
- **OPERAND**: one of:
  - Decimal integer: `42`, `-1`
  - Hex value: `0xDEADBEEF`
  - Float: `3.14`
  - Quoted string: `"hello\nworld"`
  - Key-value pair: `hash=0xA4EB1E4C args=2`

## References

- **MajiroTools** (C#): https://github.com/AtomCrafty/MajiroTools
- **majiro-py** (Python): https://github.com/trigger-segfault/majiro-py
