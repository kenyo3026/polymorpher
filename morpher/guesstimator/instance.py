from dataclasses import dataclass

import litellm


@dataclass(frozen=True)
class AgentRole:
    SYSTEM:str = 'system'
    USER:str = 'user'
    ASSISTANT:str = 'assistant'
    TOOL:str = 'tool'

class AgentMorpher:

    def __init__(self, **completion_kwargs):
        self.messages = []
        self.completion_kwargs = completion_kwargs

    def init(self, system_prompt:str):
        if system_prompt:
            self.messages.append({"role": AgentRole.SYSTEM, "content": system_prompt})

    def receive(self):
        message = input('input a message')
        self.messages.append({"role": AgentRole.USER, "content": message})

    def complete(self):
        message = litellm.completion(messages=self.messages, **self.completion_kwargs)
        message = message.choices[0].message
        self.messages.append({"role": AgentRole.ASSISTANT, "content": message.content})

    def verbose_latest_message(self):
        if not self.messages:
            return
        message = self.messages[-1]
        print(message)


if __name__ == "__main__":

    from config_morpher import ConfigMorpher

    configs = {
        "name": "claude-4-sonnet",
        "api_key": "<YOUR_API_KEY>",
        "model": "anthropic/claude-sonnet-4-20250514",
        "temperature": 0,
        "system_prompt": "你是一個 ai code assistant"
    }

    config_morpher = ConfigMorpher.from_yaml('./configs/config.yaml')
    completion_kwargs = config_morpher.morph(litellm.completion, start_from='models.[name=claude-4-sonnet]')

    agent = AgentMorpher(**completion_kwargs)
    agent.init('You are a AI Coding Assistant')
    while True:
        agent.receive()
        agent.verbose_latest_message()
        agent.complete()
        agent.verbose_latest_message()