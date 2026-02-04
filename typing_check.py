#!/usr/bin/env python3
import sys
import ast
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Any

# --- CONFIGURATION ---
# J'ai ajouté 'site-packages', 'lib', 'bin', 'include' pour éviter de scanner ton venv
IGNORE_DIRS = {
    ".git", ".idea", ".vscode", "__pycache__", ".mypy_cache", 
    "venv", "env", ".env", "node_modules", ".pytest_cache", "build", "dist",
    "site-packages", "lib", "bin", "include", "Lib", "Scripts"
}

# --- STYLE MANAGER ---
class Style:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and sys.stdout.isatty()

    def _c(self, code: str) -> str: return f"\033[{code}m" if self.enabled else ""
    
    @property
    def rst(self) -> str: return self._c("0")
    @property
    def b(self) -> str: return self._c("1")
    @property
    def d(self) -> str: return self._c("2")
    
    @property
    def red(self) -> str: return self._c("38;5;196")
    @property
    def green(self) -> str: return self._c("38;5;46")
    @property
    def yellow(self) -> str: return self._c("38;5;226")
    @property
    def blue(self) -> str: return self._c("38;5;39")
    @property
    def gray(self) -> str: return self._c("38;5;240")
    @property
    def white(self) -> str: return self._c("38;5;15")

    @property
    def bg_green(self) -> str: return self._c("48;5;46")
    @property
    def bg_red(self) -> str: return self._c("48;5;196")
    @property
    def bg_yellow(self) -> str: return self._c("48;5;226")

st = Style()

# --- UTILS ---
def draw_bar(percent: float, width: int = 12) -> str:
    if percent < 0: percent = 0
    if percent > 100: percent = 100
    filled = int(width * percent / 100)
    color = st.green if percent == 100 else (st.yellow if percent >= 70 else st.red)
    return f"{st.d}[{st.rst}{color}{'━' * filled}{st.d}{'─' * (width - filled)}{st.d}]{st.rst}"

def get_grade(score: float) -> str:
    if score == 100: return f"{st.b}{st.green} S {st.rst}"
    if score >= 90: return f"{st.b}{st.blue} A {st.rst}"
    if score >= 75: return f"{st.b}{st.yellow} B {st.rst}"
    if score >= 50: return f"{st.b}{st.red} C {st.rst}"
    return f"{st.b}{st.gray} F {st.rst}"

# --- CORE LOGIC ---
class TypeChecker:
    def __init__(self) -> None:
        self.min_return_coverage = 100.0

    def _get_annotation_name(self, node: Any) -> str:
        if node is None: return ""
        if sys.version_info >= (3, 9):
            try: return ast.unparse(node)
            except: pass
        if isinstance(node, ast.Name): return node.id
        if isinstance(node, ast.Constant): return str(node.value)
        if isinstance(node, ast.Subscript):
             val = self._get_annotation_name(node.value)
             return f"{val}[...]"
        return "complex_type"

    def _check_optional_consistency(self, fn: ast.FunctionDef, issues: List[str]) -> None:
        defaults = fn.args.defaults
        
        # FIX: Combine posonlyargs (Python 3.8+) and regular args
        # This prevents IndexError when analyzing libraries like setuptools
        pos_args = getattr(fn.args, 'posonlyargs', []) + fn.args.args
        
        if not defaults: return
        
        offset = len(pos_args) - len(defaults)
        
        for i, default_val in enumerate(defaults):
            # Safety check to avoid crash if AST is weird
            idx = offset + i
            if idx < 0 or idx >= len(pos_args):
                continue

            arg_node = pos_args[idx]
            if isinstance(default_val, ast.Constant) and default_val.value is None:
                if arg_node.annotation:
                    anno = self._get_annotation_name(arg_node.annotation)
                    if "Optional" not in anno and "None" not in anno and "|" not in anno:
                        issues.append(f"{st.yellow}L:{arg_node.lineno:<3}{st.rst} Arg '{st.b}{arg_node.arg}{st.rst}' defaults to None but type is '{anno}'. Use Optional[{anno}].")

    def _check_raw_collections(self, fn: ast.FunctionDef, issues: List[str]) -> None:
        # Check both posonlyargs and args
        all_args = getattr(fn.args, 'posonlyargs', []) + fn.args.args
        for arg in all_args:
            if not arg.annotation: continue
            if isinstance(arg.annotation, ast.Name):
                t_name = arg.annotation.id
                if t_name in ("List", "Dict", "Set", "Tuple"):
                    issues.append(f"{st.yellow}L:{arg.lineno:<3}{st.rst} Arg '{st.b}{arg.arg}{st.rst}' uses raw '{t_name}'. Prefer '{t_name}[type]'.")

    def _check_return_consistency(self, fn: ast.FunctionDef, issues: List[str]) -> None:
        if not fn.returns or not isinstance(fn.returns, ast.Name): return
        expected = fn.returns.id
        if expected not in ('int', 'str', 'bool', 'float'): return

        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and node.value is not None:
                if isinstance(node.value, ast.Constant):
                    val = node.value.value
                    actual = type(val).__name__
                    if actual != expected and not (expected == 'float' and actual == 'int'):
                         issues.append(f"{st.red}L:{node.lineno:<3}{st.rst} Function expects '{expected}' but returns '{actual}'.")

    def check_file(self, file_path: Path) -> Tuple[bool, List[str], float]:
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception as e:
            return False, [f"{st.red}Parse Error{st.rst}: {str(e)}"], 0.0

        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        
        if not functions: return True, [], 100.0

        issues: List[str] = []
        fn_total = 0
        fn_ok = 0

        for fn in functions:
            fn_issues = []
            
            # Check positional-only args AND regular args
            all_args = getattr(fn.args, 'posonlyargs', []) + fn.args.args
            
            for arg in all_args:
                if arg.arg in ("self", "cls"): continue
                if arg.annotation is None:
                    fn_issues.append(f"{st.red}L:{arg.lineno:<3}{st.rst} Missing annotation for arg '{st.b}{arg.arg}{st.rst}'")

            # Check keyword-only args
            for arg in fn.args.kwonlyargs:
                if arg.annotation is None:
                    fn_issues.append(f"{st.red}L:{arg.lineno:<3}{st.rst} Missing annotation for kw-only arg '{st.b}{arg.arg}{st.rst}'")

            if fn.returns is None and fn.name != "__init__":
                fn_issues.append(f"{st.red}L:{fn.lineno:<3}{st.rst} Missing return annotation")

            self._check_optional_consistency(fn, fn_issues)
            self._check_raw_collections(fn, fn_issues)
            self._check_return_consistency(fn, fn_issues)

            if not fn_issues:
                fn_ok += 1
            else:
                issues.append(f"{st.d}In function '{st.b}{fn.name}{st.rst}{st.d}':{st.rst}")
                issues.extend([f"   {i}" for i in fn_issues])

            fn_total += 1

        score = (fn_ok / fn_total * 100) if fn_total > 0 else 100.0
            
        return len(issues) == 0, issues, score

# --- DISCOVERY ---
def get_recursive_py_files(directory: Path) -> List[Path]:
    files: List[Path] = []
    if not directory.exists(): return files
    for p in directory.rglob("*.py"):
        # Improved Ignore Logic: Check if any part of the path matches IGNORE_DIRS
        if any(bad in p.parts for bad in IGNORE_DIRS): continue
        files.append(p)
    return sorted(files)

def parse_args(argv: List[str]) -> Tuple[bool, List[str], bool]:
    verbose = False
    targets = []
    manual = False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-v", "--verbose"): verbose = True
        elif a in ("--target", "--ex"):
            manual = True
            j = i + 1
            while j < len(argv) and not argv[j].startswith("-"):
                targets.append(argv[j])
                j += 1
            i = j - 1
        i += 1
    return verbose, targets, manual

# --- MAIN ---
def main() -> None:
    verbose, targets, manual_selection = parse_args(sys.argv)
    root = Path(".")
    myself = Path(__file__).resolve()
    
    term_w = shutil.get_terminal_size((80, 20)).columns
    print(f"\n{st.b}⚡ PYTHON STATIC ANALYZER ⚡{st.rst}".center(term_w + 10))
    print(f"{st.d}{'─' * term_w}{st.rst}")

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
        if files or manual_selection: tasks.append((d.name, files, d.name))

    if not tasks:
        print(f"  {st.yellow}⚠  No Python files found.{st.rst}\n")
        sys.exit(0)

    checker = TypeChecker()
    stats = {}
    total_bad_files = 0
    total_files = 0

    for label, files, key in tasks:
        stats[key] = {"files": 0, "score_sum": 0.0, "clean": True}
        
        print(f"\n{st.blue}📂 {st.b}{label.upper()}{st.rst}")

        if not files:
            print(f"  {st.d}╰─ (empty){st.rst}")
            continue

        for i, f in enumerate(files):
            is_last = (i == len(files) - 1)
            tree = "╰─" if is_last else "├─"
            
            ok, issues, f_score = checker.check_file(f)
            total_files += 1
            
            stats[key]["files"] += 1
            stats[key]["score_sum"] += f_score

            try: rel_path = f.relative_to(root)
            except: rel_path = f.name
            
            if ok:
                if verbose:
                    print(f"  {st.d}{tree}{st.rst} {st.green}✔{st.rst} {rel_path}")
            else:
                stats[key]["clean"] = False
                total_bad_files += 1
                print(f"  {st.d}{tree}{st.rst} {st.red}✖{st.rst} {rel_path} {st.d}(Score: {int(f_score)}%){st.rst}")
                
                prefix = "    " if is_last else "  │ "
                for issue in issues:
                    print(f"  {st.d}{prefix}{st.rst} {issue}")

    # Summary Table
    print("\n" + f"{st.b}📊 SUMMARY REPORT{st.rst}".center(term_w + 10))
    print(f"{st.d}{'─' * term_w}{st.rst}")
    
    col_w = max((len(t[0]) for t in tasks), default=10) + 2
    print(f"  {st.d}{'MODULE':<{col_w}} {'STATUS':<10} {'PROGRESS':<14} {'GRADE':<5}{st.rst}")

    for label, _, key in tasks:
        s = stats[key]
        n_files = s["files"]
        avg_score = (s["score_sum"] / n_files) if n_files > 0 else 0.0
        
        if n_files == 0:
            status = f"{st.d}EMPTY   {st.rst}"
            bar = f"{st.d}[          ]{st.rst}"
            grade = "-"
        elif s["clean"] and avg_score == 100:
            status = f"{st.green}PASS    {st.rst}"
            bar = draw_bar(100)
            grade = get_grade(100)
        else:
            status = f"{st.red}FAIL    {st.rst}"
            bar = draw_bar(avg_score)
            grade = get_grade(avg_score)

        print(f"  {st.b}{label:<{col_w}}{st.rst} {status} {bar}  {grade}")

    print("")
    if total_bad_files == 0:
        print(f"{st.bg_green}{st.b}{st.white} ✨ PERFECT RUN! ALL SYSTEMS GO. ✨ {st.rst}\n")
        sys.exit(0)
    else:
        print(f"{st.b}{st.white}Total Issues:{st.rst} {st.red}{total_bad_files} files failed checks.{st.rst}")
        if not verbose:
            print(f"{st.d}Tip: Run with --verbose to see passing files.{st.rst}")
        print("")
        sys.exit(1)

if __name__ == "__main__":
    main()
