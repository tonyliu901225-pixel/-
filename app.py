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
    page_title="小红书 AI 选题中台 (V29 极简高阶版)",
    page_icon="🍒",
    layout="wide"
)

BASE_URL = "https://generativelanguage.googleapis.com"

# 默认标题风格
DEFAULT_STYLE = """
1. 20字以内。
2. 分5行，无序号。
3. 口语化，多用emoji，职场商务风。
"""

# ==========================================
# 2. 工具函数
# ==========================================

def clean_text(text):
    """移除 AI 返回中常见的序号、前缀标签"""
    if not text: return ""
    # 匹配模式：数字+.+空格 或 类似 "1. 原标题：" 的前缀
    pattern = r'^(\d+[\.\、\s]*|原标题[:：\s]*|人设[:：\s]*|主选题[:：\s]*|细分角度[:：\s]*|分析思路[:：\s]*|爆款公式[:：\s]*|主选题方向[:：\s]*)'
    # 先处理 markdown 粗体
    text = text.replace('**', '')
    # 循环清理多行前缀
    lines = []
    for line in text.strip().split('\n'):
        line = re.sub(pattern, '', line.strip())
        if line: lines.append(line)
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
    
    st.subheader("🎨 生成风格")
    user_style = st.text_area("提示词预设", value=DEFAULT_STYLE, height=120)
    
    uploaded_file = st.file_uploader("📂 素材上传", type=['xlsx', 'csv', 'png', 'jpg', 'jpeg'])

st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V29.0 极简高阶版 | 已自动剔除标签前缀 | 支持图片识别")

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
            
            # --- 阶段 1：深度拆解 (强制要求无标签输出) ---
            p_analyze = f"""
            分析素材: "{task['content'] if task['type']=='text' else '图片'}"
            请提取以下6项，严格用 '|||' 隔开。注意：不要输出'1.'或'原标题:'这类前缀标签，直接给内容：
            原标题 ||| 人设 ||| 主选题 ||| 细分角度 ||| 标题公式 ||| 分析思路
            """
            
            ok1, res1 = call_gemini(p_analyze, api_key, st.session_state.working_model, task['content'] if task['type']=='image' else None)
            
            if ok1 and "|||" in res1:
                pts = res1.split("|||")
                if len(pts) >= 6:
                    row = {
                        "来源": task['name'],
                        "原标题": clean_text(pts[0]),
                        "人设": clean_text(pts[1]),
                        "主选题": clean_text(pts[2]),
                        "细分角度": clean_text(pts[3]),
                        "分析思路": clean_text(pts[5]),
                    }
                    # --- 阶段 2：生成 ---
                    p_gen = f"基于人设【{row['人设']}】和细分角度【{row['细分角度']}】，参考思路【{row['分析思路']}】。\n生成标题要求：\n{user_style}"
                    ok2, res2 = call_gemini(p_gen, api_key, st.session_state.working_model)
                    row["AI 爆款标题"] = clean_text(res2) if ok2 else "生成失败"
                    new_res.append(row)
            
            bar.progress((i+1)/len(tasks))
            
        st.session_state.results = new_res + st.session_state.results
        status.success("🎉 完成")

with col_out:
    if st.session_state.results:
        df_res = pd.DataFrame(st.session_state.results)
        
        st.dataframe(
            df_res,
            column_config={
                "AI 爆款标题": st.column_config.TextColumn("AI 爆款标题 (5行)", width="large"),
                "分析思路": st.column_config.TextColumn("分析思路", width="medium"),
                "细分角度": st.column_config.TextColumn("细分切入点", width="medium"),
            },
            use_container_width=True, height=600
        )
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
            df_res.to_excel(wr, index=False, sheet_name='选题库')
            bk = wr.book; ws = wr.sheets['选题库']
            fmt = bk.add_format({'text_wrap': True, 'valign': 'top', 'border': 1})
            widths = [12, 25, 12, 15, 25, 30, 50]
            for i, w in enumerate(widths): ws.set_column(i, i, w, fmt)
            
        st.download_button("📥 下载选题库 Excel", out.getvalue(), f"XHS_选题_{int(time.time())}.xlsx", use_container_width=True)
        if st.button("🗑️ 清空结果"): st.session_state.results = []; st.rerun()
