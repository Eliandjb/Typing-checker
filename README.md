# ⚡ Python Static Type Analyzer

A **zero-dependency** static analyzer that enforces strict Python type-hinting rules with clear, educational feedback.  
Built for students (42/Piscine), small projects, and CI checks.


## Features

- Recursive scan with sensible ignores (`.git`, `venv`, `site-packages`, `node_modules`)
- Type coverage grading per module (**S → F**)
- Detects common issues:
  - `x = None` without `Optional[...]` / `T | None`
  - raw generics (`List`, `Dict`, `Set` without types)
  - basic return mismatch (e.g. `-> int` returning a string literal)
- Pure Python (`ast`) — no install, no dependencies

## Install

```bash
git clone https://github.com/Eliandjb/Typing-checker.git
Usage
From your project root:
python3 tester/typing_check.py
Target specific folders:
python3 tester/typing_check.py --target P05 ex00
Verbose output:
python3 tester/typing_check.py --verbose
Example output
⚡ PYTHON STATIC ANALYZER ⚡
📂 P05
  ├─ ✔ ex00/ft_filter.py
  ╰─ ✖ ex01/main.py (Score: 50%)
     │  L:12  Arg 'data' defaults to None but type is 'list'. Use Optional[list].
     │  L:15  Missing return annotation
