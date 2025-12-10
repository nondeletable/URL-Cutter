import os
import shutil
import tempfile


def cleanup_temp_meipass():
    temp_dir = tempfile.gettempdir()
    for name in os.listdir(temp_dir):
        if name.startswith("_MEI"):
            path = os.path.join(temp_dir, name)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
            except Exception:
                # тихо игнорируем, если папка занята системой
                pass


cleanup_temp_meipass()
