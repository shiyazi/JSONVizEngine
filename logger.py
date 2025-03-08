import os
import logging
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler


class Logger:
    def __init__(self, continuous_mode=False):
        """
        初始化日志系统
        :param continuous_mode: 是否为持续运行模式，True表示持续运行，False表示单次运行
        """
        self.continuous_mode = continuous_mode
        self.logger = logging.getLogger('JSONViz')
        self.logger.setLevel(logging.INFO)

        # 清除之前的处理器
        if self.logger.handlers:
            self.logger.handlers.clear()

        # 创建日志目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_dir = os.path.join(base_dir, 'log')
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)

        # 设置日志格式
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # 根据运行模式选择不同的文件处理器
        if continuous_mode:
            # 持续运行模式：按天轮转，文件名格式：2025-03-09.log
            file_handler = TimedRotatingFileHandler(
                os.path.join(self.log_dir, datetime.now().strftime('%Y-%m-%d') + '.log'),
                when='midnight',
                interval=1,
                backupCount=30,  # 保留30天的日志
                encoding='utf-8'
            )
            # 设置后缀名格式
            file_handler.suffix = '%Y-%m-%d.log'
        else:
            # 单次运行模式：每次生成一个新文件，文件名格式：20250309-022343.log
            log_filename = datetime.now().strftime('%Y%m%d-%H%M%S') + '.log'
            file_handler = RotatingFileHandler(
                os.path.join(self.log_dir, log_filename),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )

        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def get_logger(self):
        """
        获取日志记录器
        :return: 日志记录器实例
        """
        return self.logger


# 全局日志实例
_logger_instance = None


def init_logger(continuous_mode=False):
    """
    初始化日志系统
    :param continuous_mode: 是否为持续运行模式
    :return: 日志记录器实例
    """
    global _logger_instance
    _logger_instance = Logger(continuous_mode)
    return _logger_instance.get_logger()


def get_logger():
    """
    获取日志记录器，如果未初始化则自动初始化为单次运行模式
    :return: 日志记录器实例
    """
    global _logger_instance
    if _logger_instance is None:
        return init_logger(False)
    return _logger_instance.get_logger()