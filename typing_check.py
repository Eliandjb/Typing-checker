#!/usr/bin/env python3
import sys
import ast
from pathlib import Path
from typing import List, Tuple, Dict, Set

# --- CONFIGURATION ---
# Dossiers à ignorer absolument lors du scan
IGNORE_DIRS = {
    ".git", ".idea", ".vscode", "__pycache__", ".mypy_cache", 
    "venv", "env", "node_modules", ".pytest_cache"
}
# ---------------------

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


def get_recursive_py_files(directory: Path) -> List[Path]:
    """Récupère récursivement tous les .py, sauf dans les dossiers ignorés."""
    files: List[Path] = []
    if not directory.exists():
        return files
    
    # rglob parcourt tout, mais on doit filtrer les dossiers ignorés
    for p in directory.rglob("*.py"):
        # Vérifie si un dossier parent est dans la liste noire
        parts = p.parts
        if any(bad in parts for bad in IGNORE_DIRS):
            continue
        if "__pycache__" in parts:
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
        if a in ("-v", "--verbose"):
            verbose = True
        elif a == "--no-color":
            color = False
        elif a in ("-h", "--help"):
            print(
                "Usage:\n"
                "  python3 typing_check.py [--verbose] [--target P00 P01 ...]\n\n"
                "Examples:\n"
                "  python3 typing_check.py          # Checks EVERYTHING from current dir\n"
                "  python3 typing_check.py --target P05  # Checks only P05 folder\n"
            )
            sys.exit(0)
        elif a in ("--target", "--ex"): # Support old flag --ex or new --target
            manual_selection = True
            j = i + 1
            while j < len(argv) and not argv[j].startswith("-"):
                targets.append(argv[j])
                j += 1
            i = j - 1
        else:
            print(f"Unknown option: {a}")
            sys.exit(2)
        i += 1

    return verbose, color, targets, manual_selection


def pad_right(s: str, width: int) -> str:
    return s + (" " * max(0, width - len(s)))


def main() -> None:
    verbose, color, targets, manual_selection = parse_args(sys.argv)
    st = Style(enabled=color)
    root = Path(".")
    
    # On identifie le fichier actuel pour ne pas le scanner s'il est dans l'arborescence
    myself = Path(__file__).resolve()

    checker = TypeChecker(min_return_coverage=100.0)

    title = f"{st.bold}{st.blue}TYPE CHECKER{st.reset}{st.dim} (Recursive Scan){st.reset}"
    print(title)
    print(st.dim + "-" * 58 + st.reset)

    # --- DISCOVERY ---
    # Liste de tuples : (Nom_Affichage, Liste_Fichiers, Cle_Stats)
    tasks = []

    # 1. Fichiers à la racine (seulement si pas de sélection manuelle)
    if not manual_selection:
        root_files = []
        for p in root.glob("*.py"):
            if p.resolve() == myself:
                continue
            root_files.append(p)
        if root_files:
            root_files.sort()
            tasks.append(("Root Files", root_files, "root"))

    # 2. Dossiers cibles
    dirs_to_scan = []

    if manual_selection:
        # L'utilisateur a donné des noms explicites (ex: P05, ex02, dossier_test)
        for t in targets:
            dirs_to_scan.append(root / t)
    else:
        # Scan automatique des sous-dossiers directs
        for item in root.iterdir():
            if item.is_dir():
                if item.name.startswith("."): continue # Ignorer .git, .vscode...
                if item.name in IGNORE_DIRS: continue
                
                # Si le script est dans un dossier 'tester', on l'ignore généralement
                # pour ne pas qu'il se scanne lui-même, sauf demande explicite.
                if myself.parent.name == item.name and myself.parent == item.resolve():
                     continue

                dirs_to_scan.append(item)
        dirs_to_scan.sort(key=lambda x: x.name)

    # Préparation des tâches
    for d in dirs_to_scan:
        files = get_recursive_py_files(d)
        if files: # On n'ajoute la tâche que s'il y a des fichiers Python dedans
            tasks.append((d.name, files, d.name))
        elif manual_selection:
             # Si c'était demandé explicitement mais vide, on l'ajoute quand même pour dire "EMPTY"
             tasks.append((d.name, [], d.name))

    if not tasks:
        print(f"{st.yellow}! No Python files found in scan.{st.reset}")
        sys.exit(0)

    # --- EXECUTION ---
    total_files = 0
    total_bad = 0
    total_ok = 0
    stats = {}

    for label, files, key in tasks:
        stats[key] = {"files": 0, "ok": 0, "bad": 0}
        
        print(f"{st.bold}{label}{st.reset}  {st.dim}({len(files)} file(s)){st.reset}")

        if not files:
            print(f"  {st.yellow}! no .py files found{st.reset}")
            continue

        for f in files:
            total_files += 1
            stats[key]["files"] += 1

            ok, issues = checker.check_file(f)

            # Chemin relatif pour l'affichage (ex: P05/ex00/main.py)
            display_path = f
            try:
                display_path = f.relative_to(root)
            except ValueError:
                pass

            if ok:
                total_ok += 1
                stats[key]["ok"] += 1
                if verbose:
                    print(f"  {st.green}✓{st.reset} {display_path}")
            else:
                total_bad += 1
                stats[key]["bad"] += 1
                if verbose:
                    print(f"  {st.red}✗{st.reset} {display_path}")
                    for it in issues:
                        print(f"     {st.red}-{st.reset} {it}")
                else:
                    # Affichage concis en mode non-verbose
                    print(f"  {st.red}✗{st.reset} {display_path}  {st.dim}({len(issues)}){st.reset}")

    print(st.dim + "-" * 58 + st.reset)

    # --- SUMMARY ---
    print(st.bold + "Summary" + st.reset)
    
    max_label = max((len(t[0]) for t in tasks), default=5)

    for label, _, key in tasks:
        s = stats[key]
        lbl_pad = pad_right(label, max_label)
        
        if s["bad"] == 0 and s["files"] > 0:
            status = f"{st.green}OK{st.reset}"
        elif s["files"] == 0:
            status = f"{st.yellow}EMPTY{st.reset}"
        else:
            status = f"{st.red}FAIL{st.reset}"
            
        print(f"  {lbl_pad}  {status}  {st.dim}{s['ok']}/{s['files']} passed{st.reset}")

    print(st.dim + "-" * 58 + st.reset)

    if total_bad == 0:
        print(f"{st.green}{st.bold}✓ ALL GOOD{st.reset}  {st.dim}({total_ok}/{total_files} files){st.reset}")
        sys.exit(0)

    print(f"{st.red}{st.bold}✗ FAILED{st.reset}  {st.dim}({total_bad}/{total_files} files){st.reset}")
    if not verbose:
        print(st.dim + "Tip: run with --verbose to see exact issues." + st.reset)

    sys.exit(1)


if __name__ == "__main__":
    main()
