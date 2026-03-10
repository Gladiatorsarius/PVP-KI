import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import torch

from .command_bridge import CommandConnector
from .coordinator import WebSocketCoordinator
from .device_manager import get_device
from .inference_engine import InferenceEngine
from .model import PVPModel
from .ppo_trainer import PPOTrainer

log = logging.getLogger(__name__)


class Manager:
    def __init__(self):
        self._initialized = False
        self._status_listeners = []
        self.agents = {}  # For mapping agent_id to player_name, etc.

        try:
            # --- CRITICAL INITIALIZATION ORDER ---
            # 1. Device Selection
            self.device = get_device()

            # 2. Model and Trainer
            self.model = PVPModel().to(self.device)
            self.model.eval()  # Set to evaluation mode for inference
            self.trainer = PPOTrainer(self.model, device=self.device)

            # 3. Threading and Concurrency Tools
            self.model_lock = threading.RLock()
            self.inference_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Inference')

            # 4. Core Services
            self.inference_engine = InferenceEngine(self.model, self.device)
            self._coordinator = WebSocketCoordinator(
                status_hook=self._on_coordinator_status,
                inference_engine=self.inference_engine,
                inference_executor=self.inference_executor,
                model_lock=self.model_lock
            )
            self._cmd = CommandConnector(self._handle_command)
            
            self._initialized = True
            log.info("Manager initialized successfully.")

        except Exception as e:
            log.critical(f"Manager initialization failed: {e}", exc_info=True)
            # In a real app, you might want to propagate this to the UI
            self._initialized = False

    def start(self):
        """Start optional services (command listener + coordinator)."""
        if not self._initialized:
            log.error("Cannot start services, Manager initialization failed.")
            self._emit_status({'type': 'manager_error', 'error': 'Initialization failed.'})
            return

        if self._cmd:
            try:
                self._cmd.start()
                self._emit_status({'type': 'command_connector_started'})
            except Exception as exc:
                self._emit_status({'type': 'command_connector_error', 'error': str(exc)})

        self.start_coordinator()

    def stop(self):
        """Stop services cleanly, ensuring data is saved."""
        log.info("Manager stopping services...")
        # 1. Stop accepting new connections/commands
        if self._cmd:
            try:
                self._cmd.stop()
                self._emit_status({'type': 'command_connector_stopped'})
            except Exception:
                pass
        
        self.stop_coordinator()

        # 2. Process any remaining experiences
        if self.trainer:
            log.info("Flushing experience buffer...")
            # In a more complex system, you might wait for the buffer to empty
            # For now, we just trigger one last update if possible.
            self.trainer.update()

        # 3. Save final checkpoint
        if self.trainer:
            log.info("Saving final checkpoint...")
            self.trainer.save_checkpoint()
        
        # 4. Shutdown executors
        if self.inference_executor:
            self.inference_executor.shutdown(wait=True)

        log.info("Manager stopped.")

    def start_coordinator(self):
        if not self._initialized or not self._coordinator:
            self._emit_status({'type': 'coordinator_unavailable'})
            return False
        try:
            started = self._coordinator.start()
            if started:
                self._emit_status({'type': 'coordinator_start_requested'})
            return bool(started)
        except Exception as exc:
            self._emit_status({'type': 'coordinator_error', 'error': str(exc)})
            return False

    def stop_coordinator(self):
        if not self._coordinator:
            return
        try:
            self._coordinator.stop()
            self._emit_status({'type': 'coordinator_stop_requested'})
        except Exception:
            pass

    def start_all(self):
        """Global Start-All path for VM sessions that are currently ready."""
        if not self._coordinator:
            self._emit_status({'type': 'start_all_skipped', 'reason': 'coordinator_unavailable'})
            return
        self._coordinator.start_all()

    def get_coordinator_status(self):
        if not self._coordinator:
            return {}
        try:
            return self._coordinator.status_snapshot()
        except Exception:
            return {}

    def register_status_listener(self, listener):
        if listener and listener not in self._status_listeners:
            self._status_listeners.append(listener)

    def _emit_status(self, payload: dict):
        for listener in list(self._status_listeners):
            try:
                listener(payload)
            except Exception:
                pass

    def _on_coordinator_status(self, payload: dict):
        # Here you can map coordinator agent_id to player names if needed
        self._emit_status(payload)

    def _handle_command(self, cmd: dict):
        cmd_type = cmd.get('type') if isinstance(cmd, dict) else None
        if cmd_type == 'START_ALL':
            self.start_all()
        
        # Event → Reward Processing
        # Parse events from Minecraft server and assign rewards to agents
        if cmd_type == 'HIT':
            # HIT event: {"type": "HIT", "data": "AttackerName,VictimName"}
            data = cmd.get('data', '')
            parts = data.split(',')
            if len(parts) == 2:
                attacker, victim = parts
                # For now, we don't have a player_name→agent_id mapping
                # so we'll just log this. In a real system, you'd track
                # player names in the SessionRegistry or maintain a separate map.
                log.info(f"HIT event: {attacker} hit {victim}")
                # TODO: Map attacker/victim to agent_id and add reward
                # e.g., self.trainer.add_reward(agent_id_of_attacker, +1.0)
                # e.g., self.trainer.add_reward(agent_id_of_victim, -0.5)
        
        elif cmd_type == 'DEATH':
            # DEATH event: {"type": "DEATH", "data": "PlayerName"}
            player_name = cmd.get('data', '')
            log.info(f"DEATH event: {player_name} died")
            # TODO: Map player_name to agent_id and add negative reward
            # e.g., self.trainer.add_reward(agent_id, -10.0)
        
        elif cmd_type == 'ROUND_END':
            # ROUND_END event: signals the end of an episode
            log.info("ROUND_END event received")
            # TODO: For each active agent, mark episode as done
            # e.g., for agent_id in self.coordinator.registry.all_agent_ids():
            #     self.trainer.mark_episode_done(agent_id)
            # Also trigger a training update if buffer is ready
            if self.trainer and len(self.trainer.buffer) >= self.trainer.batch_size:
                log.info("Triggering training update after ROUND_END")
                update_metrics = self.trainer.update()
                if update_metrics:
                    log.info(f"Training update: {update_metrics}")
        
        log.debug(f"Received command: {cmd}")

