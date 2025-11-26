"""
XTTrader 交易接口封装
"""
from typing import List, Dict, Optional, Any
import logging
import time
import threading

logger = logging.getLogger(__name__)

try:
    from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
    from xtquant.xttype import StockAccount
    from xtquant import xtconstant
    XTQUANT_AVAILABLE = True
except ImportError:
    XTQUANT_AVAILABLE = False
    logger.warning("xtquant未安装，将使用模拟模式")


# 常量定义
LOT_SIZE = 100  # 每手股数（A股标准）
MIN_LOT_SIZE = 100  # 最小交易单位


# 回调类定义（仅在xtquant可用时）
if XTQUANT_AVAILABLE:
    class XTTraderCallback(XtQuantTraderCallback):
        """XTTrader回调处理器"""
        
        def on_disconnected(self):
            """连接断开回调"""
            logger.warning("XTTrader连接已断开")
            # 注意：这里不能直接调用reconnect，因为可能在回调线程中
            # 实际的连接状态会在下次操作时通过check_connection检测
        
        def on_stock_order(self, order):
            """
            委托回报推送
            
            Args:
                order: XtOrder对象
            """
            logger.info(
                f"委托回报: 股票={order.stock_code}, "
                f"状态={order.order_status}, 系统ID={order.order_sysid}"
            )
        
        def on_stock_trade(self, trade):
            """
            成交变动推送
            
            Args:
                trade: XtTrade对象
            """
            logger.info(
                f"成交回报: 账户={trade.account_id}, "
                f"股票={trade.stock_code}, 订单ID={trade.order_id}"
            )
        
        def on_order_error(self, order_error):
            """
            委托失败推送
            
            Args:
                order_error: XtOrderError对象
            """
            logger.error(
                f"委托失败: 订单ID={order_error.order_id}, "
                f"错误码={order_error.error_id}, 错误信息={order_error.error_msg}"
            )
        
        def on_cancel_error(self, cancel_error):
            """
            撤单失败推送
            
            Args:
                cancel_error: XtCancelError对象
            """
            logger.error(
                f"撤单失败: 订单ID={cancel_error.order_id}, "
                f"错误码={cancel_error.error_id}, 错误信息={cancel_error.error_msg}"
            )
        
        def on_order_stock_async_response(self, response):
            """
            异步下单回报推送
            
            Args:
                response: XtOrderResponse对象
            """
            logger.info(
                f"异步下单回报: 账户={response.account_id}, "
                f"订单ID={response.order_id}, 序列号={response.seq}"
            )
        
        def on_account_status(self, status):
            """
            账户状态变更推送
            
            Args:
                status: XtAccountStatus对象
            """
            logger.info(
                f"账户状态: 账户ID={status.account_id}, "
                f"账户类型={status.account_type}, 状态={status.status}"
            )
else:
    # 模拟模式下的占位类
    class XTTraderCallback:
        """XTTrader回调处理器（模拟模式）"""
        pass

class XTTraderClient:
    """XTTrader交易客户端"""
    
    def __init__(self, path: str = "", account_id: str = "", account_type: str = "STOCK", session_id: Optional[int] = None):
        """
        初始化XTTrader客户端

        Args:
            path: XTTrader路径（mini qmt客户端安装目录下userdata_mini路径）
            account_id: 账户ID
            account_type: 账户类型，如'STOCK'（默认）、'HUGANGTONG'（沪港通）、'SHENGANGTONG'（深港通）
            session_id: 会话编号，策略使用方对于不同的Python策略需要使用不同的会话编号。如果为None，则使用时间戳
        """
        self.path = path
        self.session_id = session_id if session_id is not None else int(time.time())
        self.account_id = account_id
        self.account_type = account_type
        self.is_connected = False
        self.is_mock_mode = not XTQUANT_AVAILABLE
        self._last_heartbeat = None
        self._reconnect_lock = threading.Lock()
        
        # 初始化交易接口
        self.xttrader: Optional[Any] = None
        self.account: Optional[Any] = None
        self.callback: Optional[Any] = None
        
        if not self.is_mock_mode:
            try:
                self.xttrader = XtQuantTrader(self.path, self.session_id)
                self.account = StockAccount(self.account_id, self.account_type)
                self.callback = XTTraderCallback()
                self.xttrader.register_callback(self.callback)
                logger.info("XTTrader客户端初始化成功")
            except Exception as e:
                logger.error(f"XTTrader初始化失败: {e}，切换到模拟模式")
                self.is_mock_mode = True
        else:
            logger.info("使用模拟模式（xtquant未安装）")

    def connect(self) -> bool:
        """
        连接到XTTrader

        Returns:
            是否连接成功
        """
        if self.is_mock_mode:
            logger.info("模拟模式：连接成功")
            self.is_connected = True
            return True

        if self.xttrader is None:
            logger.error("XTTrader未初始化")
            return False

        try:
            # 启动连接
            self.xttrader.start()
            
            # 建立连接
            connect_result = self.xttrader.connect()
            if connect_result != 0:
                logger.error(f"XTTrader连接失败，错误码: {connect_result}")
                return False
            
            # 订阅账户
            subscribe_result = self.xttrader.subscribe(self.account)
            if subscribe_result != 0:
                logger.error(f"XTTrader订阅失败，错误码: {subscribe_result}")
                self.is_connected = False
                return False
            
            self.is_connected = True
            self._last_heartbeat = time.time()
            logger.info(f"XTTrader连接成功，账户: {self.account_id}")
            return True
            
        except Exception as e:
            logger.error(f"XTTrader连接异常: {e}", exc_info=True)
            self.is_connected = False
            return False

    def check_connection(self) -> bool:
        """
        检查连接状态，如果断开则尝试重连
        
        Returns:
            连接是否正常
        """
        if self.is_mock_mode:
            return self.is_connected
        
        if not self.is_connected:
            logger.warning("连接已断开，尝试重连...")
            return self.connect()
        
        # 尝试查询资产来检测连接是否真的有效
        try:
            # 简单的连接检测：如果xttrader对象存在且已连接，认为连接正常
            if self.xttrader is not None:
                self._last_heartbeat = time.time()
                return True
            else:
                logger.warning("xttrader对象不存在，需要重连")
                return self.reconnect()
        except Exception as e:
            logger.warning(f"连接检测异常: {e}，尝试重连")
            return self.reconnect()

    def reconnect(self) -> bool:
        """
        重新连接XTTrader
        
        Returns:
            是否重连成功
        """
        with self._reconnect_lock:
            if self.is_connected:
                try:
                    self.disconnect()
                except Exception as e:
                    logger.warning(f"断开旧连接时出错: {e}")
            
            logger.info("开始重连XTTrader...")
            return self.connect()


    def place_order(
        self,
        stock_code: str,
        price: float,
        volume: int,
        direction: str = "buy",
        order_type: str = "limit",
        strategy_name: str = "strategy1",
        remark: str = ""
    ) -> Dict[str, Any]:
        """
        下单

        Args:
            stock_code: 股票代码
            price: 价格
            volume: 数量（股）
            direction: 交易方向，'buy'=买入，'sell'=卖出
            order_type: 订单类型 (limit=限价单, market=市价单)，当前仅支持限价单
            strategy_name: 策略名称
            remark: 备注

        Returns:
            订单结果字典，包含 success, order_id, message
        """
        # 检查并确保连接
        if not self.check_connection():
            error_msg = "未连接到XTTrader，重连失败"
            logger.error(error_msg)
            return {
                'success': False,
                'order_id': None,
                'message': error_msg
            }

        # 参数验证
        if price <= 0:
            error_msg = f"价格必须大于0，当前价格: {price}"
            logger.error(error_msg)
            return {
                'success': False,
                'order_id': None,
                'message': error_msg
            }
        
        if volume < MIN_LOT_SIZE or volume % LOT_SIZE != 0:
            error_msg = f"数量必须是{LOT_SIZE}的整数倍，当前数量: {volume}"
            logger.error(error_msg)
            return {
                'success': False,
                'order_id': None,
                'message': error_msg
            }

        # 确定交易方向
        if direction.lower() == "buy":
            stock_side = xtconstant.STOCK_BUY if not self.is_mock_mode else "BUY"
        elif direction.lower() == "sell":
            stock_side = xtconstant.STOCK_SELL if not self.is_mock_mode else "SELL"
        else:
            error_msg = f"交易方向必须是'buy'或'sell'，当前: {direction}"
            logger.error(error_msg)
            return {
                'success': False,
                'order_id': None,
                'message': error_msg
            }

        # 模拟模式
        if self.is_mock_mode:
            order_id = f"MOCK_{stock_code}_{int(time.time())}"
            logger.info(f"模拟下单: {stock_code}, 方向: {direction}, 价格: {price}, 数量: {volume}, 订单ID: {order_id}")
            return {
                'success': True,
                'order_id': order_id,
                'message': '模拟订单已提交'
            }

        # 实际下单
        try:
            order_id = self.xttrader.order_stock(
                self.account,
                stock_code,
                stock_side,
                volume,
                xtconstant.FIX_PRICE,
                price,
                strategy_name,
                remark or 'order_test'
            )
            logger.info(f"下单成功: {stock_code}, 方向: {direction}, 价格: {price}, 数量: {volume}, 订单ID: {order_id}")
            return {
                'success': True,
                'order_id': order_id,
                'message': '订单已提交'
            }
        except Exception as e:
            error_msg = f"下单失败: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'order_id': None,
                'message': error_msg
            }

    def _calculate_volume(self, amount: float, price: float) -> int:
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
        # 计算可以买多少股，向下取整到100的倍数
        total_shares = int(amount / price)
        return (total_shares // LOT_SIZE) * LOT_SIZE

    def batch_place_orders(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量下单

        Args:
            orders: 订单列表，每个订单包含 stock_code, price, amount

        Returns:
            订单结果列表，每个结果包含 order, success, order_id, volume, message
        """
        if not orders:
            logger.warning("批量下单：订单列表为空")
            return []

        results = []
        logger.info(f"开始批量下单，共 {len(orders)} 个订单")

        for idx, order in enumerate(orders, 1):
            try:
                stock_code = order.get('stock_code', '').strip()
                price = float(order.get('price', 0))
                amount = float(order.get('amount', 0))

                # 参数验证
                if not stock_code:
                    results.append({
                        'order': order,
                        'success': False,
                        'message': '股票代码不能为空'
                    })
                    continue

                if price <= 0:
                    results.append({
                        'order': order,
                        'success': False,
                        'message': f'价格必须大于0，当前价格: {price}'
                    })
                    continue

                if amount <= 0:
                    results.append({
                        'order': order,
                        'success': False,
                        'message': f'金额必须大于0，当前金额: {amount}'
                    })
                    continue

                # 计算股数
                volume = self._calculate_volume(amount, price)

                if volume < MIN_LOT_SIZE:
                    min_amount = price * MIN_LOT_SIZE
                    results.append({
                        'order': order,
                        'success': False,
                        'message': f'金额不足一手（需要至少 {min_amount:.2f} 元）'
                    })
                    continue

                # 下单
                result = self.place_order(stock_code, price, volume)
                results.append({
                    'order': order,
                    'success': result['success'],
                    'order_id': result.get('order_id'),
                    'volume': volume,
                    'message': result['message']
                })

            except (ValueError, KeyError) as e:
                logger.error(f"处理订单 {idx} 时出错: {e}")
                results.append({
                    'order': order,
                    'success': False,
                    'message': f'订单参数错误: {str(e)}'
                })

        success_count = sum(1 for r in results if r['success'])
        logger.info(f"批量下单完成: 成功 {success_count}/{len(orders)}")
        return results

    def cancel_order(self, order_id: Any) -> Dict[str, Any]:
        """
        撤单

        Args:
            order_id: 订单编号

        Returns:
            撤单结果字典，包含 success, message
        """
        # 检查并确保连接
        if not self.check_connection():
            error_msg = "未连接到XTTrader，重连失败"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg
            }

        if self.is_mock_mode:
            logger.info(f"模拟撤单: 订单ID={order_id}")
            return {
                'success': True,
                'message': '模拟撤单已提交'
            }

        try:
            cancel_result = self.xttrader.cancel_order_stock(self.account, order_id)
            if cancel_result == 0:
                logger.info(f"撤单成功: 订单ID={order_id}")
                return {
                    'success': True,
                    'message': '撤单已提交'
                }
            else:
                error_msg = f"撤单失败，错误码: {cancel_result}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
        except Exception as e:
            error_msg = f"撤单异常: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def place_order_async(
        self,
        stock_code: str,
        price: float,
        volume: int,
        direction: str = "buy",
        strategy_name: str = "strategy1",
        remark: str = ""
    ) -> Dict[str, Any]:
        """
        异步下单

        Args:
            stock_code: 股票代码
            price: 价格
            volume: 数量（股）
            direction: 交易方向，'buy'=买入，'sell'=卖出
            strategy_name: 策略名称
            remark: 备注

        Returns:
            下单结果字典，包含 success, seq, message
            注意：seq是下单请求序号，可以和on_order_stock_async_response的委托反馈response对应起来
        """
        # 检查并确保连接
        if not self.check_connection():
            error_msg = "未连接到XTTrader，重连失败"
            logger.error(error_msg)
            return {
                'success': False,
                'seq': None,
                'message': error_msg
            }

        # 参数验证
        if price <= 0:
            error_msg = f"价格必须大于0，当前价格: {price}"
            logger.error(error_msg)
            return {
                'success': False,
                'seq': None,
                'message': error_msg
            }
        
        if volume < MIN_LOT_SIZE or volume % LOT_SIZE != 0:
            error_msg = f"数量必须是{LOT_SIZE}的整数倍，当前数量: {volume}"
            logger.error(error_msg)
            return {
                'success': False,
                'seq': None,
                'message': error_msg
            }

        # 确定交易方向
        if direction.lower() == "buy":
            stock_side = xtconstant.STOCK_BUY if not self.is_mock_mode else "BUY"
        elif direction.lower() == "sell":
            stock_side = xtconstant.STOCK_SELL if not self.is_mock_mode else "SELL"
        else:
            error_msg = f"交易方向必须是'buy'或'sell'，当前: {direction}"
            logger.error(error_msg)
            return {
                'success': False,
                'seq': None,
                'message': error_msg
            }

        if self.is_mock_mode:
            seq = int(time.time())
            logger.info(f"模拟异步下单: {stock_code}, 方向: {direction}, 价格: {price}, 数量: {volume}, 序列号: {seq}")
            return {
                'success': True,
                'seq': seq,
                'message': '模拟异步订单已提交'
            }

        try:
            seq = self.xttrader.order_stock_async(
                self.account,
                stock_code,
                stock_side,
                volume,
                xtconstant.FIX_PRICE,
                price,
                strategy_name,
                remark or 'order_test'
            )
            logger.info(f"异步下单成功: {stock_code}, 方向: {direction}, 价格: {price}, 数量: {volume}, 序列号: {seq}")
            return {
                'success': True,
                'seq': seq,
                'message': '异步订单已提交'
            }
        except Exception as e:
            error_msg = f"异步下单失败: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'seq': None,
                'message': error_msg
            }

    def query_asset(self) -> Optional[Dict[str, Any]]:
        """
        查询证券资产

        Returns:
            资产信息字典，包含 cash 等字段，如果查询失败返回None
        """
        # 检查并确保连接
        if not self.check_connection():
            logger.error("未连接到XTTrader，重连失败")
            return None

        if self.is_mock_mode:
            logger.info("模拟模式：查询资产")
            return {
                'cash': 100000.0,
                'total_asset': 100000.0,
                'market_value': 0.0
            }

        try:
            asset = self.xttrader.query_stock_asset(self.account)
            if asset:
                result = {
                    'cash': asset.cash,
                    'total_asset': getattr(asset, 'total_asset', asset.cash),
                    'market_value': getattr(asset, 'market_value', 0.0)
                }
                logger.info(f"查询资产成功: 现金={result['cash']}")
                return result
            else:
                logger.warning("查询资产返回空结果")
                return None
        except Exception as e:
            logger.error(f"查询资产失败: {e}", exc_info=True)
            return None

    def query_order(self, order_id: Any) -> Optional[Dict[str, Any]]:
        """
        根据订单编号查询委托

        Args:
            order_id: 订单编号

        Returns:
            委托信息字典，如果查询失败返回None
        """
        # 检查并确保连接
        if not self.check_connection():
            logger.error("未连接到XTTrader，重连失败")
            return None

        if self.is_mock_mode:
            logger.info(f"模拟模式：查询订单 {order_id}")
            return {
                'order_id': order_id,
                'stock_code': '000001.SZ',
                'order_volume': 100,
                'price': 10.0
            }

        try:
            order = self.xttrader.query_stock_order(self.account, order_id)
            if order:
                result = {
                    'order_id': order.order_id,
                    'stock_code': order.stock_code,
                    'order_volume': order.order_volume,
                    'price': order.price,
                    'order_status': getattr(order, 'order_status', None),
                    'order_sysid': getattr(order, 'order_sysid', None)
                }
                logger.info(f"查询订单成功: 订单ID={order_id}")
                return result
            else:
                logger.warning(f"查询订单返回空结果: 订单ID={order_id}")
                return None
        except Exception as e:
            logger.error(f"查询订单失败: {e}", exc_info=True)
            return None

    def query_orders(self) -> List[Dict[str, Any]]:
        """
        查询当日所有的委托

        Returns:
            委托信息列表
        """
        # 检查并确保连接
        if not self.check_connection():
            logger.error("未连接到XTTrader，重连失败")
            return []

        if self.is_mock_mode:
            logger.info("模拟模式：查询所有订单")
            return []

        try:
            orders = self.xttrader.query_stock_orders(self.account)
            results = []
            for order in orders:
                results.append({
                    'order_id': order.order_id,
                    'stock_code': order.stock_code,
                    'order_volume': order.order_volume,
                    'price': order.price,
                    'order_status': getattr(order, 'order_status', None),
                    'order_sysid': getattr(order, 'order_sysid', None)
                })
            logger.info(f"查询所有订单成功: 共 {len(results)} 条")
            return results
        except Exception as e:
            logger.error(f"查询所有订单失败: {e}", exc_info=True)
            return []

    def query_trades(self) -> List[Dict[str, Any]]:
        """
        查询当日所有的成交

        Returns:
            成交信息列表
        """
        # 检查并确保连接
        if not self.check_connection():
            logger.error("未连接到XTTrader，重连失败")
            return []

        if self.is_mock_mode:
            logger.info("模拟模式：查询所有成交")
            return []

        try:
            trades = self.xttrader.query_stock_trades(self.account)
            results = []
            for trade in trades:
                results.append({
                    'account_id': trade.account_id,
                    'stock_code': trade.stock_code,
                    'order_id': trade.order_id,
                    'traded_volume': trade.traded_volume,
                    'traded_price': trade.traded_price
                })
            logger.info(f"查询所有成交成功: 共 {len(results)} 条")
            return results
        except Exception as e:
            logger.error(f"查询所有成交失败: {e}", exc_info=True)
            return []

    def query_positions(self) -> List[Dict[str, Any]]:
        """
        查询当日所有的持仓

        Returns:
            持仓信息列表
        """
        # 检查并确保连接
        if not self.check_connection():
            logger.error("未连接到XTTrader，重连失败")
            return []

        if self.is_mock_mode:
            logger.info("模拟模式：查询所有持仓")
            return []

        try:
            positions = self.xttrader.query_stock_positions(self.account)
            results = []
            for position in positions:
                results.append({
                    'account_id': position.account_id,
                    'stock_code': position.stock_code,
                    'volume': position.volume,
                    'can_use_volume': getattr(position, 'can_use_volume', position.volume),
                    'avg_price': getattr(position, 'avg_price', 0.0)
                })
            logger.info(f"查询所有持仓成功: 共 {len(results)} 条")
            return results
        except Exception as e:
            logger.error(f"查询所有持仓失败: {e}", exc_info=True)
            return []

    def query_position(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        根据股票代码查询对应持仓

        Args:
            stock_code: 股票代码

        Returns:
            持仓信息字典，如果查询失败或没有持仓返回None
        """
        # 检查并确保连接
        if not self.check_connection():
            logger.error("未连接到XTTrader，重连失败")
            return None

        if self.is_mock_mode:
            logger.info(f"模拟模式：查询持仓 {stock_code}")
            return None

        try:
            position = self.xttrader.query_stock_position(self.account, stock_code)
            if position:
                result = {
                    'account_id': position.account_id,
                    'stock_code': position.stock_code,
                    'volume': position.volume,
                    'can_use_volume': getattr(position, 'can_use_volume', position.volume),
                    'avg_price': getattr(position, 'avg_price', 0.0)
                }
                logger.info(f"查询持仓成功: {stock_code}, 数量={result['volume']}")
                return result
            else:
                logger.info(f"查询持仓返回空结果: {stock_code}（可能没有持仓）")
                return None
        except Exception as e:
            logger.error(f"查询持仓失败: {e}", exc_info=True)
            return None

    def run_forever(self):
        """
        阻塞线程，接收交易推送
        注意：此方法会阻塞当前线程，通常用于主程序保持运行
        """
        if not self.is_connected:
            logger.error("未连接到XTTrader，请先调用connect()")
            return

        if self.is_mock_mode:
            logger.info("模拟模式：run_forever() 不会阻塞")
            return

        try:
            logger.info("开始阻塞线程，接收交易推送...")
            self.xttrader.run_forever()
        except Exception as e:
            logger.error(f"run_forever异常: {e}", exc_info=True)

    def disconnect(self):
        """断开连接"""
        if not self.is_connected:
            logger.debug("未连接，无需断开")
            return

        if self.is_mock_mode:
            logger.info("模拟模式：断开连接")
            self.is_connected = False
            return

        try:
            # 实际断开逻辑（如果需要调用API，在这里添加）
            self.is_connected = False
            logger.info("XTTrader已断开连接")
        except Exception as e:
            logger.error(f"断开连接时出错: {e}", exc_info=True)
            self.is_connected = False


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    client = XTTraderClient(
        path="D:\\华宝证券QMT实盘交易端 - yh\\userdata_mini",
        account_id='090000014536'
    )
    
    if client.connect():
        result = client.place_order('301591.SH', 41.47, 200)
        print(result)
        client.disconnect()
    else:
        print("连接失败")
