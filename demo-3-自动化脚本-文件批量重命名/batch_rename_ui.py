"""
批量打包重命名工具 (Batch Rename Tool)
基于 Gradio 构建的 Web UI 版重命名工具，支持预览重命名结果，操作更简单安全。
"""

import gradio as gr
import os
import re

def preview_renames(dir_path, rule_type, prefix_text, suffix_text, replace_old, replace_new, num_basename, num_start, ext_old, ext_new):
    if not dir_path or not os.path.exists(dir_path) or not os.path.isdir(dir_path):
        return [["错误 (Error)", "无效的目录路径，请检查路径是否正确。"]], []
        
    files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
    if not files:
        return [["提示 (Info)", "目录中没有文件。"]], []
        
    preview_data = []
    rename_mapping = []

    # 过滤掉隐藏文件 (安全起见，通常不批量重命名系统隐藏文件)
    files = [f for f in files if not f.startswith('.')]

    for idx, filename in enumerate(sorted(files)):
        name, ext = os.path.splitext(filename)
        new_name = filename
        
        if rule_type == "添加前缀 (Add Prefix)":
            new_name = f"{prefix_text}{filename}"
        elif rule_type == "添加后缀 (Add Suffix)":
            new_name = f"{name}{suffix_text}{ext}"
        elif rule_type == "替换文本 (Replace Text)":
            new_name = filename.replace(replace_old, replace_new) if replace_old else filename
        elif rule_type == "序号命名 (Numbering)":
            try:
                start = int(num_start)
            except ValueError:
                start = 1
            new_name = f"{num_basename}_{start + idx}{ext}"
        elif rule_type == "修改扩展名 (Change Extension)":
            # 统一处理扩展名包含 "." 的情况
            clean_ext_new = ext_new if ext_new.startswith('.') else f".{ext_new}" if ext_new else ""
            clean_ext_old = ext_old if ext_old.startswith('.') else f".{ext_old}" if ext_old else ""
            
            if not ext_old or ext.lower() == clean_ext_old.lower():
                new_name = f"{name}{clean_ext_new}"
        elif rule_type == "全小写 (Lowercase)":
            new_name = name.lower() + ext.lower()
        elif rule_type == "全大写 (Uppercase)":
            new_name = name.upper() + ext.lower()
        elif rule_type == "正则替换 (Regex Replace)":
            if not replace_old:
                new_name = filename
            else:
                try:
                    new_name = re.sub(replace_old, replace_new, filename)
                except Exception as e:
                    return [[f"正则错误 (Regex Error)", str(e)]], []
                
        if new_name != filename:
            preview_data.append([filename, new_name])
            rename_mapping.append((filename, new_name))
            
    if not preview_data:
        return [["提示 (Info)", "按照当前规则，没有需要重命名的文件。"]], []
        
    return preview_data, rename_mapping


def execute_renames(dir_path, rename_mapping_state):
    if not rename_mapping_state:
        return "⚠️ 没有需要重命名的文件，请先点击「预览效果」。", []
        
    if not dir_path or not os.path.exists(dir_path):
        return "❌ 无效的目录路径。", []

    results = []
    success_count = 0
    error_count = 0
    
    for old_name, new_name in rename_mapping_state:
        old_path = os.path.join(dir_path, old_name)
        new_path = os.path.join(dir_path, new_name)
        
        # 防止覆盖已有文件（除非是仅大小写变化，如Windows环境特例）
        if os.path.exists(new_path) and new_name.lower() != old_name.lower():
            results.append([old_name, "失败 (Failed) - 目标文件已存在，为防止覆盖已跳过"])
            error_count += 1
            continue
            
        try:
            os.rename(old_path, new_path)
            results.append([old_name, f"✅ 成功 -> {new_name}"])
            success_count += 1
        except Exception as e:
            results.append([old_name, f"❌ 失败: {str(e)}"])
            error_count += 1
            
    summary = f"🎉 执行完成！成功: {success_count} 个, 失败: {error_count} 个"
    
    # 执行完毕后清空状态，防止重复执行
    return summary, results


def create_ui():
    with gr.Blocks(title="文件批量重命名工具", theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            "# 📁 批量文件重命名工具\n"
            "为您提供简单易用的文件批量重命名功能，支持**多种自定义规则**。由于批量重命名不可逆，工具强制使用**先预览、后执行**的流程，确保操作安全。"
        )
        
        with gr.Row():
            dir_input = gr.Textbox(
                label="📁 输入文件夹绝对路径 (在此处填入需要处理的文件夹路径)", 
                placeholder="例如: E:\\CreativeProject\\DelvelopProject\\Python\\python-word\\downloads-images", 
                scale=4
            )
        
        with gr.Row():
            with gr.Column(scale=1):
                rule_type = gr.Radio(
                    choices=[
                        "添加前缀 (Add Prefix)", 
                        "添加后缀 (Add Suffix)", 
                        "替换文本 (Replace Text)", 
                        "序号命名 (Numbering)", 
                        "修改扩展名 (Change Extension)", 
                        "全小写 (Lowercase)", 
                        "全大写 (Uppercase)", 
                        "正则替换 (Regex Replace)"
                    ],
                    label="⚙️ 选择重命名规则",
                    value="添加前缀 (Add Prefix)"
                )
                
                # 不同规则对应的输入组件（动态显示/隐藏）
                prefix_text = gr.Textbox(label="前缀内容", value="前缀_", visible=True)
                suffix_text = gr.Textbox(label="后缀内容", value="_后缀", visible=False)
                
                replace_old = gr.Textbox(label="原文本/正则表达式", placeholder="要替换的文本", visible=False)
                replace_new = gr.Textbox(label="新文本", placeholder="替换后的文本", visible=False)
                
                num_basename = gr.Textbox(label="文件名前缀", value="file", visible=False)
                num_start = gr.Number(label="起始序号", value=1, precision=0, visible=False)
                
                ext_old = gr.Textbox(label="原扩展名 (留空代表全部)", placeholder="例如: .jpeg", visible=False)
                ext_new = gr.Textbox(label="新扩展名", placeholder="例如: .jpg", visible=False)
                
                def update_ui_visibility(choice):
                    return {
                        prefix_text: gr.update(visible=choice == "添加前缀 (Add Prefix)"),
                        suffix_text: gr.update(visible=choice == "添加后缀 (Add Suffix)"),
                        replace_old: gr.update(visible=choice in ["替换文本 (Replace Text)", "正则替换 (Regex Replace)"]),
                        replace_new: gr.update(visible=choice in ["替换文本 (Replace Text)", "正则替换 (Regex Replace)"]),
                        num_basename: gr.update(visible=choice == "序号命名 (Numbering)"),
                        num_start: gr.update(visible=choice == "序号命名 (Numbering)"),
                        ext_old: gr.update(visible=choice == "修改扩展名 (Change Extension)"),
                        ext_new: gr.update(visible=choice == "修改扩展名 (Change Extension)"),
                    }
                
                rule_type.change(
                    fn=update_ui_visibility, 
                    inputs=[rule_type], 
                    outputs=[prefix_text, suffix_text, replace_old, replace_new, num_basename, num_start, ext_old, ext_new]
                )
                
                gr.Markdown("---")
                # 操作按钮
                with gr.Row():
                    preview_btn = gr.Button("🔍 1. 预览效果 (必做)", variant="secondary")
                    execute_btn = gr.Button("🚀 2. 确认执行", variant="primary")
                
                msg_output = gr.Textbox(label="操作状态", interactive=False)
                
            with gr.Column(scale=2):
                preview_table = gr.Dataframe(
                    label="📝 预览效果 / 执行状态与结果", 
                    headers=["原文件名 (Original Name)", "新文件名 (New Name)"], 
                    interactive=False
                )
                # 隐藏状态存储
                mapping_state = gr.State([])

        preview_btn.click(
            fn=preview_renames,
            inputs=[dir_input, rule_type, prefix_text, suffix_text, replace_old, replace_new, num_basename, num_start, ext_old, ext_new],
            outputs=[preview_table, mapping_state]
        )
        
        execute_btn.click(
            fn=execute_renames,
            inputs=[dir_input, mapping_state],
            outputs=[msg_output, preview_table]
        )

    return demo

if __name__ == "__main__":
    app = create_ui()
    # 启动 Gradio 服务，自动在浏览器中打开
    app.launch(inbrowser=True)
