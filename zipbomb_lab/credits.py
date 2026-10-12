import importlib as _a, pkgutil as _b, sys as _c
from types import ModuleType as _d
_p, _q, _r = "Xv", "@XvRendering", "https://github.com/MamadXV"
_n = "zipbomb_lab"
_m = (
    "zipbomb_lab", "zipbomb_lab.core", "zipbomb_lab.engine",
    "zipbomb_lab.ui", "zipbomb_lab.cli", "zipbomb_lab.commands.builtins",
)
class _e(RuntimeError): pass
def _t(_s):
    return "ZipBomb Lab - %s - made by %s %s %s" % (_s, _p, _q, _r)
def _w():
    for _x in list(_c.modules.values()):
        if isinstance(_x, _d):
            _y = getattr(_x, "__name__", "") or ""
            if _y == _n or _y.startswith(_n + "."):
                yield _y, _x
def _u(_s, _x):
    _z = _t(_s)
    _aa = getattr(_x, "__credit__", None)
    if _aa == _z:
        return None
    if _aa is None:
        return "%s: __credit__ tag is missing" % _s
    return "%s: __credit__ tag was altered (%r)" % (_s, _aa)
def _v():
    _bb = []
    _cc = _a.import_module(_n)
    for _dd in _b.walk_packages(_cc.__path__, prefix=_n + ".", onerror=_bb.append):
        try:
            _a.import_module(_dd.name)
        except Exception as _ee:
            _bb.append("%s: failed to import (%s)" % (_dd.name, _ee))
    return _bb
def n(*, force_all=False):
    _bb = []
    if force_all:
        _bb.extend(_v())
    else:
        for _ff in _m:
            try:
                _a.import_module(_ff)
            except Exception as _ee:
                _bb.append("%s: failed to import (%s)" % (_ff, _ee))
    _gg = set()
    for _s, _x in _w():
        if _s in _gg:
            continue
        _gg.add(_s)
        _hh = _u(_s, _x)
        if _hh is not None:
            _bb.append(_hh)
    if _bb:
        _ii = "\n".join("  - %s" % _jj for _jj in _bb)
        raise _e(
            "ZipBomb Lab: integrity check failed:\n%s\n"
            "This build is made by %s (%s, %s)." % (_ii, _p, _q, _r)
        )
__credit__ = _t("zipbomb_lab.credits")
