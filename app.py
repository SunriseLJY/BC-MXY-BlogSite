from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from datetime import datetime, timedelta
from markdown_it import MarkdownIt
import os
import re
# 在文件顶部添加一个自定义函数来指定哈希算法
from werkzeug.security import generate_password_hash as werkzeug_generate_password_hash, check_password_hash

# 添加自定义密码哈希函数，明确指定使用pbkdf2:sha256算法
def generate_password_hash(password):
    """
    生成密码哈希，使用更通用的pbkdf2:sha256算法
    避免scrypt算法在某些环境下不被支持的问题
    """
    return werkzeug_generate_password_hash(password, method='pbkdf2:sha256')

import logging

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

# 在文件顶部添加以下导入
import os
import sys

# 修改为使用绝对路径
if getattr(sys, 'frozen', False):
    # 当应用被打包时
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    # 正常开发环境
    app = Flask(__name__)

app.config['SECRET_KEY'] = 'your-secret-key-here'

# 初始化Markdown解析器
md = MarkdownIt()

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

# 获取当前时间 - 修改为直接使用now()
def get_current_beijing_time():
    """获取当前的本地时间
    
    Returns:
        当前时间的datetime对象
    """
    # 直接使用本地时间
    return datetime.now()

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
    
    # 检查posts表是否存在，如果不存在则创建（带author_id字段）
    conn.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            author_id INTEGER,
            FOREIGN KEY (author_id) REFERENCES users (id)
        )
    ''')
    
    # 创建tags表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # 创建post_tags关联表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS post_tags (
            post_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (post_id, tag_id),
            FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
        )
    ''')
    
    # 尝试为现有posts表添加author_id列（如果不存在）
    try:
        conn.execute('ALTER TABLE posts ADD COLUMN author_id INTEGER REFERENCES users (id)')
        conn.commit()
    except sqlite3.OperationalError:
        # 如果列已存在，忽略错误
        pass
    
    conn.close()

# 首页路由，显示所有博客文章，添加分页功能
@app.route('/')
def index():
    conn = get_db_connection()
    
    # 获取搜索关键词和标签
    search_query = request.args.get('search', '')
    tag_filter = request.args.get('tag', '')
    
    # 获取页码，默认为第1页
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示10篇文章
    offset = (page - 1) * per_page
    
    # 获取所有标签（用于显示标签云）
    tags = conn.execute('SELECT id, name FROM tags').fetchall()
    all_tags = [dict(tag) for tag in tags]
    
    # 构建查询，添加分页参数
    if search_query and tag_filter:
        # 同时有搜索关键词和标签筛选
        posts = conn.execute('''
            SELECT DISTINCT p.*, u.username 
            FROM posts p 
            LEFT JOIN users u ON p.author_id = u.id
            JOIN post_tags pt ON p.id = pt.post_id
            JOIN tags t ON pt.tag_id = t.id
            WHERE (p.title LIKE ? OR p.content LIKE ?) AND t.name = ?
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
        ''', (f'%{search_query}%', f'%{search_query}%', tag_filter, per_page, offset)).fetchall()
        
        # 获取总记录数
        total = conn.execute('''
            SELECT COUNT(DISTINCT p.id) 
            FROM posts p 
            LEFT JOIN users u ON p.author_id = u.id
            JOIN post_tags pt ON p.id = pt.post_id
            JOIN tags t ON pt.tag_id = t.id
            WHERE (p.title LIKE ? OR p.content LIKE ?) AND t.name = ?
        ''', (f'%{search_query}%', f'%{search_query}%', tag_filter)).fetchone()[0]
    elif search_query:
        # 只有搜索关键词
        posts = conn.execute('''
            SELECT p.*, u.username 
            FROM posts p 
            LEFT JOIN users u ON p.author_id = u.id 
            WHERE p.title LIKE ? OR p.content LIKE ?
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
        ''', (f'%{search_query}%', f'%{search_query}%', per_page, offset)).fetchall()
        
        total = conn.execute('''
            SELECT COUNT(*) 
            FROM posts p 
            LEFT JOIN users u ON p.author_id = u.id 
            WHERE p.title LIKE ? OR p.content LIKE ?
        ''', (f'%{search_query}%', f'%{search_query}%')).fetchone()[0]
    elif tag_filter:
        # 只有标签筛选
        posts = conn.execute('''
            SELECT DISTINCT p.*, u.username 
            FROM posts p 
            LEFT JOIN users u ON p.author_id = u.id
            JOIN post_tags pt ON p.id = pt.post_id
            JOIN tags t ON pt.tag_id = t.id
            WHERE t.name = ?
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
        ''', (tag_filter, per_page, offset)).fetchall()
        
        total = conn.execute('''
            SELECT COUNT(DISTINCT p.id) 
            FROM posts p 
            JOIN post_tags pt ON p.id = pt.post_id
            JOIN tags t ON pt.tag_id = t.id
            WHERE t.name = ?
        ''', (tag_filter,)).fetchone()[0]
    else:
        # 没有搜索条件
        posts = conn.execute('''
            SELECT p.*, u.username 
            FROM posts p 
            LEFT JOIN users u ON p.author_id = u.id 
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
        ''', (per_page, offset)).fetchall()
        
        total = conn.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
    
    # 为每个文章获取标签
    posts_with_tags = []
    for post in posts:
        post_dict = dict(post)
        post_dict['content_html'] = md.render(post['content'])
        post_dict['created_at'] = format_time(post['created_at'])
        if 'author_id' not in post_dict:
            post_dict['author_id'] = None
        if 'username' not in post_dict:
            post_dict['username'] = '未知用户'
        
        # 获取文章标签
        post_tags = conn.execute('''
            SELECT t.id, t.name FROM tags t
            JOIN post_tags pt ON t.id = pt.tag_id
            WHERE pt.post_id = ?
        ''', (post_dict['id'],)).fetchall()
        post_dict['tags'] = [dict(tag) for tag in post_tags]
        
        posts_with_tags.append(post_dict)
    
    # 计算总页数
    total_pages = (total + per_page - 1) // per_page
    
    conn.close()
    
    return render_template('index.html', 
                           posts=posts_with_tags, 
                           all_tags=all_tags,
                           search_query=search_query, 
                           selected_tag=tag_filter,
                           page=page,
                           total_pages=total_pages,
                           per_page=per_page,
                           total=total)

# 查看单个博客文章路由
@app.route('/post/<int:post_id>')
def post(post_id):
    conn = get_db_connection()
    try:
        post = conn.execute('''
            SELECT p.*, u.username 
            FROM posts p 
            LEFT JOIN users u ON p.author_id = u.id 
            WHERE p.id = ?
        ''', (post_id,)).fetchone()
    except sqlite3.OperationalError:
        # 如果author_id字段不存在，使用基本查询
        post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    
    if post is None:
        conn.close()
        flash('文章不存在')
        return redirect(url_for('index'))
    
    # 渲染Markdown内容为HTML
    post_dict = dict(post)
    post_dict['content_html'] = md.render(post['content'])
    # 转换创建时间到北京时间
    post_dict['created_at'] = format_time(post['created_at'])
    # 确保字典中包含author_id和username键
    if 'author_id' not in post_dict:
        post_dict['author_id'] = None
    if 'username' not in post_dict:
        post_dict['username'] = '未知用户'
    # 检查当前用户是否为文章作者
    post_dict['is_author'] = 'user_id' in session and session['user_id'] == post_dict.get('author_id')
    
    # 获取文章标签
    post_tags = conn.execute('''
        SELECT t.id, t.name FROM tags t
        JOIN post_tags pt ON t.id = pt.tag_id
        WHERE pt.post_id = ?
    ''', (post_id,)).fetchall()
    post_dict['tags'] = [dict(tag) for tag in post_tags]
    
    conn.close()
    return render_template('post.html', post=post_dict)

# 用户认证装饰器
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 用户注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if not username or not email or not password:
            flash('所有字段都必须填写')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('两次输入的密码不一致')
            return redirect(url_for('register'))
        
        conn = get_db_connection()
        # 检查用户名是否已存在
        existing_user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if existing_user:
            conn.close()
            flash('用户名已存在')
            return redirect(url_for('register'))
        
        # 检查邮箱是否已存在
        existing_email = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if existing_email:
            conn.close()
            flash('邮箱已被注册')
            return redirect(url_for('register'))
        
        # 创建新用户并添加日志
        password_hash = generate_password_hash(password)
        conn.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)', 
                    (username, email, password_hash))
        new_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        logger.info(f'新用户注册成功：{username} (ID: {new_user["id"]}, 邮箱: {email})')
        conn.commit()
        conn.close()
        
        flash('注册成功，请登录')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# 用户登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            # 登录成功，设置session并添加日志
            session['user_id'] = user['id']
            session['username'] = user['username']
            logger.info(f'用户 {username} (ID: {user["id"]}) 成功登录')
            flash('登录成功')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误')
            return redirect(url_for('login'))
    
    return render_template('login.html')

# 用户注销路由
@app.route('/logout')
def logout():
    # 记录登出信息并清理session
    if 'username' in session:
        logger.info(f'用户 {session["username"]} (ID: {session.get("user_id")}) 已注销')
    session.clear()
    flash('已成功注销')
    return redirect(url_for('index'))

# 创建新博客文章路由
@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    conn = get_db_connection()
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tags_input = request.form.get('tags', '')
        
        if not title:
            flash('标题不能为空')
            conn.close()
            return redirect(url_for('create'))
        
        # 使用当前北京时间
        current_time = get_current_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
        
        # 开始事务
        conn.execute('BEGIN TRANSACTION')
        try:
            # 插入文章
            cursor = conn.execute('INSERT INTO posts (title, content, created_at, author_id) VALUES (?, ?, ?, ?)', 
                               (title, content, current_time, session['user_id']))
            post_id = cursor.lastrowid
            
            # 处理标签
            if tags_input:
                # 分割标签（支持逗号、空格或换行分割）
                tag_names = [tag.strip() for tag in re.split(r'[\s,]+', tags_input) if tag.strip()]
                
                for tag_name in tag_names:
                    # 查找或创建标签
                    tag = conn.execute('SELECT id FROM tags WHERE name = ?', (tag_name,)).fetchone()
                    if not tag:
                        # 创建新标签
                        cursor = conn.execute('INSERT INTO tags (name) VALUES (?)', (tag_name,))
                        tag_id = cursor.lastrowid
                    else:
                        tag_id = tag['id']
                    
                    # 建立文章和标签的关联
                    conn.execute('INSERT INTO post_tags (post_id, tag_id) VALUES (?, ?)', (post_id, tag_id))
            
            # 在成功提交事务后添加日志
            conn.commit()
            logger.info(f'用户 {session["user_id"]} 创建了新文章 {post_id}，标题：{title}')
            flash('文章创建成功')
            
        except Exception as e:
            conn.rollback()
            flash('文章创建失败: ' + str(e))
        finally:
            conn.close()
        
        return redirect(url_for('index'))
    
    conn.close()
    return render_template('create.html')

# 编辑博客文章路由
@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    
    if post is None:
        conn.close()
        flash('文章不存在')
        return redirect(url_for('index'))
    
    # 检查是否为文章作者
    if post['author_id'] != session['user_id']:
        conn.close()
        flash('无权编辑此文章')
        return redirect(url_for('post', post_id=post_id))
    
    # 获取当前文章的标签
    post_tags = conn.execute('''
        SELECT t.name FROM tags t
        JOIN post_tags pt ON t.id = pt.tag_id
        WHERE pt.post_id = ?
    ''', (post_id,)).fetchall()
    existing_tags = ', '.join([tag['name'] for tag in post_tags])
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tags_input = request.form.get('tags', '')
        
        if not title:
            flash('标题不能为空')
            conn.close()
            return redirect(url_for('edit', post_id=post_id))
        
        # 开始事务
        conn.execute('BEGIN TRANSACTION')
        try:
            # 更新文章
            conn.execute('UPDATE posts SET title = ?, content = ? WHERE id = ?', (title, content, post_id))
            logger.info(f'用户 {session["user_id"]} 更新了文章 {post_id}，新标题：{title}')
            
            # 删除旧的标签关联
            conn.execute('DELETE FROM post_tags WHERE post_id = ?', (post_id,))
            
            # 处理新标签
            if tags_input:
                # 分割标签（支持逗号、空格或换行分割）
                tag_names = [tag.strip() for tag in re.split(r'[\s,]+', tags_input) if tag.strip()]
                
                for tag_name in tag_names:
                    # 查找或创建标签
                    tag = conn.execute('SELECT id FROM tags WHERE name = ?', (tag_name,)).fetchone()
                    if not tag:
                        # 创建新标签
                        cursor = conn.execute('INSERT INTO tags (name) VALUES (?)', (tag_name,))
                        tag_id = cursor.lastrowid
                    else:
                        tag_id = tag['id']
                    
                    # 建立文章和标签的关联
                    conn.execute('INSERT INTO post_tags (post_id, tag_id) VALUES (?, ?)', (post_id, tag_id))
            
            conn.commit()
            flash('文章更新成功')
        except Exception as e:
            conn.rollback()
            flash('文章更新失败: ' + str(e))
        finally:
            conn.close()
        
        return redirect(url_for('post', post_id=post_id))
    
    # 将文章转换为字典并添加标签信息
    post_dict = dict(post)
    post_dict['existing_tags'] = existing_tags
    
    conn.close()
    return render_template('edit.html', post=post_dict)

# 删除博客文章路由
@app.route('/delete/<int:post_id>', methods=['POST'])
@login_required
def delete(post_id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    
    if post is None:
        conn.close()
        flash('文章不存在')
        return redirect(url_for('index'))
    
    # 检查是否为文章作者
    if post['author_id'] != session['user_id']:
        conn.close()
        flash('无权删除此文章')
        return redirect(url_for('post', post_id=post_id))
    
    try:
        # 在成功提交删除后添加日志
        conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        logger.info(f'用户 {session["user_id"]} 删除了文章 {post_id}，标题：{post["title"]}')
        conn.commit()
        flash('文章已删除')
    except Exception as e:
        conn.rollback()
        flash('文章删除失败: ' + str(e))
    finally:
        conn.close()
    
    return redirect(url_for('index'))

# 添加在上下文处理器之前
@app.template_filter('first_five_lines')
def first_five_lines(html_content):
    # 按换行符分割内容，取前5行
    lines = html_content.split('\n')
    first_five = '\n'.join(lines[:5])
    # 如果内容超过5行，添加省略号
    if len(lines) > 5:
        first_five += '\n<p>...</p>'
    return first_five

# 添加上下文处理器，使datetime在所有模板中可用
@app.context_processor
def inject_datetime():
    return {
        'datetime': datetime,
        'session': session,
        'utc_to_beijing': utc_to_beijing,
        'format_time': format_time
    }

# 关于页面路由
@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    # 确保templates和static文件夹存在
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    # 初始化数据库
    init_db()
    app.run(debug=True, port=80)