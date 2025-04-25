import re


def _extract_food_items(content):
    """
    提取食物名称和对应的热量
    ([^：:\n]+)      捕获组1：匹配食物名称，直到遇到冒号
    [：:]            匹配中文冒号 `：` 或 英文冒号 `:`
    (?:约)?	        非捕获组（?: 表示不存入匹配组），匹配可选的 "约"
    (\d+(\.\d+)?)	捕获组 2：匹配 卡路里数值（整数或小数）
    (\.\d+)?	    捕获组 3：匹配 小数部分（可选）
    千卡	            匹配 "千卡" 这个单位（不会被捕获
    """
    food_items = []
    food_pattern = r'([^.：:\n]+)\s*[：:]\s*(?:约)?\s*(\d+(\.\d+)?)\s*千卡'
    matches = re.finditer(food_pattern, content)
    for match in matches:
        food_name = match.group(1).strip()
        calories = float(match.group(2))
        if food_name == "总热量":
            continue
        food_items.append({'food_name': food_name, 'calories': calories})
    return food_items

content = """图中展示了1个食物：李子

1. 李子: 约47千卡

其中碳水化合物占比约14%，蛋白质占比约0.6%，脂类占比约0.2%，膳食纤维占比约1.5%，维生素占比约0.1%"""
nutrient_ratios = _extract_food_items(content)
print(nutrient_ratios)


