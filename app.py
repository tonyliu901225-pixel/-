import streamlit as st
import requests
import pandas as pd
import io
import time
import base64
import re

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(
    page_title="小红书 AI 选题中台 (V30 极简标签版)",
    page_icon="🍒",
    layout="wide"
)

BASE_URL = "https://generativelanguage.googleapis.com"

# 默认风格 (强调发散性)
DEFAULT_STYLE = """
1. 5个标题要求风格迥异 (如: 悬念感、强痛点、高情绪、干货感)。
2. 拒绝死板，拒绝翻译腔。
3. 分5行展示，无序号。
"""

# ==========================================
# 2. 工具函数
# ==========================================

def clean_text(text):
    """超级清洗：移除所有序号、前缀、标点，只留核心词"""
    if not text: return ""
    # 移除常见的 Label 前缀 (如 "人设：", "1. ")
    pattern = r'^(\d+[\.\、\s]*|原标题[:：\s]*|人设[:：\s]*|细分选题[:：\s]*|爆款元素[:：\s]*|标题公式[:：\s]*|主选题[:：\s]*)'
    
    lines = []
    for line in text.strip().split('\n'):
        # 去掉 Markdown 粗体
        cleaned = line.replace('**', '').strip()
        # 去掉前缀
        cleaned = re.sub(pattern, '', cleaned)
        # 如果是"爆款元素"这种，去掉句号
        cleaned = cleaned.rstrip('。')
        if cleaned: lines.append(cleaned)
    return "\n".join(lines)

def get_best_model(api_key):
    url = f"{BASE_URL}/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200: return None, "Key 验证失败"
        data = resp.json()
        chat_models = [m['name'].replace('models/', '') for m in data.get('models', []) 
                       if 'generateContent' in m.get('supportedGenerationMethods', [])]
        best = next((m for m in chat_models if "flash" in m), chat_models[0] if chat_models else None)
        return best, None
    except: return None, "网络异常"

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
        return False, response.text
    except Exception as e:
        return False, str(e)

# ==========================================
# 3. 界面逻辑
# ==========================================

if 'results' not in st.session_state: st.session_state.results = []
if 'working_model' not in st.session_state: st.session_state.working_model = None

with st.sidebar:
    st.header("⚙️ 控制台")
    api_key = st.text_input("API Key", type="password")
    
    if api_key and not st.session_state.working_model:
        model, err = get_best_model(api_key)
        if model: st.session_state.working_model = model; st.success(f"已锁定: {model}")
    
    st.subheader("🎨 发散度设置")
    user_style = st.text_area("生成要求", value=DEFAULT_STYLE, height=120)
    
    uploaded_file = st.file_uploader("📂 素材上传", type=['xlsx', 'csv', 'png', 'jpg', 'jpeg'])

st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V30.0 极简标签版 | 仿参考图格式 | 标题创意发散")

col_in, col_out = st.columns([1, 3])

with col_in:
    txt_input = st.text_area("在此粘贴素材", height=300, placeholder="多篇文案请空行分隔...")
    
    if st.button("✨ 执行极简分析", type="primary", use_container_width=True, disabled=not api_key):
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
            else:
                b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
                tasks.append({'type': 'image', 'content': {'mime_type': f"image/{f_type.replace('jpg','jpeg')}", 'data': b64}, 'name': f"图片:{uploaded_file.name}"})

        if not tasks: st.warning("未检测到输入"); st.stop()
            
        bar = st.progress(0); status = st.empty(); new_res = []
        
        for i, task in enumerate(tasks):
            status.markdown(f"🔄 **分析中 {i+1}/{len(tasks)}**")
            
            # --- 阶段 1：标签化拆解 (核心修改) ---
            # 移除了分析思路，增加了"爆款元素"和"标题公式"，要求极简输出
            p_analyze = f"""
            分析素材: "{task['content'] if task['type']=='text' else '图片'}"
            请提取以下5项，严格用 '|||' 隔开。
            ⚠️ 重点要求：输出必须【简明扼要】，像打标签一样，不要长句子！
            
            1. 原标题 (仅保留核心意思，10字内)
            2. 人设 (如: 销售老徐)
            3. 细分选题 (如: 订阅式送礼策略)
            4. 爆款元素 (如: 反常识+痛点+焦虑)
            5. 标题公式 (如: 痛点+反常识+方案)
            """
            
            ok1, res1 = call_gemini(p_analyze, api_key, st.session_state.working_model, task['content'] if task['type']=='image' else None)
            
            if ok1 and "|||" in res1:
                pts = res1.split("|||")
                if len(pts) >= 5:
                    row = {
                        "来源": task['name'],
                        "原标题": clean_text(pts[0]),
                        "人设": clean_text(pts[1]),
                        "细分选题": clean_text(pts[2]),
                        "爆款元素": clean_text(pts[3]),
                        "标题公式": clean_text(pts[4]),
                    }
                    # --- 阶段 2：发散性生成 ---
                    # 重点修改：要求"发散"，不让 AI 死板
                    p_gen = f"""
                    你是一个顶尖的小红书爆款标题专家。
                    基于【{row['细分选题']}】，利用元素【{row['爆款元素']}】。
                    
                    👉 请大开脑洞，创作 5 个标题。
                    ⚠️ 核心要求：
                    1. **拒绝同质化**：5个标题必须完全不同（有的设置悬念，有的直接给干货，有的引发焦虑）。
                    2. **发散思维**：不要只盯着一个点，尝试不同切入。
                    3. 格式：分5行，无序号。
                    {user_style}
                    """
                    ok2, res2 = call_gemini(p_gen, api_key, st.session_state.working_model)
                    row["AI 爆款标题"] = clean_text(res2) if ok2 else "生成失败"
                    new_res.append(row)
            
            bar.progress((i+1)/len(tasks))
            
        st.session_state.results = new_res + st.session_state.results
        status.success("🎉 完成")

with col_out:
    if st.session_state.results:
        df_res = pd.DataFrame(st.session_state.results)
        
        # 网页显示配置 (对标参考图)
        st.dataframe(
            df_res,
            column_config={
                "AI 爆款标题": st.column_config.TextColumn("AI 爆款标题 (5个发散方向)", width="large"),
                "细分选题": st.column_config.TextColumn("细分选题", width="medium"),
                "爆款元素": st.column_config.TextColumn("爆款元素", width="small"),
                "标题公式": st.column_config.TextColumn("标题公式", width="small"),
                "人设": st.column_config.TextColumn("人设", width="small"),
            },
            use_container_width=True, height=600
        )
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
            df_res.to_excel(wr, index=False, sheet_name='选题库')
            bk = wr.book; ws = wr.sheets['选题库']
            fmt = bk.add_format({'text_wrap': True, 'valign': 'top', 'border': 1})
            # 调整列宽适配 Excel
            ws.set_column('A:A', 10, fmt) # 来源
            ws.set_column('B:B', 20, fmt) # 原标题
            ws.set_column('C:C', 10, fmt) # 人设
            ws.set_column('D:D', 20, fmt) # 细分选题
            ws.set_column('E:E', 25, fmt) # 爆款元素
            ws.set_column('F:F', 25, fmt) # 标题公式
            ws.set_column('G:G', 50, fmt) # 生成标题
            
        st.download_button("📥 下载极简选题库 Excel", out.getvalue(), f"XHS_极简_{int(time.time())}.xlsx", use_container_width=True)
        if st.button("🗑️ 清空结果"): st.session_state.results = []; st.rerun()
