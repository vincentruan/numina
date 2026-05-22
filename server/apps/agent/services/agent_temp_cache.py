import shutil
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

import yaml


class AgentTempCache:
    MAX_SIZE = 100
    EXPIRE_SECONDS = 1800

    def __init__(self) -> None:
        self._cache: OrderedDict[tuple[int, int], tuple[Path, float, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_create(
        self,
        agent_id: int,
        family_id: int,
        soul_md: str,
        config_data: dict,
    ) -> Path:
        key = (agent_id, family_id)
        with self._lock:
            if key in self._cache:
                dir_path, created, _ = self._cache[key]
                self._cache[key] = (dir_path, created, time.time())
                self._cache.move_to_end(key)
                return dir_path

            temp_dir = Path(tempfile.mkdtemp(prefix=f"agent_{agent_id}_f{family_id}_"))
            (temp_dir / "SOUL.md").write_text(soul_md, encoding="utf-8")
            (temp_dir / "config.yaml").write_text(yaml.dump(config_data, allow_unicode=True), encoding="utf-8")

            if len(self._cache) >= self.MAX_SIZE:
                oldest_key = next(iter(self._cache))
                oldest_dir = self._cache[oldest_key][0]
                shutil.rmtree(oldest_dir, ignore_errors=True)
                self._cache.pop(oldest_key)

            self._cache[key] = (temp_dir, time.time(), time.time())
            return temp_dir

    def invalidate(self, agent_id: int, family_id: int) -> None:
        key = (agent_id, family_id)
        with self._lock:
            if key in self._cache:
                dir_path = self._cache[key][0]
                shutil.rmtree(dir_path, ignore_errors=True)
                self._cache.pop(key)

    def cleanup_expired(self) -> None:
        now = time.time()
        with self._lock:
            to_remove = [
                key for key, (_, _, last_used) in self._cache.items()
                if now - last_used > self.EXPIRE_SECONDS
            ]
            for key in to_remove:
                dir_path = self._cache[key][0]
                shutil.rmtree(dir_path, ignore_errors=True)
                self._cache.pop(key)


agent_temp_cache = AgentTempCache()
