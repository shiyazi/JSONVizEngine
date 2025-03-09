from flask import Flask, render_template, jsonify
import json
import os
from datetime import datetime
from flask_socketio import SocketIO
from file_monitor import FileMonitor
from logger import setup_logger, shutdown_logger

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化文件监控器和日志系统
file_monitor = None
logger = None

def load_json_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_current_result_file():
    # 获取应用根目录的绝对路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    result_dir = os.path.join(base_dir, 'result')
    # 确保目录存在
    if not os.path.exists(result_dir):
        os.makedirs(result_dir, exist_ok=True)
    result_files = [f for f in os.listdir(result_dir) if f.endswith('.json') and f != 'current.json']
    if not result_files:
        return None
    # 按文件名排序（文件名是时间戳格式），取最新的一个
    result_files.sort()
    return result_files[-1]

def get_history_data():
    # 获取应用根目录的绝对路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    history_dir = os.path.join(base_dir, 'result', 'history')
    # 确保目录存在
    if not os.path.exists(history_dir):
        os.makedirs(history_dir, exist_ok=True)
    history_files = [f for f in os.listdir(history_dir) if f.endswith('.json')]
    history_files.sort()
    
    history_data = []
    for file in history_files:
        try:
            file_path = os.path.join(history_dir, file)
            data = load_json_data(file_path)
            date_str = file.split('.')[0]  # 20250308_022824
            date_obj = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
            
            total = len(data.get('scene_result', []))
            success = sum(1 for scene in data.get('scene_result', []) if scene.get('is_success') == 1)
            skipped = sum(1 for scene in data.get('scene_result', []) if scene.get('is_success') == 2)
            failed = total - success - skipped
            
            history_data.append({
                'date': date_obj.strftime('%Y-%m-%d %H:%M:%S'),
                'total': total,
                'success': success,
                'failed': failed,
                'skipped': skipped,
                'pass_rate': (success / total * 100) if total > 0 else 0
            })
        except (ValueError, json.JSONDecodeError) as e:
            # 跳过不符合命名规范的文件或JSON格式错误的文件
            logger.warning(f"跳过处理文件 {file}: {str(e)}")
            continue
    
    # 添加当前数据到历史数据中
    current_file = get_current_result_file()
    if not current_file:
        return history_data
    base_dir = os.path.dirname(os.path.abspath(__file__))
    current_data = load_json_data(os.path.join(base_dir, 'result', current_file))
    current_date_str = current_file.split('.')[0]
    current_date_obj = datetime.strptime(current_date_str, '%Y%m%d_%H%M%S')
    
    total = len(current_data.get('scene_result', []))
    success = sum(1 for scene in current_data.get('scene_result', []) if scene.get('is_success') == 1)
    skipped = sum(1 for scene in current_data.get('scene_result', []) if scene.get('is_success') == 2)
    failed = total - success - skipped
    
    history_data.append({
        'date': current_date_obj.strftime('%Y-%m-%d %H:%M:%S'),
        'total': total,
        'success': success,
        'failed': failed,
        'skipped': skipped,
        'pass_rate': (success / total * 100) if total > 0 else 0
    })
    
    return history_data

def get_step_failures(data):
    step_failures = {}
    
    # 递归函数，用于遍历所有层级的场景和步骤
    def process_steps(steps):
        for step in steps:
            # 处理当前步骤
            step_name = step.get('step_name', 'Unknown Step')
            if step.get('is_success') == 0:
                step_failures[step_name] = step_failures.get(step_name, 0) + 1
            
            # 如果是嵌套场景，递归处理其中的步骤
            if 'scene_result' in step and isinstance(step['scene_result'], list):
                process_steps(step['scene_result'])
    
    # 处理顶层场景
    for scene in data.get('scene_result', []):
        # 处理场景本身的步骤
        process_steps(scene.get('scene_result', []))
    
    return sorted([
        {'step': k, 'failures': v} 
        for k, v in step_failures.items()], 
        key=lambda x: x['failures'], 
        reverse=True
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    current_file = get_current_result_file()
    if not current_file:
        return jsonify({'error': 'No result file found'}), 404
    base_dir = os.path.dirname(os.path.abspath(__file__))
    current_data = load_json_data(os.path.join(base_dir, 'result', current_file))
    history_data = get_history_data()
    
    total_cases = len(current_data.get('scene_result', []))
    success_cases = sum(1 for scene in current_data.get('scene_result', []) if scene.get('is_success') == 1)
    skipped_cases = sum(1 for scene in current_data.get('scene_result', []) if scene.get('is_success') == 2)
    failed_cases = total_cases - success_cases - skipped_cases
    
    return jsonify({
        'current': {
            'total': total_cases,
            'success': success_cases,
            'failed': failed_cases,
            'skipped': skipped_cases,
            'pass_rate': (success_cases / total_cases * 100) if total_cases > 0 else 0,
            'scenes': current_data.get('scene_result', []),
            'step_failures': get_step_failures(current_data)
        },
        'history': history_data
    })

@app.route('/api/history/<date_str>')
def get_history_detail(date_str):
    # 格式化日期字符串，将横杠和空格转换为下划线
    # 例如：2025-03-08 02:28:24 -> 20250308_022824
    try:
        # 如果传入的是格式化后的日期，先转换回原始格式
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        file_name = date_obj.strftime('%Y%m%d_%H%M%S') + '.json'
    except ValueError:
        # 如果已经是原始格式，直接使用
        file_name = date_str + '.json'
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'result', 'history', file_name)
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return jsonify({'error': 'History file not found'}), 404
    
    # 加载历史数据
    history_data = load_json_data(file_path)
    
    # 计算统计信息
    total_cases = len(history_data.get('scene_result', []))
    success_cases = sum(1 for scene in history_data.get('scene_result', []) if scene.get('is_success') == 1)
    skipped_cases = sum(1 for scene in history_data.get('scene_result', []) if scene.get('is_success') == 2)
    failed_cases = total_cases - success_cases - skipped_cases
    
    return jsonify({
        'total': total_cases,
        'success': success_cases,
        'failed': failed_cases,
        'skipped': skipped_cases,
        'pass_rate': (success_cases / total_cases * 100) if total_cases > 0 else 0,
        'scenes': history_data.get('scene_result', []),
        'step_failures': get_step_failures(history_data)
    })

if __name__ == '__main__':
    # 初始化日志系统
    logger = setup_logger()
    logger.info("应用启动中...")
    
    # 启动文件监控
    file_monitor = FileMonitor(socketio)
    file_monitor.start()
    
    try:
        # 使用socketio启动应用
        logger.info("Web服务器启动中...")
        socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"应用运行出错: {str(e)}")
    finally:
        # 关闭日志系统
        if file_monitor:
            file_monitor.stop()
        shutdown_logger()
        logger.info("应用已关闭")