from typing import Optional
import os
import ctypes


class ScreenCapture:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir

    def capture_to_file(self, filename: Optional[str] = None) -> Optional[str]:
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            hdc = user32.GetDC(0)
            mdc = gdi32.CreateCompatibleDC(hdc)
            bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
            gdi32.SelectObject(mdc, bmp)
            SRCCOPY = 0x00CC0020
            gdi32.BitBlt(mdc, 0, 0, width, height, hdc, 0, 0, SRCCOPY)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", ctypes.c_uint32),
                    ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16),
                    ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32),
                    ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32),
                ]

            BI_RGB = 0
            bpp = 32
            stride = ((width * bpp + 31) // 32) * 4
            buf_size = stride * height
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = width
            bmi.biHeight = -height
            bmi.biPlanes = 1
            bmi.biBitCount = bpp
            bmi.biCompression = BI_RGB
            bmi.biSizeImage = buf_size
            buf = (ctypes.c_byte * buf_size)()
            gdi32.GetDIBits(mdc, bmp, 0, height, ctypes.byref(buf), ctypes.byref(bmi), 0)

            if not filename:
                filename = f"frame_{ctypes.windll.kernel32.GetTickCount64()}.bmp"
            os.makedirs(self.out_dir, exist_ok=True)
            path = os.path.join(self.out_dir, filename)

            file_header = bytearray()
            file_size = 14 + ctypes.sizeof(BITMAPINFOHEADER) + buf_size
            file_header.extend(b"BM")
            file_header.extend(file_size.to_bytes(4, "little"))
            file_header.extend((0).to_bytes(2, "little"))
            file_header.extend((0).to_bytes(2, "little"))
            offset = 14 + ctypes.sizeof(BITMAPINFOHEADER)
            file_header.extend(offset.to_bytes(4, "little"))

            with open(path, "wb") as f:
                f.write(file_header)
                f.write(bytes(ctypes.string_at(ctypes.byref(bmi), ctypes.sizeof(BITMAPINFOHEADER))))
                f.write(bytes(buf))

            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mdc)
            user32.ReleaseDC(0, hdc)
            return path
        except Exception:
            return None