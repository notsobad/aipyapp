# Strongly-Typed Event System Guide

## Overview

The new strongly-typed event system provides type-safe event handling for the aipy project while maintaining backward compatibility.

## Key Features

### 1. Strongly-Typed Event Definitions
- Events defined using Pydantic models
- Type validation and IDE autocompletion support
- Clear event data structure definitions

### 2. Backward Compatibility
- Existing `event.data.get()` approach continues to work
- Automatic fallback: degrading to base events when type validation fails
- Support for unregistered event types

### 3. Error Handling
- Graceful error handling mechanism
- Automatic degradation on type validation failure
- Detailed error logging

## Event Types

### Task Lifecycle Events
- `TaskStartEvent`: Task start
- `TaskEndEvent`: Task end
- `RoundStartEvent`: Round start
- `RoundEndEvent`: Round end
- `TaskStatusEvent`: Task status update

### LLM Interaction Events
- `QueryStartEvent`: Query start
- `ResponseCompleteEvent`: Response complete
- `StreamStartEvent`: Stream start
- `StreamEndEvent`: Stream end
- `StreamEvent`: Stream data

### Code Operation Events
- `ExecEvent`: Code execution start
- `ExecResultEvent`: Code execution result
- `EditEvent`: Code edit (legacy compatibility)
- `EditStartEvent`: Code edit start
- `EditResultEvent`: Code edit result

### Tool Calling Events
- `ToolCallResultEvent`: Tool call result
- `McpCallEvent`: MCP tool call
- `McpResultEvent`: MCP tool call result
- `CallFunctionEvent`: Function call
- `CallFunctionResultEvent`: Function call result

### System Events
- `ExceptionEvent`: Exception event
- `RuntimeMessageEvent`: Runtime message
- `RuntimeInputEvent`: Runtime input
- `ShowImageEvent`: Show image
- `UploadResultEvent`: Upload result

## Usage

### 1. In Existing Code (Recommended Progressive Migration)

```python
# Existing approach (continues to work)
def on_task_start(self, event):
    instruction = event.data.get('instruction')
    task_id = event.data.get('task_id')

# New strongly-typed approach
def on_task_start(self, event):
    instruction = event.instruction  # Type-safe, IDE support
    task_id = event.task_id         # Autocompletion
```

### 2. Emitting Events in Task Class

```python
# Existing approach (no changes needed)
self.emit('task_start', instruction=instruction, task_id=self.task_id, title=title)

# Event will be automatically created as TaskStartEvent type
```

### 3. Registering New Event Types

```python
from aipyapp.aipy.events import EventFactory, BaseEvent
from typing import Literal

class CustomEvent(BaseEvent):
    name: Literal["custom_event"] = "custom_event"
    custom_field: str = Field(..., title="Custom Field", description="A custom field")

# Register event type
EventFactory.register_event("custom_event", CustomEvent)
```

## Migration Strategy

### Phase 1: No Changes Required
- Existing code continues to work normally
- Event emission approach unchanged
- Event handling approach remains compatible

### Phase 2: Progressive Optimization
- Change `event.data.get('field')` to `event.field`
- Enjoy type safety and IDE support
- Prioritize core event handlers

### Phase 3: Full Type Safety
- Add type annotations to plugins
- Use strongly-typed event parameters
- Remove redundant `event.data` access

## Example Code

```python
from aipyapp.aipy.events import TypedEventBus

# Create event bus
bus = TypedEventBus()

# Register handler
def handle_task_start(event):
    print(f"Task started: {event.instruction}")
    print(f"Task ID: {event.task_id}")
    print(f"Title: {event.title}")

bus.on_event("task_start", handle_task_start)

# Emit event
event = bus.emit("task_start", 
                instruction="Test task", 
                task_id="123", 
                title="Test title")

# Type-safe access
print(f"Instruction: {event.instruction}")
print(f"Timestamp: {event.timestamp}")
```

## Field Documentation

Each event field now includes:
- **title**: Short field name for forms/UI
- **description**: Detailed field description for documentation

Example:
```python
instruction: str = Field(..., title="Instruction", description="User instruction for the task")
```

## Notes

1. **Backward Compatibility**: All existing code works without modification
2. **Error Handling**: Type validation failures automatically degrade, won't break the program
3. **Performance**: Pydantic validation has slight overhead, but acceptable for event systems
4. **Extensibility**: Easy to add new event types and fields

## Debugging and Troubleshooting

### Check if Events Are Registered
```python
from aipyapp.aipy.events import EventFactory
print(EventFactory.get_registered_events())
```

### Check Event Type
```python
def debug_handler(event):
    print(f"Event type: {type(event._typed_event)}")
    print(f"Event data: {event.data}")
```

### Enable Debug Logging
Strongly-typed event creation failures will print warning messages to help diagnose issues.

## About Field Parameters

### Why `Field(...)`?
- `...` (Ellipsis) = required field, no default value
- `Field(default="value")` = optional field with default value
- `Field(default_factory=lambda: value)` = optional field with dynamic default

### Why `description` instead of `title`?
- **`title`**: Short field label for forms/UI
- **`description`**: Detailed field description for documentation and help

Both are used together for comprehensive field documentation.