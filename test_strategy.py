"""
测试脚本 - 测试策略功能
"""
import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from strategy import FibonacciPyramidStrategy
from utils import validate_stock_code, format_money, calculate_shares


def test_strategy():
    """测试策略"""
    print("=" * 60)
    print("斐波那契金字塔建仓策略测试")
    print("=" * 60)

    # 测试股票代码
    test_codes = ['600000', 'sh.600519', '000001', 'sz.000001', '300750']

    strategy = FibonacciPyramidStrategy()

    for code in test_codes:
        print(f"\n{'=' * 60}")
        print(f"测试股票: {code}")
        print('=' * 60)

        try:
            # 验证代码
            valid, result = validate_stock_code(code)
            if not valid:
                print(f"❌ 股票代码无效: {result}")
                continue

            stock_code = result
            total_amount = 100000

            print(f"✅ 标准化代码: {stock_code}")
            print(f"💰 总投资金额: {format_money(total_amount)}")

            # 生成订单
            print("\n🔍 正在分析...")
            order_result = strategy.generate_pyramid_orders(stock_code, total_amount)

            # 显示涨停信息
            limit_info = order_result['limit_up_info']
            print(f"\n📊 涨停信息:")
            print(f"  涨停日期: {limit_info['limit_up_date']}")
            print(f"  涨停价格: ¥{limit_info['limit_up_price']:.2f}")
            print(f"  最高价格: ¥{limit_info['highest_price']:.2f}")
            print(f"  最低价格: ¥{limit_info['lowest_price']:.2f}")
            print(f"  当前价格: ¥{limit_info['current_price']:.2f}")

            # 显示斐波那契回调位
            fib_levels = order_result['fibonacci_levels']
            print(f"\n📐 斐波那契回调位:")
            for level, price in sorted(fib_levels.items()):
                print(f"  {level} 回调: ¥{price:.2f}")

            # 显示订单摘要
            summary = order_result['summary']
            print(f"\n📋 订单摘要:")
            print(f"  总订单数: {summary['total_orders']}")
            print(f"  第一阶段: {summary['stage1_orders']}单, {format_money(summary['stage1_amount'])}")
            print(f"  第二阶段: {summary['stage2_orders']}单, {format_money(summary['stage2_amount'])}")

            # 显示订单明细
            print(f"\n💼 订单明细:")
            print(f"  {'阶段':<6} {'订单':<6} {'价格':<10} {'金额':<12} {'占比':<8} {'股数':<10}")
            print(f"  {'-' * 70}")

            for order in order_result['orders']:
                shares = calculate_shares(order['amount'], order['price'])
                print(f"  阶段{order['stage']:<4} "
                      f"第{order['order_no']}单  "
                      f"¥{order['price']:<8.2f} "
                      f"¥{order['amount']:<10,.0f} "
                      f"{order['percentage']:<6.1f}% "
                      f"{shares:>8}股")

            print(f"\n✅ {code} 测试完成")

        except Exception as e:
            print(f"\n❌ 测试失败: {e}")

        finally:
            strategy.logout_baostock()

    print(f"\n{'=' * 60}")
    print("所有测试完成")
    print('=' * 60)


if __name__ == '__main__':
    test_strategy()
