#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
博客用户数据库管理工具
功能：列出用户、创建用户、删除用户、修改密码
"""

import sqlite3
import sys
import getpass
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

def get_db_connection():
    """连接到SQLite数据库"""
    try:
        conn = sqlite3.connect('blog.db')
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"数据库连接错误: {e}")
        sys.exit(1)

def list_users():
    """列出所有用户"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, email, created_at FROM users ORDER BY id')
        users = cursor.fetchall()
        
        if not users:
            print("当前没有用户。")
            return
        
        print("\n=== 用户列表 ===")
        print(f"{'ID':<5} {'用户名':<20} {'邮箱':<30} {'创建时间':<20}")
        print("-" * 80)
        
        for user in users:
            print(f"{user['id']:<5} {user['username']:<20} {user['email']:<30} {user['created_at']:<20}")
            
        print("-" * 80)
        print(f"总计: {len(users)} 个用户\n")
        
    except sqlite3.Error as e:
        print(f"查询用户列表出错: {e}")
    finally:
        conn.close()

def create_user():
    """创建新用户"""
    username = input("请输入用户名: ").strip()
    if not username:
        print("用户名不能为空！")
        return
    
    email = input("请输入邮箱: ").strip()
    if not email:
        print("邮箱不能为空！")
        return
    
    # 验证邮箱格式（简单验证）
    if '@' not in email or '.' not in email.split('@')[1]:
        print("邮箱格式不正确！")
        return
    
    # 检查用户名和邮箱是否已存在
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            print("用户名已存在！")
            return
        
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            print("邮箱已被注册！")
            return
        
        # 获取密码（不显示输入）
        password = getpass.getpass("请输入密码: ")
        if not password:
            print("密码不能为空！")
            return
        
        confirm_password = getpass.getpass("请确认密码: ")
        if password != confirm_password:
            print("两次输入的密码不一致！")
            return
        
        # 创建用户
        password_hash = generate_password_hash(password)
        cursor.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        conn.commit()
        print(f"\n用户 '{username}' 创建成功！\n")
        
    except sqlite3.Error as e:
        print(f"创建用户出错: {e}")
        conn.rollback()
    finally:
        conn.close()

def delete_user():
    """删除用户"""
    list_users()  # 显示用户列表
    
    try:
        user_id = int(input("请输入要删除的用户ID: ").strip())
    except ValueError:
        print("无效的用户ID！")
        return
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 检查用户是否存在
        cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            print("用户不存在！")
            return
        
        username = user['username']
        # 确认删除
        confirm = input(f"确定要删除用户 '{username}' 吗？(y/n): ").lower()
        if confirm != 'y':
            print("已取消删除操作。")
            return
        
        # 开始事务
        conn.execute('BEGIN TRANSACTION')
        
        # 删除相关的文章（如果需要保留文章可以注释掉这行）
        cursor.execute('UPDATE posts SET author_id = NULL WHERE author_id = ?', (user_id,))
        
        # 删除用户
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        
        conn.commit()
        print(f"\n用户 '{username}' 已成功删除！\n")
        
    except sqlite3.Error as e:
        print(f"删除用户出错: {e}")
        conn.rollback()
    finally:
        conn.close()

def change_password():
    """修改用户密码"""
    list_users()  # 显示用户列表
    
    try:
        user_id = int(input("请输入要修改密码的用户ID: ").strip())
    except ValueError:
        print("无效的用户ID！")
        return
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 获取用户信息
        cursor.execute('SELECT username, password_hash FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            print("用户不存在！")
            return
        
        username = user['username']
        current_password_hash = user['password_hash']
        
        # 输入原密码进行验证
        old_password = getpass.getpass(f"请输入用户 '{username}' 的原密码: ")
        if not check_password_hash(current_password_hash, old_password):
            print("原密码错误！")
            return
        
        # 输入新密码
        new_password = getpass.getpass("请输入新密码: ")
        if not new_password:
            print("新密码不能为空！")
            return
        
        confirm_password = getpass.getpass("请确认新密码: ")
        if new_password != confirm_password:
            print("两次输入的新密码不一致！")
            return
        
        # 更新密码
        new_password_hash = generate_password_hash(new_password)
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                     (new_password_hash, user_id))
        conn.commit()
        
        print(f"\n用户 '{username}' 的密码已成功修改！\n")
        
    except sqlite3.Error as e:
        print(f"修改密码出错: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    """主函数"""
    print("=== 博客用户数据库管理工具 ===")
    print("(请确保blog.db数据库文件存在)")
    
    while True:
        print("\n请选择操作:")
        print("1. 列出所有用户")
        print("2. 创建新用户")
        print("3. 删除用户")
        print("4. 修改用户密码")
        print("0. 退出")
        
        choice = input("请输入选择 (0-4): ").strip()
        
        if choice == '1':
            list_users()
        elif choice == '2':
            create_user()
        elif choice == '3':
            delete_user()
        elif choice == '4':
            change_password()
        elif choice == '0':
            print("\n感谢使用，再见！")
            break
        else:
            print("无效的选择，请重新输入！")

# 自定义UTC到北京时间转换函数
def utc_to_beijing(utc_time):
    if isinstance(utc_time, str):
        formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%SZ']
        parsed_time = None
        for fmt in formats:
            try:
                parsed_time = datetime.strptime(utc_time, fmt)
                break
            except ValueError:
                continue
        if parsed_time is None:
            return utc_time
        utc_dt = parsed_time
    elif isinstance(utc_time, datetime):
        utc_dt = utc_time
    else:
        return utc_time
    
    # 添加8小时转换为北京时间
    return utc_dt + timedelta(hours=8)

# 格式化时间显示
def format_time(time_str):
    beijing_time = utc_to_beijing(time_str)
    if isinstance(beijing_time, datetime):
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
    return time_str

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序已中断。")
        sys.exit(0)
    except Exception as e:
        print(f"程序发生未预期的错误: {e}")
        sys.exit(1)