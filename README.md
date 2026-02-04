# 🐍 Recursive Python Type Checker

A lightweight, **zero-dependency** static analysis tool designed to enforce Python type hinting standards across your projects. 

It uses Python's built-in Abstract Syntax Tree (`ast`) to scan your code, ensuring that functions have proper argument and return type annotations.


## ✨ Features

- **Recursive Scanning:** Automatically detects `Pxx`, `exxx`, or any custom directories and scans deep into subfolders.
- **Zero Dependencies:** No `mypy`, `pylint`, or `pip install` required. Just standard Python.
- **AST Analysis:** fast and accurate checking without executing the code.
- **Smart Filtering:** Automatically ignores `.git`, `__pycache__`, `venv`, and other noise.
- **Coverage Metrics:** Calculates a return coverage score for your functions.
- **Beautiful Output:** Color-coded terminal output for easy reading.

## 🚀 Installation

Simply clone the repository. You don't need to install anything else.

```bash
git clone [https://github.com/Eliandjb/Typing-checker.git](https://github.com/Eliandjb/Typing-checker.git)
cd Typing-checker


C'est une excellente idée. Un bon README est ce qui fait la différence entre un "petit script" et un "vrai projet" sur GitHub. Puisque ton outil est maintenant récursif et adaptatif, on va le mettre en valeur.


Markdown

# 🐍 Recursive Python Type Checker

A lightweight, **zero-dependency** static analysis tool designed to enforce Python type hinting standards across your projects. 

It uses Python's built-in Abstract Syntax Tree (`ast`) to scan your code, ensuring that functions have proper argument and return type annotations.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.6+-yellow.svg)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)

## ✨ Features

- **Recursive Scanning:** Automatically detects `Pxx`, `exxx`, or any custom directories and scans deep into subfolders.
- **Zero Dependencies:** No `mypy`, `pylint`, or `pip install` required. Just standard Python.
- **AST Analysis:** fast and accurate checking without executing the code.
- **Smart Filtering:** Automatically ignores `.git`, `__pycache__`, `venv`, and other noise.
- **Coverage Metrics:** Calculates a return coverage score for your functions.
- **Beautiful Output:** Color-coded terminal output for easy reading.

## 🚀 Installation

Simply clone the repository. You don't need to install anything else.

```bash
git clone [https://github.com/Eliandjb/Typing-checker.git](https://github.com/Eliandjb/Typing-checker.git)
cd Typing-checker
🛠 Usage
Run the script from the root of your project (or anywhere else by pointing to the file).

1. Default Scan (Recursive)
Checks all Python files in the current directory and subdirectories (excluding hidden/ignored folders).

Bash

python3 typing_check.py
2. Targeted Scan
Check only specific directories (e.g., P05 or ex00).

Bash

python3 typing_check.py --target P05
Or multiple targets:

Bash

python3 typing_check.py --target P05 P06 utils
3. Verbose Mode
See exactly which functions are missing annotations.

Bash

python3 typing_check.py --verbose
📊 Example Output
Plaintext

TYPE CHECKER (Recursive Scan)
----------------------------------------------------------
P05  (3 file(s))
  ✓ P05/ex00/ft_filter.py
  ✗ P05/ex01/main.py
     - main: missing return annotation
     - calculate: param 'x' missing annotation
     - return coverage too low: 50.0%
----------------------------------------------------------
Summary
  P05    FAIL  1/3 passed
----------------------------------------------------------
✗ FAILED  (1/3 files)
🔍 What it checks
The tool enforces the following rules:

Arguments: All arguments (args, kwargs, varargs) must be typed.

Return values: All functions must have a return type (e.g., -> None, -> int).

Special cases: self and cls are ignored automatically.

🤝 Contributing
Feel free to fork this project and submit pull requests if you want to add features or improve the detection logic!

Fork the project

Create your feature branch (git checkout -b feature/AmazingFeature)

Commit your changes (git commit -m 'Add some AmazingFeature')

Push to the branch (git push origin feature/AmazingFeature)

Open a Pull Request
