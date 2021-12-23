from __future__ import absolute_import, unicode_literals

import logging
import os

import serial
import struct
from modbus_tk.defines import (
    COILS, DISCRETE_INPUTS, HOLDING_REGISTERS, ANALOG_INPUTS)
from modbus_tk.modbus_rtu import RtuServer, RtuMaster
from modbus_tk.modbus_tcp import TcpServer, TcpMaster
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder

from modbus_simulator.utils.common import path, make_dir, remove_file
from modbus_simulator.utils.pymodbus_server import DECODERS, ENCODERS

ADDRESS_RANGE = {
    COILS: 0,
    DISCRETE_INPUTS: 10001,
    HOLDING_REGISTERS: 40001,
    ANALOG_INPUTS: 30001

}

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
        if server == "tcp":
            self.server = TcpServer(*args, port=kwargs['port'],address=kwargs['address'])
        else:
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
        slave.set_values(block_name, int(address), values)

    def get_values(self, slave_id, block_name, address, size=1):
        slave = self.server.get_slave(slave_id)
        return slave.get_values(block_name, int(address), size)

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

    def decode(self, slave_id, block_name, offset, formatter):
        count = 1
        offset = int(offset)
        if '32' in formatter:
            count = 2
        elif '64' in formatter:
            count = 4
        values = self.get_values(slave_id, block_name, offset, count)
        values = list(values)
        if values:
            decoder = BinaryPayloadDecoder.fromRegisters(
                values, byteorder=Endian.Big, wordorder=Endian.Big)
            values = getattr(decoder, DECODERS.get(formatter))()
            return values, count

    def encode(self, slave_id, block_name, offset, value, formatter):
        builder = BinaryPayloadBuilder(byteorder=Endian.Big,
                                       wordorder=Endian.Big)
        add_method = ENCODERS.get(formatter)
        if 'int' in add_method:  # Temp fix
            value = int(value)
        getattr(builder, add_method)(value)
        payload = builder.to_registers()
        return self.set_values(slave_id, block_name, int(offset), payload)


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
