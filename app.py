from flask import Flask, render_template, jsonify
import json
import os
import re
from datetime import datetime
from flask_socketio import SocketIO
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    try:
        with open('result/202503080228.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 文件监控类，用于监控result目录下的文件变动
class ResultFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = time.time()
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # 防止短时间内多次触发
        if time.time() - self.last_modified < 1:
            return
        self.last_modified = time.time()
        
        # 检查是否是JSON文件
        if event.src_path.endswith('.json'):
            print(f"检测到文件变动: {event.src_path}")
            # 通过WebSocket发送更新通知
            socketio.emit('data_updated', {'file': event.src_path, 'timestamp': time.time()})

# 启动文件监控
def start_file_monitor():
    event_handler = ResultFileHandler()
    observer = Observer()
    # 监控result目录
    observer.schedule(event_handler, 'result', recursive=True)
    observer.start()
    print("文件监控已启动，监控result目录下的文件变动")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

@app.route('/api/history')
def get_history_data():
    try:
        # 获取所有历史JSON文件
        history_files = []
        
        # 检查result目录下的文件
        for file in os.listdir('result'):
            if file.endswith('.json') and re.match(r'\d{12}\.json', file):
                history_files.append(os.path.join('result', file))
        
        # 检查history子目录下的文件
        history_dir = os.path.join('result', 'history')
        if os.path.exists(history_dir):
            for file in os.listdir(history_dir):
                if file.endswith('.json') and re.match(r'\d{12}\.json', file):
                    history_files.append(os.path.join(history_dir, file))
        
        # 解析文件名中的时间并排序
        def extract_datetime(file_path):
            filename = os.path.basename(file_path)
            match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})', filename)
            if match:
                year, month, day, hour, minute = match.groups()
                return datetime(int(year), int(month), int(day), int(hour), int(minute))
            return datetime(1970, 1, 1)  # 默认时间
        
        history_files.sort(key=extract_datetime)
        
        # 读取每个文件并统计成功/失败/跳过的场景数量
        history_data = []
        for file_path in history_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if 'scene_result' in data:
                    success_count = sum(1 for scene in data['scene_result'] if scene.get('is_success') == 1)
                    failure_count = sum(1 for scene in data['scene_result'] if scene.get('is_success') == 0)
                    skipped_count = sum(1 for scene in data['scene_result'] if scene.get('is_success') == 2)
                    
                    # 从文件名提取时间
                    filename = os.path.basename(file_path)
                    date_str = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})', filename)
                    if date_str:
                        year, month, day, hour, minute = date_str.groups()
                        date_label = f"{year}-{month}-{day} {hour}:{minute}"
                    else:
                        date_label = filename
                    
                    history_data.append({
                        'date': date_label,
                        'timestamp': extract_datetime(file_path).timestamp(),
                        'success': success_count,
                        'failure': failure_count,
                        'skipped': skipped_count,
                        'total': len(data['scene_result'])
                    })
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
        
        return jsonify(history_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 在单独的线程中启动文件监控
    monitor_thread = threading.Thread(target=start_file_monitor)
    monitor_thread.daemon = True  # 设置为守护线程，这样主程序退出时，监控线程也会退出
    monitor_thread.start()
    
    # 使用socketio启动应用
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)