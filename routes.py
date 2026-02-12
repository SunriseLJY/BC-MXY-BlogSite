from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from utils import *
import os
import sys
import re

# 修改为使用绝对路径
if getattr(sys, 'frozen', False):
    # 当应用被打包时
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    # 正常开发环境
    app = Flask(__name__)

# 首页路由，显示所有博客文章，添加分页功能
@app.route('/')
def index():
    # 获取搜索关键词和标签
    search_query = request.args.get('search', '')
    tag_filter = request.args.get('tag', '')
    
    # 获取页码，默认为第1页
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示10篇文章
    offset = (page - 1) * per_page
    
    # 获取所有博客文章
    all_posts = get_all_blogs()
    
    # 收集所有标签
    all_tags_set = set()
    for post in all_posts:
        if 'tags' in post:
            for tag in post['tags']:
                all_tags_set.add(tag['name'])
    
    # 转换为标签列表
    all_tags = []
    for i, tag_name in enumerate(all_tags_set):
        all_tags.append({'id': i + 1, 'name': tag_name})
    
    # 筛选文章
    filtered_posts = []
    for post in all_posts:
        # 检查搜索关键词
        if search_query:
            if search_query not in post.get('title', '') and search_query not in post.get('content', ''):
                continue
        
        # 检查标签筛选
        if tag_filter:
            if 'tags' not in post:
                continue
            tag_found = False
            for tag in post['tags']:
                if tag['name'] == tag_filter:
                    tag_found = True
                    break
            if not tag_found:
                continue
        
        filtered_posts.append(post)
    
    # 计算总记录数
    total = len(filtered_posts)
    
    # 分页
    posts = filtered_posts[offset:offset + per_page]
    
    # 为每个文章处理内容和标签
    posts_with_tags = []
    for post in posts:
        post_dict = post.copy()
        post_dict['content_html'] = md.render(post.get('content', ''))
        post_dict['created_at'] = format_time(post.get('created_at', ''))
        if 'author_id' not in post_dict:
            post_dict['author_id'] = None
        if 'username' not in post_dict:
            post_dict['username'] = post.get('author', '未知用户')
        
        # 确保标签格式正确
        if 'tags' not in post_dict:
            post_dict['tags'] = []
        
        posts_with_tags.append(post_dict)
    
    # 计算总页数
    total_pages = (total + per_page - 1) // per_page
    
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
    # 从文件系统加载文章
    post_data = load_blog_from_file(post_id)
    
    if post_data is None:
        flash('文章不存在')
        return redirect(url_for('index'))
    
    # 渲染Markdown内容为HTML
    post_dict = post_data.copy()
    post_dict['content_html'] = md.render(post_dict.get('content', ''))
    # 转换创建时间到北京时间
    post_dict['created_at'] = format_time(post_dict.get('created_at', ''))
    # 确保字典中包含author_id和username键
    if 'author_id' not in post_dict:
        post_dict['author_id'] = None
    if 'username' not in post_dict:
        post_dict['username'] = post_dict.get('author', '未知用户')
    # 检查当前用户是否为文章作者
    post_dict['is_author'] = 'user_id' in session and session['user_id'] == post_dict.get('author_id')
    
    # 确保标签格式正确
    if 'tags' not in post_dict:
        post_dict['tags'] = []
    
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
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tags_input = request.form.get('tags', '')
        
        if not title:
            flash('标题不能为空')
            return redirect(url_for('create'))
        
        # 使用当前北京时间
        current_time = get_current_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建文章数据
        post_data = {
            'title': title,
            'content': content,
            'created_at': current_time,
            'author_id': session['user_id'],
            'author': session['username']
        }
        
        # 处理标签
        if tags_input:
            # 分割标签（支持逗号、空格或换行分割）
            tag_names = [tag.strip() for tag in re.split(r'[\s,]+', tags_input) if tag.strip()]
            tags = []
            for i, tag_name in enumerate(tag_names):
                tags.append({'id': i + 1, 'name': tag_name})
            post_data['tags'] = tags
        
        try:
            # 保存文章到文件系统
            post_id = save_blog_to_file(post_data)
            logger.info(f'用户 {session["user_id"]} 创建了新文章 {post_id}，标题：{title}')
            flash('文章创建成功')
        except Exception as e:
            flash('文章创建失败: ' + str(e))
        
        return redirect(url_for('index'))
    
    return render_template('create.html')

# 编辑博客文章路由
@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    # 从文件系统加载文章
    post_data = load_blog_from_file(post_id)
    
    if post_data is None:
        flash('文章不存在')
        return redirect(url_for('index'))
    
    # 检查是否为文章作者
    if post_data.get('author_id') != session['user_id']:
        flash('无权编辑此文章')
        return redirect(url_for('post', post_id=post_id))
    
    # 获取当前文章的标签
    existing_tags = []
    if 'tags' in post_data:
        existing_tags = [tag['name'] for tag in post_data['tags']]
    existing_tags_str = ', '.join(existing_tags)
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tags_input = request.form.get('tags', '')
        
        if not title:
            flash('标题不能为空')
            return redirect(url_for('edit', post_id=post_id))
        
        try:
            # 更新文章数据
            post_data['title'] = title
            post_data['content'] = content
            
            # 处理新标签
            if tags_input:
                # 分割标签（支持逗号、空格或换行分割）
                tag_names = [tag.strip() for tag in re.split(r'[\s,]+', tags_input) if tag.strip()]
                tags = []
                for i, tag_name in enumerate(tag_names):
                    tags.append({'id': i + 1, 'name': tag_name})
                post_data['tags'] = tags
            else:
                post_data['tags'] = []
            
            # 保存更新后的文章
            save_blog_to_file(post_data)
            logger.info(f'用户 {session["user_id"]} 更新了文章 {post_id}，新标题：{title}')
            flash('文章更新成功')
        except Exception as e:
            flash('文章更新失败: ' + str(e))
        
        return redirect(url_for('post', post_id=post_id))
    
    # 将文章转换为字典并添加标签信息
    post_dict = post_data.copy()
    post_dict['existing_tags'] = existing_tags_str
    
    return render_template('edit.html', post=post_dict)

# 删除博客文章路由
@app.route('/delete/<int:post_id>', methods=['POST'])
@login_required
def delete(post_id):
    # 从文件系统加载文章
    post_data = load_blog_from_file(post_id)
    
    if post_data is None:
        flash('文章不存在')
        return redirect(url_for('index'))
    
    # 检查是否为文章作者
    if post_data.get('author_id') != session['user_id']:
        flash('无权删除此文章')
        return redirect(url_for('post', post_id=post_id))
    
    try:
        # 删除文章文件
        delete_blog_file(post_id)
        logger.info(f'用户 {session["user_id"]} 删除了文章 {post_id}，标题：{post_data.get("title", "")}')
        flash('文章已删除')
    except Exception as e:
        flash('文章删除失败: ' + str(e))
    
    return redirect(url_for('index'))

@app.route('/download/<int:post_id>')
def download(post_id):
    from utils import BLOG_STORAGE_PATH
    from flask import send_from_directory
    import os
    
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 构建.md文件路径
    md_filename = f'{post_id}.md'
    md_filepath = os.path.join(BLOG_STORAGE_PATH, md_filename)
    
    # 检查文件是否存在
    if os.path.exists(md_filepath):
        return send_from_directory(BLOG_STORAGE_PATH, md_filename, as_attachment=True)
    else:
        flash('文件不存在')
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