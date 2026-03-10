"""
Inference Engine for the PVP-KI project.

This module is responsible for the core logic of converting a raw game frame 
into a model-predictable action. It encapsulates preprocessing, model inference,
and action post-processing.
"""
import torch
import base64
import cv2
import numpy as np
import logging
from typing import Dict, Any

# Attempt to use GPU-accelerated image decoding if available
try:
    from torchvision.io import decode_jpeg, ImageReadMode
    from torchvision.transforms.functional import to_tensor, resize
    USE_TORCHVISION = True
except ImportError:
    USE_TORCHVISION = False

log = logging.getLogger(__name__)

class InferenceEngine:
    def __init__(self, model: torch.nn.Module, device: torch.device):
        self.model = model
        self.device = device
        self.model.eval()  # Ensure model is in evaluation mode

    def _preprocess_cv2(self, jpeg_bytes: bytes) -> torch.Tensor:
        """Preprocessing using OpenCV. Fallback if torchvision is not available."""
        nparr = np.frombuffer(jpeg_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        if img is None:
            raise ValueError("Failed to decode JPEG with OpenCV")
        
        if img.shape != (64, 64):
            # This should not happen if vm_client is configured correctly, but as a safeguard:
            log.warning(f"Incorrect frame size {img.shape}, resizing to 64x64.")
            img = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA)

        # Convert to tensor, add batch and channel dimensions, normalize
        tensor = torch.from_numpy(img).float().unsqueeze(0).unsqueeze(0) / 255.0
        return tensor

    def _preprocess_torchvision(self, jpeg_bytes: bytes) -> torch.Tensor:
        """Preprocessing using torchvision for potential GPU acceleration."""
        tensor = torch.frombuffer(jpeg_bytes, dtype=torch.uint8)
        tensor = decode_jpeg(tensor, mode=ImageReadMode.GRAY) # Returns (1, H, W)
        
        if tensor.shape[1:] != (64, 64):
            log.warning(f"Incorrect frame size {tuple(tensor.shape)}, resizing to 64x64.")
            tensor = resize(tensor, [64, 64])

        # Add batch dimension, normalize
        tensor = tensor.unsqueeze(0).float() / 255.0
        return tensor

    def _map_to_protocol(self, move_logits: torch.Tensor, look_delta: torch.Tensor) -> Dict[str, Any]:
        """Maps model output tensors to the WebSocket V1 action protocol."""
        # Get discrete actions from move logits
        move_probs = torch.sigmoid(move_logits)
        move_actions = (move_probs > 0.5).squeeze().cpu().numpy()

        # Get continuous look deltas
        look_delta_cpu = look_delta.squeeze().cpu().numpy()

        action_payload = {
            "type": "action",
            "movement": {
                "w": bool(move_actions[0]), "a": bool(move_actions[1]),
                "s": bool(move_actions[2]), "d": bool(move_actions[3]),
                "jump": bool(move_actions[4])
            },
            "mouse": {
                "left_click": bool(move_actions[5]),
                "right_click": False # Not used currently
            },
            "hotbar": {
                "swap_offhand": bool(move_actions[6])
            },
            "inventory": {
                "open": bool(move_actions[7])
            },
            "look": {
                "dx": float(look_delta_cpu[0]),
                "dy": float(look_delta_cpu[1])
            }
        }
        return action_payload

    @torch.no_grad()
    def predict(self, frame_b64: str) -> Dict[str, Any]:
        """
        Main prediction function. Decodes, preprocesses, and runs inference.
        This function is thread-safe due to @torch.no_grad() and lack of side effects.
        """
        try:
            # 1. Decode Base64
            jpeg_bytes = base64.b64decode(frame_b64, validate=True)

            # 2. Preprocess Image to Tensor
            if USE_TORCHVISION:
                state_tensor = self._preprocess_torchvision(jpeg_bytes)
            else:
                state_tensor = self._preprocess_cv2(jpeg_bytes)
            
            # 3. Move tensor to the correct device
            state_tensor = state_tensor.to(self.device)

            # 4. Run Model Inference
            move_logits, look_delta, _ = self.model(state_tensor)

            # 5. Map output to action protocol
            action = self._map_to_protocol(move_logits, look_delta)
            
            return action

        except (ValueError, TypeError, base64.binascii.Error) as e:
            log.error(f"Frame decoding or preprocessing failed: {e}")
            raise  # Re-raise to be caught by the coordinator for error handling
        except Exception as e:
            log.error(f"An unexpected error occurred during inference: {e}")
            raise
