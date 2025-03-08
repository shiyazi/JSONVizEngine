import os
import time
import threading
import json
from datetime import datetime
from flask_socketio import SocketIO
from logger import get_logger


class FileMonitor:
    def __init__(self, socketio, result_dir='result', history_dir='result/history', check_interval=2):
        self.socketio = socketio
        self.result_dir = result_dir
        self.history_dir = history_dir
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.logger = get_logger()

        # 记录上次检查时的文件状态
        self.last_result_files = set()
        self.last_history_files = set()

    def start(self):
        """启动文件监控线程"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_files)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info(f"文件监控已启动，监控目录: {self.result_dir} 和 {self.history_dir}")

    def stop(self):
        """停止文件监控线程"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
        self.logger.info("文件监控已停止")

    def _get_files_info(self, directory):
        """获取目录中的文件信息"""
        # 确保使用绝对路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        abs_directory = directory if os.path.isabs(directory) else os.path.join(base_dir, directory)

        if not os.path.exists(abs_directory):
            # 如果目录不存在，尝试创建
            try:
                os.makedirs(abs_directory, exist_ok=True)
            except Exception as e:
                self.logger.error(f"创建目录失败: {str(e)}")
            return set()

        # 获取所有json文件（排除current.json）
        all_files = [f for f in os.listdir(abs_directory) if f.endswith('.json') and f != 'current.json']
        valid_files = set()

        # 如果是history目录，验证文件名格式
        if 'history' in abs_directory:
            for file in all_files:
                try:
                    # 尝试解析文件名，验证是否符合YYYYMMDD_HHMMSS.json格式
                    file_name = file.split('.')[0]
                    datetime.strptime(file_name, '%Y%m%d_%H%M%S')
                    valid_files.add(file)
                except ValueError:
                    # 文件名格式不符合要求，跳过并记录日志
                    self.logger.warning(f"跳过不符合命名规范的文件: {file}")
            return valid_files
        else:
            # 非history目录，返回所有json文件
            return set(all_files)

    def _monitor_files(self):
        """监控文件变化的主循环"""
        # 初始化文件状态
        self.last_result_files = self._get_files_info(self.result_dir)
        self.last_history_files = self._get_files_info(self.history_dir)

        while self.running:
            try:
                # 检查result目录
                current_result_files = self._get_files_info(self.result_dir)
                if current_result_files != self.last_result_files:
                    self.logger.info(f"检测到result目录文件变化: {current_result_files - self.last_result_files}")
                    self.socketio.emit('files_changed', {'type': 'result'})
                    self.last_result_files = current_result_files

                # 检查history目录
                current_history_files = self._get_files_info(self.history_dir)
                if current_history_files != self.last_history_files:
                    self.logger.info(f"检测到history目录文件变化: {current_history_files - self.last_history_files}")
                    self.socketio.emit('files_changed', {'type': 'history'})
                    self.last_history_files = current_history_files

            except Exception as e:
                self.logger.error(f"监控文件时出错: {str(e)}")

            # 休眠指定的时间间隔
            time.sleep(self.check_interval)