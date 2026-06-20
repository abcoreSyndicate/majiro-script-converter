# Конвертер скриптов Majiro

[![Python](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-8%2F8%20passing-brightgreen.svg)]()

Двунаправленный конвертер файлов скриптов визуальных новелл на движке **Majiro** (`.mjo` ↔ `.txt`).

Majiro — это японский игровой движок для визуальных новелл. Его скомпилированные файлы скриптов используют собственный бинарный формат, который этот инструмент может дизассемблировать в читаемое текстовое представление и собрать обратно в побайтово идентичный бинарный файл. Это позволяет просматривать, переводить и модифицировать игровые скрипты.

## ✨ Возможности

- 🔄 **Двунаправленная конвертация** — `.mjo` → `.txt` и `.txt` → `.mjo` с побайтово идентичным roundtrip
- 🔐 **Поддержка XOR-шифрования** — работает как с зашифрованными (`MajiroObjX1.000`), так и с открытыми (`MajiroObjV1.000`) файлами
- 📦 **Нулевые зависимости** — только стандартная библиотека Python 3.7+
- 🧪 **Полностью протестировано** — 8 модульных и интеграционных тестов, покрывающих все основные сценарии
- 🌍 **Многоязычная документация** — README на английском, русском и японском языках

## 📥 Установка

```bash
git clone https://github.com/your-username/majiro-script-converter.git
cd majiro-script-converter
```

Внешних зависимостей не требуется — только Python 3.7 или новее.

## 🚀 Быстрый старт

### Командная строка

```bash
# Дизассемблирование .mjo -> .txt
python mjo_converter.py script.mjo -o script.txt

# Сборка .txt -> .mjo
python mjo_converter.py script.txt -o script.mjo

# Авто-определение по расширению
python mjo_converter.py script.mjo      # создаст script.txt
python mjo_converter.py script.txt      # создаст script.mjo

# Принудительно сохранить без шифрования
python mjo_converter.py script.txt -o script.mjo --force-plain
```

### Python-модуль

```python
from mjo_converter import read_mjo, mjo_to_text, build_mjo_from_text, write_mjo

# Чтение и дизассемблирование
mjo = read_mjo("script.mjo")
text = mjo_to_text(mjo)

# Изменение текста (например, перевод строки)
text = text.replace("Hello", "Привет")

# Сборка обратно
new_mjo = build_mjo_from_text(text)
write_mjo("script_ru.mjo", new_mjo)
```

## 📖 Документация

Выберите язык:

- 🇬🇧 **English** — [README.md](../README.md)
- 🇷🇺 **Русский** — [README.ru.md](README.ru.md) (этот файл)
- 🇯🇵 **日本語** — [README.ja.md](README.ja.md)

Подробная спецификация формата: [FORMAT.md](FORMAT.md)

## 🧪 Запуск тестов

```bash
python test_converter.py
```

Ожидаемый вывод:
```
[OK] test_xor_key
[OK] test_roundtrip_example (159099 байт совпадают)
[OK] test_switch_encoding
[OK] test_br_encoding
[OK] test_full_encryption_cycle (bytecode 159059 байт)
[OK] test_minimal_mjo (58 байт, 18 байткода)
[OK] test_force_plain
[OK] test_text_modification (заменено 3 вхождений)
Все 8 тестов прошли успешно!
```

## 📂 Структура проекта

```
majiro-script-converter/
├── mjo_converter.py       # Основной модуль конвертера + CLI
├── test_converter.py      # Набор тестов (8 тестов)
├── README.md              # Главный файл (английский)
├── LICENSE                # Лицензия MIT
├── .gitignore             # Правила игнорирования Git
├── docs/
│   ├── README.ru.md       # Документация на русском
│   ├── README.ja.md       # Документация на японском
│   └── FORMAT.md          # Спецификация бинарного формата
└── examples/
    └── sample.txt         # Пример дизассемблированного вывода
```

## 🛠️ Технические детали

### Формат файла (.mjo)

```
Смещение  Размер  Описание
0         16      Сигнатура: "MajiroObjV1.000\0" (расшифрован) или "MajiroObjX1.000\0" (зашифрован)
16        4       uint32  main_offset      - смещение функции $main в байткоде
20        4       uint32  line_count       - количество строк в исходнике
24        4       uint32  function_count   - количество функций
28        8×N     Функции: (uint32 hash, uint32 offset) для каждой
?         4       uint32  bytecode_size    - размер байткода
?         N       byte[]  bytecode         - зашифрованный или открытый байткод
```

### Шифрование

Байткод шифруется XOR'ом с 1024-байтным ключом, который является побайтовым представлением (little-endian) стандартной CRC32-таблицы (полином `0xEDB88320`). Шифр обратим — двойное применение возвращает исходные данные.

### Текстовый формат (.txt)

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

Все смещения в hex с префиксом `0x`. Строки в кавычках с экранированием через `\`. Ассемблер автоматически вычисляет относительные смещения для инструкций перехода.

## 🤝 Участие в разработке

Мы приветствуем вклад в проект! Пожалуйста:

1. Сделайте форк репозитория
2. Создайте ветку для новой функции (`git checkout -b feature/my-change`)
3. Внесите изменения и добавьте тесты
4. Убедитесь, что все тесты проходят (`python test_converter.py`)
5. Отправьте Pull Request

## 📜 Лицензия

Проект распространяется под лицензией MIT — подробности в файле [LICENSE](../LICENSE).

## ⚠️ Отказ от ответственности

Этот инструмент предназначен для образовательных целей, проектов перевода и модификации легально полученных копий игр. Пожалуйста, уважайте права правообладателей и условия использования игр, с которыми вы работаете.

## 🙏 Благодарности

- **Автор**: abral syndicate
- **Исследование формата**: На основе реверс-инжиниринга набора инструкций IL движка Majiro
- **Референсные реализации**: `MajiroTools` от AtomCrafty (C#) и `majiro-py` от trigger-segfault (Python)

## 🌐 Языки

- [English](../README.md)
- [Русский](README.ru.md)
- [日本語](README.ja.md)
