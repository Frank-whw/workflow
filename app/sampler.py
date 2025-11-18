import os
from typing import List, Tuple
from PIL import Image


def list_recent_frames(root: str, max_count: int) -> List[str]:
    if not os.path.isdir(root):
        return []
    files = [os.path.join(root, f) for f in os.listdir(root) if f.lower().endswith('.bmp')]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return list(reversed(files[:max_count]))


def sample_even(paths: List[str], target: int) -> List[str]:
    if not paths or target <= 0:
        return []
    if len(paths) <= target:
        return paths
    step = len(paths) / target
    idxs = [int(i * step) for i in range(target)]
    return [paths[i] for i in idxs]


def make_collage(paths: List[str], grid: Tuple[int, int], out_path: str, canvas_size: Tuple[int, int] = (1280, 720)) -> str:
    if not paths:
        return ""
    rows, cols = grid
    w, h = canvas_size
    cell_w = w // cols
    cell_h = h // rows
    canvas = Image.new('RGB', (w, h), color=(0, 0, 0))
    for idx, p in enumerate(paths[: rows * cols]):
        try:
            img = Image.open(p).convert('RGB')
            img = img.resize((cell_w, cell_h))
            r = idx // cols
            c = idx % cols
            canvas.paste(img, (c * cell_w, r * cell_h))
        except Exception:
            continue
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, format='JPEG', quality=70)
    return out_path