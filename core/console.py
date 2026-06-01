import questionary

from rich.console import Console, Group
from rich.theme import Theme
from rich.table import Table
from rich.live import Live
from rich.rule import Rule
from rich.panel import Panel
from rich import box

custom_style = questionary.Style([
    ("question",    "white nobold"),
    ('answer',      'green'), 
    ("selected",    "fg:default bg:default noreverse"),
])

theme = Theme({
    "text":     "not bold white",
    "info":     "bold bright_cyan",
    "success":  "not bold green",
    "warning":  "bold yellow",
    "error":    "not bold red",
    "muted":    "dim white",
    "accent":   "bright_cyan",
    "label":    "bold cyan",
})

console = Console(theme=theme)

# Prompt Helpers
def qselect(message, choices, **kwargs):
    return questionary.select(
        message,
        qmark="",
        instruction="",
        choices=choices,
        style=custom_style,
        pointer=">",
        **kwargs
    ).ask(kbi_msg="")