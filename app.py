import streamlit as st
import requests
import pandas as pd
import io
import time
import base64

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(
    page_title="小红书 AI 选题中台 (V26 视觉全能版)",
    page_icon="🍒",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_URL = "https://generativelanguage.googleapis.com"

# 默认的标题生成风格 (用户可修改)
DEFAULT_STYLE_PROMPT = """
1. **每个标题必须控制在 20 字以内** (非常重要)。
2. 分 5 行展示，每行一个。
3. 不要加序号 (如 1. 2.)，不要加引号。
4. 口语化，带情绪，加入emoji。
5. 针对商务/职场/送礼场景。
"""

# ==========================================
# 2. 核心函数 (支持图片)
# ==========================================

def get_best_model(api_key):
    """智能模型筛选器 (自动锁定支持视觉的 flash 模型)"""
    url = f"{BASE_URL}/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None, f"Key 验证失败 ({resp.status_code})"
            
        data = resp.json()
        models = data.get('models', [])
        
        # 筛选支持生成内容的模型
        chat_models = []
        for m in models:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                name = m['name'].replace('models/', '')
                chat_models.append(name)
        
        if not chat_models:
            return None, "未找到可用模型。"
            
        # 优选 Flash (速度快且视觉能力强)
        best_model = chat_models[0]
        for m in chat_models:
            if "flash" in m: 
                best_model = m; break
            elif "pro" in m and "vision" not in m:
                best_model = m
                
        return best_model, None

    except Exception as e:
        return None, f"网络错误: {e}"

def call_gemini(prompt, api_key, model_name, image_data=None):
    """
    通用 AI 调用 (支持纯文本 或 文本+图片)
    image_data: {'mime_type': 'image/png', 'data': 'base64_string...'}
    """
    url = f"{BASE_URL}/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    # 构建请求体
    parts = [{"text": prompt}]
    
    # 如果有图片，加入图片数据
    if image_data:
        parts.append({
            "inline_data": {
                "mime_type": image_data['mime_type'],
                "data": image_data['data']
            }
        })
        
    payload = {"contents": [{"parts": parts}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60) # 图片处理稍慢，给60秒
        if response.status_code == 200:
            return True, response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return False, f"API报错 {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return False, f"网络错误: {str(e)}"

# ==========================================
# 3. 界面逻辑
# ==========================================

if 'results' not in st.session_state:
    st.session_state.results = []
if 'working_model' not in st.session_state:
    st.session_state.working_model = None

# --- 侧边栏 ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Xiaohongshu_logo.svg/1200px-Xiaohongshu_logo.svg.png", width=50)
    st.header("⚙️ 全局设置")
    
    api_key = st.text_input("输入 API Key", type="password", help="请用带绿勾的 Key")
    
    # 模型检测
    if api_key and not st.session_state.working_model:
        with st.spinner("正在连接 Google 视觉大脑..."):
            model, err = get_best_model(api_key)
            if model:
                st.session_state.working_model = model
                st.success(f"✅ 视觉模型就绪: {model}")
            else:
                st.error(f"❌ {err}")
    
    st.divider()
    
    # --- 新功能 1: 提示词预设 ---
    st.subheader("🎨 风格调优 (Prompt)")
    with st.expander("点击修改标题生成要求", expanded=False):
        user_style_prompt = st.text_area(
            "在此调整输出风格/字数/语气：", 
            value=DEFAULT_STYLE_PROMPT,
            height=150
        )
    
    st.divider()
    # --- 新功能 2: 支持图片上传 ---
    uploaded_file = st.file_uploader(
        "📂 上传素材 (Excel/图片)", 
        type=['xlsx', 'csv', 'png', 'jpg', 'jpeg'],
        accept_multiple_files=False
    )
    st.caption("支持：Excel表格 或 笔记截图/产品实拍图")

# --- 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V26.0 视觉全能版 | 支持图片识别 | 自定义风格")

col1, col2 = st.columns([1, 1.5])

# 左侧：输入
with col1:
    st.subheader("📝 输入素材")
    txt_input = st.text_area("粘贴文案 (纯文本模式)", height=200, placeholder="在此粘贴竞品文案...")
    
    can_run = api_key and st.session_state.working_model
    
    if st.button("✨ 开始智能生成", type="primary", use_container_width=True, disabled=not can_run):
        
        # 1. 统一构建任务列表
        # 任务结构: {'type': 'text'/'image', 'content': ..., 'name': ...}
        tasks = []
        
        # A. 处理文本框输入
        if txt_input:
            texts = [t.strip() for t in txt_input.split('\n\n') if len(t.strip()) > 5]
            for t in texts:
                tasks.append({'type': 'text', 'content': t, 'name': t[:10]})
                
        # B. 处理上传文件 (Excel 或 图片)
        if uploaded_file:
            file_type = uploaded_file.name.split('.')[-1].lower()
            
            # 如果是 Excel/CSV -> 读文字
            if file_type in ['xlsx', 'csv']:
                try:
                    df = pd.read_csv(uploaded_file) if file_type == 'csv' else pd.read_excel(uploaded_file)
                    file_texts = df.iloc[:, 0].dropna().astype(str).tolist()
                    for t in file_texts:
                        tasks.append({'type': 'text', 'content': t, 'name': str(t)[:10]})
                except: st.error("表格读取失败")
            
            # 如果是 图片 -> 读二进制
            elif file_type in ['png', 'jpg', 'jpeg']:
                try:
                    # 读取图片字节并转 Base64
                    bytes_data = uploaded_file.getvalue()
                    base64_str = base64.b64encode(bytes_data).decode('utf-8')
                    mime_type = f"image/{file_type if file_type != 'jpg' else 'jpeg'}"
                    
                    tasks.append({
                        'type': 'image', 
                        'content': {'mime_type': mime_type, 'data': base64_str},
                        'name': f"图片: {uploaded_file.name}"
                    })
                except: st.error("图片处理失败")

        if not tasks: st.warning("请先输入内容或上传文件"); st.stop()
            
        # 2. 开始执行
        progress_bar = st.progress(0)
        status_text = st.empty()
        new_results = []
        model_used = st.session_state.working_model
        
        for i, task in enumerate(tasks):
            status_text.markdown(f"🔄 **正在分析第 {i+1}/{len(tasks)} 条...**")
            
            # --- Step 1: 拆解 (区分文本和图片) ---
            
            if task['type'] == 'text':
                prompt_analyze = f"""
                分析文案:"{task['content'][:800]}..."
                请提取以下4项，严格用 '|||' 隔开：
                1. 原标题
                2. 人设 (销售老徐 / 总助Fiona / 其他)
                3. 核心选题 (⚠️要求：切入点要极细！必须包含具体场景或具体痛点)
                4. 爆款公式
                """
                img_data = None
            else:
                # 图片模式
                prompt_analyze = f"""
                请仔细看这张图片。
                提取并分析以下4项信息，严格用 '|||' 隔开：
                1. 图片中的核心文案或主题 (作为原标题)
                2. 推测发帖人设 (销售老徐 / 总助Fiona / 其他)
                3. 核心选题 (⚠️要求：根据图片内容提炼极细的痛点或场景)
                4. 适合这张图的爆款标题公式
                """
                img_data = task['content']

            # 调用 AI (分析)
            ok1, res1 = call_gemini(prompt_analyze, api_key, model_used, image_data=img_data)
            
            item = {
                "来源": task['name'],
                "人设": "未知",
                "选题": "解析失败",
                "生成标题": ""
            }
            
            if ok1 and "|||" in res1:
                parts = res1.replace('```', '').strip().split('|||')
                if len(parts) >= 4:
                    item["人设"] = parts[1].strip()
                    item["选题"] = parts[2].strip()
                    formula = parts[3].strip()
                    
                    # --- Step 2: 生成 (使用用户自定义的 Style Prompt) ---
                    prompt_gen = f"""
                    你现在是小红书博主【{item['人设']}】。
                    针对细分选题："{item['选题']}"。
                    参考公式："{formula}"。
                    
                    👉 请写 5 个标题。
                    ⚠️ 严格遵守以下风格要求：
                    {user_style_prompt}
                    """
                    # 生成步骤不需要图片，只需要文字逻辑
                    ok2, res2 = call_gemini(prompt_gen, api_key, model_used)
                    item["生成标题"] = res2 if ok2 else "生成失败"
                else:
                    item["生成标题"] = res1
            else:
                item["生成标题"] = res1
            
            new_results.append(item)
            progress_bar.progress((i + 1) / len(tasks))
            
        st.session_state.results = new_results + st.session_state.results
        status_text.success("🎉 完成！")

# 右侧：结果
with col2:
    st.subheader(f"📊 结果 ({len(st.session_state.results)})")
    
    if st.session_state.results:
        df_res = pd.DataFrame(st.session_state.results)
        
        st.dataframe(
            df_res, 
            column_config={
                "生成标题": st.column_config.TextColumn("AI 爆款标题", width="large", help="自动换行"),
                "选题": st.column_config.TextColumn("细分切入点", width="medium"),
                "来源": st.column_config.TextColumn("来源", width="small"),
            },
            use_container_width=True,
            height=600
        )
        
        # Excel 导出配置
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False, sheet_name='Sheet1')
            workbook = writer.book
            worksheet = writer.sheets['Sheet1']
            wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
            worksheet.set_column('A:A', 15)
            worksheet.set_column('B:B', 15)
            worksheet.set_column('C:C', 30, wrap_format)
            worksheet.set_column('D:D', 50, wrap_format)
            
        st.download_button(
            label="📥 下载 Excel",
            data=output.getvalue(),
            file_name=f"小红书AI_{int(time.time())}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        if st.button("🗑️ 清空"):
            st.session_state.results = []
            st.rerun()
