"""
XTTrader 交易接口封装
"""
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

from xtquant.xttrader import XtQuantTrader,XtQuantTraderCallback
from xtquant.xttype import StockAccount
from xtquant import xtconstant
import time


class MyXtQuantTraderCallback(XtQuantTraderCallback):
    def on_disconnected(self):
        """
        连接断开
        :return:
        """
        print("connection lost")
    def on_stock_order(self, order):
        """
        委托回报推送
        :param order: XtOrder对象
        :return:
        """
        print("on order callback:")
        print(order.stock_code, order.order_status, order.order_sysid)
    def on_stock_trade(self, trade):
        """
        成交变动推送
        :param trade: XtTrade对象
        :return:
        """
        print("on trade callback")
        print(trade.account_id, trade.stock_code, trade.order_id)
    def on_order_error(self, order_error):
        """
        委托失败推送
        :param order_error:XtOrderError 对象
        :return:
        """
        print("on order_error callback")
        print(order_error.order_id, order_error.error_id, order_error.error_msg)
    def on_cancel_error(self, cancel_error):
        """
        撤单失败推送
        :param cancel_error: XtCancelError 对象
        :return:
        """
        print("on cancel_error callback")
        print(cancel_error.order_id, cancel_error.error_id, cancel_error.error_msg)
    def on_order_stock_async_response(self, response):
        """
        异步下单回报推送
        :param response: XtOrderResponse 对象
        :return:
        """
        print("on_order_stock_async_response")
        print(response.account_id, response.order_id, response.seq)
    def on_account_status(self, status):
        """
        :param response: XtAccountStatus 对象
        :return:
        """
        print("on_account_status")
        print(status.account_id, status.account_type, status.status)

class XTTraderClient:
    """XTTrader交易客户端"""
    def __init__(self, path: str = "", account_id: str = ""):
        """
        初始化XTTrader客户端

        Args:
            path: 路径
            session_id: 会话ID
            account_id: 账户ID
        """
        self.path = path
        self.session_id = int(time.time())
        self.account_id = account_id
        self.is_connected = False

        # 尝试导入xtquant，如果没有安装则使用模拟模式
        try:
            self.xttrader = XtQuantTrader(self.path, self.session_id)
            self.account = StockAccount(self.account_id)
            self.callback = MyXtQuantTraderCallback()
            self.xttrader.register_callback(self.callback)
        except ImportError:
            logger.warning("xtquant未安装，使用模拟模式")
            self.xttrader = None
            self.account = None

    def connect(self) -> bool:
        """
        连接到XTTrader

        Returns:
            是否连接成功
        """
        if self.xttrader is None:
            logger.info("模拟模式：连接成功")
            self.is_connected = True
            return True

        try:
            # 实际连接逻辑
            self.xttrader.start()
            connect_result = self.xttrader.connect()
            if connect_result != 0:
                logger.error(f"XTTrader连接失败: {connect_result}")
                return False
            self.is_connected = True
            subscribe_result = self.xttrader.subscribe(self.account)
            if subscribe_result != 0:
                logger.error(f"XTTrader订阅失败: {subscribe_result}")
                return False
            logger.info("XTTrader连接成功")
            return True
        except Exception as e:
            logger.error(f"XTTrader连接失败: {e}")
            return False


    def place_order(
        self,
        stock_code: str,
        price: float,
        volume: int,
        order_type: str = "limit"
    ) -> Dict:
        """
        下单

        Args:
            stock_code: 股票代码
            price: 价格
            volume: 数量（股）
            order_type: 订单类型 (limit=限价单, market=市价单)

        Returns:
            订单结果
        """
        if not self.is_connected:
            raise Exception("未连接到XTTrader")

        if self.xttrader is None:
            # 模拟模式
            logger.info(f"模拟下单: {stock_code}, 价格: {price}, 数量: {volume}")
            return {
                'success': True,
                'order_id': f"MOCK_{stock_code}_{price}_{volume}",
                'message': '模拟订单已提交'
            }

        try:
            # 实际下单逻辑
            order_id = self.xttrader.order_stock(self.account, stock_code, xtconstant.STOCK_BUY, volume, xtconstant.FIX_PRICE, price, 'strategy1', 'order_test')
            return {
                'success': True,
                'order_id': order_id,
                'message': '订单已提交'
            }
        except Exception as e:
            logger.error(f"下单失败: {e}")
            return {
                'success': False,
                'order_id': None,
                'message': str(e)
            }

    def batch_place_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量下单

        Args:
            orders: 订单列表，每个订单包含 stock_code, price, amount

        Returns:
            订单结果列表
        """
        results = []

        for order in orders:
            stock_code = order['stock_code']
            price = order['price']
            amount = order['amount']

            # 计算股数（每手100股）
            volume = int(amount / price / 100) * 100

            if volume < 100:
                results.append({
                    'order': order,
                    'success': False,
                    'message': f'金额不足一手（需要至少 {price * 100:.2f} 元）'
                })
                continue

            result = self.place_order(stock_code, price, volume)
            results.append({
                'order': order,
                'success': result['success'],
                'order_id': result.get('order_id'),
                'volume': volume,
                'message': result['message']
            })

        return results

    def disconnect(self):
        """断开连接"""
        if self.xttrader is None:
            logger.info("模拟模式：断开连接")
            self.is_connected = False
            return

        try:
            # 实际断开逻辑
            self.is_connected = False
            logger.info("XTTrader已断开")
        except Exception as e:
            logger.error(f"断开连接失败: {e}")


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    import time
    client = XTTraderClient(
        path="D:\\华宝证券QMT实盘交易端 - yh\\userdata_mini",session_id=int(time.time()),account_id='090000014536'
    )
    client.connect()

    result = client.place_order('301591.SH', 41.47, 200)
    print(result)

    client.disconnect()
