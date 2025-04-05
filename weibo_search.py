from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time
import pandas as pd
import re
import os
import pickle
import json
from datetime import datetime

class WeiboSpider:
    def __init__(self, keyword):
        # Set up Chrome options
        chrome_options = Options()
        # Add any needed options
        # chrome_options.add_argument("--headless")  # Uncomment if you want to run in headless mode
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # 避免被检测为自动化工具
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Use webdriver_manager to automatically get the correct ChromeDriver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        # 修改navigator.webdriver为false，进一步逃过检测
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.wait = WebDriverWait(self.driver, 20)
        self.base_url = f"https://s.weibo.com/weibo?q={keyword}&xsort=hot&suball=1&Refer=g"
        self.current_page = 1
        self.max_pages = 2  # 限制最多页数
        self.cookie_file = "weibo_cookies.pkl"
        self.cookie_json_file = "weibo_cookies.json"  # 添加JSON格式的cookie文件，以便查看和调试
        
        # Store collected data
        self.weibo_data = []
        self.keyword = keyword

    def start(self):
        # 先访问微博主页，而不是直接访问搜索页，这样更有利于cookie的设置
        self.driver.get("https://weibo.com")
        time.sleep(2)
        
        # 处理登录
        if not self.handle_login():
            print("登录失败，请重试")
            return
            
        # 登录成功后再访问搜索页面
        print("正在跳转到搜索页面...")
        self.driver.get(self.base_url)
        time.sleep(3)
        
        while self.current_page <= self.max_pages:  # 限制最多页数
            print(f"正在爬取第 {self.current_page} 页...")
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".card-wrap"))
                )
            except TimeoutException:
                print("页面加载超时，可能是被限制或网络问题")
                break
                
            # 处理本页内容
            self.parse_page()
            
            # 尝试翻页
            if not self.go_to_next_page():
                print("已经是最后一页，爬取结束")
                break
                
            self.current_page += 1
            time.sleep(2)  # 防止请求过快
        
        if self.current_page > self.max_pages:
            print(f"已达到设定的最大页数 {self.max_pages}，爬取结束")
        
        # 保存数据到Excel
        self.save_to_excel()

    def parse_page(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR, ".card-wrap")
        for card in cards:
            try:
                # 获取微博ID
                weibo_id = card.get_attribute("mid")
                
                # 展开全文
                self.expand_full_text(card)
                
                # 获取内容 - 增强版，处理多种内容格式
                content = self.extract_content(card, weibo_id)
                
                # 获取发布时间
                try:
                    time_element = card.find_element(By.CSS_SELECTOR, ".from a:first-child")
                    publish_time = time_element.text.strip()
                except NoSuchElementException:
                    publish_time = ""
                
                # 获取微博链接
                try:
                    link_element = card.find_element(By.CSS_SELECTOR, ".from a:first-child")
                    weibo_link = link_element.get_attribute("href")
                except NoSuchElementException:
                    weibo_link = ""
                
                # 获取点赞数、评论数、转发数
                like_count, comment_count, repost_count = self.get_interaction_counts(card)
                
                # 打印内容
                print("微博ID:", weibo_id)
                print("内容:", content)
                print("点赞数:", like_count)
                print("评论数:", comment_count)
                print("转发数:", repost_count)
                print("发布时间:", publish_time)
                print("微博链接:", weibo_link)
                print("-" * 50)
                
                # 存储数据
                self.weibo_data.append({
                    "微博id": weibo_id,
                    "内容": content,
                    "点赞数": like_count,
                    "评论数": comment_count,
                    "转发数": repost_count,
                    "发布时间": publish_time,
                    "微博链接": weibo_link
                })
                
            except Exception as e:
                print("提取内容失败：", str(e))
    
    def extract_content(self, card, weibo_id):
        """通用的内容提取方法，不包含特定硬编码的适配"""
        content = ""
        
        # 按优先级尝试不同的内容提取方法
        selectors = [
            "p.txt[node-type='feed_list_content_full']",  # 已展开的全文内容
            "p.txt[node-type='feed_list_content']",       # 标准文本内容
            ".media-title",                               # 媒体标题
            ".card-comment p.txt",                        # 转发评论
            ".content p",                                 # 通用内容段落
        ]
        
        # 尝试所有可能的选择器
        for selector in selectors:
            try:
                if (selector == ".content p"):
                    # 对于多段落内容，需要特殊处理
                    elements = card.find_elements(By.CSS_SELECTOR, selector)
                    texts = []
                    for element in elements:
                        text = element.text.strip()
                        # 过滤掉操作按钮文本
                        if text and not any(keyword in text for keyword in ["转发", "评论", "赞"]):
                            texts.append(text)
                    if texts:
                        content = " ".join(texts)
                        break
                else:
                    # 对于单一选择器
                    element = card.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text:
                        if "card-comment" in selector:
                            content = f"转发微博: {text}"
                        else:
                            content = text
                        break
            except NoSuchElementException:
                continue
        
        # 如果上述方法都失败，尝试使用JavaScript获取内容
        if not content:
            try:
                script = """
                return arguments[0].innerText;
                """
                js_content = self.driver.execute_script(script, card)
                if js_content:
                    # 清理内容
                    lines = [line.strip() for line in js_content.split("\n") if line.strip()]
                    # 过滤掉操作按钮文本
                    filtered_lines = [line for line in lines if not any(keyword in line for keyword in ["转发", "评论", "赞"])]
                    if filtered_lines:
                        content = " ".join(filtered_lines[:3])  # 只取前几行，避免过多无关内容
            except:
                pass
        
        # 最后的备用方案
        if not content:
            try:
                # 截取卡片中的文本前100个字符作为内容预览
                text = card.text.strip()
                content = text[:100].replace("\n", " ") if text else "无法提取内容"
            except:
                content = "无法提取内容"
                
        return content
    
    def get_interaction_counts(self, card):
        """获取微博互动数据：点赞数、评论数、转发数 - 修复版本"""
        try:
            # 默认值
            repost_count = "0"
            comment_count = "0"
            like_count = "0"
            
            # 方法1：标准方式 - 查找交互元素列表
            try:
                card_act = card.find_element(By.CSS_SELECTOR, ".card-act")
                interaction_elements = card_act.find_elements(By.CSS_SELECTOR, "ul li")
                
                if interaction_elements and len(interaction_elements) >= 2:
                    # 解析转发数 (通常是第2个元素)
                    if len(interaction_elements) >= 2:
                        repost_text = interaction_elements[1].text.strip()
                        repost_count = self.extract_number(repost_text)
                    
                    # 解析评论数 (通常是第3个元素)
                    if len(interaction_elements) >= 3:
                        comment_text = interaction_elements[2].text.strip()
                        comment_count = self.extract_number(comment_text)
                    
                    # 解析点赞数 (通常是第4个元素)
                    if len(interaction_elements) >= 4:
                        # 仅当存在文本时才使用文本
                        like_text = interaction_elements[3].text.strip()
                        if like_text and re.search(r'\d+', like_text):
                            like_count = self.extract_number(like_text)
                        else:
                            # 尝试从交互元素的属性中获取点赞数
                            try:
                                like_element = interaction_elements[3].find_element(By.CSS_SELECTOR, "a")
                                like_title = like_element.get_attribute("title") or ""
                                like_action_data = like_element.get_attribute("action-data") or ""
                                
                                # 从title属性中获取
                                if "赞" in like_title and re.search(r'\d+', like_title):
                                    like_count = self.extract_number(like_title)
                                # 从action-data属性中获取
                                elif "attitude_count" in like_action_data:
                                    match = re.search(r'attitude_count=(\d+)', like_action_data)
                                    if match:
                                        like_count = match.group(1)
                            except:
                                pass
            except NoSuchElementException:
                pass
                
            # 方法2：直接查找特定的交互元素（如果方法1未找到有效数据）
            if like_count == "0" or comment_count == "0" or repost_count == "0":
                # 点赞数的查找方法优先级
                like_selectors = [
                    ".woo-box-flex .woo-like-count",   # 新版微博点赞数
                    ".pos-abs .woo-like-count",        # 另一种新版样式
                    ".card .price",                    # 某些情况下的点赞数
                    "[node-type='like_status'] em",    # 老版点赞数
                    "a[action-type='like'] em",        # 另一种老版点赞数
                    ".like_status .line em"            # 更老的版本
                ]
                
                # 尝试点赞数的选择器
                if like_count == "0":
                    for selector in like_selectors:
                        try:
                            elements = card.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                for element in elements:
                                    text = element.text.strip()
                                    if text and re.search(r'\d+', text):
                                        like_count = self.extract_number(text)
                                        break
                                if like_count != "0":
                                    break
                        except:
                            continue
                
                # 如果仍然没有找到点赞数，尝试使用JavaScript直接获取
                if like_count == "0":
                    try:
                        # 获取卡片的所有文本，并尝试找到包含"赞"的部分
                        like_script = """
                        var elements = arguments[0].querySelectorAll('*');
                        for (var i = 0; i < elements.length; i++) {
                            var text = elements[i].innerText || '';
                            if (text.includes('赞') && /\\d+/.test(text)) {
                                return text;
                            }
                        }
                        return '';
                        """
                        like_text = self.driver.execute_script(like_script, card)
                        if like_text:
                            like_count = self.extract_number(like_text)
                    except:
                        pass
                
                # 评论数查找方法
                comment_selectors = [
                    ".woo-box-flex .comment-auto",    # 新版评论数
                    "[node-type='comment_btn_text']", # 老版评论数
                    "a[action-type='commentBox'] span", # 另一种老版评论数
                    ".comment_auto"                   # 更老的版本
                ]
                
                if comment_count == "0":
                    for selector in comment_selectors:
                        try:
                            elements = card.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                for element in elements:
                                    text = element.text.strip()
                                    if text and re.search(r'\d+', text):
                                        comment_count = self.extract_number(text)
                                        break
                                if comment_count != "0":
                                    break
                        except:
                            continue
                
                # 转发数查找方法
                repost_selectors = [
                    ".woo-box-flex .repost-auto",     # 新版转发数
                    "[node-type='forward_btn_text']", # 老版转发数
                    "a[action-type='forward'] span",  # 另一种老版转发数
                    ".repost_auto"                    # 更老的版本
                ]
                
                if repost_count == "0":
                    for selector in repost_selectors:
                        try:
                            elements = card.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                for element in elements:
                                    text = element.text.strip()
                                    if text and re.search(r'\d+', text):
                                        repost_count = self.extract_number(text)
                                        break
                                if repost_count != "0":
                                    break
                        except:
                            continue
            
            # 调试日志
            if like_count == "0":
                print(f"警告: 微博ID {card.get_attribute('mid')} 的点赞数提取失败")
                
            return like_count, comment_count, repost_count
            
        except Exception as e:
            print(f"获取互动数据失败: {str(e)}")
            return "0", "0", "0"
    
    def extract_number(self, text):
        """从文本中提取数字"""
        if not text:
            return "0"
            
        # 清理数字文本
        number = "0"
        match = re.search(r'\d+(\.\d+)?', text)
        if match:
            number_text = match.group()
            
            # 处理"万"的情况
            if "万" in text:
                try:
                    number = str(int(float(number_text) * 10000))
                except:
                    number = "0"
            else:
                number = number_text
                
        return number
    
    def clean_count(self, count_str):
        """清理数字字符串，处理'万'等情况"""
        if not count_str or count_str in ["转发", "评论", "赞"]:
            return "0"
        
        if "万" in count_str:
            count_str = count_str.replace("万", "")
            try:
                return str(int(float(count_str) * 10000))
            except:
                return "0"
        return count_str
    
    def expand_full_text(self, card):
        try:
            expand_btn = card.find_element(
                By.CSS_SELECTOR, "a[action-type='fl_unfold']"
            )
            self.driver.execute_script("arguments[0].click();", expand_btn)
            time.sleep(0.5)  # 等待内容展开
        except NoSuchElementException:
            pass

    def go_to_next_page(self):
        try:
            # 查找下一页按钮，注意微博可能有多种页面结构
            try:
                # 第一种方式：直接找"下一页"按钮
                next_btn = self.driver.find_element(By.CSS_SELECTOR, "a.next")
                
                # 检查是否是最后一页（有些时候最后一页的"下一页"按钮会存在但是没有href或者被禁用）
                if "disable" in next_btn.get_attribute("class") or not next_btn.get_attribute("href"):
                    return False
                
                # 使用JavaScript点击，避免元素可能被覆盖的问题
                self.driver.execute_script("arguments[0].click();", next_btn)
                
                # 等待页面加载
                time.sleep(2)
                
                # 确保新页面已加载
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".card-wrap")))
                return True
                
            except NoSuchElementException:
                # 尝试第二种方式：查找页码列表中的"下一页"
                try:
                    # 有些微博页面的翻页是通过页码列表实现的
                    current_page_element = self.driver.find_element(By.CSS_SELECTOR, ".pagenum")
                    current_page_text = current_page_element.text
                    # 提取当前页码，如"第1页"中的1
                    current_page_num = int(''.join(filter(str.isdigit, current_page_text)))
                    
                    # 构造下一页的URL
                    next_page_url = f"{self.base_url}&page={current_page_num + 1}"
                    self.driver.get(next_page_url)
                    
                    # 等待页面加载
                    time.sleep(2)
                    
                    # 确保新页面已加载
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".card-wrap")))
                    return True
                    
                except (NoSuchElementException, ValueError):
                    return False
                    
        except (NoSuchElementException, TimeoutException) as e:
            print(f"翻页出错: {str(e)}")
            return False

    def handle_login(self):
        """处理登录逻辑，优先使用已保存的cookies，如果失效则自动打开登录页面"""
        # 首先尝试加载cookies
        if self.load_cookies():
            print("已加载保存的登录信息")
            self.driver.refresh()  # 刷新页面应用cookies
            time.sleep(3)
            
            # 验证cookies是否有效（检查是否仍需登录）
            login_status = self.check_login_status()
            if login_status:
                print("登录成功！")
                return True
            else:
                print("保存的登录信息已过期，需要重新登录")
        
        # 如果没有cookies或cookies已过期，则自动打开登录页面
        print("自动打开微博登录页面...")
        # 直接访问登录URL，这比点击登录按钮更可靠
        self.driver.get("https://weibo.com/login.php")
        time.sleep(2)
        
        # 确保已经成功跳转到登录页面
        if "login" not in self.driver.current_url.lower():
            # 如果不是登录页面，尝试点击登录按钮
            try:
                # 尝试多种可能的登录按钮选择器
                login_selectors = [
                    ".login_innerwrap a", 
                    ".gn_login a", 
                    ".gn_login_list a",
                    "a[node-type='loginBtn']",
                    "a.login"
                ]
                
                for selector in login_selectors:
                    login_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if login_buttons:
                        # 使用JavaScript点击，避免可能的覆盖问题
                        self.driver.execute_script("arguments[0].click();", login_buttons[0])
                        print(f"找到并点击了登录按钮 ({selector})")
                        time.sleep(2)
                        break
            except Exception as e:
                print(f"尝试点击登录按钮时出错: {e}")
        
        print("请在打开的浏览器窗口中完成登录")
        print("登录成功后将自动保存登录信息，下次运行时将自动使用")
        print("提示：请确保完全登录成功（看到个人头像或用户名），然后等待脚本继续运行")
        
        # 等待用户登录
        try:
            # 使用lambda函数包装check_login_status方法，避免参数不匹配的问题
            self.wait.until(lambda driver: self.check_login_status())
            print("检测到成功登录")
            
            # 保存cookies以供下次使用
            self.save_cookies()
            print("已保存登录信息")
            return True
        except TimeoutException:
            print("登录超时，可能需要重新运行程序")
            return False

    def check_login_status(self):
        """检查是否已经登录成功（更可靠的方式）"""
        try:
            # 尝试多种方式检测登录状态
            
            # 方法1: 检查是否有登录按钮 - 如果有则表示未登录
            try:
                login_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".login_innerwrap, .gn_login, .gn_login_list")
                if login_buttons:
                    return False
            except:
                pass
                
            # 方法2: 检查是否有用户名或头像 - 如果有则表示已登录
            try:
                user_elements = self.driver.find_elements(By.CSS_SELECTOR, ".gn_name, .Screen_account_1aXEn, .name")
                if user_elements:
                    for element in user_elements:
                        if element.text.strip() or element.get_attribute("title"):
                            print(f"找到用户元素: {element.text.strip() or element.get_attribute('title')}")
                            return True
            except:
                pass
                
            # 方法3: 检查是否有登出按钮 - 如果有则表示已登录
            try:
                logout_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='logout']")
                if logout_elements:
                    return True
            except:
                pass
                
            # 方法4: 尝试获取页面上的用户ID
            user_id = self.driver.execute_script("return $CONFIG ? $CONFIG['uid'] : ''")
            if user_id and user_id != '':
                print(f"找到用户ID: {user_id}")
                return True
                
            return False
        except Exception as e:
            print(f"检查登录状态时出错: {e}")
            return False

    def save_cookies(self):
        """保存当前会话的cookies到文件（同时保存为pickle和json格式）"""
        try:
            cookies = self.driver.get_cookies()
            
            # 保存为pickle格式（用于程序读取）
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(cookies, f)
                
            # 同时保存为json格式（便于人工查看和调试）
            with open(self.cookie_json_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=4)
                
            print(f"成功保存了 {len(cookies)} 个cookies")
        except Exception as e:
            print(f"保存cookies失败: {str(e)}")
    
    def load_cookies(self):
        """从文件加载cookies"""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'rb') as f:
                    cookies = pickle.load(f)
                
                print(f"正在加载 {len(cookies)} 个cookies...")
                # 添加cookies到浏览器
                for cookie in cookies:
                    try:
                        # 移除可能导致问题的属性
                        if 'expiry' in cookie:
                            del cookie['expiry']
                            
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        print(f"添加cookie失败 ({cookie.get('name')}): {str(e)}")
                        
                return True
            return False
        except Exception as e:
            print(f"加载cookies失败: {str(e)}")
            return False
    
    def save_to_excel(self):
        """将爬取的数据保存到Excel文件"""
        if not self.weibo_data:
            print("没有获取到数据，Excel文件未生成")
            return
        
        # 创建DataFrame
        df = pd.DataFrame(self.weibo_data)
        
        # 生成文件名（包含关键词和时间）
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"weibo_{self.keyword}_{now}.xlsx"
        
        # 保存Excel（移除encoding参数，Excel文件不支持此参数）
        df.to_excel(filename, index=False)
        print(f"数据已保存到 {filename}")

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

if __name__ == "__main__":
    keyword = "喜剧之王单口季"  # 替换为你要搜索的关键词
    spider = WeiboSpider(keyword)
    spider.start()