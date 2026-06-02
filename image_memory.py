from typing import Dict, Optional
from uuid import uuid4

_image_store: Dict[str, bytes] = {}


def store_image(image_bytes: bytes, image_key: Optional[str] = None) -> str:
    if not image_key:
        image_key = uuid4().hex
    _image_store[image_key] = image_bytes
    return image_key


def get_image(image_key: str) -> Optional[bytes]:
    return _image_store.get(image_key)
