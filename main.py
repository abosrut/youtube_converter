import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich import box
import time
import os
import subprocess

# Попытка импортировать Pillow для конвертации изображений
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


# --- Глобальные объекты и константы ---
console = Console()
APP_VERSION = "5.1" # Обновили версию
EXCLUDED_FILES = ['downloader.py', 'ffmpeg.exe', 'ffplay.exe', 'ffprobe.exe']

# --- Абсолютный путь к FFmpeg для надежности ---
script_dir = os.path.dirname(os.path.abspath(__file__))
ffmpeg_path = os.path.join(script_dir, 'ffmpeg.exe')

# --- Создаем папку для загрузок, чтобы избежать проблем с правами доступа ---
DOWNLOADS_DIR = os.path.join(script_dir, "Downloads")
try:
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
except OSError as e:
    console.print(f"[bold red]Критическая ошибка: не удалось создать папку 'Downloads': {e}[/bold red]")
    DOWNLOADS_DIR = script_dir # В случае ошибки, пытаемся сохранить в текущую папку

# --- UI Функции и константы ---
MAIN_HEADER_ART = f"""
[bold cyan]
 ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗██████╗ ████████╗ ██████╗ ██████╗
██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗
██║     ██║   ██║██╔██╗ ██║██║   ██║█████╗  ██████╔╝   ██║   ██║   ██║██████╔╝
██║     ██║   ██║██║╚██╗██║██║   ██║██╔══╝  ██╔══██╗   ██║   ██║   ██║██╔══██╗
╚██████╗╚██████╔╝██║ ╚████║╚██████╔╝███████╗██║  ██║   ██║   ╚██████╔╝██║  ██║
 ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
[/bold cyan]
[dim]CLI Edition v{APP_VERSION}[/dim]
"""

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    clear_screen()
    console.print(MAIN_HEADER_ART, justify="center")
    console.print("─" * console.width)

def show_error(message, details=""):
    console.print(Panel(f"[bold]ОШИБКА:[/bold] {message}\n[dim]{details}[/dim]", title="[bold red]СИСТЕМНОЕ СООБЩЕНИЕ[/bold red]", border_style="red"))

def show_success(message):
    console.print(Panel(f"[bold]УСПЕХ:[/bold] {message}", title="[bold green]СИСТЕМНОЕ СООБЩЕНИЕ[/bold green]", border_style="green"))

def prompt_input():
    return console.input(f"[bold]Выберите функцию: [/bold]")

def list_files_in_dir():
    """Сканирует и отображает доступные для конвертации файлы."""
    try:
        files = [f for f in os.listdir(script_dir) if os.path.isfile(os.path.join(script_dir, f)) and f not in EXCLUDED_FILES]
        if not files:
            console.print("[yellow]В текущей папке нет подходящих файлов для конвертации.[/yellow]")
            return False
        
        table = Table(title="[bold]Доступные файлы в папке[/bold]", box=box.SIMPLE_HEAD, padding=(0, 1))
        table.add_column("Имя файла", style="cyan")
        for f in files:
            table.add_row(f)
        console.print(table)
        return True
    except Exception as e:
        show_error("Не удалось прочитать файлы в папке.", str(e))
        return False

# --- Логика скачивания ---
progress_bar = Progress(TextColumn("[bold cyan]{task.fields[filename]}", justify="right"), BarColumn(bar_width=None), "[progress.percentage]{task.percentage:>3.1f}%", "•", DownloadColumn(), "•", TransferSpeedColumn(), "•", TimeRemainingColumn(), console=console, transient=True)
task_id = None
def progress_hook(d):
    global task_id
    if d['status'] == 'downloading':
        if task_id is None: 
            task_id = progress_bar.add_task("download", filename=d.get('filename', '...'), total=d.get('total_bytes') or d.get('total_bytes_estimate'))
        progress_bar.update(task_id, completed=d.get('downloaded_bytes'))
    # Убрали сброс task_id при 'finished', чтобы он не создавал новую строку для аудио/видео

def download_logic(search_prefix=""):
    """Общая логика для скачивания по ссылке или названию."""
    global task_id
    task_id = None # Сбрасываем ID задачи перед каждой новой загрузкой

    query = console.input("[bold]Введите URL или поисковый запрос: [/bold]")
    if not query.strip(): return
    
    if not (query.startswith("http://") or query.startswith("https://")):
        query = f"{search_prefix}{query}"
        
    while True:
        choice = console.input("[bold]Выберите формат ([1] Видео, [2] Аудио): [/bold]")
        if choice in ["1", "2"]: break
        else: show_error("Неверная команда.")
    is_audio = (choice == "2")

    if is_audio and not os.path.exists(ffmpeg_path):
        show_error("'ffmpeg.exe' не найден.", "Для сохранения в MP3 он необходим."); return

    ydl_opts = {
        'progress_hooks': [progress_hook], 'noplaylist': True, 'quiet': True, 'no_warnings': True,
        'default_search': 'auto',
    }
    if is_audio:
        ydl_opts.update({
            'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'), 'ffmpeg_location': ffmpeg_path
        })
    else:
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'outtmpl': os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s'), 'merge_output_format': 'mp4'
        })
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            with console.status("[bold yellow]Поиск и анализ...", spinner="dots"):
                info = ydl.extract_info(query, download=False)
                entry = info['entries'][0] if 'entries' in info else info
                title = entry.get('title', 'Неизвестное медиа')
                url_to_download = entry.get('webpage_url')
            
            console.print(f"\n[dim]Найдено: [white]'{title}'[/white]. Начинаю загрузку...[/dim]")
            with progress_bar: ydl.download([url_to_download])
            
            final_filename = ydl.prepare_filename(entry)
            if is_audio: final_filename = os.path.splitext(final_filename)[0] + ".mp3"
            
            relative_path = os.path.relpath(final_filename, script_dir)
            show_success(f"Файл сохранен в папку 'Downloads' как: [bold white]{os.path.basename(relative_path)}[/bold white]")

    except Exception as e:
        show_error("Не удалось скачать медиа.", str(e))

# --- Логика конвертации ---
def convert_image(input_filename, target_format):
    full_input_path = os.path.join(script_dir, input_filename)
    if not os.path.exists(full_input_path):
        show_error(f"Файл '{input_filename}' не найден."); return
    output_filename = os.path.splitext(full_input_path)[0] + f".{target_format}"
    try:
        with console.status(f"[bold yellow]Конвертация...", spinner="bouncingBar"):
            with Image.open(full_input_path) as img:
                if target_format == 'ico':
                    img.save(output_filename, format='ICO', sizes=[(16, 16), (32, 32), (48, 48)])
                else:
                    if img.mode in ['RGBA', 'P'] and target_format.lower() in ['jpg', 'jpeg']:
                        img = img.convert('RGB')
                    img.save(output_filename)
        show_success(f"Файл сохранен как: [bold white]{os.path.basename(output_filename)}[/bold white]")
    except Exception as e:
        show_error("Ошибка во время конвертации изображения.", str(e))

def convert_audio(input_filename, target_format, options):
    full_input_path = os.path.join(script_dir, input_filename)
    if not os.path.exists(full_input_path):
        show_error(f"Файл '{input_filename}' не найден."); return
    output_file = os.path.splitext(full_input_path)[0] + f".{target_format}"
    command = [ffmpeg_path, '-i', full_input_path, '-y'] + options + [output_file]
    try:
        with console.status(f"[bold yellow]Конвертация...", spinner="earth"):
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        show_success(f"Файл сохранен как: [bold white]{os.path.basename(output_file)}[/bold white]")
    except subprocess.CalledProcessError as e:
        show_error("Ошибка во время конвертации.", e.stderr.decode('utf-8', errors='ignore'))

# --- Главное меню ---
def main():
    if not PILLOW_AVAILABLE:
        show_error("Библиотека 'Pillow' не установлена.", "Выполните: pip install Pillow")
        time.sleep(3)

    command_map = {
        # Медиа
        '1': lambda: download_logic("ytsearch:"),
        '2': lambda: download_logic("scsearch:"),
        '3': lambda: download_logic("spsearch:"),
        # Изображения
        '11': lambda: run_converter("конвертер JPG -> PNG", lambda filename: convert_image(filename, 'png')),
        '12': lambda: run_converter("конвертер PNG -> JPG", lambda filename: convert_image(filename, 'jpg')),
        '13': lambda: run_converter("конвертер WEBP -> PNG", lambda filename: convert_image(filename, 'png')),
        '14': lambda: run_converter("конвертер PNG -> ICO", lambda filename: convert_image(filename, 'ico')),
        # Аудио
        '21': lambda: run_converter("конвертер MP3 -> M4A", lambda filename: convert_audio(filename, 'm4a', ['-c:a', 'aac'])),
        '22': lambda: run_converter("конвертер M4A -> MP3", lambda filename: convert_audio(filename, 'mp3', ['-b:a', '192k'])),
        '23': lambda: run_converter("конвертер WAV -> MP3", lambda filename: convert_audio(filename, 'mp3', ['-b:a', '192k'])),
        '24': lambda: run_converter("конвертер MP3 -> OGG", lambda filename: convert_audio(filename, 'ogg', ['-c:a', 'libvorbis'])),
        '25': lambda: run_converter("конвертер OGG -> MP3", lambda filename: convert_audio(filename, 'mp3', ['-b:a', '192k'])),
    }

    while True:
        print_header()
        
        main_grid = Table.grid(expand=True)
        main_grid.add_column(); main_grid.add_column(); main_grid.add_column()
        
        media_table = Table(title="[bold]Медиа[/bold]", box=None, show_header=False, title_justify="left")
        image_table = Table(title="[bold]Изображения[/bold]", box=None, show_header=False, title_justify="left")
        audio_table = Table(title="[bold]Аудио[/bold]", box=None, show_header=False, title_justify="left")

        media_table.add_row("[cyan][1][/cyan] YouTube", "Загрузка")
        media_table.add_row("[cyan][2][/cyan] SoundCloud", "Загрузка")
        media_table.add_row("[cyan][3][/cyan] Spotify", "Загрузка")

        image_table.add_row("[cyan][11][/cyan] JPG", "-> PNG")
        image_table.add_row("[cyan][12][/cyan] PNG", "-> JPG")
        image_table.add_row("[cyan][13][/cyan] WEBP", "-> PNG")
        image_table.add_row("[cyan][14][/cyan] PNG", "-> ICO")

        audio_table.add_row("[cyan][21][/cyan] MP3", "-> M4A")
        audio_table.add_row("[cyan][22][/cyan] M4A", "-> MP3")
        audio_table.add_row("[cyan][23][/cyan] WAV", "-> MP3")
        audio_table.add_row("[cyan][24][/cyan] MP3", "-> OGG")
        audio_table.add_row("[cyan][25][/cyan] OGG", "-> MP3")

        main_grid.add_row(media_table, image_table, audio_table)
        
        console.print(Panel(main_grid, border_style="dim"))
        console.print("[dim][q] Выход[/dim]")
        
        choice = prompt_input()

        if choice.lower() == 'q':
            console.print("\n[bold red]Отключение.[/bold red]"); break
        
        if choice in command_map:
            command_map[choice]()
            console.input("\n[dim]Нажмите Enter для возврата в меню...[/dim]")
        else:
            show_error("Неверная команда."); time.sleep(1)

def run_converter(title, func):
    """Общая логика для запуска любого конвертера."""
    print_header(title)
    if not list_files_in_dir():
        return
    filename = console.input("[bold]Имя файла для конвертации: [/bold]")
    func(filename)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Процесс прерван. Отключение.[/bold red]")

