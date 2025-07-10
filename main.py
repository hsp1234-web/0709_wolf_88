import typer
from rich.console import Console

app = typer.Typer(help="【普羅米修斯之火】中央指揮部")
console = Console()

# ... 各作戰單元的指令將會註冊於此 ...

if __name__ == "__main__":
    app()
