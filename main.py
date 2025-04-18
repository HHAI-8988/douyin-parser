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
        
        # 尝试方法2: 如果找到视频ID，使用抖音官方API
        if video_id:
            try:
                # 生成新的随机Cookie
                cookies = generate_douyin_cookies()
                cookie_str = cookies_to_string(cookies)
                
                # 使用移动端UA
                mobile_ua = get_mobile_ua()
                
                # 抖音API请求头
                api_headers = {
                    'User-Agent': mobile_ua,
                    'Referer': 'https://www.douyin.com/',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept': 'application/json, text/plain, */*',
                    'Cookie': cookie_str,
                    'Connection': 'keep-alive',
                    'X-Requested-With': 'XMLHttpRequest',
                }
                
                # 抖音API请求URL
                api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"
                api_resp = requests.get(api_url, headers=api_headers, timeout=15)
                
                debug_info["api_url"] = api_url
                debug_info["api_status_code"] = api_resp.status_code
                debug_info["api_headers"] = dict(api_resp.headers)
                
                # 尝试解析JSON响应
                try:
                    data = api_resp.json()
                    debug_info["api_response_sample"] = str(data)[:500] + "...(截断)"  # 截断显示
                    
                    if 'item_list' in data and len(data['item_list']) > 0:
                        item = data['item_list'][0]
                        
                        # 提取视频信息
                        title = item.get('desc', '未找到标题')
                        
                        # 提取封面
                        cover_image = None
                        if 'cover_data' in item and 'url_list' in item['cover_data'] and len(item['cover_data']['url_list']) > 0:
                            cover_image = item['cover_data']['url_list'][0]
                        elif 'video' in item and 'cover' in item['video'] and 'url_list' in item['video']['cover'] and len(item['video']['cover']['url_list']) > 0:
                            cover_image = item['video']['cover']['url_list'][0]
                        
                        # 提取无水印视频地址
                        video_url = None
                        if 'video' in item and 'play_addr' in item['video'] and 'url_list' in item['video']['play_addr'] and len(item['video']['play_addr']['url_list']) > 0:
                            video_url = item['video']['play_addr']['url_list'][0]
                            # 替换域名，获取无水印链接
                            video_url = video_url.replace('playwm', 'play')
                        
                        # 构建结果
                        if video_url and video_url != "未找到视频链接":
                            result = {
                                "status": "success",
                                "data": {
                                    "video_url": video_url,
                                    "title": title,
                                    "cover_image": cover_image if cover_image else "未找到封面",
                                    "video_id": video_id,
                                    "method": "api",
                                    "debug_info": debug_info
                                }
                            }
                            return JSONResponse(content=result)
                except Exception as e:
                    debug_info["api_json_error"] = str(e)
                    debug_info["api_raw_response"] = api_resp.text[:500] + "...(截断)"
            except Exception as e:
                debug_info["method2_error"] = str(e)
        
        # 尝试方法3: 使用移动端模拟请求
        try:
            # 生成新的随机Cookie
            cookies = generate_douyin_cookies()
            cookie_str = cookies_to_string(cookies)
            
            # 使用移动端UA
            mobile_ua = get_mobile_ua()
            
            # 移动端请求头
            mobile_headers = {
                'User-Agent': mobile_ua,
                'Referer': 'https://www.douyin.com/',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Cookie': cookie_str,
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # 直接请求原始URL，模拟移动端
            mobile_resp = requests.get(url, headers=mobile_headers, timeout=15, allow_redirects=True)
            mobile_final_url = mobile_resp.url
            
            debug_info["mobile_final_url"] = str(mobile_final_url)
            debug_info["mobile_status_code"] = mobile_resp.status_code
            
            # 保存HTML前1000个字符用于调试
            mobile_html = mobile_resp.text
            mobile_html_length = len(mobile_html)
            debug_info["mobile_html_length"] = mobile_html_length
            debug_info["mobile_html_sample"] = mobile_html[:1000] if mobile_html_length > 1000 else mobile_html
            
            # 尝试多种正则模式匹配视频地址
            patterns = [
                r'playAddr: \\"(.*?)\\"',
                r'playAddr: "(.*?)"',
                r'"playAddr":"(.*?)"',
                r'"play_addr":.*?"url_list":\["(.*?)"',
                r'"url":"(https://.*?\.mp4.*?)"',
                r'src="(https://www.douyin.com/aweme/.*?)"',
                r'src="(https://v.douyin.com/.*?)"',
                r'"(https://v\d+-\w+\.douyinvod\.com/[^"]+)"',
                r'href="(https://www.iesdouyin.com/share/video/\d+/)"',
                r'<video [^>]*src="([^"]+)"',
                r'<source [^>]*src="([^"]+)"',
                r'playAddr: "(http[^"]+)"',
                r'"url":"([^"]+\.mp4[^"]*)"',
                r'"play_addr":\{"uri":"([^"]+)"',
                r'src="(https?://[^"]+\.mp4[^"]*)"'
            ]
            
            video_url = None
            matched_pattern = None
            
            for pattern in patterns:
                match = re.search(pattern, mobile_html)
                if match:
                    video_url = match.group(1)
                    matched_pattern = pattern
                    # 替换转义字符
                    video_url = video_url.replace('\\u002F', '/').replace('\\/', '/')
                    break
            
            debug_info["mobile_matched_pattern"] = matched_pattern
            
            # 提取标题
            title_patterns = [
                r'<title>(.*?)</title>',
                r'"title":"(.*?)"',
                r'"desc":"(.*?)"'
            ]
            
            title_text = "未找到标题"
            for pattern in title_patterns:
                title_match = re.search(pattern, mobile_html)
                if title_match:
                    title_text = title_match.group(1)
                    break
            
            # 提取封面
            cover_patterns = [
                r'cover: \\"(.*?)\\"',
                r'cover: "(.*?)"',
                r'"cover":"(.*?)"',
                r'"cover_url":"(.*?)"',
                r'poster="([^"]+)"',
                r'"origin_cover":\{"uri":"([^"]+)"'
            ]
            
            cover_url = None
            for pattern in cover_patterns:
                match = re.search(pattern, mobile_html)
                if match:
                    cover_url = match.group(1)
                    # 替换转义字符
                    cover_url = cover_url.replace('\\u002F', '/').replace('\\/', '/')
                    break
            
            # 如果找到视频链接，返回结果
            if video_url and video_url != "未找到视频链接":
                result = {
                    "status": "success",
                    "data": {
                        "video_url": video_url,
                        "title": title_text,
                        "cover_image": cover_url if cover_url else "未找到封面",
                        "method": "mobile",
                        "debug_info": debug_info
                    }
                }
                return JSONResponse(content=result)
        except Exception as e:
            debug_info["method3_error"] = str(e)
        
        # 尝试方法4: 如果有视频ID，尝试构建直接下载链接
        if video_id:
            try:
                direct_url = build_direct_download_url(video_id)
                debug_info["direct_url"] = direct_url
                
                result = {
                    "status": "success",
                    "data": {
                        "video_url": direct_url,
                        "title": f"抖音视频_{video_id}",
                        "cover_image": "未找到封面",
                        "video_id": video_id,
                        "method": "direct_build",
                        "debug_info": debug_info
                    }
                }
                return JSONResponse(content=result)
            except Exception as e:
                debug_info["method4_error"] = str(e)
        
        # 如果所有方法都失败，返回错误信息
        result = {
            "status": "error",
            "msg": "无法解析视频链接，请检查链接是否正确或尝试其他链接",
            "data": {
                "video_url": "未找到视频链接",
                "title": "未找到标题",
                "cover_image": "未找到封面",
                "debug_info": debug_info
            }
        }
        
        return JSONResponse(content=result)
    except Exception as e:
        # 捕获所有异常，返回详细错误信息
        error_info = {
            "status": "error", 
            "msg": f"解析过程中出现错误: {str(e)}", 
            "traceback": str(e.__traceback__.tb_lineno),
            "url": url
        }
        return JSONResponse(content=error_info)

# 后续可以优化正则和异常处理，适配更多格式

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
