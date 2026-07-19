"""
ANT BMS action / control commands.

Reverse-engineered from the app control page (`bmskongzhi.vue`): every button
sends ``WriteData(<command id>, 0, 0x51, 0)`` — function ``0x51`` with the
command id placed in the address field and a zero-length payload. (The
"save settings to flash" button is the same mechanism with id 7.)

Each command is grouped the same way the app groups them on screen.
``confirm`` marks destructive/disruptive actions that should be confirmed
before sending (MOS off, restart, factory reset, Bluetooth off, …).
"""
from dataclasses import dataclass

from . import protocol as p

FUNC_COMMAND = 0x51


@dataclass(frozen=True)
class Command:
    id: int
    key: str
    label: str
    group: str
    confirm: bool = False


# group keys -> display label (in app order)
COMMAND_GROUPS = [
    ("mos", "MOS Control"),
    ("system", "System & Presets"),
    ("counters", "Clear Counters"),
    ("advanced", "Bluetooth & Advanced"),
]
COMMAND_GROUP_LABELS = dict(COMMAND_GROUPS)

COMMANDS = [
    # MOS control (app: kongzhi)
    Command(6, "charge_mos_on", "Charge MOS on", "mos"),
    Command(4, "charge_mos_off", "Charge MOS off", "mos", confirm=True),
    Command(3, "discharge_mos_on", "Discharge MOS on", "mos"),
    Command(1, "discharge_mos_off", "Discharge MOS off", "mos", confirm=True),

    # System & presets (app: kongzhi1)
    Command(40, "load_lifepo4_params", "Load LiFePO₄ default params", "system", confirm=True),
    Command(39, "load_nmc_params", "Load NMC (ternary) default params", "system", confirm=True),
    Command(38, "load_lto_params", "Load LTO (titanate) default params", "system", confirm=True),
    Command(8, "reset_current", "Reset current calibration", "system"),
    Command(13, "auto_balance_on", "Enable auto-balance", "system"),
    Command(14, "auto_balance_off", "Disable auto-balance", "system"),
    Command(9, "restart_bms", "Restart BMS", "system", confirm=True),
    Command(11, "shutdown_bms", "Shut down BMS", "system", confirm=True),
    Command(12, "factory_reset", "Restore factory settings", "system", confirm=True),
    Command(52, "force_charge", "Force charging", "system", confirm=True),

    # Clear counters (app: kongzhi2)
    Command(33, "clear_acc_charge_ah", "Clear accumulated charge (Ah)", "counters", confirm=True),
    Command(32, "clear_acc_discharge_ah", "Clear accumulated discharge (Ah)", "counters", confirm=True),
    Command(35, "clear_acc_charge_time", "Clear accumulated charge time", "counters", confirm=True),
    Command(34, "clear_acc_discharge_time", "Clear accumulated discharge time", "counters", confirm=True),
    Command(37, "clear_protect_time", "Clear protection time", "counters", confirm=True),
    Command(36, "clear_runtime", "Clear runtime", "counters", confirm=True),
    Command(15, "clear_system_log", "Clear system log", "counters", confirm=True),

    # Bluetooth & advanced (app: kongzhi3)
    Command(42, "restore_original_factory", "Restore original factory settings", "advanced", confirm=True),
    Command(16, "bt_initialize", "Initialize Bluetooth", "advanced", confirm=True),
    Command(29, "bt_power_on", "Bluetooth power on", "advanced"),
    Command(28, "bt_power_off", "Bluetooth power off", "advanced", confirm=True),
    Command(30, "buzzer_on", "Force buzzer on", "advanced"),
    Command(31, "buzzer_off", "Force buzzer off", "advanced"),
    Command(44, "save_application", "Save application params", "advanced"),
    Command(45, "save_user_params", "Save to user params", "advanced"),

    # The save-settings-to-flash button uses the same mechanism (id 7).
    Command(7, "save_settings", "Save settings to flash", "system"),
]

CMD_BY_ID = {c.id: c for c in COMMANDS}
CMD_BY_KEY = {c.key: c for c in COMMANDS}


def build_command(command_id: int) -> bytes:
    """Build the frame for a control command id (func 0x51, len 0)."""
    return p.build_frame(FUNC_COMMAND, command_id, 0, b"")


def resolve(id_or_key) -> Command:
    """Look up a Command by numeric id or string key. Raises KeyError."""
    if isinstance(id_or_key, int) or (isinstance(id_or_key, str) and id_or_key.isdigit()):
        return CMD_BY_ID[int(id_or_key)]
    return CMD_BY_KEY[id_or_key]
