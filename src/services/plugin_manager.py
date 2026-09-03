import concurrent.futures
import importlib.util
import inspect
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from src.models.search_item import SearchResultItem
from src.plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """
    可插拔搜索插件管理器（单例模式）。
    负责插件的自动发现、动态加载、生命周期管理与并发调度。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_lock = threading.Lock()
        self.discover_plugins()

    def discover_plugins(self, plugin_dir: Optional[str] = None):
        """
        自动扫描指定插件目录，动态导入并实例化所有继承自 BasePlugin 的类。
        """
        if not plugin_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            plugin_dir = os.path.join(base_dir, "plugins")

        if not os.path.isdir(plugin_dir):
            logger.warning(f"插件目录不存在: {plugin_dir}")
            return

        with self._plugin_lock:
            for filename in os.listdir(plugin_dir):
                if not filename.endswith(".py"):
                    continue
                if filename in ("__init__.py", "base_plugin.py"):
                    continue

                filepath = os.path.join(plugin_dir, filename)
                mod_name = f"src.plugins.{filename[:-3]}"

                try:
                    spec = importlib.util.spec_from_file_location(mod_name, filepath)
                    if not spec or not spec.loader:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            inspect.isclass(attr)
                            and issubclass(attr, BasePlugin)
                            and attr is not BasePlugin
                        ):
                            try:
                                instance = attr()
                                self._plugins[instance.name] = instance
                                logger.info(
                                    f"成功加载插件: [{instance.name}] {instance.display_name} v{instance.version}"
                                )
                            except Exception as init_err:
                                logger.error(f"插件实例化失败 ({attr_name}): {init_err}")

                except Exception as e:
                    logger.error(f"导入插件模块失败 ({filename}): {e}")

            # 应用持久化配置
            try:
                from src.services.system_config_service import get_plugin_settings
                settings = get_plugin_settings()
                for name, plugin in self._plugins.items():
                    if name in settings and "is_enabled" in settings[name]:
                        plugin.is_enabled = bool(settings[name]["is_enabled"])
            except Exception as conf_err:
                logger.warning(f"加载插件持久化配置失败: {conf_err}")

    def register_plugin(self, plugin: BasePlugin):
        """手动注册插件实例"""
        with self._plugin_lock:
            self._plugins[plugin.name] = plugin
            logger.info(f"手动注册插件成功: [{plugin.name}]")

    def reload_plugins(self, plugin_dir: Optional[str] = None) -> List[BasePlugin]:
        """重新扫描插件目录并热重载加载"""
        self.discover_plugins(plugin_dir)
        return self.get_all_plugins()

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        with self._plugin_lock:
            return self._plugins.get(name)

    def get_all_plugins(self) -> List[BasePlugin]:
        with self._plugin_lock:
            return list(self._plugins.values())

    def get_enabled_plugins(self) -> List[BasePlugin]:
        with self._plugin_lock:
            return [p for p in self._plugins.values() if p.is_enabled]

    def enable_plugin(self, name: str) -> bool:
        with self._plugin_lock:
            plugin = self._plugins.get(name)
            if plugin:
                plugin.is_enabled = True
                logger.info(f"插件已启用: {name}")
                try:
                    from src.services.system_config_service import save_plugin_status
                    save_plugin_status(name, True)
                except Exception as e:
                    logger.error(f"持久化插件 [{name}] 启用状态失败: {e}")
                return True
            return False

    def disable_plugin(self, name: str) -> bool:
        with self._plugin_lock:
            plugin = self._plugins.get(name)
            if plugin:
                plugin.is_enabled = False
                logger.info(f"插件已停用: {name}")
                try:
                    from src.services.system_config_service import save_plugin_status
                    save_plugin_status(name, False)
                except Exception as e:
                    logger.error(f"持久化插件 [{name}] 停用状态失败: {e}")
                return True
            return False


    def search_all(self, keyword: str, max_workers: int = 4) -> List[SearchResultItem]:
        """
        并发调度所有已启用的插件执行搜索，并汇聚返回标准结果。
        单插件异常或超时自动隔离，不影响整体流程。
        """
        enabled = self.get_enabled_plugins()
        if not enabled or not keyword:
            return []

        all_results: List[SearchResultItem] = []

        def _do_search(plugin: BasePlugin) -> List[SearchResultItem]:
            try:
                logger.info(f"插件 [{plugin.name}] 开始搜索: {keyword}")
                res = plugin.search(keyword)
                logger.info(f"插件 [{plugin.name}] 搜索完成，找到 {len(res)} 条结果。")
                return res
            except Exception as err:
                logger.error(f"插件 [{plugin.name}] 搜索异常: {err}")
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_plugin = {executor.submit(_do_search, p): p for p in enabled}
            for future in concurrent.futures.as_completed(future_to_plugin):
                p = future_to_plugin[future]
                try:
                    res = future.result(timeout=p.timeout + 1.0)
                    if res:
                        all_results.extend(res)
                except concurrent.futures.TimeoutError:
                    logger.warning(f"插件 [{p.name}] 搜索超时 (限制: {p.timeout}s)")
                except Exception as e:
                    logger.error(f"处理插件 [{p.name}] 结果时发生异常: {e}")

        return all_results


# 全局单例便捷访问
plugin_manager = PluginManager()
