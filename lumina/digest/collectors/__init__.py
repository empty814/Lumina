"""
lumina/digest/collectors — 各数据源采集函数包

约定：在此包下的子模块（base 除外）中，所有名为 collect_* 的函数
自动被发现并注册到 COLLECTORS 列表。新增数据源只需建文件、写函数，
无需修改本文件。
"""
import importlib
import pkgutil
from pathlib import Path

from lumina.digest.collectors.base import Collector

_SKIP_MODULES = {"base"}


def _discover() -> list[Collector]:
    """扫描包内所有子模块，收集满足 Collector Protocol 的 collect_* 函数。"""
    discovered: list[Collector] = []
    pkg_path = str(Path(__file__).parent)
    for mod_info in pkgutil.iter_modules([pkg_path]):
        if mod_info.name in _SKIP_MODULES:
            continue
        mod = importlib.import_module(f"{__package__}.{mod_info.name}")
        for attr_name in dir(mod):
            if not attr_name.startswith("collect_"):
                continue
            obj = getattr(mod, attr_name)
            if callable(obj) and isinstance(obj, Collector):
                discovered.append(obj)
    return discovered


COLLECTORS = _discover()
