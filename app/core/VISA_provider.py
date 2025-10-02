# core/VISA_provider.py
import pyvisa
from typing import Optional, Union, Type
from types import TracebackType
import logging
import time

class VISError(Exception):
    """Базовое исключение для ошибок VISA"""
    pass

class VISConnectionError(VISError):
    """Ошибка подключения к VISA-устройству"""
    pass

class VISTimeoutError(VISError):
    """Ошибка таймаута операции"""
    pass

class VISReadWriteError(VISError):
    """Ошибка чтения/записи"""
    pass

class VISAProvider:
    DEFAULT_SETTINGS = {
        'default': {
            'timeout': 5000,  # таймаут в мс
            'read_terminator': '\n',
            'write_terminator': '\n',
            'chunk_size': 4096,
            'query_delay': 0.1
        }
    }
    
    def __init__(self, resource_name: Optional[str] = None, device_type: str = 'default',
                 logger: Optional[logging.Logger] = None, **kwargs):
        self.resource_name = resource_name
        self.device_type = device_type
        self.rm = pyvisa.ResourceManager()
        self.session = None
        self.is_connected = False
        self.settings = self.DEFAULT_SETTINGS.get(device_type, {}).copy()
        self.settings.update(kwargs)
        self.logger = logger or logging.getLogger(__name__)

    def connect(self, resource_name: Optional[str] = None) -> None:
        if resource_name is not None:
            self.resource_name = resource_name
        if not self.resource_name:
            raise VISConnectionError("Resource name not specified")

        try:
            self.session = self.rm.open_resource(self.resource_name)
            # Применяем настройки
            self.session.timeout = self.settings['timeout']
            self.session.read_termination = self.settings['read_terminator']
            self.session.write_termination = self.settings['write_terminator']
            self.session.chunk_size = self.settings['chunk_size']
            self.session.query_delay = self.settings['query_delay']
            
            self.is_connected = True
            self.logger.info(f"Connected to {self.resource_name}")
            return True
            
        except pyvisa.Error as e:
            self.is_connected = False
            self.logger.error(f"Connection failed: {e}")
            raise VISConnectionError(f"Failed to connect to {self.resource_name}: {e}")

    def disconnect(self) -> None:
        if self.session:
            self.session.close()
            self.is_connected = False
            self.logger.info(f"Disconnected from {self.resource_name}")

    def write(self, data: str) -> None:
        if not self.is_connected or not self.session:
            raise VISConnectionError("Not connected to VISA device")
            
        try:
            self.session.write(data)
        except pyvisa.Error as e:
            self.is_connected = False
            self.logger.error(f"Write failed: {e}")
            raise VISReadWriteError(f"Write operation failed: {e}")

    def read(self) -> str:
        if not self.is_connected or not self.session:
            raise VISConnectionError("Not connected to VISA device")
            
        try:
            return self.session.read()
        except pyvisa.Error as e:
            self.is_connected = False
            self.logger.error(f"Read failed: {e}")
            raise VISReadWriteError(f"Read operation failed: {e}")

    def read_raw(self) -> bytes:
        if not self.is_connected or not self.session:
            raise VISConnectionError("Not connected to VISA device")
            
        try:
            return self.session.read_raw()
        except pyvisa.Error as e:
            self.is_connected = False
            self.logger.error(f"Read raw failed: {e}")
            raise VISReadWriteError(f"Read raw operation failed: {e}")

    def query(self, command: str, delay: float = 0.1) -> str:
        if not self.is_connected or not self.session:
            raise VISConnectionError("Not connected to VISA device")
            
        try:
            return self.session.query(command)
        except pyvisa.Error as e:
            self.is_connected = False
            self.logger.error(f"Query failed: {e}")
            raise VISReadWriteError(f"Query operation failed: {e}")

    def clear_buffers(self) -> None:
        if self.session:
            try:
                self.session.clear()
            except pyvisa.Error as e:
                self.logger.warning(f"Clear buffers failed: {e}")

    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type: Optional[Type[BaseException]], 
                 exc_val: Optional[BaseException], 
                 exc_tb: Optional[TracebackType]) -> bool:
        self.disconnect()
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    try:
        with VISAProvider('TCPIP0::192.168.1.1::INSTR') as visa:
            response = visa.query("*IDN?")
            print(f"Device ID: {response}")
    except VISError as e:
        print(f"VISA error occurred: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
