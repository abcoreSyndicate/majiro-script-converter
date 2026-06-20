# Majiro スクリプト変換ツール

[![Python](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-8%2F8%20passing-brightgreen.svg)]()

**Majiroエンジン**のビジュアルノベル・スクリプトファイル(`.mjo` ↔ `.txt`)を双方向変換するツールです。

Majiroは日本のビジュアルノベルゲームエンジンです。コンパイルされたスクリプトファイルは独自のバイナリ形式を使用しており、このツールはそれを読可能なテキスト表現に逆アセンブルし、バイト単位で同一のバイナリファイルに再アセンブルすることができます。これにより、ゲームスクリプトの閲覧、翻訳、修正が可能になります。

## ✨ 特徴

- 🔄 **双方向変換** — `.mjo` → `.txt` および `.txt` → `.mjo` をバイト単位で同一のラウンドトリップで実現
- 🔐 **XOR暗号サポート** — 暗号化版(`MajiroObjX1.000`)と非暗号化版(`MajiroObjV1.000`)の両方に対応
- 📦 **ゼロ依存** — Python 3.7+の標準ライブラリのみ
- 🧪 **完全なテスト** — すべての主要なコードパスをカバーする8つの単体・結合テスト
- 🌍 **多言語ドキュメント** — 英語、ロシア語、日本語のREADMEを提供

## 📥 インストール

```bash
git clone https://github.com/your-username/majiro-script-converter.git
cd majiro-script-converter
```

外部依存関係は不要です — Python 3.7以上のみ必要です。

## 🚀 クイックスタート

### コマンドライン

```bash
# .mjo -> .txt への逆アセンブル
python mjo_converter.py script.mjo -o script.txt

# .txt -> .mjo へのアセンブル
python mjo_converter.py script.txt -o script.mjo

# 拡張子による自動判定
python mjo_converter.py script.mjo      # script.txt を作成
python mjo_converter.py script.txt      # script.mjo を作成

# 強制的に非暗号化で保存
python mjo_converter.py script.txt -o script.mjo --force-plain
```

### Pythonモジュールとして使用

```python
from mjo_converter import read_mjo, mjo_to_text, build_mjo_from_text, write_mjo

# 読み込みと逆アセンブル
mjo = read_mjo("script.mjo")
text = mjo_to_text(mjo)

# テキストを修正(例: 翻訳)
text = text.replace("Hello", "こんにちは")

# 再アセンブル
new_mjo = build_mjo_from_text(text)
write_mjo("script_ja.mjo", new_mjo)
```

## 📖 ドキュメント

言語を選択してください:

- 🇬🇧 **English** — [README.md](../README.md)
- 🇷🇺 **Русский** — [README.ru.md](README.ru.md)
- 🇯🇵 **日本語** — [README.ja.md](README.ja.md) (このファイル)

詳細なフォーマット仕様: [FORMAT.md](FORMAT.md)

## 🧪 テストの実行

```bash
python test_converter.py
```

期待される出力:
```
[OK] test_xor_key
[OK] test_roundtrip_example (159099バイト一致)
[OK] test_switch_encoding
[OK] test_br_encoding
[OK] test_full_encryption_cycle (bytecode 159059バイト)
[OK] test_minimal_mjo (58バイト、18バイトコード)
[OK] test_force_plain
[OK] test_text_modification (3箇所を置換)
All 8 tests passed!
```

## 📂 プロジェクト構成

```
majiro-script-converter/
├── mjo_converter.py       # メイン変換モジュール + CLI
├── test_converter.py      # テストスイート(8テスト)
├── README.md              # メインファイル(英語)
├── LICENSE                # MITライセンス
├── .gitignore             # Gitの無視パターン
├── docs/
│   ├── README.ru.md       # ロシア語ドキュメント
│   ├── README.ja.md       # 日本語ドキュメント
│   └── FORMAT.md          # バイナリフォーマット仕様
└── examples/
    └── sample.txt         # 逆アセンブル出力の例
```

## 🛠️ 技術詳細

### ファイル形式 (.mjo)

```
オフセット  サイズ  説明
0           16     シグネチャ: "MajiroObjV1.000\0" (非暗号化) または "MajiroObjX1.000\0" (暗号化)
16          4      uint32  main_offset      - バイトコード内の$main関数のオフセット
20          4      uint32  line_count       - ソース行数
24          4      uint32  function_count   - 関数数
28          8×N    関数: (uint32 hash, uint32 offset) × 関数数
?           4      uint32  bytecode_size    - バイトコードサイズ(バイト単位)
?           N      byte[]  bytecode         - 暗号化または非暗号化のバイトコード
```

### 暗号化

バイトコードセクションは、標準的なCRC-32ルックアップテーブル(多項式 `0xEDB88320`)から派生した1024バイトのキーでXOR暗号化されています。キーはリトルエンディアンのuint32値としてエンコードされます。暗号は可逆的(2回適用すると元に戻る)です。

### テキスト形式 (.txt)

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

すべてのオフセットは`0x`プレフィックス付きの16進数です。文字列はバックスラッシュエスケープ付きの引用符で囲まれます。アセンブラは分岐命令の相対オフセットを自動的に計算します。

## 🤝 貢献

貢献を歓迎します!以下の手順でお願いします:

1. リポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/my-change`)
3. 変更を加えてテストを追加
4. すべてのテストが通ることを確認 (`python test_converter.py`)
5. プルリクエストを送信

## 📜 ライセンス

このプロジェクトはMITライセンスの下でライセンスされています — 詳細は[LICENSE](../LICENSE)ファイルを参照してください。

## ⚠️ 免責事項

このツールは、教育目的、翻訳プロジェクト、正当に取得したゲームコピーの modding を意図しています。著作権者の権利と、ゲームの利用規約を尊重してください。

## 🙏 クレジット

- **作者**: abral syndicate
- **フォーマット研究**: MajiroエンジンのIL命令セットのリバースエンジニアリングに基づく
- **参考実装**: AtomCraftyの`MajiroTools`(C#)およびtrigger-segfaultの`majiro-py`(Python)

## 🌐 言語

- [English](../README.md)
- [Русский](README.ru.md)
- [日本語](README.ja.md)
