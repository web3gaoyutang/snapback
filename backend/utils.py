"""
工具函数模块
"""
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, List, Dict, Any
import re
import json
import os
import logging

logger = logging.getLogger(__name__)

# baostock 交易日缓存
_trading_day_cache: Dict[str, bool] = {}
_baostock_logged_in = False


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


def get_trading_days(start_date: str, end_date: str, use_baostock: bool = True) -> list[str]:
    """
    获取两个日期之间的交易日（使用 baostock 查询，考虑节假日）

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        use_baostock: 是否使用 baostock 查询，默认True

    Returns:
        交易日列表
    """
    if use_baostock:
        try:
            import baostock as bs
            _ensure_baostock_login()
            
            if _baostock_logged_in:
                # 使用 baostock 查询交易日
                rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
                
                if rs.error_code == '0':
                    trading_days = []
                    while (rs.error_code == '0') & rs.next():
                        row_data = rs.get_row_data()
                        # row_data[0] 是日期，row_data[1] 是 is_trading_day ('1' 或 '0')
                        if row_data[1] == '1':  # 是交易日
                            trading_days.append(row_data[0])
                    return trading_days
                else:
                    logger.warning(f"baostock 查询交易日失败: {rs.error_msg}，使用简单判断")
        except ImportError:
            logger.debug("baostock 未安装，使用简单判断")
        except Exception as e:
            logger.warning(f"baostock 查询异常: {e}，使用简单判断")
    
    # 回退到简单判断
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    trading_days = []
    current = start

    while current <= end:
        if current.weekday() < 5:  # 周一到周五
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


def _ensure_baostock_login():
    """确保 baostock 已登录"""
    global _baostock_logged_in
    if not _baostock_logged_in:
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code == '0':
                _baostock_logged_in = True
                logger.debug("baostock 登录成功")
            else:
                logger.warning(f"baostock 登录失败: {lg.error_msg}")
        except ImportError:
            logger.warning("baostock 未安装，将使用简单判断")
        except Exception as e:
            logger.warning(f"baostock 登录异常: {e}")


def is_trading_day(date: Optional[datetime] = None, use_cache: bool = True) -> bool:
    """
    判断是否为交易日（使用 baostock 查询，考虑节假日）

    Args:
        date: 日期，如果为None则使用当前日期
        use_cache: 是否使用缓存，默认True

    Returns:
        是否为交易日
    """
    if date is None:
        date = datetime.now()
    
    # 格式化日期为字符串
    date_str = date.strftime('%Y-%m-%d')
    
    # 检查缓存
    if use_cache and date_str in _trading_day_cache:
        return _trading_day_cache[date_str]
    
    # 首先进行简单判断（周末肯定不是交易日）
    if date.weekday() >= 5:  # 周六、周日
        _trading_day_cache[date_str] = False
        return False
    
    # 尝试使用 baostock 查询
    try:
        import baostock as bs
        _ensure_baostock_login()
        
        if _baostock_logged_in:
            # 查询指定日期是否为交易日
            # baostock 的 query_trade_dates 接口
            rs = bs.query_trade_dates(start_date=date_str, end_date=date_str)
            
            if rs.error_code == '0':
                # 解析结果
                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    # 检查 is_trading_day 字段，'1' 表示交易日，'0' 表示非交易日
                    is_trading = data_list[0][1] == '1'
                    _trading_day_cache[date_str] = is_trading
                    return is_trading
                else:
                    # 如果没有数据，可能是非交易日
                    logger.debug(f"baostock 未返回 {date_str} 的数据，假设为非交易日")
                    _trading_day_cache[date_str] = False
                    return False
            else:
                logger.warning(f"baostock 查询交易日失败: {rs.error_msg}，使用简单判断")
                # 回退到简单判断
                is_trading = date.weekday() < 5
                _trading_day_cache[date_str] = is_trading
                return is_trading
        else:
            # baostock 未登录，使用简单判断
            logger.debug("baostock 未登录，使用简单判断")
            is_trading = date.weekday() < 5
            _trading_day_cache[date_str] = is_trading
            return is_trading
            
    except ImportError:
        # baostock 未安装，使用简单判断
        logger.debug("baostock 未安装，使用简单判断")
        is_trading = date.weekday() < 5
        _trading_day_cache[date_str] = is_trading
        return is_trading
    except Exception as e:
        # 查询异常，使用简单判断
        logger.warning(f"查询交易日异常: {e}，使用简单判断")
        is_trading = date.weekday() < 5
        _trading_day_cache[date_str] = is_trading
        return is_trading


def get_market_hours() -> tuple[dt_time, dt_time, dt_time, dt_time]:
    """
    获取A股交易时间

    Returns:
        (上午开盘时间, 上午收盘时间, 下午开盘时间, 下午收盘时间)
    """
    # A股交易时间：
    # 上午：9:30 - 11:30
    # 下午：13:00 - 15:00
    morning_open = dt_time(9, 30)
    morning_close = dt_time(11, 30)
    afternoon_open = dt_time(13, 0)
    afternoon_close = dt_time(15, 0)
    
    return morning_open, morning_close, afternoon_open, afternoon_close


def is_trading_time(current_time: Optional[datetime] = None) -> bool:
    """
    判断当前是否在交易时间内

    Args:
        current_time: 当前时间，如果为None则使用当前时间

    Returns:
        是否在交易时间内
    """
    if current_time is None:
        current_time = datetime.now()
    
    if not is_trading_day(current_time):
        return False
    
    morning_open, morning_close, afternoon_open, afternoon_close = get_market_hours()
    current_time_only = current_time.time()
    
    # 检查是否在上午交易时间或下午交易时间
    is_morning = morning_open <= current_time_only <= morning_close
    is_afternoon = afternoon_open <= current_time_only <= afternoon_close
    
    return is_morning or is_afternoon


def get_next_trading_day(date: Optional[datetime] = None) -> datetime:
    """
    获取下一个交易日（使用 baostock 查询）

    Args:
        date: 起始日期，如果为None则使用当前日期

    Returns:
        下一个交易日
    """
    if date is None:
        date = datetime.now()
    
    # 最多查询未来30天
    max_days = 30
    next_day = date + timedelta(days=1)
    days_checked = 0
    
    while days_checked < max_days:
        if is_trading_day(next_day):
            return next_day
        next_day += timedelta(days=1)
        days_checked += 1
    
    # 如果30天内没找到，返回计算出的日期（可能不准确）
    logger.warning(f"在 {max_days} 天内未找到下一个交易日，返回计算日期")
    return next_day


def get_market_close_time(date: Optional[datetime] = None) -> datetime:
    """
    获取指定交易日的收盘时间

    Args:
        date: 日期，如果为None则使用当前日期

    Returns:
        收盘时间（当天15:00）
    """
    if date is None:
        date = datetime.now()
    
    return date.replace(hour=15, minute=0, second=0, microsecond=0)


def get_market_open_time(date: Optional[datetime] = None) -> datetime:
    """
    获取指定交易日的开盘时间

    Args:
        date: 日期，如果为None则使用当前日期

    Returns:
        开盘时间（当天9:30）
    """
    if date is None:
        date = datetime.now()
    
    return date.replace(hour=9, minute=30, second=0, microsecond=0)


def save_pending_orders(orders: List[Dict[str, Any]], file_path: str = "pending_orders.json") -> bool:
    """
    保存待重新下单的订单列表

    Args:
        orders: 订单列表
        file_path: 保存文件路径

    Returns:
        是否保存成功
    """
    try:
        data = {
            'save_time': datetime.now().isoformat(),
            'orders': orders
        }
        
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存待下单订单失败: {e}")
        return False


def load_pending_orders(file_path: str = "pending_orders.json") -> List[Dict[str, Any]]:
    """
    加载待重新下单的订单列表

    Args:
        file_path: 文件路径

    Returns:
        订单列表，如果文件不存在或读取失败返回空列表
    """
    try:
        if not os.path.exists(file_path):
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('orders', [])
    except Exception as e:
        print(f"加载待下单订单失败: {e}")
        return []


def clear_pending_orders(file_path: str = "pending_orders.json") -> bool:
    """
    清除待重新下单的订单列表

    Args:
        file_path: 文件路径

    Returns:
        是否清除成功
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as e:
        print(f"清除待下单订单失败: {e}")
        return False


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
