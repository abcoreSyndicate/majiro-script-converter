# Majiro Script Converter

[![Python](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-8%2F8%20passing-brightgreen.svg)]()

A bidirectional converter for **Majiro engine** visual novel script files (`.mjo` ↔ `.txt`).

The Majiro engine is a Japanese visual novel game engine. Its compiled script files use a custom binary format that this tool can disassemble into a readable text representation and assemble back into a byte-identical binary file. This enables inspection, translation, and modification of game scripts.

## ✨ Features

- 🔄 **Bidirectional conversion** — `.mjo` → `.txt` and `.txt` → `.mjo` with byte-identical roundtrip
- 🔐 **XOR cipher support** — handles both encrypted (`MajiroObjX1.000`) and plain (`MajiroObjV1.000`) variants
- 📦 **Zero dependencies** — pure Python 3.7+ standard library only
- 🧪 **Fully tested** — 8 unit and integration tests covering all major code paths
- 🌍 **Multilingual docs** — README available in English, Russian, and Japanese

## 📥 Installation

```bash
git clone https://github.com/your-username/majiro-script-converter.git
cd majiro-script-converter
```

No external dependencies required — only Python 3.7 or later.

## 🚀 Quick Start

### Command Line

```bash
# Disassemble .mjo -> .txt
python mjo_converter.py script.mjo -o script.txt

# Assemble .txt -> .mjo
python mjo_converter.py script.txt -o script.mjo

# Auto-detect by extension
python mjo_converter.py script.mjo      # creates script.txt
python mjo_converter.py script.txt      # creates script.mjo

# Force plain (unencrypted) output
python mjo_converter.py script.txt -o script.mjo --force-plain
```

### Python Module

```python
from mjo_converter import read_mjo, mjo_to_text, build_mjo_from_text, write_mjo

# Read and disassemble
mjo = read_mjo("script.mjo")
text = mjo_to_text(mjo)

# Modify the text (e.g., translate a string)
text = text.replace("Hello", "こんにちは")

# Reassemble
new_mjo = build_mjo_from_text(text)
write_mjo("script_ja.mjo", new_mjo)
```

## 📖 Documentation

Choose your language:

- 🇬🇧 **English** — [README.md](README.md) (this file)
- 🇷🇺 **Русский** — [docs/README.ru.md](docs/README.ru.md)
- 🇯🇵 **日本語** — [docs/README.ja.md](docs/README.ja.md)

Detailed format specification: [docs/FORMAT.md](docs/FORMAT.md)

## 🧪 Running Tests

```bash
python test_converter.py
```

Expected output:
```
[OK] test_xor_key
[OK] test_roundtrip_example (159099 bytes match)
[OK] test_switch_encoding
[OK] test_br_encoding
[OK] test_full_encryption_cycle (bytecode 159059 bytes)
[OK] test_minimal_mjo (58 bytes, 18 bytecode)
[OK] test_force_plain
[OK] test_text_modification (replaced 3 occurrences)
All 8 tests passed!
```

## 📂 Project Structure

```
majiro-script-converter/
├── mjo_converter.py       # Main converter module + CLI
├── test_converter.py      # Test suite (8 tests)
├── README.md              # This file (English)
├── LICENSE                # MIT License
├── .gitignore             # Git ignore patterns
├── docs/
│   ├── README.ru.md       # Russian documentation
│   ├── README.ja.md       # Japanese documentation
│   └── FORMAT.md          # Binary format specification
└── examples/
    └── sample.txt         # Example disassembled output
```

## 🛠️ Technical Details

### File Format (.mjo)

```
Offset  Size    Description
0       16      Signature: "MajiroObjV1.000\0" (plain) or "MajiroObjX1.000\0" (encrypted)
16      4       uint32  main_offset      - offset of $main function in bytecode
20      4       uint32  line_count       - number of source lines
24      4       uint32  function_count   - number of functions
28      8×N     Functions: (uint32 hash, uint32 offset) for each function
?       4       uint32  bytecode_size    - size of bytecode in bytes
?       N       byte[]  bytecode         - encrypted or plain bytecode
```

### Encryption

The bytecode section is XOR-encrypted with a 1024-byte key derived from the standard CRC-32 lookup table (polynomial `0xEDB88320`), encoded as little-endian uint32 values. The cipher is reciprocal (XOR applied twice returns the original).

### Text Format (.txt)

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

All offsets use the `0x` hex prefix. Strings are quoted with backslash escaping. The assembler automatically calculates relative jump offsets for branch instructions.

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-change`)
3. Make your changes and add tests
4. Ensure all tests pass (`python test_converter.py`)
5. Submit a pull request

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is intended for educational purposes, translation projects, and modding of legally obtained game copies. Please respect the rights of copyright holders and the terms of service of the games you are working with.

## 🙏 Credits

- **Author**: abral syndicate
- **Format research**: Based on reverse-engineering of the Majiro engine IL instruction set
- **Reference implementations**: AtomCrafty's `MajiroTools` (C#) and trigger-segfault's `majiro-py` (Python)

## 🌐 Languages

- [English](README.md)
- [Русский](docs/README.ru.md)
- [日本語](docs/README.ja.md)
