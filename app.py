from flask import Flask, render_template, jsonify
import json
import os
import re
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    try:
        # 动态查找result目录下的最新JSON文件
        json_files = [f for f in os.listdir('result') if f.endswith('.json') and re.match(r'\d{8}_\d{6}\.json', f)]
        
        if not json_files:
            return jsonify({'error': '没有找到符合格式的JSON文件'}), 404
            
        # 按文件名排序（新格式的文件名包含时间信息）
        latest_file = sorted(json_files)[-1]
        file_path = os.path.join('result', latest_file)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history_data():
    try:
        # 获取所有历史JSON文件
        history_files = []
        
        # 检查result目录下的文件
        for file in os.listdir('result'):
            if file.endswith('.json') and re.match(r'\d{8}_\d{6}\.json', file):
                history_files.append(os.path.join('result', file))
        
        # 检查history子目录下的文件
        history_dir = os.path.join('result', 'history')
        if os.path.exists(history_dir):
            for file in os.listdir(history_dir):
                if file.endswith('.json') and re.match(r'\d{8}_\d{6}\.json', file):
                    history_files.append(os.path.join(history_dir, file))
        
        # 解析文件名中的时间并排序
        def extract_datetime(file_path):
            filename = os.path.basename(file_path)
            # 匹配新格式 (20250308_163837)
            match = re.match(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', filename)
            if match:
                year, month, day, hour, minute, second = match.groups()
                return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
            
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
                    # 匹配新格式 (20250308_163837)
                    date_str = re.match(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', filename)
                    if date_str:
                        year, month, day, hour, minute, second = date_str.groups()
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
    app.run(debug=True)