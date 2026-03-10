from PyQt6.QtWidgets import QApplication
import sys
print("PyQt6 imported successfully")

import torch
print("Torch imported successfully after PyQt6")
print("Torch version:", torch.__version__)
print("Success - no conflict!")
