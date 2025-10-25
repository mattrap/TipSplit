import os, uuid, pathlib, hashlib, platform


def get_device_id() -> str:
    cfg = pathlib.Path.home() / ".tipsplit" / "device_id.txt"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    if cfg.exists():
        return cfg.read_text().strip()
    raw = f"{uuid.uuid4()}::{platform.system()}::{platform.node()}::{platform.machine()}"
    dev = hashlib.sha256(raw.encode()).hexdigest()[:32]
    cfg.write_text(dev)
    return dev
