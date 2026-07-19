"""
字体配置 - 单一数据源
所有字体相关逻辑统一在此文件管理，前后端共用
"""
import subprocess
import logging

logger = logging.getLogger("subtitle-burner")

# 常见中文字体到 Noto CJK 的映射（处理 Windows/macOS 字体名在 Linux 不可用的情况）
FONT_ALIASES = {
    # Windows 字体
    "Microsoft YaHei": "Noto Sans CJK SC",
    "SimHei": "Noto Sans CJK SC",
    "SimSun": "Noto Serif CJK SC",
    "KaiTi": "Noto Sans CJK SC",
    "FangSong": "Noto Serif CJK SC",
    "STSong": "Noto Serif CJK SC",
    "STHeiti": "Noto Sans CJK SC",
    # macOS 字体
    "PingFang SC": "Noto Sans CJK SC",
    "PingFang TC": "Noto Sans CJK TC",
    "STXihei": "Noto Sans CJK SC",
    "Songti SC": "Noto Serif CJK SC",
    # 思源（Source Han = Noto CJK 的别名）
    "Source Han Sans SC": "Noto Sans CJK SC",
    "Source Han Serif SC": "Noto Serif CJK SC",
    "Source Han Sans TC": "Noto Sans CJK TC",
    "Source Han Serif TC": "Noto Serif CJK TC",
    # 通用名
    "sans-serif": "Noto Sans CJK SC",
    "serif": "Noto Serif CJK SC",
    "monospace": "Noto Sans Mono CJK SC",
}

# 字体分类：用于前端下拉菜单分组（只显示容器内实际可用的字体）
FONT_CATEGORIES = {
    "Google Noto 中文简体": [
        "Noto Sans CJK SC",
        "Noto Sans CJK SC Light",
        "Noto Sans CJK SC Medium",
        "Noto Sans CJK SC Bold",
        "Noto Serif CJK SC",
        "Noto Serif CJK SC Light",
        "Noto Serif CJK SC Bold",
    ],
    "Google Noto 中文繁体": [
        "Noto Sans CJK TC",
        "Noto Serif CJK TC",
    ],
    "文泉驿字体": [
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
    ],
}


def _get_system_fonts():
    """通过 fc-list 检测系统已安装的字体"""
    try:
        result = subprocess.run(
            ["fc-list", ":lang=zh", "family"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            logger.warning("fc-list 执行失败，使用默认字体列表")
            return _get_default_fonts()

        fonts = set()
        for line in result.stdout.strip().split("\n"):
            name = line.strip().rstrip(",")
            if name:
                fonts.add(name)
        return sorted(fonts) if fonts else _get_default_fonts()
    except Exception as e:
        logger.warning(f"检测系统字体失败: {e}，使用默认字体列表")
        return _get_default_fonts()


def _get_default_fonts():
    """fc-list 不可用时的默认字体列表"""
    return [
        "Noto Sans CJK SC",
        "Noto Sans CJK SC Light",
        "Noto Sans CJK SC Medium",
        "Noto Sans CJK SC Bold",
        "Noto Serif CJK SC",
        "Noto Serif CJK SC Light",
        "Noto Serif CJK SC Bold",
        "Noto Sans CJK TC",
        "Noto Serif CJK TC",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
    ]


def get_available_fonts():
    """获取可用字体列表（带分类，供前端使用）"""
    installed = _get_system_fonts()

    available = []
    for category, fonts in FONT_CATEGORIES.items():
        category_fonts = []
        for font in fonts:
            # 实际安装的字体，或者能映射到已安装字体的别名
            actual = FONT_ALIASES.get(font, font)
            if actual in installed or font in installed:
                category_fonts.append(font)
        if category_fonts:
            available.append({
                "category": category,
                "fonts": category_fonts
            })

    return available


def resolve_font(font_family):
    """将用户选择的字体名解析为实际可用的字体名"""
    return FONT_ALIASES.get(font_family, font_family)
