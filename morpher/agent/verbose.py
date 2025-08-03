import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass(frozen=True)
class VerboseStyle:
    SIMPLE: str = 'simple'
    PRETTY: str = 'pretty'
    COMPACT: str = 'compact'

    @classmethod
    def get_values(cls) -> List[str]:
        """Get all available verbose style values"""
        instance = cls()
        return [value for value in instance.__dict__.values()]

    @classmethod
    def is_valid(cls, style: str) -> bool:
        """Check if a style string is valid"""
        return style.lower() in cls.get_values()


class BaseMessageVerboser(ABC):
    """Abstract base class for message verbosers"""

    @abstractmethod
    def verbose_message(self, message: Dict[str, Any]) -> None:
        """Display a message in a specific format"""
        pass


class SimpleMessageVerboser(BaseMessageVerboser):
    """Simple message verboser that prints raw message"""

    def verbose_message(self, message: Dict[str, Any]) -> None:
        print(message)


class CompactMessageVerboser(BaseMessageVerboser):
    """Compact message verboser for minimal output"""

    def verbose_message(self, message: Dict[str, Any]) -> None:
        role = message.get('role', 'unknown')
        content = message.get('content', '')

        # Display in compact format
        if role == 'tool':
            func_name = message.get('name', 'unknown')
            print(f"🔧 {func_name}: {content[:50]}{'...' if len(content) > 50 else ''}")
        elif role == 'assistant':
            if message.get('tool_calls'):
                tool_names = [tc.function.name for tc in message.get('tool_calls', [])]
                print(f"🤖 Calling tools: {', '.join(tool_names)}")
            if content:
                print(f"🤖 {content[:80]}{'...' if len(content) > 80 else ''}")
        else:
            print(f"{'👤' if role == 'user' else '🔧'} {content[:80]}{'...' if len(content) > 80 else ''}")


class PrettyMessageVerboser(BaseMessageVerboser):
    """Pretty formatted message verboser with colors and structure"""

    def __init__(self, 
                 max_content_length: int = 1000,
                 max_tool_result_length: int = 500,
                 max_arg_length: int = 100,
                 show_colors: bool = True):
        self.max_content_length = max_content_length
        self.max_tool_result_length = max_tool_result_length
        self.max_arg_length = max_arg_length
        self.show_colors = show_colors

        # Set role colors and titles
        self.role_colors = {
            'system': '\033[95m',      # Purple
            'user': '\033[92m',        # Green
            'assistant': '\033[94m',   # Blue
            'tool': '\033[93m'         # Yellow
        } if show_colors else {}

        self.reset_color = '\033[0m' if show_colors else ''

        self.role_titles = {
            'system': '🔧 System',
            'user': '👤 User',
            'assistant': '🤖 Assistant',
            'tool': '⚡ Tool'
        }

    def verbose_message(self, message: Dict[str, Any]) -> None:
        role = message.get('role', 'unknown')

        color = self.role_colors.get(role, '\033[97m' if self.show_colors else '')
        title = self.role_titles.get(role, f'❓ {role.title()}')

        print(f"\n{color}{'='*60}")
        print(f"{title}")
        print(f"{'='*60}{self.reset_color}")

        # Handle different role types
        if role == 'tool':
            self._handle_tool_message(message, color)
        elif role == 'assistant':
            self._handle_assistant_message(message, color)
        else:
            self._handle_general_message(message, color)

        print(f"{color}{'='*60}{self.reset_color}\n")

    def _handle_tool_message(self, message: Dict[str, Any], color: str) -> None:
        """Handle tool response messages"""
        print(f"{color}Tool Call ID:{self.reset_color} {message.get('tool_call_id', 'N/A')}")
        print(f"{color}Function:{self.reset_color} {message.get('name', 'N/A')}")
        print(f"{color}Result:{self.reset_color}")

        content = message.get('content', '')
        if len(content) > self.max_tool_result_length:
            print(f"  {content[:self.max_tool_result_length]}...")
            print(f"  {color}[Content truncated - {len(content)} total chars]{self.reset_color}")
        else:
            print(f"  {content}")

    def _handle_assistant_message(self, message: Dict[str, Any], color: str) -> None:
        """Handle assistant messages"""
        content = message.get('content')
        if content:
            print(f"{color}Response:{self.reset_color}")
            print(f"  {content}")

        # Handle tool calls
        tool_calls = message.get('tool_calls')
        if tool_calls:
            print(f"\n{color}Tool Calls:{self.reset_color}")
            for i, tool_call in enumerate(tool_calls, 1):
                func_name = tool_call.function.name
                arguments = tool_call.function.arguments
                print(f"  {i}. {color}{func_name}{self.reset_color}")
                try:
                    args_dict = json.loads(arguments)
                    for key, value in args_dict.items():
                        if isinstance(value, str) and len(value) > self.max_arg_length:
                            value = f"{value[:self.max_arg_length]}..."
                        print(f"     {key}: {value}")
                except:
                    print(f"     Raw args: {arguments}")

    def _handle_general_message(self, message: Dict[str, Any], color: str) -> None:
        """Handle system and user messages"""
        content = message.get('content', '')
        if len(content) > self.max_content_length:
            print(f"  {content[:self.max_content_length]}...")
            print(f"  {color}[Content truncated - {len(content)} total chars]{self.reset_color}")
        else:
            print(f"  {content}")


# Factory function for convenience
class VerboserFactory:
    """Factory class to create message verbosers"""

    @staticmethod
    def get(style: str = 'pretty', **kwargs) -> BaseMessageVerboser:
        """Create verboser instance based on style"""
        if style == 'simple':
            return SimpleMessageVerboser()
        elif style == 'compact':
            return CompactMessageVerboser()
        elif style == 'pretty':
            return PrettyMessageVerboser(**kwargs)
        else:
            raise ValueError(f"Unknown verboser style: {style}")

    @staticmethod
    def get_available_styles() -> List[str]:
        """Get all available verboser styles"""
        return VerboseStyle.get_values()


if __name__ == "__main__":

    # Test VerboseStyle
    print(VerboseStyle.get_values())  # ['simple', 'pretty', 'compact']
    print(VerboseStyle.is_valid('pretty'))  # True
    print(VerboseStyle.is_valid('invalid'))  # False
    print(VerboseStyle.PRETTY)  # 'pretty'

    # Test Verboser
    # Initialize test message
    message = {
        'role': 'assistant',
        'content': 'Hello! I can help you with that.',
        'tool_calls': None
    }

    # Test pretty verboser
    pretty = VerboserFactory('pretty')
    pretty.verbose_message(message)

    # Test compact verboser
    compact = VerboserFactory('compact')
    compact.verbose_message(message)