from __future__ import absolute_import, unicode_literals

import logging
import os

import serial
from modbus_tk.defines import (
    COILS, DISCRETE_INPUTS, HOLDING_REGISTERS, ANALOG_INPUTS)
from modbus_tk.modbus_rtu import RtuServer, RtuMaster
from modbus_tk.modbus_tcp import TcpServer, TcpMaster

from modbus_simulator.utils.common import path, make_dir, remove_file

ADDRESS_RANGE = {
    COILS: 0,
    DISCRETE_INPUTS: 10001,
    HOLDING_REGISTERS: 40001,
    ANALOG_INPUTS: 30001

}
import struct

REGISTER_QUERY_FIELDS = {"bit": range(0, 16),
                         "byteorder": ["big", "little"],
                         "formatter": ["default", "float1"],
                         "scaledivisor": 1,
                         "scalemultiplier": 1,
                         "wordcount": 1,
                         "wordorder": ["big", "little"]}

SERVERS = {
    "tcp": TcpServer,
    "rtu": RtuServer
}

MASTERS = {
    "tcp": TcpMaster,
    "rtu": RtuMaster
}

BLOCK_TYPES = {"coils": COILS,
               "discrete_inputs": DISCRETE_INPUTS,
               "holding_registers": HOLDING_REGISTERS,
               "input_registers": ANALOG_INPUTS}
MODBUS_TCP_PORT = 5440


class PseudoSerial(object):
    def __init__(self, tty_name, **kwargs):
        self.ser = serial.Serial()
        self.ser.port = tty_name

        self.serial_conf(**kwargs)
        self.open()

    def serial_conf(self, **kwargs):
        self.ser.baudrate = kwargs.get('baudrate', 9600)
        self.ser.bytesize = kwargs.get('bytesize', serial.EIGHTBITS)
        self.ser.parity = kwargs.get('parity', serial.PARITY_NONE)
        self.ser.stopbits = kwargs.get('stopbits', serial.STOPBITS_ONE)
        self.ser.timeout = kwargs.get('timeout', 2)  # Non-Block reading
        self.ser.xonxoff = kwargs.get('xonxoff', False)  # Disable Software Flow Control
        self.ser.rtscts = kwargs.get('rtscts', False)  # Disable (RTS/CTS) flow Control
        self.ser.dsrdtr = kwargs.get('dsrdtr', False)  # Disable (DSR/DTR) flow Control
        self.ser.writeTimeout = kwargs.get('writetimeout', 2)

    def open(self):
        self.ser.open()
        self.ser.flushInput()
        self.ser.flushOutput()

    def close(self):
        self.ser.close()

    def get_serial_object(self):
        return self.ser


class ModbusSimu(object):
    _server_add = ()

    def __init__(self, server="tcp", *args, **kwargs):
        self._server_type = server
        self._port = kwargs.get('port', None)
        if server == 'rtu':
            tty_name = kwargs['port']
            kwargs.pop('port', None)
            self._serial = PseudoSerial(tty_name, **kwargs)
            kwargs = {k: v for k, v in kwargs.iteritems() if k == "serial"}
            kwargs['serial'] = self._serial.ser
        else:
            kwargs['port'] = int(kwargs['port'])
        self.server = SERVERS.get(server, None)(*args, **kwargs)
        self.simulate = kwargs.get('simulate', False)

    @property
    def server_type(self):
        return self._server_type

    @property
    def port(self):
        return self._port

    def add_slave(self, slave_id):
        self.server.add_slave(slave_id)

    def remove_slave(self, slave_id):
        self.server.remove_slave(slave_id)

    def remove_all_slave(self):
        self.server.remove_all_slaves()

    def add_block(self, slave_id, block_name, block_type, starting_add, size):
        slave = self.server.get_slave(slave_id)
        slave.add_block(block_name, block_type, starting_add, size)

    def remove_block(self, slave_id, block_name):
        slave = self.server.get_slave(slave_id)
        slave.remove_block(block_name)

    def remove_all_blocks(self, slave_id):
        slave = self.server.get_slave(slave_id)
        slave.remove_all_blocks()

    def set_values(self, slave_id, block_name, address, values):
        slave = self.server.get_slave(slave_id)
        slave.set_values(block_name, address, values)

    def get_values(self, slave_id, block_name, address, size=1):
        slave = self.server.get_slave(slave_id)
        return slave.get_values(block_name, address, size)

    def start(self):
        self.server.start()
        if self._server_type == "tcp":
            self._server_add = self.server._sa

    def stop(self):
        self.server.stop()
        if self._server_type == 'rtu':
            self._serial.close()
        self._server_add = ()

    def get_slaves(self):
        if self.server is not None:
            return self.server._databank._slaves


def swap_bytes(byte_array):
    temp = []
    for x in byte_array:
        temp.append(float(struct.unpack("<H", struct.pack(">H", x))[0]))
    return temp


def process_words(byte_array):
    temp = ""
    for x in byte_array:
        temp += "%04x" % x
    return [int(temp, 16)]


def change_word_endianness(words):
    pack_str = ">I" if len(words) > 1 else ">H"
    unpack_str = "<I" if len(words) > 1 else "<H"
    temp = []
    for x in words:
        temp.append(float(struct.unpack(unpack_str,
                                        struct.pack(pack_str, x))[0]))
    return temp


def get_bit(byteval, idx):
    # bitnum field in modbus proto implementation starts from 1 - 16 instead
    # of 0-15
    try:
        idx = int(idx)
    except ValueError:
        return byteval
    byteval = int(byteval)
    if idx == 0:
        idx = 1
    return [1 if (byteval & (1 << idx-1)) != 0 else 0]


def pack_float(words):
    temp = []
    for x in words:
        temp.append(struct.unpack("!f", ("%08x" % x).decode('hex'))[0])
    return temp


class Configuration:
    def __init__(self, no_modbus_log=False, no_modbus_console_log=False,
                 no_modbus_file_log=True, modbus_console_log_level="DEBUG",
                 modbus_file_log_level="DEBUG", modbus_log=""):
        self.no_modbus_log = no_modbus_log
        self.no_modbus_console_log = no_modbus_console_log
        self.no_modbus_file_log = no_modbus_file_log
        self.modbus_console_log_level = modbus_console_log_level
        self.modbus_file_log_level = modbus_file_log_level
        self.modbus_log = modbus_log

    def to_dict(self):
        return vars(self)


def configure_modbus_logger(cfg, protocol_logger ="modbus_tk",
                            recycle_logs=True):
    """
    Configure the logger.

    Args:
        cfg (Namespace): The PUReST config namespace.
    """

    logger = logging.getLogger(protocol_logger)
    if isinstance(cfg, dict):
        cfg = Configuration(**cfg)

    if cfg.no_modbus_log:
        logger.setLevel(logging.ERROR)
        logger.addHandler(logging.NullHandler())
    else:
        logger.setLevel(logging.DEBUG)
        fmt = (
            "%(asctime)s - %(levelname)s - "
            "%(module)s::%(funcName)s @ %(lineno)d - %(message)s"
        )
        fmtr = logging.Formatter(fmt)

        if not cfg.no_modbus_console_log:
            sh = logging.StreamHandler()
            sh.setFormatter(fmtr)
            sh.setLevel(cfg.modbus_console_log_level.upper())
            logger.addHandler(sh)

        if not cfg.no_modbus_file_log:
            modbus_log = path(cfg.modbus_log)
            if recycle_logs:
                remove_file(modbus_log)
            make_dir(os.path.dirname(modbus_log))
            fh = logging.FileHandler(modbus_log)
            fh.setFormatter(fmtr)
            fh.setLevel(cfg.modbus_file_log_level.upper())
            logger.addHandler(fh)

