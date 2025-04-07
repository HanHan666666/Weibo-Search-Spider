# Weibo Search - 微博搜索爬虫

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/badge/python-3.7%2B-blue)

## 简介
Weibo Search 是一个强大的微博搜索爬虫工具，用于搜索和提取微博内容、互动数据及相关信息。该工具支持自动登录、cookie保存与加载、内容展开、分页爬取等功能，同时兼容微博不同版本的界面布局。

## 特性

- **自动登录处理**: 自动打开微博登录页面，支持cookie保存和加载，避免重复登录
- **强大的内容提取**: 支持提取多种格式的微博内容，包括标准文本、全文展开、视频描述等
- **互动数据统计**: 精准抓取点赞数、评论数、转发数等互动指标
- **分页爬取**: 支持自动翻页，可设置最大爬取页数
- **数据导出**: 将爬取结果保存为Excel文件，便于后续分析

## 安装

### 前置需求
- Python 3.7+
- Chrome浏览器

### 环境安装
1. 克隆仓库
```bash
git clone https://github.com/your-username/weibo_search.git
cd weibo_search
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

### 所需依赖
```
selenium
pandas
webdriver-manager
```

## 使用方法

### 基本使用
1. 打开 `weibo_search.py` 文件，在最后修改搜索关键词:
```python
if __name__ == "__main__":
    keyword = "你的搜索关键词"  # 替换为你要搜索的关键词
    spider = WeiboSpider(keyword)
    spider.start()
```

2. 运行脚本:
```bash
python weibo_search.py
```

3. 首次运行时会自动打开浏览器，**但需需要手动点击登录按钮进行登录**。登录成功后，程序会自动保存登录信息(cookie)，下次运行时将无需重复登录。

4. 爬取完成后，结果将保存为Excel文件，文件名格式为：`weibo_{关键词}_{日期时间}.xlsx`

### 高级设置

您可以通过修改代码中的以下参数来自定义爬取行为：

1. 修改最大爬取页数:
```python
self.max_pages = 30  # 设置想要爬取的最大页数
```

2. 启用无头模式 (不显示浏览器界面):
```python
# 取消注释以下行启用无头模式
chrome_options.add_argument("--headless")
```

3. 修改等待超时时间:
```python
self.wait = WebDriverWait(self.driver, 20)  # 将20改为您期望的超时秒数
```

## 数据字段说明

爬取的Excel文件包含以下字段:
- **微博ID**: 微博的唯一标识符
- **内容**: 微博正文内容
- **点赞数**: 获得的点赞数量
- **评论数**: 评论数量
- **转发数**: 转发/分享数量
- **发布时间**: 微博发布时间
- **微博链接**: 原微博的URL链接

## 常见问题


### Q: 爬取的数据不完整或点赞数都是0？
A: 微博界面可能发生了变化，可以查看控制台输出的警告信息，并根据情况修改代码中的CSS选择器。

## 免责声明

本工具仅供学习和研究使用，请遵守微博平台的使用条款和相关法律法规。不要过度爬取或将获取的数据用于商业目的。使用本工具造成的任何后果，由使用者自行承担。

## 贡献

欢迎通过以下方式贡献:
1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启一个 Pull Request

## 许可证

本项目基于 MIT 许可证开源 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

如有问题，请通过 GitHub Issues 联系

---
*注意: 请合理使用本工具，尊重网站规则和他人创作。*