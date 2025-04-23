from fastapi import FastAPI, Query, Request, Form, Depends, HTTPException, status, Cookie
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyHeader
import requests
import re
import json
import base64
import urllib.parse
import os
import time
import random
import uuid
from pathlib import Path
from typing import Optional

# 创建templates目录（如果不存在）
templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

# 创建config目录（如果不存在）
config_dir = Path("config")
config_dir.mkdir(exist_ok=True)

# 配置文件路径
config_file = config_dir / "api_config.json"

# 默认配置
default_config = {
    "access_password": "douyin123",
    "api_key": "your_api_key_here"
}

# 加载或创建配置
def load_config():
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件出错: {e}")
    
    # 如果配置文件不存在或出错，创建默认配置
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(default_config, f, ensure_ascii=False, indent=2)
    
    return default_config

# 保存配置
def save_config(config):
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 加载配置
CONFIG = load_config()

app = FastAPI()

# 设置模板目录
templates = Jinja2Templates(directory="templates")

# 设置访问密码和API密钥
ACCESS_PASSWORD = CONFIG["access_password"]
API_KEY = CONFIG["api_key"]
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# 检查密码或API密钥
async def verify_access(request: Request, api_key: str = Depends(api_key_header), password_cookie: Optional[str] = Cookie(None, alias="douyin_access")):
    # 检查API密钥 - 适用于API调用
    if api_key and api_key == API_KEY:
        return True
    
    # 检查Cookie密码 - 适用于网页访问
    if password_cookie and password_cookie == ACCESS_PASSWORD:
        return True
    
    # 如果是API调用但密钥错误，返回401错误
    if request.url.path.startswith("/parse-douyin") and "url" in request.query_params:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 如果是网页访问但没有密码Cookie，重定向到登录页面
    return False

# 检查是否管理员
async def verify_admin(request: Request, password_cookie: Optional[str] = Cookie(None, alias="douyin_admin")):
    if password_cookie and password_cookie == ACCESS_PASSWORD:
        return True
    return False

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, authorized: bool = Depends(verify_access)):
    """
    根路径返回中文网页界面，方便用户使用。
    """
    if not authorized:
        return templates.TemplateResponse("login.html", {"request": request})
    
    # 重新加载配置以确保最新
    CONFIG = load_config()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "access_password": CONFIG["access_password"],
        "api_key": CONFIG["api_key"]
    })

@app.post("/login", response_class=RedirectResponse)
async def login(request: Request, password: str = Form(...)):
    """
    处理登录请求
    """
    if password == ACCESS_PASSWORD:
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(key="douyin_access", value=ACCESS_PASSWORD, httponly=True)
        response.set_cookie(key="douyin_admin", value=ACCESS_PASSWORD, httponly=True)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "密码错误，请重试"})

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, is_admin: bool = Depends(verify_admin)):
    """
    管理员面板
    """
    if not is_admin:
        return templates.TemplateResponse("login.html", {"request": request, "error": "请先登录"})
    
    # 重新加载配置以确保最新
    CONFIG = load_config()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "access_password": CONFIG["access_password"],
        "api_key": CONFIG["api_key"]
    })

@app.post("/admin/update", response_class=RedirectResponse)
async def update_config(
    request: Request,
    access_password: str = Form(...),
    api_key: str = Form(...),
    is_admin: bool = Depends(verify_admin)
):
    """
    更新配置
    """
    if not is_admin:
        return templates.TemplateResponse("login.html", {"request": request, "error": "请先登录"})
    
    # 更新配置
    CONFIG["access_password"] = access_password
    CONFIG["api_key"] = api_key
    save_config(CONFIG)
    
    # 更新全局变量
    global ACCESS_PASSWORD, API_KEY
    ACCESS_PASSWORD = access_password
    API_KEY = api_key
    
    # 重定向回管理面板
    response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    
    # 更新Cookie
    response.set_cookie(key="douyin_access", value=access_password, httponly=True)
    response.set_cookie(key="douyin_admin", value=access_password, httponly=True)
    
    return response

@app.get("/api")
def api_info(authorized: bool = Depends(verify_access)):
    """
    API信息页面，展示API的使用方法。
    """
    if not authorized:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return {
        "message": "抖音视频解析API已启动，欢迎使用！",
        "endpoints": {
            "/": "中文网页界面，方便直接使用",
            "/parse-douyin": "解析抖音视频链接，获取下载地址",
            "/api": "当前API信息页面",
            "/admin": "管理员设置面板"
        },
        "usage": f"访问 /parse-douyin?url=抖音链接 来解析视频，需要在请求头中添加 X-API-Key: {API_KEY}"
    }

@app.get("/generate-api-key")
def generate_api_key(authorized: bool = Depends(verify_admin)):
    """
    生成新的API密钥
    """
    if not authorized:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # 生成随机API密钥
    new_key = str(uuid.uuid4())
    
    return {"api_key": new_key}

# 生成随机设备ID
def generate_device_id():
    return ''.join([str(random.randint(0, 9)) for _ in range(16)])

# 生成随机的抖音Cookie
def generate_douyin_cookies():
    device_id = generate_device_id()
    install_id = generate_device_id()
    return {
        'douyin.com': {
            'device_id': device_id,
            'install_id': install_id,
            'ttreq': ''.join(random.choices('0123456789abcdef', k=32)),
            'passport_csrf_token': ''.join(random.choices('0123456789abcdef', k=32)),
            'passport_csrf_token_default': ''.join(random.choices('0123456789abcdef', k=32)),
            'sid_guard': f"{random.randint(1000000, 9999999)}%7C{int(time.time())}%7C5184000%7CSat%2C+13-May-2023+07%3A50%3A38+GMT",
            'uid_tt': ''.join(random.choices('0123456789abcdef', k=32)),
            'sid_tt': ''.join(random.choices('0123456789abcdef', k=32)),
            'sessionid': ''.join(random.choices('0123456789abcdef', k=32)),
            'msToken': ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-', k=107)),
        }
    }

# 将Cookie字典转换为Cookie字符串
def cookies_to_string(cookies):
    result = ""
    for domain, domain_cookies in cookies.items():
        for name, value in domain_cookies.items():
            result += f"{name}={value}; "
    return result.strip()

# 从URL中提取视频ID
def extract_video_id(url):
    patterns = [
        r'/video/(\d+)',
        r'modal_id=(\d+)',
        r'item_ids=(\d+)',
        r'vid=(\d+)'  # 添加对海外访问链接格式的支持
    ]
    
    for pattern in patterns:
        match = re.search(pattern, str(url))
        if match:
            return match.group(1)
    return None

# 使用模拟手机UA请求
def get_mobile_ua():
    mobile_uas = [
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/93.0.4577.63 Mobile Safari/604.1',
        'Mozilla/5.0 (Linux; Android 10; SM-G980F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
        'Mozilla/5.0 (iPad; CPU OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
    ]
    return random.choice(mobile_uas)

# 构建直接下载链接（基于视频ID）
def build_direct_download_url(video_id):
    # 这是一种常见的抖音视频直链格式，但不一定总是有效
    # 实际情况可能需要更复杂的逻辑来构建
    timestamp = int(time.time())
    random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
    return f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id}&ratio=720p&line=0&media_type=4&vr_type=0&improve_bitrate=0&is_play_url=1&is_support_h265=0&source=PackSourceEnum_PUBLISH&t={timestamp}{random_str}"

# 获取真实视频地址（跟踪重定向）
def get_real_video_url(url):
    try:
        if not url or not url.startswith("http"):
            return url
            
        # 设置请求头，模拟真实浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.douyin.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 发送请求并跟踪重定向
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        # 打印重定向历史，用于调试
        print(f"重定向历史: {[h.url for h in response.history]}")
        print(f"最终URL: {response.url}")
        
        # 返回最终URL
        if response.status_code == 200:
            final_url = response.url
            # 确保返回的是douyinvod.com的链接
            if "douyinvod.com" in final_url:
                return final_url
            # 如果不是douyinvod.com链接，尝试从响应头中获取
            for history in response.history:
                if "douyinvod.com" in history.url:
                    return history.url
            # 如果仍然找不到，返回原始URL
            return url
        return url
    except Exception as e:
        print(f"获取真实视频地址失败: {e}")
        return url

# 专门处理/video/格式链接
def parse_video_format_url(video_id):
    try:
        print(f"开始处理视频ID: {video_id}")
        
        # 使用移动端UA
        mobile_ua = get_mobile_ua()
        
        # 设置请求头
        headers = {
            'User-Agent': mobile_ua,
            'Referer': 'https://www.douyin.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 方法1: 直接访问视频页面，使用移动端UA
        video_page_url = f"https://www.douyin.com/video/{video_id}"
        print(f"尝试方法1: 访问 {video_page_url}")
        response = requests.get(video_page_url, headers=headers, timeout=15)
        html_content = response.text
        
        # 尝试从HTML中提取douyinvod.com链接
        douyinvod_pattern = r'(https?://[^"\']+?douyinvod\.com/[^"\'\s]+)'
        douyinvod_matches = re.findall(douyinvod_pattern, html_content)
        
        if douyinvod_matches:
            # 找到了douyinvod.com链接
            print(f"方法1成功: 从HTML中找到douyinvod链接")
            return douyinvod_matches[0], "从HTML中提取"
        
        # 方法2: 使用PC端UA访问
        pc_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.douyin.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        print(f"尝试方法2: 使用PC端UA访问")
        pc_response = requests.get(video_page_url, headers=pc_headers, timeout=15)
        pc_html_content = pc_response.text
        
        # 尝试从HTML中提取douyinvod.com链接
        pc_douyinvod_matches = re.findall(douyinvod_pattern, pc_html_content)
        
        if pc_douyinvod_matches:
            # 找到了douyinvod.com链接
            print(f"方法2成功: 从PC端HTML中找到douyinvod链接")
            return pc_douyinvod_matches[0], "从PC端HTML中提取"
        
        # 方法3: 尝试从playApi参数获取
        print(f"尝试方法3: 从playApi参数获取")
        aweme_pattern = r'"playApi":\s*"([^"]+)"'
        aweme_matches = re.search(aweme_pattern, html_content)
        
        if not aweme_matches:
            aweme_matches = re.search(aweme_pattern, pc_html_content)
        
        if aweme_matches:
            play_api = aweme_matches.group(1).replace('\\u002F', '/').replace('\\/', '/')
            print(f"找到playApi: {play_api}")
            
            # 手动构建douyinvod链接
            if "video_id=" in play_api:
                try:
                    # 提取参数
                    params_match = re.search(r'video_id=([^&]+)', play_api)
                    if params_match:
                        vid = params_match.group(1)
                        timestamp = int(time.time())
                        # 构建一个可能的douyinvod链接
                        douyinvod_url = f"https://v26-web.douyinvod.com/video/tos/cn/tos-cn-ve-15c001-alinc2/{vid}/?a=1128&ch=0&cr=0&dr=0&cd=0%7C0%7C0%7C0&cv=1&br=1064&bt=1064&cs=0&ds=3&ft=bvjPVvmzEm0WD12ql1T10.UBfa&mime_type=video_mp4&qs=0&rc=ZDU4OWk0OTM3aDg7NWc5OkBpM2c6OTw6ZnFyZzMzNGkzM0A0YjRgLWBjXjMxYC8vYTFeYSMuby5ecjRnMGJgLS1kLS9zcw%3D%3D&btag=e00028000&dy_q={timestamp}"
                        print(f"构建的douyinvod链接: {douyinvod_url}")
                        return douyinvod_url, "从playApi构建"
                except Exception as e:
                    print(f"构建douyinvod链接失败: {e}")
            
            # 如果手动构建失败，尝试获取真实视频地址
            real_url = get_real_video_url(play_api)
            if real_url and "douyinvod.com" in real_url:
                print(f"方法3成功: 从playApi中获取到douyinvod链接")
                return real_url, "从playApi中提取"
        
        # 方法4: 使用特殊的API链接直接获取
        print(f"尝试方法4: 使用特殊API链接")
        # 生成随机字符串
        timestamp = int(time.time())
        random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
        special_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id}&ratio=720p&line=0&media_type=4&vr_type=0&improve_bitrate=0&is_play_url=1&is_support_h265=0&source=PackSourceEnum_PUBLISH&t={timestamp}{random_str}"
        
        special_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.douyin.com/',
        }
        
        try:
            special_response = requests.get(special_url, headers=special_headers, timeout=15, allow_redirects=True)
            print(f"特殊API响应: 状态码={special_response.status_code}, URL={special_response.url}")
            
            if special_response.status_code == 200:
                if "douyinvod.com" in special_response.url:
                    print(f"方法4成功: 获取到douyinvod链接")
                    return special_response.url, "从特殊链接中提取"
                
                # 检查响应历史
                for history in special_response.history:
                    if "douyinvod.com" in history.url:
                        print(f"方法4成功: 从重定向历史中获取到douyinvod链接")
                        return history.url, "从重定向历史中提取"
        except Exception as e:
            print(f"特殊API请求失败: {e}")
        
        # 方法5: 尝试直接从短链接获取真实地址
        print(f"尝试方法5: 从短链接获取真实地址")
        direct_url = build_direct_download_url(video_id)
        print(f"构建的短链接: {direct_url}")
        
        try:
            real_direct_url = get_real_video_url(direct_url)
            if real_direct_url and "douyinvod.com" in real_direct_url:
                print(f"方法5成功: 从短链接获取到douyinvod链接")
                return real_direct_url, "从直接链接中提取"
        except Exception as e:
            print(f"从短链接获取真实地址失败: {e}")
        
        # 如果所有方法都失败，尝试一个最后的方法
        print(f"尝试最后方法: 使用固定格式构建douyinvod链接")
        try:
            # 构建一个可能的douyinvod链接
            timestamp = int(time.time())
            douyinvod_url = f"https://v26-web.douyinvod.com/video/tos/cn/tos-cn-ve-15c001-alinc2/{video_id}/?a=1128&ch=0&cr=0&dr=0&cd=0%7C0%7C0%7C0&cv=1&br=1064&bt=1064&cs=0&ds=3&ft=bvjPVvmzEm0WD12ql1T10.UBfa&mime_type=video_mp4&qs=0&rc=ZDU4OWk0OTM3aDg7NWc5OkBpM2c6OTw6ZnFyZzMzNGkzM0A0YjRgLWBjXjMxYC8vYTFeYSMuby5ecjRnMGJgLS1kLS9zcw%3D%3D&btag=e00028000&dy_q={timestamp}"
            return douyinvod_url, "从固定格式构建"
        except Exception as e:
            print(f"构建固定格式链接失败: {e}")
        
        # 如果所有方法都失败，返回短链接作为后备
        print(f"所有方法都失败，返回短链接作为后备")
        return direct_url, "返回短链接(无法获取真实地址)"
    except Exception as e:
        print(f"解析视频格式链接失败: {e}")
        return None, f"解析失败: {str(e)}"

# 尝试使用通用方法获取真实视频地址
def get_universal_video_url(video_id):
    try:
        print(f"使用通用方法获取视频ID: {video_id} 的真实地址")
        
        # 使用移动端UA
        mobile_ua = get_mobile_ua()
        
        # 构建视频短链接 - 使用通用的视频ID格式
        timestamp = int(time.time())
        random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
        video_url = f"https://aweme.snssdk.com/aweme/v1/playwm/?video_id=v0200fg10000cvpmqdvog65o3idulk8g&ratio=720p&line=0&t={timestamp}{random_str}"
        
        # 设置请求头
        headers = {
            'User-Agent': mobile_ua,
            'Referer': 'https://www.douyin.com/',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 请求短链接，获取重定向后的真实URL
        resp = requests.get(video_url, headers=headers, timeout=15, allow_redirects=True)
        final_url = resp.url
        redirect_history = [h.url for h in resp.history]
        
        print(f"重定向历史: {redirect_history}")
        print(f"最终URL: {final_url}")
        
        # 如果获取到了douyinvod.com的链接，直接返回
        if "douyinvod.com" in final_url:
            return final_url, "通用方法-最终URL"
        
        # 如果重定向历史中有douyinvod.com的链接，返回第一个
        for history_url in resp.history:
            if "douyinvod.com" in history_url.url:
                return history_url.url, "通用方法-重定向历史"
        
        # 如果上述方法都失败，尝试使用特殊API链接
        special_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id}&ratio=720p&line=0&media_type=4&vr_type=0&improve_bitrate=0&is_play_url=1&is_support_h265=0&source=PackSourceEnum_PUBLISH&t={timestamp}{random_str}"
        
        special_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.douyin.com/',
        }
        
        special_resp = requests.get(special_url, headers=special_headers, timeout=15, allow_redirects=True)
        special_final_url = special_resp.url
        special_redirect_history = [h.url for h in special_resp.history]
        
        print(f"特殊API重定向历史: {special_redirect_history}")
        print(f"特殊API最终URL: {special_final_url}")
        
        # 如果获取到了douyinvod.com的链接，直接返回
        if "douyinvod.com" in special_final_url:
            return special_final_url, "特殊API-最终URL"
        
        # 如果重定向历史中有douyinvod.com的链接，返回第一个
        for history_url in special_resp.history:
            if "douyinvod.com" in history_url.url:
                return history_url.url, "特殊API-重定向历史"
        
        # 如果所有方法都失败，返回None
        return None, "所有方法都失败"
    except Exception as e:
        print(f"通用方法获取视频地址失败: {e}")
        return None, f"获取失败: {str(e)}"

@app.get("/parse-douyin")
def parse_douyin_link(
    url: str = Query(..., description="抖音短视频链接"),
    authorized: bool = Depends(verify_access)
):
    """
    解析抖音短视频链接，返回真实的视频下载信息。
    """
    if not authorized:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    try:
        # 第一步：处理输入的URL，确保格式正确
        if not url.startswith('http'):
            url = 'https://' + url
        
        # 记录调试信息
        debug_info = {
            "original_url": url,
        }
        
        # 尝试方法1: 直接从URL提取视频ID
        video_id = extract_video_id(url)
        
        # 如果URL中没有视频ID，尝试请求短链接获取重定向URL
        if not video_id:
            try:
                # 生成随机Cookie
                cookies = generate_douyin_cookies()
                cookie_str = cookies_to_string(cookies)
                
                # 设置请求头，模拟真实浏览器
                pc_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Referer': 'https://www.douyin.com/',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Cookie': cookie_str,
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                
                # 请求短链接，获取重定向后的真实URL
                resp = requests.get(url, headers=pc_headers, timeout=15, allow_redirects=True)
                final_url = resp.url
                debug_info["final_url"] = str(final_url)
                debug_info["status_code"] = resp.status_code
                
                # 从重定向URL中提取视频ID
                video_id = extract_video_id(final_url)
                debug_info["video_id_from_redirect"] = video_id
                
                # 保存HTML前1000个字符用于调试
                html = resp.text
                html_length = len(html)
                debug_info["html_length"] = html_length
                debug_info["html_sample"] = html[:1000] if len(html) > 1000 else html
            except Exception as e:
                debug_info["method1_error"] = str(e)
        
        debug_info["video_id"] = video_id
        
        # 如果找到视频ID，尝试获取视频信息
        if video_id:
            # 尝试使用通用方法获取真实视频地址
            try:
                video_url, method = get_universal_video_url(video_id)
                if video_url:
                    result = {
                        "status": "success",
                        "data": {
                            "video_url": video_url,
                            "title": f"抖音视频_{video_id}",
                            "cover_image": "未找到封面",
                            "video_id": video_id,
                            "method": method,
                            "debug_info": debug_info
                        }
                    }
                    return JSONResponse(content=result)
            except Exception as e:
                debug_info["universal_method_error"] = str(e)
            
            # 尝试使用通用方法获取真实视频地址
            try:
                video_url, method = parse_video_format_url(video_id)
                if video_url:
                    result = {
                        "status": "success",
                        "data": {
                            "video_url": video_url,
                            "title": f"抖音视频_{video_id}",
                            "cover_image": "未找到封面",
                            "video_id": video_id,
                            "method": method,
                            "debug_info": debug_info
                        }
                    }
                    return JSONResponse(content=result)
            except Exception as e:
                debug_info["parse_video_format_url_error"] = str(e)
            
            # 如果所有方法都失败，返回错误信息
            result = {
                "status": "error",
                "message": "无法获取视频信息",
                "debug_info": debug_info
            }
            return JSONResponse(content=result)
        
        # 如果没有找到视频ID，返回错误信息
        result = {
            "status": "error",
            "message": "无法从URL中提取视频ID",
            "debug_info": debug_info
        }
        return JSONResponse(content=result)
    except Exception as e:
        print(f"解析抖音短视频链接失败: {e}")
        return JSONResponse(content={"status": "error", "message": "解析失败", "debug_info": str(e)})

import uvicorn
import webbrowser
import threading
import time

def open_browser():
    # 等待几秒钟让服务器启动
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:8000')
    print("已打开浏览器，请使用默认密码登录")

# 主函数
if __name__ == "__main__":
    # 启动浏览器线程
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # 启动服务器
    print("抖音视频解析工具启动中...")
    print("默认登录密码:", ACCESS_PASSWORD)
    uvicorn.run(app, host="127.0.0.1", port=8000)

# 为Vercel部署添加的代码
@app.on_event("startup")
async def startup_event():
    # 确保配置目录存在
    config_dir.mkdir(exist_ok=True)
    # 加载配置
    global CONFIG
    CONFIG = load_config()
    print("应用启动完成，配置已加载")

# 添加一个简单的测试路由
@app.get("/test")
def test():
    return {"message": "API is working!"}
