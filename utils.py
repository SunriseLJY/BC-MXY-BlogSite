import sqlite3
import logging
import json
import os
import sys
from datetime import datetime, timedelta
from markdown_it import MarkdownIt
from werkzeug.security import generate_password_hash as werkzeug_generate_password_hash, check_password_hash

# 初始化Markdown解析器
md = MarkdownIt()

# 博客文件存储路径
if getattr(sys, 'frozen', False):
    # 当应用被打包时，使用当前工作目录作为存储路径
    BLOG_STORAGE_PATH = os.path.join(os.getcwd(), 'static', 'blogs')
else:
    # 正常开发环境
    BLOG_STORAGE_PATH = 'static/blogs'

# 确保博客存储目录存在
os.makedirs(BLOG_STORAGE_PATH, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("blog.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 添加自定义密码哈希函数，明确指定使用pbkdf2:sha256算法
def generate_password_hash(password):
    """
    生成密码哈希，使用更通用的pbkdf2:sha256算法
    避免scrypt算法在某些环境下不被支持的问题
    """
    return werkzeug_generate_password_hash(password, method='pbkdf2:sha256')

# 自定义UTC到北京时间转换函数（GMT+8） - 修改为直接返回时间
def utc_to_beijing(utc_time):
    """简化的时间处理函数
    
    Args:
        utc_time: 时间，可以是字符串或datetime对象
        
    Returns:
        处理后的时间对象
    """
    # 如果输入是字符串，尝试解析为datetime对象
    if isinstance(utc_time, str):
        # 尝试不同的时间格式解析
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d'
        ]
        
        parsed_time = None
        for fmt in formats:
            try:
                parsed_time = datetime.strptime(utc_time, fmt)
                break
            except ValueError:
                continue
        
        if parsed_time is None:
            # 如果无法解析，返回原始输入
            return utc_time
        
        return parsed_time
    elif isinstance(utc_time, datetime):
        # 直接返回datetime对象，不再加8小时
        return utc_time
    else:
        # 如果输入既不是字符串也不是datetime对象，直接返回
        return utc_time

# 格式化时间显示
def format_time(time_obj):
    """格式化时间对象为可读字符串
    
    Args:
        time_obj: 时间对象，可以是字符串、datetime或其他
        
    Returns:
        格式化后的时间字符串
    """
    # 转换为北京时间
    beijing_time = utc_to_beijing(time_obj)
    
    # 如果转换后的结果仍然不是datetime对象，返回原始值
    if not isinstance(beijing_time, datetime):
        return beijing_time
    
    # 格式化为字符串
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')

# 获取当前北京时间
def get_current_beijing_time():
    """获取当前的北京时间
    
    Returns:
        当前北京时间的datetime对象
    """
    # 获取当前UTC时间并添加8小时
    return datetime.utcnow() + timedelta(hours=8)

# 连接数据库的辅助函数
def get_db_connection():
    conn = sqlite3.connect('blog.db')
    conn.row_factory = sqlite3.Row
    return conn

# 从文件系统加载博客文章
def load_blog_from_file(post_id):
    """从文件系统加载博客文章
    
    Args:
        post_id: 博客文章ID
        
    Returns:
        博客文章字典，如果不存在返回None
    """
    json_path = os.path.join(BLOG_STORAGE_PATH, f'{post_id}.json')
    md_path = os.path.join(BLOG_STORAGE_PATH, f'{post_id}.md')
    
    if not os.path.exists(json_path) or not os.path.exists(md_path):
        return None
    
    # 读取JSON元数据
    with open(json_path, 'r', encoding='utf-8') as f:
        post_data = json.load(f)
    
    # 读取Markdown内容
    with open(md_path, 'r', encoding='utf-8') as f:
        post_data['content'] = f.read()
    
    return post_data

# 保存博客文章到文件系统
def save_blog_to_file(post_data):
    """保存博客文章到文件系统
    
    Args:
        post_data: 博客文章字典
        
    Returns:
        保存后的博客文章ID
    """
    # 生成或使用现有ID
    if 'id' not in post_data:
        # 生成新ID
        existing_files = os.listdir(BLOG_STORAGE_PATH)
        post_ids = []
        for file in existing_files:
            if file.endswith('.json'):
                try:
                    post_ids.append(int(file.split('.')[0]))
                except:
                    pass
        post_id = max(post_ids) + 1 if post_ids else 1
        post_data['id'] = post_id
    else:
        post_id = post_data['id']
    
    # 确保创建时间存在
    if 'created_at' not in post_data:
        post_data['created_at'] = get_current_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
    
    # 分离内容和元数据
    content = post_data.pop('content', '')
    
    # 保存JSON元数据
    json_path = os.path.join(BLOG_STORAGE_PATH, f'{post_id}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)
    
    # 保存Markdown内容
    md_path = os.path.join(BLOG_STORAGE_PATH, f'{post_id}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return post_id

# 删除博客文章文件
def delete_blog_file(post_id):
    """删除博客文章文件
    
    Args:
        post_id: 博客文章ID
    """
    json_path = os.path.join(BLOG_STORAGE_PATH, f'{post_id}.json')
    md_path = os.path.join(BLOG_STORAGE_PATH, f'{post_id}.md')
    
    if os.path.exists(json_path):
        os.remove(json_path)
    if os.path.exists(md_path):
        os.remove(md_path)

# 获取所有博客文章
def get_all_blogs():
    """获取所有博客文章
    
    Returns:
        博客文章列表
    """
    blogs = []
    existing_files = os.listdir(BLOG_STORAGE_PATH)
    post_ids = []
    
    # 收集所有文章ID
    for file in existing_files:
        if file.endswith('.json'):
            try:
                post_ids.append(int(file.split('.')[0]))
            except:
                pass
    
    # 去重并排序
    post_ids = sorted(list(set(post_ids)), reverse=True)
    
    # 加载每个文章
    for post_id in post_ids:
        post = load_blog_from_file(post_id)
        if post:
            blogs.append(post)
    
    return blogs

# 初始化数据库
def init_db():
    conn = get_db_connection()
    
    # 先创建用户表，因为posts表会引用它
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.close()