# core/parser.py
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

@dataclass
class ChannelMetadata:
    '''Метаданные канала осциллографа'''
    record_length: int = 0
    sample_interval: float = 0.0
    vertical_scale: float = 1.0
    vertical_offset: float = 0.0
    vertical_units: str = "V"
    horizontal_units: str = "s"
    probe: float = 1.0
    channel_name: str = ""

class Channel:
    def __init__(self, name):
        self.name = name
        self.data = pd.DataFrame(columns=['Время','Амплитуда'])
        self.metadata = ChannelMetadata(channel_name=name)
        self.raw_metadata = {}

    def set_data(self, time_data: pd.Series, amplitude_data: pd.Series):

        self.data = pd.DataFrame({
            'Время' : time_data.values,
            'Амплитуда' : amplitude_data.values
        })

    def set_metadata_from_dict(self, metadata_dict: Dict[str, Any]):

        self.raw_metadata = metadata_dict
        self.metadata = metadata_dict

        for raw_key, value in metadata_dict.items():
            if not isinstance(raw_key, str):
                continue

            raw_key_lower = raw_key.lower()

            #временная заглушка т.к в расчётах метаданные не используются
            #print(raw_key)


    def __repr__(self):
        return f'Канал {self.name}, размер массива {len(self.data)}'
            


class DataParser:
    '''Парсер данных осциллографа с поддержкой различных форматов'''
    def __init__(self):
        self.channels = {} # Dict[str, pd.DataFrame]

    def parsefile(self, file_path: str, file_type: str = 'csv') -> bool:
        '''
        Парсинг файла данных осциллографа
        Текстовый формат пока не реализован
        Args:
            file_path: путь к файлу
            file_type: тип файла ('xlsx/xls', 'csv', 'txt')
        
        Returns:
            bool: успешность парсинга
        '''
        try:
            if file_type == 'csv':
                return self._parse_csv(file_path)
            elif file_type == 'xlsx' or file_type == 'xls':
                return self._parse_excel(file_path)
            else:
                raise ValueError(f'Неподдерживаемый формат файла: {file_type}')
            
        except Exception as e:
            print(f'Функция чтения файла не работает')
            return False
        
    def _parse_excel(self, file_path: str) -> bool:
        '''Парсинг Excel файла с данными осциллографа'''
        try:
            with pd.ExcelFile(file_path) as xlsx:
                #Абсолютно глупо, что что бы получить название канала, надо указать название канала в структуре
                #Переделать что бы читалось из метаданных

                channel_structures = [
                    {
                        'metadata_cols': 'A:C',
                        'time_col': 'D',
                        'amplitude_col': 'E'
                    },
                    {
                        'metadata_cols': 'G:I',
                        'time_col': 'J',
                        'amplitude_col': 'K'
                    }
                ]

                for channel_info in channel_structures:
                    channel = self._parse_excel_channel(xlsx, channel_info)
                    if channel:
                        self.channels[channel.name] = channel
                
                return len(self.channels) > 0 
        except Exception as e:
            print(f"Ошибка парсинга Excel файла: {e}")
            return False

    
    def _parse_excel_channel(self, xlsx: pd.ExcelFile, channel_info: Dict[str, str]) -> Optional[Channel]:
        try:
            metadata_df = pd.read_excel(
                xlsx,
                usecols=channel_info['metadata_cols'],
                header=None,
                nrows=16
            ).dropna(how='all').T

            metadata_dict = dict(zip(metadata_df.iloc[0], metadata_df.iloc[1]))

            time_data = pd.read_excel(
                xlsx,
                usecols=channel_info['time_col'],
                header=None
            ).squeeze()

            amplitude_data = pd.read_excel(
                xlsx,
                usecols=channel_info['amplitude_col'],
                header=None
            ).squeeze()

            channel = Channel(metadata_dict['Source'])
            channel.set_data(time_data, amplitude_data) # type: ignore
            channel.set_metadata_from_dict(metadata_dict)

            return channel
        except Exception as e:
            print(f"Ошибка парсинга канала {channel_info['name']}: {e}")
            return None

    def _parse_csv(self, file_path: str) -> bool:
        '''Парсинг CSV файла с данными осциллографа'''
        try:
            #Используем контекстный менеджер для чтения CSV
            with open(file_path, 'r', encoding='utf-8') as file:
                df = pd.read_csv(file, header=None)
            
            # Остальной код без изменений
            metadata_ch1 = df.iloc[:16, 0:3].dropna(how='all').T
            metadata_ch2 = df.iloc[:16, 6:9].dropna(how='all').T
            data = df.iloc[:, [3, 4, 9, 10]]
            
            # Преобразование метаданных в словари
            metadata_dict_ch1 = dict(zip(metadata_ch1.iloc[0], metadata_ch1.iloc[1]))
            metadata_dict_ch2 = dict(zip(metadata_ch2.iloc[0], metadata_ch2.iloc[1]))
            
            # Создание и настройка каналов
            channel1 = Channel(metadata_dict_ch1['Source'])
            channel1.set_data(data.iloc[:, 0], data.iloc[:, 1])
            channel1.set_metadata_from_dict(metadata_dict_ch1)
            
            channel2 = Channel(metadata_dict_ch2['Source'])
            channel2.set_data(data.iloc[:, 2], data.iloc[:, 3])
            channel2.set_metadata_from_dict(metadata_dict_ch2)
            
            self.channels[channel1.name] = channel1
            self.channels[channel2.name] = channel2
            
            return True
            
        except Exception as e:
            print(f"Ошибка парсинга CSV файла: {e}")
            return False
    
    def get_channel_names(self) -> List[str]:
        '''Получение списка имен каналов'''
        return list(self.channels.keys())
    
    def get_channel(self, channel_name: str) -> Optional[Channel]:
        '''Получение канала по имени'''
        return self.channels.get(channel_name)   


if __name__ == '__main__':
    parser = DataParser()
    success = parser.parsefile('С-1 1-1,5 30.csv', 'csv')

    if not success:
        print('переделывай')

    for channel_name in parser.get_channel_names():
        print(channel_name)
        channel = parser.get_channel(channel_name)
        if channel:
            print(channel.data)
            print(channel.metadata)
            