from flask import Flask
import os
from routes import *
from utils import *

app.config['SECRET_KEY'] = 'your-secret-key-here'

if __name__ == '__main__':
    # 确保templates和static文件夹存在
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/blogs', exist_ok=True)
    # 初始化数据库（仅用于用户认证）
    init_db()
    app.run(debug=True, host="0.0.0.0", port=80)