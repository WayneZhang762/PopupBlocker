"""打包脚本：生成图标 → PyInstaller 出 exe。

用法（项目根目录）：
    .venv\\Scripts\\python.exe build.py            # onedir，推荐
    .venv\\Scripts\\python.exe build.py --onefile  # 单文件便携版
    .venv\\Scripts\\python.exe build.py --tool     # 只打「测试弹窗生成器」单文件 exe
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ICON = ROOT / "app.ico"
NAME = "静窗"
TOOL_NAME = "测试弹窗生成器"
TOOL_ENTRY = ROOT / "tools" / "popup_simulator.py"
TOOL_WORK = ROOT / ".build_tools"


def make_icon() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.ui.icons import write_ico

    app = QApplication.instance() or QApplication([])
    ok = write_ico(str(ICON), 256)
    print(f"图标生成：{ICON} -> {ok}")


def run(onefile: bool) -> int:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--windowed",
        "--name", NAME,
        "--icon", str(ICON),
        "--add-data", f"{ROOT / 'app' / 'data' / 'builtin_rules.json'}{os.pathsep}app/data",
        "--hidden-import", "win32timezone",
        "--collect-submodules", "app",
    ]
    if onefile:
        args.append("--onefile")
    args.append(str(ROOT / "app" / "main.py"))

    print("执行：", " ".join(args))
    return subprocess.call(args, cwd=str(ROOT))


def build_tool() -> int:
    """把测试弹窗生成器打成单文件 exe，方便没装 Python 的机器直接用。"""
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--windowed", "--onefile",
        "--name", TOOL_NAME,
        "--icon", str(ICON),
        "--distpath", str(DIST),
        "--workpath", str(TOOL_WORK),
        str(TOOL_ENTRY),
    ]
    print("执行：", " ".join(args))
    code = subprocess.call(args, cwd=str(ROOT))
    shutil.rmtree(TOOL_WORK, ignore_errors=True)
    spec = ROOT / f"{TOOL_NAME}.spec"
    if spec.exists():
        spec.unlink()
    if code == 0:
        print(f"\n打包完成：{DIST / (TOOL_NAME + '.exe')}")
    return code


def cleanup() -> None:
    for path in (BUILD, ROOT / f"{NAME}.spec"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()


def main() -> int:
    make_icon()
    if "--tool" in sys.argv:
        return build_tool()
    onefile = "--onefile" in sys.argv
    code = run(onefile)
    cleanup()
    if code == 0:
        target = DIST / (f"{NAME}.exe" if onefile else f"{NAME}/{NAME}.exe")
        print(f"\n打包完成：{target}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
