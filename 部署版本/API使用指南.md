# 抖音视频解析API使用指南

## 简介

这个工具可以帮你获取抖音视频的无水印下载地址。除了网页界面外，还提供了API接口，让你可以在自己的程序中调用这个功能。

## 什么是API？

API就像是一个"服务窗口"，你可以通过它向服务器发送请求，获取你需要的信息。在这里，你可以发送抖音链接，服务器会返回视频的下载地址。

## 一键启动服务

我们提供了一键启动脚本，让你可以轻松使用：

1. 双击 `启动抖音视频解析工具.bat`
2. 等待几秒钟，浏览器会自动打开
3. 使用默认密码 `douyin123` 登录
4. 开始使用工具解析视频

## 如何使用API？

### 方式一：在浏览器中直接访问（最简单）

如果你只是想快速测试，可以在浏览器地址栏输入：
```
http://127.0.0.1:8000/parse-douyin?url=抖音链接
```

注意：这种方式需要你先在浏览器中登录系统。

### 方式二：在程序中调用（更灵活）

如果你想在自己的程序中调用这个API，需要：

1. **准备信息**：
   - 抖音视频链接
   - API密钥（在管理设置标签页中查看）

2. **发送请求**：
   - 请求地址：`http://127.0.0.1:8000/parse-douyin?url=抖音链接`
   - 请求头：`X-API-Key: 你的API密钥`

3. **获取结果**：
   服务器会返回一个JSON格式的结果，包含：
   - `video_url`：视频下载地址
   - `title`：视频标题
   - `cover_image`：封面图片地址

## 示例代码（不懂代码可以忽略）

以下是几种常见编程语言的调用示例：

### 网页JavaScript

```javascript
// 抖音链接
const douyinUrl = "https://v.douyin.com/xxxxxx/";
// API密钥（从管理设置中获取）
const apiKey = "你的API密钥";

// 发送请求
fetch(`http://127.0.0.1:8000/parse-douyin?url=${encodeURIComponent(douyinUrl)}`, {
  headers: {
    "X-API-Key": apiKey
  }
})
.then(response => response.json())
.then(data => {
  if (data.status === "success") {
    // 获取视频下载地址
    const videoUrl = data.data.video_url;
    console.log("视频下载地址:", videoUrl);
  } else {
    console.log("解析失败:", data.msg);
  }
});
```

### Python

```python
import requests

# 抖音链接
douyin_url = "https://v.douyin.com/xxxxxx/"
# API密钥（从管理设置中获取）
api_key = "你的API密钥"

# 发送请求
response = requests.get(
    "http://127.0.0.1:8000/parse-douyin",
    params={"url": douyin_url},
    headers={"X-API-Key": api_key}
)

# 获取结果
result = response.json()
if result["status"] == "success":
    video_url = result["data"]["video_url"]
    print(f"视频下载地址: {video_url}")
else:
    print(f"解析失败: {result['msg']}")
```

## 常见问题

### 1. 如何获取API密钥？

1. 登录系统后，点击顶部的"管理设置"标签
2. 在页面中可以看到当前的API密钥
3. 如果想生成新的密钥，点击"生成新密钥"按钮
4. 记得点击"保存设置"使新密钥生效

### 2. 返回401错误怎么办？

这表示API密钥不正确或未提供。请检查：
- 是否正确复制了API密钥
- 请求头中的`X-API-Key`是否拼写正确

### 3. 返回解析失败怎么办？

可能原因：
- 链接格式不正确
- 抖音视频不存在或已被删除
- 抖音更新了防爬机制

尝试使用不同格式的抖音链接，或查看返回的错误信息获取更多线索。

## 注意事项

1. 本工具仅用于学习和研究，请勿用于商业用途
2. 请尊重原创作者的版权，不要非法传播视频内容
3. 使用本工具所产生的一切法律责任由使用者自行承担
