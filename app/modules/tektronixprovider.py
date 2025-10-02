# modules/tektronixprovider.py
import pandas as pd
import logging
from typing import Dict, Any, List, Tuple, Optional
from struct import unpack
from tm_devices import DeviceManager
from tm_devices.drivers import MDO3K
from core.parser import Channel

logger = logging.getLogger(__name__)

class TektronixError(Exception):
    """Базовое исключение для ошибок Tektronix"""
    pass

class TektronixCommunicationError(TektronixError):
    """Ошибка связи с прибором"""
    pass

class TektronixAcquisitionError(TektronixError):
    """Ошибка получения данных от прибора"""
    pass

class TektronixProvider:
    USB_IDS = {'0699': ['0408', '0409', '0410']}  # Tektronix Vendor IDs
    
    def __init__(self, resource_name: str = None):
        self.resource_name = resource_name
        self.device_manager = None
        self.scope = MDO3K
        self.chnum = 4
        self.connection_status = 0
        self.model_name = ""
        
    def connect(self) -> bool:
        """Установка соединения с прибором"""
        try:
            self.device_manager = DeviceManager(verbose=False)
            self.scope = self.device_manager.add_scope(self.resource_name)
            
            # Получаем информацию о устройстве
            self.model_name = self.scope.model
            self._determine_channel_count()
            
            self.connection_status = 1
            logger.info(f"Connected to {self.model_name} with {self.chnum} channels")
            return True
            
        except Exception as e:
            self.connection_status = 0
            logger.error(f"Connection failed: {str(e)}")
            raise TektronixCommunicationError(f"Connection failed: {str(e)}")
        
    def _determine_channel_count(self):
        """Определение количества каналов на основе модели прибора"""
        self.chnum = self.scope.total_channels
        
    def disconnect(self):
        """Разрыв соединения с прибором"""
        try:
            if self.device_manager:
                self.device_manager.remove_all_devices()
                self.device_manager.close()
            self.connection_status = 0
            logger.info("Disconnected from device")
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            raise TektronixCommunicationError(f"Disconnect failed: {str(e)}")
        
    def is_channel_on(self, ch: int) -> bool:
        """Проверка активности канала"""
        try:
            if not 1 <= ch <= self.chnum:
                raise ValueError(f"Invalid channel number: {ch}")
                
            response = self.scope.commands.select.ch[ch].query()
            return response == "1" or "ON" in response.upper()
        except Exception as e:
            logger.error(f"Channel status check failed: {str(e)}")
            raise TektronixCommunicationError(f"Channel status check failed: {str(e)}")
        
    def get_channel_data(self, ch: int) -> Optional[Channel]:
        """Получение данных с канала"""
        try:
            if not 1 <= ch <= self.chnum:
                raise ValueError(f"Invalid channel number: {ch}")
                
            if not self.is_channel_on(ch):
                logger.warning(f"Channel {ch} is disabled")
                return None
            
            # Настраиваем параметры данных
            self.scope.commands.data.source.write(f"CH{ch}")
            self.scope.commands.data.encdg.write("RIBINARY")  # Signed integer binary
            self.scope.commands.data.width.write(2)  # 2 bytes per point
            self.scope.commands.data.start.write(1)
            
            # Получаем количество точек
            record_length = int(self.scope.commands.horizontal.recordlength.query())
            self.scope.commands.data.stop.write(record_length)
            
            # Получаем параметры waveform
            ymult = float(self.scope.commands.wfmoutpre.ymult.query())
            yzero = float(self.scope.commands.wfmoutpre.yzero.query())
            yoff = float(self.scope.commands.wfmoutpre.yoff.query())
            xincr = float(self.scope.commands.wfmoutpre.xincr.query())
            
            # Используем низкоуровневые методы для чтения бинарных данных
            self.scope.write("CURVe?")
            
            # Читаем сырые бинарные данные
            raw_data = self.scope.read_raw()
            
            # Обрабатываем бинарный формат TEKTRONIX
            if not raw_data.startswith(b'#'):
                raise TektronixAcquisitionError("Invalid binary data format")
            
            # Получаем количество цифр в длине данных
            n_digits = int(raw_data[1:2])
            
            # Извлекаем длину данных
            data_length_str = raw_data[2:2+n_digits].decode('ascii')
            data_length = int(data_length_str)
            
            # Извлекаем бинарные данные (пропускаем заголовок)
            header_length = 2 + n_digits
            binary_data = raw_data[header_length:header_length + data_length]
            
            # Преобразуем сырые данные в напряжения
            points_num = len(binary_data) // 2
            raw_values = unpack(f'>{points_num}h', binary_data)
            amplitudes = [(value - yoff) * ymult + yzero for value in raw_values]
            
            # Создаем временную ось
            times = [i * xincr for i in range(points_num)]
            
            # Создаем канал и заполняем данными
            channel = Channel(f"CH{ch}")
            channel.set_data(pd.Series(times), pd.Series(amplitudes))
            
            return channel
            
        except Exception as e:
            logger.error(f"Failed to get data from channel {ch}: {str(e)}")
            return None

    def TimeBase_scale(self, value: float = None) -> str:
        """Установка/получение масштаба временной развертки"""
        try:
            if value is not None:
                return self.scope.commands.horizontal.scale.write(value)
            else:
                return self.scope.commands.horizontal.scale.query()
        except Exception as e:
            logger.error(f"TimeBase_scale failed: {str(e)}")
            raise TektronixCommunicationError(f"TimeBase operation failed: {str(e)}")
        
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()