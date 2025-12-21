# utils/file_parser.py
import os
import PyPDF2
from pptx import Presentation
import pandas as pd
from xmindparser import xmind_to_dict
from utils.logger import logger


class FileParser:
    """
    统一文件解析器
    负责将各种格式文件转换为纯文本
    """

    @classmethod
    def parse(cls, file_path: str) -> str:
        """统一解析入口"""
        if not os.path.exists(file_path):
            return ""

        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)
        content = ""

        try:
            if ext == '.pdf':
                content = cls._parse_pdf(file_path)
            elif ext == '.pptx':
                content = cls._parse_pptx(file_path)
            elif ext in ['.xlsx', '.xls']:
                content = cls._parse_excel(file_path)
            elif ext == '.xmind':
                content = cls._parse_xmind(file_path)
            elif ext in ['.txt', '.md', '.py', '.java', '.json', '.csv', '.xml', '.html', '.css', '.js', '.sql', '.sh']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            else:
                return f"[提示: 不支持解析 {ext} 格式的文件: {filename}]"

        except Exception as e:
            error_msg = f"文件解析失败 {filename}: {str(e)}"
            logger.error(error_msg)
            return f"[系统提示: {error_msg}]"

        if content:
            return f"\n\n=== 开始文件: {filename} ===\n{content}\n=== 结束文件 ===\n"
        return ""

    @staticmethod
    def _parse_pdf(path):
        text = ""
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n[Page {i + 1}]\n{page_text}"
        return text

    @staticmethod
    def _parse_pptx(path):
        text = ""
        prs = Presentation(path)
        for i, slide in enumerate(prs.slides):
            slide_text = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    slide_text.append(shape.text)
            if slide_text:
                text += f"\n[Slide {i + 1}]\n" + "\n".join(slide_text)
        return text

    @staticmethod
    def _parse_excel(path):
        text = ""
        # 读取所有 sheet
        dfs = pd.read_excel(path, sheet_name=None)
        for sheet_name, df in dfs.items():
            text += f"\n\n### Sheet: {sheet_name}\n"
            # 转换为 Markdown 表格
            text += df.to_markdown(index=False)
        return text

    @staticmethod
    def _parse_xmind(path):
        text = ""
        sheets = xmind_to_dict(path)
        for sheet in sheets:
            root_topic = sheet.get('topic', {})
            text += f"\n\n### 画布: {sheet.get('title', '未命名')}\n"
            text += FileParser._xmind_recursion(root_topic)
        return text

    @staticmethod
    def _xmind_recursion(data, level=0):
        """递归解析 XMind"""
        indent = "  " * level
        title = data.get('title', '无标题')
        result = f"{indent}- {title}\n"
        for topic in data.get('topics', []):
            result += FileParser._xmind_recursion(topic, level + 1)
        return result