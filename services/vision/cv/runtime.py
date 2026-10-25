"""Identity of the OpenCV build that ran a vision call."""

import platform

import cv2


def runtime_info() -> dict[str, str]:
    """Return the OpenCV version, file path, and CPU architecture."""
    return {
        "cv2_version": cv2.__version__,
        "cv2_path": cv2.__file__,
        "host_arch": platform.machine(),
    }
