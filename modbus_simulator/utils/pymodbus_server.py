from __future__ import absolute_import, unicode_literals

from pymodbus.server.sync import ModbusSerialServer
from pymodbus.server.sync import ModbusTcpServer
from pymodbus.server.sync import ModbusSingleRequestHandler
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext

from pymodbus.transaction import ModbusRtuFramer
from pymodbus.payload import BinaryPayloadDecoder, Endian, BinaryPayloadBuilder

from threading import Thread, RLock
import logging

log = logging.getLogger(__name__)

SERVERS = {
    "tcp": ModbusTcpServer,
    "rtu": ModbusSerialServer
}

_FX_MAPPER = {
    "coils": 1,
    'discrete_inputs': 2,
    'input_registers': 4,
    'holding_registers': 3
}

_STORE_MAPPER = {
    "coils": "c",
    'discrete_inputs': 'd',
    'input_registers': 'i',
    'holding_registers': 'h'
}

DECODERS = {
    'int16': "decode_16bit_int",
    'int32': "decode_32bit_int",
    'int64': "decode_64bit_int",
    'uint16': "decode_16bit_uint",
    'uint32': "decode_32bit_uint",
    'uint64': "decode_64bit_uint",
    'float32': "decode_32bit_float",
    'float64': "decode_64bit_float",

}

ENCODERS = {
    'int16': "add_16bit_int",
    'int32': "add_32bit_int",
    'int64': "add_64bit_int",
    'uint16': "add_16bit_uint",
    'uint32': "add_32bit_uint",
    'uint64': "add_64bit_uint",
    'float32': "add_32bit_float",
    'float64': "add_64bit_float",

}


class CustomDataBlock(ModbusSequentialDataBlock):

    def __init__(self, *args, **kwargs):
        super(CustomDataBlock, self).__init__(*args, **kwargs)
        self._data_lock = RLock()

    def update(self, size):
        with self._data_lock:
            values = [self.default_value] * size
            self.values.extend(values)


class CustomSingleRequestHandler(ModbusSingleRequestHandler):

    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.running = True
        self.setup()


class MbusSerialServer(ModbusSerialServer):

    handler = None

    def __init__(self, *args, **kwargs):
        super(MbusSerialServer, self).__init__(*args, **kwargs)
        self._build_handler()

    def _build_handler(self):
        ''' A helper method to create and monkeypatch
            a serial handler.

        :returns: A patched handler
        '''
        request = self.socket
        request.send = request.write
        request.recv = request.read
        self.handler = CustomSingleRequestHandler(request,
            (self.device, self.device), self)

    def serve_forever(self):
        ''' Callback for connecting a new client thread

        :param request: The request to handle
        :param client: The address of the client
        '''
        log.debug("Started thread to serve client")
        if not self.handler:
            self._build_handler()
        while self.is_running:
            self.handler.handle()

    def server_close(self):
        ''' Callback for stopping the running server
        '''
        log.debug("Modbus server stopped")
        self.is_running = False
        self.handler.finish()
        self.handler.running = False
        self.handler = None
        self.socket.close()


class ThreadedModbusServer(Thread):

    def __init__(self, server):
        super(ThreadedModbusServer, self).__init__(name="ModbusServerThread")
        self._server = server
        self.daemon = True

    def run(self):
        self._server.serve_forever()

    def stop(self):
        if isinstance(self._server, ModbusTcpServer):
            self._server.shutdown()
        else:
            if self._server.socket:
                self._server.server_close()


class ModbusSimu(object):
    _server_add = ()

    def __init__(self, server="tcp", *args, **kwargs):
        # initialize server information
        self.identity = ModbusDeviceIdentification()
        self._add_device_info()
        self._server_type = server
        self._port = kwargs.get('port', None)

        self.context = ModbusServerContext(single=False)
        self.simulate = kwargs.get('simulate', False)
        byte_order = kwargs.pop("byte_order", "big")
        word_order = kwargs.pop("word_order", "big")
        self.byte_order = Endian.Big if byte_order == "big" else Endian.Little
        self.word_order = Endian.Big if word_order == "big" else Endian.Little
        self.dirty = False
        if server == "tcp":
            self._port = int(self._port)
            self._address = kwargs.get("address", "localhost")
            self.server = ModbusTcpServer(self.context,
                                          identity=self.identity,
                                          address=(self._address, self._port))
        else:
            self.server = MbusSerialServer(self.context,
                                           framer=ModbusRtuFramer,
                                           identity=self.identity, **kwargs)
        self.server_thread = ThreadedModbusServer(self.server)

    def _add_device_info(self):
        self.identity.VendorName = 'Riptide'
        self.identity.ProductCode = 'sim-007'
        self.identity.VendorUrl = 'http://github.com/riptideio/'
        self.identity.ProductName = 'Modbus Server'
        self.identity.ModelName = 'Modbus Server'
        self.identity.MajorMinorRevision = '2.0.0'

    @property
    def server_type(self):
        return self._server_type

    @property
    def port(self):
        return self._port

    def _add_default_slave_context(self):
        return ModbusSlaveContext(
            di=CustomDataBlock(0, 0),
            hr=CustomDataBlock(0, 0),
            co=CustomDataBlock(0, 0),
            ir=CustomDataBlock(0, 0),

        )

    @staticmethod
    def _calc_offset(block_name, address):
        address = int(address)
        if block_name == "coils":
            return address
        elif block_name == "discrete_inputs":
            return address-10001 if address >= 10001 else address
        elif block_name == "input_registers":
            return address - 30001 if address >= 30001 else address
        else:
            return address - 40001 if address >= 40001 else address

    def add_slave(self, slave_id):
        self.context[slave_id] = self._add_default_slave_context()

    def remove_slave(self, slave_id):
        del self.context[slave_id]

    def remove_all_slave(self):
        self.context = ModbusServerContext(single=False)

    def add_block(self, slave_id, block_name, block_type, starting_add, size):
        slave = self.get_slave(slave_id)
        if not slave.validate(_FX_MAPPER[block_name], starting_add, count=size):
            slave.store[_STORE_MAPPER[block_name]].update(size)
        else:
            log.debug("Block '{}' on slave '{}' already exists".format(block_name, slave_id))

    def remove_block(self, slave_id, block_name):
        slave = self.get_slave(slave_id)
        slave.store[_STORE_MAPPER[block_name]].reset()

    def remove_all_blocks(self, slave_id):
        slave = self.get_slave(slave_id)
        slave.remove_all_blocks()

    def set_values(self, slave_id, block_name, address, values):
        values = values if isinstance(values, (list, tuple)) else [values]
        slave = self.get_slave(slave_id)
        address = self._calc_offset(block_name, address)
        if slave.validate(_FX_MAPPER[block_name], address, count=len(values)):
            slave.setValues(_FX_MAPPER[block_name], address, values)

    def get_values(self, slave_id, block_name, address, size=1):
        slave = self.get_slave(slave_id)
        address = self._calc_offset(block_name, address)
        if slave.validate(_FX_MAPPER[block_name], address, count=size):
            return slave.getValues(_FX_MAPPER[block_name], address, size)

    def get_slave(self, slave_id):
        return self.context[slave_id]

    def decode(self, slave_id, block_name, offset, formatter):
        count = 1
        if '32' in formatter:
            count = 2
        elif '64' in formatter:
            count = 4
        values = self.get_values(slave_id, block_name, offset, count)
        if values:
            decoder = BinaryPayloadDecoder.fromRegisters(
                values, byteorder=self.byte_order, wordorder=self.word_order)
            values = getattr(decoder, DECODERS.get(formatter))()
            return values, count

    def encode(self, slave_id, block_name, offset, value, formatter):
        builder = BinaryPayloadBuilder(byteorder=self.byte_order,
                                       wordorder=self.word_order)
        add_method = ENCODERS.get(formatter)
        getattr(builder, add_method)(value)
        payload = builder.to_registers()
        return self.set_values(slave_id, block_name, offset, payload)

    def start(self):
        if self.dirty:
            self.server_thread = ThreadedModbusServer(self.server)
        self.server_thread.start()

    def stop(self):
        self.server_thread.stop()
        self.dirty = True
        # if self._server_type == 'rtu':
        #     self._serial.close()
        # self._server_add = ()

    def get_slaves(self):
        if self.server is not None:
            return self.server._databank._slaves


if __name__ == "__main__":
    s = ModbusSimu(server="rtu", port="/dev/ptyp0")
    # s = ModbusSimu(address="localhost", port=5020)
    s.start()
    s.add_slave(1)
    s.add_block(1, "holding registers", "holding_registers", 0, 100)
    s.add_block(1, "coils", "holding_registers", 0, 100)
    s.set_values(1, "holding registers", 0, [34] * 55)
    log.info(s.get_values(1, "holding registers", 0, 100))
    s.stop()
