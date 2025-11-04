"""
工具函数模块
"""
from datetime import datetime, timedelta
import re


def validate_stock_code(stock_code: str) -> tuple[bool, str]:
    """
    验证股票代码格式

    Args:
        stock_code: 股票代码

    Returns:
        (是否有效, 标准化后的代码或错误信息)
    """
    if not stock_code:
        return False, "股票代码不能为空"

    stock_code = stock_code.strip().lower()

    # 如果已经有前缀
    if stock_code.startswith('sh.') or stock_code.startswith('sz.'):
        code_num = stock_code[3:]
        if not code_num.isdigit() or len(code_num) != 6:
            return False, "股票代码格式错误，应为6位数字"
        return True, stock_code

    # 没有前缀，自动添加
    if not stock_code.isdigit() or len(stock_code) != 6:
        return False, "股票代码格式错误，应为6位数字"

    # 6开头是上海
    if stock_code.startswith('6'):
        return True, f'sh.{stock_code}'
    # 0、3开头是深圳
    elif stock_code.startswith(('0', '3')):
        return True, f'sz.{stock_code}'
    else:
        return False, "无法识别的股票代码，上海以6开头，深圳以0或3开头"


def format_money(amount: float) -> str:
    """
    格式化金额显示

    Args:
        amount: 金额

    Returns:
        格式化后的字符串
    """
    if amount >= 100000000:  # 1亿
        return f'{amount/100000000:.2f}亿'
    elif amount >= 10000:  # 1万
        return f'{amount/10000:.2f}万'
    else:
        return f'{amount:.2f}'


def calculate_shares(amount: float, price: float) -> int:
    """
    根据金额和价格计算可购买的股数（向下取整到100的倍数）

    Args:
        amount: 金额
        price: 价格

    Returns:
        股数（必定是100的倍数）
    """
    if price <= 0:
        return 0

    # 计算可以买多少股
    total_shares = int(amount / price)

    # 向下取整到100的倍数（一手）
    shares = (total_shares // 100) * 100

    return shares


def get_trading_days(start_date: str, end_date: str) -> list[str]:
    """
    获取两个日期之间的交易日（简化版，不考虑节假日）

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        交易日列表
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    trading_days = []
    current = start

    while current <= end:
        # 周一到周五是交易日（不考虑节假日）
        if current.weekday() < 5:
            trading_days.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)

    return trading_days


def calculate_profit(
    buy_price: float,
    current_price: float,
    shares: int
) -> dict:
    """
    计算盈亏

    Args:
        buy_price: 买入价格
        current_price: 当前价格
        shares: 持仓股数

    Returns:
        盈亏信息字典
    """
    cost = buy_price * shares
    current_value = current_price * shares
    profit = current_value - cost
    profit_rate = (profit / cost * 100) if cost > 0 else 0

    return {
        'cost': cost,
        'current_value': current_value,
        'profit': profit,
        'profit_rate': profit_rate
    }


def get_risk_level(fib_level: float) -> str:
    """
    根据斐波那契回调位评估风险等级

    Args:
        fib_level: 斐波那契回调位（0-1之间）

    Returns:
        风险等级描述
    """
    if fib_level < 0.382:
        return "极低风险"
    elif fib_level < 0.5:
        return "低风险"
    elif fib_level < 0.618:
        return "中等风险"
    elif fib_level < 0.786:
        return "较高风险"
    else:
        return "高风险"


def generate_order_description(
    stage: int,
    order_no: int,
    fib_level: float,
    total_orders: int
) -> str:
    """
    生成订单描述

    Args:
        stage: 阶段（1或2）
        order_no: 订单号
        fib_level: 斐波那契回调位
        total_orders: 总订单数

    Returns:
        订单描述
    """
    risk = get_risk_level(fib_level)
    return f"第{stage}阶段 第{order_no}单 ({fib_level:.3f}回调位, {risk})"


if __name__ == '__main__':
    # 测试代码
    print("=== 股票代码验证测试 ===")
    test_codes = ['600000', 'sh.600000', '000001', 'sz.000001', '300750', '123456', 'abc']
    for code in test_codes:
        valid, result = validate_stock_code(code)
        print(f"{code:15} -> {result}")

    print("\n=== 金额格式化测试 ===")
    amounts = [1000, 15000, 100000, 1500000, 50000000, 120000000]
    for amount in amounts:
        print(f"{amount:12} -> {format_money(amount)}")

    print("\n=== 股数计算测试 ===")
    tests = [(10000, 10.5), (50000, 15.8), (5000, 100)]
    for amount, price in tests:
        shares = calculate_shares(amount, price)
        actual_cost = shares * price
        print(f"金额: {amount}, 价格: {price} -> {shares}股, 实际花费: {actual_cost:.2f}")

    print("\n=== 盈亏计算测试 ===")
    profit_info = calculate_profit(10.5, 12.0, 1000)
    print(f"买入价: 10.5, 当前价: 12.0, 持仓: 1000股")
    print(f"成本: {profit_info['cost']}, 市值: {profit_info['current_value']}")
    print(f"盈亏: {profit_info['profit']:.2f}, 收益率: {profit_info['profit_rate']:.2f}%")

    print("\n=== 风险等级测试 ===")
    levels = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    for level in levels:
        print(f"{level:.3f} -> {get_risk_level(level)}")
