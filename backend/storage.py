"""
数据存储模块 - 用于保存订单历史记录
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class OrderStorage:
    """订单存储类"""

    def __init__(self, storage_dir: str = 'data'):
        """
        初始化存储

        Args:
            storage_dir: 存储目录
        """
        self.storage_dir = storage_dir
        self.orders_file = os.path.join(storage_dir, 'orders.json')
        self.ensure_storage_dir()

    def ensure_storage_dir(self):
        """确保存储目录存在"""
        os.makedirs(self.storage_dir, exist_ok=True)

        if not os.path.exists(self.orders_file):
            with open(self.orders_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False)

    def save_order(self, order_data: Dict) -> str:
        """
        保存订单记录

        Args:
            order_data: 订单数据

        Returns:
            订单ID
        """
        order_id = datetime.now().strftime('%Y%m%d%H%M%S%f')

        record = {
            'order_id': order_id,
            'timestamp': datetime.now().isoformat(),
            'data': order_data
        }

        # 读取现有订单
        orders = self.load_all_orders()
        orders.append(record)

        # 保存
        with open(self.orders_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)

        return order_id

    def load_all_orders(self) -> List[Dict]:
        """
        加载所有订单记录

        Returns:
            订单列表
        """
        if not os.path.exists(self.orders_file):
            return []

        with open(self.orders_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_order_by_id(self, order_id: str) -> Optional[Dict]:
        """
        根据ID获取订单

        Args:
            order_id: 订单ID

        Returns:
            订单记录或None
        """
        orders = self.load_all_orders()
        for order in orders:
            if order['order_id'] == order_id:
                return order
        return None

    def get_orders_by_stock(self, stock_code: str) -> List[Dict]:
        """
        获取某只股票的所有订单

        Args:
            stock_code: 股票代码

        Returns:
            订单列表
        """
        orders = self.load_all_orders()
        return [
            order for order in orders
            if order['data'].get('stock_code') == stock_code
        ]

    def get_recent_orders(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的订单

        Args:
            limit: 返回数量

        Returns:
            订单列表
        """
        orders = self.load_all_orders()
        return orders[-limit:][::-1]  # 倒序返回最近的

    def delete_order(self, order_id: str) -> bool:
        """
        删除订单记录

        Args:
            order_id: 订单ID

        Returns:
            是否成功
        """
        orders = self.load_all_orders()
        new_orders = [o for o in orders if o['order_id'] != order_id]

        if len(new_orders) == len(orders):
            return False

        with open(self.orders_file, 'w', encoding='utf-8') as f:
            json.dump(new_orders, f, ensure_ascii=False, indent=2)

        return True

    def get_statistics(self) -> Dict:
        """
        获取统计信息

        Returns:
            统计数据
        """
        orders = self.load_all_orders()

        if not orders:
            return {
                'total_orders': 0,
                'total_stocks': 0,
                'total_amount': 0,
                'first_order_date': None,
                'last_order_date': None
            }

        stocks = set()
        total_amount = 0

        for order in orders:
            data = order['data']
            stocks.add(data.get('stock_code', ''))
            total_amount += data.get('total_amount', 0)

        return {
            'total_orders': len(orders),
            'total_stocks': len(stocks),
            'total_amount': total_amount,
            'first_order_date': orders[0]['timestamp'],
            'last_order_date': orders[-1]['timestamp']
        }


if __name__ == '__main__':
    # 测试代码
    storage = OrderStorage('test_data')

    # 测试保存订单
    test_order = {
        'stock_code': 'sh.600000',
        'total_amount': 100000,
        'orders': [
            {'price': 12.5, 'amount': 14000},
            {'price': 12.3, 'amount': 14000}
        ]
    }

    order_id = storage.save_order(test_order)
    print(f"订单已保存，ID: {order_id}")

    # 测试读取订单
    order = storage.get_order_by_id(order_id)
    print(f"\n读取订单: {order}")

    # 测试统计
    stats = storage.get_statistics()
    print(f"\n统计信息: {stats}")

    # 清理测试数据
    import shutil
    shutil.rmtree('test_data')
    print("\n测试完成，已清理测试数据")
