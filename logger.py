import os
import logging
import time
import threading
from datetime import datetime

class Logger:
    def __init__(self, log_dir='logs', log_level=logging.INFO, check_interval=60):
        self.log_dir = log_dir
        self.log_level = log_level
        self.check_interval = check_interval  # 检查日期变更的间隔（秒）
        self.logger = None
        self.file_handler = None
        self.current_date = None
        self.current_log_file = None
        self.running = False
        self.thread = None
        
        # 确保日志目录存在
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.abs_log_dir = os.path.join(base_dir, self.log_dir)
        if not os.path.exists(self.abs_log_dir):
            os.makedirs(self.abs_log_dir, exist_ok=True)
        
        # 初始化日志记录器
        self._setup_logger()
        
    def _setup_logger(self):
        """设置日志记录器"""
        # 创建logger
        self.logger = logging.getLogger('app_logger')
        self.logger.setLevel(self.log_level)
        
        # 清除现有的处理器
        if self.logger.handlers:
            for handler in self.logger.handlers:
                self.logger.removeHandler(handler)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 创建文件处理器
        self._setup_file_handler()
    
    def _setup_file_handler(self):
        """设置文件处理器"""
        # 获取当前日期
        now = datetime.now()
        self.current_date = now.date()
        
        # 生成日志文件名 (格式: YYYYMMDD_HHMMSS.log)
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        self.current_log_file = os.path.join(self.abs_log_dir, f"{timestamp}.log")
        
        # 创建文件处理器
        if self.file_handler:
            self.logger.removeHandler(self.file_handler)
            self.file_handler.close()
        
        self.file_handler = logging.FileHandler(self.current_log_file, encoding='utf-8')
        self.file_handler.setLevel(self.log_level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.file_handler.setFormatter(file_formatter)
        self.logger.addHandler(self.file_handler)
        
        self.logger.info(f"日志文件已创建: {self.current_log_file}")
    
    def _rename_log_file(self):
        """将当前日志文件重命名为日期格式"""
        if not self.current_log_file or not os.path.exists(self.current_log_file):
            return
        
        # 生成新的文件名 (格式: YYYY-MM-DD.log)
        new_filename = os.path.join(self.abs_log_dir, f"{self.current_date.strftime('%Y-%m-%d')}.log")
        
        # 如果已存在同名文件，先备份
        if os.path.exists(new_filename):
            backup_filename = os.path.join(self.abs_log_dir, f"{self.current_date.strftime('%Y-%m-%d')}_backup_{int(time.time())}.log")
            try:
                os.rename(new_filename, backup_filename)
                self.logger.info(f"已备份现有日志文件: {new_filename} -> {backup_filename}")
            except Exception as e:
                self.logger.error(f"备份日志文件失败: {str(e)}")
        
        # 关闭当前文件处理器
        self.logger.removeHandler(self.file_handler)
        self.file_handler.close()
        
        # 重命名文件
        try:
            os.rename(self.current_log_file, new_filename)
            self.logger.info(f"日志文件已重命名: {self.current_log_file} -> {new_filename}")
        except Exception as e:
            self.logger.error(f"重命名日志文件失败: {str(e)}")
    
    def _check_date_change(self):
        """检查日期是否变更，如果变更则轮转日志"""
        while self.running:
            try:
                # 获取当前日期
                now = datetime.now()
                current_date = now.date()
                
                # 如果日期已变更
                if current_date != self.current_date:
                    self.logger.info(f"检测到日期变更: {self.current_date} -> {current_date}")
                    
                    # 重命名旧日志文件
                    self._rename_log_file()
                    
                    # 更新当前日期
                    self.current_date = current_date
                    
                    # 创建新的日志文件
                    self._setup_file_handler()
            except Exception as e:
                # 使用控制台输出错误，因为logger可能已经失效
                print(f"检查日期变更时出错: {str(e)}")
            
            # 休眠指定的时间间隔
            time.sleep(self.check_interval)
    
    def start(self):
        """启动日志监控线程"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._check_date_change)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info("日志监控已启动，将在日期变更时自动轮转日志")
    
    def stop(self):
        """停止日志监控线程"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
        self.logger.info("日志监控已停止")
    
    def get_logger(self):
        """获取日志记录器"""
        return self.logger

# 创建全局日志实例
app_logger = None

def setup_logger(log_dir='logs', log_level=logging.INFO, check_interval=60):
    """设置全局日志记录器"""
    global app_logger
    if app_logger is None:
        app_logger = Logger(log_dir, log_level, check_interval)
        app_logger.start()
    return app_logger.get_logger()

def get_logger():
    """获取全局日志记录器"""
    global app_logger
    if app_logger is None:
        return setup_logger()
    return app_logger.get_logger()

def shutdown_logger():
    """关闭日志系统"""
    global app_logger
    if app_logger:
        app_logger.stop()
        app_logger = None