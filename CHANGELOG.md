# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-20

### Added
- Initial release
- Bidirectional conversion between `.mjo` (binary) and `.txt` (text) formats
- Support for both encrypted (`MajiroObjX1.000`) and plain (`MajiroObjV1.000`) signatures
- XOR cipher with 1024-byte key derived from CRC-32 lookup table
- Full instruction set support (100+ Majiro IL opcodes)
- Command-line interface with auto-detection by file extension
- Python module API for programmatic access
- 8 unit and integration tests covering:
  - XOR key correctness
  - Byte-identical roundtrip on real example
  - `switch`/`case` instruction encoding/decoding
  - `br` instruction relative offset calculation
  - Full encryption cycle on real bytecode
  - Minimal `.mjo` roundtrip
  - Force-plain output mode
  - Text modification and reassembly
- Comprehensive documentation in three languages:
  - English (`README.md`)
  - Russian (`docs/README.ru.md`)
  - Japanese (`docs/README.ja.md`)
- Binary format specification (`docs/FORMAT.md`)
- MIT License
- `.gitignore` for Python projects
- `setup.py` for PyPI distribution
- Example disassembled output (`examples/sample.txt`)

### Technical Notes
- Pure Python 3.7+ standard library only — zero external dependencies
- Byte-identical roundtrip verified on real Majiro engine scripts
- Handles edge cases: empty bytecode, single function, switch/case, branch targets
