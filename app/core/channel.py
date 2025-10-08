# core/channel.py

import pandas as pd
import logging

logger = logging.getLogger(__name__)

class Channel:
    """Класс для хранения данных канала"""
    
    def __init__(self, name, data=None):
        self.name = name
        self.data = data if data is not None else pd.DataFrame()
    
    def __repr__(self):
        return f"Channel(name='{self.name}', data_shape={self.data.shape})"
    
    def copy(self):
        """Создание копии канала"""
        return Channel(self.name, self.data.copy())