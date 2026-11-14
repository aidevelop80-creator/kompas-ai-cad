# run_freecad.py — Мост запуска FreeCAD 1.1 из виртуального окружения проекта
# Использование:
#   .venv\Scripts\python.exe run_freecad.py build_flange_fc.py output/Flange_D100_h60.FCStd
#   .venv\Scripts\python.exe run_freecad.py build_flange_fc.py output/Flange_D100_h60.FCStd --keep-open
import os
import subprocess
import sys
import tempfile

FREECAD_CMD = r"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
FREECAD_GUI = r"C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe"


def render_fcstd_to_png(fcstd_path: str, png_path: str, keep_open: bool = False):
    abs_fcstd = os.path.abspath(fcstd_path).replace("\\", "\\\\")
    abs_png = os.path.abspath(png_path).replace("\\", "\\\\")
    os.makedirs(os.path.dirname(os.path.abspath(png_path)), exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w", suffix="_fc_render.py", delete=False, encoding="utf-8"
    ) as tf:
        tmp_py = tf.name
    abs_tmp = os.path.abspath(tmp_py).replace("\\", "\\\\")

    render_code = f'''
import os
import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

_doc = None
KEEP_OPEN = {bool(keep_open)}

def _step1_open():
    global _doc
    _doc = App.openDocument("{abs_fcstd}")
    App.setActiveDocument(_doc.Name)
    Gui.setActiveDocument(_doc.Name)
    tips = {{getattr(b, "Tip", None) for b in _doc.Objects if b.TypeId == "PartDesign::Body"}}
    for obj in _doc.Objects:
        vo = getattr(obj, "ViewObject", None)
        if vo is None:
            continue
        if obj.TypeId == "PartDesign::Body" or obj in tips:
            vo.Visibility = True
        elif obj.TypeId.startswith("Sketcher::") or obj.TypeId.startswith("PartDesign::"):
            vo.Visibility = False
    _doc.recompute()
    _doc.save()
    QtWidgets.QApplication.processEvents()
    QtCore.QTimer.singleShot(400, _step2_camera)

def _step2_camera():
    gdoc = Gui.getDocument(_doc.Name)
    view = gdoc.ActiveView
    view.viewIsometric()
    view.fitAll()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    QtCore.QTimer.singleShot(400, _step3_save)

def _step3_save():
    try:
        gdoc = Gui.getDocument(_doc.Name)
        view = gdoc.ActiveView
        view.saveImage("{abs_png}", 1280, 960, "Current")
        if not KEEP_OPEN:
            App.closeDocument(_doc.Name)
    finally:
        try:
            os.remove("{abs_tmp}")
        except Exception:
            pass
        if not KEEP_OPEN:
            QtWidgets.QApplication.quit()

QtCore.QTimer.singleShot(600, _step1_open)
'''
    with open(tmp_py, "w", encoding="utf-8") as f:
        f.write(render_code)

    if keep_open:
        subprocess.Popen([FREECAD_GUI, tmp_py])
        print(f"[OK RENDER PNG] {png_path} (окно FreeCAD оставлено открытым)")
    else:
        try:
            subprocess.run([FREECAD_GUI, tmp_py], check=True)
            print(f"[OK RENDER PNG] {png_path}")
        finally:
            if os.path.exists(tmp_py):
                os.remove(tmp_py)


def main():
    keep_open = "--close" not in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--keep-open", "--open")]

    if not args:
        print(
            "Использование: .venv\\Scripts\\python.exe run_freecad.py <script.py> [model.FCStd] [--keep-open]"
        )
        sys.exit(1)

    env = os.environ.copy()
    env["FC_TARGET_SCRIPT"] = os.path.abspath(args[0])
    runner_cmd = (
        'exec("import os, sys, traceback\\n'
        "try:\\n"
        "    p = os.environ['FC_TARGET_SCRIPT']\\n"
        "    sys.path.insert(0, os.path.dirname(p))\\n"
        "    exec(open(p, encoding='utf-8').read(), {'__name__': '__main__', '__file__': p})\\n"
        "    sys.stdout.flush(); sys.stderr.flush(); os._exit(0)\\n"
        "except SystemExit as e:\\n"
        "    sys.stdout.flush(); sys.stderr.flush(); os._exit(int(e.code) if isinstance(e.code, int) else 0)\\n"
        "except Exception:\\n"
        '    traceback.print_exc(); sys.stdout.flush(); sys.stderr.flush(); os._exit(1)")'
    )
    res = subprocess.run([FREECAD_CMD, "-c", runner_cmd], env=env)
    if res.returncode != 0:
        sys.exit(res.returncode)

    if len(args) >= 2:
        fcstd_path = args[1]
        png_path = os.path.splitext(fcstd_path)[0] + "_fc.png"
        render_fcstd_to_png(fcstd_path, png_path, keep_open=keep_open)


if __name__ == "__main__":
    main()
