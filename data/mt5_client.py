import MetaTrader5 as mt5
import pandas as pd
import logging

logger = logging.getLogger("GoldAI.MT5Client")

class MT5Client:
    """
    จัดการการเชื่อมต่อและดึงข้อมูลจาก MetaTrader 5
    เวอร์ชัน: Signal-Only (Data Provider)
    """
    def __init__(self, symbol, login=None, password=None, server=None):
        self.symbol = symbol
        self.login = login
        self.password = password
        self.server = server

    def connect(self):
        if self.login and self.password:
            initialized = mt5.initialize(login=self.login, password=self.password, server=self.server)
        else:
            initialized = mt5.initialize()

        if not initialized:
            logger.error(f"MT5 Initialize Failed: {mt5.last_error()}")
            return False
        if not mt5.symbol_select(self.symbol, True):
            logger.error(f"MT5 Symbol Select Failed for {self.symbol}: {mt5.last_error()}")
            mt5.shutdown()
            return False
        logger.info(f"Connected to MT5 successfully for {self.symbol}")
        return True

    def ensure_connection(self):
        """ตรวจสอบการเชื่อมต่อและลอง Reconnect หากหลุด"""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is not None:
            return True
        
        logger.warning("MT5 connection lost. Attempting to reconnect...")
        for i in range(3):
            try:
                if self.connect():
                    logger.info(f"Reconnected to MT5 on attempt {i+1}")
                    return True
            except Exception as e:
                logger.error(f"Reconnect attempt {i+1} failed: {e}")
        
        logger.critical("Could not restore MT5 connection after 3 attempts.")
        return False

    def get_rates(self, timeframe, count=300):
        """ดึงข้อมูลแท่งเทียนย้อนหลัง"""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            logger.warning(f"Failed to get rates for {self.symbol} on timeframe {timeframe}")
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_current_price(self):
        """ดึงราคา Ask/Bid ปัจจุบัน"""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logger.warning(f"Failed to get tick for {self.symbol}")
            return None
        return tick.ask, tick.bid

    def get_point(self):
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return None
        return float(symbol_info.point)

    def shutdown(self):
        logger.info("Shutting down MT5 connection")
        mt5.shutdown()
