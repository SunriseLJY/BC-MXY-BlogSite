# Flask Markdown 博客系统

一个基于Flask框架开发的简易博客系统，支持Markdown内容编辑、用户认证、标签管理和分页浏览等功能。

## 🚀 项目特点

- **Markdown支持**：文章内容使用Markdown格式编写，自动渲染为HTML显示
- **用户认证系统**：注册、登录、注销功能，支持密码安全存储
- **文章管理**：创建、编辑、删除博客文章
- **标签系统**：支持为文章添加多个标签，便于分类和搜索
- **搜索功能**：支持按标题和内容搜索文章
- **分页浏览**：首页文章列表支持分页，每页显示10篇文章
- **响应式设计**：基本的响应式布局，适配不同设备
- **UTF-8编码支持**：日志文件使用UTF-8编码，确保中文显示正常
- **可打包为EXE**：支持使用PyInstaller打包为Windows可执行文件

## 🛠 技术栈

- **后端框架**：Flask 2.x
- **数据库**：SQLite3
- **Markdown解析**：markdown-it-py
- **密码加密**：Werkzeug Security
- **前端技术**：HTML5, CSS3, JavaScript
- **模板引擎**：Jinja2

## 📋 安装与部署

### 方法一：直接运行Python脚本

#### 1. 环境要求

- Python 3.8+
- pip包管理器

#### 2. 安装依赖

```bash
pip install flask markdown-it-py werkzeug
```

#### 3. 运行应用

```bash
python app.py
```

应用将在 http://localhost:5000 启动

### 方法二：使用打包的EXE文件

#### 1. 打包应用（可选）

如果需要自行打包：

```bash
pip install pyinstaller
pyinstaller blog.spec
```

或者使用单行命令：

```bash
pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" --hidden-import=markdown-it-py --hidden-import=flask app.py
```

#### 2. 运行打包后的应用

在`dist`目录下找到`blog.exe`，双击运行即可。首次运行会自动创建必要的数据库文件和表结构。

## 📖 使用指南

### 用户注册与登录

1. 访问 `/register` 页面注册新账号
2. 注册成功后自动跳转到登录页面
3. 登录后可以创建和管理自己的博客文章

### 文章管理

#### 创建文章
1. 登录后点击导航栏中的"写文章"
2. 填写标题、内容（Markdown格式）和标签
3. 点击"发布"按钮保存

#### 编辑文章
1. 访问自己发布的文章详情页
2. 点击"编辑"按钮修改内容
3. 点击"更新"按钮保存修改

#### 删除文章
1. 访问自己发布的文章详情页
2. 点击"删除"按钮并确认

### 文章搜索与标签筛选

- 使用首页顶部的搜索框按关键词搜索
- 点击标签云中的标签筛选相关文章
- 分页浏览支持搜索和筛选条件的保持

## ⚠️ 注意事项

1. **数据库存储**：使用SQLite数据库，数据保存在`blog.db`文件中
2. **日志记录**：应用操作日志保存在`blog.log`文件中，使用UTF-8编码
3. **密码安全**：使用`pbkdf2:sha256`算法进行密码哈希，确保安全性
4. **端口占用**：默认使用5000端口，确保该端口未被占用
5. **权限管理**：用户只能编辑和删除自己发布的文章

## 📝 项目结构

BC-MXY BlogSite Python Test/
├── app.py # 主应用程序文件 
├── blog.db # SQLite数据库文件 
├── blog.log # 日志文件 
├── static/ # 静态资源文件夹 
│ └── css/ # CSS样式文件 
├── templates/ # 模板文件 
│ ├── base.html # 基础模板 
│ ├── index.html # 首页 
│ ├── post.html # 文章详情页 
│ ├── create.html # 创建文章页
│ ├── edit.html # 编辑文章页 
│ ├── login.html # 登录页 
│ ├── register.html # 注册页
| |── about.html # 关于页面 

## 🔧 常见问题

### 无法登录或密码错误

如果遇到哈希算法不支持的错误（如`unsupported hash type scrypt`），请使用以下步骤重置密码：

1. 停止应用
2. 运行下方脚本
3. 使用临时密码登录后修改为新密码

```python
# migrate_passwords.py
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('blog.db')
cursor = conn.cursor()
cursor.execute('SELECT id, username FROM users')
users = cursor.fetchall()

for user in users:
    user_id, username = user
    temp_password = f'Password123!'
    new_hash = generate_password_hash(temp_password, method='pbkdf2:sha256')
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
    print(f'用户 {username} 的密码已重置为: {temp_password}')

conn.commit()
conn.close()
```

### 端口被占用

修改app.py文件中的端口配置：

```python
app.run(debug=True, port=8000)  # 将5000改为其他可用端口
```

## 🤝 贡献

欢迎提出问题和建议，帮助改进这个项目！
