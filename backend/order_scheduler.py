"""
订单定时任务调度器
用于在收盘前3分钟检查未成交订单，次交易日开盘后3分钟自动重新下单
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
try:
    from backend.utils import (
        is_trading_day, get_market_close_time, get_market_open_time,
        is_trading_time
    )
    from backend.xt_trader import XTTraderClient
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from backend.utils import (
        is_trading_day, get_market_close_time, get_market_open_time,
        is_trading_time
    )
    from backend.xt_trader import XTTraderClient

logger = logging.getLogger(__name__)


class OrderScheduler:
    """订单定时任务调度器"""
    
    def __init__(self, trader: XTTraderClient, check_interval: int = 60):
        """
        初始化调度器
        
        Args:
            trader: XTTraderClient实例
            check_interval: 检查间隔（秒），默认60秒
        """
        self.trader = trader
        self.check_interval = check_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._last_check_time = None
        self._last_reload_time = None
        self.pending_orders_file = "pending_orders.json"
    
    def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("调度器已在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("订单调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("订单调度器已停止")
    
    def _run(self):
        """调度器主循环"""
        while self.running:
            try:
                now = datetime.now()
                
                # 检查是否是交易日
                if is_trading_day(now):
                    # 检查是否需要检查未成交订单（收盘前3分钟）
                    self._check_pending_orders(now)
                    
                    # 检查是否需要重新下单（开盘后3分钟）
                    self._reload_pending_orders(now)
                
                # 等待指定间隔后再次检查
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"调度器运行异常: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def _check_pending_orders(self, now: datetime):
        """
        检查是否需要检查未成交订单
        
        Args:
            now: 当前时间
        """
        try:
            close_time = get_market_close_time(now)
            check_time = close_time - timedelta(minutes=3)
            
            # 在收盘前3分钟到收盘之间执行检查
            if check_time <= now <= close_time:
                # 避免重复执行（每分钟最多执行一次）
                if (self._last_check_time is None or 
                    (now - self._last_check_time).total_seconds() >= 60):
                    logger.info(f"执行收盘前检查未成交订单，当前时间: {now.strftime('%H:%M:%S')}")
                    pending_orders = self.trader.check_and_save_pending_orders(
                        self.pending_orders_file
                    )
                    self._last_check_time = now
                    if pending_orders:
                        logger.info(f"发现 {len(pending_orders)} 个未成交订单已保存")
        except Exception as e:
            logger.error(f"检查未成交订单时出错: {e}", exc_info=True)
    
    def _reload_pending_orders(self, now: datetime):
        """
        检查是否需要重新下单
        
        Args:
            now: 当前时间
        """
        try:
            open_time = get_market_open_time(now)
            reload_time = open_time + timedelta(minutes=3)
            reload_end_time = open_time + timedelta(minutes=10)
            
            # 在开盘后3分钟到10分钟之间执行重新下单
            if reload_time <= now <= reload_end_time:
                # 避免重复执行（每天最多执行一次）
                today = now.date()
                if (self._last_reload_time is None or 
                    self._last_reload_time.date() != today):
                    logger.info(f"执行开盘后重新下单，当前时间: {now.strftime('%H:%M:%S')}")
                    results = self.trader.reload_pending_orders(
                        self.pending_orders_file
                    )
                    self._last_reload_time = now
                    if results:
                        success_count = sum(1 for r in results if r['new_order_result'].get('success'))
                        logger.info(f"重新下单完成: 成功 {success_count}/{len(results)}")
        except Exception as e:
            logger.error(f"重新下单时出错: {e}", exc_info=True)
    
    def manual_check_pending_orders(self) -> list:
        """
        手动触发检查未成交订单
        
        Returns:
            未成交订单列表
        """
        logger.info("手动触发检查未成交订单")
        return self.trader.check_and_save_pending_orders(self.pending_orders_file)
    
    def manual_reload_pending_orders(self) -> list:
        """
        手动触发重新下单
        
        Returns:
            重新下单结果列表
        """
        logger.info("手动触发重新下单")
        return self.trader.reload_pending_orders(self.pending_orders_file)


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建交易客户端
    trader = XTTraderClient()
    
    if trader.connect():
        # 创建调度器
        scheduler = OrderScheduler(trader)
        scheduler.start()
        
        try:
            # 保持运行
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
            scheduler.stop()
            trader.disconnect()
    else:
        logger.error("连接失败，无法启动调度器")

