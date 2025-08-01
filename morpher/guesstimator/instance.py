import json
from dataclasses import dataclass
from typing import List

import litellm

from morpher.tools import TOOL_FUNCS


@dataclass(frozen=True)
class AgentRole:
    SYSTEM    :str = 'system'
    USER      :str = 'user'
    ASSISTANT :str = 'assistant'
    TOOL      :str = 'tool'

@dataclass
class ToolCallResponse:
    role         :str
    tool_call_id :str
    name         :str
    content      :str

    def form_content(self):
        return '\n'.join([f'**{key}:**\n{value}' for key, value in self.__dict__.items()
                          if not key == 'role'])

    def form_message(self):
        message = self.__dict__
        message['content'] = self.form_content()
        return message

class AgentMorpher:

    def __init__(self, tools=None, **completion_kwargs):
        self.messages = []
        self.completion_kwargs = completion_kwargs
        self.tools = tools
        self.tool_funcs = []
        if tools:
            self.completion_kwargs.update(
                {
                    'tools': tools,
                    'tool_choice': 'auto'
                }
            )
            self.tool_funcs = {
                # name:func for name, func in TOOL_FUNCS.items()
                # if name in self.tools
                tool['function']['name']:TOOL_FUNCS[tool['function']['name']] for tool in self.tools \
                if tool['function']['name'] in TOOL_FUNCS
            }

    def init(self, system_prompt:str):
        if system_prompt:
            self.messages.append({"role": AgentRole.SYSTEM, "content": system_prompt})

    def call_tool(self, tool_calls:List[litellm.types.utils.ChatCompletionMessageToolCall]):
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            if func_name in self.tool_funcs:
                try:
                    content = self.tool_funcs[func_name](**arguments)
                    content = str(content)
                except Exception as e:
                    content = f"Error executing {func_name}: {str(e)}"
            else:
                content = f"Unknown tool: {func_name}"

            tool_response = ToolCallResponse(
                role = AgentRole.TOOL,
                tool_call_id = tool_call.id,
                name = func_name,
                content = content,
            )

            self.messages.append(tool_response.form_message())
            self.verbose_latest_message()

    def receive(self):
        while True:
            message = input('Input a message: ').strip()
            if message:
                break
        self.messages.append({"role": AgentRole.USER, "content": message})
        self.verbose_latest_message()

    def complete(self):
        message = litellm.completion(messages=self.messages, **self.completion_kwargs)
        message = message.choices[0].message
        self.messages.append(message.__dict__)
        self.verbose_latest_message()

        if message.tool_calls:
            self.call_tool(message.tool_calls)
            self.complete()

    def verbose_latest_message(self):
        if not self.messages:
            return
        message = self.messages[-1]
        print(message)


if __name__ == "__main__":

    from config_morpher import ConfigMorpher

    configs = {
        "models": {
            "name": "claude-4-sonnet",
            "api_key": "<YOUR_API_KEY>",
            "model": "anthropic/claude-sonnet-4-20250514",
            "temperature": 0,
            "system_prompt": "你是一個 ai code assistant",
        },
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "load",
                    "description": "Loads the content of a file as plain text given its file path.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "The path to the file to be loaded."
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            }
        ]
    }

    config_morpher = ConfigMorpher(configs)

    completion_kwargs = config_morpher.morph(litellm.completion, start_from='models.[name=claude-4-sonnet]')
    tools = config_morpher.fetch('tools')

    agent = AgentMorpher(tools=tools, **completion_kwargs)
    agent.init('You are a AI Coding Assistant')
    while True:
        agent.receive()
        agent.complete()