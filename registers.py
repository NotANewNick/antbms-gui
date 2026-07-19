"""
ANT BMS settings register map.

Reverse-engineered from the ANT BMS Android app (uni-app bundle, module `b42a`,
`param_list`). Each setting is a little-endian value stored in the BMS settings
memory at byte `address`. Most settings are 16-bit (2 bytes); a few capacity
fields are 32-bit (see CAPACITY_HIGH_WORD_ADDRESSES).

Engineering value  ->  raw register value:  raw = round(value * scale)
Raw register value ->  engineering value:  value = raw / scale
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Register:
    id: int
    address: int       # byte offset in the settings memory
    key: str           # stable machine name
    name: str          # human-readable English name
    scale: float       # raw = value * scale
    decimals: int      # display precision
    unit: str
    size: int = 2      # bytes


REGISTERS = [
    Register(id=0, address=0, key='cell_overvoltage_protection', name='Cell overvoltage protection', scale=1000, decimals=0, unit='', size=2),
    Register(id=1, address=2, key='cell_overvoltage_recovery', name='Cell overvoltage recovery', scale=1000, decimals=0, unit='', size=2),
    Register(id=2, address=4, key='cell_secondary_overvoltage_protection', name='Cell secondary overvoltage protection', scale=1000, decimals=0, unit='', size=2),
    Register(id=3, address=6, key='cell_secondary_overvoltage_recovery', name='Cell secondary overvoltage recovery', scale=1000, decimals=0, unit='', size=2),
    Register(id=4, address=8, key='pack_overvoltage_protection', name='Pack overvoltage protection', scale=10, decimals=0, unit='', size=2),
    Register(id=5, address=10, key='pack_overvoltage_recovery', name='Pack overvoltage recovery', scale=10, decimals=0, unit='', size=2),
    Register(id=6, address=12, key='cell_undervoltage_protection', name='Cell undervoltage protection', scale=1000, decimals=0, unit='', size=2),
    Register(id=7, address=14, key='cell_undervoltage_recovery', name='Cell undervoltage recovery', scale=1000, decimals=0, unit='', size=2),
    Register(id=8, address=16, key='cell_secondary_undervoltage_protection', name='Cell secondary undervoltage protection', scale=1000, decimals=0, unit='', size=2),
    Register(id=9, address=18, key='cell_secondary_undervoltage_recovery', name='Cell secondary undervoltage recovery', scale=1000, decimals=0, unit='', size=2),
    Register(id=10, address=20, key='pack_undervoltage_protection', name='Pack undervoltage protection', scale=10, decimals=0, unit='', size=2),
    Register(id=11, address=22, key='pack_undervoltage_recovery', name='Pack undervoltage recovery', scale=10, decimals=0, unit='', size=2),
    Register(id=12, address=24, key='cell_voltage_diff_protection', name='Cell voltage-diff protection', scale=1000, decimals=0, unit='', size=2),
    Register(id=13, address=26, key='cell_voltage_diff_recovery', name='Cell voltage-diff recovery', scale=1000, decimals=0, unit='', size=2),
    Register(id=14, address=28, key='reserved', name='Reserved', scale=1000, decimals=0, unit='', size=2),
    Register(id=15, address=30, key='reserved_1', name='Reserved', scale=1000, decimals=0, unit='', size=2),
    Register(id=16, address=32, key='cell_overvoltage_alarm', name='Cell overvoltage alarm', scale=1000, decimals=0, unit='', size=2),
    Register(id=17, address=34, key='cell_overvoltage_alarm_recovery', name='Cell overvoltage alarm recovery', scale=1000, decimals=0, unit='', size=2),
    Register(id=18, address=36, key='pack_overvoltage_alarm', name='Pack overvoltage alarm', scale=10, decimals=0, unit='', size=2),
    Register(id=19, address=38, key='pack_overvoltage_alarm_recovery', name='Pack overvoltage alarm recovery', scale=10, decimals=0, unit='', size=2),
    Register(id=20, address=40, key='cell_undervoltage_alarm', name='Cell undervoltage alarm', scale=1000, decimals=0, unit='', size=2),
    Register(id=21, address=42, key='cell_undervoltage_alarm_recovery', name='Cell undervoltage alarm recovery', scale=1000, decimals=0, unit='', size=2),
    Register(id=22, address=44, key='pack_undervoltage_alarm', name='Pack undervoltage alarm', scale=10, decimals=0, unit='', size=2),
    Register(id=23, address=46, key='pack_undervoltage_alarm_recovery', name='Pack undervoltage alarm recovery', scale=10, decimals=0, unit='', size=2),
    Register(id=24, address=48, key='cell_voltage_diff_alarm', name='Cell voltage-diff alarm', scale=1000, decimals=0, unit='', size=2),
    Register(id=25, address=50, key='cell_voltage_diff_alarm_recovery', name='Cell voltage-diff alarm recovery', scale=1000, decimals=0, unit='', size=2),
    Register(id=52, address=104, key='charge_overcurrent_protection', name='Charge overcurrent protection', scale=10, decimals=0, unit='', size=2),
    Register(id=53, address=106, key='charge_overcurrent_protection_delay', name='Charge overcurrent protection delay', scale=1, decimals=0, unit='', size=2),
    Register(id=54, address=108, key='discharge_overcurrent_protection', name='Discharge overcurrent protection', scale=10, decimals=0, unit='', size=2),
    Register(id=55, address=110, key='discharge_overcurrent_protection_delay', name='Discharge overcurrent protection delay', scale=1, decimals=0, unit='', size=2),
    Register(id=56, address=112, key='discharge_overcurrent_l2_protection', name='Discharge overcurrent L2 protection', scale=10, decimals=0, unit='', size=2),
    Register(id=57, address=114, key='discharge_overcurrent_l2_protection_delay', name='Discharge overcurrent L2 protection delay', scale=1, decimals=0, unit='', size=2),
    Register(id=58, address=116, key='short_circuit_protection_current', name='Short-circuit protection current', scale=1, decimals=0, unit='', size=2),
    Register(id=59, address=118, key='short_circuit_protection_current_1', name='Short-circuit protection current', scale=1, decimals=0, unit='', size=2),
    Register(id=60, address=120, key='reserved_2', name='Reserved', scale=1, decimals=0, unit='', size=2),
    Register(id=61, address=122, key='reserved_3', name='Reserved', scale=1, decimals=0, unit='', size=2),
    Register(id=62, address=124, key='charge_overcurrent_alarm', name='Charge overcurrent alarm', scale=10, decimals=0, unit='', size=2),
    Register(id=63, address=126, key='charge_overcurrent_alarm_recovery', name='Charge overcurrent alarm recovery', scale=10, decimals=0, unit='', size=2),
    Register(id=64, address=128, key='discharge_overcurrent_alarm', name='Discharge overcurrent alarm', scale=10, decimals=0, unit='', size=2),
    Register(id=65, address=130, key='discharge_overcurrent_alarm_recovery', name='Discharge overcurrent alarm recovery', scale=10, decimals=0, unit='', size=2),
    Register(id=66, address=132, key='soc_level_1_alarm', name='SOC level-1 alarm', scale=1, decimals=0, unit='', size=2),
    Register(id=67, address=134, key='soc_level_2_alarm', name='SOC level-2 alarm', scale=1, decimals=0, unit='', size=2),
    Register(id=68, address=136, key='reserved_4', name='Reserved', scale=1, decimals=0, unit='', size=2),
    Register(id=69, address=138, key='reserved_5', name='Reserved', scale=1, decimals=0, unit='', size=2),
    Register(id=70, address=140, key='balance_limit_voltage', name='Balance limit voltage', scale=1000, decimals=3, unit='V', size=2),
    Register(id=71, address=142, key='balance_start_voltage_charging', name='Balance start voltage (charging)', scale=1000, decimals=3, unit='V', size=2),
    Register(id=72, address=144, key='balance_start_voltage_diff', name='Balance start voltage-diff', scale=1000, decimals=3, unit='V', size=2),
    Register(id=73, address=146, key='balance_stop_voltage_diff', name='Balance stop voltage-diff', scale=1000, decimals=3, unit='V', size=2),
    Register(id=74, address=148, key='balance_current', name='Balance current', scale=1, decimals=0, unit='', size=2),
    Register(id=75, address=150, key='balance_charge_current', name='Balance charge current', scale=10, decimals=0, unit='A', size=2),
    Register(id=76, address=152, key='battery_type_selection', name='Battery type selection', scale=1, decimals=0, unit='', size=2),
    Register(id=77, address=154, key='configured_cell_count_series', name='Configured cell count (series)', scale=1, decimals=0, unit='cells', size=2),
    Register(id=78, address=156, key='undervoltage_internal_resistance_compensation', name='Undervoltage internal-resistance compensation', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=79, address=158, key='auto_shutdown_voltage', name='Auto shutdown voltage', scale=1000, decimals=3, unit='V', size=2),
    Register(id=80, address=160, key='max_charge_request_current', name='Max charge request current', scale=10, decimals=1, unit='A', size=2),
    Register(id=81, address=162, key='battery_physical_capacity', name='Battery physical capacity', scale=1000000, decimals=1, unit='Ah', size=4),
    Register(id=82, address=164, key='battery_physical_capacity_1', name='Battery physical capacity', scale=1000000, decimals=1, unit='Ah', size=2),
    Register(id=83, address=166, key='remaining_capacity', name='Remaining capacity', scale=1000000, decimals=1, unit='Ah', size=4),
    Register(id=84, address=168, key='remaining_capacity_1', name='Remaining capacity', scale=1000000, decimals=1, unit='Ah', size=2),
    Register(id=85, address=170, key='total_cycle_capacity', name='Total cycle capacity', scale=1000000, decimals=1, unit='Ah', size=4),
    Register(id=86, address=172, key='total_cycle_capacity_1', name='Total cycle capacity', scale=1000000, decimals=1, unit='Ah', size=2),
    Register(id=87, address=174, key='cell_voltage_at_100pct_soc', name='Cell voltage @100% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=88, address=176, key='cell_voltage_at_90pct_soc', name='Cell voltage @90% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=89, address=178, key='cell_voltage_at_80pct_soc', name='Cell voltage @80% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=90, address=180, key='cell_voltage_at_70pct_soc', name='Cell voltage @70% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=91, address=182, key='cell_voltage_at_60pct_soc', name='Cell voltage @60% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=92, address=184, key='cell_voltage_at_50pct_soc', name='Cell voltage @50% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=93, address=186, key='cell_voltage_at_40pct_soc', name='Cell voltage @40% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=94, address=188, key='cell_voltage_at_30pct_soc', name='Cell voltage @30% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=95, address=190, key='cell_voltage_at_20pct_soc', name='Cell voltage @20% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=96, address=192, key='cell_voltage_at_10pct_soc', name='Cell voltage @10% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=97, address=194, key='cell_voltage_at_0pct_soc', name='Cell voltage @0% SOC', scale=1000, decimals=3, unit='V', size=2),
    Register(id=98, address=196, key='soc_calibration_method', name='SOC calibration method', scale=1, decimals=0, unit='', size=2),
    Register(id=99, address=198, key='wire_connection_resistance_1', name='Wire/connection resistance 1', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=100, address=200, key='wire_connection_resistance_2', name='Wire/connection resistance 2', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=101, address=202, key='wire_connection_resistance_3', name='Wire/connection resistance 3', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=102, address=204, key='wire_connection_resistance_4', name='Wire/connection resistance 4', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=103, address=206, key='wire_connection_resistance_5', name='Wire/connection resistance 5', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=104, address=208, key='wire_connection_resistance_6', name='Wire/connection resistance 6', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=105, address=210, key='wire_connection_resistance_7', name='Wire/connection resistance 7', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=106, address=212, key='wire_connection_resistance_8', name='Wire/connection resistance 8', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=107, address=214, key='wire_connection_resistance_9', name='Wire/connection resistance 9', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=108, address=216, key='wire_connection_resistance_10', name='Wire/connection resistance 10', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=109, address=218, key='wire_connection_resistance_11', name='Wire/connection resistance 11', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=110, address=220, key='wire_connection_resistance_12', name='Wire/connection resistance 12', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=111, address=222, key='wire_connection_resistance_13', name='Wire/connection resistance 13', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=112, address=224, key='wire_connection_resistance_14', name='Wire/connection resistance 14', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=113, address=226, key='wire_connection_resistance_15', name='Wire/connection resistance 15', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=114, address=228, key='wire_connection_resistance_16', name='Wire/connection resistance 16', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=115, address=230, key='wire_connection_resistance_17', name='Wire/connection resistance 17', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=116, address=232, key='wire_connection_resistance_18', name='Wire/connection resistance 18', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=117, address=234, key='wire_connection_resistance_19', name='Wire/connection resistance 19', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=118, address=236, key='wire_connection_resistance_20', name='Wire/connection resistance 20', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=119, address=238, key='wire_connection_resistance_21', name='Wire/connection resistance 21', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=120, address=240, key='wire_connection_resistance_22', name='Wire/connection resistance 22', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=121, address=242, key='wire_connection_resistance_23', name='Wire/connection resistance 23', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=122, address=244, key='wire_connection_resistance_24', name='Wire/connection resistance 24', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=123, address=246, key='wire_connection_resistance_25', name='Wire/connection resistance 25', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=124, address=248, key='wire_connection_resistance_26', name='Wire/connection resistance 26', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=125, address=250, key='wire_connection_resistance_27', name='Wire/connection resistance 27', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=126, address=252, key='wire_connection_resistance_28', name='Wire/connection resistance 28', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=127, address=254, key='wire_connection_resistance_29', name='Wire/connection resistance 29', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=128, address=256, key='wire_connection_resistance_30', name='Wire/connection resistance 30', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=129, address=258, key='wire_connection_resistance_31', name='Wire/connection resistance 31', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=130, address=260, key='wire_connection_resistance_32', name='Wire/connection resistance 32', scale=10, decimals=1, unit='mΩ', size=2),
    Register(id=131, address=262, key='battery_id_word_1', name='Battery ID word 1', scale=10, decimals=1, unit='', size=2),
    Register(id=132, address=264, key='battery_id_word_2', name='Battery ID word 2', scale=10, decimals=1, unit='', size=2),
    Register(id=133, address=266, key='battery_id_word_3', name='Battery ID word 3', scale=10, decimals=1, unit='', size=2),
    Register(id=134, address=268, key='battery_id_word_4', name='Battery ID word 4', scale=10, decimals=1, unit='', size=2),
    Register(id=135, address=270, key='battery_id_word_5', name='Battery ID word 5', scale=10, decimals=1, unit='', size=2),
    Register(id=136, address=272, key='battery_id_word_6', name='Battery ID word 6', scale=10, decimals=1, unit='', size=2),
    Register(id=137, address=274, key='battery_id_word_7', name='Battery ID word 7', scale=10, decimals=1, unit='', size=2),
    Register(id=138, address=276, key='battery_id_word_8', name='Battery ID word 8', scale=10, decimals=1, unit='', size=2),
    Register(id=139, address=278, key='battery_id_word_9', name='Battery ID word 9', scale=10, decimals=1, unit='', size=2),
    Register(id=140, address=280, key='battery_id_word_10', name='Battery ID word 10', scale=10, decimals=1, unit='', size=2),
    Register(id=141, address=282, key='battery_id_word_11', name='Battery ID word 11', scale=10, decimals=1, unit='', size=2),
    Register(id=142, address=284, key='battery_id_word_12', name='Battery ID word 12', scale=10, decimals=1, unit='', size=2),
    Register(id=143, address=286, key='battery_id_word_13', name='Battery ID word 13', scale=10, decimals=1, unit='', size=2),
    Register(id=144, address=288, key='battery_id_word_14', name='Battery ID word 14', scale=10, decimals=1, unit='', size=2),
    Register(id=145, address=290, key='battery_id_word_15', name='Battery ID word 15', scale=10, decimals=1, unit='', size=2),
    Register(id=146, address=292, key='battery_id_word_16', name='Battery ID word 16', scale=10, decimals=1, unit='', size=2),
    Register(id=147, address=294, key='reserved_6', name='Reserved', scale=10, decimals=1, unit='', size=2),
    Register(id=148, address=296, key='reserved_7', name='Reserved', scale=10, decimals=1, unit='', size=2),
    Register(id=149, address=298, key='current_sensor_range', name='Current sensor range', scale=10, decimals=1, unit='', size=2),
    Register(id=150, address=300, key='no_current_auto_standby_time_s', name='No-current auto-standby time (s)', scale=1, decimals=0, unit='', size=2),
    Register(id=151, address=302, key='bluetooth_address_code', name='Bluetooth address code', scale=1, decimals=0, unit='', size=2),
    Register(id=152, address=304, key='static_consumption_current', name='Static consumption current', scale=10, decimals=1, unit='', size=2),
    Register(id=153, address=306, key='battery_temp_sensor_mask', name='Battery temp-sensor mask', scale=1, decimals=0, unit='', size=2),
    Register(id=154, address=308, key='startup_current', name='Startup current', scale=1, decimals=0, unit='', size=2),
    Register(id=155, address=310, key='system_reference_voltage', name='System reference voltage', scale=1000, decimals=3, unit='', size=2),
    Register(id=156, address=312, key='pack_voltage_conversion_factor', name='Pack voltage conversion factor', scale=1, decimals=0, unit='', size=2),
    Register(id=157, address=314, key='system_run_time', name='System run time', scale=1, decimals=0, unit='', size=2),
    Register(id=158, address=316, key='discharge_prohibited_duration', name='Discharge-prohibited duration', scale=1, decimals=0, unit='', size=2),
    Register(id=159, address=318, key='charge_prohibited_duration', name='Charge-prohibited duration', scale=1, decimals=0, unit='', size=2),
    Register(id=160, address=320, key='discharge_allowed_duration', name='Discharge-allowed duration', scale=1, decimals=0, unit='', size=2),
    Register(id=161, address=322, key='charge_allowed_duration', name='Charge-allowed duration', scale=1, decimals=0, unit='', size=2),
    Register(id=162, address=324, key='jumper_config_l', name='Jumper config L', scale=1, decimals=0, unit='', size=2),
    Register(id=163, address=326, key='jumper_config_h', name='Jumper config H', scale=1, decimals=0, unit='', size=2),
]

# Registers that are the HIGH word of the preceding 32-bit value -> skip when iterating
CAPACITY_HIGH_WORD_ADDRESSES = {164, 168, 172}

REG_BY_KEY = {r.key: r for r in REGISTERS}
REG_BY_ADDR = {r.address: r for r in REGISTERS}
REG_BY_ID = {r.id: r for r in REGISTERS}

# Address ranges the official app reads to cover all settings (start, length).
# Used for full read / backup. Mirrors the per-page reads in the app.
SETTINGS_READ_CHUNKS = [
    (0, 52), (56, 44), (104, 32), (140, 12), (152, 142), (298, 34),
]

# Setting groups, matching the app's settings pages (each page reads one address
# range). Order = the order the pages appear in the app. ``page`` is the source
# .vue file name (romanized), kept only as a cross-reference back to the app.
SETTING_GROUPS = [
    {"key": 'voltage', "label": 'Voltage', "desc": 'Cell & pack voltage protection / alarm', "page": 'dianya.vue', "lo": 0, "hi": 56},
    {"key": 'temperature', "label": 'Temperature', "desc": 'Charge / discharge / MOS temperature protection', "page": 'wendu.vue', "lo": 56, "hi": 104},
    {"key": 'current', "label": 'Current', "desc": 'Charge / discharge over-current protection', "page": 'dianliu.vue', "lo": 104, "hi": 140},
    {"key": 'balance', "label": 'Balance', "desc": 'Cell balancing', "page": 'junheng.vue', "lo": 140, "hi": 152},
    {"key": 'battery', "label": 'Battery', "desc": 'Capacity, SOC curve, wiring resistance, battery IDs', "page": 'dianchi.vue', "lo": 152, "hi": 294},
    {"key": 'system', "label": 'System', "desc": 'System & hardware configuration', "page": 'xitong.vue', "lo": 294, "hi": 332},
]

GROUP_ORDER = [g["key"] for g in SETTING_GROUPS]
GROUP_LABELS = {g["key"]: g["label"] for g in SETTING_GROUPS}


def group_for_address(address: int) -> str:
    """Return the app group key a settings byte address belongs to."""
    for g in SETTING_GROUPS:
        if g["lo"] <= address < g["hi"]:
            return g["key"]
    return "other"
