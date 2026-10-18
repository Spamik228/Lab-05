from pathlib import Path
import typer
from findex5.index import build_distributed_index

app = typer.Typer(help="Findex search engine CLI")

@app.callback(invoke_without_command=True)
def index(
    data_dir: Path = typer.Option(Path(r"D:\pr\findex1\data"), "--data-dir", help="Шлях до директорії з корпусом текстів"),
    workers: int = typer.Option(4, "--workers", help="Кількість воркерів (потоків/процесів)"),
    executor: str = typer.Option("serial", "--executor", help="Тип екзекутора: serial, threads, processes"),
    with_positions: bool = typer.Option(False, "--with-positions", help="Зберігати позиції термінів"),
):
    """Побудова пошукового індексу з підтримкою паралельності."""
    if not data_dir.exists():
        typer.echo(f"❌ Шлях не існує: {data_dir}", err=True)
        raise typer.Exit(code=1)

    all_paths = sorted(list(data_dir.rglob("*.txt")))
    if not all_paths:
        typer.echo(f"❌ Не знайдено .txt файлів у {data_dir}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"📂 Знайдено {len(all_paths)} файлів. Запуск побудови індексу...")
    typer.echo(f"⚙️ Режим: executor={executor}, workers={workers}")

    try:
        idx = build_distributed_index(
            all_paths=all_paths,
            workers=workers,
            executor_type=executor,
            with_positions=with_positions,
        )
        typer.echo(f"✅ Успішно побудовано! {idx}")
    except Exception as e:
        typer.echo(f"❌ Помилка під час побудови індексу: {e}", err=True)
        raise


if __name__ == "__main__":
    app()