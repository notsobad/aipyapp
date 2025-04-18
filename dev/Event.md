# Event 描述

全局对象 `event_bus` 负责事件注册和通知。

# Event 类型
## task_start
- 调用方式：pipeline
- 参数：prompt dict

`promot['task']` 为用户输入的任务。

## exec
- 调用方式：pipeline
- 参数：blocks dict

`blocks['main']` 为即将执行的代码块。

## result
- 调用方式：pipeline
- 参数：result dict

## response_complete
- 调用方式：broadcast
- 参数：response dict
  - llm: LLM 名称
  - content: LLM 返回消息的完整内容


