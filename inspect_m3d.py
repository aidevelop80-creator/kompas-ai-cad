# inspect_m3d.py — Универсальный декомпилятор моделей КОМПАС-3D (.m3d) для обучения ИИ-агента
import glob
import os
import sys

import pythoncom

from kompas_core import OBJ_SKETCH, _connect_existing_or_new_kompas, _wrap
from sdk_ref import kompas_api5_v16 as K5
from sdk_ref import kompas_api7_v16 as K7


def _extract_vars_from_feature7(feat7) -> list[tuple[str, str, float, str, str]]:
    """Извлекает переменные (Имя, Выражение, Значение, Комментарий, НазначениеПараметра) из IFeature7."""
    result = []
    seen = set()
    for ext_flag in (True, False):
        for sketch_flag in (False, True):
            try:
                raw_vars = feat7.Variables(ext_flag, sketch_flag)
            except Exception:
                continue
            if raw_vars is None:
                continue
            items = raw_vars if isinstance(raw_vars, (list, tuple)) else [raw_vars]
            for item in items:
                try:
                    v = _wrap(K7.IVariable7, item)
                    name = str(v.Name or "")
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    expr = str(v.Expression or "")
                    val = float(v.Value)
                    note = str(v.Note or "")
                    pnote = str(getattr(v, "ParameterNote", "") or "")
                    result.append((name, expr, val, note, pnote))
                except Exception:
                    pass
    return result


def _inspect_sketch_geometry(sk_ent, sf7) -> list[str]:
    """Извлекает базовую плоскость/грань эскиза и координаты всех отрезков, осевых и окружностей."""
    lines_info = []
    try:
        sk_def = _wrap(K5.ksSketchDefinition, sk_ent.GetDefinition())
        pl = _wrap(K5.ksEntity, sk_def.GetPlane())
        pl_name = (pl.name or "").strip()
        if pl_name:
            lines_info.append(f"  - Базовая плоскость эскиза: **`{pl_name}`**")
        else:
            lines_info.append(
                f"  - Базовая плоскость эскиза: **Плоская грань детали (type={pl.type})**"
            )
    except Exception:
        return lines_info

    # Открываем эскиз и читаем примитивы через API7 IDrawingContainer (LineSegments, Circles, Arcs)
    doc2d_raw = sk_def.BeginEdit()
    try:
        # Также проверяем итератор API5 с правильным приведением типов
        doc2d = _wrap(K5.ksDocument2D, doc2d_raw)
        # В API7 активный 2D-документ в режиме редактирования эскиза отдает IDrawingContainer
        try:
            sk7 = _wrap(K7.ISketch, sf7)
            frag7 = sk7.BeginEdit()
            views_mgr = _wrap(K7.IViewsAndLayersManager, frag7.ViewsAndLayersManager)
            view7 = _wrap(K7.IView, views_mgr.Views.ActiveView)
            dc = _wrap(K7.IDrawingContainer, view7)
            sk7.EndEdit()
        except Exception:
            dc = None

        # Если IDrawingContainer доступен напрямую из sk7:
        if dc is None:
            # Читаем через итератор текущего документа doc2d
            pass
    except Exception:
        pass
    finally:
        sk_def.EndEdit()

    # Чтение 2D-объектов через API7 ISketch.BeginEdit() (когда эскиз закрыт в API5)
    try:
        sk7 = _wrap(K7.ISketch, sf7)
        doc2d_7 = _wrap(K7.IKompasDocument2D, sk7.BeginEdit())
        try:
            v_mgr = _wrap(K7.IViewsAndLayersManager, doc2d_7.ViewsAndLayersManager)
            views = _wrap(K7.IViews, v_mgr.Views)
            v0 = _wrap(K7.IView, views.ActiveView)
            dc = _wrap(K7.IDrawingContainer, v0)

            # 1. Отрезки (LineSegments)
            lsegs = _wrap(K7.ILineSegments, dc.LineSegments)
            for i in range(lsegs.Count):
                ls = _wrap(K7.ILineSegment, lsegs.LineSegment(i))
                st = (
                    "ОСЕВАЯ (style=3)"
                    if ls.Style == 3
                    else f"Основная (style={ls.Style})"
                )
                lines_info.append(
                    f"  - Отрезок [{st}]: `({ls.X1:.2f}, {ls.Y1:.2f}) -> ({ls.X2:.2f}, {ls.Y2:.2f})`"
                )

            # 2. Окружности (Circles)
            circs = _wrap(K7.ICircles, dc.Circles)
            for i in range(circs.Count):
                c = _wrap(K7.ICircle, circs.Circle(i))
                lines_info.append(
                    f"  - Окружность [style={c.Style}]: Центр `({c.Xc:.2f}, {c.Yc:.2f})`, Радиус `R={c.Radius:.2f}` (`D={c.Radius * 2:.2f}`)"
                )

            # 3. Дуги (Arcs)
            arcs = _wrap(K7.IArcs, dc.Arcs)
            for i in range(arcs.Count):
                a = _wrap(K7.IArc, arcs.Arc(i))
                lines_info.append(
                    f"  - Дуга [style={a.Style}]: Центр `({a.Xc:.2f}, {a.Yc:.2f})`, `R={a.Radius:.2f}`"
                )
        finally:
            sk7.EndEdit()
    except Exception:
        pass

    return lines_info


def inspect_m3d(filepath: str) -> str:
    """Анализирует файл .m3d и сохраняет подробный инженерный слепок <name>_blueprint.md."""
    abs_path = os.path.abspath(filepath)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Файл не найден: {abs_path}")

    pythoncom.CoInitialize()
    api5 = _connect_existing_or_new_kompas(visible=True)
    api7 = _wrap(K7.IApplication, api5.ksGetApplication7())

    docs = _wrap(K7.IDocuments, api7.Documents)
    doc7 = _wrap(K7.IKompasDocument, docs.Open(abs_path, True, False))
    doc7_3d = _wrap(K7.IKompasDocument3D, doc7)
    part7 = _wrap(K7.IPart7, doc7_3d.TopPart)
    feat7_root = _wrap(K7.IFeature7, part7)

    doc3d = _wrap(K5.ksDocument3D, api5.ActiveDocument3D())
    part5 = _wrap(K5.ksPart, doc3d.GetPart(-1))

    report = []
    report.append(
        f"# Инженерный слепок эталонной модели: `{os.path.basename(abs_path)}`"
    )
    res, x1, y1, z1, x2, y2, z2 = part5.GetGabarit(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    mip = _wrap(K5.ksMassInertiaParam, part5.CalcMassInertiaProperties(0x1))
    report.append(
        f"- **Габариты (DX x DY x DZ):** `{abs(x2 - x1):.2f} x {abs(y2 - y1):.2f} x {abs(z2 - z1):.2f}` мм"
    )
    report.append(
        f"- **Координаты бокса (Min..Max):** X(`{x1:.1f}..{x2:.1f}`), Y(`{y1:.1f}..{y2:.1f}`), Z(`{z1:.1f}..{z2:.1f}`)"
    )
    report.append(f"- **Объем:** `{float(mip.v):.2f}` мм³\n")

    # 1. Выгружаем пользовательские переменные конструктора
    root_vars = _extract_vars_from_feature7(feat7_root)
    report.append("## 1. Таблица пользовательских переменных конструктора")
    report.append("| Имя | Выражение | Значение | Комментарий |")
    report.append("| :--- | :--- | :--- | :--- |")
    for name, expr, val, note, _ in root_vars:
        if not name.startswith("v"):
            report.append(f"| **`{name}`** | `{expr}` | `{val}` | {note} |")

    sketches_by_name = {}
    all_ents5 = _wrap(K5.ksEntityCollection, part5.EntityCollection(OBJ_SKETCH))
    for i in range(all_ents5.GetCount()):
        e = _wrap(K5.ksEntity, all_ents5.GetByIndex(i))
        sketches_by_name[e.name.strip()] = e

    # 2. Выгружаем настоящее дерево построения через IFeature7.SubFeatures
    report.append("\n## 2. Дерево построения, Эскизы и Формулы параметров")
    try:
        raw_sub = feat7_root.SubFeatures(0, True, False)
        sub_list = (
            raw_sub
            if isinstance(raw_sub, (list, tuple))
            else ([raw_sub] if raw_sub else [])
        )
    except Exception:
        sub_list = []

    step_num = 1
    for item in sub_list:
        try:
            sf = _wrap(K7.IFeature7, item)
            fname = str(sf.Name or "").strip()
            if (
                not fname
                or fname == "Начало координат"
                or fname.startswith("Плоскость")
                or fname.startswith("Ось")
            ):
                continue

            report.append(f"\n### Шаг {step_num}: `{fname}`")
            step_num += 1

            clean_name = fname.replace("(+)", "").replace("(-)", "").strip()
            if clean_name in sketches_by_name:
                geom_lines = _inspect_sketch_geometry(sketches_by_name[clean_name], sf)
                if geom_lines:
                    report.append("- **Геометрия внутри эскиза:**")
                    report.extend(geom_lines)

            f_vars = _extract_vars_from_feature7(sf)
            active_vars = [v for v in f_vars if v[4] != "Исключить из расчета"]
            if active_vars:
                report.append("- **Параметры и привязанные формулы (`v...`):**")
                for vname, vexpr, vval, vnote, vpnote in active_vars:
                    label = vpnote or vnote or "Параметр"
                    formula = (
                        f" = **`{vexpr}`**"
                        if vexpr
                        and vexpr != str(vval)
                        and vexpr != f"{vval:.1f}"
                        and vexpr != f"{int(vval)}"
                        else ""
                    )
                    report.append(f"  - `{vname}` ({label}): `{vval}`{formula}")
        except Exception:
            continue

    out_md = os.path.splitext(abs_path)[0] + "_blueprint.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"[OK BLUEPRINT] Создан слепок модели: {out_md}")
    return out_md


def main():
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if os.path.isdir(target):
            files = glob.glob(os.path.join(target, "*.m3d"))
        else:
            files = [target]
    else:
        files = glob.glob(os.path.join("example", "*.m3d"))

    if not files:
        print("[WARN] Не найдено файлов .m3d в папке example/")
        return

    for fpath in files:
        inspect_m3d(fpath)


if __name__ == "__main__":
    main()
