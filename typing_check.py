#!/usr/bin/env python3
import sys
import ast
from pathlib import Path
from typing import List, Tuple, Dict


class Style:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.stdout.isatty()

    def _c(self, code: str) -> str:
        return f"\033[{code}m" if self.enabled else ""

    @property
    def reset(self) -> str:
        return self._c("0")

    @property
    def bold(self) -> str:
        return self._c("1")

    @property
    def dim(self) -> str:
        return self._c("2")

    @property
    def red(self) -> str:
        return self._c("31")

    @property
    def green(self) -> str:
        return self._c("32")

    @property
    def yellow(self) -> str:
        return self._c("33")

    @property
    def blue(self) -> str:
        return self._c("34")


class TypeChecker:
    def __init__(self, min_return_coverage: float = 100.0) -> None:
        self.min_return_coverage = min_return_coverage

    def _check_function(self, fn: ast.FunctionDef, issues: List[str]) -> None:
        for arg in fn.args.args:
            if arg.arg in ("self", "cls"):
                continue
            if arg.annotation is None:
                issues.append(f"{fn.name}: param '{arg.arg}' missing annotation")

        if fn.args.vararg is not None and fn.args.vararg.annotation is None:
            issues.append(f"{fn.name}: vararg '*{fn.args.vararg.arg}' missing annotation")

        if fn.args.kwarg is not None and fn.args.kwarg.annotation is None:
            issues.append(f"{fn.name}: kwarg '**{fn.args.kwarg.arg}' missing annotation")

        for arg in fn.args.kwonlyargs:
            if arg.annotation is None:
                issues.append(f"{fn.name}: kw-only param '{arg.arg}' missing annotation")

        if fn.returns is None and fn.name != "__init__":
            issues.append(f"{fn.name}: missing return annotation")

    def check_file(self, file_path: Path) -> Tuple[bool, List[str]]:
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except FileNotFoundError:
            return False, ["file not found"]
        except SyntaxError as e:
            return False, [f"syntax error: {e}"]
        except Exception as e:
            return False, [f"read/parse error: {e}"]

        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if not functions:
            return True, []

        issues: List[str] = []

        fn_total = 0
        fn_ok_return = 0

        for fn in functions:
            fn_total += 1
            if fn.returns is not None or fn.name == "__init__":
                fn_ok_return += 1
            self._check_function(fn, issues)

        if fn_total > 0:
            coverage = (fn_ok_return / fn_total) * 100.0
            if coverage < self.min_return_coverage:
                issues.append(f"return coverage too low: {coverage:.1f}%")

        return len(issues) == 0, issues


def list_py_files(ex_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in ex_dir.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        files.append(p)
    return sorted(files)


def parse_args(argv: List[str]) -> Tuple[bool, bool, List[int]]:
    verbose = False
    color = True
    exos: List[int] = []

    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-v", "--verbose"):
            verbose = True
        elif a == "--no-color":
            color = False
        elif a in ("-h", "--help"):
            print(
                "Usage:\n"
                "  python3 typing_check.py [--verbose] [--no-color] [--ex 0 1 2 3 4]\n\n"
                "Examples:\n"
                "  python3 typing_check.py\n"
                "  python3 typing_check.py --verbose\n"
                "  python3 typing_check.py --ex 0 1 2\n"
            )
            sys.exit(0)
        elif a == "--ex":
            j = i + 1
            while j < len(argv) and not argv[j].startswith("-"):
                try:
                    exos.append(int(argv[j]))
                except ValueError:
                    print(f"Invalid ex number: {argv[j]}")
                    sys.exit(2)
                j += 1
            i = j - 1
        else:
            print(f"Unknown option: {a}")
            sys.exit(2)
        i += 1

    if not exos:
        exos = [0, 1, 2, 3, 4]

    return verbose, color, exos


def pad_right(s: str, width: int) -> str:
    return s + (" " * max(0, width - len(s)))


def main() -> None:
    verbose, color, exos = parse_args(sys.argv)
    st = Style(enabled=color)

    checker = TypeChecker(min_return_coverage=100.0)
    root = Path(".")

    title = f"{st.bold}{st.blue}TYPE CHECKER{st.reset}{st.dim} (AST hints){st.reset}"
    print(title)
    print(st.dim + "-" * 58 + st.reset)

    total_files = 0
    total_bad = 0
    total_ok = 0

    per_ex_stats: Dict[int, Dict[str, int]] = {}
    errors_by_file: List[Tuple[Path, List[str]]] = []

    for n in exos:
        ex_dir = root / f"ex{n}"
        per_ex_stats[n] = {"files": 0, "ok": 0, "bad": 0}

        header = f"{st.bold}ex{n}{st.reset}"
        if not ex_dir.exists() or not ex_dir.is_dir():
            print(f"{header}  {st.red}✗ missing directory{st.reset}")
            total_bad += 1
            continue

        py_files = list_py_files(ex_dir)
        if not py_files:
            print(f"{header}  {st.yellow}! no .py files found{st.reset}")
            continue

        print(f"{header}  {st.dim}{len(py_files)} file(s){st.reset}")

        for f in py_files:
            total_files += 1
            per_ex_stats[n]["files"] += 1

            ok, issues = checker.check_file(f)

            if ok:
                total_ok += 1
                per_ex_stats[n]["ok"] += 1
                if verbose:
                    print(f"  {st.green}✓{st.reset} {f}")
            else:
                total_bad += 1
                per_ex_stats[n]["bad"] += 1
                errors_by_file.append((f, issues))
                if verbose:
                    print(f"  {st.red}✗{st.reset} {f}")
                    for it in issues:
                        print(f"     {st.red}-{st.reset} {it}")
                else:
                    print(f"  {st.red}✗{st.reset} {f}  {st.dim}({len(issues)} issue(s)){st.reset}")

    print(st.dim + "-" * 58 + st.reset)

    # Summary per ex
    max_label = max((len(f"ex{n}") for n in per_ex_stats), default=3)
    print(st.bold + "Summary" + st.reset)
    for n in exos:
        s = per_ex_stats.get(n, {"files": 0, "ok": 0, "bad": 0})
        label = pad_right(f"ex{n}", max_label)
        if s["bad"] == 0 and s["files"] > 0:
            status = f"{st.green}OK{st.reset}"
        elif s["files"] == 0:
            status = f"{st.yellow}EMPTY{st.reset}"
        else:
            status = f"{st.red}FAIL{st.reset}"
        print(f"  {label}  {status}  {st.dim}{s['ok']}/{s['files']} passed{st.reset}")

    print(st.dim + "-" * 58 + st.reset)

    if total_bad == 0:
        print(f"{st.green}{st.bold}✓ ALL GOOD{st.reset}  {st.dim}({total_ok}/{total_files} files){st.reset}")
        sys.exit(0)

    print(f"{st.red}{st.bold}✗ FAILED{st.reset}  {st.dim}({total_bad}/{total_files} files){st.reset}")

    if not verbose:
        print(st.dim + "Tip: run with --verbose to see exact issues per file." + st.reset)

    sys.exit(1)


if __name__ == "__main__":
    main()

