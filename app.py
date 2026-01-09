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
    page_title="小红书 AI 选题中台 (V28 逻辑透明版)",
    page_icon="🍒",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_URL = "https://generativelanguage.googleapis.com"

# 默认风格预设
DEFAULT_STYLE_PROMPT = """
1. **每个标题必须控制在 20 字以内** (非常重要)。
2. 分 5 行展示，每行一个。
3. 不要加序号 (如 1. 2.)，不要加引号。
4. 口语化，带情绪，加入emoji。
"""

# ==========================================
# 2. 核心函数
# ==========================================

def get_best_model(api_key):
    url = f"{BASE_URL}/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200: return None, "Key 验证失败"
        data = resp.json()
        chat_models = [m['name'].replace('models/', '') for m in data.get('models', []) 
                       if 'generateContent' in m.get('supportedGenerationMethods', [])]
        if not chat_models: return None, "未找到可用模型"
        best = chat_models[0]
        for m in chat_models:
            if "flash" in m: best = m; break
        return best, None
    except: return None, "网络连接错误"

def call_gemini(prompt, api_key, model_name, image_data=None):
    url = f"{BASE_URL}/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    parts = [{"text": prompt}]
    if image_data:
        parts.append({"inline_data": {"mime_type": image_data['mime_type'], "data": image_data['data']}})
    payload = {"contents": [{"parts": parts}]}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return True, response.json()['candidates'][0]['content']['parts'][0]['text']
        return False, f"API 报错: {response.status_code}"
    except Exception as e:
        return False, str(e)

# ==========================================
# 3. 界面逻辑
# ==========================================

if 'results' not in st.session_state:
    st.session_state.results = []
if 'working_model' not in st.session_state:
    st.session_state.working_model = None

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Xiaohongshu_logo.svg/1200px-Xiaohongshu_logo.svg.png", width=50)
    st.header("⚙️ 全局设置")
    api_key = st.text_input("输入 API Key", type="password")
    
    if api_key and not st.session_state.working_model:
        model, err = get_best_model(api_key)
        if model: st.session_state.working_model = model; st.success(f"已就绪: {model}")
        else: st.error(err)
    
    st.divider()
    st.subheader("🎨 标题风格设置")
    user_style_prompt = st.text_area("在此调整生成逻辑：", value=DEFAULT_STYLE_PROMPT, height=150)
    
    st.divider()
    uploaded_file = st.file_uploader("📂 上传素材 (Excel/图片)", type=['xlsx', 'csv', 'png', 'jpg', 'jpeg'])

# --- 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V28.0 逻辑透明版 | 新增分析思路列 | 全结构化输出")

col1, col2 = st.columns([1, 2.5])

with col1:
    st.subheader("📝 输入素材")
    txt_input = st.text_area("粘贴文案 (多篇请按空行分隔)", height=250)
    
    can_run = api_key and st.session_state.working_model
    
    if st.button("✨ 开始结构化分析", type="primary", use_container_width=True, disabled=not can_run):
        tasks = []
        if txt_input:
            for t in [x.strip() for x in txt_input.split('\n\n') if len(x.strip()) > 5]:
                tasks.append({'type': 'text', 'content': t, 'name': t[:10]})
        if uploaded_file:
            f_type = uploaded_file.name.split('.')[-1].lower()
            if f_type in ['xlsx', 'csv']:
                df_up = pd.read_csv(uploaded_file) if f_type == 'csv' else pd.read_excel(uploaded_file)
                for t in df_up.iloc[:, 0].dropna().astype(str).tolist():
                    tasks.append({'type': 'text', 'content': t, 'name': t[:10]})
            elif f_type in ['png', 'jpg', 'jpeg']:
                b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
                mime = f"image/{f_type.replace('jpg','jpeg')}"
                tasks.append({'type': 'image', 'content': {'mime_type': mime, 'data': b64}, 'name': f"图片:{uploaded_file.name}"})

        if not tasks: st.warning("未检测到有效输入"); st.stop()
            
        bar = st.progress(0); status = st.empty(); new_res = []
        
        for i, task in enumerate(tasks):
            status.markdown(f"🔄 **处理中 {i+1}/{len(tasks)}: {task['name']}**")
            
            # --- 核心 Prompt：增加分析思路项 ---
            if task['type'] == 'text':
                p_analyze = f"""
                分析文案: "{task['content'][:800]}"
                请拆解以下6项，严格用 '|||' 隔开，不要有任何多余文字：
                1. 原标题概括
                2. 人设特征
                3. 主选题方向
                4. 细分角度 (⚠️要求: 切入点极细)
                5. 爆款公式
                6. 分析思路 (⚠️说明: 解释为什么要选这个角度，抓住了什么用户痛点或情绪点，构思逻辑是什么)
                """
                img_d = None
            else:
                p_analyze = f"""
                观察图片，拆解以下6项，严格用 '|||' 隔开：
                1. 图片画面主题
                2. 推测博主人设
                3. 主选题方向
                4. 细分角度
                5. 建议使用的爆款公式
                6. 分析思路 (⚠️说明: 解释你从图中读出的关键信息以及标题构思逻辑)
                """
                img_d = task['content']

            ok1, res1 = call_gemini(p_analyze, api_key, st.session_state.working_model, img_d)
            
            if ok1 and "|||" in res1:
                pts = res1.replace('```', '').strip().split('|||')
                if len(pts) >= 6:
                    row = {
                        "来源": task['name'],
                        "原标题": pts[0].strip(),
                        "人设": pts[1].strip(),
                        "主选题": pts[2].strip(),
                        "细分角度": pts[3].strip(),
                        "分析思路": pts[5].strip(),
                        "生成标题": ""
                    }
                    # 第二步：生成标题
                    p_gen = f"""基于分析思路【{row['分析思路']}】、人设【{row['人设']}】和细分角度【{row['细分角度']}】，参考公式【{pts[4].strip()}】。
                    请生成标题：\n{user_style_prompt}"""
                    ok2, res2 = call_gemini(p_gen, api_key, st.session_state.working_model)
                    row["生成标题"] = res2 if ok2 else "生成失败"
                    new_res.append(row)
            bar.progress((i+1)/len(tasks))
            
        st.session_state.results = new_res + st.session_state.results
        status.success("🎉 分析完成！")

with col2:
    st.subheader(f"📊 逻辑透明分析资产库 ({len(st.session_state.results)})")
    if st.session_state.results:
        df_res = pd.DataFrame(st.session_state.results)
        
        # 网页显示配置
        st.dataframe(
            df_res,
            column_config={
                "生成标题": st.column_config.TextColumn("AI 爆款标题", width="large"),
                "分析思路": st.column_config.TextColumn("AI 分析思路", width="medium"),
                "细分角度": st.column_config.TextColumn("细分角度", width="medium"),
            },
            use_container_width=True, height=600
        )
        
        # Excel 导出配置 (增加分析思路列宽)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
            df_res.to_excel(wr, index=False, sheet_name='选题逻辑分析')
            bk = wr.book; ws = wr.sheets['选题逻辑分析']
            fmt = bk.add_format({'text_wrap': True, 'valign': 'top', 'border': 1})
            ws.set_column('A:A', 12, fmt) # 来源
            ws.set_column('B:B', 15, fmt) # 原标题
            ws.set_column('C:C', 12, fmt) # 人设
            ws.set_column('D:D', 15, fmt) # 主选题
            ws.set_column('E:E', 25, fmt) # 细分角度
            ws.set_column('F:F', 30, fmt) # 分析思路
            ws.set_column('G:G', 45, fmt) # 生成标题
            
        st.download_button("📥 下载带逻辑分析的 Excel", out.getvalue(), 
                           f"小红书选题库_V28_{int(time.time())}.xlsx", 
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                           use_container_width=True)
        if st.button("🗑️ 清空所有结果"): st.session_state.results = []; st.rerun()
