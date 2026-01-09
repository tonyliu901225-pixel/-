import streamlit as st
import requests
import socket
import os

st.set_page_config(page_title="API 流程终极诊断器", page_icon="🕵️", layout="wide")

st.title("🕵️ API 调用流程：全链路体检")
st.info("此程序不生成文案，专门用于找出报错的根本原因。")

# --- 输入区 ---
st.markdown("### 1. 准备工作")
api_key = st.text_input("请输入您的 API Key (AIza 开头)", type="password")
start_btn = st.button("🚀 开始全链路诊断", type="primary")

if start_btn:
    st.divider()
    
    # ==========================================
    # 环节 A: 环境与网络自检
    # ==========================================
    st.header("环节 A: 环境与网络自检")
    
    # 1. 查环境
    try:
        # Streamlit Cloud 并没有固定的 IP，但我们可以通过 hostname 猜测
        hostname = socket.gethostname()
        st.write(f"🔹 **当前运行环境主机名:** `{hostname}`")
        
        if "localhost" in hostname or "0.0.0.0" in os.environ.get("HOST", ""):
            st.warning("⚠️ 警告: 看起来像是在本地环境。如果您没开 VPN，下面的网络测试可能会失败。")
        else:
            st.success("✅ 检测到云端环境 (Streamlit Cloud)，网络应当畅通。")
    except:
        st.write("🔹 环境检测跳过")

    # 2. 查网络 (Ping Google)
    st.write("🔹 **正在尝试连接 Google 核心服务...**")
    try:
        # 尝试连接 Google 的发现服务，这是一个极轻量的请求
        # 注意：这里不带 Key，单纯测网络通不通
        test_url = "https://generativelanguage.googleapis.com"
        resp = requests.get(test_url, timeout=5)
        
        if resp.status_code == 404: 
            # 404 是正常的，因为我们没指定具体页面，但说明服务器由 Google 回复了
            st.success(f"✅ 网络通畅！成功连接到 {test_url}")
        else:
            st.info(f"✅ 网络连通 (状态码 {resp.status_code})")
            
    except Exception as e:
        st.error(f"❌ 网络极其异常！无法连接 Google。")
        st.code(str(e))
        st.stop() # 网络不通，后面不用测了

    # ==========================================
    # 环节 B: 钥匙 (Key) 权限验证
    # ==========================================
    st.divider()
    st.header("环节 B: 钥匙 (Key) 权限验证")
    
    if not api_key:
        st.error("❌ 您没有输入 Key，无法测试此环节。")
        st.stop()

    st.write("🔹 **正在询问 Google: '这把钥匙能开哪些门？'**")
    
    # 我们调用 listModels 接口。这个接口最能反映 Key 的真实权限。
    # 它可以区分出：是 Key 坏了？还是 Key 没权限？还是 Key 类型不对？
    models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    try:
        resp = requests.get(models_url, timeout=10)
        
        # --- 诊断逻辑核心 ---
        if resp.status_code == 200:
            st.success("✅ **完美！Key 有效且权限正确！**")
            data = resp.json()
            models = [m['name'].replace('models/', '') for m in data.get('models', [])]
            st.write(f"📜 Google 返回了 {len(models)} 个可用模型：")
            st.code(models)
            
            # 检查是否有 flash
            if "gemini-1.5-flash" in models:
                st.success("🎉 确认：您的 Key 支持 `gemini-1.5-flash`！")
            else:
                st.warning("⚠️ 注意：您的 Key 有效，但列表里没有 `gemini-1.5-flash`。可能需要用 `gemini-pro`。")

        elif resp.status_code == 400:
            st.error("❌ **Key 格式错误 (HTTP 400)**")
            st.write("原因：Key 可能复制错了，或者包含空格。")
            st.write(f"Google 反馈: `{resp.text}`")

        elif resp.status_code == 403:
            st.error("❌ **权限不足 (HTTP 403)**")
            st.write("原因：Key 是对的，但被 Google 拦截了。")
            st.write("可能性 1：您的 Google Cloud 项目没有开启 'Generative Language API'。")
            st.write("可能性 2：这把 Key 设置了 IP 限制。")
            st.write(f"Google 反馈: `{resp.text}`")

        elif resp.status_code == 404:
            st.error("❌ **服务未找到 (HTTP 404)**")
            st.write("这是最常见的问题！")
            st.write("🔴 **极大概率原因：您拿的是 Vertex AI (企业版) 的 Key，却用在了 AI Studio (个人版) 的代码里。**")
            st.write("Vertex AI 的 Key 无法识别 `generativelanguage.googleapis.com` 这个地址。")
            st.write("👉 解决办法：请务必去 'REd book' 项目里，找那个带有 ✅ 的 Key。")

        else:
            st.error(f"❌ 未知错误 (HTTP {resp.status_code})")
            st.code(resp.text)

    except Exception as e:
        st.error(f"验证 Key 时发生异常: {e}")

    # ==========================================
    # 环节 C: 最终实战模拟
    # ==========================================
    if resp.status_code == 200: # 只有 Key 验证通过才测这一步
        st.divider()
        st.header("环节 C: 实战模拟生成")
        st.write("🔹 **尝试发送 'Hello' 给 AI...**")
        
        # 强制使用刚才获取到的第一个模型，确保不报 404
        target_model = models[0] if models else "gemini-1.5-flash"
        st.info(f"使用模型: {target_model}")
        
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": "Hello"}]}]}
        
        try:
            r = requests.post(gen_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
            if r.status_code == 200:
                st.balloons()
                st.success(f"🎉🎉🎉 **测试通过！AI 回复了：**")
                st.write(r.json()['candidates'][0]['content']['parts'][0]['text'])
                st.markdown("---")
                st.markdown("### ✅ 结论：现在的环境和 Key 都是 100% 没问题的！")
                st.markdown("您可以放心地把代码改回业务版了。")
            else:
                st.error(f"生成失败: {r.text}")
        except Exception as e:
            st.error(f"实战模拟出错: {e}")
