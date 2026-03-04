from dataclasses import dataclass, field
from threading import Lock
from time import time
from typing import Any, Dict, Optional


@dataclass
class AgentSessionState:
    agent_id: int
    session_id: str
    episode_id: str
    client_role: str = 'vm-runtime'
    state: str = 'connected'
    last_frame_id: int = -1
    last_seen_ms: int = 0
    action_id: int = 0
    connected_at_ms: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)


class SessionRegistry:
    def __init__(self):
        self._lock = Lock()
        self._by_agent: Dict[int, AgentSessionState] = {}

    @staticmethod
    def _now_ms() -> int:
        return int(time() * 1000)

    def register_hello(self, *, agent_id: int, session_id: str, episode_id: str, client_role: str, capabilities: Optional[Dict[str, Any]] = None) -> AgentSessionState:
        with self._lock:
            state = AgentSessionState(
                agent_id=agent_id,
                session_id=session_id,
                episode_id=episode_id,
                client_role=client_role or 'vm-runtime',
                state='registered',
                connected_at_ms=self._now_ms(),
                last_seen_ms=self._now_ms(),
                meta={'capabilities': capabilities or {}},
            )
            self._by_agent[agent_id] = state
            return state

    def mark_ready(self, agent_id: int) -> Optional[AgentSessionState]:
        # Validate agent_id is a valid positive integer
        if not isinstance(agent_id, int) or agent_id <= 0:
            return None
        with self._lock:
            state = self._by_agent.get(agent_id)
            if not state:
                return None
            state.state = 'ready'
            state.last_seen_ms = self._now_ms()
            return state

    def mark_started(self, agent_id: int) -> Optional[AgentSessionState]:
        with self._lock:
            state = self._by_agent.get(agent_id)
            if not state:
                return None
            state.state = 'started'
            state.last_seen_ms = self._now_ms()
            return state

    def mark_running(self, agent_id: int) -> Optional[AgentSessionState]:
        with self._lock:
            state = self._by_agent.get(agent_id)
            if not state:
                return None
            state.state = 'running'
            state.last_seen_ms = self._now_ms()
            return state

    def mark_frame(self, *, agent_id: int, frame_id: int, timestamp_ms: int, episode_id: Optional[str] = None, session_id: Optional[str] = None) -> Optional[AgentSessionState]:
        with self._lock:
            state = self._by_agent.get(agent_id)
            if not state:
                return None
            if session_id:
                state.session_id = session_id
            if episode_id:
                state.episode_id = episode_id
            state.last_frame_id = frame_id
            state.last_seen_ms = timestamp_ms
            if state.state == 'started':
                state.state = 'running'
            return state

    def next_action_id(self, agent_id: int) -> int:
        with self._lock:
            state = self._by_agent.get(agent_id)
            if not state:
                return 1
            state.action_id += 1
            return state.action_id

    def disconnect(self, agent_id: int) -> Optional[AgentSessionState]:
        with self._lock:
            state = self._by_agent.get(agent_id)
            if not state:
                return None
            state.state = 'disconnected'
            state.last_seen_ms = self._now_ms()
            return state

    def get(self, agent_id: int) -> Optional[AgentSessionState]:
        with self._lock:
            return self._by_agent.get(agent_id)

    def snapshot(self) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            return {
                aid: {
                    'agent_id': st.agent_id,
                    'session_id': st.session_id,
                    'episode_id': st.episode_id,
                    'state': st.state,
                    'last_frame_id': st.last_frame_id,
                    'last_seen_ms': st.last_seen_ms,
                    'action_id': st.action_id,
                    'connected_at_ms': st.connected_at_ms,
                    'client_role': st.client_role,
                    'meta': dict(st.meta),
                }
                for aid, st in self._by_agent.items()
            }

    def ready_agent_ids(self):
        with self._lock:
            return [aid for aid, st in self._by_agent.items() if st.state == 'ready']
