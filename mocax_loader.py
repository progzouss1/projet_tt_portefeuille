# -*- coding: utf-8 -*-
"""Rend ``import mocaxpy`` fonctionnel (MoCaX Suite). Linux ET Windows.

    from mocax_loader import load_mocax
    mocaxpy = load_mocax(search_roots=[r"C:\\...\\MoCaX\\Windows\\vs2017\\64bit"])

Natif : ``mocaxc.dll`` (Windows) / ``libmocaxc.so`` (Linux).
Sous Windows (Python >= 3.8) le PATH ne sert plus a resoudre les DLL : on
enregistre le dossier de mocaxc.dll (os.add_dll_directory), on la pre-charge
par son chemin absolu, puis on redirige les noms nus ("mocaxc.dll",
"libmocaxc.so", "mocaxc") vers ce chemin pendant l'import de mocaxpy.

mocaxpy est un simple enrobage ctypes : le code "Python 2.7" de l'editeur
tourne tel quel en Python 3 (from __future__ ...).
"""
from __future__ import print_function, division

import ctypes
import os
import re
import sys

from compat import IS_WINDOWS, default_mocax_root, fix_conda_dll_path, walk_platform

_MODULE = None
_DLL_DIR_HANDLES = []
_NATIVE_STEM = "mocaxc"


def _stem(name):
    b = os.path.basename(str(name)).lower()
    b = re.sub(r"(\.dll|\.so(\.\d+)*|\.dylib)$", "", b)
    return b[3:] if b.startswith("lib") else b


def _is_native(f):
    f = f.lower()
    return f.endswith(".dll") if IS_WINDOWS else (".so" in f)


def load_mocax(search_roots=None, verbose=True):
    """Localise, pre-charge et importe ``mocaxpy`` ; renvoie le module."""
    global _MODULE
    if _MODULE is not None:
        return _MODULE
    fix_conda_dll_path()
    roots = [r for r in (search_roots or [default_mocax_root()]) if r]

    # 1) package importable
    parent = _find_package(roots)
    if parent is None:
        raise RuntimeError("Module 'mocaxpy' introuvable sous %s (donner le dossier "
                           "...\\MoCaX\\Windows\\vs2017\\64bit)." % roots)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    if verbose:
        print("mocaxpy trouve dans :", parent)

    # 2) natif
    lib = _find_native(roots + [parent])
    if lib is None:
        raise RuntimeError("%s introuvable sous %s" % (
            "mocaxc.dll" if IS_WINDOWS else "libmocaxc.so", roots))
    lib_dir = os.path.dirname(lib)
    if IS_WINDOWS:
        if hasattr(os, "add_dll_directory"):
            _DLL_DIR_HANDLES.append(os.add_dll_directory(lib_dir))
        os.environ["PATH"] = lib_dir + os.pathsep + os.environ.get("PATH", "")
    try:
        if IS_WINDOWS:
            ctypes.CDLL(lib)
        else:
            ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
    except OSError as exc:
        raise OSError("Chargement de %s impossible : %s%s" % (lib, exc, _hint(exc)))
    if verbose:
        print("natif pre-charge :", lib)

    # 3) import avec redirection des noms nus vers le chemin absolu
    redirect = lambda n: lib if (n and _stem(n) == _NATIVE_STEM) else n
    orig_load, OrigCDLL = ctypes.cdll.LoadLibrary, ctypes.CDLL

    class _RedirectCDLL(OrigCDLL):
        def __init__(self, name, *a, **kw):
            OrigCDLL.__init__(self, redirect(name), *a, **kw)

    ctypes.cdll.LoadLibrary = lambda n: orig_load(redirect(n))
    ctypes.CDLL = _RedirectCDLL
    try:
        import mocaxpy
    finally:
        ctypes.cdll.LoadLibrary, ctypes.CDLL = orig_load, OrigCDLL
    _MODULE = mocaxpy
    if verbose:
        print("mocaxpy importe. Version :", getattr(mocaxpy, "__version__", "n/a"))
    return mocaxpy


def _hint(exc):
    s = str(exc)
    if "193" in s:
        return "\n -> WinError 193 : DLL 32 bits ; prendre le dossier 64bit."
    if "126" in s:
        return ("\n -> WinError 126 : dependance manquante, le plus souvent le runtime "
                "Visual C++ 2015-2022 x64 (vcruntime140.dll, msvcp140.dll) : installer "
                "'Microsoft Visual C++ Redistributable x64'.")
    return ""


def _find_package(roots):
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in walk_platform(root):
            if os.path.basename(dirpath) == "mocaxpy" and "__init__.py" in files:
                return os.path.dirname(dirpath)
            if "mocaxpy.py" in files:
                return dirpath
    return None


def _find_native(roots):
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in walk_platform(root):
            for f in files:
                if _is_native(f) and _stem(f) == _NATIVE_STEM:
                    return os.path.join(dirpath, f)
    return None
