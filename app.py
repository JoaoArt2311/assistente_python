from __future__ import annotations

import ctypes
import ipaddress
import json
import platform
import queue
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Assistente de Suporte TI"
APP_VERSION = "1.0.1"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HEADER_COLOR = "#3FA642"


class SupportToolError(RuntimeError):
    """Erro esperado ao executar uma ação de suporte."""


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def is_admin() -> bool:
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def ps_quote(value: str) -> str:
    """Escapa texto para uma string literal simples do PowerShell."""
    return "'" + value.replace("'", "''") + "'"


def run_powershell(script: str, timeout: int = 90) -> str:
    if not is_windows():
        raise SupportToolError("Esta automação foi criada para computadores com Windows.")

    encoding_setup = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$ProgressPreference = 'SilentlyContinue'; "
    )
    command = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        encoding_setup + script,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SupportToolError("O Windows demorou demais para responder à operação.") from exc
    except OSError as exc:
        raise SupportToolError(f"Não foi possível abrir o PowerShell: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Erro não identificado").strip()
        raise SupportToolError(detail)
    return result.stdout.strip().lstrip("\ufeff")


def parse_json_output(output: str):
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise SupportToolError(
            "O Windows retornou uma resposta que não pôde ser interpretada."
        ) from exc


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def format_bytes(value) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "Não informado"
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.2f} {units[index]}"


def format_list(value) -> str:
    items = [str(item) for item in as_list(value) if item not in (None, "")]
    return ", ".join(items) if items else "Não informado"


def collect_inventory() -> dict:
    script = r"""
$ErrorActionPreference = 'Stop'
$cs = Get-CimInstance Win32_ComputerSystem
$bios = Get-CimInstance Win32_BIOS
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$disks = @(
    Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
        [ordered]@{
            unidade = $_.DeviceID
            volume = $_.VolumeName
            tamanho_bytes = [int64]$_.Size
            livre_bytes = [int64]$_.FreeSpace
        }
    }
)
$networks = @(
    Get-NetIPConfiguration -ErrorAction SilentlyContinue |
        Where-Object { $_.NetAdapter.Status -eq 'Up' } |
        ForEach-Object {
            [ordered]@{
                nome = $_.InterfaceAlias
                descricao = $_.NetAdapter.InterfaceDescription
                ipv4 = @($_.IPv4Address | ForEach-Object { $_.IPAddress })
                gateway = @($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop })
                dns = @($_.DNSServer.ServerAddresses)
                mac = $_.NetAdapter.MacAddress
            }
        }
)
$printers = @(
    Get-CimInstance Win32_Printer -ErrorAction SilentlyContinue | ForEach-Object {
        [ordered]@{
            nome = $_.Name
            driver = $_.DriverName
            porta = $_.PortName
            padrao = [bool]$_.Default
            rede = [bool]$_.Network
        }
    }
)
$data = [ordered]@{
    coletado_em = (Get-Date).ToString('dd/MM/yyyy HH:mm:ss')
    computador = $env:COMPUTERNAME
    usuario = "$env:USERDOMAIN\$env:USERNAME"
    fabricante = $cs.Manufacturer
    modelo = $cs.Model
    numero_serie = $bios.SerialNumber
    dominio_ou_grupo = $cs.Domain
    em_dominio = [bool]$cs.PartOfDomain
    sistema = $os.Caption
    versao = $os.Version
    arquitetura = $os.OSArchitecture
    ultima_inicializacao = $os.LastBootUpTime.ToString('dd/MM/yyyy HH:mm:ss')
    processador = $cpu.Name
    nucleos = $cpu.NumberOfCores
    processadores_logicos = $cpu.NumberOfLogicalProcessors
    ram_bytes = [int64]$cs.TotalPhysicalMemory
    discos = $disks
    redes = $networks
    impressoras = $printers
}
$data | ConvertTo-Json -Depth 8 -Compress
"""
    data = parse_json_output(run_powershell(script, timeout=120))
    if not isinstance(data, dict):
        raise SupportToolError("O inventário retornado está vazio ou incompleto.")
    return data


def inventory_to_text(data: dict) -> str:
    lines = [
        f"{APP_NAME} - Relatório da máquina",
        "=" * 58,
        f"Coletado em: {data.get('coletado_em', 'Não informado')}",
        "",
        "IDENTIFICAÇÃO",
        f"Computador: {data.get('computador', 'Não informado')}",
        f"Usuário: {data.get('usuario', 'Não informado')}",
        f"Fabricante: {data.get('fabricante', 'Não informado')}",
        f"Modelo: {data.get('modelo', 'Não informado')}",
        f"Número de série: {data.get('numero_serie', 'Não informado')}",
        f"Domínio/Grupo: {data.get('dominio_ou_grupo', 'Não informado')}",
        "",
        "SISTEMA E HARDWARE",
        f"Windows: {data.get('sistema', 'Não informado')}",
        f"Versão: {data.get('versao', 'Não informado')}",
        f"Arquitetura: {data.get('arquitetura', 'Não informado')}",
        f"Última inicialização: {data.get('ultima_inicializacao', 'Não informado')}",
        f"Processador: {data.get('processador', 'Não informado')}",
        f"Núcleos/Processadores lógicos: {data.get('nucleos', '-')} / "
        f"{data.get('processadores_logicos', '-')}",
        f"Memória RAM: {format_bytes(data.get('ram_bytes'))}",
        "",
        "DISCOS",
    ]

    disks = as_list(data.get("discos"))
    if not disks:
        lines.append("Nenhum disco local encontrado.")
    for disk in disks:
        lines.append(
            f"{disk.get('unidade', '-')} {disk.get('volume') or ''} | "
            f"Total: {format_bytes(disk.get('tamanho_bytes'))} | "
            f"Livre: {format_bytes(disk.get('livre_bytes'))}"
        )

    lines.extend(["", "REDE"])
    networks = as_list(data.get("redes"))
    if not networks:
        lines.append("Nenhuma interface de rede ativa encontrada.")
    for network in networks:
        lines.extend(
            [
                f"Interface: {network.get('nome', 'Não informado')}",
                f"  Descrição: {network.get('descricao', 'Não informado')}",
                f"  IPv4: {format_list(network.get('ipv4'))}",
                f"  Gateway: {format_list(network.get('gateway'))}",
                f"  DNS: {format_list(network.get('dns'))}",
                f"  MAC: {network.get('mac') or 'Não informado'}",
            ]
        )

    lines.extend(["", "IMPRESSORAS"])
    printers = as_list(data.get("impressoras"))
    if not printers:
        lines.append("Nenhuma impressora encontrada.")
    for printer in printers:
        default = " | PADRÃO" if printer.get("padrao") else ""
        lines.append(
            f"{printer.get('nome', 'Sem nome')} | Driver: "
            f"{printer.get('driver', 'Não informado')} | Porta: "
            f"{printer.get('porta', 'Não informada')}{default}"
        )

    lines.extend(["", "-" * 58, f"Gerado pelo {APP_NAME} v{APP_VERSION}"])
    return "\n".join(lines)


def list_printers() -> list[dict]:
    script = r"""
$items = @(
    Get-CimInstance Win32_Printer -ErrorAction Stop | ForEach-Object {
        [ordered]@{
            nome = $_.Name
            driver = $_.DriverName
            porta = $_.PortName
            padrao = [bool]$_.Default
            offline = [bool]$_.WorkOffline
            compartilhada = [bool]$_.Shared
            rede = [bool]$_.Network
        }
    }
)
$items | ConvertTo-Json -Depth 4 -Compress
"""
    return as_list(parse_json_output(run_powershell(script)))


def list_printer_drivers() -> list[str]:
    script = (
        "$items = @(Get-PrinterDriver -ErrorAction Stop | "
        "Select-Object -ExpandProperty Name | Sort-Object -Unique); "
        "$items | ConvertTo-Json -Compress"
    )
    return [str(item) for item in as_list(parse_json_output(run_powershell(script)))]


def load_printer_state() -> tuple[list[dict], list[str]]:
    return list_printers(), list_printer_drivers()


def add_shared_printer(connection: str) -> None:
    connection = connection.strip()
    if not connection.startswith("\\\\") or connection.count("\\") < 3:
        raise SupportToolError(
            "Informe o caminho no formato \\\\servidor\\nome-da-impressora."
        )
    script = f"Add-Printer -ConnectionName {ps_quote(connection)} -ErrorAction Stop"
    run_powershell(script)


def add_ip_printer(ip: str, name: str, driver: str) -> None:
    ip = ip.strip()
    name = name.strip()
    driver = driver.strip()
    try:
        parsed_ip = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise SupportToolError("Informe um endereço IP válido para a impressora.") from exc
    if parsed_ip.version != 4:
        raise SupportToolError("Nesta versão, utilize um endereço IPv4.")
    if not name:
        raise SupportToolError("Informe um nome para a impressora.")
    if not driver:
        raise SupportToolError("Selecione um driver de impressora já instalado.")

    port_name = f"IP_{ip}"
    script = f"""
$ErrorActionPreference = 'Stop'
$portName = {ps_quote(port_name)}
$printerName = {ps_quote(name)}
$driverName = {ps_quote(driver)}
$printerIp = {ps_quote(ip)}
if (-not (Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue)) {{
    Add-PrinterPort -Name $portName -PrinterHostAddress $printerIp -ErrorAction Stop
}}
if (Get-Printer -Name $printerName -ErrorAction SilentlyContinue) {{
    throw "Já existe uma impressora com o nome informado."
}}
Add-Printer -Name $printerName -DriverName $driverName -PortName $portName -ErrorAction Stop
"""
    run_powershell(script)


def install_inf_driver(inf_path: str) -> str:
    if not is_windows():
        raise SupportToolError("A instalação de drivers está disponível somente no Windows.")
    path = Path(inf_path)
    if path.suffix.lower() != ".inf" or not path.is_file():
        raise SupportToolError("Selecione um arquivo de driver com extensão .INF.")
    try:
        result = subprocess.run(
            ["pnputil.exe", "/add-driver", str(path), "/install"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SupportToolError(f"Não foi possível instalar o driver: {exc}") from exc
    if result.returncode != 0:
        raise SupportToolError((result.stderr or result.stdout).strip())
    return (result.stdout or "Driver processado com sucesso.").strip()


def remove_printer(name: str) -> None:
    run_powershell(f"Remove-Printer -Name {ps_quote(name)} -ErrorAction Stop")


def set_default_printer(name: str) -> None:
    script = (
        "$network = New-Object -ComObject WScript.Network; "
        f"$network.SetDefaultPrinter({ps_quote(name)})"
    )
    run_powershell(script)


def print_test_page(name: str) -> None:
    if not is_windows():
        raise SupportToolError("A página de teste está disponível somente no Windows.")
    try:
        result = subprocess.run(
            ["rundll32.exe", "printui.dll,PrintUIEntry", "/k", "/n", name],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SupportToolError(f"Não foi possível imprimir a página de teste: {exc}") from exc
    if result.returncode != 0:
        raise SupportToolError((result.stderr or "Falha ao enviar a página de teste.").strip())


def restart_spooler() -> None:
    run_powershell("Restart-Service -Name Spooler -Force -ErrorAction Stop")


class AssistenteTI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1040x720")
        self.minsize(900, 620)
        self.configure(bg="#F4F6FB")
        self.inventory_data: dict | None = None
        self.status_var = tk.StringVar(value="Pronto para começar.")
        self.admin_var = tk.StringVar()
        self._async_results: queue.Queue = queue.Queue()
        self._active_jobs = 0

        self._setup_style()
        self._build_header()
        self._build_content()
        self._build_statusbar()
        self.after(100, self._drain_async_results)
        self.after(250, self._initial_load)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#F4F6FB")
        style.configure("Card.TFrame", background="#FFFFFF", relief="flat")
        style.configure("TLabel", background="#F4F6FB", foreground="#182033", font=("Segoe UI", 10))
        style.configure("Card.TLabel", background="#FFFFFF", foreground="#182033", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=HEADER_COLOR, foreground="#FFFFFF", font=("Segoe UI Semibold", 20))
        style.configure("Subtitle.TLabel", background=HEADER_COLOR, foreground="#D8D2FA", font=("Segoe UI", 10))
        style.configure("Admin.TLabel", background=HEADER_COLOR, foreground="#77E6B6", font=("Segoe UI Semibold", 9))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(18, 10))
        style.configure("Primary.TButton", background="#2E12D1", foreground="#FFFFFF")
        style.map("Primary.TButton", background=[("active", "#2E12D1"), ("pressed", "#2410A6")])
        style.configure("Danger.TButton", background="#D64550", foreground="#FFFFFF")
        style.map("Danger.TButton", background=[("active", "#B93640")])
        style.configure("TNotebook", background="#F4F6FB", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI Semibold", 12), padding=(30, 12))
        style.map("TNotebook.Tab", foreground=[("selected", "#3615FA")])
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=28, background="#FFFFFF", fieldbackground="#FFFFFF")
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))
        style.configure("TLabelframe", background="#FFFFFF", padding=12)
        style.configure("TLabelframe.Label", background="#FFFFFF", foreground="#25106B", font=("Segoe UI Semibold", 10))

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=HEADER_COLOR, height=115)
        header.pack(fill="x")
        header.pack_propagate(False)
        left = tk.Frame(header, bg=HEADER_COLOR)
        left.pack(side="left", padx=28, pady=16)
        ttk.Label(left, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="Inventário rápido e configuração de impressoras para o suporte diário",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Label(header, textvariable=self.admin_var, style="Admin.TLabel").pack(
            side="right", padx=28
        )

    def _build_content(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=20, pady=18)
        inventory_tab = ttk.Frame(notebook)
        printer_tab = ttk.Frame(notebook)
        notebook.add(inventory_tab, text="  Inventário da máquina  ")
        notebook.add(printer_tab, text="  Impressoras  ")
        self._build_inventory_tab(inventory_tab)
        self._build_printer_tab(printer_tab)

    def _build_inventory_tab(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", padx=4, pady=(14, 20))
        ttk.Button(
            toolbar,
            text="Coletar informações",
            style="Primary.TButton",
            command=self._collect_inventory,
            width= 20
        ).pack(side="left")
        self.export_button = ttk.Button(
            toolbar, text="Salvar relatório", command=self._export_inventory, state="disabled",
            width= 20
        )
        self.export_button.pack(side="left", padx=(16,0))

        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True)
        self.inventory_text = tk.Text(
            card,
            wrap="word",
            font=("Consolas", 10),
            bg="#FFFFFF",
            fg="#182033",
            relief="flat",
            padx=12,
            pady=12,
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(card, orient="vertical", command=self.inventory_text.yview)
        self.inventory_text.configure(yscrollcommand=scrollbar.set)
        self.inventory_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._set_inventory_text(
            "Clique em “Coletar informações” para gerar um inventário desta máquina.\n\n"
            "Serão coletados: identificação, número de série, Windows, processador, "
            "memória, discos, rede e impressoras."
        )

    def _build_printer_tab(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Atualizar lista", command=self._refresh_printers).pack(side="left")
        ttk.Button(toolbar, text="Instalar driver (.INF)", command=self._choose_driver).pack(
            side="left", padx=8
        )
        ttk.Button(toolbar, text="Reiniciar serviço de impressão", command=self._restart_spooler).pack(
            side="left"
        )

        tree_card = ttk.Frame(parent, style="Card.TFrame", padding=8)
        tree_card.pack(fill="both", expand=True)
        columns = ("nome", "driver", "porta", "estado", "padrao")
        self.printer_tree = ttk.Treeview(tree_card, columns=columns, show="headings", height=8)
        headings = {
            "nome": "Impressora",
            "driver": "Driver",
            "porta": "Porta",
            "estado": "Estado",
            "padrao": "Padrão",
        }
        widths = {"nome": 230, "driver": 260, "porta": 120, "estado": 90, "padrao": 70}
        for column in columns:
            self.printer_tree.heading(column, text=headings[column])
            self.printer_tree.column(column, width=widths[column], minwidth=60)
        tree_scroll = ttk.Scrollbar(tree_card, orient="vertical", command=self.printer_tree.yview)
        self.printer_tree.configure(yscrollcommand=tree_scroll.set)
        self.printer_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(8, 12))
        ttk.Button(actions, text="Definir como padrão", command=self._set_default).pack(side="left")
        ttk.Button(actions, text="Imprimir página de teste", command=self._print_test).pack(
            side="left", padx=8
        )
        ttk.Button(
            actions, text="Remover selecionada", style="Danger.TButton", command=self._remove_printer
        ).pack(side="left")

        forms = ttk.Frame(parent)
        forms.pack(fill="x")
        forms.columnconfigure(0, weight=1)
        forms.columnconfigure(1, weight=1)

        shared = ttk.LabelFrame(forms, text="Adicionar impressora compartilhada")
        shared.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(shared, text="Caminho (ex.: \\\\SERVIDOR\\Financeiro)", style="Card.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.shared_path_var = tk.StringVar()
        ttk.Entry(shared, textvariable=self.shared_path_var).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Button(
            shared, text="Adicionar compartilhada", style="Primary.TButton", command=self._add_shared
        ).grid(row=2, column=0, sticky="w")
        shared.columnconfigure(0, weight=1)

        ip_frame = ttk.LabelFrame(forms, text="Adicionar impressora por IP")
        ip_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ip_frame.columnconfigure(1, weight=1)
        self.ip_var = tk.StringVar()
        self.printer_name_var = tk.StringVar()
        self.driver_var = tk.StringVar()
        ttk.Label(ip_frame, text="Endereço IPv4", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(ip_frame, textvariable=self.ip_var, width=18).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(ip_frame, text="Nome", style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(ip_frame, textvariable=self.printer_name_var).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(ip_frame, text="Driver", style="Card.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 8))
        self.driver_combo = ttk.Combobox(ip_frame, textvariable=self.driver_var, state="readonly")
        self.driver_combo.grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Button(
            ip_frame, text="Adicionar por IP", style="Primary.TButton", command=self._add_ip
        ).grid(row=3, column=1, sticky="e", pady=(8, 0))

    def _build_statusbar(self) -> None:
        bar = tk.Frame(self, bg="#E7EAF2", height=30)
        bar.pack(fill="x", side="bottom")
        tk.Label(
            bar,
            textvariable=self.status_var,
            bg="#E7EAF2",
            fg="#4A5368",
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", padx=20, pady=6)

    def _initial_load(self) -> None:
        if not is_windows():
            self.admin_var.set("Ambiente não Windows")
            self.status_var.set("Esta ferramenta deverá ser executada em um computador Windows.")
            return
        self.admin_var.set("Administrador" if is_admin() else "Modo comum • algumas ações podem exigir administrador")
        self._refresh_printers(silent=True)

    def _run_async(self, description: str, function, on_success=None) -> None:
        self.status_var.set(description)
        self._active_jobs += 1
        self.configure(cursor="wait")

        def worker() -> None:
            try:
                result = function()
            except Exception as exc:  # converte falhas do sistema em aviso visual
                self._async_results.put((False, exc, None))
                return
            self._async_results.put((True, result, on_success))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_async_results(self) -> None:
        try:
            while True:
                succeeded, result, callback = self._async_results.get_nowait()
                self._active_jobs = max(0, self._active_jobs - 1)
                if succeeded:
                    self._operation_succeeded(result, callback)
                else:
                    self._operation_failed(result)
        except queue.Empty:
            pass
        if self._active_jobs == 0:
            self.configure(cursor="")
        self.after(100, self._drain_async_results)

    def _operation_succeeded(self, result, callback) -> None:
        self.status_var.set("Operação concluída com sucesso.")
        if callback:
            callback(result)

    def _operation_failed(self, error: Exception) -> None:
        self.status_var.set("A operação não foi concluída.")
        messagebox.showerror(APP_NAME, str(error))

    def _set_inventory_text(self, text: str) -> None:
        self.inventory_text.configure(state="normal")
        self.inventory_text.delete("1.0", "end")
        self.inventory_text.insert("1.0", text)
        self.inventory_text.configure(state="disabled")

    def _collect_inventory(self) -> None:
        self._run_async("Coletando informações da máquina...", collect_inventory, self._show_inventory)

    def _show_inventory(self, data: dict) -> None:
        self.inventory_data = data
        self._set_inventory_text(inventory_to_text(data))
        self.export_button.configure(state="normal")
        self.status_var.set("Inventário coletado.")

    def _export_inventory(self) -> None:
        if not self.inventory_data:
            return
        computer = self.inventory_data.get("computador", "computador")
        date_tag = datetime.now().strftime("%Y-%m-%d_%H-%M")
        suggested = f"inventario_{computer}_{date_tag}.txt"
        selected = filedialog.asksaveasfilename(
            title="Salvar relatório da máquina",
            defaultextension=".txt",
            initialfile=suggested,
            filetypes=[("Relatório de texto", "*.txt")],
        )
        if not selected:
            return
        try:
            txt_path = Path(selected)
            txt_path.write_text(inventory_to_text(self.inventory_data), encoding="utf-8")
            json_path = txt_path.with_suffix(".json")
            json_path.write_text(
                json.dumps(self.inventory_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível salvar o relatório: {exc}")
            return
        self.status_var.set(f"Relatórios salvos em {txt_path.parent}")
        messagebox.showinfo(
            APP_NAME,
            f"Relatório salvo em dois formatos:\n\n{txt_path.name}\n{json_path.name}",
        )

    def _refresh_printers(self, silent: bool = False) -> None:
        def show(state: tuple[list[dict], list[str]]) -> None:
            printers, drivers = state
            for item in self.printer_tree.get_children():
                self.printer_tree.delete(item)
            for printer in printers:
                status = "Offline" if printer.get("offline") else "Disponível"
                values = (
                    printer.get("nome", ""),
                    printer.get("driver", ""),
                    printer.get("porta", ""),
                    status,
                    "Sim" if printer.get("padrao") else "",
                )
                self.printer_tree.insert("", "end", values=values)
            current = self.driver_var.get()
            self.driver_combo.configure(values=drivers)
            if current in drivers:
                self.driver_var.set(current)
            elif drivers:
                self.driver_combo.current(0)
            self.status_var.set(f"{len(printers)} impressora(s) encontrada(s).")

        description = "Carregando impressoras e drivers..." if not silent else "Preparando impressoras..."
        self._run_async(description, load_printer_state, show)

    def _choose_driver(self) -> None:
        selected = filedialog.askopenfilename(
            title="Selecione o arquivo do driver",
            filetypes=[("Driver de impressora", "*.inf")],
        )
        if not selected:
            return
        if not messagebox.askyesno(
            APP_NAME,
            "A instalação de driver pode exigir acesso de administrador. Deseja continuar?",
        ):
            return

        def done(output: str) -> None:
            messagebox.showinfo(APP_NAME, output or "Driver processado com sucesso.")
            self._refresh_printers(silent=True)

        self._run_async("Instalando driver de impressora...", lambda: install_inf_driver(selected), done)

    def _add_shared(self) -> None:
        path = self.shared_path_var.get().strip()

        def done(_result) -> None:
            self.shared_path_var.set("")
            messagebox.showinfo(APP_NAME, "Impressora compartilhada adicionada.")
            self._refresh_printers(silent=True)

        self._run_async("Adicionando impressora compartilhada...", lambda: add_shared_printer(path), done)

    def _add_ip(self) -> None:
        ip = self.ip_var.get().strip()
        name = self.printer_name_var.get().strip()
        driver = self.driver_var.get().strip()

        def done(_result) -> None:
            self.ip_var.set("")
            self.printer_name_var.set("")
            messagebox.showinfo(APP_NAME, "Impressora por IP adicionada.")
            self._refresh_printers(silent=True)

        self._run_async(
            "Criando porta e adicionando impressora...",
            lambda: add_ip_printer(ip, name, driver),
            done,
        )

    def _selected_printer(self) -> str | None:
        selection = self.printer_tree.selection()
        if not selection:
            messagebox.showwarning(APP_NAME, "Selecione uma impressora na lista.")
            return None
        values = self.printer_tree.item(selection[0], "values")
        return str(values[0]) if values else None

    def _set_default(self) -> None:
        name = self._selected_printer()
        if not name:
            return

        def done(_result) -> None:
            self._refresh_printers(silent=True)

        self._run_async("Definindo impressora padrão...", lambda: set_default_printer(name), done)

    def _print_test(self) -> None:
        name = self._selected_printer()
        if not name:
            return

        def done(_result) -> None:
            messagebox.showinfo(APP_NAME, "Página de teste enviada para a impressora.")

        self._run_async("Enviando página de teste...", lambda: print_test_page(name), done)

    def _remove_printer(self) -> None:
        name = self._selected_printer()
        if not name:
            return
        if not messagebox.askyesno(APP_NAME, f"Deseja realmente remover a impressora “{name}”?", icon="warning"):
            return

        def done(_result) -> None:
            self._refresh_printers(silent=True)

        self._run_async("Removendo impressora...", lambda: remove_printer(name), done)

    def _restart_spooler(self) -> None:
        if not messagebox.askyesno(
            APP_NAME,
            "Isso reiniciará temporariamente o serviço de impressão. Deseja continuar?",
        ):
            return

        def done(_result) -> None:
            messagebox.showinfo(APP_NAME, "Serviço de impressão reiniciado.")
            self._refresh_printers(silent=True)

        self._run_async("Reiniciando serviço de impressão...", restart_spooler, done)


def main() -> None:
    app = AssistenteTI()
    app.mainloop()


if __name__ == "__main__":
    main()
