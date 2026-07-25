"""
MailMind AI Developer CLI Voice Client - Terminal UI Renderer.

Architectural Decision Rationale:
---------------------------------
1. Single Responsibility: Formats and displays colored terminal cards, headers, status lines, VAD state updates,
   STT transcripts, and conversation engine prompt outputs.
2. Resilient Color Fallback: Uses `colorama` for cross-platform ANSI color formatting (Windows, Linux, macOS)
   with automatic plain-text fallback if `colorama` is missing or stdout is redirected.
3. Extensible Milestone Cards: Includes generic card rendering methods for future milestones (Milestones 7-12:
   LLM assistant responses, tool execution, email actions, RAG retrieval).
"""

# Try importing colorama safely with plain-text fallback
try:
    import colorama
    from colorama import Fore, Style
    colorama.init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

    class ForeFallback:
        GREEN = ""
        YELLOW = ""
        RED = ""
        CYAN = ""
        BLUE = ""
        MAGENTA = ""
        WHITE = ""
        RESET = ""

    class StyleFallback:
        BRIGHT = ""
        DIM = ""
        RESET_ALL = ""

    Fore = ForeFallback()  # type: ignore[assignment, misc]
    Style = StyleFallback()  # type: ignore[assignment, misc]


class TerminalUI:
    """
    Renders styled CLI terminal elements, status indicators, and event cards.
    """

    def __init__(self, use_color: bool = True) -> None:
        self.use_color: bool = use_color and HAS_COLORAMA

    def print_header(self, server_url: str, sample_rate: int) -> None:
        """
        Renders application welcome banner.
        """
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
        print(f"{Fore.CYAN}{Style.BRIGHT}       MailMind AI Developer Voice Client")
        print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}")
        print(f"{Fore.WHITE} Server URL : {Fore.YELLOW}{server_url}")
        print(f"{Fore.WHITE} Audio Spec : {Fore.YELLOW}{sample_rate}Hz 16-bit PCM Mono (50ms chunks)")
        print(f"{Fore.CYAN}{'-' * 60}\n")

    def print_status(self, status: str, session_id: str | None = None, message: str = "") -> None:
        """
        Renders connection lifecycle status update.
        """
        status_upper = status.upper()
        if status_upper == "CONNECTED":
            badge = f"{Fore.GREEN}{Style.BRIGHT}[CONNECTED]"
            sess_info = f" | Session ID: {Fore.YELLOW}{session_id}" if session_id else ""
            print(f"{badge}{sess_info} {Fore.WHITE}{message}")
            print(f"{Fore.CYAN}{Style.BRIGHT}[LISTENING...] Speak into your microphone. VAD & STT active.\n")
        elif status_upper in ["RECONNECTING", "CONNECTING"]:
            badge = f"{Fore.YELLOW}{Style.BRIGHT}[{status_upper}]"
            print(f"{badge} {Fore.WHITE}{message}")
        elif status_upper in ["DISCONNECTED", "FAILED", "CLOSED"]:
            badge = f"{Fore.RED}{Style.BRIGHT}[{status_upper}]"
            print(f"{badge} {Fore.WHITE}{message}")
        else:
            print(f"{Fore.BLUE}[STATUS] {status}: {message}")

    def print_vad_event(self, state: str, details: str = "") -> None:
        """
        Renders Voice Activity Detection (VAD) state transitions.
        """
        state_str = state.lower()
        if "started" in state_str:
            badge = f"{Fore.GREEN}[VAD] {state}"
        elif "active" in state_str:
            badge = f"{Fore.GREEN}{Style.BRIGHT}[VAD] {state}"
        elif "silence" in state_str:
            badge = f"{Fore.YELLOW}[VAD] {state}"
        elif "complete" in state_str:
            badge = f"{Fore.CYAN}{Style.BRIGHT}[VAD] {state}"
        else:
            badge = f"{Fore.BLUE}[VAD] {state}"

        extra = f" ({details})" if details else ""
        print(f" {badge}{Fore.WHITE}{extra}")

    def print_transcript(self, text: str, processing_ms: float = 0.0, provider: str = "groq") -> None:
        """
        Renders Speech-To-Text (STT) transcript card.
        """
        print(f"\n{Fore.CYAN}{'-' * 50}")
        print(f"{Fore.CYAN}{Style.BRIGHT}[STT TRANSCRIPT]")
        print(f"{Fore.WHITE} Text       : {Fore.GREEN}{Style.BRIGHT}{text}")
        print(f"{Fore.WHITE} Provider   : {Fore.YELLOW}{provider}")
        print(f"{Fore.WHITE} Latency    : {Fore.YELLOW}{processing_ms:.1f} ms")
        print(f"{Fore.CYAN}{'-' * 50}\n")

    def print_conversation_ready(
        self, turn: int, history_length: int, latest_message: str, prompt: str
    ) -> None:
        """
        Renders Conversation Intelligence Engine ready card with prompt inspection.
        """
        print(f"\n{Fore.YELLOW}{'=' * 50}")
        print(f"{Fore.YELLOW}{Style.BRIGHT}[CONVERSATION READY - ENGINE PREPARED]")
        print(f"{Fore.WHITE} Turn Number   : {Fore.CYAN}{turn}")
        print(f"{Fore.WHITE} History Size  : {Fore.CYAN}{history_length} turns")
        print(f"{Fore.WHITE} User Message  : {Fore.GREEN}{latest_message}")
        print(f"{Fore.WHITE} Prompt Preview:")
        print(f"{Fore.BLUE}{Style.DIM}{prompt}")
        print(f"{Fore.YELLOW}{'=' * 50}\n")

    def print_error(self, code: str, message: str) -> None:
        """
        Renders structured error card.
        """
        print(f"\n{Fore.RED}{Style.BRIGHT}[ERROR - {code}]")
        print(f"{Fore.RED}{message}\n")

    def print_future_event(self, event_type: str, payload: dict) -> None:
        """
        Generic fallback renderer for future milestone events (Milestones 7-12).
        """
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}[FUTURE EVENT: {event_type.upper()}]")
        for k, v in payload.items():
            print(f"{Fore.WHITE} {k:<15}: {Fore.YELLOW}{v}")
        print(f"{Fore.MAGENTA}{'-' * 50}\n")
