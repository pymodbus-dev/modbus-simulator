from __future__ import absolute_import, unicode_literals
from modbus_tk.modbus_tcp import TcpServer, TcpMaster
from modbus_tk.modbus_rtu import RtuServer, RtuMaster
from modbus_tk.defines import (
    COILS, DISCRETE_INPUTS, HOLDING_REGISTERS, ANALOG_INPUTS)
import logging
from common import path, make_dir, remove_file
import os

ADDRESS_RANGE = {
    COILS: 0,
    DISCRETE_INPUTS: 10001,
    HOLDING_REGISTERS: 40001,
    ANALOG_INPUTS: 30001

}
import struct

REGISTER_QUERY_FIELDS = {"bit": range(1, 17),
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


class ModBusSimu(object):

    def __init__(self, server="tcp", *args, **kwargs):
        self.server = SERVERS.get(server, None)(*args, **kwargs)
        self.simulate = kwargs.get('simulate', False)

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

    def get_values(self, slave_id, block_name, address, size):
        slave = self.server.get_slave(slave_id)
        return slave.get_values(block_name, address, size)

    def start(self):
        self.server.start()
        self.sa = self.server._sa

    def stop(self):
        self.server.stop()


class ModBusMaster(object):
    def __init__(self, master="tcp", *args, **kwargs):
        self.master = MASTERS.get(master, None)(*args, **kwargs)

    def close(self):
        self.master.close()

    def get_value(self, ptype, slave_id, function_code, starting_address,
                  quantity_of_x=1, output_value=0, data_format="",
                  expected_length=-1, **kwargs):
        # if ptype in ["BI", "BO"]:
        #     return self._get_value(slave_id, function_code, starting_address,
        #           quantity_of_x, output_value, data_format,
        #           expected_length)
        # else:
        return self._get_formatted_value(ptype, slave_id,
                                         function_code, starting_address,
                                         quantity_of_x, **kwargs)

    def _get_value(self, slave_id, function_code, starting_address,
                   quantity_of_x=1, output_value=0, data_format="",
                   expected_length=-1):
        starting_address -= ADDRESS_RANGE[function_code]
        return self.master.execute(slave_id, function_code, starting_address,
                                   quantity_of_x, output_value, data_format,
                                   expected_length)

    def _get_formatted_value(self, ptype, slave_id, function_code,
                             starting_address,
                             quantity_of_x, **kwargs):
        # pre process
        # The register data in the response message are packed as two bytes
        # per register, with the binary contents right justified within
        # each byte. For each register, the first byte contains the high
        # order bits and the second contains the low order bits.
        wordcount = kwargs.get("wordcount", 1)
        quantity_of_x *= wordcount

        raw_val = self._get_value(slave_id, function_code,
                                  starting_address, quantity_of_x)
        formatter = kwargs.get("formatter", "default")

        # post process
        if ptype not in ["BI", "BO"]:
            byteorder = kwargs.get("byteorder", "big")
            wordorder = kwargs.get("wordorder", "big")
            if byteorder != "big":
                raw_val = swap_bytes(raw_val)
            if wordcount > 1:
                raw_val = process_words(raw_val)
            if wordorder != "big":
                raw_val = change_word_endianness(raw_val)
            if formatter == "float1":
                raw_val = pack_float(raw_val)
            scalemultiplier = kwargs.get("scalemultiplier", 1)

            scaledivisor = kwargs.get("scaledivisor", 1.0)
            scaledivisor = float(scaledivisor)

            bit = kwargs.get("bit", "")
            if bit != "":
                raw_val = get_bit(raw_val[0], bit)
            raw_val = [v*scalemultiplier for v in raw_val]
            raw_val = [v/scaledivisor for v in raw_val]
        return raw_val


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


def configure_modbus_logger(cfg, recycle_logs=True):
    """
    Configure the logger.

    Args:
        cfg (Namespace): The PUReST config namespace.
    """

    logger = logging.getLogger("modbus_tk")
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

