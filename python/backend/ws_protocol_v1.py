from typing import Any, Dict, Tuple

PROTOCOL_VERSION = 'v1'


COMMON_REQUIRED_FIELDS = (
    'protocol_version',
    'session_id',
    'agent_id',
    'episode_id',
    'timestamp_ms',
)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_incoming_message(message: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(message, dict):
        return False, 'message must be an object'

    message_type = message.get('type')
    if not isinstance(message_type, str) or not message_type:
        return False, 'missing message type'

    if message_type in {'hello', 'ready', 'heartbeat', 'stop', 'disconnect'}:
        if message.get('protocol_version') != PROTOCOL_VERSION:
            return False, 'invalid protocol_version'
        if not _is_int(message.get('agent_id')) or int(message.get('agent_id', 0)) < 1:
            return False, 'invalid agent_id'
        return True, ''

    if message_type == 'frame':
        return validate_frame_message(message)

    return False, f'unsupported message type: {message_type}'


def validate_frame_message(message: Dict[str, Any]) -> Tuple[bool, str]:
    for field in COMMON_REQUIRED_FIELDS:
        if field not in message:
            return False, f'missing {field}'

    if message.get('protocol_version') != PROTOCOL_VERSION:
        return False, 'invalid protocol_version'

    if not _is_int(message.get('agent_id')) or int(message.get('agent_id', 0)) < 1:
        return False, 'invalid agent_id'

    if not _is_int(message.get('timestamp_ms')):
        return False, 'invalid timestamp_ms'

    if not _is_int(message.get('frame_id')):
        return False, 'invalid frame_id'

    channels = message.get('channels')
    if channels != 1:
        return False, 'channels must be 1 for protocol v1'

    encoding = message.get('encoding')
    if encoding != 'jpeg':
        return False, 'encoding must be jpeg for protocol v1'

    payload_b64 = message.get('payload_b64')
    if not isinstance(payload_b64, str) or not payload_b64:
        return False, 'missing payload_b64'

    return True, ''


def default_action_payload(*, session_id: str, agent_id: int, episode_id: str, action_id: int, timestamp_ms: int) -> Dict[str, Any]:
    return {
        'type': 'action',
        'protocol_version': PROTOCOL_VERSION,
        'session_id': session_id,
        'agent_id': int(agent_id),
        'episode_id': episode_id,
        'action_id': int(action_id),
        'timestamp_ms': int(timestamp_ms),
        'movement': {
            'forward': False,
            'back': False,
            'left': False,
            'right': False,
            'jump': False,
            'sprint': False,
            'sneak': False,
            'attack': False,
            'use': False,
        },
        'look': {
            'dx': 0.0,
            'dy': 0.0,
        },
        'mouse': {
            'left_click': False,
            'right_click': False,
            'hold_ms': 0,
        },
    }
