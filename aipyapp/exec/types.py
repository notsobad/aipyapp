from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator

class ExecResult(BaseModel):
    """Result of the execution of a block."""
    stdout: str | None = Field(default=None, description='Standard output')
    stderr: str | None = Field(default=None, description='Standard error')
    errstr: str | None = Field(default=None, description='Error string')
    traceback: str | None = Field(default=None, description='Traceback')

    def has_error(self) -> bool:
        return self.errstr or self.traceback or self.stderr

class ProcessResult(ExecResult):
    """Result of the execution of a process."""
    returncode: int | None = Field(default=None, description='Return code of the process')

    def has_error(self) -> bool:
        return self.returncode != 0 or super().has_error()

class PythonResult(ExecResult):
    """Result of the execution of a Python block."""
    states: Dict[str, Any] | None = Field(default=None, description='States of the execution')

    @model_validator(mode="after")
    def check_not_all_none(self):
        if all(not getattr(self, field) for field in self.__class__.model_fields):
            object.__setattr__(self, 'errstr', 'Strange error: all fields are None')
        return self
    
    def has_error(self) -> bool:
        if super().has_error():
            return True
        
        try:
            success = self.states['success']    
        except:
            success = False
        return not success