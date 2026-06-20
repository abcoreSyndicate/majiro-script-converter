# Contributing to Majiro Script Converter

Thank you for your interest in contributing! 🎉

## Code of Conduct

Be respectful and constructive. We welcome contributors of all skill levels.

## How to Contribute

### Reporting Bugs

1. Check existing [issues](../../issues) to avoid duplicates
2. Use the bug report template
3. Include:
   - Python version (`python --version`)
   - Operating system
   - Minimal reproduction steps
   - Expected vs actual behavior
   - Sample `.mjo` or `.txt` file (if possible)

### Suggesting Features

Open an issue with the `enhancement` label. Describe:
- The problem the feature would solve
- Proposed solution
- Any alternative approaches considered

### Submitting Pull Requests

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/my-change`
3. **Make your changes**:
   - Write clear, documented code
   - Follow PEP 8 style guidelines
   - Add tests for new functionality
   - Update documentation if needed
4. **Verify tests pass**: `python test_converter.py`
5. **Commit**: `git commit -m "Add: clear description of change"`
6. **Push**: `git push origin feature/my-change`
7. **Open a Pull Request**

## Development Setup

```bash
git clone https://github.com/your-username/majiro-script-converter.git
cd majiro-script-converter
# No installation needed — pure Python
python test_converter.py  # run tests
```

## Coding Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints where reasonable
- Write docstrings for public functions (English preferred, but Russian/Japanese accepted)
- Keep functions focused and small
- Add comments only where the code is not self-explanatory

## Adding New Opcodes

To add support for a new Majiro IL opcode:

1. Identify the opcode hex value and instruction name
2. Determine operand types (`.i`, `.r`, `.s`, `.iarr`, etc.)
3. Add an entry to `OPCODE_TABLE` in `mjo_converter.py`
4. If the instruction uses relative jump offsets, add a special case in
   `_encode_operands` and the disassembly logic
5. Add a test case in `test_converter.py`

Example:

```python
("newop.i", 0x999, [OpcodeOperand("i")], []),
("newop.s", 0x99A, [OpcodeOperand("s")], []),
```

## Testing

All contributions must pass the existing test suite:

```bash
python test_converter.py
```

When adding new functionality, please add corresponding tests.

## Documentation

- Update `README.md` (English) for user-facing changes
- Update `docs/README.ru.md` and `docs/README.ja.md` if possible
- Update `docs/FORMAT.md` for format-related changes
- Add an entry to `CHANGELOG.md` under "Unreleased"

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
