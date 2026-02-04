#!/usr/bin/env python3
import sys
import ast
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Set

# --- CONFIGURATION ---
IGNORE_DIRS = {
    ".git", ".idea", ".vscode", "__pycache__", ".mypy_cache", 
    "venv", "env", "node_modules", ".pytest_cache"
}

class Style:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.stdout.isatty()

    def _c(self, code: str) -> str:
        return f"\033[{code}m" if self.enabled else ""

    @property
    def rst(self) -> str: return self._c("0")
    @property
    def b(self) -> str: return self._c("1") # Bold
    @property
    def d(self) -> str: return self._c("2") # Dim
    @property
    def i(self) -> str: return self._c("3") # Italic
    @property
    def u(self) -> str: return self._c("4") # Underline
    
    # Foreground
    @property
    def red(self) -> str: return self._c("31")
    @property
    def green(self) -> str: return self._c("32")
    @property
    def yellow(self) -> str: return self._c("33")
    @property
    def blue(self) -> str: return self._c("34")
    @property
    def cyan(self) -> str: return self._c("36")
    @property
    def white(self) -> str: return self._c("37")

    # Background (pour les badges)
    @property
    def bg_green(self) -> str: return self._c("42")
    @property
    def bg_red(self) -> str: return self._c("41")
    @property
    def bg_yellow(self) -> str: return self._c("43")

def draw_progress_bar(percent: float, width: int = 10, st: Style = None) -> str:
    """Dessine une barre de progression [████░░]"""
    if percent < 0: percent = 0
    if percent > 100: percent = 100
    
    filled = int(width * percent / 100)
    empty = width - filled
    
    # Couleur de la barre selon le score
    c = st.green if percent == 100 else (st.yellow if percent > 50 else st.red)
    
    bar = c + "█" * filled + st.d + "░" * empty + st.rst
    return f"{st.d}[{st.rst}{bar}{st.d}]{st.rst}"

class TypeChecker:
    def __init__(self, min_return_coverage: float = 100.0) -> None:
        self.min_return_coverage = min_return_coverage

    def _check_return_consistency(self, fn: ast.FunctionDef, issues: List[str]) -> None:
        if not fn.returns or not isinstance(fn.returns, ast.Name):
            return

        expected_type = fn.returns.id
        if expected_type not in ('int', 'str', 'bool', 'float'):
            return

        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and node.value is not None:
                if isinstance(node.value, ast.Constant):
                    val = node.value.value
                    actual_type = type(val).__name__
                    if actual_type != expected_type:
                        issues.append(
                            f"{fn.name}: return type mismatch (returns '{actual_type}' but expecting '{expected_type}')"
                        )

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

        if fn.returns is None and fn.name != "__init__":
            issues.append(f"{fn.name}: missing return annotation")
        
        self._check_return_consistency(fn, issues)

    def check_file(self, file_path: Path) -> Tuple[bool, List[str]]:
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception as e:
            return False, [f"parse error: {e}"]

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

def get_recursive_py_files(directory: Path) -> List[Path]:
    files: List[Path] = []
    if not directory.exists():
        return files
    
    for p in directory.rglob("*.py"):
        parts = p.parts
        if any(bad in parts for bad in IGNORE_DIRS):
            continue
        files.append(p)
    return sorted(files)

def parse_args(argv: List[str]) -> Tuple[bool, bool, List[str], bool]:
    verbose = False
    color = True
    targets: List[str] = []
    manual_selection = False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-v", "--verbose"): verbose = True
        elif a == "--no-color": color = False
        elif a in ("-h", "--help"):
            print("Usage: python3 typing_check.py [--verbose] [--target DIR]")
            sys.exit(0)
        elif a in ("--target", "--ex"):
            manual_selection = True
            j = i + 1
            while j < len(argv) and not argv[j].startswith("-"):
                targets.append(argv[j])
                j += 1
            i = j - 1
        i += 1
    return verbose, color, targets, manual_selection

def main() -> None:
    verbose, color, targets, manual_selection = parse_args(sys.argv)
    st = Style(enabled=color)
    root = Path(".")
    myself = Path(__file__).resolve()
    
    # Header
    term_width = shutil.get_terminal_size((80, 20)).columns
    print("\n" + f" {st.b}{st.white}TYPE CHECKER{st.rst} {st.blue}AST Analysis{st.rst} ".center(term_width + (len(st.b) if st.enabled else 0), "─"))
    
    checker = TypeChecker(min_return_coverage=100.0)
    
    # Discovery Logic
    tasks = []
    if not manual_selection:
        root_files = [p for p in root.glob("*.py") if p.resolve() != myself]
        if root_files: tasks.append(("Root Files", sorted(root_files), "root"))

    dirs_to_scan = []
    if manual_selection:
        for t in targets: dirs_to_scan.append(root / t)
    else:
        for item in root.iterdir():
            if item.is_dir() and not item.name.startswith(".") and item.name not in IGNORE_DIRS:
                if myself.parent == item.resolve(): continue
                dirs_to_scan.append(item)
        dirs_to_scan.sort(key=lambda x: x.name)

    for d in dirs_to_scan:
        files = get_recursive_py_files(d)
        if files or manual_selection:
            tasks.append((d.name, files, d.name))

    if not tasks:
        print(f"\n  {st.yellow}⚠ No files to check.{st.rst}\n")
        sys.exit(0)

    # Execution
    total_files = 0
    total_bad = 0
    stats = {}

    for label, files, key in tasks:
        stats[key] = {"files": 0, "ok": 0, "bad": 0}
        
        # Section Header
        print(f"\n{st.b}{st.cyan}● {label.upper()}{st.rst}")
        
        if not files:
            print(f"  {st.d}╰─ (empty){st.rst}")
            continue

        for i, f in enumerate(files):
            is_last = (i == len(files) - 1)
            tree_char = "╰─" if is_last else "├─"
            
            total_files += 1
            stats[key]["files"] += 1
            ok, issues = checker.check_file(f)

            # Relatif path for display
            try: display_path = f.relative_to(root)
            except ValueError: display_path = f.name

            if ok:
                stats[key]["ok"] += 1
                if verbose:
                    print(f"  {st.d}{tree_char}{st.rst} {st.green}✔{st.rst} {st.d}{display_path}{st.rst}")
            else:
                total_bad += 1
                stats[key]["bad"] += 1
                # If verbose, print detailed, else just a red line
                if verbose:
                    print(f"  {st.d}{tree_char}{st.rst} {st.red}✖ {display_path}{st.rst}")
                    for issue in issues:
                        prefix = "    " if is_last else "  │ "
                        print(f"  {st.d}{prefix}  • {issue}{st.rst}")
                else:
                    print(f"  {st.d}{tree_char}{st.rst} {st.red}✖ {display_path}{st.rst} {st.red}{len(issues)} err{st.rst}")

    # Summary
    print("\n" + " SUMMARY ".center(term_width, "─"))
    
    max_label_len = max((len(t[0]) for t in tasks), default=10)
    
    for label, _, key in tasks:
        s = stats[key]
        n_files = s['files']
        n_ok = s['ok']
        
        # Calculate percentage
        pct = (n_ok / n_files * 100) if n_files > 0 else 0
        
        # Badge
        if n_files == 0:
            badge = f"{st.d}[ EMPTY  ]{st.rst}"
        elif s['bad'] == 0:
            badge = f"{st.bg_green}{st.b}{st.white}  PASS  {st.rst}"
        else:
            badge = f"{st.bg_red}{st.b}{st.white}  FAIL  {st.rst}"
            
        bar = draw_progress_bar(pct, width=12, st=st)
        
        print(f" {label:<{max_label_len}}  {badge}  {bar} {st.d}{n_ok}/{n_files}{st.rst}")

    print("")
    if total_bad == 0:
        print(f"{st.green}✨  All {total_files} files look good! Nice job.{st.rst}\n")
        sys.exit(0)
    else:
        print(f"{st.red}💥  Found issues in {total_bad} file(s).{st.rst}")
        if not verbose:
            print(f"{st.d}    Run with --verbose to see details.{st.rst}")
        print("")
        sys.exit(1)

if __name__ == "__main__":
    main()
