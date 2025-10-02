# modules/gwinstekprovider.py
import pandas as pd
import logging
from typing import Dict, Any, List, Tuple, Optional
from core.com_provider import COMProvider
from core.parser import Channel
from struct import unpack
import time
import re

# Настройка логирования
logger = logging.getLogger(__name__)

class GWInstekError(Exception):
    """Базовое исключение для ошибок GWInstek"""
    pass

class GWInstekCommunicationError(GWInstekError):
    """Ошибка связи с прибором"""
    pass

class GWInstekAcquisitionError(GWInstekError):
    """Ошибка получения данных от прибора"""
    pass

class GWInstekProvider:
    USB_IDS = {'2184': ['0043', '0044', '0045', '0046'], '098f': ['2205']}
    
    def __init__(self, port: str = None):
        if 'COM' in port:
            port = port
        elif 'ASRL' in port:
            port = port.replace('ASRL','COM')[:4]
        self.com = COMProvider(port, 'gwinstek')
        self.chnum = 4
        self.connection_status = 0
        self.model_name = ""
        
    def connect(self) -> bool:
        """Установка соединения с прибором"""
        try:
            if not self.com.connect():
                raise GWInstekCommunicationError("Failed to establish COM connection")
            
            response = self.com.query("*IDN?\n")
            if not response:
                raise GWInstekCommunicationError("No response to IDN query")
            
            parts = response.split(',')
            if len(parts) < 2:
                raise GWInstekCommunicationError(f"Invalid IDN response: {response}")
            
            self.model_name = parts[1]
            self._determine_channel_count()
            self.connection_status = 1
            logger.info(f"Connected to {self.model_name} with {self.chnum} channels")
            return True
            
        except Exception as e:
            self.connection_status = 0
            logger.error(f"Connection failed: {str(e)}")
            raise GWInstekCommunicationError(f"Connection failed: {str(e)}")
        
    def _determine_channel_count(self):
        """Определение количества каналов на основе модели прибора"""
        two_ch_models = [
            'DCS-1052B', 'GDS-1072B', 'DCS-1072B', 'IDS-1072B', 
            'GDS-71072B', 'GDS-1072R', 'GDS-1072E', 'DSO-1072D',
            'GDS-1102B', 'DCS-1102B', 'IDS-1102B', 'GDS-71102B',
            'GDS-1102R', 'GDS-1102E', 'DSO-1102D', 'GDS-1102DC',
            'GDS-1102EC', 'GDS-1102EY', 'GDS-1102B-LAN',
            'GDS-1152E', 'GDS-1202B', 'GDS-71202B', 'RSDS-1202B'
        ]
        four_ch_models = [
            'GDS-1054B', 'DCS-1054B', 'IDS-1054B', 'GDS-71054B',
            'GDS-1054R', 'GDS-1054E', 'GDS-1074B', 'DCS-1074B',
            'IDS-1074B', 'GDS-71074B', 'GDS-1074R', 'GDS-1074E',
            'DSO-1074D', 'GDS-1104B', 'DCS-1104B', 'IDS-1104B',
            'GDS-71104B', 'GDS-1104R', 'GDS-1104E', 'DSO-1104D',
            'GDS-1104EP'
        ]
        
        if any(model in self.model_name for model in two_ch_models):
            self.chnum = 2
        elif any(model in self.model_name for model in four_ch_models):
            self.chnum = 4
        else:
            logger.warning(f"Unknown model {self.model_name}, defaulting to 4 channels")
            self.chnum = 4
        
    def disconnect(self):
        """Разрыв соединения с прибором"""
        try:
            self.com.disconnect()
            self.connection_status = 0
            logger.info("Disconnected from device")
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            raise GWInstekCommunicationError(f"Disconnect failed: {str(e)}")
        
    def TimeBase_scale(self, value: float = None) -> str:
        """Установка/получение масштаба временной развертки"""
        try:
            if value is not None:
                command = f":TIMebase:SCALe {value}\n"
                return self.com.query(command)
            else:
                return self.com.query(":TIMebase:SCALe?\n")
        except Exception as e:
            logger.error(f"TimeBase_scale failed: {str(e)}")
            raise GWInstekCommunicationError(f"TimeBase operation failed: {str(e)}")
        
    def is_channel_on(self, ch: int) -> bool:
        """Проверка активности канала"""
        try:
            if not 1 <= ch <= self.chnum:
                raise ValueError(f"Invalid channel number: {ch}")
                
            response = self.com.query(f":CHAN{ch}:DISP?\n")
            return response.strip() == "ON"
        except Exception as e:
            logger.error(f"Channel status check failed: {str(e)}")
            raise GWInstekCommunicationError(f"Channel status check failed: {str(e)}")
        
    def get_channel_data(self, ch: int) -> Optional[Channel]:
        """Получение данных с канала"""
        try:
            if not 1 <= ch <= self.chnum:
                raise ValueError(f"Invalid channel number: {ch}")
                
            if not self.is_channel_on(ch):
                logger.warning(f"Channel {ch} is disabled")
                return None
            
            # Устанавливаем заголовок ответа
            self.com.write(":HEAD ON\n")
            
            # Проверяем статус acquisition
            self._check_acq_state(ch)
            
            # Запрашиваем данные
            self.com.write(f":ACQ{ch}:MEM?\n")
            
            # Читаем и парсим заголовок с метаданными
            header = self._read_ascii_header()
            metadata = self._parse_header(header)
            
            # Читаем бинарные данные
            raw_data = self._read_binary_data()
            
            # Создаем канал и заполняем данными
            channel = Channel(f"CH{ch}")
            channel.set_metadata_from_dict(metadata)
            
            # Преобразуем сырые данные в напряжения и временные метки
            time_data, amplitude_data = self._convert_raw_data(raw_data, metadata)
            channel.set_data(time_data, amplitude_data)
            
            return channel
            
        except GWInstekAcquisitionError as e:
            logger.warning(f"Partial data received for channel {ch}: {str(e)}")
            # Пытаемся обработать частичные данные
            if 'raw_data' in locals() and raw_data:
                try:
                    channel = Channel(f"CH{ch}")
                    channel.set_metadata_from_dict(metadata)
                    time_data, amplitude_data = self._convert_raw_data(raw_data, metadata)
                    channel.set_data(time_data, amplitude_data)
                    return channel
                except Exception as inner_e:
                    logger.error(f"Failed to process partial data: {str(inner_e)}")
                    return None
            else:
                logger.error(f"No data received for channel {ch}: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"Failed to get data from channel {ch}: {str(e)}")
            return None
        
    def _check_acq_state(self, ch: int):
        """Проверка статуса готовности данных"""
        for attempt in range(5):
            try:
                response = self.com.query(f":ACQ{ch}:STAT?\n")
                if response and response.strip() == "1":
                    return
                time.sleep(0.1)
            except Exception as e:
                logger.warning(f"Acquisition status check attempt {attempt+1} failed: {str(e)}")
        
        raise GWInstekAcquisitionError(f"Channel {ch} acquisition timeout")
        
    def _read_ascii_header(self) -> str:
        """Чтение текстового заголовка до маркера бинарных данных"""
        header_lines = []
        timeout = time.time() + 5  # 5 секунд таймаут
        
        while time.time() < timeout:
            line = self.com.read_line().strip()
            if line:
                header_lines.append(line)
                if "Waveform Data;" in line:
                    return "\n".join(header_lines)
        
        raise GWInstekAcquisitionError("ASCII header read timeout")
        
    def _parse_header(self, header: str) -> Dict[str, Any]:
        """Парсинг метаданных из заголовка"""
        try:
            metadata = {}
            pattern = r'([^,;]+),([^;]*);'
            matches = re.findall(pattern, header)
            
            for key, value in matches:
                if key not in ['Waveform Data']:
                    metadata[key.strip()] = value.strip()
                    
            return metadata
        except Exception as e:
            raise GWInstekAcquisitionError(f"Failed to parse header: {str(e)}")
        
    def _read_binary_data(self) -> bytes:
        """Чтение бинарных данных с правильной обработкой заголовка"""
        try:
            # Читаем начальный байт бинарного заголовка
            first_byte = self.com.read(1)
            if not first_byte or first_byte != b'#':
                raise GWInstekAcquisitionError("Invalid binary header start")
            
            # Читаем количество цифр в длине данных
            n_digits_byte = self.com.read(1)
            if not n_digits_byte:
                raise GWInstekAcquisitionError("No digit count received")
            
            n_digits = int(n_digits_byte)
            
            # Читаем длину данных
            length_bytes = self.com.read(n_digits)
            if not length_bytes:
                raise GWInstekAcquisitionError("No length bytes received")
            
            data_length = int(length_bytes)
            
            # Читаем сами данные
            raw_data = self.com.read(data_length)
            received_length = len(raw_data)
            
            if received_length != data_length:
                # Не все данные получены, но продолжаем с тем что есть
                logger.warning(f"Incomplete data received: {received_length}/{data_length} bytes")
                # Обрезаем до четного количества байт для корректной распаковки
                if received_length % 2 != 0:
                    raw_data = raw_data[:received_length - 1]
                    received_length -= 1
                    logger.warning(f"Trimmed 1 byte to make even length")
                
                if received_length == 0:
                    raise GWInstekAcquisitionError("No data received after trimming")
                    
                return raw_data

            return raw_data
            
        except Exception as e:
            raise GWInstekAcquisitionError(f"Binary data read failed: {str(e)}")
        
    def _convert_raw_data(self, raw_data: bytes, metadata: Dict[str, Any]) -> Tuple[pd.Series, pd.Series]:
        """Конвертация сырых данных в физические величины"""
        try:
            points_num = len(raw_data) // 2
            raw_values = unpack(f'>{points_num}h', raw_data)
            
            vdiv = float(metadata.get('Vertical Scale', 1))
            dt = float(metadata.get('Sampling Period', 1))
            vpos = float(metadata.get('Vertical Position', 0))
            
            dv = vdiv / 25
            amplitudes = [float(value) * dv for value in raw_values]
            
            times = [i * dt for i in range(points_num)]
            
            return pd.Series(times), pd.Series(amplitudes)
            
        except Exception as e:
            raise GWInstekAcquisitionError(f"Data conversion failed: {str(e)}")

    # Методы для работы с пробами (заглушки для будущей реализации)
    def ChanProbeRat(self, channel: int, ratio: float = None) -> float:
        """Установка/получение коэффициента пробника"""
        pass

    def ChanProbeType(self, channel: int) -> str:
        """Получение типа пробника"""
        pass
        
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()