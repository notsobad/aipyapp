from typing import Any, Dict, ClassVar
import os

from pydantic import BaseModel, Field, model_serializer, SerializationInfo

class ExecResult(BaseModel):
    """Result of the execution of a block."""
    stdout: str | None = Field(default=None, description='Standard output')
    stderr: str | None = Field(default=None, description='Standard error')
    errstr: str | None = Field(default=None, description='Error string')
    traceback: str | None = Field(default=None, description='Traceback')
    # Only used to control JSON serialization truncation; excluded from output
    serialize_max_chars: int | None = Field(
        default=128 * 1024,
        exclude=True,
        description=(
            'Max chars for JSON serialization; '
            '<=0 or None disables truncation.'
        ),
    )

    # Which fields to truncate at serialization time
    _serialize_truncate_fields: ClassVar[tuple[str, ...]] = (
        'stdout', 'stderr', 'errstr', 'traceback'
    )

    @staticmethod
    def _truncate_text(s: str | None, max_len: int | None) -> str | None:
        if s is None or max_len is None or max_len <= 0:
            return s
        if len(s) <= max_len:
            return s
        # Append a brief note so callers are aware the text was truncated
        return s[:max_len] + f"... [truncated {len(s) - max_len} chars]"

    @model_serializer(mode='wrap')
    def _serialize(self, handler, info: SerializationInfo):
        # Get base serialized data first
        data = handler(self)
        # Only truncate when serializing to JSON
        if getattr(info, 'mode', None) != 'json':
            return data

        try:
            limit = int(os.getenv('AIPY_SERIALIZE_MAX_CHARS', '0'))
        except ValueError:
            limit = self.serialize_max_chars

        if limit and limit > 0:
            for key in self._serialize_truncate_fields:
                if key in data:
                    data[key] = self._truncate_text(data.get(key), limit)
        return data

    def has_error(self) -> bool:
        return bool(self.errstr or self.traceback or self.stderr)

class ProcessResult(ExecResult):
    """Result of the execution of a process."""
    returncode: int | None = Field(
        default=None,
        description='Return code of the process',
    )

    def has_error(self) -> bool:
        return self.returncode != 0 or super().has_error()

class PythonResult(ExecResult):
    """Result of the execution of a Python block."""
    states: Dict[str, Any] | None = Field(
        default=None,
        description='States of the execution',
    )

    def has_error(self) -> bool:
        if super().has_error():
            return True
        
        try:
            states = self.states or {}
            success = bool(states.get('success', True))
        except Exception:
            success = True
        return not bool(success)