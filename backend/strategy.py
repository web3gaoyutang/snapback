"""
斐波那契回调金字塔建仓策略
"""
import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional


class FibonacciPyramidStrategy:
    """斐波那契回调金字塔建仓策略"""

    def __init__(self):
        self.is_logged_in = False

    def login_baostock(self):
        """登录baostock"""
        if not self.is_logged_in:
            lg = bs.login()
            if lg.error_code != '0':
                raise Exception(f"baostock登录失败: {lg.error_msg}")
            self.is_logged_in = True

    def logout_baostock(self):
        """登出baostock"""
        if self.is_logged_in:
            bs.logout()
            self.is_logged_in = False

    def find_latest_limit_up(self, stock_code: str, days: int = 60) -> Optional[Dict]:
        """
        查找最近的涨停日期

        Args:
            stock_code: 股票代码 (如 sh.600000 或 sz.000001)
            days: 往前查找的天数

        Returns:
            涨停日期信息字典，包含日期、最高价、最低价等
        """
        self.login_baostock()

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # 获取历史K线数据
        rs = bs.query_history_k_data_plus(
            stock_code,
            "date,code,open,high,low,close,preclose,volume,amount,pctChg",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 不复权
        )

        if rs.error_code != '0':
            raise Exception(f"获取历史数据失败: {rs.error_msg}")

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        df = pd.DataFrame(data_list, columns=rs.fields)

        # 转换数据类型
        df['pctChg'] = pd.to_numeric(df['pctChg'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['open'] = pd.to_numeric(df['open'], errors='coerce')

        # 删除无效数据
        df = df.dropna()

        # 查找涨停（涨幅接近10%，ST股票是5%）
        # 这里使用9.5%作为涨停阈值，因为实际涨停可能略小于10%
        limit_up_df = df[df['pctChg'] >= 9.5].sort_values('date', ascending=False)

        if len(limit_up_df) == 0:
            return None

        # 获取最近一次涨停
        latest_limit_up = limit_up_df.iloc[0]
        limit_up_date = latest_limit_up['date']

        # 获取涨停后到现在的数据，用于计算最高点和最低点
        limit_up_index = df[df['date'] == limit_up_date].index[0]
        after_limit_df = df.iloc[limit_up_index:]

        highest_price = after_limit_df['high'].max()
        lowest_price = after_limit_df['low'].min()

        return {
            'limit_up_date': limit_up_date,
            'limit_up_price': float(latest_limit_up['close']),
            'highest_price': float(highest_price),
            'lowest_price': float(lowest_price),
            'current_price': float(df.iloc[-1]['close']),
            'stock_code': stock_code
        }

    def calculate_fibonacci_levels(self, high: float, low: float) -> Dict[str, float]:
        """
        计算斐波那契回调位

        Args:
            high: 最高价
            low: 最低价

        Returns:
            各个回调位的价格
        """
        diff = high - low

        return {
            '0.382': high - diff * 0.382,
            '0.500': high - diff * 0.500,
            '0.618': high - diff * 0.618,
            '0.700': high - diff * 0.700,
            '0.786': high - diff * 0.786,
        }

    def generate_pyramid_orders(
        self,
        stock_code: str,
        total_amount: float
    ) -> Dict:
        """
        生成金字塔建仓订单

        策略：
        - 0.5-0.618回调：分5次进7成仓（每次14%）
        - 0.618-0.7回调：分3次进3成仓（每次10%）

        Args:
            stock_code: 股票代码
            total_amount: 总投资金额

        Returns:
            订单信息字典
        """
        # 查找涨停信息
        limit_info = self.find_latest_limit_up(stock_code)

        if limit_info is None:
            raise Exception(f"未找到股票 {stock_code} 最近60天的涨停记录")

        high = limit_info['highest_price']
        low = limit_info['lowest_price']

        # 计算斐波那契回调位
        fib_levels = self.calculate_fibonacci_levels(high, low)

        # 生成订单
        orders = []

        # 第一阶段：0.5-0.618回调，分5次进7成仓
        stage1_amount = total_amount * 0.7
        stage1_per_order = stage1_amount / 5
        price_range_1 = np.linspace(fib_levels['0.500'], fib_levels['0.618'], 5)

        for i, price in enumerate(price_range_1):
            orders.append({
                'stage': 1,
                'order_no': i + 1,
                'price': round(price, 2),
                'amount': round(stage1_per_order, 2),
                'percentage': 14.0,
                'description': f'第一阶段第{i+1}单 (0.5-0.618回调区间)'
            })

        # 第二阶段：0.618-0.7回调，分3次进3成仓
        stage2_amount = total_amount * 0.3
        stage2_per_order = stage2_amount / 3
        price_range_2 = np.linspace(fib_levels['0.618'], fib_levels['0.700'], 3)

        for i, price in enumerate(price_range_2):
            orders.append({
                'stage': 2,
                'order_no': i + 1,
                'price': round(price, 2),
                'amount': round(stage2_per_order, 2),
                'percentage': 10.0,
                'description': f'第二阶段第{i+1}单 (0.618-0.7回调区间)'
            })

        return {
            'stock_code': stock_code,
            'total_amount': total_amount,
            'limit_up_info': limit_info,
            'fibonacci_levels': fib_levels,
            'orders': orders,
            'summary': {
                'total_orders': len(orders),
                'stage1_orders': 5,
                'stage1_amount': round(stage1_amount, 2),
                'stage2_orders': 3,
                'stage2_amount': round(stage2_amount, 2)
            }
        }


if __name__ == '__main__':
    # 测试代码
    strategy = FibonacciPyramidStrategy()
    try:
        result = strategy.generate_pyramid_orders('sh.600000', 100000)
        print("订单生成成功:")
        print(f"股票代码: {result['stock_code']}")
        print(f"总金额: {result['total_amount']}")
        print(f"\n涨停信息:")
        print(f"  涨停日期: {result['limit_up_info']['limit_up_date']}")
        print(f"  最高价: {result['limit_up_info']['highest_price']}")
        print(f"  最低价: {result['limit_up_info']['lowest_price']}")
        print(f"  当���价: {result['limit_up_info']['current_price']}")
        print(f"\n斐波那契回调位:")
        for level, price in result['fibonacci_levels'].items():
            print(f"  {level}: {price:.2f}")
        print(f"\n订单明细:")
        for order in result['orders']:
            print(f"  {order['description']}: 价格 {order['price']}, 金额 {order['amount']}")
    finally:
        strategy.logout_baostock()
