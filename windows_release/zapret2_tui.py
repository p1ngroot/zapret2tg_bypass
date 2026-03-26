#!/usr/bin/env python3
"""
Zapret2 TUI - Легковесный TUI интерфейс для обхода блокировок Telegram на Windows
Использует winws2 (WinDivert) для перехвата и модификации трафика
"""

import asyncio
import subprocess
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Button, Label, Static, Input, Checkbox, Select, Log
from textual.binding import Binding
from textual.screen import Screen
from textual.reactive import reactive
import psutil


# Конфигурация по умолчанию для Telegram
TELEGRAM_CONFIG = {
    "name": "Telegram",
    "enabled": True,
    "ports_tcp": "443,80,88,8080",
    "ports_udp": "443,3478,3479,3480,3481,5222,5223,5224,8888,9898,9899,9900,10000-10100",
    "strategies": [
        {
            "name": "TLS Fake",
            "enabled": True,
            "lua_desync": "fake:blob=fake_default_tls:badsum:repeats=2",
            "filter_l7": "tls",
            "hostlist": "telegram.org,t.me,telegram.me,tg.dev"
        },
        {
            "name": "Multisplit",
            "enabled": True,
            "lua_desync": "multisplit:pos=2,host+1:badsum",
            "filter_l7": "tls,http",
            "hostlist": "telegram.org,t.me,telegram.me"
        },
        {
            "name": "UDP Length",
            "enabled": True,
            "lua_desync": "udplen:increment=2",
            "filter_l7": "quic,discord,stun",
            "ports_udp": "443,3478,3479,3480,3481"
        }
    ],
    "wf_raw_filter": "",
    "autohostlist": True,
    "debug": False
}

DEFAULT_CONFIG = {
    "telegram": TELEGRAM_CONFIG,
    "global": {
        "debug": False,
        "daemon": False,
        "qnum": 200,
        "bind_fix4": True,
        "bind_fix6": True,
        "ipcache_hostname": True,
        "wf_filter_lan": False,
        "wf_filter_loopback": True,
        "wf_tcp_empty": False
    }
}


class StatusScreen(Screen):
    """Экран статуса"""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Назад"),
        Binding("r", "refresh", "Обновить"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="status-container"):
            yield Static("## Статус службы", id="status-title")
            yield Static("", id="status-content")
            yield Button("Перезапустить службу", id="restart-btn", variant="warning")
            yield Button("Остановить службу", id="stop-btn", variant="error")
            yield Button("Запустить службу", id="start-btn", variant="success")
        yield Footer()
    
    def on_mount(self) -> None:
        self.refresh_status()
    
    def refresh_status(self) -> None:
        """Обновить статус"""
        content = self.query_one("#status-content", Static)
        status_info = get_winws2_status()
        
        lines = []
        lines.append(f"**Статус:** {'[green]Работает[/green]' if status_info['running'] else '[red]Остановлен[/red]'}")
        lines.append(f"**PID:** {status_info['pid'] if status_info['pid'] else 'N/A'}")
        lines.append(f"**Время работы:** {status_info['uptime']}")
        lines.append(f"**Потребление памяти:** {status_info['memory']}")
        lines.append(f"**Потоки:** {status_info['threads']}")
        lines.append("")
        lines.append("**Последние логи:**")
        lines.extend(status_info.get('logs', ['Нет логов']))
        
        content.update("\n".join(lines))
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "restart-btn":
            restart_winws2()
        elif event.button.id == "stop-btn":
            stop_winws2()
        elif event.button.id == "start-btn":
            start_winws2()
        self.refresh_status()
    
    def action_refresh(self) -> None:
        self.refresh_status()


class ConfigScreen(Screen):
    """Экран конфигурации"""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Назад"),
        Binding("s", "save", "Сохранить"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(id="config-scroll"):
            yield Static("## Конфигурация Telegram", id="config-title")
            
            with Vertical(id="telegram-config"):
                yield Checkbox("Включить Telegram", id="tg-enabled", value=True)
                yield Label("TCP порты:")
                yield Input(value="443,80,88,8080", id="tg-ports-tcp", placeholder="443,80,88,8080")
                yield Label("UDP порты:")
                yield Input(value="443,3478,3479,3480,3481,5222,5223,5224,8888,9898,9899,9900,10000-10100", 
                           id="tg-ports-udp", placeholder="443,3478...")
                
                yield Static("### Стратегии", id="strategies-title")
                
                with Vertical(id="strategy-1"):
                    yield Checkbox("TLS Fake", id="strat-fake-enabled", value=True)
                    yield Input(value="fake:blob=fake_default_tls:badsum:repeats=2", 
                               id="strat-fake-lua", placeholder="Lua десинк")
                    yield Input(value="tls", id="strat-fake-l7", placeholder="L7 фильтр")
                    yield Input(value="telegram.org,t.me,telegram.me,tg.dev", 
                               id="strat-fake-hosts", placeholder="Хосты")
                
                with Vertical(id="strategy-2"):
                    yield Checkbox("Multisplit", id="strat-split-enabled", value=True)
                    yield Input(value="multisplit:pos=2,host+1:badsum", 
                               id="strat-split-lua", placeholder="Lua десинк")
                    yield Input(value="tls,http", id="strat-split-l7", placeholder="L7 фильтр")
                    yield Input(value="telegram.org,t.me,telegram.me", 
                               id="strat-split-hosts", placeholder="Хосты")
                
                with Vertical(id="strategy-3"):
                    yield Checkbox("UDP Length", id="strat-udp-enabled", value=True)
                    yield Input(value="udplen:increment=2", 
                               id="strat-udp-lua", placeholder="Lua десинк")
                
                yield Checkbox("Автохостлист", id="tg-autohostlist", value=True)
                yield Checkbox("Режим отладки", id="tg-debug", value=False)
            
            yield Static("## Глобальные настройки", id="global-title")
            
            with Vertical(id="global-config"):
                yield Checkbox("Отладка", id="global-debug", value=False)
                yield Checkbox("Фоновый режим", id="global-daemon", value=False)
                yield Checkbox("Исправление IPv4", id="global-bind-fix4", value=True)
                yield Checkbox("Исправление IPv6", id="global-bind-fix6", value=True)
                yield Checkbox("Кэш имён хостов", id="global-ipcache", value=True)
                yield Checkbox("Фильтр LAN", id="global-wf-lan", value=False)
                yield Checkbox("Фильтр Loopback", id="global-wf-loopback", value=True)
            
            with Horizontal(id="config-buttons"):
                yield Button("Сохранить", id="save-btn", variant="primary")
                yield Button("Сбросить", id="reset-btn", variant="default")
                yield Button("Применить и перезапустить", id="apply-btn", variant="success")
        
        yield Footer()
    
    def on_mount(self) -> None:
        self.load_config()
    
    def load_config(self) -> None:
        """Загрузить конфигурацию"""
        config = load_config()
        tg = config.get('telegram', TELEGRAM_CONFIG)
        gl = config.get('global', DEFAULT_CONFIG['global'])
        
        self.query_one("#tg-enabled", Checkbox).value = tg.get('enabled', True)
        self.query_one("#tg-ports-tcp", Input).value = tg.get('ports_tcp', "443,80,88,8080")
        self.query_one("#tg-ports-udp", Input).value = tg.get('ports_udp', "443,3478,3479,3480,3481,5222,5223,5224,8888,9898,9899,9900,10000-10100")
        self.query_one("#tg-autohostlist", Checkbox).value = tg.get('autohostlist', True)
        self.query_one("#tg-debug", Checkbox).value = tg.get('debug', False)
        
        strategies = tg.get('strategies', [])
        if len(strategies) > 0:
            self.query_one("#strat-fake-enabled", Checkbox).value = strategies[0].get('enabled', True)
            self.query_one("#strat-fake-lua", Input).value = strategies[0].get('lua_desync', "fake:blob=fake_default_tls:badsum:repeats=2")
            self.query_one("#strat-fake-l7", Input).value = strategies[0].get('filter_l7', "tls")
            self.query_one("#strat-fake-hosts", Input).value = strategies[0].get('hostlist', "telegram.org,t.me,telegram.me,tg.dev")
        
        if len(strategies) > 1:
            self.query_one("#strat-split-enabled", Checkbox).value = strategies[1].get('enabled', True)
            self.query_one("#strat-split-lua", Input).value = strategies[1].get('lua_desync', "multisplit:pos=2,host+1:badsum")
            self.query_one("#strat-split-l7", Input).value = strategies[1].get('filter_l7', "tls,http")
            self.query_one("#strat-split-hosts", Input).value = strategies[1].get('hostlist', "telegram.org,t.me,telegram.me")
        
        if len(strategies) > 2:
            self.query_one("#strat-udp-enabled", Checkbox).value = strategies[2].get('enabled', True)
            self.query_one("#strat-udp-lua", Input).value = strategies[2].get('lua_desync', "udplen:increment=2")
        
        self.query_one("#global-debug", Checkbox).value = gl.get('debug', False)
        self.query_one("#global-daemon", Checkbox).value = gl.get('daemon', False)
        self.query_one("#global-bind-fix4", Checkbox).value = gl.get('bind_fix4', True)
        self.query_one("#global-bind-fix6", Checkbox).value = gl.get('bind_fix6', True)
        self.query_one("#global-ipcache", Checkbox).value = gl.get('ipcache_hostname', True)
        self.query_one("#global-wf-lan", Checkbox).value = gl.get('wf_filter_lan', False)
        self.query_one("#global-wf-loopback", Checkbox).value = gl.get('wf_filter_loopback', True)
    
    def save_config_from_ui(self) -> dict:
        """Сохранить конфигурацию из UI"""
        config = {
            "telegram": {
                "enabled": self.query_one("#tg-enabled", Checkbox).value,
                "ports_tcp": self.query_one("#tg-ports-tcp", Input).value,
                "ports_udp": self.query_one("#tg-ports-udp", Input).value,
                "autohostlist": self.query_one("#tg-autohostlist", Checkbox).value,
                "debug": self.query_one("#tg-debug", Checkbox).value,
                "strategies": [
                    {
                        "name": "TLS Fake",
                        "enabled": self.query_one("#strat-fake-enabled", Checkbox).value,
                        "lua_desync": self.query_one("#strat-fake-lua", Input).value,
                        "filter_l7": self.query_one("#strat-fake-l7", Input).value,
                        "hostlist": self.query_one("#strat-fake-hosts", Input).value
                    },
                    {
                        "name": "Multisplit",
                        "enabled": self.query_one("#strat-split-enabled", Checkbox).value,
                        "lua_desync": self.query_one("#strat-split-lua", Input).value,
                        "filter_l7": self.query_one("#strat-split-l7", Input).value,
                        "hostlist": self.query_one("#strat-split-hosts", Input).value
                    },
                    {
                        "name": "UDP Length",
                        "enabled": self.query_one("#strat-udp-enabled", Checkbox).value,
                        "lua_desync": self.query_one("#strat-udp-lua", Input).value
                    }
                ]
            },
            "global": {
                "debug": self.query_one("#global-debug", Checkbox).value,
                "daemon": self.query_one("#global-daemon", Checkbox).value,
                "bind_fix4": self.query_one("#global-bind-fix4", Checkbox).value,
                "bind_fix6": self.query_one("#global-bind-fix6", Checkbox).value,
                "ipcache_hostname": self.query_one("#global-ipcache", Checkbox).value,
                "wf_filter_lan": self.query_one("#global-wf-lan", Checkbox).value,
                "wf_filter_loopback": self.query_one("#global-wf-loopback", Checkbox).value
            }
        }
        save_config(config)
        return config
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.save_config_from_ui()
            self.notify("Конфигурация сохранена!", severity="information")
        elif event.button.id == "reset-btn":
            self.load_config()
            self.notify("Конфигурация сброшена", severity="warning")
        elif event.button.id == "apply-btn":
            self.save_config_from_ui()
            restart_winws2()
            self.notify("Конфигурация применена, служба перезапущена", severity="information")
    
    def action_save(self) -> None:
        self.save_config_from_ui()
        self.notify("Конфигурация сохранена!", severity="information")


class Zapret2TUI(App):
    """Основное TUI приложение Zapret2"""
    
    CSS = """
    Screen {
        align: center middle;
    }
    
    #main-container {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    
    #header-widget {
        dock: top;
        height: 3;
        background: $primary;
        color: $text;
        padding: 1;
    }
    
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    
    #content {
        height: 1fr;
    }
    
    #menu-container {
        width: 100%;
        height: auto;
        margin: 1 0;
    }
    
    Button {
        margin: 0 1;
        min-width: 20;
    }
    
    #log-container {
        height: 1fr;
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }
    
    Log {
        height: 1fr;
        background: $surface;
    }
    
    #stats-container {
        height: auto;
        max-height: 10;
        margin: 1 0;
        padding: 1;
        border: solid $accent;
    }
    
    .stat-label {
        color: $text-muted;
    }
    
    .stat-value {
        color: $success;
        text-style: bold;
    }
    
    #config-scroll {
        height: 1fr;
    }
    
    #config-title, #global-title, #strategies-title {
        padding: 1 0;
    }
    
    #telegram-config, #global-config {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }
    
    #config-buttons {
        height: auto;
        align: center middle;
        margin: 1 0;
    }
    
    #status-container {
        width: 80%;
        height: 80%;
        align: center middle;
        border: solid $primary;
        padding: 2;
    }
    
    #status-title {
        padding: 1 0;
    }
    
    #status-content {
        height: 1fr;
        padding: 1;
        background: $surface;
    }
    
    #status-container Button {
        width: 100%;
        margin: 1 0;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Выход"),
        Binding("c", "push_screen('config')", "Конфиг"),
        Binding("s", "push_screen('status')", "Статус"),
        Binding("t", "toggle_service", "Старт/Стоп"),
        Binding("l", "clear_log", "Очистить лог"),
        Binding("r", "refresh_stats", "Обновить"),
    ]
    
    log_messages = reactive([])
    stats = reactive({
        "packets_processed": 0,
        "packets_modified": 0,
        "packets_dropped": 0,
        "connections": 0
    })
    
    def __init__(self):
        super().__init__()
        self.winws2_process = None
        self.config_file = Path(__file__).parent / "config.json"
        self.log_file = Path(__file__).parent / "zapret2.log"
        
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(id="main-container"):
            yield Static("# Zapret2 TUI - Telegram Unblocker", id="header-widget")
            
            with Horizontal(id="menu-container"):
                yield Button("⚙️ Конфигурация", id="config-btn", variant="primary")
                yield Button("📊 Статус", id="status-btn", variant="secondary")
                yield Button("▶️ Старт", id="start-btn", variant="success")
                yield Button("⏹️ Стоп", id="stop-btn", variant="error")
                yield Button("🔄 Рестарт", id="restart-btn", variant="warning")
            
            with Container(id="stats-container"):
                yield Static(f"""[bold]Статистика:[/bold]
Пакетов обработано: [green]{self.stats['packets_processed']}[/green] | 
Модифицировано: [yellow]{self.stats['packets_modified']}[/yellow] | 
Отброшено: [red]{self.stats['packets_dropped']}[/red] | 
Соединений: [blue]{self.stats['connections']}[/blue]""", id="stats-widget")
            
            with Container(id="log-container"):
                yield Log(id="log-widget", highlight=True, markup=True)
            
            yield Footer()
        
        yield Footer()
    
    def on_mount(self) -> None:
        self.title = "Zapret2 TUI"
        self.sub_title = "Telegram Unblocker для Windows"
        self.start_log_updater()
        self.check_winws2_status()
        
    def start_log_updater(self):
        """Запустить обновление логов"""
        async def update_logs():
            while True:
                await asyncio.sleep(1)
                self.read_log_file()
                self.update_stats()
        asyncio.create_task(update_logs())
    
    def read_log_file(self):
        """Читать лог файл"""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-50:]  # Последние 50 строк
                    for line in lines:
                        line = line.strip()
                        if line and not any(x in line for x in self.log_messages[-100:]):
                            self.log_messages = self.log_messages + [line]
                            if len(self.log_messages) > 100:
                                self.log_messages = self.log_messages[-100:]
        except Exception as e:
            pass
    
    def update_stats(self):
        """Обновить статистику"""
        status = get_winws2_status()
        if status['running']:
            # Парсим логи для статистики
            for msg in self.log_messages[-10:]:
                if 'packet' in msg.lower():
                    self.stats['packets_processed'] += 1
                if 'modify' in msg.lower():
                    self.stats['packets_modified'] += 1
                if 'drop' in msg.lower():
                    self.stats['packets_dropped'] += 1
        
        stats_widget = self.query_one("#stats-widget", Static)
        stats_widget.update(f"""[bold]Статистика:[/bold]
Пакетов обработано: [green]{self.stats['packets_processed']}[/green] | 
Модифицировано: [yellow]{self.stats['packets_modified']}[/yellow] | 
Отброшено: [red]{self.stats['packets_dropped']}[/red] | 
Соединений: [blue]{self.stats['connections']}[/blue] |
Статус: {'[green]РАБОТАЕТ[/green]' if status['running'] else '[red]ОСТАНОВЛЕН[/red]'}""")
    
    def check_winws2_status(self):
        """Проверить статус winws2"""
        status = get_winws2_status()
        if not status['running']:
            self.notify("Служба winws2 не запущена", severity="warning")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "config-btn":
            self.push_screen("config")
        elif event.button.id == "status-btn":
            self.push_screen("status")
        elif event.button.id == "start-btn":
            start_winws2()
            self.notify("Служба запущена", severity="information")
        elif event.button.id == "stop-btn":
            stop_winws2()
            self.notify("Служба остановлена", severity="warning")
        elif event.button.id == "restart-btn":
            restart_winws2()
            self.notify("Служба перезапущена", severity="information")
    
    def action_toggle_service(self):
        """Переключить службу"""
        status = get_winws2_status()
        if status['running']:
            stop_winws2()
            self.notify("Служба остановлена", severity="warning")
        else:
            start_winws2()
            self.notify("Служба запущена", severity="information")
    
    def action_clear_log(self):
        """Очистить лог"""
        self.log_messages = []
        log_widget = self.query_one("#log-widget", Log)
        log_widget.clear()
        self.notify("Лог очищен", severity="information")
    
    def action_refresh_stats(self):
        """Обновить статистику"""
        self.update_stats()
        self.notify("Статистика обновлена", severity="information")
    
    def on_log_line_added(self, event: Log.LineAdded) -> None:
        """Обработка новой строки лога"""
        pass


def load_config() -> dict:
    """Загрузить конфигурацию"""
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_CONFIG


def save_config(config: dict):
    """Сохранить конфигурацию"""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_winws2_status() -> dict:
    """Получить статус winws2 процесса"""
    status = {
        "running": False,
        "pid": None,
        "uptime": "N/A",
        "memory": "N/A",
        "threads": "N/A",
        "logs": []
    }
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'winws2' in proc.info['name'].lower() if proc.info['name'] else False:
                status["running"] = True
                status["pid"] = proc.info['pid']
                p = psutil.Process(proc.info['pid'])
                status["uptime"] = str(datetime.now() - datetime.fromtimestamp(p.create_time()))
                status["memory"] = f"{p.memory_info().rss / 1024 / 1024:.1f} MB"
                status["threads"] = p.num_threads()
                
                # Читаем лог
                log_path = Path(__file__).parent / "zapret2.log"
                if log_path.exists():
                    with open(log_path, 'r', encoding='utf-8') as f:
                        status["logs"] = f.readlines()[-10:]
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return status


def generate_winws2_command(config: dict = None) -> str:
    """Сгенерировать команду для winws2"""
    if config is None:
        config = load_config()
    
    tg = config.get('telegram', {})
    gl = config.get('global', {})
    
    # Базовые параметры
    cmd_parts = ["winws2"]
    
    # Глобальные параметры
    if gl.get('debug'):
        cmd_parts.append("--debug=1")
    if gl.get('daemon'):
        cmd_parts.append("--daemon")
    if gl.get('bind_fix4'):
        cmd_parts.append("--bind-fix4")
    if gl.get('bind_fix6'):
        cmd_parts.append("--bind-fix6")
    if gl.get('ipcache_hostname'):
        cmd_parts.append("--ipcache-hostname=1")
    
    # WinDivert фильтры
    wf_parts = []
    if tg.get('ports_tcp'):
        wf_parts.append(f"--wf-tcp-out={tg['ports_tcp']}")
    if tg.get('ports_udp'):
        wf_parts.append(f"--wf-udp-out={tg['ports_udp']}")
        wf_parts.append(f"--wf-udp-in={tg['ports_udp']}")
    
    if gl.get('wf_filter_lan'):
        cmd_parts.append("--wf-filter-lan=1")
    else:
        cmd_parts.append("--wf-filter-lan=0")
    
    if gl.get('wf_filter_loopback'):
        cmd_parts.append("--wf-filter-loopback=1")
    else:
        cmd_parts.append("--wf-filter-loopback=0")
    
    cmd_parts.extend(wf_parts)
    
    # Lua скрипты
    lua_scripts = Path(__file__).parent / "lua"
    if lua_scripts.exists():
        cmd_parts.append(f"--lua-init=@{lua_scripts / 'zapret-lib.lua'}")
        cmd_parts.append(f"--lua-init=@{lua_scripts / 'zapret-antidpi.lua'}")
        cmd_parts.append(f"--lua-init=@{lua_scripts / 'zapret-auto.lua'}")
    
    # Профили стратегий
    strategies = tg.get('strategies', [])
    enabled_strategies = [s for s in strategies if s.get('enabled', False)]
    
    if enabled_strategies:
        for i, strat in enumerate(enabled_strategies):
            if i > 0:
                cmd_parts.append("--new")
            
            # Фильтры
            if strat.get('filter_l7'):
                cmd_parts.append(f"--filter-l7={strat['filter_l7']}")
            
            # Хостлисты
            if strat.get('hostlist'):
                hostlist_file = Path(__file__).parent / "hosts.txt"
                with open(hostlist_file, 'w', encoding='utf-8') as f:
                    for host in strat['hostlist'].split(','):
                        f.write(host.strip() + '\n')
                cmd_parts.append(f"--hostlist={hostlist_file}")
            
            # Lua десинк
            if strat.get('lua_desync'):
                cmd_parts.append(f"--lua-desync={strat['lua_desync']}")
    
    # Автохостлист
    if tg.get('autohostlist'):
        autohost_file = Path(__file__).parent / "autohostlist.txt"
        cmd_parts.append(f"--hostlist-auto={autohost_file}")
    
    return " ".join(cmd_parts)


def start_winws2(config: dict = None):
    """Запустить winws2"""
    stop_winws2()  # Сначала остановим если запущен
    
    cmd = generate_winws2_command(config)
    log_path = Path(__file__).parent / "zapret2.log"
    
    try:
        # Запускаем в фоне
        with open(log_path, 'a', encoding='utf-8') as log_file:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=Path(__file__).parent
            )
        return True
    except Exception as e:
        print(f"Ошибка запуска winws2: {e}")
        return False


def stop_winws2():
    """Остановить winws2"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'winws2' in proc.info['name'].lower() if proc.info['name'] else False:
                proc.terminate()
                proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            try:
                proc.kill()
            except:
                pass


def restart_winws2(config: dict = None):
    """Перезапустить winws2"""
    stop_winws2()
    import time
    time.sleep(2)
    start_winws2(config)


def main():
    """Точка входа"""
    # Инициализация конфигурации
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        save_config(DEFAULT_CONFIG)
    
    # Создаем файл хостов
    hosts_path = Path(__file__).parent / "hosts.txt"
    if not hosts_path.exists():
        with open(hosts_path, 'w', encoding='utf-8') as f:
            f.write("telegram.org\n")
            f.write("t.me\n")
            f.write("telegram.me\n")
            f.write("tg.dev\n")
    
    # Создаем директорию для Lua скриптов
    lua_dir = Path(__file__).parent / "lua"
    lua_dir.mkdir(exist_ok=True)
    
    app = Zapret2TUI()
    app.register_screen("config", ConfigScreen)
    app.register_screen("status", StatusScreen)
    app.run()


if __name__ == "__main__":
    main()
