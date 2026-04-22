import gradio as gr
import os
import re
import tempfile
import zipfile
import shutil

def preview_renames(uploaded_files, rule_type, prefix_text, suffix_text, replace_old, replace_new, num_basename, num_start, ext_old, ext_new):
    if not uploaded_files:
        return [["提示 (Info)", "请先上传需要重命名的文件。"]], []
        
    preview_data = []
    # 存储临时路径和目标新文件名的映射关系
    # mapping: [(temp_path, new_basename), ...]
    rename_mapping = []

    # uploaded_files 是一个临时文件路径的列表
    for idx, temp_path in enumerate(uploaded_files):
        # Gradio 在保存临时文件时，通常会保留原始文件名在临时目录中
        filename = os.path.basename(temp_path)
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
                
        preview_data.append([filename, new_name])
        rename_mapping.append((temp_path, new_name))
            
    return preview_data, rename_mapping

def execute_renames(rename_mapping_state):
    """
    服务器执行重命名：
    无法直接覆盖用户的本地文件。因此我们需要：
    1. 在服务器上创建一个临时文件夹暂存重命名后的文件
    2. 将修改好的文件打包成 ZIP
    3. 提供给用户下载
    """
    if not rename_mapping_state:
        return "⚠️ 请先上传文件并点击「预览效果」。", None
        
    # 创建服务器临时工作区存放重新命名的文件
    output_dir = tempfile.mkdtemp(prefix="renamed_files_")
    
    success_count = 0
    error_count = 0
    
    for temp_path, new_name in rename_mapping_state:
        target_path = os.path.join(output_dir, new_name)
        
        # 复制文件到新目录并使用新名称
        try:
            shutil.copy2(temp_path, target_path)
            success_count += 1
        except Exception as e:
            error_count += 1

    if success_count == 0:
         return "❌ 处理失败，没有文件被成功打包。", None
         
    # 将文件打包为ZIP
    zip_filename = "Renamed_Files.zip"
    zip_filepath = os.path.join(tempfile.gettempdir(), zip_filename)
    
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # 写入 zip 时的短路径 (仅文件名)
                zipf.write(file_path, arcname=file)
                
    summary = f"🎉 处理完成！成功了 {success_count} 个文件。（准备下载打包文件）"
    
    # 返回提示语 以及 生成完毕的ZIP文件路径
    return summary, zip_filepath

def create_server_ui():
    with gr.Blocks(title="云端文件批量重命名工具", theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            "# ☁️ 云端批量文件重命名工具 (Server Edition)\n"
            "这是由于部署在服务器环境做出的适配版本。线上服务器无法直接读取或修改您电脑内磁盘（如 `E盘` 或 `D盘`）的本地文件。 **流程已调整为：上传文件 -> 在线预览配置 -> 处理打包 -> 下载 ZIP。**"
        )
        
        with gr.Row():
            # 这里是最大的区别：使用文件组件替代了之前的纯文本路径
            file_upload = gr.File(
                label="📁 上传本地需要重命名的文件 (支持多选)", 
                file_count="multiple",
                type="filepath" 
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
                with gr.Row():
                    preview_btn = gr.Button("🔍 1. 预览效果 (必做)", variant="secondary")
                    execute_btn = gr.Button("📦 2. 确认执行并打包下载", variant="primary")
                
                msg_output = gr.Textbox(label="操作状态", interactive=False)
                
            with gr.Column(scale=2):
                preview_table = gr.Dataframe(
                    label="📝 预览文件效果 (原文件名 -> 新文件名)", 
                    headers=["原文件名 (Original Name)", "新文件名 (New Name)"], 
                    interactive=False
                )
                
                # 处理完毕后，给用户提供一个供下载的组件
                output_file = gr.File(label="📥 批量处理完成，点击下载压缩包", interactive=False, visible=True)
                mapping_state = gr.State([])

        preview_btn.click(
            fn=preview_renames,
            inputs=[file_upload, rule_type, prefix_text, suffix_text, replace_old, replace_new, num_basename, num_start, ext_old, ext_new],
            outputs=[preview_table, mapping_state]
        )
        
        execute_btn.click(
            fn=execute_renames,
            inputs=[mapping_state],
            outputs=[msg_output, output_file]
        )

    return demo

if __name__ == "__main__":
    app = create_server_ui()
    # server_name="0.0.0.0" 允许外部网络访问
    app.launch(server_name="0.0.0.0", server_port=7860)
