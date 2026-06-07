# -*- coding: utf-8 -*-
"""
练字字帖生成器 - 独立 Web 版
包含所有核心功能，无需额外脚本文件
"""
import os
import re
import math
import tempfile
import shutil
import threading
import webbrowser
import importlib.util
from flask import Flask, request, send_file, render_template_string
from PIL import Image, ImageDraw, ImageFont

# ========================== 虚线绘制工具 ==========================
def draw_dashed_line(draw, start, end, fill, dash_length=6, gap_length=4):
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux = dx / length
    uy = dy / length
    cur_x, cur_y = x1, y1
    t = 0
    while t + dash_length <= length:
        end_x = cur_x + ux * dash_length
        end_y = cur_y + uy * dash_length
        draw.line((cur_x, cur_y, end_x, end_y), fill=fill, width=1)
        cur_x = end_x + ux * gap_length
        cur_y = end_y + uy * gap_length
        t += dash_length + gap_length
    if t < length:
        draw.line((cur_x, cur_y, x2, y2), fill=fill, width=1)

# ========================== 配置类 ==========================
class CalligraphyConfig:
    def __init__(self,
                 char_list=None,
                 gray_level=None,
                 gray_factor=0.5,
                 cols_per_row=11,
                 page_size='A4',
                 dpi=300,
                 margin_mm=12,
                 title="幼小衔接练字",
                 font_path=None,
                 border_color=(70, 175, 70),
                 dash_color=(190, 190, 190),
                 cell_spacing=0,
                 line_spacing=0,
                 char_font_ratio=0.7):
        
        self.char_list = char_list or []
        self.gray_level = gray_level
        self.gray_factor = gray_factor
        self.cols_per_row = cols_per_row
        self.page_size = page_size
        self.dpi = dpi
        self.margin_mm = margin_mm
        self.title = title
        self.font_path = font_path
        self.border_color = border_color
        self.dash_color = dash_color
        self.cell_spacing = cell_spacing
        self.line_spacing = line_spacing
        self.char_font_ratio = char_font_ratio

        if page_size == 'A4':
            self.width_px = int(8.27 * dpi)
            self.height_px = int(11.69 * dpi)
        else:
            w_mm, h_mm = page_size
            self.width_px = int(w_mm / 25.4 * dpi)
            self.height_px = int(h_mm / 25.4 * dpi)
        
        self.margin_px = int(self.margin_mm / 25.4 * dpi)

# ========================== 字帖生成器 ==========================
class CalligraphyGenerator:
    def __init__(self, config):
        self.config = config
        self._validate_input()
        self._load_fonts()
        self._determine_gray_color()
        self._compute_cell_size()

    def _validate_input(self):
        chars = []
        for item in self.config.char_list:
            s = str(item).strip()
            if s:
                chars.append(s[0])
        if not chars:
            raise ValueError("char_list 为空或无有效汉字")
        self.chars = chars
        self.total_chars = len(chars)

    def _load_fonts(self):
        font_path = self.config.font_path
        if font_path is None:
            possible_fonts = [
                "C:/Windows/Fonts/simkai.ttf",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/msyh.ttc",
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
            ]
            for f in possible_fonts:
                if os.path.exists(f):
                    font_path = f
                    break
            else:
                font_path = None
        self.font_path = font_path

    def _determine_gray_color(self):
        if self.config.gray_level is not None:
            g = max(0, min(255, self.config.gray_level))
        else:
            g = int(255 * (1 - self.config.gray_factor))
            g = max(0, min(255, g))
        self.gray_color = (g, g, g)

    def _compute_cell_size(self):
        usable_width = self.config.width_px - 2 * self.config.margin_px
        cols = self.config.cols_per_row
        spacing = self.config.cell_spacing
        if spacing == 0:
            cell_size = usable_width // cols
        else:
            total_spacing = (cols - 1) * spacing
            cell_size = (usable_width - total_spacing) // cols
        if cell_size < 40:
            cell_size = 40
        self.cell_size = cell_size
        self.half_cell = cell_size // 2

    def _compute_rows_per_page(self):
        margin = self.config.margin_px
        title_height = self._get_title_height() if self.config.title else 0
        usable_height = self.config.height_px - 2 * margin - title_height
        
        if self.config.line_spacing == 0:
            rows_per_page = usable_height // self.cell_size
        else:
            max_rows = 0
            while True:
                h = (max_rows + 1) * self.cell_size + max_rows * self.config.line_spacing
                if h <= usable_height:
                    max_rows += 1
                else:
                    break
            rows_per_page = max_rows
        return max(1, rows_per_page)

    def _get_title_height(self):
        if not self.config.title:
            return 0
        temp_img = Image.new('RGB', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        try:
            font_title = ImageFont.truetype(self.font_path, 48) if self.font_path else ImageFont.load_default()
        except:
            font_title = ImageFont.load_default()
        bbox = temp_draw.textbbox((0, 0), self.config.title, font=font_title)
        text_height = bbox[3] - bbox[1]
        return text_height + 40

    def _draw_grid(self, draw, x1, y1, x2, y2):
        draw.rectangle([x1, y1, x2, y2], outline=self.config.border_color, width=1)
        mid_y = (y1 + y2) / 2
        draw_dashed_line(draw, (x1, mid_y), (x2, mid_y), fill=self.config.dash_color, dash_length=6, gap_length=4)
        mid_x = (x1 + x2) / 2
        draw_dashed_line(draw, (mid_x, y1), (mid_x, y2), fill=self.config.dash_color, dash_length=6, gap_length=4)
        draw_dashed_line(draw, (x1, y1), (x2, y2), fill=self.config.dash_color, dash_length=6, gap_length=4)
        draw_dashed_line(draw, (x2, y1), (x1, y2), fill=self.config.dash_color, dash_length=6, gap_length=4)

    def _draw_text_centered(self, draw, x1, y1, x2, y2, text, font, fill_color):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        draw.text((cx, cy), text, font=font, fill=fill_color, anchor="mm")

    def _create_page_image(self, page_chars):
        img = Image.new("RGB", (self.config.width_px, self.config.height_px), "white")
        draw = ImageDraw.Draw(img)

        char_font_size = int(self.cell_size * self.config.char_font_ratio)
        title_font_size = int(char_font_size * 0.8)

        try:
            font_char = ImageFont.truetype(self.font_path, char_font_size) if self.font_path else ImageFont.load_default()
            font_title = ImageFont.truetype(self.font_path, title_font_size) if self.font_path else ImageFont.load_default()
        except:
            font_char = ImageFont.load_default()
            font_title = ImageFont.load_default()

        margin = self.config.margin_px
        if self.config.title:
            title_bbox = draw.textbbox((0, 0), self.config.title, font=font_title)
            title_w = title_bbox[2] - title_bbox[0]
            title_x = (self.config.width_px - title_w) / 2
            title_y = margin // 2
            draw.text((title_x, title_y), self.config.title, font=font_title, fill=(0, 0, 0))
            title_height = title_y + (title_bbox[3] - title_bbox[1]) + 20
        else:
            title_height = 0

        start_y = margin + title_height
        black = (0, 0, 0)

        for idx, ch in enumerate(page_chars):
            row_top = start_y + idx * (self.cell_size + self.config.line_spacing) * 2
            line1_y = row_top
            line2_y = row_top + self.cell_size

            for col in range(self.config.cols_per_row):
                x_left = margin + col * (self.cell_size + self.config.cell_spacing)
                x_right = x_left + self.cell_size
                y1 = line1_y
                y2 = line1_y + self.cell_size
                self._draw_grid(draw, x_left, y1, x_right, y2)
                if col == 0:
                    self._draw_text_centered(draw, x_left, y1, x_right, y2, ch, font_char, black)
                else:
                    self._draw_text_centered(draw, x_left, y1, x_right, y2, ch, font_char, self.gray_color)

            for col in range(self.config.cols_per_row):
                x_left = margin + col * (self.cell_size + self.config.cell_spacing)
                x_right = x_left + self.cell_size
                y1 = line2_y
                y2 = line2_y + self.cell_size
                self._draw_grid(draw, x_left, y1, x_right, y2)

        return img

    def generate_pdf(self, output_pdf_path=None):
        if output_pdf_path is None:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            output_pdf_path = os.path.join(desktop, "练字字帖.pdf")

        rows_per_page = self._compute_rows_per_page()
        chars_per_page = rows_per_page // 2
        if chars_per_page == 0:
            raise RuntimeError("页面高度不足以放下一个完整的字（两行），请减小边距或增大页面尺寸")

        pages = []
        for i in range(0, self.total_chars, chars_per_page):
            page_chars = self.chars[i:i+chars_per_page]
            pages.append(page_chars)

        if not pages:
            raise RuntimeError("没有生成任何页面")

        images = []
        for idx, page_chars in enumerate(pages, start=1):
            img = self._create_page_image(page_chars)
            images.append(img)
            print(f"生成第 {idx} 页，包含 {len(page_chars)} 个汉字")

        if len(images) == 1:
            images[0].save(output_pdf_path, save_all=True, dpi=(self.config.dpi, self.config.dpi))
        else:
            images[0].save(output_pdf_path, save_all=True, append_images=images[1:], dpi=(self.config.dpi, self.config.dpi))

        print(f"字帖 PDF 已保存至: {output_pdf_path}")
        return output_pdf_path

    # ---------- 文章字帖 ----------
    def _split_article_into_lines(self, article_text):
        max_cols = self.config.cols_per_row
        lines = []
        current_line_chars = []
        for ch in article_text:
            if ch == '\n':
                if current_line_chars:
                    lines.append(current_line_chars)
                    current_line_chars = []
            elif ch == '\r':
                continue
            else:
                current_line_chars.append(ch)
                if len(current_line_chars) >= max_cols:
                    lines.append(current_line_chars)
                    current_line_chars = []
        if current_line_chars:
            lines.append(current_line_chars)
        return lines

    def _compute_text_rows_per_page(self):
        margin = self.config.margin_px
        title_height = self._get_title_height() if self.config.title else 0
        usable_height = self.config.height_px - 2 * margin - title_height
        group_height = 2 * self.cell_size + self.config.line_spacing
        if group_height <= 0:
            return 1
        max_groups = usable_height // group_height
        return max(1, max_groups)

    def _draw_article_page(self, text_lines):
        img = Image.new("RGB", (self.config.width_px, self.config.height_px), "white")
        draw = ImageDraw.Draw(img)

        char_font_size = int(self.cell_size * self.config.char_font_ratio)
        title_font_size = int(char_font_size * 0.8)

        try:
            font_char = ImageFont.truetype(self.font_path, char_font_size) if self.font_path else ImageFont.load_default()
            font_title = ImageFont.truetype(self.font_path, title_font_size) if self.font_path else ImageFont.load_default()
        except:
            font_char = ImageFont.load_default()
            font_title = ImageFont.load_default()

        margin = self.config.margin_px
        if self.config.title:
            title_bbox = draw.textbbox((0, 0), self.config.title, font=font_title)
            title_w = title_bbox[2] - title_bbox[0]
            title_x = (self.config.width_px - title_w) / 2
            title_y = margin // 2
            draw.text((title_x, title_y), self.config.title, font=font_title, fill=(0, 0, 0))
            title_height = title_y + (title_bbox[3] - title_bbox[1]) + 20
        else:
            title_height = 0

        start_y = margin + title_height
        cols = self.config.cols_per_row

        for line_idx, line_chars in enumerate(text_lines):
            line_top_y = start_y + line_idx * (2 * self.cell_size + self.config.line_spacing)
            trace_y = line_top_y
            blank_y = line_top_y + self.cell_size

            for col in range(cols):
                x_left = margin + col * (self.cell_size + self.config.cell_spacing)
                x_right = x_left + self.cell_size
                y1 = trace_y
                y2 = trace_y + self.cell_size
                self._draw_grid(draw, x_left, y1, x_right, y2)
                if col < len(line_chars):
                    ch = line_chars[col]
                    self._draw_text_centered(draw, x_left, y1, x_right, y2, ch, font_char, self.gray_color)

            for col in range(cols):
                x_left = margin + col * (self.cell_size + self.config.cell_spacing)
                x_right = x_left + self.cell_size
                y1 = blank_y
                y2 = blank_y + self.cell_size
                self._draw_grid(draw, x_left, y1, x_right, y2)

        return img

    def generate_article_pdf(self, article_text, output_pdf_path=None):
        if output_pdf_path is None:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            output_pdf_path = os.path.join(desktop, "文章练字字帖.pdf")

        all_text_lines = self._split_article_into_lines(article_text)
        if not all_text_lines:
            raise ValueError("文章内容为空")

        max_text_lines_per_page = self._compute_text_rows_per_page()
        if max_text_lines_per_page == 0:
            raise RuntimeError("页面高度不足以放下任何一行文本")

        pages_lines = []
        for i in range(0, len(all_text_lines), max_text_lines_per_page):
            page_lines = all_text_lines[i:i+max_text_lines_per_page]
            if len(page_lines) < max_text_lines_per_page:
                page_lines += [[] for _ in range(max_text_lines_per_page - len(page_lines))]
            pages_lines.append(page_lines)

        images = []
        for idx, page_lines in enumerate(pages_lines, start=1):
            img = self._draw_article_page(page_lines)
            images.append(img)
            actual_lines = sum(1 for line in page_lines if line)
            print(f"生成第 {idx} 页，共 {max_text_lines_per_page} 行（实际 {actual_lines} 行）")

        if len(images) == 1:
            images[0].save(output_pdf_path, save_all=True, dpi=(self.config.dpi, self.config.dpi))
        else:
            images[0].save(output_pdf_path, save_all=True, append_images=images[1:], dpi=(self.config.dpi, self.config.dpi))

        print(f"文章字帖 PDF 已保存至: {output_pdf_path}")
        return output_pdf_path

    # ---------- 多故事自动分页 ----------
    def generate_stories_pdf(self, stories_text, split_pattern=None, strip_star=True, output_pdf_path=None):
        if output_pdf_path is None:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            output_pdf_path = os.path.join(desktop, "多故事练字字帖.pdf")

        if split_pattern is None:
            split_pattern = r'\n\s*\n'
        raw_stories = re.split(split_pattern, stories_text.strip())
        raw_stories = [s.strip() for s in raw_stories if s.strip()]

        if not raw_stories:
            raise ValueError("没有检测到任何故事内容")

        processed_stories = []
        for story in raw_stories:
            if strip_star:
                lines = story.split('\n')
                new_lines = []
                for line in lines:
                    line = re.sub(r'^\*\*(.*?)\*\*$', r'\1', line.strip())
                    new_lines.append(line)
                story = '\n'.join(new_lines)
            processed_stories.append(story)

        max_text_lines_per_page = self._compute_text_rows_per_page()
        if max_text_lines_per_page == 0:
            raise RuntimeError("页面高度不足以放下任何一行文本")

        all_page_lines = []
        cur_page_lines = []

        for story_idx, story_text in enumerate(processed_stories):
            story_lines = self._split_article_into_lines(story_text)
            if not story_lines:
                continue

            if story_idx > 0 and cur_page_lines:
                if len(cur_page_lines) < max_text_lines_per_page:
                    cur_page_lines += [[] for _ in range(max_text_lines_per_page - len(cur_page_lines))]
                all_page_lines.append(cur_page_lines)
                cur_page_lines = []

            for line_chars in story_lines:
                cur_page_lines.append(line_chars)
                if len(cur_page_lines) >= max_text_lines_per_page:
                    all_page_lines.append(cur_page_lines)
                    cur_page_lines = []

        if cur_page_lines:
            if len(cur_page_lines) < max_text_lines_per_page:
                cur_page_lines += [[] for _ in range(max_text_lines_per_page - len(cur_page_lines))]
            all_page_lines.append(cur_page_lines)

        if not all_page_lines:
            raise RuntimeError("没有生成任何页面")

        images = []
        for idx, page_lines in enumerate(all_page_lines, start=1):
            img = self._draw_article_page(page_lines)
            images.append(img)
            actual_lines = sum(1 for line in page_lines if line)
            print(f"生成第 {idx} 页，共 {max_text_lines_per_page} 行（实际 {actual_lines} 行）")

        if len(images) == 1:
            images[0].save(output_pdf_path, save_all=True, dpi=(self.config.dpi, self.config.dpi))
        else:
            images[0].save(output_pdf_path, save_all=True, append_images=images[1:], dpi=(self.config.dpi, self.config.dpi))

        print(f"多故事字帖 PDF 已保存至: {output_pdf_path}")
        return output_pdf_path

# ========================== Flask Web 应用 ==========================
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

script_dir = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(script_dir, "temp_files")
os.makedirs(TEMP_DIR, exist_ok=True)
import atexit
def cleanup_temp():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
atexit.register(cleanup_temp)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0,2,4))
    return (70, 175, 70)

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>练字字帖生成器</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: #f5f7fa;
            margin: 0;
            padding: 20px;
            color: #1e293b;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 24px;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1);
            padding: 24px 28px;
        }
        h1 {
            font-size: 1.8rem;
            margin-top: 0;
            margin-bottom: 0.25rem;
            color: #0f3b2c;
        }
        .sub {
            color: #475569;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 12px;
            margin-bottom: 24px;
        }
        .config-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 18px;
            background: #f8fafc;
            padding: 20px;
            border-radius: 20px;
            margin-bottom: 24px;
        }
        .param-group label {
            display: block;
            font-weight: 600;
            font-size: 0.85rem;
            margin-bottom: 6px;
            color: #0f3b2c;
        }
        .param-group input, .param-group select {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            font-size: 0.9rem;
            background: white;
        }
        .param-group input[type="color"] {
            height: 38px;
            padding: 2px;
        }
        .param-group small {
            font-size: 0.7rem;
            color: #64748b;
        }
        .button-row {
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        .btn {
            flex: 1;
            background: #1e4620;
            border: none;
            padding: 12px 16px;
            border-radius: 40px;
            font-weight: bold;
            font-size: 1rem;
            color: white;
            cursor: pointer;
            transition: 0.2s;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .btn:hover { background: #2d6a2d; transform: translateY(-1px); }
        .btn:active { transform: translateY(1px); }
        .text-area-box {
            margin: 20px 0;
        }
        textarea {
            width: 100%;
            min-height: 220px;
            padding: 14px;
            font-family: monospace;
            font-size: 14px;
            border: 1px solid #cbd5e1;
            border-radius: 20px;
            resize: vertical;
        }
        .status {
            margin-top: 20px;
            background: #f1f5f9;
            padding: 12px 16px;
            border-radius: 28px;
            font-size: 0.9rem;
            color: #0f3b2c;
        }
        footer {
            margin-top: 30px;
            text-align: center;
            font-size: 0.75rem;
            color: #94a3b8;
        }
    </style>
</head>
<body>
<div class="container">
    <h1>📝 练字字帖生成器</h1>
    <div class="sub">田字格描红｜支持字体上传｜三合一模式</div>

    <form id="genForm" enctype="multipart/form-data">
        <div class="config-grid">
            <div class="param-group">
                <label>📁 本地字体 (.ttf/.otf)</label>
                <input type="file" name="font_file" accept=".ttf,.otf,.TTF,.OTF">
                <small>不选则使用系统默认楷体/黑体</small>
            </div>
            <div class="param-group">
                <label>🎨 格子边框颜色</label>
                <input type="color" name="border_color" value="#47af47">
            </div>
            <div class="param-group">
                <label>📏 灰度系数 (0黑~1淡)</label>
                <input type="range" name="gray_factor" min="0" max="1" step="0.01" value="0.20">
                <span id="grayVal">0.20</span>
            </div>
            <div class="param-group">
                <label>🔢 每行格子数</label>
                <input type="number" name="cols_per_row" min="5" max="20" value="16" step="1">
            </div>
            <div class="param-group">
                <label>📄 纸张</label>
                <select name="page_size">
                    <option value="A4">A4 (210x297mm)</option>
                    <option value="custom">自定义(mm)</option>
                </select>
                <div id="customSize" style="display:none; margin-top:6px;">
                    <input type="number" name="width_mm" placeholder="宽度mm" value="210" step="1"> x
                    <input type="number" name="height_mm" placeholder="高度mm" value="297" step="1">
                </div>
            </div>
            <div class="param-group">
                <label>📐 边距 (mm)</label>
                <input type="number" name="margin_mm" value="12" step="1" min="5">
            </div>
            <div class="param-group">
                <label>✍️ 字体比例 (字大小/格子)</label>
                <input type="number" name="char_font_ratio" value="0.72" step="0.02" min="0.5" max="0.85">
            </div>
            <div class="param-group">
                <label>🏷️ 标题</label>
                <input type="text" name="title" value="幼小衔接练字帖" placeholder="留空则不显示">
            </div>
            <div class="param-group">
                <label>📏 格子间距(px)</label>
                <input type="number" name="cell_spacing" value="0" step="1">
            </div>
            <div class="param-group">
                <label>📐 行间距(px)</label>
                <input type="number" name="line_spacing" value="0" step="1">
            </div>
            <div class="param-group">
                <label>🎨 辅助线颜色</label>
                <input type="color" name="dash_color" value="#c0c0c0">
            </div>
            <div class="param-group">
                <label>🖨️ DPI</label>
                <input type="number" name="dpi" value="300" step="50" min="150">
            </div>
        </div>

        <div class="button-row">
            <button type="submit" data-mode="basic" class="btn">📖 基础字帖 (单字列表)</button>
            <button type="submit" data-mode="article" class="btn">📜 文章字帖</button>
            <button type="submit" data-mode="stories" class="btn">📚 多故事字帖</button>
        </div>

        <div class="text-area-box">
            <label style="font-weight:600;">✏️ 文本内容</label>
            <textarea name="content_text" placeholder="【基础模式】输入汉字序列（自动按字符拆分）
【文章模式】输入整篇文章（支持古诗/短文）
【故事模式】输入多个故事，用空行分隔">天地人你我他</textarea>
        </div>
    </form>

    <div id="status" class="status">⚙️ 配置好参数后，点击上方按钮生成 PDF</div>
    <footer>生成后自动下载 PDF | 临时文件会在程序关闭后清理</footer>
</div>

<script>
    const form = document.getElementById('genForm');
    const statusDiv = document.getElementById('status');
    const graySlider = document.querySelector('input[name="gray_factor"]');
    const graySpan = document.getElementById('grayVal');
    const pageSizeSelect = document.querySelector('select[name="page_size"]');
    const customDiv = document.getElementById('customSize');

    graySlider.addEventListener('input', () => {
        graySpan.innerText = parseFloat(graySlider.value).toFixed(2);
    });
    pageSizeSelect.addEventListener('change', () => {
        customDiv.style.display = pageSizeSelect.value === 'custom' ? 'flex' : 'none';
    });

    async function generate(mode) {
        const formData = new FormData(form);
        formData.append('action', mode);
        statusDiv.innerHTML = '⏳ 正在生成字帖，请稍等...';
        try {
            const response = await fetch('/generate', {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                const err = await response.text();
                throw new Error(err || '生成失败');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `汉字字帖练习_${mode}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            statusDiv.innerHTML = '✅ 生成成功！PDF 已下载。';
        } catch (err) {
            statusDiv.innerHTML = `❌ 错误：${err.message}`;
        }
    }

    const btns = document.querySelectorAll('.btn');
    btns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const mode = btn.getAttribute('data-mode');
            generate(mode);
        });
    });
</script>
</body>
</html>'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate_pdf_web():
    try:
        action = request.form.get('action')
        if not action or action not in ('basic', 'article', 'stories'):
            return "无效的生成模式", 400

        content = request.form.get('content_text', '').strip()
        if not content:
            return "文本内容不能为空", 400

        gray_factor = float(request.form.get('gray_factor', 0.28))
        cols_per_row = int(request.form.get('cols_per_row', 14))
        margin_mm = int(request.form.get('margin_mm', 12))
        dpi = int(request.form.get('dpi', 300))
        title = request.form.get('title', '').strip()
        char_font_ratio = float(request.form.get('char_font_ratio', 0.72))
        cell_spacing = int(request.form.get('cell_spacing', 0))
        line_spacing = int(request.form.get('line_spacing', 0))
        border_color_hex = request.form.get('border_color', '#47af47')
        dash_color_hex = request.form.get('dash_color', '#c0c0c0')

        page_size_val = request.form.get('page_size', 'A4')
        if page_size_val == 'custom':
            try:
                w_mm = int(request.form.get('width_mm', 210))
                h_mm = int(request.form.get('height_mm', 297))
                page_size = (w_mm, h_mm)
            except:
                page_size = 'A4'
        else:
            page_size = 'A4'

        font_path = None
        uploaded_font = request.files.get('font_file')
        if uploaded_font and uploaded_font.filename:
            ext = os.path.splitext(uploaded_font.filename)[1].lower()
            if ext in ['.ttf', '.otf']:
                temp_font = os.path.join(TEMP_DIR, f"user_font_{os.urandom(4).hex()}{ext}")
                uploaded_font.save(temp_font)
                font_path = temp_font

        border_color = hex_to_rgb(border_color_hex)
        dash_color = hex_to_rgb(dash_color_hex)

        out_pdf = os.path.join(TEMP_DIR, f"output_{action}_{os.urandom(6).hex()}.pdf")

        if action == 'basic':
            char_list = [ch for ch in content if ch.strip() and not ch.isspace()]
            if not char_list:
                return "基础模式需要至少一个有效汉字", 400
            config = CalligraphyConfig(
                char_list=char_list,
                gray_factor=gray_factor,
                cols_per_row=cols_per_row,
                page_size=page_size,
                dpi=dpi,
                margin_mm=margin_mm,
                title=title if title else None,
                font_path=font_path,
                border_color=border_color,
                dash_color=dash_color,
                cell_spacing=cell_spacing,
                line_spacing=line_spacing,
                char_font_ratio=char_font_ratio
            )
            generator = CalligraphyGenerator(config)
            generator.generate_pdf(out_pdf)
        elif action == 'article':
            config = CalligraphyConfig(
                char_list=["占"],
                gray_factor=gray_factor,
                cols_per_row=cols_per_row,
                page_size=page_size,
                dpi=dpi,
                margin_mm=margin_mm,
                title=title if title else None,
                font_path=font_path,
                border_color=border_color,
                dash_color=dash_color,
                cell_spacing=cell_spacing,
                line_spacing=line_spacing,
                char_font_ratio=char_font_ratio
            )
            generator = CalligraphyGenerator(config)
            generator.generate_article_pdf(content, out_pdf)
        else:  # stories
            config = CalligraphyConfig(
                char_list=["占"],
                gray_factor=gray_factor,
                cols_per_row=cols_per_row,
                page_size=page_size,
                dpi=dpi,
                margin_mm=margin_mm,
                title=title if title else None,
                font_path=font_path,
                border_color=border_color,
                dash_color=dash_color,
                cell_spacing=cell_spacing,
                line_spacing=line_spacing,
                char_font_ratio=char_font_ratio
            )
            generator = CalligraphyGenerator(config)
            generator.generate_stories_pdf(content, output_pdf_path=out_pdf)

        if not os.path.exists(out_pdf):
            return f"PDF 文件未生成，请检查控制台错误", 500

        return send_file(out_pdf, as_attachment=True, download_name=f"练字字帖_{action}.pdf")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"服务器内部错误: {str(e)}", 500

if __name__ == '__main__':
    print("="*50)
    print("✨ 练字字帖生成器 - 独立 Web 版")
    print("👉 正在自动打开浏览器...")
    print("📁 临时目录:", TEMP_DIR)
    print("="*50)
    threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000')).start()
    app.run(debug=False, host='127.0.0.1', port=5000)